# Candidate Handover Card — Tang Candidate B

**Candidate name:** Tang Candidate B — Evidence → H/A/D Emission → Viterbi  
**Git Commit:** D evidence-support optimization commit on `research/tang/independent-v1`
**Work branch:** `research/tang/independent-v1`  
**Model overview:** L1 frame evidence with a split-contest gate and 5 m control-zone limit, L2
normalized H/A/D emission probabilities with 50-frame H/A smoothing and 5-frame D smoothing, L3
three-state Viterbi decoder with explicit transition costs, low-confidence segment filtering,
D evidence-support constraints, X/forced-block handling and conservative H/A flicker absorption.

## Module structure

- `src/mtah_possession/candidates/tang/features.py`: L1 evidence.
- `src/mtah_possession/candidates/tang/emission.py`: L2 H/A/D probabilities.
- `src/mtah_possession/candidates/tang/decoder.py`: L3 Viterbi decoder.
- `src/mtah_possession/candidates/tang/smart_tagging.py`: candidate-local SportsCode reader.
- `src/mtah_possession/candidates/tang/adapter.py`: frozen L0/L4 adapter.
- `scripts/build_candidate_tang.py`: repository-friendly CLI.

## Run environment

- Python 3.12
- NumPy 2.5.4
- pytest 9.2.0
- Ruff 0.17.3
- No pandas, external API, network model, SkillCorner or external match data

## Input requirements

- `MTAH_DATA_DIR` points to a local folder containing `tactical/` and `broadcast/`.
- Required files: tactical ATD metadata/raw tracking and Smart Tagging XML.
- Candidate config: `configs/candidates/tang/candidate-b.json`.

## Output requirements

- `frame,label` CSV with 199,319 rows and frames 0..199318.
- Labels H/A/D/X.
- Aggregate health JSON.

## Reproduction command

```bash
MTAH_DATA_DIR=/mnt/d/mtah2027-data \
  .venv/bin/python scripts/build_candidate_tang.py \
  --output outputs/candidate-b.csv \
  --config configs/candidates/tang/candidate-b.json \
  --health-report outputs/candidate-b.health.json \
  --force
.venv/bin/python scripts/validate_submission.py outputs/candidate-b.csv
```

## Test results

- Candidate synthetic tests: 24 passed.
- Full repository: 88 passed (64 frozen + 24 candidate).
- `pytest -W error`: 88 passed.
- Ruff check: pass.
- Ruff format check: pass.

## Validator result

Project validator: pass for the current 199,319-row output. The previous official-format
validator run passed the same row/frame contract, but must be rerun for the final handover output.
This is a format check only, not an accuracy result.

## Legal evaluation evidence

None. No approved external data and no independent evaluation split were used. The public
five-minute ground truth was not used for training, tuning or model selection.

**Generalisation status:** `GENERALISATION NOT ESTABLISHED`

## Aggregate local result

- Labels: H=72,161, A=59,966, D=26,730, X=40,462.
- Segments: H=201, A=189, D=85.
- Mean durations: H=14.360 s, A=12.691 s, D=12.579 s.
- Contested frames: 24,989; loose-ball frames: 29,815; emission valid/invalid: 115,166 / 84,153.
- D evidence: 32,381 frames have an exact explicit source; 377 final D frames have no exact
  current source but sit inside the five-frame smoothing halo; 0 final D frames are outside that
  halo.
- Change scope: 3,100 of 199,319 frames changed versus the previous stable output; 2,900 are
  D→H/A, 200 are H/A boundary shifts, and no X label changed.
- D/tracking overlap: 1,303 frames total. Only 304 have strong forced/ball-rest/out-of-bounds
  support; the 999 weak-only overlap frames remain H=640, A=328, D=31.
- Output SHA-256: `f24bdbcca46170ba2e42d3dff08cd7c56279a8913febb3f1aa4e26a840f06c47`.
- Repeat run: byte-identical.

## Main failure modes

- Tracking candidates are still noisy; H/A segmentation remains higher than the conservative
  DP-005 state machine.
- Smart Tagging team labels are phases, not possessions; 4,400 tracking/Smart-Tagging conflicts
  remain explicit diagnostics.
- Missing/contested/loose-ball evidence makes the emission invalid on 84,153 frames; Viterbi
  persistence handles them but cannot recover evidence that is not present. The 5 m control limit
  improves continuity at the cost of more abstention.
- No cross-match evidence; aggregate plausibility is not accuracy.

## Ablation

Disabling Smart Tagging in `configs/candidates/tang/candidate-b-no-smart.json` produces
H=74,122, A=72,761, D=11,974, 333 H/A possessions and 72 D segments. It removes the long
Smart-Tagging-assisted dead-ball stretches (D mean falls from 12.3 s to 6.7 s). This shows a
material contribution to D in this dataset, not accuracy or generalisation.

## Known limitations

- No calibrated probabilities; `normalized_probability` is a score interface, not a statistical
  calibration claim.
- No external training, tuning, bootstrap or cross-match generalisation.
- The decoder no longer creates D purely from temporal persistence. The 377 D frames without an
  exact source are bounded to the documented five-frame smoothing halo.
- A duration-aware Viterbi path is implemented and tested but disabled in the main config:
  0.6 s dwell did not change segment counts and 1.2 s strong dwell increased D segments from 96
  to 186. The experimental configs remain for independent comparison.
- Evidence-strength hysteresis is implemented and tested. It preserves strong quick switches and
  suppresses weak flicker in synthetic tests, but did not change the 384/96 structure on the local
  match; the stable config keeps it disabled.
- Relative time-to-ball is implemented and tested. It resolves synthetic closing/receding cases,
  but at real-data weight 0.4 and 1.0 it increased H/A segmentation to 401 and 419; the stable
  config keeps `time_to_ball_weight=0`.
- Optional `--decision-log` writes a local frame-level diagnostic with derived features and
  confidence. It is not committed or uploaded.
- Local pressure advantage (5 m player counts, contested-only) was tested: 402 H/A and 95 D,
  but it increases H/A fragmentation; disabled in the stable config.
- A lower restart-recovery cost was tested: 399 H/A but 208 D segments; rejected.
- Tracking-anomaly slot gating was tested: synthetic jump handling passed, but the real output
  remained 384/96 with only minor label/invalid changes; disabled in the stable config.

## Interface relationship to frozen base

- Reuses frozen L0 tracking/observation/alignment and L4 CSV/validator.
- Adds only candidate-local modules and a separate candidate config.
- Does not modify `configs/state-engine.json`, frozen `pipeline/build_submission.py`,
  frozen `algorithm_config.py`, or stable tags.

## Engineering self-check conclusion

The candidate is complete enough for design/engineering review and independent comparison. It is
not a promoted or validated model. Generalisation is not established.
