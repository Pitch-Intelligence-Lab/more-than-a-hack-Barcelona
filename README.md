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
- Synthetic and team-local tactical runs pass.
- Final tactical output: 199,319 rows, SHA-256 `caf42b0775d695e29859f775c67d42162a92d32655facb202c548b3b59fb220f`.

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

## Build and validate the tactical baseline

```powershell
$env:MTAH_DATA_DIR = "E:\mtah2027-data"
.\.venv\Scripts\python scripts\build_submission.py `
  --output outputs\submission.csv `
  --config configs\baseline.json
.\.venv\Scripts\python scripts\validate_submission.py outputs\submission.csv
```

The data root must contain `tactical/` and `broadcast/`. An existing output is only replaced with `--force`. The builder writes and validates a temporary CSV before atomically replacing the destination.

## Baseline algorithm

1. Read the first `Team` metadata entry as home and the second as away.
2. Map every player slot through its `teamId`.
3. Convert ATD `frame_id` to submission frame `frame_id - 1`.
4. Convert normalised coordinates to metres using the 105.3 x 68.0 m pitch.
5. Use no candidate when the ball or players are missing, or when the closest home and away distances tie.
6. Apply a centred 50-frame half-width majority vote and emit H, A or D.

The 50-frame setting is a pre-registered continuity preset, not a value tuned on this match. It does not yet implement controlled possession or a true dead-ball detector.

## Documents

- [Team operating model](docs/team-operating-model.md)
- [Team roster](docs/team-roster.md)
- [Decision log](docs/decision-log.md)
- [Experiment log](docs/experiment-log.md)
- [Tooling policy](docs/tooling-policy.md)
- [Technical report](docs/technical-report.md)
- [Engineering handoff](docs/handoff.md)
- [Final checklist](docs/final-checklist.md)
- [Notion task template](notion/task-template.md)
- [Notion task board import](notion/task-board.csv)
