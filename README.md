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
- Formal algorithm: not started.

## Documents

- [Team operating model](docs/team-operating-model.md)
- [Team roster](docs/team-roster.md)
- [Decision log](docs/decision-log.md)
- [Experiment log](docs/experiment-log.md)
- [Technical report](docs/technical-report.md)
- [Final checklist](docs/final-checklist.md)
- [Notion task template](notion/task-template.md)
- [Notion task board import](notion/task-board.csv)
