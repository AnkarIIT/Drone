"""Run the full brain on a simulated scenario and print a scorecard."""
from __future__ import annotations
import sys
from collections import Counter
import numpy as np

from skybrain.engine import Engine
from skybrain.sim import make_scenario, scan
from skybrain.threat import LEVELS, Site
from skybrain.tracker import Tracker

KIND_EXPECT = {"hostile": "must reach ALERT early", "loiterer": "must reach ALERT (loitering)",
               "benign": "must stay below ALERT", "bird": "must stay IGNORE", "friendly": "must stay IGNORE"}


def run(seed: int = 7, T: int = 240, dt: float = 1.0, verbose: bool = True):
    rng = np.random.default_rng(seed)
    truths, site = make_scenario(rng), Site()
    tracker, engine = Tracker(), Engine(Site(), {"FRIEND-01"})
    votes: dict[int, Counter] = {}          # track id -> Counter(truth id)   (evaluation only)
    seen_conf: set[int] = set()
    inner_entry: dict[int, float] = {}
    log: list[tuple] = []
    for k in range(T):
        t = k * dt
        for tr in truths:
            if t >= tr.t_start and tr.id not in inner_entry and np.linalg.norm(tr.pos[:2]) <= site.r_inner:
                inner_entry[tr.id] = t
        confirmed = tracker.step(t, scan(t, truths, rng))
        for trk in confirmed:
            seen_conf.add(trk.id)
            live = [tr for tr in truths if t >= tr.t_start]
            if live:
                d = [np.linalg.norm(trk.x[:3] - tr.pos) for tr in live]
                if min(d) < 80:
                    votes.setdefault(trk.id, Counter())[live[int(np.argmin(d))].id] += 1
        for e in engine.step(t, confirmed):
            log.append((t, e))
            if e.needs_human:   # simulated operator approves the escalation
                engine.record_decision(t, e.track_id, "operator-1", True, "simulated")
        for tr in truths:
            if t >= tr.t_start:
                tr.step(dt, rng)
    owner = {tid: v.most_common(1)[0][0] for tid, v in votes.items()}
    clutter_tracks = [tid for tid in seen_conf if tid not in owner]
    rows = []
    for tr in truths:
        mine = [tid for tid, o in owner.items() if o == tr.id]
        first = {lv: min((engine.states[tid].first[lv] for tid in mine if lv in engine.states[tid].first), default=None)
                 for lv in (2, 3, 4)}
        peak = max((max(engine.states[tid].first) if engine.states[tid].first else 0 for tid in mine), default=0)
        tr.inner_entry = inner_entry.get(tr.id)
        rows.append((tr, mine, first, peak))
    if verbose:
        print(f"seed={seed}  duration={T}s  clutter/min={0.3 * 60:.0f}\n")
        print(f"{'id':>2} {'kind':9} {'tracks':>6} {'peak level':>10} {'ALERT at':>9} {'enters inner':>13} {'lead':>6}  expectation")
        for tr, mine, first, peak in rows:
            a, ent = first[3], inner_entry.get(tr.id)
            lead = f"{ent - a:5.0f}s" if (a is not None and ent is not None) else "   -  "
            print(f"{tr.id:>2} {tr.kind:9} {len(mine):>6} {LEVELS[peak]:>10} {('t=%.0f' % a) if a is not None else '-':>9} "
                  f"{('t=%.0f' % ent) if ent is not None else '-':>13} {lead:>6}  {KIND_EXPECT[tr.kind]}")
        print(f"\nfalse (clutter) confirmed tracks: {len(clutter_tracks)}  ->  {len(clutter_tracks) / T * 3600:.0f}/hour")
        print(f"audit records: {len(engine.audit.records)}   chain valid: {engine.audit.verify()}")
        engine.audit.save("audit_log.jsonl")
    return rows, clutter_tracks, engine, truths


def batch(n: int = 30) -> None:
    """Monte-Carlo scorecard across n random seeds."""
    threats = caught = harmless = bad_alert = bad_warn = clutter = 0
    leads = []
    for seed in range(100, 100 + n):
        rows, clut, _, _ = run(seed, verbose=False)
        clutter += len(clut)
        for tr, mine, first, peak in rows:
            if tr.kind in ("hostile", "loiterer"):
                threats += 1
                caught += first[3] is not None
                if tr.kind == "hostile" and first[3] is not None and tr.inner_entry is not None:
                    leads.append(tr.inner_entry - first[3])
            else:
                harmless += 1
                bad_alert += peak >= 3
                bad_warn += peak >= 2
    print(f"{n} random runs  ({threats} threats, {harmless} harmless objects)")
    print(f"threats reaching ALERT            : {caught}/{threats}")
    print(f"harmless objects -> ALERT         : {bad_alert}/{harmless}")
    print(f"harmless objects -> WARN or higher: {bad_warn}/{harmless}")
    print(f"false clutter tracks per hour     : {clutter / (n * 240) * 3600:.1f}")
    if leads:
        print(f"hostile warning lead time (ALERT before critical zone): mean {np.mean(leads):.0f}s, worst {min(leads):.0f}s")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "batch":
        batch(int(sys.argv[2]) if len(sys.argv) > 2 else 30)
    else:
        run(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
