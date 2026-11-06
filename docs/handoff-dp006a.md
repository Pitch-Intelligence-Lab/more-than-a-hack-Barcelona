# Engineering Handoff: DP-006A Revision 1

```text
Source branch: feature/DP-006A-leakage-promotion-gate
Source commit: b4630764565bf9ce9f8a65069454ec8c47151024
Local revision branch: feature/DP-006A-leakage-promotion-gate
Local commit: pending local commit; not pushed
Pull request: https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona/pull/3 remains open; unapproved for merge
Changed files:
  README.md
  configs/external-splits.json
  docs/decision-log.md
  docs/evaluation-contract.md
  docs/experiment-log.md
  docs/external-data-audit.md
  docs/external-evaluation.md
  docs/handoff-dp006.md
  docs/handoff-dp006a.md
  docs/technical-report.md
  scripts/evaluate_external.py
  src/mtah_possession/data/model_input.py
  src/mtah_possession/data/neutral.py
  src/mtah_possession/data/skillcorner.py
  src/mtah_possession/evaluation/external.py
  src/mtah_possession/evaluation/provenance.py
  src/mtah_possession/evaluation/runner.py
  src/mtah_possession/evaluation/splits.py
  tests/test_external_metrics.py
  tests/test_external_runner.py
  tests/test_external_splits.py
  tests/test_neutral_adapter.py
  tests/test_provenance.py
  tests/test_skillcorner_adapter.py
Tests:
  100 passed
Warning-free tests:
  100 passed with -W error
Ruff:
  check passed; format check passed
External data accessed: no
Network calls:
  only `git fetch origin` to synchronize repository state;
  no SkillCorner API, external file access or external evaluation
Push/PR update for Revision 1: no; merge: no
Target CSV generated: no
Contract version: 1.1.0
Adapter version: 1.1.0
Known limitations:
  the existing one-match split remains diagnostic_only;
  validation and holdout are still empty;
  no external metric report was opened or regenerated;
  phase-derived DP-006 results remain structurally coupled to the proxy.
Approval decisions required:
  review the local Revision 1 diff;
  approve any push or update to stacked PR #3;
  separately approve any merge;
  approve any separate external-data follow-up request.
```

## Implemented controls

- Possession changes cannot affect `ModelInput` or end-to-end labels, reasons and prediction hashes.
- Detected, extrapolated and missing source observations remain distinct.
- CLI split selection is mandatory and has no silent default.
- Diagnostic, validation and promotion modes require matching split types.
- `ready_for_validation` cannot authorise promotion.
- Promotion requires `ready_for_promotion_review`; precheck failure occurs before external loading.
- Transition metrics include precision, recall and F1.
- Per-match metrics and explicit cross-match macro/micro aggregation are defined.
- Reports include code, adapter, configuration and contract versions plus report identity hashes.

## Review status

No target submission was built. No external match was read or evaluated. No SkillCorner raw file, local external report or generated external label was opened during Revision 1.
