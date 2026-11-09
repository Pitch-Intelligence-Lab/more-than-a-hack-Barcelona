# Tang Candidate B — Experiment Decision Records

## ED-01: Contest gate and validity cleanup

- Hypothesis: split visible votes and close distances should not force H/A.
- Implementation: `contest_margin_m=1.5`; contested frames are unresolved.
- Observed: H/A possessions 436 -> 410; uncertain frames increased.
- Decision: retain; it reduces unsupported team decisions.

## ED-02: D-specific smoothing

- Hypothesis: H/A noise and D boundary response need different time scales.
- Implementation: H/A 50-frame smoothing, D 5-frame smoothing.
- Observed: D segments became more responsive; later control-zone tuning reduced D fragmentation.
- Decision: retain the two time scales.

## ED-03: Low-confidence short-segment filter

- Hypothesis: filtered/semi-Markov segment scoring can remove low-quality flicker while preserving
  high-confidence quick switches.
- Implementation: short H/A/D segments merge only when mean confidence is low and both neighbours
  share the same team.
- Observed on real data: no output change; residual short segments were high-confidence.
- Decision: retain as a conservative guard, not as an accuracy claim.

## ED-04: Five-metre control zone

- Hypothesis: outside a control radius, the nearest-player signal should be treated as uncertain.
- Literature basis: possession-zone/duel-zone work (arXiv:2202.00804), loosened for noisy tracking.
- Observed: 406 -> 384 H/A possessions; D 101 -> 96; invalid/uncertain frames 64,443 -> 84,153.
- Decision: retain in the stable candidate; record the abstention trade-off.

## ED-05: Smart Tagging ablation

- Hypothesis: Smart Tagging should contribute team/restart and long dead-ball evidence.
- Implementation: disable Smart Tagging with the same L1/L2/L3.
- Observed: D frames 29,630 -> 11,974; D mean 12.3 s -> 6.7 s.
- Decision: keep Smart Tagging enabled, but only as weak/restart/dead-ball evidence.

## ED-06: Fixed dwell

- Hypothesis: a minimum state duration reduces flicker.
- Implementation: 0.6 s and 1.2 s age-augmented Viterbi.
- Observed: 0.6 s did not change segment counts; 1.2 s reduced H/A to 377 but increased D to 186.
- Decision: reject fixed dwell; keep only as experimental configs.

## ED-07: Evidence-strength hysteresis

- Hypothesis: strong H/A probability margins can justify a faster transition than weak evidence.
- Implementation: transition-cost discount proportional to the evidence margin, capped at 2 logits.
- Observed: synthetic strong switch preserved and weak flicker suppressed; real output remained
  384 H/A and 96 D, with only boundary-frame changes.
- Decision: keep experimental; no stable-main change without independent evidence.

## ED-08: Relative time-to-ball

- Hypothesis: player/ball closing motion can resolve ambiguous tracking frames.
- Implementation: project relative velocity onto the ball direction, compute team time-to-ball,
  and apply it only where tracking is already invalid, contested or loose.
- Observed: synthetic closing/receding test passed; real output became 419/90 at weight 1.0 and
  401/94 at weight 0.4, versus 384/96 in the stable main.
- Decision: reject for the stable main because it increases H/A fragmentation. Keep both weight
  variants for comparison.

## ED-09: Local per-frame decision log

- Hypothesis: transition errors need frame-level explanations, not only aggregate health.
- Implementation: optional `--decision-log` CSV with derived features, confidence and reason.
- Observed: 199,320 local lines on the full match; synthetic test passed.
- Decision: retain as a local diagnostic tool; keep it outside Git and cloud uploads.

## ED-10: Local pressure advantage

- Hypothesis: a five-metre player-count advantage can resolve contested frames.
- Implementation: use only contested frames, require a strict count advantage.
- Observed: 402 H/A and 95 D segments at weight 1.0; fragmented versus the 384/96 stable main.
- Decision: keep as an experiment; do not promote.

## ED-11: Lower restart recovery cost

- Hypothesis: a stronger restart boost and lower D→H/A penalty will reduce restart recovery delay.
- Implementation: restart penalty 1.5, restart boost 2.5.
- Observed: H/A 399, D 208; D segmentation doubled.
- Decision: reject; stable restart costs remain.

## ED-12: Tracking-anomaly slot gating

- Hypothesis: removing implausible player slots from the current tracking frame will reduce bad team evidence.
- Implementation: per-slot speed >15 m/s or acceleration >50 m/s² makes that slot missing for the frame.
- Observed: synthetic jump test passed; real output remained 384/96 with only small label/invalid changes.
- Decision: keep experimental; tracking jumps are not the dominant segmentation driver.
