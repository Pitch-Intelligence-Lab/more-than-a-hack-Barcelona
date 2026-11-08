# DP-006 Policy Remediation 006 Closure Correction Evidence

> C2 lifecycle notice: this file records the correction candidate in which
> SourceIdentitySet data modeling passed but one-ledger multi-match production
> lifecycle remained incomplete. Current C2 production evidence is in
> `DP-006_POLICY_REMEDIATION_006_C2_LIFECYCLE_EVIDENCE.md`.

**Task:** `DP-006-POLICY-REMEDIATION-006-CLOSURE-CORRECTION`

**Review baseline:** `9fffc4f4363e478ac8edba1edbb2e25867894ec3`

**Implementation commit:** `7942bf7a5bd13dace4bbddb01bb5118d3b8e2223`

**Branch:** `feature/DP-006-POLICY-v2`

**PR:** #9

**Requested gate:** Independent REPAIR-006 Re-review only

## Status

```text
C1 Migration atomicity: FIX CANDIDATE
C2 Multi-match SourceIdentitySet: FIX CANDIDATE
C3 Governance / Source separation: FIX CANDIDATE

RC-01 through RC-17: PASS
R6-01 through R6-12: PASS
RP5-01 through RP5-09: PASS

Policy implementation final acceptance: HOLD
PR #9: OPEN, UNMERGED, HOLD
Final Assurance: NOT STARTED
REPAIR-007: NOT STARTED
```

This document is engineer evidence only. It does not declare Policy
implementation PASS and does not authorize merge, Final Assurance or real-data
research.

## C1: Migration atomicity

The migration path now derives the old Holdout Manifest SHA-256 from the first
legacy `SEALED_VERIFIED` record. The CLI no longer accepts a caller-supplied old
Manifest hash.

Before writing, migration now:

1. acquires the per-ledger cross-process lock;
2. rereads and validates the existing ledger;
3. rejects a changed or stale ledger head;
4. constructs the complete candidate record;
5. validates record schema, hash chain, protocol order, lifecycle state,
   Manifest/path/split/source seal invariants and migration-receipt binding;
6. writes a complete candidate file to a temporary file;
7. fsyncs and atomically replaces the ledger.

Wrong old Manifest probe through the production CLI:

```text
cli_returncode=1
failure_class=old_holdout_manifest_sha256
ledger_sha256_before=dab1fb4fa21c9f444e20f97935b929ec908726f138a5006212357c1aab75b58c
ledger_sha256_after=dab1fb4fa21c9f444e20f97935b929ec908726f138a5006212357c1aab75b58c
ledger_bytes_equal=True
```

The RC-05 stale-head test injects a valid concurrent `AUTHORIZATION_DENIED`
record after migration has sampled the old head. Migration rejects the stale
head and preserves the concurrent record. RC-06 injects an atomic-replace
failure and confirms that no partial JSONL record remains.

## C2: SourceIdentitySet

The first V5 seal binds:

- the canonical source-set descriptor digest;
- all sorted member `match_id` values;
- each member's repository-relative source config;
- the sorted `match_id -> source_identity_sha256` map.

Runtime reconstructs the complete current set before the external loader, then
selects the current match from the sealed map. Unknown matches, additions,
removals, swapped mappings, duplicate IDs and post-seal descriptor expansion
fail closed.

Synthetic two-match probe:

```text
holdout_matches=holdout-1,holdout-2
source_set_sha256=a7997466ab00990a367977eda588a0be5b3edaf51241393c2611fc0f19a54405
first_match_identity=af5745108bcd47a97e672f57bd9ac206bf1b0cf562ba9a1f5fb8d517be0b06eb
second_match_identity=65a349ab0c2c2fe82c5ed4c95d50a8666c867a93bca444d4aa1789e36f4240b5
first_match_outcome=PASS
second_match_outcome=PASS
unknown_match_outcome=REJECTED; loader=0
mapping_tamper_outcome=REJECTED
```

The production SkillCorner single-match compatibility example remains:

```text
source_identity_sha256=12254db9c834c7b85a55056611474a63ffd93173184d3e375e0f87684d73a5c2
source_config_sha256=ce49db2aca9e066b80a4245cbfff82964e60d04f6b51b9387fb61cb5a6e09cf2
source_set_sha256=e6b8765badc136c99f91e64693273e54a1a4b8020321a3552c9c5e44161af37f
```

Examples are recorded in:

- `docs/policy/SOURCE_IDENTITY_EXAMPLE.json`
- `docs/policy/SOURCE_IDENTITY_SET_EXAMPLE.json`
- `docs/policy/SOURCE_SET_DESCRIPTOR_EXAMPLE.json`

## C3: Governance / Source separation

