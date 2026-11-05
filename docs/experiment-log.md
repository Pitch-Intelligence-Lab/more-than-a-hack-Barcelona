# Experiment Log

Never paste competition data, frame excerpts, videos or screenshots into this public file.

## E-001: Synthetic engineering verification

- Date: 2026-11-05
- Inputs: synthetic metadata and raw ATD only
- Ground truth: none
- Real tactical data: not read
- Coverage: environment failures, frame-ID conversion, missing observations, slot count, truncation, metric distance, tie handling, team mapping, majority vote, 199,319-row generation, validation failure, atomic cleanup, determinism, forbidden paths and repository asset scan
- Result: 30 tests passed; Ruff check and format check passed
- Decision: proceed to integration review and team-local tactical run

The category counts in the synthetic 199,319-row test are not claims about the match.

## E-002: Team-local tactical baseline

- Date: 2026-11-05
- Status: passed after a missing-slot regression fix
- First run: 199,319 rows; H=72,553, A=53,918, D=72,848, X=0
- Repeat run: identical byte output
- SHA-256: `caf42b0775d695e29859f775c67d42162a92d32655facb202c548b3b59fb220f`
- Project validator: passed
- Official validator: passed
- Possession count reported by the official validator: 669 segments of mean 7.6 seconds
- Inputs: tactical ATD metadata and raw tracking only
- Rule compliance: no broadcast, video, ground truth, manual labels, training, or tuning

The initial implementation produced all-D output because NaN slots contaminated each team's minimum distance. The fix ignores non-finite positions and has an explicit synthetic regression test.

## E-003: Public-window implementation check

- Date: 2026-11-05
- Purpose: confirm the implemented baseline is coherent with the published baseline, without selecting parameters from the public answer
- macroF1: 0.6209
- spellF1: 0.3256
- Predicted possessions in the public window: 26
- Mean predicted possession duration: 10.8 seconds
- Decision: no parameter changes based on this result

The public five-minute answer was used only for an automated sanity check after the algorithm and configuration were frozen. It was not used for training or repeated parameter selection.

## E-004: DP-005 synthetic behavior suite

- Date: 2026-11-05
- Inputs: synthetic tracking and evidence only
- Ground truth: none
- Real tactical data: not read by the test suite
- Coverage: observed/interpolated/missing ball, short occlusion, long missing gap without D evidence, direct H to A, direct A to H, dead ball and restart, rapid pass-by candidate, short flicker, X boundaries, missing slots, health report, configuration provenance, repeated output and baseline fallback
- Result: 53 tests passed; Ruff check and format check passed
- Decision: freeze the DP-005 parameter set and run the local tactical build once

## E-005: DP-005 team-local tactical run

- Date: 2026-11-05
- Configuration: `configs/state-engine.json`
- Inputs: tactical ATD metadata and raw tracking only
- Ground truth: not read
- Training or tuning: none
- Rows: 199,319; frame range 0 through 199318
- Labels: H=81,311, A=74,490, D=3,056, X=40,462
- H/A/D segments: H=166, A=175, D=19
- Segment durations: mean H=19.593 s, A=17.026 s, D=6.434 s; all H/A/D mean=17.651 s
- Ball quality: observed=113,488, interpolated=108, missing=85,723
- Graded ball quality: observed=94,214, interpolated=39, missing=64,604
- Transitions: H->A=162, A->H=159, H->D=4, A->D=14, D->H=6, D->A=13
- Output SHA-256: `db132162c9711f01dd5ff9bca4b9867baac8ed64ded80b700944bc2c13dc0177`
- Repeat run: byte-identical SHA-256
- Project validator: passed
- Official format validator: passed
- Baseline fallback rebuild: passed with previous SHA-256 `caf42b0775d695e29859f775c67d42162a92d32655facb202c548b3b59fb220f`

The run produced no evidence that X leaked outside the configured ungraded blocks: H+A+D equals the 158,857 graded frames and X equals the 40,462 ungraded frames.

## E-006: Frozen public-window smoke test

- Date: 2026-11-05
- Timing: one automated run after DP-005 implementation and parameters were frozen
- Public window: 7,500 graded frames; 17 reference possessions
- macroF1: 0.4998
- spellF1: 0.3897
- alive/dead F1: 0.8913
- team accuracy on reference-alive frames: 0.8456
- Predicted possessions: 22 of mean 13.6 s; reference: 17 of mean 14.2 s
- Fragmentation ratio: 1.10
- D class: precision 0, recall 0, F1 0
- Abstained frames on graded reference: 0
- Decision: no parameter or design change after the smoke test

The weak D result confirms that sustained ball rest is not sufficient to recognise most dead-ball intervals. This is now a known limitation for external-data validation, not a basis for tuning on the provided match.

