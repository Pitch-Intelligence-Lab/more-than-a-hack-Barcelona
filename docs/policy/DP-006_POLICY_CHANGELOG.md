# DP-006 Policy Changelog

## DP-006-POLICY-v2

**Date:** 2026-11-08

**Status:** proposed design baseline

### Superseded

- `D-033 possession labels are evaluation-only` as a blanket rule.
  - Superseded by role-based label governance.
  - External possession may supervise training when provider rights and internal authorization pass.
  - Possession labels remain prohibited from `ModelInput`.

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

