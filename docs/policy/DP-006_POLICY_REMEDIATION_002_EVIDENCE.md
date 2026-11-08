# DP-006 Policy Remediation 002 Evidence

> Historical second-round evidence. R3 was subsequently returned for ledger
> state-machine remediation under DP-006-POLICY-REMEDIATION-003. See
> `DP-006_POLICY_REMEDIATION_003_EVIDENCE.md` for current R3 evidence.

**Task:** DP-006-POLICY-REMEDIATION-002

**Review baseline:** `20595823ac3c2973a371324b17bb1fdda1d64aca`

**Branch:** `feature/DP-006-POLICY-v2`

**PR:** #9

**Result:** remediation candidate submitted for PM/QA review

## Status

```text
R3 Holdout: FIX CANDIDATE, PM/QA review required
R5 Temporal: FIX CANDIDATE, PM/QA review required
Policy implementation final acceptance: HOLD
Real-data research: HOLD
Merge: DENIED
```

## R3 before and after

### Before

- Promotion did not bind `HOLDOUT_SEAL_VERIFIED`, the holdout match set, or the
  current match to the declared split.
- Freeze hashes were trusted CLI strings rather than values computed from the
  model, feature, configuration, hyperparameter, evaluator and metric artifacts.
- Holdout unseal, result, failure and compromised events had no production
  append-only persistence.

### After

- Promotion checks `HOLDOUT_SEAL_VERIFIED=PASS`, a non-empty holdout manifest,
  exact equality with `split_manifest.holdout`, and current-match membership
  before `match_loader`.
- `compute_freeze_hashes()` resolves six artifact categories, rejects path
  escapes, missing paths and symlinks, hashes sorted files, and derives category
  hashes from the resulting path-and-file-digest payload.
- `HoldoutManifest.require_frozen()` compares the computed identity with the
  sealed manifest for every Promotion run.
- `outputs/holdout/<holdout-key>.jsonl` is append-only and persisted with
  `flush()` plus `fsync()`. Each record carries a timestamp, event type,
  holdout ID, match IDs, freeze identity, manifest hash, code commit, prediction
  hash, previous-record hash and reason.
- Policy authorization failure creates or appends a `COMPROMISED` record when a
  loaded holdout, valid code commit and writable ledger are available.

Current computed artifact identity:

```text
model=9843dcf2969e770452e3d7e1e6add6bcb6edaaaf4e7184bfbd3d21746503dfe3
feature_set=2d1ac11c13cacb303b139dda5d0d2cad82fefc0c35b33bb47a720ee28c07ec2e
configuration=e6c556db41f67ee43198da74fbbd67cbf059b236ef5384a7b6950f866a24fd25
hyperparameters=0712e6e94145ff7445d4c06f08769a24144f5d641287893ed8f59d612a9db3f5
evaluation_script=2f468d3bf1dc7ae18121be3ab122659c510a47c477ae4c8a0129255ecd196d1d
metric_contract_version=1.1.0:25ec4f45bd0e01cde9bd61fa4e7463b2adb42e5aef484e154f639aa768444a49
```

## R5 before and after

### Before

The production path started with empty temporal metadata. `with_event_evidence()`
inherited that empty tuple, so the real evaluator validated no event-derived
fields and an empty registry acted as a pass condition.

### After

- `PhaseLayerEvidence` carries temporal provenance for
  `forced_dead_mask`, `restart_evidence` and `source_codes`.
- Every temporal record carries the phase interval, event start, availability
  source, semantics version and a complete per-frame availability sequence.
- `with_event_evidence()` injects the phase evidence temporal records instead of
  inheriting the base record.
- The real prediction path rejects non-empty phase evidence with empty or
  incomplete temporal metadata.
- Phase masks and source codes require per-frame availability; a single
  `available_at=0.0` placeholder is rejected.
- Each frame is checked against its own `available_at <= current_time`
  condition before model use.
- Future-only fields without `interval_end` remain HOLD.

## Required counterexamples

| ID | Test | Result |
|---|---|---|
| HT-01 | `test_holtl01_holdout_seal_hold_blocks_before_loader` | Rejected; loader calls `0` |
| HT-02 | `test_holtl02_empty_holdout_matches_fail_before_loader` | Rejected; loader calls `0` |
| HT-03 | `test_holtl03_wrong_match_and_split_mismatch_fail_before_loader` | Rejected; loader calls `0` |
| HT-04 | `test_holtl04_actual_artifact_change_is_compromised_before_loader` | Rejected; `COMPROMISED` persisted; loader calls `0` |
| HT-05 | `test_holtl05_unseal_and_result_are_persisted` | Events persisted in order: `SEALED_VERIFIED`, `UNSEALED`, `EVALUATION_STARTED`, `EVALUATION_COMPLETED` |
| TP-01 | `test_nonempty_phase_evidence_without_temporal_metadata_fails` | Rejected by the real prediction path |
| TP-02 | `test_global_zero_placeholder_for_phase_mask_is_rejected` | Rejected by per-frame availability requirement |
| TP-03 | `test_per_frame_availability_rejects_frame_before_event` | Rejected at frame `0` |
| TP-04 | `test_future_field_without_interval_end_is_hold` | HOLD |
| TP-05 | `test_model_input_hold_blocks_before_loader[phase_model_input-phase_model_input]` | Rejected; loader calls `0` |

Additional regression:

- `test_holdout_freeze_mismatch_fails_before_external_loader` proves a sealed
  identity mismatch fails before the external loader.
- `test_nonempty_phase_evidence_requires_temporal_metadata_for_each_field` proves
  partial temporal coverage cannot authorize phase-derived fields.

Synthetic ledger sample:

```text
HT-05 events=SEALED_VERIFIED, UNSEALED, EVALUATION_STARTED, EVALUATION_COMPLETED
HT-05 holdout_id=holdout-514a30d2d4a49b41
HT-05 manifest_sha256=ca55fb1ddb86bf8c98665f513deadaf1279739b1b5586c2d7d3afc7cc746e3c3
HT-05 prediction_sha256=59f1c53487f9a8db59fdf6e5c1e63154707b6b22da802280b9b3648e5f1a3a49
HT-05 previous_record_chain=verified
HT-04 events=COMPROMISED
HT-04 reason=holdout freeze hash or metric contract does not match
```

## Quality gates

```text
pytest -q -W error: 157 passed
invalid MTAH_EXTERNAL_DATA_DIR: 157 passed
Ruff check: PASS
Ruff format --check: PASS
Tracked external data files: 0
Real evaluation run: no
Training or tuning run: no
```

## Baseline integrity

```text
Stable tag: foundation-stable-dp005-v1.2.0-2026-11-06
Stable commit: c4b80a99695fa89f97d9a4a8296f249493bdd278
Research tag: foundation-research-dp006a-v1.1.0-2026-11-06
Research commit: cdfeaf3d1f06914a255c291859315f766eb8a945
Frozen data package expected SHA-256: 8b053decd116b0f7913c6bc234cc82c48eb03a4ac93241ed632f975c9fe896b4
```

The frozen-package value was checked against the reviewed task baseline
manifest. Package bytes were not read or recomputed because this task prohibits
real external-data access.

The five historical DP-006 files still match their recorded Git blob IDs and
are unchanged by this remediation.

## Review boundary

The engineer does not declare Policy implementation PASS and does not merge
PR #9. PM/QA owns final acceptance and any authorization to activate real data.
