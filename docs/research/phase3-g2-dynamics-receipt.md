# Phase-3 G2 Dynamics Engineer Receipt

## 1. Delivery identity

```yaml
task_id: MTAH-PHASE3-G2-EXTRACTOR-001
repository: Pitch-Intelligence-Lab/more-than-a-hack-Barcelona
branch: feature/MTAH-PHASE3-G2-DYNAMICS
baseline: 1ed6dd0e9b2160b39bd419f3c7223261f446d6a0
implementation_commit: 1df76a8f6eb216dcf0c3d31e637632dcd5cdeab6
pull_request: https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona/pull/12
base_branch: dev
merge: withheld
training: not started
```

The PR advances to the final docs-only commit containing this receipt.

## 2. Implemented scope

The independent G2 layer derives causal `delta5__` and `delta25__` columns for
the 15 approved base features. It reads only `features.csv.gz` and its sibling
`metadata.json`, uses no future rows, and does not modify `P2-FS-0.1`,
`reference.csv.gz`, event data or provider status/possession.

Output columns are exactly:

```text
match_id
frame_number
game_section
delta5__<15 features>
delta25__<15 features>
```

## 3. Modified files

| File | Reason |
|---|---|
| `src/mtah_possession/research/phase2/g2.py` | causal G2 derivation, validation and atomic output |
| `src/mtah_possession/research/phase2/g2_cli.py` | `derive-g2` CLI |
| `tests/research/phase2/test_g2_extractor.py` | G2 regression matrix |
| `docs/research/phase3-g2-dynamics.md` | operator and schema documentation |
| `docs/research/phase3-g2-dynamics-receipt.md` | this delivery receipt |
| `README.md` | G2 usage entry point |

## 4. Tests

```text
pytest -q -W error: 94 passed
ruff check .: PASS
ruff format --check .: PASS (63 files)
git diff --check: PASS
```

New tests cover:

- exact 5-frame and 25-frame differences;
- run-start and half/frame-gap isolation;
- missing current/historical values;
- fixed output order and columns;
- signed home/away swap behavior;
- deterministic gzip bytes;
- overwrite refusal;
- provider/reference schema rejection;
- input/output metadata hashes;
- input metadata hash mismatch fail-closed.

## 5. Real development runs

The command used for each match was:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m mtah_possession.research.phase2.g2_cli derive-g2 `
  --features <features.csv.gz> `
  --output-dir <outputs\phase3\g2\<match>>
```

WMX and WOH are complete derivations; WOY, WPY and WQQ are schema/smoke
derivations. All five have exactly one G2 row per input feature row and two
continuous half runs.

| Match | Input rows | G2 rows | Runs | Elapsed s | G2 SHA-256 |
|---|---:|---:|---:|---:|---|
| `J03WMX` | 145,967 | 145,967 | 2 | 18.271 | `0e53f751c948ae94b9fd6ce7e823343468dab4a15e1c765fb222991f46869e60` |
| `J03WOH` | 137,214 | 137,214 | 2 | 17.137 | `5b5b51e761a89db3ab58f1cd43dfb289bf0c347d2144552755ed6703f6e0d504` |
| `J03WOY` | 142,536 | 142,536 | 2 | 17.899 | `737fcc9b175d98e71172cbf6e727153f3f418b43313e377205201ba98d0e24f4` |
| `J03WPY` | 146,211 | 146,211 | 2 | 18.239 | `d7386e07709840f48104cb713bb662c00403bd101b86b72b21dde3218aadacfc` |
| `J03WQQ` | 142,345 | 142,345 | 2 | 17.776 | `c6a4fbcc0162109764a16ae2ebd45fd03045cad92f3be9194dd431b3ae35f701` |

WMX metadata core values:

```text
g2_schema_version=P2-G2-0.1
input_schema_version=P2-FS-0.1
input_features_sha256=bf6b65ea6237d57101931f8d59b4f2c36af24e982ff76da4662214697c05918a
rows=145967
run_count=2
section_boundary_count=1
frame_gap_count=0
repository_head=1df76a8f6eb216dcf0c3d31e637632dcd5cdeab6
implementation_commit=1df76a8f6eb216dcf0c3d31e637632dcd5cdeab6
source_tree_dirty=false
```

Missingness summaries:

| Match | Lag | Columns | Missing total | Missing min | Missing max | First 25 rows total |
|---|---:|---:|---:|---:|---:|---:|
| `J03WMX` | 5 | 15 | 68,000 | 10 | 6,795 | 75 |
| `J03WMX` | 25 | 15 | 70,000 | 50 | 6,975 | 375 |
| `J03WOH` | 5 | 15 | 14,520 | 10 | 1,447 | 75 |
| `J03WOH` | 25 | 15 | 15,720 | 50 | 1,547 | 375 |

The complete per-column missing counts are recorded in each
`g2_metadata.json`.

## 6. Boundary

This is a feature-engineering implementation only. It does not train, select a
model, evaluate a lockbox, use public five-minute GT, or alter DP-005, DP-006,
Holdout, Exposure Register or the frozen CDA package. PM must rerun the
G0+G1 versus G0+G1+G2 comparison before model-research acceptance.

```text
G2 implementation complete for PM review
merge: withheld
model research: pending PM rerun
```
