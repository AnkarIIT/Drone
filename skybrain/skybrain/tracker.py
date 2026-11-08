"""Multi-target tracker: constant-velocity Kalman filters + gated global-nearest-neighbour association."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
import numpy as np
from scipy.optimize import linear_sum_assignment

from .sim import Measurement

BIG = 1e6


@dataclass
class Track:
    id: int
    x: np.ndarray              # [x y z vx vy vz]
    P: np.ndarray
    t: float
    born: float
    last_update: float
    hits: int = 1
    misses: int = 0
    scans: int = 1
    confirmed: bool = False
    amps: deque = field(default_factory=lambda: deque(maxlen=20))
    vels: deque = field(default_factory=lambda: deque(maxlen=12))
    rf: deque = field(default_factory=lambda: deque(maxlen=10))
    path: list = field(default_factory=list)
    outer_since: float | None = None


class Tracker:
    def __init__(self, q: float = 1.0, gate: float = 16.27, confirm_hits: int = 3,
                 confirm_window: int = 5, max_coast: int = 6):
        self.q, self.gate = q, gate
        self.confirm_hits, self.confirm_window, self.max_coast = confirm_hits, confirm_window, max_coast
        self.tracks: list[Track] = []
        self._next = 1
        self.H = np.hstack([np.eye(3), np.zeros((3, 3))])

    def _predict(self, trk: Track, t: float) -> None:
        dt = t - trk.t
        F = np.eye(6)
        F[:3, 3:] = dt * np.eye(3)
        I = np.eye(3)
        Q = self.q ** 2 * np.block([[dt ** 4 / 4 * I, dt ** 3 / 2 * I], [dt ** 3 / 2 * I, dt ** 2 * I]])
        trk.x = F @ trk.x
        trk.P = F @ trk.P @ F.T + Q
        trk.t = t

    def _update(self, trk: Track, m: Measurement) -> None:
        R = m.sigma ** 2 * np.eye(3)
        S = self.H @ trk.P @ self.H.T + R
        K = trk.P @ self.H.T @ np.linalg.inv(S)
        trk.x = trk.x + K @ (m.pos - self.H @ trk.x)
        IKH = np.eye(6) - K @ self.H
        trk.P = IKH @ trk.P @ IKH.T + K @ R @ K.T          # Joseph form: stays symmetric / PSD
        trk.hits += 1
        trk.misses = 0
        trk.last_update = m.t
        trk.amps.append(m.amp)
        trk.vels.append(trk.x[3:].copy())
        if m.rf_id:
            trk.rf.append((m.rf_id, m.rf_auth))

    def _spawn(self, m: Measurement) -> Track:
        x = np.concatenate([m.pos, np.zeros(3)])
        P = np.diag([m.sigma ** 2] * 3 + [20.0 ** 2, 20.0 ** 2, 8.0 ** 2])
        trk = Track(self._next, x, P, m.t, m.t, m.t)
        self._next += 1
        trk.amps.append(m.amp)
        if m.rf_id:
            trk.rf.append((m.rf_id, m.rf_auth))
        return trk

    def step(self, t: float, meas: list[Measurement]) -> list[Track]:
        for trk in self.tracks:
            self._predict(trk, t)
            trk.scans += 1
        matched_t, matched_m = set(), set()
        if self.tracks and meas:
            C = np.full((len(self.tracks), len(meas)), BIG)
            for i, trk in enumerate(self.tracks):
                for j, m in enumerate(meas):
                    S = self.H @ trk.P @ self.H.T + m.sigma ** 2 * np.eye(3)
                    r = m.pos - self.H @ trk.x
                    d2 = float(r @ np.linalg.solve(S, r))
                    if d2 <= self.gate:
                        C[i, j] = d2
            for i, j in zip(*linear_sum_assignment(C)):
                if C[i, j] < BIG:
                    self._update(self.tracks[i], meas[j])
                    matched_t.add(i)
                    matched_m.add(j)
        for i, trk in enumerate(self.tracks):
            if i not in matched_t:
                trk.misses += 1
        for j, m in enumerate(meas):
            if j not in matched_m:
                self.tracks.append(self._spawn(m))
        keep = []
        for trk in self.tracks:
            if not trk.confirmed and trk.hits >= self.confirm_hits and trk.scans <= self.confirm_window:
                trk.confirmed = True
            dead = (trk.misses > self.max_coast) if trk.confirmed else \
                   (trk.misses >= 2 or trk.scans > self.confirm_window)
            if not dead:
                trk.path.append((t, *trk.x[:3]))
                keep.append(trk)
        self.tracks = keep
        return [trk for trk in self.tracks if trk.confirmed]
