# Technical Report: Tactical Possession State Engine

**Team:** Pitch Intelligence Lab

**Status:** DP-005 first implementation; DP-001 through DP-004 retained as fallback

**Code repository:** <https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona>

## Scope

DP-005 replaces the fixed majority-vote baseline with a configurable temporal state engine. The engine reads tactical ATD through the existing adapter, distinguishes observation quality, combines small independent evidence signals, permits direct H to A and A to H changes, and uses D only for explicit stoppage evidence.

X is emitted only for the published frame blocks outside the two graded halves. Every frame known to be graded receives H, A or D.

## Inputs used and dropped

Used:

- Tactical FIFA/EPTS metadata
- Tactical raw ATD positions and speeds
- Published frame and scoring contract

Implemented as optional interfaces but not enabled:

- Smart Tagging weak team/dead-ball prior
- Restart-zone proximity
- Optimistic reachability
- Minimum-segment cleanup
- Isolated dead-ball cleanup

Deliberately unused:

- Tactical or broadcast video pixels
- Broadcast tracking
- Homography
- Competition possession ground truth for design or parameter selection
- External labels or trained models

## Pipeline

1. The metadata maps the first team to H and the second to A. Every player slot is mapped through its metadata `teamId`.
2. ATD `frame_id` is converted to the zero-based submission frame.
3. Ball observations become `observed`, `interpolated` or `missing`. Only an internally bracketed gap of at most 0.4 seconds is linearly interpolated.
4. Player positions are converted from normalised coordinates to metres before distance calculations. Non-finite slots are excluded.
5. The engine computes independent evidence: nearest-team distance, visible three-player team vote, ball speed/rest duration, optional restart-zone distance and optional optimistic reachability.
6. Nearest-team evidence is rejected on a frame where it conflicts with the visible-player vote.
7. A deterministic H/A/D state machine applies persistence and transition rules.
8. Optional whole-interval cleanup runs after inference.
9. The complete CSV is validated, atomically installed, hashed and summarized in an aggregate health report.

## Evidence definitions

| Evidence | Unit | Missing-data behavior | Failure mode |
|---|---|---|---|
| Nearest-team distance | metres | No finite player means no team candidate | Duplicate, drifting or invisible slots near the ball |
| Visible-player vote | number of slots | Missing slots do not vote | A compact defensive block can outvote the actual receiver |
| Ball speed/rest | m/s and seconds | Slow feature carries; observed-evidence flag stays false when missing | Shielding or waiting for support can resemble dead ball |
| Restart-zone proximity | metres | Missing ball gives no value | Generic anchors do not prove a restart occurred |
| Optimistic reachability | seconds | Missing player speed assumes zero observed speed plus the configured bonus | Every player is optimistically assumed to run toward the ball |
| Smart Tagging prior | team/dead/restart flags | Missing or N/A team contributes no side | Automatically inferred phases can be wrong and are not possession labels |

## State rules

- A first usable team candidate initializes H or A directly.
- A missing ball does not change the current state. A long gap with no dead-ball evidence preserves the last state.
- A direct H to A or A to H change requires 0.8 seconds of persistent opposing evidence.
- D requires explicit evidence for 0.8 seconds.
- The enabled default D evidence is an observed ball under 0.5 m/s for at least 1.5 seconds.
- A team candidate for 0.4 seconds can restart play from D.
- H to A and A to H are direct. The engine never inserts D merely to bridge two teams.
- Known ungraded frame blocks produce X. They also terminate temporal continuity across halftime or match boundaries.

## Structural cleanup

`short_flicker_absorption` replaces a segment of at most 0.24 seconds only when the segment immediately before and after has the same H/A/D value. It never bridges X.

`minimum_segment_duration` and `isolated_dead_ball_removal` are separate named steps but are disabled. They must not be enabled until external evidence shows that they do not erase real short possessions or stoppages.

## Parameters and provenance

The machine-readable source of truth is `configs/state-engine.json`. Every parameter includes value, unit, source and rationale.

