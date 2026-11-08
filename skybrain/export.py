"""Run the brain on a simulated scenario and export ONLY its outputs as replay.json (schema 1),
then bake that into dashboard.html. The dashboard never sees truth or tracker internals."""
from __future__ import annotations
import json
import sys
from dataclasses import asdict

from skybrain.engine import Engine
from skybrain.sim import make_scenario, scan
from skybrain.threat import LEVELS, Site
from skybrain.tracker import Tracker
import numpy as np


def build(seed: int = 7, T: int = 240, dt: float = 1.0) -> dict:
    rng = np.random.default_rng(seed)
    truths, site = make_scenario(rng), Site()
    tracker, engine = Tracker(), Engine(site, {"FRIEND-01"})
    frames, events = [], []
    for k in range(T):
        t = k * dt
        confirmed = tracker.step(t, scan(t, truths, rng))
        events += [asdict(e) for e in engine.step(t, confirmed)]
        frames.append({"t": t, "tracks": engine.snapshot(confirmed)})
        for tr in truths:
            if t >= tr.t_start:
                tr.step(dt, rng)
    return {"schema": 1,
            "meta": {"source": "simulator", "positions": "straight-line estimate", "seed": seed, "dt": dt,
                     "zones": {"inner": site.r_inner, "outer": site.r_outer, "sensor": 2500.0},
                     "levels": [LEVELS[i] for i in range(5)]},
            "frames": frames, "events": events, "audit": engine.audit.records, "audit_valid": engine.audit.verify()}


if __name__ == "__main__":
    data = build(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
    blob = json.dumps(data, separators=(",", ":"), default=float)
    open("replay.json", "w").write(blob)
    html = open("dashboard_template.html").read().replace("__REPLAY__", blob.replace("</", "<\\/"))
    open("dashboard.html", "w").write(html)
    print(f"replay.json {len(blob) / 1024:.0f} KB, {len(data['frames'])} frames, {len(data['events'])} events, "
          f"audit chain valid: {data['audit_valid']}  -> dashboard.html")
