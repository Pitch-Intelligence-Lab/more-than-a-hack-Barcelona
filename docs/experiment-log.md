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
