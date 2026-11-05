# External Evaluation Contract

**Version:** DP-006A draft

**Status:** local, unapproved, and not pushed

## Model-input allowlist

The state-engine input is `TrackingData` with only:

- frame count;
- home and away team identity strings;
- team-to-slot mapping;
- ball positions;
- player-slot positions;
- frame alignment metadata;
- optional slot speeds.

`neutral_to_tracking` converts provider-neutral geometry into this type. It must not copy possession labels, possession status, proxy labels or proxy sources.

External possession fields are evaluation-only. They may be used to construct proxy metrics after inference, but they must not enter `TrackingData`, `EvidenceSeries`, state transitions or cleanup.

## Phase-derived D coupling

The phase-aware DP-006 diagnostic candidate may use declared phase intervals as model evidence. The external proxy also uses phase absence to derive D. This coupling makes the development result diagnostic rather than independent validation.

Phase-aware candidate results cannot be described as target-state accuracy or generalisation performance.

## Match-level splits

Splits are assigned by whole match:

- development: diagnostic engineering and rule comparison;
- validation: compare frozen candidates only;
- holdout: final generalisation check after parameter freeze.

No frame-level random split is allowed. Match IDs must be unique and disjoint across splits.

The current manifest is diagnostic only:

- development: `2017461`
- validation: empty
- holdout: empty
- status: `insufficient_for_generalisation`

## Diagnostic mode

Diagnostic evaluation requires at least one development match and permits the current one-match manifest. It can produce aggregate development metrics, but it cannot authorise promotion or a final-candidate claim.

## Promotion gate

Promotion is allowed only when all conditions hold:

1. development is non-empty;
2. validation is non-empty;
3. holdout is non-empty;
4. status is exactly `ready_for_validation`;
5. splits remain disjoint.

The one-match manifest intentionally fails this gate. Promotion mode validates the gate before reading external match data.

## Required metrics and provenance

External reports include:

- macro F1 and H/A/D class F1;
- possession-segment F1 proxy;
- transition precision, recall, F1 and matched count;
- false-D and missed-D frame counts and durations;
- team switches and mean possession duration;
- deterministic prediction hash;
- source file hashes;
- match ID and split identity;
- model-input and source provenance.

Transition F1 is the harmonic mean of transition precision and recall. Precision and recall remain separately reported.

## DP-006A review status

DP-006A changes were prepared from synthetic fixtures without reading the local SkillCorner files, running external evaluation, changing target parameters, building a target submission, pushing, or opening a pull request.
