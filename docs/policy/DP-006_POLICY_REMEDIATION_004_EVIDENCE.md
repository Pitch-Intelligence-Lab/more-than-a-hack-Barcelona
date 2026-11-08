# DP-006 Policy Remediation 004 Evidence

**Task:** DP-006-POLICY-REMEDIATION-004

**Base commit:** `d83cb9e0096a852e9245b8734111746403b0d337`

**Branch:** `feature/DP-006-POLICY-v2`

**PR:** #9

**Result:** model/governance identity separation and legacy migration candidate
for PM/QA review

## Status

```text
R3 model freeze category purity: FIX CANDIDATE
R3 governance authorization identity: FIX CANDIDATE
R3 legacy freeze migration: FIX CANDIDATE
R3 Event/State, stable identity and tuning contamination: PRESERVED

Policy implementation final acceptance: HOLD
Real-data research: HOLD
Merge: DENIED
```

## Before remediation

The reviewed task-package probe changed only `HOLDOUT_SEAL_VERIFIED` in a legacy
combined freeze specification:

```text
outcome=REJECTED: holdout freeze hash or metric contract does not match
events=COMPROMISED
```

This demonstrated that governance authorization state was incorrectly part of
the model identity.

## Model freeze categories

The production freeze specification now uses schema `2.0` and explicitly
separates:

| Category | Included | Purpose |
|---|---|---|
| `prediction_code` | yes | State inference and submission pipeline |
| `feature_set` | yes | Ball, evidence and possession features |
| `data_transform` | yes | Data loading and model-input conversion |
| `algorithm_configuration` | yes | State-engine behavior |
| `hyperparameters` | yes | Frozen numeric parameters |
| `evaluation_script` | yes | External evaluation implementation |
| `metric_contract` | yes | Metric semantics and implementation |
| `configs/policy/*` | no | Governance authorization state |
| `src/mtah_possession/governance/*` | no | Ledger, policy, authorization and artifact governance |
| holdout manifest and ledger output | no | Holdout lifecycle and audit records |

Every category stores a reason in
`configs/policy/artifact-freeze-v2.json`. Schema-2 computation also rejects any
expanded governance-only path inside a model-freeze category.

Current production model freeze:

```text
model=752a8a9a092222961824c309facc41e6c07f97377f71e797b1bc77d15a0a8440
feature_set=2d1ac11c13cacb303b139dda5d0d2cad82fefc0c35b33bb47a720ee28c07ec2e
configuration=94c06802da803878ee7a2248af3f213e7f2cb1cfd7c852ca055efc10af6eacac
hyperparameters=0712e6e94145ff7445d4c06f08769a24144f5d641287893ed8f59d612a9db3f5
evaluation_script=6e0381bff7f6a89c72ac8df24655814881d09e93d17098eb30d0f8b8cfcfae1c
metric_contract_version=1.1.0:25ec4f45bd0e01cde9bd61fa4e7463b2adb42e5aef484e154f639aa768444a49
```

## Governance authorization identity

`GovernanceAuthorizationIdentity` contains:

```text
provider
source_revision
policy_version
policy_sha256
license_status
internal_research_authorization
evaluation_authorization
temporal_authorization
phase_authorization
holdout_seal_authorization
authorization_status_digest
evidence_ids
```

New ledger events record this identity. It is not included in the model freeze
comparison. A permission change therefore produces `AUTHORIZATION_DENIED`
without changing lifecycle state or creating `COMPROMISED`.

Permission-switch evidence with the separated freeze specification:

```text
freeze_before.model=8aaa9865f062d3929ec32194e917b2de296bbcd2cf6c4f1326ec3b4f143241ea
freeze_after.model=8aaa9865f062d3929ec32194e917b2de296bbcd2cf6c4f1326ec3b4f143241ea
model_freeze_unchanged=True

governance_digest_before=6c9ec6f799e5ecf60836ab5ee32b9f1a12f222c10b34f914749f629c1ee57835
governance_digest_after=b63ddf92a462c621221a66d52f7ed96188138b59c8a0dee1cedc4cf2774ccaba
holdout_status_before=PASS
holdout_status_after=HOLD
```

