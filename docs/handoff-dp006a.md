# Engineering Handoff: DP-006A

```text
Branch: feature/DP-006A-leakage-promotion-gate
Local commit: local branch HEAD; not pushed
Changed files:
  src/mtah_possession/evaluation/external.py
  src/mtah_possession/evaluation/splits.py
  scripts/evaluate_external.py
  tests/test_external_metrics.py
  tests/test_external_splits.py
  tests/test_neutral_adapter.py
  docs/evaluation-contract.md
  docs/decision-log.md
  docs/experiment-log.md
  README.md
Tests:
  86 passed
Warning-free tests:
  86 passed with -W error
Ruff:
  check passed; format check passed
External data accessed: no
Network calls:
  only `git fetch origin` to synchronize repository state;
  no SkillCorner API, external file access or external evaluation
Push/PR/merge: no
Known limitations:
  the existing one-match split remains diagnostic only;
  validation and holdout are still empty;
  no external metric report was regenerated;
  phase-derived DP-006 results remain structurally coupled to the proxy.
Approval decisions required:
  review the local diff;
  approve any later push or pull-request update;
  approve any separate external-data follow-up request.
```

## Implemented controls

- Possession-label leakage regression compares two synthetic neutral matches with identical geometry and differing possession fields. The resulting `TrackingData` must be identical and contains no possession field.
- Transition F1 is added to the external metrics and report as the harmonic mean of precision and recall.
- Diagnostic evaluation remains usable with one development match.
- Promotion requires non-empty development, validation and holdout sets plus status `ready_for_validation`.
- Promotion mode rejects the current one-match manifest before external data is read.
- The evaluation contract documents the model-input allowlist, evaluation-only labels, phase coupling, split rules, promotion conditions and provenance.

## Review status

No target submission was built. No external match was read or evaluated. No SkillCorner raw file, local external report or generated external label was opened during DP-006A.
