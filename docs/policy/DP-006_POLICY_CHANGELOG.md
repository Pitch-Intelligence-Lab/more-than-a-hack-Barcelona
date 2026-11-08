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

## DP-006-POLICY-REMEDIATION-006

**Date:** 2026-11-08

**Status:** bounded closure candidate for DP-006 Final Assurance Review

### Closed

- bind canonical provider/config/path/file Source Identity to V4 Holdout seals;
- reject all post-seal Source changes before the external loader;
- verify migration target artifacts from the actual migration Git tree;
- reject worktree/commit mismatches and invalid approval/old-code ancestry;
- preserve audit-only migration and all prior authorization/lifecycle controls.

### Not claimed

Policy implementation final acceptance remains `HOLD`.
No automatic REPAIR-007 is authorized.

## DP-006-POLICY-REMEDIATION-006-CLOSURE-CORRECTION

**Date:** 2026-11-08

**Status:** closure-correction candidate for Independent REPAIR-006 Re-review

### Fixed

- derive the legacy Holdout Manifest SHA from the original sealed ledger;
- serialize ledger appends and migrations, then reread and verify the expected
  head under the lock;
- validate the complete candidate ledger before an atomic replacement;
- seal the complete Holdout `SourceIdentitySet`, including its descriptor and
  sorted per-match source identities;
- resolve source-set member configs as repository-relative paths;
- use a source-only canonical projection so governance permission fields do not
  enter Source Identity;
- re-run Governance Authorization after permission restoration.

### Not claimed

This is an engineer correction candidate only. It does not start Final
Assurance, authorize REPAIR-007 or merge PR #9, and it does not declare Policy
implementation PASS.

## DP-006-POLICY-REMEDIATION-006-C2-LIFECYCLE-CLOSURE

**Date:** 2026-11-09

**Status:** C2 production lifecycle candidate for Independent REPAIR-006 Re-review

### Fixed

- stop comparing a later Holdout match against the first sealed single-match
  `source_identity`;
- select the current match identity from the sealed `SourceIdentitySet`;
- add V6 collection and match event scopes;
- track `NOT_STARTED`, `RUNNING`, `FAILED` and `COMPLETED` independently per
  match;
- derive aggregate completion only when every registered match is completed;
- require one shared ledger for positive multi-match evidence;
- preserve collection-level `COMPROMISED` as a permanent terminal state;
- keep V4 and V5 ledgers fail-closed behind controlled re-seal requirements.

### Not claimed

This is an engineer candidate only. Final Assurance, REPAIR-007, merge and
Policy implementation PASS remain not authorized.

## DP-006-POLICY-REMEDIATION-006-TUNING-CONTAMINATION-CLOSURE

**Date:** 2026-11-09

**Status:** tuning-contamination candidate for Independent REPAIR-006 Re-review

### Fixed

- allow tuning contamination from any matching completed Holdout member without
  requiring aggregate completion;
- reread and validate the ledger inside the per-ledger lock;
- append a collection-level, permanent `COMPROMISED` event atomically;
- reject unknown, cross-Holdout and non-completed predictions without mutation;
- make runner START, contamination and all lifecycle writes share the same lock
  linearization point;
- prevent a post-contamination completion from becoming a usable result.

### Not claimed

Final Assurance, REPAIR-007, merge and Policy implementation PASS remain not
authorized.

## DP-006-FINAL-ASSURANCE-REVIEW-HANDOFF

**Date:** 2026-11-09

**Status:** frozen evidence handoff for Independent Final Assurance Review

### Added

- Final Assurance evidence index tied to Review HEAD
  `4a8a96aba8f9ec547e8950db55e998605b9c86bc`;
- known P1 for collection-level contamination source-identity readability;
- explicit TOCTOU review item between source validation and loader re-read;
- corrected Remote HEAD records from the completed tuning-contamination handoff.

### Boundary

No implementation, algorithm, Ledger, SourceIdentitySet, authorization or
DP-005/frozen-data behavior is changed. Final Assurance, Policy implementation
acceptance, PR merge and real-data research remain separate decisions.

## DP-006-FINAL-ASSURANCE-TOCTOU-001

