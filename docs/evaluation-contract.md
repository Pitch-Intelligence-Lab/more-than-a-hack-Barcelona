# External Evaluation Contract

**Version:** 1.1.0

**Status:** PR open; unapproved for merge

**Source:** PR #3 at reviewed commit `b4630764565bf9ce9f8a65069454ec8c47151024`, based on research branch `feature/DP-006-generalisation-dead-ball`

**Target model under review:** DP-005 v1.2 remains provisional; DP-006 remains diagnostic

## ModelInput boundary

The model receives only:

```text
ModelInput
├── TrackingData
│   ├── frame count
│   ├── team identities and slot mapping
│   ├── ball positions
│   ├── player-slot positions
│   ├── frame alignment
│   └── optional slot speeds
└── AllowedEventEvidence
    ├── approved ungraded mask
    ├── approved confirmed-dead mask
    ├── approved restart evidence
    └── source codes
```

Possession group, possession player ID, proxy labels and proxy sources are evaluation-only. They are not fields of `TrackingData`, `AllowedEventEvidence` or `ModelInput`.

Phase team fields do not determine H/A. Approved phase intervals and restart evidence may affect only the confirmed-dead and restart states for which they are explicitly enabled.

The raw provider object is consumed by the adapter and evaluation target builder. It is not passed into state inference or cleanup.

## Observation quality

Source quality retains three categories:

| Source quality | Meaning |
|---|---|
| detected | Provider marked the observation as detected |
| extrapolated | Provider supplied an extrapolated position |
| missing | No finite source position |

The current model policy excludes extrapolated positions from `TrackingData` and treats them as unavailable. This exclusion does not erase the source-quality category in `NeutralMatch`.

Model-usable quality is separate:

- detected positions may enter `TrackingData`;
- extrapolated positions are excluded under the current policy;
- short internal gaps may later be filled by the target engine's bounded interpolation;
- absent positions remain missing.

## Evaluation-only target

External possession is a proxy target:

- home/away possession group maps to H/A;
- missing possession inside an active phase maps to X;
- missing possession with no active phase inside a declared period maps to D;
- outside-period or missing-row frames map to X.

The target is consumed only after model prediction. It is not an input to prediction, cleanup or candidate selection.

DP-006 phase-gap prediction is structurally coupled to the proxy D definition because both use phase intervals. Its development result is diagnostic and cannot establish independent generalisation.

## Splits and lifecycle

Splits are assigned by whole match and must be disjoint.

Lifecycle values:

| Status | Meaning |
|---|---|
| `diagnostic_only` | Development diagnostics only |
| `ready_for_validation` | Frozen candidates may be checked on validation matches |
| `ready_for_promotion_review` | Validation is complete; holdout promotion review may proceed |
| `promoted` | Candidate has completed approved promotion |

`ready_for_validation` does not permit promotion.

Current manifest:

- development: `2017461`
- validation: empty
- holdout: empty
- status: `diagnostic_only`

Evaluation modes and required split:

| Mode | Required split | Gate |
|---|---|---|
| diagnostic | development | at least one development match |
| validation | validation | non-empty development, validation and holdout; status ready for validation |
| promotion | holdout | non-empty all splits; status `ready_for_promotion_review` |

The CLI requires an explicit `--split`; there is no default. The selected split must match the mode.

## Fail-closed order

Evaluation performs:

1. split manifest validation;
2. explicit mode/split consistency check;
3. lifecycle and emptiness gate;
4. external root and code-commit checks;
5. external match loading;
6. prediction;
7. proxy-target scoring.

Promotion-precheck failure must result in zero external-data-loader calls.

## Metric definitions

### Frames

- Only target frames with H/A/D are graded.
- Target X frames do not contribute to class confusion or macro F1.
- Prediction X on a graded target frame counts as a miss for each of H/A/D.

### Teams and segments

H/A possessions are maximal contiguous H/A runs. D or X terminates a run. Segment F1 uses same-team one-to-one IoU matching at thresholds 0.3, 0.4, 0.5, 0.6 and 0.7, then averages F1 over those thresholds.

### Transitions

Transitions are changes between consecutive non-X states in H/A/D. X resets temporal adjacency and does not create a transition.

Predicted and target transition events are matched one-to-one within 0.5 seconds using smallest-time-distance greedy assignment. Precision is matched divided by predicted events; recall is matched divided by target events; F1 is their harmonic mean.

### D metrics

- false D: predicted D on target H/A;
- missed D: target D with predicted H/A;
- both are reported in frames and seconds.

### Match and cross-match aggregation

Per-match records retain macro F1, class F1, segment F1, transition metrics, D errors, switches, mean possession duration, label counts and a deterministic prediction hash.

Cross-match macro F1 is the arithmetic mean of each match's macro F1. Micro metrics sum per-class confusion counts and transition counts across matches before recomputing F1 and transition precision/recall.

## Provenance and identity

External reports must include:

- code commit;
- source adapter version;
- configuration schema version;
- evaluation contract version;
- source input hashes;
- every candidate prediction hash;
- deterministic report hash.

Current versions:

- source adapter: `1.1.0`
- evaluation contract: `1.1.0`
- external configuration schema: `1.0`

The report hash is computed from the canonical report payload before adding the provenance block.

## Revision 1 review status

This revision was prepared using synthetic fixtures and code already in the repository. During preparation:

- no SkillCorner API or local raw file was accessed;
- no external evaluation was run;
- no model or target parameter changed;
- no target submission was generated;
- no push, PR update or merge occurred.
