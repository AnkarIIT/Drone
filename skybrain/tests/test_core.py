import numpy as np
import pytest

from run_demo import run
from skybrain.audit import AuditLog
from skybrain.classify import classify
from skybrain.sim import Measurement
from skybrain.threat import cpa_distance, time_to_radius
from skybrain.tracker import Tracker


def test_time_to_radius_and_cpa():
    p, v = np.array([1000.0, 0.0]), np.array([-10.0, 0.0])
    assert abs(time_to_radius(p, v, 300.0) - 70.0) < 1e-6          # 700 m at 10 m/s
    assert time_to_radius(np.array([100.0, 0.0]), v, 300.0) == 0.0  # already inside
    assert time_to_radius(np.array([1000.0, 900.0]), np.array([-10.0, 0.0]), 300.0) == float("inf")
    assert abs(cpa_distance(np.array([1000.0, 200.0]), v) - 200.0) < 1e-6


def test_kalman_tracks_straight_line():
    rng, tr = np.random.default_rng(0), Tracker()
    for k in range(30):
        pos = np.array([1000.0 - 15 * k, 500.0, 80.0])
        tr.step(float(k), [Measurement(float(k), pos + rng.normal(0, 8, 3), 8.0, -20.0)])
    (trk,) = [t for t in tr.tracks if t.confirmed]
    assert abs(trk.x[3] + 15) < 2.0 and np.linalg.norm(trk.x[:3] - [1000 - 15 * 29, 500, 80]) < 25


def test_audit_chain_detects_tampering():
    log = AuditLog()
    for i in range(5):
        log.append("EVT", {"i": i})
    assert log.verify()
    log.records[2]["payload"]["i"] = 99
    assert not log.verify()


def test_unverified_friendly_id_is_not_trusted():
    tr = Tracker()
    trk = tr._spawn(Measurement(0.0, np.zeros(3), 5.0, -20.0, "FRIEND-01", False))
    for _ in range(12):
        trk.amps.append(-20.0)
        trk.rf.append(("FRIEND-01", False))                      # spoofed: ID without verification
        trk.vels.append(np.array([10.0, 0.0, 0.0]))
    assert classify(trk, {"FRIEND-01"})[0] == "drone"
    trk.rf.clear()
    for _ in range(4):
        trk.rf.append(("FRIEND-01", True))
    assert classify(trk, {"FRIEND-01"})[0] == "friendly"


def test_end_to_end_threats_alerted_early_and_harmless_quiet():
    for seed in (7, 11, 23):
        rows, clutter, engine, _ = run(seed, verbose=False)
        for tr, mine, first, peak in rows:
            if tr.kind == "hostile":
                assert first[3] is not None and tr.inner_entry - first[3] > 30
            if tr.kind in ("bird", "friendly", "benign"):
                assert peak < 3, (seed, tr.kind)
        assert engine.audit.verify()


def test_human_decision_is_logged():
    _, _, engine, _ = run(7, verbose=False)
    kinds = [r["kind"] for r in engine.audit.records]
    assert "RECOMMEND" in kinds and "HUMAN_DECISION" in kinds
    decisions = [r for r in engine.audit.records if r["kind"] == "HUMAN_DECISION"]
    assert all(r["payload"]["recommendation_id"] for r in decisions)


def test_recommendation_is_single_use_and_expires():
    from skybrain.engine import Engine, ROEConfig
    from skybrain.threat import Site
    rng = np.random.default_rng(4)
    tracker = Tracker()
    engine = Engine(Site(), set(), ROEConfig(recommendation_ttl=2.0))
    for t in range(20):
        confirmed = tracker.step(float(t), [
            Measurement(float(t), np.array([100.0, 0.0, 50.0]), 3.0, -18.0)
        ])
        events = engine.step(float(t), confirmed)
        if any(e.kind == "RECOMMEND" for e in events):
            recommendation = next(e for e in events if e.kind == "RECOMMEND")
            break
    else:
        raise AssertionError("expected a recommendation")
    engine.step(recommendation.expires_at, [])
    assert engine.states[recommendation.track_id].recommendation_status == "EXPIRED"
    with pytest.raises(ValueError, match="expired"):
        engine.record_decision(recommendation.expires_at, recommendation.track_id, "op", True,
                               recommendation_id=recommendation.recommendation_id)
    with pytest.raises(ValueError, match="monotonic"):
        engine.step(recommendation.expires_at - 1, [])


def test_replay_contract_exposes_only_brain_outputs():
    from export import build
    d = build(7, T=120)
    assert d["schema"] == 1 and d["meta"]["source"] == "simulator" and d["audit_valid"]
    allowed = {"id", "x", "y", "z", "vx", "vy", "sig", "level", "label", "conf", "why"}
    for f in d["frames"]:
        for k in f["tracks"]:
            assert set(k) == allowed                       # no truth ids, no covariance, no tracker internals
