# Engineering Handoff: DP-005

```text
Task ID: DP-005.1 through DP-005.7
Branch: feature/DP-005-general-state-machine
Commit: feature-branch HEAD reported with the pull request
Pull request: pending authenticated GitHub PR creation
Changed files:
  configs/state-engine.json
  src/mtah_possession/algorithm_config.py
  src/mtah_possession/data/observations.py
  src/mtah_possession/data/tracking.py
  src/mtah_possession/features/evidence.py
  src/mtah_possession/pipeline/build_submission.py
  src/mtah_possession/pipeline/health.py
  src/mtah_possession/states/cleanup.py
  src/mtah_possession/states/possession_state.py
  tests and DP-005 documentation
How to run:
  $env:MTAH_DATA_DIR = "E:\mtah2027-data"
  .\.venv\Scripts\python.exe scripts\build_submission.py `
    --output outputs\submission-state-engine.csv `
    --config configs\state-engine.json `
    --health-report outputs\submission-state-engine.health.json `
    --force
Tests:
  53 passed
  ruff check: pass
  ruff format --check: pass
Validator:
  project validator: pass
  official format validator: pass
Output SHA-256:
  db132162c9711f01dd5ff9bca4b9867baac8ed64ded80b700944bc2c13dc0177
Rows:
  199319, frames 0..199318
Label counts:
  H=81311, A=74490, D=3056, X=40462
Segment summary:
  H: count=166, mean=19.593 s, shortest=0.88 s, longest=218.28 s
  A: count=175, mean=17.026 s, shortest=0.28 s, longest=247.16 s
  D: count=19, mean=6.434 s, shortest=0.08 s, longest=47.56 s
Observation quality:
  observed=113488, interpolated=108, missing=85723
  graded: observed=94214, interpolated=39, missing=64604
Transition summary:
  H->A=162, A->H=159, H->D=4, A->D=14, D->H=6, D->A=13
Input hashes:
  atd_meta=327e35e32e46a647389b88f883d4f9a2ab931e3e6148aef2fcf8f22b1e93c43a
  atd_raw=f130e350d2bfdf734b7e32f072931fccc6d015c1e837d082064875fe0a700431
Parameters changed and source:
  every value, unit, source and rationale is recorded in configs/state-engine.json;
  defaults use official facts, general football priors and frozen engineering assumptions
Known limitations:
  public smoke macroF1=0.4998, spellF1=0.3897, D F1=0; ball rest can confuse
  shielding with a stoppage; local player evidence can fail in a crowded box;
  optional Smart Tagging, restart-zone and reachability features are disabled
Blockers:
  GitHub PR creation still needs an authenticated interactive session. No algorithm,
  validation or data-compliance blocker remains.
```

## Verification notes

- Repeat generation produced the same bytes and SHA-256.
- H+A+D equals all 158,857 graded frames; X equals all 40,462 configured ungraded frames.
- The DP-001 through DP-004 fallback rebuild retained its prior SHA-256
  `caf42b0775d695e29859f775c67d42162a92d32655facb202c548b3b59fb220f`.
- No competition file or generated CSV is tracked by Git.
- The public five-minute possession answer was not used to choose or compare DP-005 variants.
- One public smoke run occurred only after parameter freeze and produced no parameter change.

