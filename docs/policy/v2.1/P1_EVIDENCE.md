# DP-006 Policy v2.1 P1 Evidence

**Baseline:** `b6f61a475600498ae7993b352ecb8b94e19c77ec`

**Implementation commit:** `6788c6ceac6ad9ad0bbbf4a74edae9cf324c3100`

**Branch:** `feature/DP-006-POLICY-v2.1-proportional-access`

## Status

```text
P0 call-chain verification: DELIVERED
P1 bounded implementation: FIX CANDIDATE
Policy v2.1 final acceptance: NOT CLAIMED
PB-01 through PB-15: PASS
Existing 271 tests: PRESERVED
Real-data research: HOLD
REPAIR-007: NOT AUTHORIZED
```

## P0 artifacts

- `docs/policy/v2.1/CALL_CHAIN_MATRIX.md`
- `docs/policy/v2.1/DATA_BOUNDARY_MATRIX.md`

P0 found no requirement to rewrite Source Identity, Holdout, DP-005 or frozen
data. The default Holdout manifest is `unassigned` with an empty match set.

## Policy v2.1

```text
config: configs/policy/external-data-policy-v2.1.json
schema: schemas/external-data-policy-v2.1.schema.json
```

Policy v2 is retained as historical/compatibility policy. Production defaults
for Runner, Evaluate, Audit and Migration now use v2.1.

Scoped internal risk acceptance:

```text
scope_id
provider
source_revision
match_ids
allowed_uses
restrictions
risk_owner
accepted_at
review_at
status=PROJECT_RISK_ACCEPTED_INTERNAL
```

The status cannot replace `LICENSE_VERIFIED` and cannot authorize final
candidate, publication or redistribution.

## PredictionSource / EvaluationReference

```text
PredictionSource
  metadata
  periods
  tracking geometry
  observation quality
  approved phase/event evidence
  source checksums/identity

EvaluationReference
  possession group/player reference
  evaluation phase truth
  same source checksums
```

The production evaluator builds predictions first. An evaluation reference is
constructed only through the post-prediction callback and must share the
PredictionSource checksum identity.

## Observed-use evidence

Tracking-only:

```text
read_roles=license,readme,tracking,match
transformed_feature_families=tracking_geometry
evaluation_reference_read=False
```

Full-scored:

```text
read_roles=license,readme,tracking,match,phases
transformed_feature_families=tracking_geometry,phase_event_evidence
evaluation_reference_read=True
```

Observed phase reads without a phase declaration fail closed. Phase HOLD blocks
phase candidates but does not block tracking-only prediction.

## Audit split

```text
audit --mode structural
  -> READ_PREPROCESS only
  -> no label profiles
  -> no proxy
  -> works while evaluation reference is HOLD

audit --mode proxy
  -> evaluation reference + label profiles
  -> proxy generation
  -> fails when evaluation/label gates are HOLD
```

## PB results

| Test | Result |
|---|---|
| PB-01 | Phase HOLD does not block tracking-only; phase candidate remains blocked |
| PB-02 | Tracking-only loader does not read phases |
| PB-03 | Prediction-only path does not read possession reference |
| PB-04 | Reference is built after prediction hashes |
| PB-05 | Unauthorized possession training target is rejected |
| PB-06 | Invalid label profile cannot be evaluation reference |
| PB-07 | Undeclared phase candidate/read is rejected |
| PB-08 | Structural audit runs with evaluation HOLD |
| PB-09 | Proxy audit fails with evaluation HOLD |
| PB-10 | Scoped internal risk cannot authorize final candidate |
| PB-11 | `2017461` cannot become holdout |
| PB-12 | Historically exposed matches cannot become holdout |
| PB-13 | Projection checksum mismatch is rejected |
| PB-14 | Phase evidence without temporal metadata fails |
| PB-15 | Holdout HOLD fails before loader |

## Quality gates

```text
pytest -q -W error: 287 passed
invalid MTAH_EXTERNAL_DATA_DIR: 287 passed
Ruff check: PASS
Ruff format --check: PASS
```

## Freeze impact

```text
Source Identity example SHA-256: 12254db9c834c7b85a55056611474a63ffd93173184d3e375e0f87684d73a5c2
DP-005 stable commit: c4b80a99695fa89f97d9a4a8296f249493bdd278
Stable tree: 599125166450341dc19a922772acc48c48ff9f57
Research tag commit: cdfeaf3d1f06914a255c291859315f766eb8a945
origin/main tree: 599125166450341dc19a922772acc48c48ff9f57
Frozen data package expected SHA-256: 8b053decd116b0f7913c6bc234cc82c48eb03a4ac93241ed632f975c9fe896b4
```

No Source Identity schema field, Holdout manifest, DP-005 artifact or frozen data
was rewritten. The changed evaluation code will produce a new Evaluation
Identity for new candidates; existing v2 results remain historical.