`SourceIdentity.source_config_sha256` is now the digest of a source-only
canonical projection. It includes provider, source revision, match metadata,
file paths and file hashes, license/readme content hashes, FPS, teams, pitch and
coordinate convention. It excludes `data_license_status`,
`data_license_evidence`, repository software-license declarations, approval
evidence and internal authorization.

External governance-field probe:

```text
source_identity_before_permission_update=af5745108bcd47a97e672f57bd9ac206bf1b0cf562ba9a1f5fb8d517be0b06eb
source_identity_after_license_update=af5745108bcd47a97e672f57bd9ac206bf1b0cf562ba9a1f5fb8d517be0b06eb
source_identity_unchanged=True
```

Policy authorization probe:

```text
governance_identity_before_policy_change=6c9ec6f799e5ecf60836ab5ee32b9f1a12f222c10b34f914749f629c1ee57835
governance_identity_hold=b63ddf92a462c621221a66d52f7ed96188138b59c8a0dee1cedc4cf2774ccaba
governance_identity_pass=6c9ec6f799e5ecf60836ab5ee32b9f1a12f222c10b34f914749f629c1ee57835
governance_reauthorization_identity_changed=True
```

The RC-16 production-path test first records `AUTHORIZATION_DENIED` under
HOLD, then restores PASS and confirms that authorization executes again before
the loader and evaluation can continue.

Actual source mutation probe:

```text
source_identity_before_file_change=af5745108bcd47a97e672f57bd9ac206bf1b0cf562ba9a1f5fb8d517be0b06eb
source_identity_after_file_change=48edc206c7c3647be7192799edfdb931bef7d93fda3d7934fac66ee3109a66b9
source_identity_changed=True
rejection=sealed Source Identity has changed
loader_calls=0
ledger_sha256_before=09037ce47641c589b00d30ed09e08f73cf9b3efd9b4086cf17a726ade6a3ea5b
ledger_sha256_after=09037ce47641c589b00d30ed09e08f73cf9b3efd9b4086cf17a726ade6a3ea5b
ledger_bytes_equal=True
```

## Required tests

| Test | Result |
|---|---|
| RC-01 | Wrong old Manifest SHA rejected by CLI; ledger bytes unchanged |
| RC-02 | Wrong candidate protocol order rejected; ledger bytes unchanged |
| RC-03 | Illegal state transition rejected; ledger bytes unchanged |
| RC-04 | Seal-invariant failure rejected; ledger bytes unchanged |
| RC-05 | Stale head rejected; concurrent valid update preserved |
| RC-06 | Simulated write failure leaves no partial record |
| RC-07 | Two-match SourceIdentitySet validates both per-match identities |
| RC-08 | Unknown third match rejected before loader |
| RC-09 | Source-set member addition/removal rejected |
| RC-10 | Swapped match/identity mapping rejected |
| RC-11 | Duplicate match ID rejected |
| RC-12 | Post-seal member addition rejected; ledger bytes unchanged |
| RC-13 | Single-match Holdout remains compatible |
| RC-14 | `data_license_status` change does not alter Source Identity |
| RC-15 | `data_license_evidence` change does not alter Source Identity |
| RC-16 | Governance authorization reruns after HOLD to PASS |
| RC-17 | Source file/path/metadata change alters identity and blocks loader |

Historical regressions:

```text
R6-01 through R6-12: PASS
RP5-01 through RP5-09: PASS
Prior 206 tests: preserved
```

## Quality gates

```text
pytest -q -W error: 223 passed in 51.21s
invalid MTAH_EXTERNAL_DATA_DIR: 223 passed in 50.50s
Ruff check: PASS
Ruff format --check: PASS
Task package validation: PASS
task_package_sha256=9B6D66E379E7A057008029322CF368C213745BDD35E189D4A2CFA1CB3ED42158
External data accessed: NO
Real evaluation run: NO
Training or tuning run: NO
Tracked external-data files: 0
```

## Baseline and history

```text
Stable tag: foundation-stable-dp005-v1.2.0-2026-11-06
Stable commit: c4b80a99695fa89f97d9a4a8296f249493bdd278
Research tag: foundation-research-dp006a-v1.1.0-2026-11-06
Research commit: cdfeaf3d1f06914a255c291859315f766eb8a945
Frozen data package expected SHA-256: 8b053decd116b0f7913c6bc234cc82c48eb03a4ac93241ed632f975c9fe896b4
```

No DP-005, stable/research tag, frozen data package or R5 file is changed by this
correction.

## Remaining HOLD

- Independent REPAIR-006 Re-review.
- DP-006 Final Assurance has not been started.
- Real provider rights and internal authorization.
- Real temporal/phase verification and cross-provider mappings.
- Active independent Holdout and merge approval.

PR #9 must remain OPEN, UNMERGED and HOLD. Final acceptance belongs to PM/QA.
