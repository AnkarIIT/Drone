# SKYBRAIN

### Defensive airspace intelligence for decisions that must remain explainable

Skybrain is an experimental counter-drone **detection, tracking, assessment, and
human-decision support system**. It is designed around a simple principle:

> **The system may recommend. A human must decide.**

Skybrain does not contain jamming, interception, targeting, or autonomous
engagement logic. Its job is to turn uncertain sensor observations into
traceable, conservative recommendations that an authorized operator can review.

---

## Why Skybrain

Small drones are fast, inexpensive, difficult to classify, and capable of
appearing in dense or degraded sensing environments. A useful defensive system
cannot depend on one sensor, one motion model, one identity signal, or one
perfect network connection.

Skybrain is being built to remain trustworthy when:

- targets manoeuvre sharply or travel at high speed;
- sensors disagree, drop out, or produce clutter;
- a drone broadcasts a spoofed friendly identity;
- GPS or communications are degraded;
- multiple tracks compete for operator attention;
- recommendations become stale or expire;
- every decision must be reconstructed later.

This repository is a **research and engineering prototype**, not a fielded
military system and not evidence of operational readiness.

## Core pipeline

```text
sensor observations
        ↓
time and quality validation
        ↓
multi-sensor association
        ↓
manoeuvring track estimation
        ↓
identity and classification
        ↓
uncertainty-aware threat assessment
        ↓
human-only recommendation
        ↓
authenticated, tamper-evident audit
```

The operator dashboard is deliberately downstream of the brain. It reads a
versioned output contract; it does not calculate threat levels, infer identity,
or activate effects.

## Current capabilities

The current prototype includes:

- simulated airspace scenarios with hostile, benign, friendly, bird, loitering,
  and clutter tracks;
- gated multi-target tracking with track confirmation and covariance;
- conservative handling of unverified friendly IDs;
- transparent classification of friendly, drone, bird, and unknown tracks;
- threat levels from `IGNORE` through `CRITICAL`;
- anti-flapping escalation and de-escalation behavior;
- human-only recommendations;
- recommendation IDs, expiry, single-use decisions, and explicit decision
  rejection for stale or mismatched recommendations;
- hash-chained audit records;
- replay export with a strict public data contract;
- a mobile-aware replay dashboard for inspection and testing.

## Repository map

| Path | Purpose |
|---|---|
| `skybrain/skybrain/sim.py` | Synthetic targets, measurements, and scenarios |
| `skybrain/skybrain/tracker.py` | Multi-target tracking and track lifecycle |
| `skybrain/skybrain/classify.py` | Transparent identity and object classification |
| `skybrain/skybrain/threat.py` | Zone geometry and threat assessment |
| `skybrain/skybrain/engine.py` | Human recommendation and control state |
| `skybrain/skybrain/audit.py` | Tamper-evident hash-chained audit log |
| `skybrain/run_demo.py` | End-to-end scorecard and simulation runner |
| `skybrain/export.py` | Brain-output replay exporter |
| `skybrain/dashboard_template.html` | Replay dashboard source |
| `skybrain/Plan.txt` | Final architecture, verification, and release plan |
| `skybrain/tests/test_core.py` | Core behavior and contract tests |

## Quick start

From the `skybrain` directory:

```powershell
python -m pip install -r requirements.txt
python run_demo.py 7
python run_demo.py batch 40
python -m pytest -q
```

Generate and open the replay dashboard:

```powershell
python export.py 7
start dashboard.html
```

Use another integer to generate a different deterministic scenario:

```powershell
python export.py 23
```

The dashboard is a replay viewer. Its `Approve` and `Reject` controls are
intentionally local to the replay and are marked **NOT SENT TO BRAIN**.

## Public replay contract

`replay.json` is the dashboard boundary. The exported data contains:

- metadata and zone definitions;
- per-frame track estimates;
- brain events and recommendations;
- audit records and audit validity.

The contract intentionally excludes truth IDs, raw sensor data, covariance
matrices, tracker internals, and simulation-only details. A test fails if
private brain state leaks through this boundary.

## Safety and security posture

Skybrain is designed as defensive decision support:

- no effector control;
- no autonomous engagement;
- no approval by silence or timeout;
- no trust in an unverified friendly broadcast ID;
- no hidden dashboard-side threat logic;
- explicit recommendation expiry;
- explicit audit trail for human decisions;
- fail-closed behavior for invalid or ambiguous control input.

These are engineering constraints, not claims that the prototype is safe for
deployment. Any operational use would require independent safety, security,
human-factors, legal, and systems-integration review.

## Known limitations

The simulator is not a sensor range, and passing simulator tests is not field
validation. The current prototype still requires:

- a reconciled IMM tracker for cruise, acceleration, and coordinated-turn
  models;
- real multi-sensor fusion and sensor-health handling;
- bounded manoeuvre-aware threat prediction;
- durable authenticated audit storage;
- clock, latency, queue, restart, and degraded-mode handling;
- hardware-in-the-loop and representative sensor replay;
- independent safety, security, and operator evaluations.

See [`skybrain/Plan.txt`](skybrain/Plan.txt) for the complete implementation
sequence and release gates.

## Project direction

The next milestone is not a live dashboard. It is a brain and control core that
passes deterministic tests for fast targets, sharp turns, crossings, spoofed
identity, stale data, sensor failure, duplicate decisions, and audit recovery.

Only after that foundation is stable should Skybrain move to a live, authenticated
stream in read-only shadow mode.

---

**Skybrain is built for clarity under uncertainty: detect carefully, explain
honestly, recommend conservatively, and keep the decision accountable.**
