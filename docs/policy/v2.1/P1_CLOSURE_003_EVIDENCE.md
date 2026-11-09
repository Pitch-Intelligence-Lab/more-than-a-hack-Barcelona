# DP-006 Policy v2.1 P1 Closure 003 Evidence

```text
Task: DP-006-POLICY-V2.1-P1-CLOSURE-003
Baseline: 3410dd6cf33286d135460fd2978325f2dcec34e4
Implementation commit: 5bbe856e52fdcefd646f5f21069148d1e866f0b4
Branch: feature/DP-006-POLICY-v2.1-proportional-access
P1 Closure 003 result: FIX CANDIDATE
Policy v2.1 final acceptance: AWAITING INDEPENDENT REVIEW
Real-data research: HOLD
REPAIR-007: NOT AUTHORIZED
```

This closure fixes only the two remaining P1 authorization-integrity gaps. It
does not reopen Promotion, Structural Audit, PredictionSource or observed-use,
and does not modify Source Identity, Holdout lifecycle, DP-005 or frozen data.

## Scoped-risk failure classification

Authorization failures are now classified:

```text
EXTERNAL_LICENSE_HOLD
INTERNAL_RESEARCH_HOLD
USE_PERMISSION_HOLD
MISSING_EVIDENCE
UNREGISTERED_EVIDENCE
PERMISSION_FAIL
POLICY_INTEGRITY_ERROR
SOURCE_IDENTITY_ERROR
```

Only the first three may enter the scoped internal-risk fallback. The policy
loader additionally enforces:

```text
permission.status=PASS
=> evidence_ids non-empty
=> every evidence ID belongs to provider source_evidence
```

Before:

```text
PASS use + evidence_ids=[]
+ valid scoped risk
=> ALLOWED with SCOPED_INTERNAL_RISK

PASS use + unregistered evidence
+ valid scoped risk
=> ALLOWED with SCOPED_INTERNAL_RISK
```

After:

```text
PASS use + evidence_ids=[]
=> PolicyError at policy load

PASS use + unregistered evidence
=> PolicyError at policy load

permission FAIL + valid scope
=> DENY

malformed policy + valid scope
=> DENY

valid LICENSE/INTERNAL/use HOLD + valid scope
=> ALLOWED with SCOPED_INTERNAL_RISK
```

## Exposure trust chain

Exposure authorization now verifies three independent layers:

```text
register
  -> exact bytes, path identity and logical path
anchor
  -> exact bytes and anchor path identity
trust root
  -> exact SHA-256 pinned in production code
```

The production trust root is not a CLI input. Both
`scripts/evaluate_external.py` and `scripts/audit_external.py` no longer expose
an alternate `--exposure-register` option.

Default committed identities:

```text
register: configs/policy/exposure-register-v1.json
register path identity: f67b8f9365e0147c8e66b233b18e5b2ade92f914460ba15cae80784059ae0a84
register SHA-256: 5c1579495502bad3d3a75af6addd54148d272beaa15f42a84eb43506da5d7376

anchor: configs/policy/exposure-register-anchor-v1.json
anchor path identity: cba9023cd1702b046b7e00aece7b0ea153faa3ff7e0f466cd93ea1cc12a900fe
anchor SHA-256: 1f1c927e7e2892c9e8ecde978251134da453fee2e03e3f66db2cdc30f3ef7be8

trust root: configs/policy/exposure-register-trust-root-v1.json
trusted trust-root SHA-256: 584fa741fc0b0b624b96d8758d13b5437b76cadc6608e9ae376be3ab572c0159
```

The Holdout authorization snapshot also binds provider and exact sorted match
set. Changing only the register, changing only the anchor, changing both while
retaining the old trust root, or switching to another register path all fail
closed.

## Monotonic reseal evidence

A synthetic monotonic reseal probe produced:

```text
register before: 787e5a44fd2923def61ecad6fc9aad861880ca0a9435be3bc7daf09bb58a4b62
register after:  cc3272e6e0d647babb14604719c6b1c6859177b054496cf80eeccd605f129603
anchor before:   35368a8d845de8dc61524bef14c76ccf3adb0ec73b18a956fcc3c1dedd692543
anchor after:    6fde3fae47aed5c8d437cef72e6b4d95427b2f592539e34bc0ae53a77059c7d5
root before:     e9a3b67b30ee4443031423d75b3f298da546819f24fd77ebe5ff0bcaaac54636
root after:      af4bfb1ec20061f9f4eaf109ff128cabdb672c6f3b58c6c1d0cd89f72f01ba81
highest before:  {"101":"ID_ONLY"}
highest after:   {"101":"METADATA_SEEN"}
audit complete:  true
```

The reseal audit record contains old/new register hashes, old/new anchor hashes,
`reseal_id`, approver, timestamp, reason, approval evidence and before/after
high-water maps. A lowering reseal is rejected without changing anchor or trust
root bytes.

## PB-24 through PB-34

```text
PB-24 PASS: empty evidence + valid scope denied
PB-25 PASS: unregistered evidence + valid scope denied
PB-26 PASS: valid HOLD use + valid scope allowed with scoped basis
PB-27 PASS: malformed policy cannot become allowed
PB-28 PASS: direct TRACKING_SEEN -> ID_ONLY edit denied
PB-29 PASS: alternate register path denied and CLI option absent
PB-30 PASS: register hash change after seal denied
PB-31 PASS: lowering reseal denied; bytes unchanged
PB-32 PASS: missing register/anchor/trust-root/hash denied
PB-33 PASS: simultaneous register+anchor replacement denied by old root
PB-34 PASS: monotonic reseal allowed with complete audit
```

An additional production-path negative test confirms that a permission `FAIL`
cannot be hidden by HOLD statuses plus a valid scoped risk.

## Regression and safety

```text
PB-01 through PB-23: PASS
Closure 003 tests: 16 passed
Full suite: 328 passed
Strict suite: 328 passed with -W error
Invalid external root: 328 passed
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

This is a Closure 003 fix candidate for independent re-review. It is not a
Policy v2.1 PASS claim and does not authorize a PR merge or real-data research.
