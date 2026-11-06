# Candidate Handover Card — Tang Candidate B

**Candidate name:** Tang Candidate B — Evidence → H/A/D Emission → Viterbi  
**Git Commit:** final commit on `research/tang/independent-v1`  
**Work branch:** `research/tang/independent-v1`  
**Model overview:** L1 frame evidence, L2 normalized H/A/D emission probabilities with a centred
temporal smoothing window, L3 three-state Viterbi decoder with explicit H/A/D transition costs,
X/forced-block handling and conservative H/A flicker absorption.

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

- Candidate synthetic tests: 8 passed.
- Full repository: 72 passed (64 frozen + 8 candidate).
- `pytest -W error`: 72 passed.
- Ruff check: pass.
- Ruff format check: pass.

## Validator result

Project validator: pass.

Official-format validator: pass using official commit
`f8f2629ff1e0985f81d7e59d8413678514ee1530`. The validator script's CRLF SHA-256 matches the
Action Pack value `d716bf6fce9c8a8d334a9258a3bfca63b8153ae9cd98a4bf80fe0d04693af914`;
the WSL/LF checkout hashes to `07ac29499acbd337e1dc1de1832d63f6e1fa1d981e22f6ad08212529e2bbee14`.
The official validator reports 199,319 rows and 436 possessions of mean 12.2 s. This is a format
check only, not an accuracy result.

## Legal evaluation evidence

None. No approved external data and no independent evaluation split were used. The public
five-minute ground truth was not used for training, tuning or model selection.

**Generalisation status:** `GENERALISATION NOT ESTABLISHED`

## Aggregate local result

- Labels: H=71,228, A=61,607, D=26,022, X=40,462.
- Segments: H=220, A=216, D=69.
- Mean durations: H=12.951 s, A=11.409 s, D=15.085 s.
- Output SHA-256: `866f02601da425e9545e073cf1c37de1146bd2b4b19d604173cbc14c834490a7`.
- Repeat run: byte-identical.

## Main failure modes

- Tracking candidates are still noisy; H/A segmentation remains higher than the conservative
  DP-005 state machine.
- Smart Tagging team labels are phases, not possessions; 8,964 tracking/Smart-Tagging conflicts
  remain explicit diagnostics.
- Missing ball makes the emission invalid on 28,834 frames; Viterbi persistence handles them but
  cannot recover evidence that is not present.
- No cross-match evidence; aggregate plausibility is not accuracy.

## Known limitations

- No calibrated probabilities; `normalized_probability` is a score interface, not a statistical
  calibration claim.
- No external training, tuning, bootstrap or cross-match generalisation.
- D source decomposition includes 2,014 final D frames with no current declared source, which are
  decoder persistence/context rather than an independent evidence signal.

## Interface relationship to frozen base

- Reuses frozen L0 tracking/observation/alignment and L4 CSV/validator.
- Adds only candidate-local modules and a separate candidate config.
- Does not modify `configs/state-engine.json`, frozen `pipeline/build_submission.py`,
  frozen `algorithm_config.py`, or stable tags.

## Engineering self-check conclusion

The candidate is complete enough for design/engineering review and independent comparison. It is
not a promoted or validated model. Generalisation is not established.
