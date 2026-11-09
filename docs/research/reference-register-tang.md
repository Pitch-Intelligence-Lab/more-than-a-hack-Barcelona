# Tang Candidate B Reference Register

These references were read for method ideas only. No competition data, labels or external
training data were taken from them. No code was copied into Candidate B.

| ID | Work | Link | License / status | Relevance to Candidate B |
|---|---|---|---|---|
| R-01 | Vidal-Codina et al., *Automatic event detection in football using tracking data* (2022) | https://arxiv.org/abs/2202.00804 | arXiv paper; conceptual use only | Possession zone, duel zone, possession/duel decision tree, set-piece triggers |
| R-02 | Chacoma et al., *Modeling ball possession dynamics in the game of football* (2020) | https://arxiv.org/abs/2005.04020 | arXiv paper; conceptual use only | Possession intervals, duration statistics, duels as possession-change events |
| R-03 | Zaratiana et al., *Filtered Semi-Markov CRF* (2023) | https://arxiv.org/abs/2311.18028 | CC BY 4.0 (per arXiv HTML) | Segment-level scoring, duration modeling and filtering of candidate segments |
| R-04 | Kim et al., *SoccerCPD: Formation and Role Change-Point Detection* (2022) | https://arxiv.org/abs/2206.10926 | arXiv/KDD paper; conceptual use only | Change-point segmentation instead of frame-by-frame decisions |

## Adopted ideas

- **Possession/duel zones (R-01).** Candidate B uses a 5 m noise-tolerant control limit and a
  split-contest gate. The paper's 0.5-1 m radii are stricter than this automatic tracking feed;
  the larger bound is recorded as an engineering assumption, not as a reproduced result.
- **Relative motion (R-01).** The paper records ball displacement and incoming/outgoing direction.
  Candidate B implements an experimental team time-to-ball feature, but does not promote it: in
  the local aggregate it increased H/A segmentation.
- **Segment-level filtering (R-03).** Short H/A or D segments are merged only when their mean
  emission confidence is low and both neighbours have the same team. High-confidence quick
  switches are preserved. This is a post-decoder approximation of segment-level scoring.
- **Possession duration / duel intuition (R-02).** Candidate B treats possession as a temporal
  interval and keeps duels/contests as an explicit uncertainty state. No distribution parameters
  were fitted to this match.

## Not adopted yet

- Full semi-Markov CRF training or segment enumeration: no labels are available for this task.
- SoccerCPD's change-point graph and role-adjacency construction: a future L3 comparison, not part
  of the current deterministic decoder.
- The detailed set-piece trigger geometry from R-01: Smart Tagging already supplies set-piece and
  restart intervals; duplicating those geometric detectors would add complexity without validation.

## Compliance

- No external match data, labels, videos or tracking files were used for Candidate B.
- No public five-minute ground truth was used for parameter selection or model comparison.
- References are recorded for method provenance and independent review.
