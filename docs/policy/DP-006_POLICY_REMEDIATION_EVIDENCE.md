# DP-006 Policy Remediation Evidence

**Task:** DP-006-POLICY-REMEDIATION-001

**Reviewed baseline:** `a1fd8064f1578fab78b78c2a202729910da30071`

**Result:** remediation candidate submitted for independent PM/QA review

## R1–R8

| ID | Status | Production integration |
|---|---|---|
| R1 complete use gate | PASS candidate | `evaluation/runner.py` calls the centralized authorization gate for read, tracking input, phase input, evaluation uses and label profiles before `match_loader`. |
| R2 audit gate | PASS candidate | `scripts/audit_external.py` authorizes read, evaluation, possession profile, phase profile, label semantics and phase semantics before match loading/proxy construction. |
| R3 holdout integration | PASS candidate | Runner maps split manifests to `SplitAssignment`, loads the v2 holdout manifest in promotion mode and validates all freeze hashes with `HoldoutManifest.require_frozen()`. |
| R4 phase-gap proxy gate | PASS candidate | `map_proxy_target()` requires PASS possession and phase profiles and records definition IDs, mapping IDs and mapping versions. |
| R5 temporal integration | PASS candidate | `predict_model_input()` invokes temporal validation; future-only fields without `interval_end` are HOLD. |
| R6 licence representation | PASS candidate | SkillCorner manifest separates `repository_software_license=MIT` from `data_license_status=HOLD` and evidence IDs. |
| R7 historical restoration | PASS | Five historical files match their recorded `cdfeaf3` Git blob IDs. |
| R8 official traceability | PASS candidate | Rule rows include repository, revision, file, lines, SHA-256, evidence ID, quote, implication and decision. |

## Four core counterexamples

### CE-01: Tracking input HOLD

**Before:** read/evaluation were allowed, but tracking and phase model-input gates were never checked; the probe returned `runner_result=ACCEPTED_WITH_MODEL_INPUT_GATES_ON_HOLD`.

**After:** `test_model_input_hold_blocks_before_loader[tracking_model_input-tracking_model_input]`

- Expected exception identifies `tracking_model_input`.
- Mock external loader call count is asserted as `0`.
- No output report is written.

### CE-02: Audit evaluation HOLD

**Before:** audit checked only read/preprocess and then reached external file handling. The probe reported `audit_checked_evaluation_gate=False`.

**After:** `test_audit_evaluation_hold_fails_before_output`

- Audit fails with `evaluation_reference` authorization error.
- Exit code is non-zero.
- No audit output file is created.
- The nonexistent external root is not reached.

### CE-03: `2017461` placed in holdout

**Before:** the prior promotion test placed `2017461` in holdout and expected evaluation success.

**After:** `test_2017461_in_holdout_fails_before_external_loader`

- `SplitAssignment.validate()` rejects `2017461` outside development.
- External loader call count is `0`.
- Promotion cannot proceed.

### CE-04: Future field without interval end

**Before:** `event_end_x` with `interval_end=None` returned PASS.

**After:** `test_future_field_without_interval_end_is_hold`

- Temporal status is HOLD.
- `require_available()` rejects the field.
- The production prediction path calls temporal validation before feature use.

## Additional fail-closed tests

- phase model input HOLD blocks before loader;
- possession or phase label profile HOLD blocks before loader;
- sealed holdout freeze mismatch blocks before loader;
- audit and evaluator fail on SkillCorner HOLD;
- ModelInput allowlist rejects possession, player-possession, phase-team and future-result variants;
- phase-gap proxy rejects a HOLD phase profile.

## Historical restoration

| File | Required/base blob | Restored blob | Match |
|---|---|---|---|
| `docs/external-data-audit.md` | `1482f7a09cce1ac55aafa17a9d9c68532d89d048` | `1482f7a09cce1ac55aafa17a9d9c68532d89d048` | yes |
| `docs/external-evaluation.md` | `6e36f81b4f29b6839cb3bf2a738aad5a37b658d1` | `6e36f81b4f29b6839cb3bf2a738aad5a37b658d1` | yes |
| `docs/experiment-log.md` | `54f288528f771d64bd4810bf66d418646028f3e9` | `54f288528f771d64bd4810bf66d418646028f3e9` | yes |
| `docs/technical-report.md` | `19ef8fcc4c5d28789c4c2e805d2681eef09295e2` | `19ef8fcc4c5d28789c4c2e805d2681eef09295e2` | yes |
| `docs/engineering-sprint-dp006.md` | `356746322f5bb9a20653c20d2ff604f830f80016` | `356746322f5bb9a20653c20d2ff604f830f80016` | yes |

## Safety

```text
External data accessed: no
Real external evaluation run: no
Training or tuning run: no
Stable foundation changed: no
Frozen data package changed: no
```

The policy implementation remains under PM/QA review and real-data research remains HOLD.
