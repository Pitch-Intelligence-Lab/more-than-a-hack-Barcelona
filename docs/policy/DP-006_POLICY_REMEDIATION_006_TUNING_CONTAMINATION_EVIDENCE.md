# DP-006 Policy Remediation 006 Tuning Contamination Evidence

**Task:** `DP-006-POLICY-REMEDIATION-006-TUNING-CONTAMINATION-CLOSURE`

**Review baseline:** `9f0558b1eac4472b30963427781b68d8e79598ef`

**Implementation commit:** `b8a93cc955ec80c549489c00f2ad1737663abba0`

**Branch:** `feature/DP-006-POLICY-v2`

**PR:** #9

**Requested gate:** Independent REPAIR-006 Re-review only

## Status

```text
C2 partial-completion contamination: FIX CANDIDATE
C2 global COMPROMISED: FIX CANDIDATE
C2 concurrency linearization: FIX CANDIDATE
C1 Migration atomicity: PASS, PRESERVED
C3 Governance / Source separation: PASS, PRESERVED

TC-01 through TC-12: PASS
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

## Atomic contamination transaction

`mark_holdout_used_for_tuning()` now opens the same per-ledger lock used by all
other lifecycle appends. Inside that lock it:

1. rereads and validates the complete ledger;
2. rejects an existing `COMPROMISED` or migrated terminal state;
3. requires `prediction_sha256` to match a completed member record in the
   current Holdout;
4. builds a collection-level `COMPROMISED` record with `match_id=null`;
5. validates the complete candidate ledger;
6. atomically replaces the ledger file.

The aggregate is not required to be `COMPLETED`. A matching completed member is
sufficient even when another member is `NOT_STARTED`, `RUNNING` or `FAILED`.

## Partial completion evidence

```text
match_1_state_before=COMPLETED
match_2_state_before=NOT_STARTED
aggregate_before=IN_PROGRESS
prediction_sha256=59f1c53487f9a8db59fdf6e5c1e63154707b6b22da802280b9b3648e5f1a3a49
tuning_mark_outcome=ACCEPTED
aggregate_after=COMPROMISED

events_after_mark:
  SEALED_VERIFIED       null
  UNSEALED              null
  EVALUATION_STARTED    holdout-1
  EVALUATION_COMPLETED  holdout-1
  COMPROMISED           null

ledger_sha256_before=b3b283acb1bd6e3d4bc87af83ef9b2813460f843023b4f2e5d0079881b12cbfa
ledger_sha256_after_mark=07b51a920dcbb8c458022f1f9b69e80d9187ae51e18c0cb2c5861396ec908a2a
next_match_rejection=holdout ledger is permanently COMPROMISED
loader_calls_after_mark=0
ledger_unchanged_after_rejection=True
```

## Concurrency linearization

### COMPROMISED first

```text
rejection=holdout ledger has events after COMPROMISED
loader_calls=0
events:
  SEALED_VERIFIED       null
  UNSEALED              null
  EVALUATION_STARTED    holdout-1
  EVALUATION_COMPLETED  holdout-1
  COMPROMISED           null
```

No `EVALUATION_STARTED` for `holdout-2` is accepted after contamination.

### STARTED first

```text
rejection=holdout ledger has events after COMPROMISED
loader_calls=1
events:
  SEALED_VERIFIED       null
  UNSEALED              null
  EVALUATION_STARTED    holdout-1
  EVALUATION_COMPLETED  holdout-1
  EVALUATION_STARTED    holdout-2
  COMPROMISED           null
final_state=COMPROMISED
```

The second loader was permitted only because its START had already linearized
before contamination. Its result was not written as `EVALUATION_COMPLETED`.

## Negative behavior

- no matching completed member: rejected with ledger bytes unchanged;
- unknown prediction SHA: rejected with ledger bytes unchanged;
- prediction from another Holdout: rejected;
- modified/re-sealed Manifest cannot clear existing `COMPROMISED`;
- repeated contamination request: rejected with no duplicate terminal event;
- candidate validation failure: no write;
- single-match tuning contamination remains compatible;
- all terminal, failed, running and not-started members are rejected after the
  collection becomes `COMPROMISED`.

## TC test results

| Test | Result |
|---|---|
| TC-01 | Partial completion member result compromises whole Holdout |
| TC-02 | Other unstarted match rejected after contamination; loader `0` |
| TC-03 | Completed match rerun rejected after contamination; loader `0` |
| TC-04 | Completed plus failed member can be contaminated |
| TC-05 | No completed member rejected; ledger unchanged |
| TC-06 | Unknown prediction SHA rejected; ledger unchanged |
| TC-07 | Prediction from another Holdout rejected |
| TC-08 | Manifest change cannot clear permanent compromise |
| TC-09 | Both concurrency linearization orders are safe |
| TC-10 | Single-match behavior remains compatible |
| TC-11 | Repeated contamination rejected; ledger unchanged |
| TC-12 | Candidate validation failure leaves ledger unchanged |

## Quality gates

```text
pytest -q -W error: 251 passed
invalid MTAH_EXTERNAL_DATA_DIR: 251 passed
Ruff check: PASS
Ruff format --check: PASS
Task package validation: PASS
task_package_sha256=667E8A9D0302A1034485F7E7E34DAB6B13ECFCFEDE974A9162AFBE48188C6EB2
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

## Remaining HOLD

- Independent REPAIR-006 Re-review.
- Final Assurance has not started.
- Real provider rights and internal authorization.
- Real temporal/phase verification and cross-provider mappings.
- Active independent Holdout and merge approval.

PR #9 must remain OPEN, UNMERGED and HOLD.
