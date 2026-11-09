# Tang Candidate B — Stable Algorithm Specification

This document describes only the stable main candidate (`configs/candidates/tang/candidate-b.json`),
not the dwell, hysteresis or Smart-Tagging ablation experiments.

## 1. Scope and contract

- Input: tactical ATD metadata/raw tracking and Smart Tagging from `MTAH_DATA_DIR`.
- Output: 199,319 rows, frames 0..199318, labels H/A/D/X.
- Frozen L0/L4: supplied by the stable base; Candidate B does not change them.
- Generalisation: `GENERALISATION NOT ESTABLISHED`.

## 2. L1 evidence

For each frame:

1. Map ATD `frame_id` 1..199319 to submission frame 0..199318.
2. Prepare ball observations: observed, interpolated or missing.
3. Compute nearest visible home/away player distance in metres.
4. Compute a small visible-player neighbourhood vote (k=3).
5. Combine nearest distance and vote into a tracking candidate.
6. Detect split contests: both teams close and vote split -> no forced team.
7. Detect loose ball: nearest player beyond 5 m -> no forced team.
8. Detect visible ball outside the normalized pitch -> dead-ball evidence.
9. Detect ball rest duration/speed and Smart Tagging phase/restart evidence.
10. Smart Tagging team is used only when tracking has no candidate; tracking wins conflicts.

## 3. L2 emission

The emission is a normalized probability triple `[p_H, p_A, p_D]`:

- team distance evidence contributes negative scaled distance to H/A;
- visible-player vote contributes a normalized H/A term;
- a tracking candidate adds a H/A bonus;
- Smart Tagging team adds a weak H/A term only when tracking has no candidate;
- D receives ball-rest, out-of-bounds and Smart-Tagging restart-anchored dead-ball evidence;
- restart evidence lowers the D score.

Invalid/uncertain frames use uniform probabilities and `valid=False`. A missing ball alone does
not create D.

## 4. Temporal smoothing

- H/A probabilities use a centred 50-frame (2 s) smoothing window.
- D probabilities use a separate centred 5-frame (0.2 s) window.
- Smoothing never crosses an ungraded block or the forced-dead block.

## 5. L3 decoding

- Three-state Viterbi over H/A/D.
- Self-transition cost 0; H↔A switch cost; H/A↔D entry/exit costs.
- D→H/A cost is reduced by active restart evidence.
- Ungraded blocks emit X and reset temporal state.
- Frames 110808..113741 are forced D.
- Short H/A flicker and low-confidence short segments may be absorbed only when bracketed by the
  same team.

The stable config has `dwell_frames=0`, `hysteresis_gain=0` and `time_to_ball_weight=0`.
The duration-aware, hysteresis and relative-velocity paths are experiments, not part of the stable
algorithm.

## 6. Reproduction

```bash
MTAH_DATA_DIR=/mnt/d/mtah2027-data \
  .venv/bin/python scripts/build_candidate_tang.py \
  --output outputs/candidate-b.csv \
  --config configs/candidates/tang/candidate-b.json \
  --health-report outputs/candidate-b.health.json \
  --decision-log outputs/candidate-b.decision-log.csv \
  --force
.venv/bin/python scripts/validate_submission.py outputs/candidate-b.csv
```

Stable output SHA-256:

```text
db2400dc0de196e814438401797326c358c1d8c2486e0cd22c24aab182127b69
```

The optional decision log is a local diagnostic artifact only. It must remain under `outputs/`
or another ignored local directory and must not be committed or uploaded.

## 7. Known limitations

- No independent evaluation data; no claim of spellF1 improvement.
- Tracking gaps and identity switches remain major error sources.
- Smart Tagging phases are weak evidence and are not possession labels.
- The 5 m control gate improves continuity but increases uncertainty to 84,153 frames.
- Aggregate possession counts are diagnostics, not accuracy evidence.
