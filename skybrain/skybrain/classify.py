"""Track classifier. Transparent rule/score model today; swap in a trained model later behind the same interface."""
from __future__ import annotations
import numpy as np

from .tracker import Track


def features(trk: Track) -> dict:
    amps, V = np.array(trk.amps), np.array(trk.vels)
    f = {"n": len(amps), "amp": float(amps.mean()) if len(amps) else -99.0, "speed": 0.0, "turn": 0.0}
    if len(V) >= 4:
        f["speed"] = float(np.linalg.norm(V[:, :2], axis=1).mean())
        heading = np.unwrap(np.arctan2(V[:, 1], V[:, 0]))
        f["turn"] = float(np.std(np.diff(heading)))
    return f


def classify(trk: Track, whitelist: set[str], min_evidence: int = 10) -> tuple[str, float]:
    """Returns (label, confidence). Labels: friendly | drone | bird | unknown.

    Security rule: a friendly ID only counts if it was cryptographically verified (rf_auth).
    A plain broadcast ID can be copied by an attacker, so it is never trusted on its own.
    """
    verified = [i for i, auth in trk.rf if auth and i in whitelist]
    if len(verified) >= 3:
        return "friendly", 0.99
    f = features(trk)
    if f["n"] < min_evidence:
        return "unknown", 0.0
    s = 1.0 * (f["amp"] + 24.0) - 8.0 * (f["turn"] - 0.18)      # >0 favours drone, <0 favours bird
    p = 1.0 / (1.0 + np.exp(-s))
    return ("drone", float(p)) if p >= 0.5 else ("bird", float(1 - p))