**Date:** 2026-11-09

**Status:** A2 Source Integrity P0 remediation candidate for full Assurance rerun

### Fixed

- bind the production runner to an immutable SkillCorner manifest snapshot;
- read each license/readme/tracking/phases/match file once and use the same
  bytes for checksum and parsing;
- return loader actual Source Identity, checksums and snapshot digest;
- compare sealed and actual identities before evaluator;
- persist mismatch failures without `EVALUATION_COMPLETED`;
- bind collection-level tuning contamination to the trigger member identity;
- require match events to share their Source Identity member.

### Boundary

This does not declare Final Assurance PASS, Policy implementation PASS, PR merge
approval or real-data authorization.

## DP-006-FINAL-ASSURANCE-AUDIT-SNAPSHOT-001

**Date:** 2026-11-09

**Status:** Audit production P0 remediation candidate for full Assurance rerun

### Fixed

- bind `scripts/audit_external.py` to one immutable manifest snapshot;
- build Source Identity and authorization from the same snapshot manifest;
- pass the snapshot and expected identity to the production snapshot loader;
- validate actual identity, checksums, snapshot digest and match ID before map or
  report generation;
- write source-integrity provenance into successful Audit output;
- fail without replacing successful/partial output on mismatch;
- mark the mutable-path loader compatibility-only and scan production scripts for
  its use.

### Boundary

This does not declare Final Assurance PASS, Policy implementation PASS, merge
approval or real-data authorization.

## DP-006-FINAL-ARCHIVE

**Date:** 2026-11-09

**Status:** independent Final Assurance PASS archived; PM signature pending

### Recorded

- Final implementation commit `748c4dbe6cd189e0a5f815e1127155ff45c9a85d`;
- Final documentation evidence commit
  `86c1cd4c246c8ac14ec53d33e8c830476debca98`;
- Remote HEAD at Final Assurance
  `ee86017b5fdaa6c380fe1d8ad3562779399b085d`;
- A1 Authorization, A2 Source Integrity, A3 Identity Integrity, A4 Lifecycle
  Integrity and A5 Reproducibility all PASS;
- 271 tests, invalid external-root, Ruff and format checks pass;
- stable/research tags and frozen objects unchanged;
- no real data access, training, tuning or real evaluation.

### Boundary

This is a docs-only archive. Policy implementation signature, PR merge and
real-data research authorization remain PM decisions. No REPAIR-007 is
authorized.

## DP-006-POLICY-REMEDIATION-005

**Date:** 2026-11-08

**Status:** audit-only migration and immutable-seal candidate for PM/QA review

### Fixed

- migration now produces only `MIGRATED_AUDIT_ONLY` and never Promotion authority;
- migration receipts are verified against real Git commits, committed approval
  evidence and current approved Model/Evaluation/Split identities;
- first `SEALED_VERIFIED` binds immutable Holdout Manifest content/path and split
  manifest SHA-256;
- `runner.py`, `splits.py` and `configs/external-splits.json` now affect
  Evaluation/Split Identity;
- compromised match sets cannot be recovered through migration, re-sealing or a
  new stable identity.

### Not claimed

Policy implementation final acceptance, merge and real-data research
authorization remain `HOLD` for PM/QA.

## DP-006-POLICY-REMEDIATION-004

**Date:** 2026-11-08

**Status:** model/governance identity separation candidate for PM/QA review

### Fixed

- remove the external-data policy from the model freeze;
- replace the all-source model path with explicit prediction, feature, data
  transform, configuration, hyperparameter, evaluation and metric categories;
- exclude policy files and governance-only code from model freeze comparison;
- record a separate governance authorization identity on new ledger events;
- preserve `AUTHORIZATION_DENIED` semantics when permissions change;
- append `FREEZE_PROTOCOL_MIGRATED` to legacy ledgers without deleting or
  rebuilding original events;
- prevent a compromised legacy ledger from being migrated to a clean state;
- add a production migration CLI with approval, rule and commit evidence.

### Not claimed

Policy implementation final acceptance, merge and real-data research
authorization remain `HOLD` for PM/QA.

