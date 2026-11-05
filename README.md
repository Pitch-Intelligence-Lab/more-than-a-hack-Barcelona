# More Than a Hack 2027 Team Workspace

Local collaboration repository for the More Than a Hack 2027 possession challenge.

**Team:** Pitch Intelligence Lab

**Members:** 何, 唐, 莫

**Team GitHub account:** `orson0414`

**Notion owner:** 何

**Repository:** <https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona>

The scored output is a 199,319-row CSV with labels H, A, D and X. The ranking metric is spellF1. This repository is intended to contain code, tests and documentation only.

## Safety boundary

- Keep competition videos, tracking files, homography files and screenshots outside this repository.
- Do not provide competition data to cloud AI tools.
- Do not hand-label or manually correct the provided match.
- Do not train, fit or tune on the provided match video or possession ground truth.
- Use external data only when its licence permits the intended use.

Coding agents must follow [AGENTS.md](AGENTS.md). They work directly in `E:\mtah2027-code`, use `E:\mtah2027-data` only through configuration, and deliver commits on feature branches rather than standalone ZIP files.

## Planned local layout

```text
E:\mtah2027-code\    this repository
E:\mtah2027-data\    local competition data, never committed
```

Set the data root outside this workspace:

```powershell
$env:MTAH_DATA_DIR = "E:\mtah2027-data"
```

## Current status

- Team registration: complete.
- Tactical and broadcast data: received and structurally checked.
- Public scorer: reproduced.
- DP-001 through DP-004 implemented in `feature/DP-001-DP-004-tactical-baseline`.
- DP-005 configurable state engine implemented in `feature/DP-005-general-state-machine`.
- Synthetic and team-local tactical runs pass.
- DP-005 v1.2 tactical output: 199,319 rows, SHA-256 `1de6261504c7cb539a4e78f42f18011c692b9bd148ea3e77fbca44df9c0b9401`.
- Baseline fallback: SHA-256 `caf42b0775d695e29859f775c67d42162a92d32655facb202c548b3b59fb220f`.
- Public-window macroF1 0.6209 and spellF1 0.3256 are baseline references, not tuning targets.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
```

## Synthetic tests

The tests need no match data.

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
```

## Build and validate the state engine

```powershell
$env:MTAH_DATA_DIR = "E:\mtah2027-data"
.\.venv\Scripts\python scripts\build_submission.py `
  --output outputs\submission-state-engine.csv `
  --config configs\state-engine.json `
  --health-report outputs\submission-state-engine.health.json `
  --force
.\.venv\Scripts\python scripts\validate_submission.py outputs\submission-state-engine.csv
```

The data root must contain `tactical/` and `broadcast/`. An existing output is only replaced with `--force`. The builder writes and validates a temporary CSV before atomically replacing the destination. The health report contains aggregate observation quality, segments, transitions, reasons and hashes only.

The verified DP-001 through DP-004 baseline remains available as a fallback:

```powershell
.\.venv\Scripts\python scripts\build_submission.py `
  --output outputs\submission-baseline-fallback.csv `
  --config configs\baseline.json `
  --force
```

## DP-005 algorithm

1. Read the first `Team` metadata entry as home and the second as away.
2. Map every player slot through its `teamId`.
3. Convert ATD `frame_id` to submission frame `frame_id - 1`.
4. Convert normalised coordinates to metres using the 105.3 x 68.0 m pitch.
5. Mark ball observations as observed, interpolated or missing. Interpolation is bounded to 0.4 seconds and never extends from an edge.
6. Compute independent nearest-team, visible near-player vote, ball rest, restart, restart-zone and optimistic reachability evidence. Missing slots are ignored; missing ball observations carry forward the current state.
7. Require persistent opposing evidence for 0.8 seconds before a direct H to A or A to H change.
8. Force D for frames 110808 through 113741, the interval between the official second-half start and the actual kickoff. State inference and cleanup cannot remove this block.
9. Enter D elsewhere only after sustained explicit dead-ball evidence. Ball rest for 1.5 seconds is the default weak evidence; missing ball alone is not D.
10. Permit a restart from D after 0.4 seconds of team evidence, shortened to 0.2 seconds only while independent restart evidence remains active.
11. Absorb only short same-neighbour H/A flicker after inference. D is preserved by default; forced-dead frames are protected under every cleanup configuration.
12. Emit X only on the configured, officially known ungraded blocks: before kickoff, halftime and after the final whistle.

Every state-engine parameter is stored in `configs/state-engine.json` with its unit, source and rationale. The configuration supports FPS, frame count, pitch dimensions, match identifier, coordinate representation, team-mapping source and optional assets. State durations are specified in seconds.

## Verified aggregate run

- Rows: 199,319; frame range 0 through 199318
- Labels: H=79,250, A=73,608, D=5,999, X=40,462
- Forced second-half pre-kickoff block: 2,934 frames, all D
- H/A/D segments: H=161, A=170, D=20
- Ball observations: observed=113,488, interpolated=108, missing=85,723
- Cleanup removed label counts: H=0, A=0, D=0
- Repeat generation: byte-identical, SHA-256 `1de6261504c7cb539a4e78f42f18011c692b9bd148ea3e77fbca44df9c0b9401`
- Project validator: pass
- Official format validator: pass
- Baseline fallback rebuild: exact previous SHA-256
- Frozen public smoke: macroF1 0.4998, spellF1 0.3897, D-class F1 0 (no post-smoke tuning)

The second-half pre-kickoff defect is fixed, but the public D result shows that dead-ball recognition remains incomplete. Good possession continuity and spellF1 do not establish that every task state is solved.

## Documents

- [Team operating model](docs/team-operating-model.md)
- [Team roster](docs/team-roster.md)
- [Decision log](docs/decision-log.md)
- [Experiment log](docs/experiment-log.md)
- [Tooling policy](docs/tooling-policy.md)
- [Technical report](docs/technical-report.md)
- [Engineering handoff](docs/handoff.md)
- [DP-005 engineering sprint](docs/engineering-sprint-dp005.md)
- [External reference register](docs/reference-register.md)
- [Final checklist](docs/final-checklist.md)
- [Notion task template](notion/task-template.md)
- [Notion task board import](notion/task-board.csv)
