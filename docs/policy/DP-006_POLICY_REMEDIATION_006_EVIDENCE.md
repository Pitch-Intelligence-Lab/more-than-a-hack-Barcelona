# DP-006 Policy Remediation 006 Closure Evidence

**Task:** DP-006-POLICY-REMEDIATION-006

**Base commit:** `d924f7fafd8b63f653dea6966ea127e61c87e460`

**Branch:** `feature/DP-006-POLICY-v2`

**PR:** #9

**Result:** bounded closure candidate ready for DP-006 Final Assurance Review

## Status

```text
R6.1 Source Identity: FIX CANDIDATE
R6.2 Source immutability: FIX CANDIDATE
R6.3 Source paths/files: FIX CANDIDATE
R6.4 Migration targets from Git objects: FIX CANDIDATE
R6.5 Migration ancestry: FIX CANDIDATE
R6.6 No worktree self-report: FIX CANDIDATE
R6.7 Existing repairs: PRESERVED
R6.8 Final Assurance readiness: READY FOR INDEPENDENT REVIEW

Policy implementation final acceptance: HOLD
Real-data research: HOLD
Merge: DENIED
Automatic REPAIR-007: NOT APPROVED
Next gate: DP-006 Final Assurance Review
```

## P0-A before remediation

The independent review changed the tracking pointer and SHA after the first
seal:

```text
tracking.path: tracking -> different-tracking-file.jsonl
tracking.sha256 changed
final event: EVALUATION_COMPLETED
loader_used_changed_source_config=true
```

The loader verified file checksums, but the Source Identity was not in the seal.

## P0-A after remediation

Source Identity is canonicalized and bound to every V4 lifecycle event. Measured
probe:

```text
source_identity_before=84660be35078ac41475f0eea11df69fd6aab164884f3d1eb44dfe0a0e4a4a542
source_identity_after=f7406e9b439fc705a5ce8907b5740d4f5b3f84adeaa010f3ffa8658a5845a184
source_config_sha256_before=9a4768cc3cf591be7596c0d8112372450422194e96bedf3cb3022bb1c0be37a2
source_config_sha256_after=38a440a3c1e91e0bc6bf036f4e9c1e155a4d2d0ec2ecd4c9a4a232e772b29b9d
outcome=REJECTED: sealed Source Identity has changed
loader_calls=0
ledger_sha256_before=05ecbebb4cdd13c500e1f796e6581b724e0084086d6be01c709b66dff68659a0
ledger_sha256_after=05ecbebb4cdd13c500e1f796e6581b724e0084086d6be01c709b66dff68659a0
```

Changes to tracking/phases/match path or SHA, source revision, match ID, FPS,
teams, pitch dimensions and coordinate convention all fail before the loader.
Governance permission changes do not enter Source Identity.

### Canonical production Source Identity

The complete example is in `docs/policy/SOURCE_IDENTITY_EXAMPLE.json`.

```text
provider=skillcorner
source_revision=4340d274572876239c154c90bc507a9b3250a656
match_id=2017461
fps=10
home_team_id=868
away_team_id=4177
pitch_length_m=105.0
pitch_width_m=68.0
coordinate_convention=metres-center-origin
source_config_sha256=4e9a396caaec128fcb586983bf97d8ba45f436119dc7fbd6b2bfe110dc11d929
source_identity_sha256=e7c435682d7920647017bf05d8c6804d2714032f9a452480cf73f6b30213a3e1
```

## P0-B before remediation

The independent review changed an uncommitted prediction artifact and committed
only a new receipt:

```text
artifact_differs_from_migration_commit=True
migration_accepted=MIGRATED_AUDIT_ONLY
```

The receipt was treated as target identity instead of a declaration requiring
Git-object verification.

## P0-B after remediation

Migration now extracts `git archive <migration_commit>` and recomputes model,
evaluation, split, Holdout Manifest, freeze spec, policy, source config/source
identity and migration-tool identities from Git objects. It also compares the
current worktree targets with the commit.

Ancestry checks require:

```text
migration_commit is an ancestor of approval_commit
old_code_commit is an ancestor of migration_commit
```

Verified synthetic migration:

```text
migration_commit=b5deefa5328575083e1494c1f0b7d695ab7a8727
approval_commit=ea9703c3e68c068d5a1326f53e7ab92f926cac24
state=MIGRATED_AUDIT_ONLY
target_model=8aaa9865f062d3929ec32194e917b2de296bbcd2cf6c4f1326ec3b4f143241ea
target_evaluation=bf040bd24ecaa23cf65e8392d03497890f7635d4340b21e0cf0add4fa283fe42
target_split_sha256=3e5156f813fddba6df99ed0134cddab6012cf4f5ccfc20a62484a584f2b5ce7a
target_holdout_sha256=ca55fb1ddb86bf8c98665f513deadaf1279739b1b5586c2d7d3afc7cc746e3c3
source_config_sha256=9a4768cc3cf591be7596c0d8112372450422194e96bedf3cb3022bb1c0be37a2
source_identity_sha256=84660be35078ac41475f0eea11df69fd6aab164884f3d1eb44dfe0a0e4a4a542
migration_tool_sha256=a3dfa4b91f7dede780987fd254b621793febb3e4866ed2e45774940076fb1323
promotion_authorized=False
```

## R6 test results

| Test | Result |
|---|---|
| R6-01 | Tracking path mutation rejected; loader `0`; ledger unchanged |
| R6-02 | Tracking SHA mutation rejected; loader `0`; ledger unchanged |
| R6-03 | Phases/match path or SHA mutation rejected; loader `0` |
| R6-04 | Source revision, match ID or FPS mutation rejected; loader `0` |
| R6-05 | Team, pitch or coordinate mutation rejected; loader `0` |
| R6-06 | Same Source Identity retry after `EVALUATION_FAILED` succeeds; no `COMPROMISED` |
| R6-07 | Uncommitted model plus new receipt rejected; ledger unchanged |
| R6-08 | Migration commit artifact vs receipt mismatch rejected |
| R6-09 | Missing target artifact in migration commit rejected |
| R6-10 | Approval commit not descending from migration commit rejected |
| R6-11 | Old code commit without ancestry relationship rejected |
| R6-12 | Normal migration is `MIGRATED_AUDIT_ONLY`; Promotion loader `0` |

RP5-01 through RP5-09 and the prior 187 tests remain passing.

## Quality gates

```text
pytest -q -W error: 206 passed
invalid MTAH_EXTERNAL_DATA_DIR: 206 passed
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
Task ZIP SHA-256: 332A94B1EF509DDF5AA7BA49CB7C7B69D41E51829CDE04CE27365E98B901B2E1
Stable tag: foundation-stable-dp005-v1.2.0-2026-11-06
Stable commit: c4b80a99695fa89f97d9a4a8296f249493bdd278
Research tag: foundation-research-dp006a-v1.1.0-2026-11-06
Research commit: cdfeaf3d1f06914a255c291859315f766eb8a945
Frozen data package expected SHA-256: 8b053decd116b0f7913c6bc234cc82c48eb03a4ac93241ed632f975c9fe896b4
```

Five historical DP-006 files remain byte-identical to their recorded blobs. R5
temporal, DP-005, stable/research tags and frozen data remain unchanged.

## Review boundary

This is an engineer candidate only. It is ready for independent DP-006 Final
Assurance Review and does not claim Policy implementation PASS. PR #9 remains
OPEN, UNMERGED and HOLD.
