"""Synthetic world: truth targets + one noisy sensor, so the brain can be built and measured without hardware."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass
class Measurement:
    t: float
    pos: np.ndarray            # (3,) metres, local ENU, site at origin
    sigma: float               # 1-sigma position noise (m)
    amp: float                 # signature proxy (dB), drones stronger than birds
    rf_id: str | None = None   # broadcast ID decoded from RF, if any
    rf_auth: bool = False      # True only if the ID was cryptographically verified


@dataclass
class Truth:
    id: int
    kind: str                  # hostile | loiterer | benign | bird | friendly
    pos: np.ndarray
    vel: np.ndarray
    speed: float
    amp_mean: float
    mode: str = "straight"     # straight | loiter | bird | patrol
    pd: float = 0.92
    t_start: float = 0.0
    rf_id: str | None = None
    rf_auth: bool = False
    turn_sigma: float = 0.0
    loiter_at: float = 900.0
    orbit_r: float = 250.0

    def step(self, dt: float, rng: np.random.Generator) -> None:
        h = np.arctan2(self.vel[1], self.vel[0])
        if self.mode == "bird":
            h += rng.normal(0, self.turn_sigma) * np.sqrt(dt)
            self.vel[:2] = self.speed * np.array([np.cos(h), np.sin(h)])
        elif self.mode == "loiter" and np.linalg.norm(self.pos[:2]) <= self.loiter_at:
            h += self.speed / self.orbit_r * dt
            self.vel[:2] = self.speed * np.array([np.cos(h), np.sin(h)])
            self.vel[2] = 0.0
        elif self.mode == "patrol":
            h += self.speed / 150.0 * dt
            self.vel[:2] = self.speed * np.array([np.cos(h), np.sin(h)])
        self.pos = self.pos + self.vel * dt
        self.pos[2] = float(np.clip(self.pos[2], 10.0, 400.0))


def _polar(bearing_deg: float, r: float, z: float) -> np.ndarray:
    a = np.radians(bearing_deg)
    return np.array([r * np.cos(a), r * np.sin(a), z])


def _toward_site(p: np.ndarray, speed: float) -> np.ndarray:
    d = np.array([0.0, 0.0, 20.0]) - p
    return speed * d / np.linalg.norm(d)


def make_scenario(rng: np.random.Generator) -> list[Truth]:
    T: list[Truth] = []
    p = _polar(40, 2300, 120)       # H1: straight-in attacker
    T.append(Truth(1, "hostile", p, _toward_site(p, 18), 18, -20))
    p = _polar(200, 2300, 90)       # H2: fast attacker spoofing a friendly ID (unverified)
    T.append(Truth(2, "hostile", p, _toward_site(p, 25), 25, -19, t_start=30, rf_id="FRIEND-01", rf_auth=False))
    p = _polar(300, 2200, 100)      # L1: surveillance drone that circles inside the outer zone
    T.append(Truth(3, "loiterer", p, _toward_site(p, 10), 10, -21, mode="loiter"))
    p = _polar(120, 1400, 50)       # B1: bird flying straight at the site
    T.append(Truth(4, "bird", p, _toward_site(p, 8), 8, -28, mode="bird", pd=0.75, turn_sigma=0.5))
    for i in range(2):              # more birds, random
        p = _polar(rng.uniform(0, 360), rng.uniform(500, 2000), rng.uniform(30, 90))
        h = rng.uniform(0, 2 * np.pi)
        T.append(Truth(5 + i, "bird", p, np.array([8 * np.cos(h), 8 * np.sin(h), 0.0]), 8, -28,
                       mode="bird", pd=0.75, turn_sigma=0.5))
    T.append(Truth(7, "benign", np.array([-2300.0, 1900.0, 80.0]), np.array([15.0, 0.0, 0.0]), 15, -21))
    T.append(Truth(8, "friendly", np.array([150.0, 0.0, 60.0]), np.array([0.0, 8.0, 0.0]), 8, -21,
                   mode="patrol", rf_id="FRIEND-01", rf_auth=True))
    return T


def scan(t: float, truths: list[Truth], rng: np.random.Generator, max_range: float = 2500.0,
         clutter_rate: float = 0.3, rf_p: float = 0.6) -> list[Measurement]:
    ms: list[Measurement] = []
    for tr in truths:
        if t < tr.t_start:
            continue
        r = float(np.linalg.norm(tr.pos))
        if r > max_range or rng.random() > tr.pd:
            continue
        sigma = 5.0 + 0.006 * r
        got_rf = tr.rf_id is not None and rng.random() < rf_p
        ms.append(Measurement(t, tr.pos + rng.normal(0, sigma, 3), sigma, float(rng.normal(tr.amp_mean, 2.5)),
                              tr.rf_id if got_rf else None, tr.rf_auth if got_rf else False))
    for _ in range(rng.poisson(clutter_rate)):
        pos = np.array([rng.uniform(-max_range, max_range), rng.uniform(-max_range, max_range), rng.uniform(5, 200)])
        ms.append(Measurement(t, pos, 20.0, float(rng.normal(-34, 4))))
    return [ms[i] for i in rng.permutation(len(ms))]
