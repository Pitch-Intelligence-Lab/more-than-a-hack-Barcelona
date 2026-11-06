# Tang Candidate B — Risk and Error Analysis

This is a risk analysis, not a confirmed error distribution. No complete ground truth was read,
so statements below identify mechanisms and diagnostics to investigate later.

## Over-segmentation risks

- Noisy nearest-player candidates near a contested ball.
- Smart Tagging phase boundaries that do not coincide with possession changes.
- Ball rest or out-of-bounds bursts that are shorter than a real stoppage.
- Viterbi transition costs interacting with a short but real possession.

Diagnostics: short H/A/D run counts, transition rate, boundary confidence, and source provenance.

## Under-segmentation risks

- Long smoothing and persistence can merge two possessions across a quick hand-over.
- A missing-ball gap can preserve the previous team after control has changed.
- A contest gate can over-abstain and let the decoder carry the previous state too long.

Diagnostics: possession duration tails, transition latency, and evidence margin around boundaries.

## Dead-ball risks

- Missing ball is not equivalent to dead ball; Candidate B avoids missing-only D.
- Low ball speed can occur during shielding or waiting for support.
- Smart Tagging set-piece windows are approximate and may include live play after restart.
- A 5 m control limit can turn a long pass into an invalid emission; persistence handles it, but
  the true team may change during the gap.

Diagnostics: D source decomposition, pre/post restart evidence, and D segment duration.

## Tracking quality risks

- Player identity switches can make a distant wrong player look like the nearest candidate.
- Extreme position jumps and implausible speeds are not yet filtered frame-by-frame.
- Missing player slots are excluded, but a single noisy visible slot can still dominate.

Diagnostics: slot jump rate, quality-conditioned confidence, and candidate disagreement.

## Competition-specific risks

- The public five-minute window is not a leaderboard and was not used for tuning.
- Aggregate structure cannot prove spellF1 improvement.
- Class imbalance makes D accuracy look better or worse depending on the metric used.
- X is not a free uncertain label at a true transition; spellF1 forward-fills abstentions.

## Current status

The stable candidate is an engineering artifact ready for design review. It is not a validated
model. Generalisation and official private score remain unknown.
