"""Decision engine: classify -> assess -> apply rules of engagement -> recommend to a human -> audit.

It never acts. Level >= recommend_level produces a RECOMMEND event that needs a human decision,
and the decision itself is written to the audit log.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

from .audit import AuditLog
from .classify import classify
from .threat import LEVELS, Site, assess
from .tracker import Track


@dataclass
class ROEConfig:
    recommend_level: int = 3        # level at which a human is asked to decide
    deescalate_after: int = 5       # consecutive lower readings before a level is lowered (anti-flapping)
    recommendation_ttl: float = 15.0  # open recommendations expire unless explicitly decided
    approval_required: bool = True  # fixed True in this core; effectors are out of scope


@dataclass
class Event:
    t: float
    track_id: int
    kind: str                       # LEVEL_CHANGE | RECOMMEND
    level: int
    label: str
    detail: str
    needs_human: bool = False
    recommendation_id: str | None = None
    expires_at: float | None = None


@dataclass
class _State:
    level: int = 0
    down: int = 0
    recommended: bool = False
    first: dict = field(default_factory=dict)   # level -> first time reached
    label: str = "unknown"
    conf: float = 0.0
    why: str = ""
    recommendation_id: str | None = None
    recommendation_status: str | None = None
    recommendation_expires_at: float | None = None


class Engine:
    def __init__(self, site: Site, whitelist: set[str], roe: ROEConfig | None = None, audit: AuditLog | None = None):
        self.site, self.whitelist = site, whitelist
        self.roe, self.audit = roe or ROEConfig(), audit or AuditLog()
        self.states: dict[int, _State] = {}
        self._last_t: float | None = None

    def step(self, t: float, tracks: list[Track]) -> list[Event]:
        if not np.isfinite(t) or (self._last_t is not None and t < self._last_t):
            raise ValueError("engine time must be finite and monotonic")
        self._last_t = t
        events: list[Event] = []
        for track_id, st in self.states.items():
            if st.recommendation_status == "OPEN" and st.recommendation_expires_at is not None \
                    and t >= st.recommendation_expires_at:
                st.recommendation_status = "EXPIRED"
                events.append(Event(t, track_id, "RECOMMEND_EXPIRED", st.level, st.label,
                                    "Human decision window expired; no action was taken",
                                    recommendation_id=st.recommendation_id,
                                    expires_at=st.recommendation_expires_at))
        for trk in tracks:
            st = self.states.setdefault(trk.id, _State())
            label, conf = classify(trk, self.whitelist)
            rng = float(np.linalg.norm(trk.x[:2]))
            if rng <= self.site.r_outer:
                trk.outer_since = trk.outer_since if trk.outer_since is not None else t
            else:
                trk.outer_since = None
            dwell = 0.0 if trk.outer_since is None else t - trk.outer_since
            a = assess(trk, label, self.site, dwell)
            st.label, st.conf, st.why = label, conf, "; ".join(a.reasons)
            if a.level > st.level:
                st.level, st.down = a.level, 0
                st.first.setdefault(a.level, t)
                events.append(Event(t, trk.id, "LEVEL_CHANGE", a.level, label, "; ".join(a.reasons)))
            elif a.level < st.level:
                st.down += 1
                if st.down >= self.roe.deescalate_after:
                    st.level, st.down = a.level, 0
                    events.append(Event(t, trk.id, "LEVEL_CHANGE", a.level, label, "; ".join(a.reasons)))
            else:
                st.down = 0
            if st.level >= self.roe.recommend_level and not st.recommended:
                st.recommended = True
                st.recommendation_id = f"rec-{trk.id}-{int(round(t * 1000))}"
                st.recommendation_status = "OPEN"
                st.recommendation_expires_at = t + self.roe.recommendation_ttl
                events.append(Event(t, trk.id, "RECOMMEND", st.level, label,
                                    "Escalate to the authorised response team", needs_human=True,
                                    recommendation_id=st.recommendation_id,
                                    expires_at=st.recommendation_expires_at))
        for e in events:
            self.audit.append(e.kind, {"t": e.t, "track": e.track_id, "level": LEVELS[e.level],
                                       "label": e.label, "detail": e.detail, "needs_human": e.needs_human,
                                       "recommendation_id": e.recommendation_id,
                                       "expires_at": e.expires_at})
        return events

    def snapshot(self, tracks: list[Track]) -> list[dict]:
        """The brain's public per-scan output. Dashboards read only this, never tracker internals."""
        out = []
        for trk in tracks:
            st = self.states.get(trk.id)
            if st is None:
                continue
            out.append({"id": trk.id, "x": round(float(trk.x[0]), 1), "y": round(float(trk.x[1]), 1),
                        "z": round(float(trk.x[2]), 1), "vx": round(float(trk.x[3]), 1),
                        "vy": round(float(trk.x[4]), 1), "sig": round(float(np.sqrt(np.trace(trk.P[:3, :3]) / 3)), 1),
                        "level": st.level, "label": st.label, "conf": round(st.conf, 2), "why": st.why})
        return out

    def record_decision(self, t: float, track_id: int, operator: str, approved: bool,
                        note: str = "", recommendation_id: str | None = None) -> None:
        """Record one decision for the current open recommendation; never triggers an effector."""
        if not np.isfinite(t):
            raise ValueError("decision time must be finite")
        if not operator or not operator.strip():
            raise ValueError("operator identity is required")
        st = self.states.get(track_id)
        if st is None or st.recommendation_id is None:
            raise ValueError(f"no recommendation exists for track {track_id}")
        if recommendation_id is not None and recommendation_id != st.recommendation_id:
            raise ValueError("recommendation ID does not match the current track recommendation")
        if st.recommendation_status != "OPEN":
            raise ValueError(f"recommendation is {st.recommendation_status.lower()}, not open")
        if st.recommendation_expires_at is not None and t >= st.recommendation_expires_at:
            st.recommendation_status = "EXPIRED"
            self.audit.append("RECOMMEND_EXPIRED", {
                "t": t, "track": track_id, "recommendation_id": st.recommendation_id,
                "reason": "decision arrived after expiry"
            })
            raise ValueError("recommendation expired before the decision was received")
        st.recommendation_status = "APPROVED" if approved else "REJECTED"
        self.audit.append("HUMAN_DECISION", {
            "t": t, "track": track_id, "operator": operator, "approved": approved,
            "note": note, "recommendation_id": st.recommendation_id,
            "status": st.recommendation_status
        })
