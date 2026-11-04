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
