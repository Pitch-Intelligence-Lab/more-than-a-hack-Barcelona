# External Development Evaluation

**Match:** `2017461`

**Split:** development only

**Proxy:** SkillCorner possession group plus explicit phase-based dead/unknown mapping

**Status:** diagnostic; not evidence of generalisation and not a final-candidate selection

## Protocol

All candidates received the same provider-neutral tracking observations and declared period boundaries. Detected positions only were used. Confirmation and state durations remained in seconds; the 10 FPS adapter changed frame counts, not durations.

The target is a proxy:

- explicit home/away possession group maps to H/A;
- no possession inside an active in-play phase maps to X;
- no possession with no active phase inside a declared period maps to D;
- outside declared periods and missing tracking rows map to X.

No organiser ground truth was read.

## Candidate definitions

- `dp001_004_baseline`: metric nearest-player candidate and a 2-second temporal majority vote.
- `dp005`: the v1.2 tracking-only state engine, with external periods mapped to ungraded X boundaries and no target-specific forced block.
- `dp006_phase_proxy`: DP-005 with ball rest removed as proof of D, plus phase-gap evidence and cleanup protection.

The DP-006 branch uses the same phase input from which the proxy's D class is derived. Its external result is therefore structurally coupled to the proxy and must not be presented as an independent generalisation result.

## Results

| Candidate | macro F1 | segment F1 proxy | false D frames | missed D frames | team switches | matched transitions |
|---|---:|---:|---:|---:|---:|---:|
| DP-001–004 baseline | 0.6703 | 0.2038 | 925 | 9,153 | 445 | 53 |
| DP-005 | 0.3265 | 0.2575 | 21 | 28,421 | 353 | 52 |
| DP-006 phase proxy | 0.7910 | 0.3258 | 2,515 | 0 | 311 | 75 |

False-D durations are 92.5 s, 2.1 s and 251.5 s respectively. Missed-D durations are 915.3 s, 2,842.1 s and 0 s.

Additional DP-006 measurements:

- H class F1: 0.7616
- A class F1: 0.6535
- D class F1: 0.9579
- Transition precision: 0.1620
- Transition recall: 0.2187
- Mean possession duration: 7.49 s
- Prediction SHA-256: `f0efba7212ddcd98fe8c34078e9ef6d057e8fc61b1afc41f853db0385240f08b`
- Aggregate report SHA-256: `8a9f8d2af046f5271afe7ee6067236c695277e9e52fbbf0b63434abb20e2e699`

## Interpretation

DP-005 improves the external possession-segment proxy over the baseline and removes most false D, but it still misses almost all proxy dead-ball frames. This matches the target smoke failure mode.

DP-006's phase-gap candidate strongly improves the proxy D metric, but it does so partly by using the same external phase source used to define the proxy. Two issues prevent promotion:

1. The target data path has no equivalent validated phase-gap source in the current model.
2. There is no validation or holdout external match.

The development comparison therefore recommends keeping DP-005 v1.2 as the provisional target candidate and retaining the DP-001–004 baseline. It does not select DP-006 as the final submission.

## Reproduction

```powershell
$env:MTAH_EXTERNAL_DATA_DIR = "E:\external-data\skillcorner"
.\.venv\Scripts\python scripts\audit_external.py `
  --output outputs\external-data-audit.json
.\.venv\Scripts\python scripts\evaluate_external.py `
  --split development `
  --mode diagnostic `
  --code-commit <full-code-commit> `
  --output outputs\external-dp006-development.json
```

The output reports are aggregate-only and remain untracked.
