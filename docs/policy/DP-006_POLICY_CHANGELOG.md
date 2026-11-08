# DP-006 Policy Changelog

## DP-006-POLICY-v2

**Date:** 2026-11-08

**Status:** proposed design baseline

### Superseded

- `D-033 possession labels are evaluation-only` as a blanket rule.
  - Superseded by role-based label governance.
  - External possession may supervise training when provider rights and internal authorization pass.
  - Possession labels remain prohibited from `ModelInput`.
- Historical DP-006 external-data-audit interpretation of the SkillCorner MIT
  repository license.
  - Superseded by `SKILLCORNER_AUTHORIZATION_STATUS.md`.
  - The repository software license is MIT; SkillCorner data rights remain HOLD.

### Added

- provider × use × status policy;
- label roles and evidence-gated role transitions;
- temporal availability policy for Dynamic Events;
- phase gap and phase-team leakage controls;
- possession player-ID auxiliary-target controls;
- provider label definition and mapping IDs;
- holdout status lifecycle;
- fail-closed policy checks before external data loading.

### Clarified

- Official rules permit external data and external supervision subject to access, rights and documentation.
- SkillCorner data rights remain HOLD.
- Official five-minute ground truth remains pipeline-check only.

### Unchanged

- DP-005 parameters;
- stable foundation;
- frozen cross-match data package v1;
- P0 data audit archive;
- DP-006A research baseline.

## DP-006-POLICY-REMEDIATION-001

**Date:** 2026-11-08

**Status:** remediation candidate submitted for independent PM/QA review

### Added

- unified authorization result covering read/preprocess, tracking input,
  phase input, evaluation reference, label profiles and holdout freeze checks;
- audit evaluation-reference and phase-profile gates;
- phase-gap proxy profile and mapping enforcement;
- holdout sealed-freeze validation at the production evaluator entry point;
- temporal validation in the actual model prediction path;
- separated repository software licence and data-license status;
- official-rule traceability with revision, line range and evidence hash.

### Restored

The five historical DP-006 files listed in the remediation manifest were
restored byte-for-byte to their `cdfeaf3` blob IDs. Current policy guidance lives
only under `docs/policy/`.

### Not claimed

This changelog does not declare final policy acceptance. PM/QA review remains
required, and all real external-data research remains `HOLD`.

## DP-006-POLICY-REMEDIATION-002

**Date:** 2026-11-08

**Status:** remediation candidate submitted for independent PM/QA review

### Fixed

- bind Promotion to `HOLDOUT_SEAL_VERIFIED`, the declared split, a non-empty
  holdout match set and the current match;
- compute all freeze identities from six real artifact categories rather than
  accepting trusted CLI hash strings;
- persist sealed, unsealed, started, completed, failed and compromised holdout
  lifecycle events in an append-only hash-chained JSONL ledger;
- carry real per-frame temporal availability for phase masks, restart evidence
  and source codes through `with_event_evidence()` and the production evaluator;
- reject empty or incomplete temporal registries and scalar zero-time
  placeholders for phase-derived fields.

### Not claimed

R3 and R5 are fix candidates only. Policy implementation final acceptance,
merge and real-data research authorization remain `HOLD` for PM/QA.

## DP-006-POLICY-REMEDIATION-003

**Date:** 2026-11-08

**Status:** Holdout ledger state-machine fix candidate for PM/QA review

### Fixed

- separate `AUTHORIZATION_DENIED` from permanent Holdout contamination;
- derive lifecycle state through an explicit event reducer;
- make `COMPROMISED` permanent across Promotion attempts;
- identify a Holdout by provider plus sorted match IDs rather than manifest SHA;
- add a production CLI/API that marks a completed result as used for tuning and
  permanently compromises the Holdout;
- fail closed on invalid JSON, broken hash chains, illegal event order and
  mismatched stable identity.

### Not claimed

Policy implementation final acceptance, merge and real-data research
authorization remain `HOLD` for PM/QA.