## E-007: PR #1 remediation and second-half boundary validation

- Date: 2026-11-05
- Tests: 64 passed
- Warning-free tests: 64 passed with `-W error`
- Ruff check and format check: passed
- Forced-dead configuration: frames 110808 through 113741
- Forced-dead result: 2,934 of 2,934 frames were D
- Rows: 199,319; frame range 0 through 199318
- Labels: H=79,250, A=73,608, D=5,999, X=40,462
- Graded total H+A+D: 158,857; X: 40,462
- H/A/D segments: H=161, A=170, D=20
- Segment durations: mean H=19.689 s, A=17.320 s, D=11.998 s
- Cleanup removals: H=0, A=0, D=0
- Transitions: H->A=157, A->H=154, H->D=4, A->D=14, D->H=7, D->A=13
- Output SHA-256: `1de6261504c7cb539a4e78f42f18011c692b9bd148ea3e77fbca44df9c0b9401`
- Repeat generation: byte-identical
- Project validator: passed
- Official format validator: passed
- Baseline fallback: rebuilt with unchanged SHA-256 `caf42b0775d695e29859f775c67d42162a92d32655facb202c548b3b59fb220f`

## E-008: Frozen public smoke after remediation

- Date: 2026-11-05
- Timing: one run after the v1.2 fixes and parameters were frozen
- macroF1: 0.4998
- spellF1: 0.3897
- D class: precision 0, recall 0, F1 0
- Predicted possessions: 22 of mean 13.6 s
- Fragmentation ratio: 1.10
- Decision: no parameter or design change after the score

The public window does not cover the repaired 110808..113741 block, so it cannot measure that defect. The unchanged public score means only that the remediation did not alter the smoke window. The D-class result remains a major unresolved limitation.

## E-009: SkillCorner Gate A audit

- Date: 2026-11-05
- Repository commit: `4340d274572876239c154c90bc507a9b3250a656`
- Match: `2017461`
- Licence: MIT
- Scope: one match, tracking plus phases plus match metadata; no body pose or video
- Frames: 71,451 at 10 FPS
- Declared-period tracking frames: 58,450
- Outside-period frames: 13,001
- Phase rows: 433; in-play coverage 28,610 frames
- Missing possession: 42,563; missing possession inside a phase: 956
- Proxy labels: H=17,796, A=11,092, D=28,606, X=13,957
- Tracking checksum: `59cfa5588efee041da439f44df5b5b92f2b7305571dc831164e3d05f7415787a`
- Aggregate report: `outputs/external-data-audit.json`
- Aggregate report SHA-256: `38c8d6727b031f7d3eeae9f9c319986498eece505d228c38e0f55c7a2d60bacc`
- Result: Gate A passed for one-match local development research only

## E-010: External development candidate comparison

- Date: 2026-11-05
- Split: development match `2017461` only
- Validation and holdout: unavailable
- Protocol: same detected observations and declared periods for all candidates

| Candidate | macro F1 | segment F1 proxy | false D | missed D | switches |
|---|---:|---:|---:|---:|---:|
| DP-001–004 baseline | 0.6703 | 0.2038 | 925 | 9,153 | 445 |
| DP-005 | 0.3265 | 0.2575 | 21 | 28,421 | 353 |
| DP-006 phase proxy | 0.7910 | 0.3258 | 2,515 | 0 | 311 |

DP-006's phase-gap candidate uses the same phase source that helps define the proxy D target. The apparent advantage is therefore structurally coupled and not independent generalisation evidence.

False-D durations are 92.5 s, 2.1 s and 251.5 s; missed-D durations are 915.3 s, 2,842.1 s and 0 s.

The aggregate comparison report `outputs/external-dp006-development.json` has SHA-256 `8a9f8d2af046f5271afe7ee6067236c695277e9e52fbbf0b63434abb20e2e699`.

## E-011: DP-006 selection decision

- Date: 2026-11-05
- Decision: do not promote DP-006 automatically
- Provisional target candidate: DP-005 v1.2
- Fallback: DP-001 through DP-004
- Reason: only one external development match is available, no target-equivalent phase source is validated, and no validation or holdout match exists
- Target smoke: unchanged from E-008 because no target-model change was selected

## E-012: DP-006 engineering verification

- Date: 2026-11-05
- Tests: 79 passed
- Warning-free tests: 79 passed with `-W error`
- Ruff check and format check: passed
- Target project validator: passed
- Official target format validator: passed
- Target output unchanged: 199,319 rows, SHA-256 `1de6261504c7cb539a4e78f42f18011c692b9bd148ea3e77fbca44df9c0b9401`
- Repository scan: no competition or external JSONL/archive data tracked
