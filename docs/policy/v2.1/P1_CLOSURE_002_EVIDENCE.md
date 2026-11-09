# DP-006 Policy v2.1 P1 Closure 002 Evidence

```text
Task: DP-006-POLICY-V2.1-P1-CLOSURE-002
Baseline: b3d243d2745cb530664aa3dae162cb6dae5bcd6a
Implementation commit: de79afc532f028dde862ebe088d5d858236fc229
Branch: feature/DP-006-POLICY-v2.1-proportional-access
P1 Closure implementation: FIX CANDIDATE
Policy v2.1 final acceptance: AWAITING INDEPENDENT REVIEW
Real-data research: HOLD
REPAIR-007: NOT AUTHORIZED
```

This closure changes only the six reviewed P1/P2 boundaries. It does not
redefine Source Identity, Holdout lifecycle, DP-005, frozen data, stable tags
or research tags.

## P1-A Promotion requires scoring

Before:

```text
mode=PROMOTION
plan=tracking_only
result_type=ExternalPredictionBatch
evaluation_completed=false
```

After:

```text
mode=PROMOTION
plan=tracking_only or prediction_phase_only
PolicyError: promotion requires a scored evaluation plan
loader_calls=0
ledger_path_created=false
EVALUATION_STARTED=false
```

Both `run_external_evaluation()` and the CLI validate the plan before loading a
config, opening a ledger, unsealing, or calling an external loader. PB-16 covers
both prediction-only plans and both entrypoints. PB-17 verifies the scored
Promotion lifecycle remains:

```text
SEALED_VERIFIED -> UNSEALED -> EVALUATION_STARTED -> EVALUATION_COMPLETED
```

## P1-B Scoped internal risk

`require_allowed()` now returns an authorization decision with a basis and
optional scope ID. `authorize_external_run()` records the decision in
`AuthorizedExternalRun.use_bases`, `scope_ids`, and the machine-readable run
report.

```text
valid grant:
  authorization_basis=SCOPED_INTERNAL_RISK
  scope_id=RISK-INTERNAL-CLOSURE-002
  LICENSE_VERIFIED remains HOLD

invalid grant:
  expired or not-yet-active
  source revision mismatch
  match mismatch
  use mismatch
  missing owner or restrictions
  => denied

permanently denied uses:
  final_candidate
  publication
  source_redistribution
  derived_redistribution
```

Scoped internal risk is limited to `download_store` and `read_preprocess`.
It cannot authorize model training, phase input, evaluation-reference access,
or any final/public/redistribution use. Other temporal, phase, label and
ModelInput gates remain in force. PB-18 through PB-20 cover these paths.

## P1-C Exposure Register

The machine-readable register is:

```text
configs/policy/exposure-register-v1.json
```

The production authorization chain requires a matching register record for
every Holdout match. Missing records fail closed. The selected records are
returned in the report as `exposure_disclosure`.

```text
ID_ONLY / METADATA_SEEN       -> allowed and disclosed
TRACKING_SEEN or higher       -> denied
MODEL_EXPERIMENT_USED         -> denied
EVALUATION_REFERENCE_SEEN     -> denied
HOLDOUT_RESULT_SEEN           -> denied
2017461                       -> development-only
split metadata change         -> does not clear exposure history
```

PB-12 exercises the production Runner path, not a helper. All denied probes
assert external loader calls are zero.

## P1-D Structural audit

Structural mode now reports only structural phase facts:

```text
phase_rows
phase_interval_valid
phase_coverage_frames
```

PB-22 patches `derive_gap_dead_directives()` and
`compile_phase_evidence()` to raise, sets `EVALUATION_AUTHORIZED=HOLD` and
`PHASE_SEMANTICS_VERIFIED=HOLD`, and still obtains a successful structural
report. The structural output contains no `phase_gap_dead_frames` and no
`proxy_counts`.

Proxy mode remains the only mode that derives phase-gap dead evidence and
requires its separate authorization profiles.

## P1-E PredictionSource projection

`PredictionSource.phases` now contains `PredictionPhaseInterval` values only:

```text
start_frame
end_frame
period
source
```

`phase.team`, provider phase kind, restart and dead-ball truth are not exposed
through `PredictionSource`. Full `PhaseSpan` evidence remains available only
in the post-prediction `EvaluationReference`.

PB-21 verifies the exact field set and the absence of team, kind, restart and
dead-ball accessors. PB-02 continues to verify tracking-only mode does not read
phases.

## Observed-use evidence

Observed use now distinguishes declaration from execution:

```text
evaluation_reference_read=false
  -> set true only after the actual reference loader/callback returns

transformed_feature_families
  -> tracking_geometry only when the tracking branch runs
  -> phase_event_evidence only when the phase candidate branch runs

runtime phases without a declared phase/evaluation use
  -> rejected
```

PB-23 verifies the callback count, reference-read transition, tracking-only
feature family, full-scored phase family, and observed-use overflow rejection.

## Regression evidence

```text
PB-01 through PB-23: PASS
Prior 287 tests: retained
Full suite: 312 passed
Strict suite: 312 passed with -W error
Invalid external root: 312 passed
External root existed: no
Ruff check: PASS
Ruff format --check: PASS
git diff --check: PASS
```

## Frozen and safety checks

```text
Stable tag: foundation-stable-dp005-v1.2.0-2026-11-06
Stable commit: c4b80a99695fa89f97d9a4a8296f249493bdd278
Stable tree: 599125166450341dc19a922772acc48c48ff9f57
Research tag: foundation-research-dp006a-v1.1.0-2026-11-06
Research commit: cdfeaf3d1f06914a255c291859315f766eb8a945
Frozen data package SHA-256: 8b053decd116b0f7913c6bc234cc82c48eb03a4ac93241ed632f975c9fe896b4
DP-005 modified: no
Stable/research tag moved: no
Frozen data modified: no
External config/split/holdout files modified: no
Real external data accessed: no
Training/tuning run: no
Real evaluation run: no
Active Holdout enabled: no
REPAIR-007 started: no
```

## Review boundary

This is a fix candidate for independent P1 Closure re-review. It is not a
Policy v2.1 PASS claim and does not approve a PR merge or any real-data use.
