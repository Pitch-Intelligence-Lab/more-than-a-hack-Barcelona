# One-Match 128057 Run Log

## Task

```text
Task ID: MTAH-IND-DATA-001-SMOKE
Parent: MTAH-IND-DATA-001
Match: 128057
Dataset: atomscott/soccertrack-v2
Revision: v1.2
Resolved SHA: 325bd4c57ee8e135ab652f3921d274526ada496b
```

## Preflight

```text
PR #13 head: b9da5432feddc41bcebcc269d335530951be9022
HF environment token: PRESENT via approved User environment import
Gated file ball/128057_1st_ball.npz: HTTP 200
HF_XET_HIGH_PERFORMANCE: enabled for large-file retry
Selected manifest: 23 files, 12,823,435,353 bytes
Stage 1: 20 files, 5,768,542,573 bytes
Stage 2: 3 files, 7,054,892,780 bytes
Mirror used: NO
```

The browser-verified gated download was not used as an automation credential.
No browser cookie was converted into a token and no unapproved local file was
consumed. The authenticated token was imported without printing or persisting
it.

Authenticated download command (token read from the environment, never printed):

```powershell
if (-not $env:HF_TOKEN) { $env:HF_TOKEN = [Environment]::GetEnvironmentVariable("HF_TOKEN", "User") }
.\.venv\Scripts\python.exe scripts\download_soccertrack_stage1.py `
  --manifest docs\data-acquisition\MTAH-IND-DATA-001-SMOKE\ONE_MATCH_128057_FILE_MANIFEST.csv `
  --annotations-root D:\mtah2027-data\INDEPENDENT-VALIDATION-001\SoccerTrack-v2\annotations `
  --metadata-root D:\mtah2027-data\INDEPENDENT-VALIDATION-001\SoccerTrack-v2\metadata
```

The first GSR download was retried through Xet with
`HF_XET_HIGH_PERFORMANCE=1`; it remained incomplete at approximately 192 MB of
compressed transfer and was not promoted to the final file.

## Commands/results

```text
Remote/tree and gated-file checks: PREFLIGHT_PASSED
Stage 1 complete files: 5 / 20
Stage 1 complete bytes: 681,207 / 5,768,542,573
GSR first half: partial 42,991,748 bytes; not accepted
GSR second half: not downloaded
Stage 2 download: NOT STARTED
GSR bounded parse: NOT COMPLETED; payload incomplete
Ball NPZ parse: PASS for two small files
BAS event audit: PASS for class/team/player_id counts; visibility field absent
Raw event audit: NOT STARTED; payload missing
Video decode/FPS/duration checks: NOT STARTED
Cross-source timing alignment: NOT STARTED
Local file SHA-256 registry: 5 complete files recorded
Peak memory/runtime: NOT MEASURED for the failed full Stage 1 run
```

## Final state

```text
STAGE1_FAIL
```

No data was downloaded or committed. Resume only after the gate/token
conditions in the task package are satisfied.
