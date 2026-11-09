# DP-006 Policy Remediation 006 C2 Lifecycle Closure Evidence

> Tuning-contamination notice: this file records the lifecycle candidate in
> which same-ledger execution and member lifecycle passed review but partial
> completion contamination remained open. Current evidence is in
> `DP-006_POLICY_REMEDIATION_006_TUNING_CONTAMINATION_EVIDENCE.md`.

**Task:** `DP-006-POLICY-REMEDIATION-006-C2-LIFECYCLE-CLOSURE`

**Review baseline:** `0aaac62b04b8ba0aae4c6dfda55451f971cdf4a7`

**Implementation commit:** `3d4683de74e12e50304455f108a70a9796a6e216`

**Branch:** `feature/DP-006-POLICY-v2`

**PR:** #9

**Requested gate:** Independent REPAIR-006 Re-review only

## Status

```text
C1 Migration atomicity: PASS, PRESERVED
C2 SourceIdentitySet data model: PASS, PRESERVED
C2 multi-match production integration: FIX CANDIDATE
C2 match-level lifecycle: FIX CANDIDATE
C3 Governance / Source separation: PASS, PRESERVED

CL-01 through CL-16: PASS
RC-01 through RC-17: PASS
R6-01 through R6-12: PASS
RP5-01 through RP5-09: PASS

Policy implementation final acceptance: HOLD
PR #9: OPEN, UNMERGED, HOLD
Final Assurance: NOT STARTED
REPAIR-007: NOT STARTED
```

This is engineer evidence only. It does not declare Policy implementation PASS,
authorize merge, start Final Assurance or authorize real-data research.

## V6 lifecycle

The ledger now writes `schema_version=6.0`,
`freeze_protocol_version=source-set-match-lifecycle-v6`, and a
collection-or-match `match_id` on every new record.

```text
SEALED_VERIFIED       collection-level
UNSEALED              collection-level
EVALUATION_STARTED    match-level
EVALUATION_FAILED     match-level
EVALUATION_COMPLETED  match-level
COMPROMISED           collection-level, permanent
```

Each registered match independently moves through:

```text
NOT_STARTED -> RUNNING -> COMPLETED
                    \-> FAILED -> RUNNING -> COMPLETED
```

The aggregate is `COMPLETED` only when every registered match is `COMPLETED`.

## Same-ledger production path

The synthetic Holdout contains both matches under one stable Holdout ID and one
`ledger_dir`.

```text
holdout_id=holdout-56b296a8bf3b3a886c8cf494
sealed_members=holdout-1,holdout-2
match_1_identity=af5745108bcd47a97e672f57bd9ac206bf1b0cf562ba9a1f5fb8d517be0b06eb
match_2_identity=65a349ab0c2c2fe82c5ed4c95d50a8666c867a93bca444d4aa1789e36f4240b5
positive_loader_calls=2
```

Event sequence:

```text
SEALED_VERIFIED       match_id=null
UNSEALED              match_id=null
EVALUATION_STARTED    match_id=holdout-1
EVALUATION_COMPLETED  match_id=holdout-1
EVALUATION_STARTED    match_id=holdout-2
EVALUATION_COMPLETED  match_id=holdout-2
```

Member and aggregate states:

```text
after holdout-1:
  holdout-1=COMPLETED
  holdout-2=NOT_STARTED
  aggregate=IN_PROGRESS

after holdout-2:
  holdout-1=COMPLETED
  holdout-2=COMPLETED
  aggregate=COMPLETED
```

The first match's single `source_identity` is no longer compared with the current
match. Runner selects the current match identity from the sealed
`SourceIdentitySet`. V4 remains fail-closed through the controlled re-seal
requirement; V5 ledgers are likewise rejected for a V6 controlled re-seal.

## Failure and retry isolation

```text
failed_match=holdout-1
failure_loader_calls=1
retry_loader_calls=1
other_match_loader_calls=1

SEALED_VERIFIED       match_id=null
UNSEALED              match_id=null
EVALUATION_STARTED    match_id=holdout-1
EVALUATION_FAILED     match_id=holdout-1
EVALUATION_STARTED    match_id=holdout-1
EVALUATION_COMPLETED  match_id=holdout-1
EVALUATION_STARTED    match_id=holdout-2
EVALUATION_COMPLETED  match_id=holdout-2

final_states:
  holdout-1=COMPLETED
  holdout-2=COMPLETED
```

Failure of one member does not prevent retry of that member or execution of
another uncompleted member.

## Identity failure

Changing the second match tracking SHA after the collection seal:

```text
rejection=sealed Source Identity set has changed
loader_calls=0
ledger_sha256_before=d0277e89b4872233e24dd0f22cc803d04332f630e8ac5e965e04e16943a3ae6b
ledger_sha256_after=d0277e89b4872233e24dd0f22cc803d04332f630e8ac5e965e04e16943a3ae6b
ledger_bytes_equal=True
```

Unknown matches, swapped identities, file/metadata changes and source-set
membership changes all fail before the external loader.

## CL test results

| Test | Result |
|---|---|
| CL-01 | Same ledger, sequential `holdout-1` then `holdout-2`: both completed |
| CL-02 | Second match runs after first completed |
| CL-03 | Completed match cannot run again; loader `0`; ledger unchanged |
| CL-04 | Failed match retries independently |
| CL-05 | First match failed; second match still runs |
| CL-06 | One completed member leaves aggregate `IN_PROGRESS` |
| CL-07 | Aggregate `COMPLETED` only after all members complete |
| CL-08 | Unknown third match rejected before loader |
| CL-09 | Swapped source identity mapping rejected before loader |
| CL-10 | File/metadata change rejected before loader |
| CL-11 | Source-set member change rejected before loader |
| CL-12 | Independent ledger dirs cannot produce a completed shared Holdout |
| CL-13 | Single-match Holdout remains compatible |
| CL-14 | `COMPROMISED` permanently rejects every match |
| CL-15 | Identity failure leaves ledger bytes unchanged |
| CL-16 | Running match blocks only that match; other match can execute |

## Quality gates

```text
pytest -q -W error: 239 passed
invalid MTAH_EXTERNAL_DATA_DIR: 239 passed
Ruff check: PASS
Ruff format --check: PASS
Task package validation: PASS
task_package_sha256=1A44380138BBF5CA466BEE2FE4F56FB3A37A866FFA685202632294082D2E460E
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

No DP-005, R5, frozen data package, stable tag or research tag is changed.
C1 atomicity and C3 source/governance separation remain covered by the existing
RC and R6 regressions.

## Remaining HOLD

- Independent REPAIR-006 Re-review.
- Final Assurance has not started.
- Real provider rights and internal authorization.
- Real temporal/phase verification and cross-provider mappings.
- Active independent Holdout and merge approval.

PR #9 must remain OPEN, UNMERGED and HOLD.
