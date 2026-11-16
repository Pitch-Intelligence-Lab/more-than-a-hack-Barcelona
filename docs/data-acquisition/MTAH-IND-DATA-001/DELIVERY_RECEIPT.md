# MTAH-IND-DATA-001 Delivery Receipt

## Delivery identity

```text
Task ID: MTAH-IND-DATA-001
Repository baseline: 8801ac724ae3d8cc14fdeb5bc5d55493030b53b8
Source branch: data/MTAH-IND-DATA-001
PR: #13 https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona/pull/13
Final commit: docs-only receipt commit containing this file
```

## SoccerTrack v2

```text
Requested revision: v1.2
Resolved SHA: 325bd4c57ee8e135ab652f3921d274526ada496b
Gate accepted by account: NOT CONFIRMED
Authenticated token: NOT PRESENT
Gated-file probe: HTTP 401
Downloaded bytes: 0
File count: 0
Manifest verification: REMOTE TREE ONLY; PASS against 244 entries / 144,847,069,949 bytes
Video verification: NOT STARTED
GSR parse verification: NOT STARTED
BAS parse verification: NOT STARTED
```

## Afriskaut

```text
Requested SHA: c972c8cd0b4489b3917516036193f8ed4f4f8f01
ZIP SHA-256: NOT COMPUTED; NOT DOWNLOADED
Match count: NOT INSPECTED
Event count: NOT INSPECTED
Event-map review: NOT STARTED
Reason: SoccerTrack access preflight did not pass
```

## Metrica

```text
Status: LICENSE_UNRESOLVED / ACQUISITION_DEFERRED
```

## Label availability

```text
Available data: remote metadata and pinned tree only
Available labels: none payload-verified
Usable supervision for H/A/D: NONE
Not available: SoccerTrack payloads, field schemas, videos, Afriskaut payloads, H/A/D/X truth
Licence restriction: gated CC BY 4.0 dataset; no training/publication/redistribution authorization
```

## Required validation commands

From the repository root:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest -q -W error
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
git diff --check 8801ac724ae3d8cc14fdeb5bc5d55493030b53b8...HEAD
git status --porcelain
```

The preceding blocked-run verification passed:

```text
pytest -q -W error: 96 passed
Ruff check: PASS
Ruff format --check: PASS
git diff --check: PASS
worktree: clean
```

## Final status

```text
BLOCKED
```

The next step requires a repository-authorized actor to confirm that the current
Hugging Face account has accepted the dataset gate and to provide an
authenticated token through an approved secret mechanism. No token may be
committed or logged.