## Legacy ledger migration

Legacy records are preserved unchanged. The old combined identity is not
silently interpreted as a new model-only hash. Migration appends one
`FREEZE_PROTOCOL_MIGRATED` event to the original chain and original Holdout ID:

```text
ledger_path_unchanged=True
holdout_id_unchanged=True
events_before=SEALED_VERIFIED
events_after=SEALED_VERIFIED,FREEZE_PROTOCOL_MIGRATED
old_event_preserved=True
old_protocol_version=combined-policy-model-v1
new_protocol_version=model-governance-separated-v2
old_code_commit=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
migration_commit=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
legacy_combined_model=2247f4a988ede9aca6f1308a0090f22e4b3eff981cdf8454647c6ba1a17af9ea
new_model=8aaa9865f062d3929ec32194e917b2de296bbcd2cf6c4f1326ec3b4f143241ea
governance_identity_digest=6c9ec6f799e5ecf60836ab5ee32b9f1a12f222c10b34f914749f629c1ee57835
approver=qa-lead
```

Production migration entry:

```text
scripts/migrate_holdout_ledger.py
```

The entry computes current model artifacts, constructs the governance identity,
requires approver/reason/migration commit, preserves the original ledger and
appends the migration event. An old `COMPROMISED` ledger cannot be migrated to a
clean state. Missing or tampered migration evidence fails closed before the
external loader.

## Required acceptance cases

| Test | Result |
|---|---|
| FR-01 Holdout permission PASS→HOLD | Model freeze unchanged; governance digest changed; `AUTHORIZATION_DENIED`; lifecycle unchanged; no `COMPROMISED`; loader `0` |
| FR-02 Evaluation permission PASS→HOLD | Same separated identity behavior |
| FR-03 Permission restoration | Same stable ledger reused; prior denial retained; evaluation completes |
| FR-04 Predictive artifact change | Model freeze changed; `COMPROMISED`; loader `0` |
| FR-05 Governance-only code change | Model freeze unchanged; no `COMPROMISED` |
| MG-01 Clean legacy ledger | Original path/ID/events retained; migration appended; subsequent evaluation succeeds |
| MG-02 Compromised legacy ledger | Migration rejected; original bytes retained; Promotion loader `0` |
| MG-03 Missing/tampered migration | Fail closed before loader |

## Quality gates

```text
pytest -q -W error: 174 passed
invalid MTAH_EXTERNAL_DATA_DIR: 174 passed
Ruff check: PASS
Ruff format --check: PASS
Review task package validation: PASS
External data accessed: NO
Real evaluation run: NO
Training or tuning run: NO
Tracked external-data files: 0
```

## Baseline integrity

```text
Task ZIP SHA-256: 9641A24083C7D1BE11CC873484ED9304A58C120CB008AEE87DFE04E406471FA9
Stable tag: foundation-stable-dp005-v1.2.0-2026-11-06
Stable commit: c4b80a99695fa89f97d9a4a8296f249493bdd278
Research tag: foundation-research-dp006a-v1.1.0-2026-11-06
Research commit: cdfeaf3d1f06914a255c291859315f766eb8a945
Frozen data package expected SHA-256: 8b053decd116b0f7913c6bc234cc82c48eb03a4ac93241ed632f975c9fe896b4
```

The frozen-package value matches the reviewed task baseline manifest. Package
bytes were not read or recomputed because real external-data access is
prohibited. R5, DP-005, split/freeze data, stable tags and historical DP-006
documents remain outside this remediation.

## Review boundary

The engineer does not declare Policy implementation PASS and does not merge
PR #9. PM/QA owns final acceptance, merge approval and real-data authorization.
