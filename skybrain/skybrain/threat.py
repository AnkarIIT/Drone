"""Threat assessment: geometry of a track relative to the protected site -> level 0..4 with reasons."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

from .tracker import Track

LEVELS = {0: "IGNORE", 1: "OBSERVE", 2: "WARN", 3: "ALERT", 4: "CRITICAL"}


@dataclass
class Site:
    r_inner: float = 300.0     # critical zone (m)
    r_outer: float = 1500.0    # warning zone (m)


@dataclass
class Assessment:
    level: int
    rng: float
    ttz_inner: float
    cpa: float
    reasons: list = field(default_factory=list)


def time_to_radius(p: np.ndarray, v: np.ndarray, R: float) -> float:
    """Seconds until a constant-velocity target first reaches horizontal radius R (0 if inside, inf if never)."""
    a, b, c = float(v @ v), 2.0 * float(p @ v), float(p @ p) - R * R
    if c <= 0:
        return 0.0
    if a < 1e-9:
        return float("inf")
    disc = b * b - 4 * a * c
    if disc < 0:
        return float("inf")
    t = (-b - np.sqrt(disc)) / (2 * a)
    return float(t) if t >= 0 else float("inf")


def cpa_distance(p: np.ndarray, v: np.ndarray) -> float:
    """Closest horizontal approach to the site centre if the target keeps its velocity."""
    a = float(v @ v)
    t = 0.0 if a < 1e-9 else max(0.0, -float(p @ v) / a)
    return float(np.linalg.norm(p + v * t))


def assess(trk: Track, label: str, site: Site, dwell: float, loiter_s: float = 45.0) -> Assessment:
    p, v = trk.x[:2], trk.x[3:5]
    rng = float(np.linalg.norm(p))
    ttz_in, ttz_out = time_to_radius(p, v, site.r_inner), time_to_radius(p, v, site.r_outer)
    cpa = cpa_distance(p, v)
    if label in ("bird", "friendly"):
        return Assessment(0, rng, ttz_in, cpa, [f"classified {label}"])
    level, why = 1, ["drone-like object detected"]
    if rng <= site.r_outer:
        level, why = 2, ["inside outer zone"]
    elif ttz_out < 120 and cpa < site.r_outer:
        level, why = 2, [f"will enter outer zone in {ttz_out:.0f}s"]
    if (ttz_in < 60 and cpa < site.r_inner) or dwell >= loiter_s:
        level = 3
        why = [f"on course for critical zone in {ttz_in:.0f}s"] if dwell < loiter_s else [f"loitering {dwell:.0f}s in outer zone"]
    if rng <= site.r_inner or (ttz_in < 20 and cpa < site.r_inner):
        level, why = 4, ["in / about to enter critical zone"]
    if label == "unknown":
        level = min(level, 1)             # not enough evidence yet: observe only, never escalate on thin data
        why.append("class not yet confirmed")
    return Assessment(level, rng, ttz_in, cpa, why)
