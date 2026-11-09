# DP-006 Policy Remediation 003 Evidence

> Historical third-round evidence. R3 was subsequently refined by
> DP-006-POLICY-REMEDIATION-004 to separate model freeze from governance
> authorization identity. See `DP-006_POLICY_REMEDIATION_004_EVIDENCE.md`.

**Task:** DP-006-POLICY-REMEDIATION-003

**Base commit:** `9c883b031c0496ed9053f794494322dca8d10201`

**Branch:** `feature/DP-006-POLICY-v2`

**PR:** #9

**Result:** Holdout ledger state-machine fix candidate for PM/QA review

## Status

```text
R3 authorization denial semantics: FIX CANDIDATE
R3 event/state reduction: FIX CANDIDATE
R3 COMPROMISED terminal enforcement: FIX CANDIDATE
R3 stable holdout identity: FIX CANDIDATE
R3 tuning contamination entry: FIX CANDIDATE
R3 ledger fail-closed behavior: FIX CANDIDATE

Policy implementation final acceptance: HOLD
Real-data research: HOLD
Merge: DENIED
```

## Before remediation

Authorization HOLD probe:

```text
authorization_error=HOLDOUT_SEAL_VERIFIED=HOLD
events_after_hold=COMPROMISED
reason=HOLDOUT_SEAL_VERIFIED=HOLD
```

COMPROMISED reuse probe:

```text
ledger_before=COMPROMISED
run_after_compromised=ACCEPTED
events=COMPROMISED,SEALED_VERIFIED,UNSEALED,EVALUATION_STARTED,EVALUATION_COMPLETED
```

## After remediation

Authorization HOLD probe:

```text
authorization_error=HOLDOUT_SEAL_VERIFIED=HOLD
events_after_hold=AUTHORIZATION_DENIED
state=SEALED
loader_calls=0
```

COMPROMISED reuse probe:

```text
ledger_before=COMPROMISED
run_after_compromised=REJECTED
error=holdout ledger is permanently COMPROMISED
state=COMPROMISED
loader_calls=0
events=COMPROMISED
```

## State machine

Events are stored independently from lifecycle state. State is derived through
`reduce_holdout_state()` and never from the last event alone.

```text
Events:
AUTHORIZATION_DENIED
SEALED_VERIFIED
UNSEALED
EVALUATION_STARTED
EVALUATION_COMPLETED
EVALUATION_FAILED
COMPROMISED

States:
SEALED
UNSEALED
EVALUATION_RUNNING
EVALUATION_COMPLETED
EVALUATION_FAILED
COMPROMISED
```

- `AUTHORIZATION_DENIED` records the denial reason without changing state.
- `EVALUATION_FAILED` records a technical failure without automatic contamination.
- `EVALUATION_STARTED` may retry from `EVALUATION_FAILED` with the same frozen
  candidate.
- Any valid `COMPROMISED` event becomes permanent and rejects every later
  Promotion before `match_loader`.
- Invalid event order, missing initial events, broken hash chains, invalid JSON
  and mismatched stable identity fail closed.

## Stable Holdout identity

The ledger path no longer includes the holdout manifest SHA-256. It is derived
from:

```text
sha256(canonical JSON of provider + sorted unique match IDs)
```

Every record also stores the canonical provider, stable holdout ID and sorted
match set. The manifest SHA-256 remains an event field for provenance but cannot
be changed to create a new ledger identity for the same provider and match set.

## Tuning contamination entrance

Production API:

```text
mark_holdout_used_for_tuning(...)
```

Production CLI:

```text
scripts/mark_holdout_used_for_tuning.py
```

The entrance:

- locates a ledger through provider plus sorted match IDs;
- requires an existing `EVALUATION_COMPLETED` state;
- requires the supplied prediction SHA-256 to match the completed result;
- appends a permanent `COMPROMISED` event with reason, prediction hash and
  previous-record hash;
- does not access external match data;
- causes all later Promotion attempts to fail with loader calls `0`.

## Required acceptance cases

| Test | Result |
|---|---|
| SM-01 authorization HOLD | `AUTHORIZATION_DENIED`; state `SEALED`; no `COMPROMISED`; loader `0` |
| SM-02 existing COMPROMISED | Rejected before loader; no new event; loader `0` |
| SM-03 manifest SHA change | Same stable ledger; state remains `COMPROMISED`; loader `0` |
| SM-04 normal completion | `SEALED_VERIFIED`, `UNSEALED`, `EVALUATION_STARTED`, `EVALUATION_COMPLETED` |
| SM-05 execution failure | `EVALUATION_FAILED`; no contamination; retry with same freeze succeeds |
| SM-06 result used for tuning | Production CLI persists `COMPROMISED`; later Promotion loader `0` |
| SM-07 corrupt ledger | Fail closed before loader; corrupted bytes are not overwritten |
| SM-08 illegal event order | State reduction fails before loader |

## Quality gates

```text
pytest -q -W error: 165 passed
invalid MTAH_EXTERNAL_DATA_DIR: 165 passed
Ruff check: PASS
Ruff format --check: PASS
Review task package validation: PASS
External data accessed: NO
Real evaluation run: NO
Training or tuning run: NO
Tracked external-data files: 0
```

## Artifact identity after the state-machine change

```text
model=4e044dab55123fdecebaa644d7f7411e3e3f995aa70c4a725b9bdd35b95c11f1
feature_set=2d1ac11c13cacb303b139dda5d0d2cad82fefc0c35b33bb47a720ee28c07ec2e
configuration=e6c556db41f67ee43198da74fbbd67cbf059b236ef5384a7b6950f866a24fd25
hyperparameters=0712e6e94145ff7445d4c06f08769a24144f5d641287893ed8f59d612a9db3f5
evaluation_script=2f468d3bf1dc7ae18121be3ab122659c510a47c477ae4c8a0129255ecd196d1d
metric_contract_version=1.1.0:25ec4f45bd0e01cde9bd61fa4e7463b2adb42e5aef484e154f639aa768444a49
```

## Baseline integrity

```text
Stable tag: foundation-stable-dp005-v1.2.0-2026-11-06
Stable commit: c4b80a99695fa89f97d9a4a8296f249493bdd278
Research tag: foundation-research-dp006a-v1.1.0-2026-11-06
Research commit: cdfeaf3d1f06914a255c291859315f766eb8a945
Frozen data package expected SHA-256: 8b053decd116b0f7913c6bc234cc82c48eb03a4ac93241ed632f975c9fe896b4
```

The frozen-package value matches the reviewed baseline manifest. Package bytes
were not read or recomputed because the task prohibits real external-data access.

The five historical DP-006 documents remain byte-identical to their recorded
Git blob IDs. R5, DP-005, stable tags, frozen data and split/freeze
configuration were not changed.

## Review boundary

The engineer does not declare Policy implementation PASS and does not merge
PR #9. PM/QA owns final acceptance and any authorization to activate real data.