| Parameter | Value | Source |
|---|---:|---|
| Ball interpolation maximum | 0.4 s | engineering-assumption |
| Candidate confirmation | 0.8 s | general-football-prior |
| Restart confirmation | 0.4 s | general-football-prior |
| Dead-ball confirmation | 0.8 s | engineering-assumption |
| Minimum ball-rest duration | 1.5 s | engineering-assumption |
| Rest speed threshold | 0.5 m/s | engineering-assumption |
| Near-player vote neighbourhood | 3 players | general-football-prior |
| Restart-zone radius | 8 m | engineering-assumption |
| Optimistic extra speed | 2 m/s | engineering-assumption |
| Short-flicker maximum | 0.24 s | general-football-prior |
| Minimum-segment threshold | 0.4 s, disabled | engineering-assumption |
| Isolated-D maximum | 0.4 s, disabled | engineering-assumption |
| Use visible vote | true | general-football-prior |
| Use ball rest for D | true | engineering-assumption |
| Enable restart zone | false | engineering-assumption |
| Enable reachability | false | engineering-assumption |
| Enable Smart Tagging | false | engineering-assumption |
| Enable short-flicker cleanup | true | general-football-prior |
| Enable minimum-segment cleanup | false | engineering-assumption |
| Enable isolated-D cleanup | false | engineering-assumption |

Official facts in the configuration are 25 FPS, 199,319 target frames, the 105.3 by 68.0 m pitch from the team's tracking configuration, the normalised coordinate convention, and the published graded/ungraded frame blocks.

No parameter was selected by comparing outputs against this match's public or private possession ground truth. No public five-minute score was used to choose or reject a DP-005 design variant.

After freezing this implementation, one automated public-window smoke test reported macroF1 0.4998 and spellF1 0.3897. D-class F1 was 0. The run predicted 22 possessions of mean 13.6 s against 17 reference possessions of mean 14.2 s, with fragmentation ratio 1.10 and alive/dead F1 0.8913. No parameter or design change followed the smoke result.

## Training data

None. No model is trained, fitted or tuned. No external labels are used.

## Verified tactical run

- Rows and frames: 199,319 rows, frame 0 through 199318
- Labels: H=81,311, A=74,490, D=3,056, X=40,462
- H/A/D segment counts: H=166, A=175, D=19
- Segment duration: mean H=19.593 s, A=17.026 s, D=6.434 s
- Ball quality: observed=113,488, interpolated=108, missing=85,723
- Graded ball quality: observed=94,214, interpolated=39, missing=64,604
- Transitions: H->A=162, A->H=159, H->D=4, A->D=14, D->H=6, D->A=13
- Input metadata SHA-256: `327e35e32e46a647389b88f883d4f9a2ab931e3e6148aef2fcf8f22b1e93c43a`
- Input raw-tracking SHA-256: `f130e350d2bfdf734b7e32f072931fccc6d015c1e837d082064875fe0a700431`
- Output SHA-256: `db132162c9711f01dd5ff9bca4b9867baac8ed64ded80b700944bc2c13dc0177`
- Repeat generation: byte-identical
- Project validator: pass
- Official format validator: pass

The sum H+A+D equals all 158,857 graded frames. X equals all 40,462 configured ungraded frames.

The DP-001 through DP-004 baseline can still be rebuilt with `configs/baseline.json`; its prior SHA-256 remains `caf42b0775d695e29859f775c67d42162a92d32655facb202c548b3b59fb220f`.

## Determinism

- All timing thresholds are specified in seconds and converted using the configured FPS.
- The match identifier, frame count, pitch dimensions, coordinate convention and team-mapping source are configuration values.
- No random operation is used.
- Evidence is assembled in fixed order and state transitions are deterministic.
- CSV output is UTF-8 with LF line endings.
- Final output is replaced only after full validation.
- The same code, configuration and inputs produce identical bytes and SHA-256.

## Known limitations

- Ball rest is only a proxy for a stoppage and can misclassify shielding or waiting for support.
- The frozen public smoke test missed every D frame, confirming that the current ball-rest trigger is inadequate for general dead-ball recognition.
- Nearest-player and local-vote evidence can be wrong in a crowded penalty area.
- Interpolation can preserve context but cannot recover a genuinely changing ball trajectory.
- Smart Tagging, restart-zone and reachability evidence are implemented but disabled.
- Strict duration priors have not yet been validated on licensed external matches.
- The public five-minute answer was not used to compare DP-005 design variants.

## Reproduction

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
$env:MTAH_DATA_DIR = "E:\mtah2027-data"
.\.venv\Scripts\python scripts\build_submission.py `
  --output outputs\submission-state-engine.csv `
  --config configs\state-engine.json `
  --health-report outputs\submission-state-engine.health.json `
  --force
.\.venv\Scripts\python scripts\validate_submission.py outputs\submission-state-engine.csv
```

## Compliance

No competition video, extracted tracking row, screenshot or clip was sent to a cloud AI service or committed. No hand label or manual correction was used. The local tactical run was performed by code through `MTAH_DATA_DIR`; only aggregate counts, validation status and hashes are reported.
