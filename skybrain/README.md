# skybrain (working name)

The brain of a counter-drone system: **detect -> track -> classify -> assess -> recommend to a human -> audit.**
Effector-agnostic by design. No jam / intercept code lives here; responses are only recommended, and a human decision is logged.

## Run
    pip install -r requirements.txt
    python run_demo.py 7          # one scenario with a scorecard
    python run_demo.py batch 40   # Monte-Carlo scorecard over 40 random runs
    pytest                        # 7 tests

## Pipeline
| Module | Job |
|---|---|
| `sim.py` | Synthetic world: 2 attackers (one spoofing a friendly ID), a loiterer, 3 birds, a benign pass-by, a friendly patrol, clutter |
| `tracker.py` | Kalman filters + gated global-nearest-neighbour association, M-of-N track confirmation |
| `classify.py` | friendly / drone / bird / unknown. A friendly ID counts only if cryptographically verified |
| `threat.py` | Time-to-zone, closest approach, loiter dwell -> level 0-4 (IGNORE, OBSERVE, WARN, ALERT, CRITICAL) |
| `engine.py` | Rules of engagement, anti-flapping hysteresis, RECOMMEND events, human decision logging |
| `audit.py` | Hash-chained, tamper-evident log |

## Operator dashboard
    python export.py 7     # runs the brain, writes replay.json, bakes dashboard.html
Open `dashboard.html` in any browser. It is a **replay viewer** that reads only `replay.json`.
Always on screen: `SOURCE: SIMULATOR`, `POSITIONS: STRAIGHT-LINE ESTIMATE`, 2-sigma error rings on every track.
Approve / Reject clicks are local to the replay and are labelled "NOT SENT TO BRAIN".

### Data contract (replay.json, schema 1)
- `meta`: source, positions, seed, dt, zone radii, level names
- `frames[]`: `t` and `tracks[]` with `id x y z vx vy sig level label conf why` (nothing else)
- `events[]`: `t track_id kind level label detail needs_human`
- `audit[]`: hash-chained records, plus `audit_valid`
A test fails if anything beyond this leaves the brain.

## Scorecard (40 random simulated runs)
- Threats reaching ALERT: 120/120, at least 56 s before the critical zone (mean 62 s)
- Harmless objects raising ALERT: 0/200; raising WARN or higher: 1/200
- False clutter tracks: 0 per hour

## Honest limits (read before believing the numbers)
- These results are on **my own simulator**, not real sensors. They prove the logic works, not that it works in the field.
- One sensor, constant-velocity motion model, straight-line attackers. Real drones manoeuvre: add an IMM filter next.
- The classifier uses simple features (signature proxy, heading variability). Replace with a model trained on real data behind the same `classify()` interface.
- Filter noise `q` and classifier thresholds were tuned on this simulator. Retune on real data.

## Next steps
1. Make the dashboard live (stream `Engine.snapshot()` instead of a replay file) and write operator decisions back to the audit log
2. IMM tracker plus a second sensor type (RF) in the fusion step
3. Ingest recorded real data (public RF / video datasets) and measure false alarms per day
4. Authenticated-ID handshake for friendly drones
