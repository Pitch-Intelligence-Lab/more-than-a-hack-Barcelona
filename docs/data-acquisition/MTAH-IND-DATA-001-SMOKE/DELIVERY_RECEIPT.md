# One-Match 128057 Delivery Receipt

## Identity

```text
Task ID: MTAH-IND-DATA-001-SMOKE
Repository: Pitch-Intelligence-Lab/more-than-a-hack-Barcelona
Branch: data/MTAH-IND-DATA-001
Baseline: 8801ac724ae3d8cc14fdeb5bc5d55493030b53b8
Previous audited HEAD: b9da5432feddc41bcebcc269d335530951be9022
PR: #13
PR base: dev
PR state: OPEN, UNMERGED
Final docs commit: docs-only commit containing this receipt
Remote HEAD: final docs-only commit after PR update
```

## Access

```text
HF token: PRESENT via approved User environment import
Gated file probe: HTTP 200
Unapproved mirror: NOT USED
Browser cookie conversion: NOT PERFORMED
```

## Selected scope

```text
SoccerTrack revision: v1.2
Resolved SHA: 325bd4c57ee8e135ab652f3921d274526ada496b
Selected files: 23
Selected bytes: 12,823,435,353
Stage 1: 20 files / 5,768,542,573 bytes
Stage 2: 3 files / 7,054,892,780 bytes
Downloaded complete files: 5
Downloaded complete bytes: 681,207
Partial GSR file: 42,991,748 bytes, not accepted
Local SHA-256 entries: 5
ZIPs: none downloaded
```

Complete local files:

| Path | Bytes | SHA-256 |
|---|---:|---|
| `D:\mtah2027-data\INDEPENDENT-VALIDATION-001\SoccerTrack-v2\metadata\CHANGES_v1_1.md` | 7,074 | `87bf4afa1907f9031af03bddb082d0a4622e113c964aac21737f6d070510fa9c` |
| `D:\mtah2027-data\INDEPENDENT-VALIDATION-001\SoccerTrack-v2\metadata\CHANGES_v1_2.md` | 8,959 | `751162ed78c4643045a21d9df4cd4fdd07519a06871ef0ea82b34c209b8e90eb` |
| `D:\mtah2027-data\INDEPENDENT-VALIDATION-001\SoccerTrack-v2\annotations\ball\128057_1st_ball.npz` | 124,396 | `e0b77001cbc4ba74c2ea882d9a40e5220ebac5f27aec702953eef1d3fe11b9bd` |
| `D:\mtah2027-data\INDEPENDENT-VALIDATION-001\SoccerTrack-v2\annotations\ball\128057_2nd_ball.npz` | 129,720 | `13fe13fc7bcb4bb19e8c57bd79f64281643b5e24eea0df52f1e24b5c8f5cc36b` |
| `D:\mtah2027-data\INDEPENDENT-VALIDATION-001\SoccerTrack-v2\annotations\bas\128057\128057_12_class_events.json` | 411,058 | `03bb79bdf9404ad9e8bb1c8c569676ec82614ea3e2360238d10ff8fd78c9f577` |

Incomplete GSR:

```text
D:\mtah2027-data\INDEPENDENT-VALIDATION-001\SoccerTrack-v2\annotations\gsr\128057\128057_1st.json.part
bytes: 42,991,748
sha256: 606876be4a826d5c81626e2e459a2a4e9a8dacc15704a86144fbc7b9fff6514e
status: PARTIAL_NOT_ACCEPTED
```

The actual download command was the masked form:

```powershell
if (-not $env:HF_TOKEN) { $env:HF_TOKEN = [Environment]::GetEnvironmentVariable("HF_TOKEN", "User") }
.\.venv\Scripts\python.exe scripts\download_soccertrack_stage1.py --manifest <manifest> --annotations-root <D_ROOT> --metadata-root <D_ROOT>
```

Download tooling: `huggingface_hub==2.4.0`, `hf-xet==1.8.0`. Audit parser:
`ijson==3.6.0`, NumPy `2.5.4`, Python `3.12.10`.

The selected manifest was independently compared against the package:

```text
23 rows
12,823,435,353 bytes
Stage 1: 20 rows / 5,768,542,573 bytes
Stage 2: 3 rows / 7,054,892,780 bytes
manifest differences: 0
```

## Verification

```text
Local payload roots: present
GSR parse: NOT COMPLETED; incomplete first-half payload
Ball parse: PASS for two small files
BAS/raw event audit: BAS parsed; raw event payload missing
Video audit: NOT STARTED
Timing/alignment audit: NOT STARTED
Peak memory/runtime: NOT MEASURED
```

## Final status

```text
FAIL
```

This receipt does not authorize model work, feature selection, lockbox access,
training, tuning or redistribution. Resume only after approved authenticated
access or approved staged files are provided.
