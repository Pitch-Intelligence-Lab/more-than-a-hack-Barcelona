# DP-006 Policy v2.1 P1 Closure 004 Evidence

```text
Task: DP-006-POLICY-V2.1-P1-CLOSURE-004
Baseline: e2b892c2861c008dfe3cad2909f9288f091abb1d
Implementation commit: fb7cca7fc852025b3b6231509b9623e224d7b0ad
Branch: feature/DP-006-POLICY-v2.1-proportional-access
P1 Closure 004 result: FIX CANDIDATE
Policy v2.1 final acceptance: AWAITING INDEPENDENT REVIEW
Real-data research: HOLD
REPAIR-007: NOT AUTHORIZED
```

This closure fixes only the remaining HOLD-use evidence rule and Exposure
Identity binding to the Holdout Ledger lifecycle. It does not reopen Promotion,
Structural Audit, PredictionSource or observed-use.

## HOLD use evidence rule

The normative rule is recorded in
`docs/policy/v2.1/HOLD_USE_EVIDENCE_POLICY.md`.

Before:

```text
HOLD use + evidence_ids=[]
+ valid scope
=> ALLOWED with SCOPED_INTERNAL_RISK

HOLD use + evidence_ids=["EV-NOT-REGISTERED"]
+ valid scope
=> ALLOWED with SCOPED_INTERNAL_RISK
```

After:

```text
HOLD use + evidence_ids=[]
+ valid scope
=> ALLOWED with SCOPED_INTERNAL_RISK

HOLD use + unregistered evidence
=> DENY at policy load

PASS use + empty evidence
=> DENY at policy load

PASS use + unregistered evidence
=> DENY at policy load

FAIL use
=> DENY
```

## Ledger V7 Exposure Identity

New production Holdout ledgers use:

```text
schema_version: 7.0
freeze_protocol_version: exposure-bound-match-lifecycle-v7
```

Every V7 record contains:

```text
exposure_register_path_identity
exposure_register_sha256
exposure_anchor_path_identity
exposure_anchor_sha256
exposure_trust_root_sha256
exposure_reseal_id
```

The Exposure Identity is immutable from the first V7 record. It is compared
again when an existing Ledger is opened. The append-only hash chain and Holdout
member lifecycle remain unchanged.

Lifecycle behavior:

```text
first seal                 -> records complete Exposure Identity
same identity retry        -> existing failed/same-source retry semantics preserved
reseal changed identity    -> old Ledger retry denied before loader
failed/in-progress reuse   -> denied when Exposure Identity differs
completed Ledger           -> permanently non-reusable
new seal/new Ledger        -> allowed with new identity
legacy V6 without identity -> fail closed before authorization/loader
```

Old V6 bytes are retained. There is no inferred identity, no silent migration,
no reset and no overwrite. Operators must use a new sealed Holdout Ledger.

## PB-35 through PB-41

```text
PB-35 PASS: HOLD use + empty evidence + valid scope -> scoped allow
PB-36 PASS: HOLD use + unregistered evidence -> deny
PB-37 PASS: failed Ledger after register reseal -> old Ledger denied, loader=0
PB-38 PASS: failed Ledger after anchor/root change -> old Ledger denied, loader=0
PB-39 PASS: completed Ledger reuse -> denied, loader=0, bytes unchanged
PB-40 PASS: legal new seal/new Ledger -> completed with V7 identity
PB-41 PASS: V6 Ledger without Exposure Identity -> fail closed, loader=0
```

## Regression and safety

```text
PB-01 through PB-34: PASS
Closure 004 tests: 7 passed
Full suite: 335 passed
Strict suite: 335 passed with -W error
Invalid external root: 335 passed
Ruff check: PASS
Ruff format --check: PASS
git diff --check: PASS
```

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
Real external data accessed: no
Training/tuning run: no
Real evaluation run: no
Active Holdout enabled: no
REPAIR-007 started: no
```

## Review boundary

This is a Closure 004 fix candidate for independent re-review. It is not a
Policy v2.1 PASS claim and does not authorize PR merge or real-data research.
