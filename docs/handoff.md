# Engineering Handoff: DP-005

```text
Task: PR #1 remediation and DP-005 review gate
Branch: feature/DP-005-general-state-machine
Commit: feature-branch HEAD; exact hash is reported on PR #1
Pull request: https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona/pull/1
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
Fixes completed:
  forced D for second-half pre-kickoff frames 110808..113741;
  finite-only missing-team distance arithmetic;
  restart evidence wired into D-to-team confirmation;
  default D preservation in cleanup;
  forced-block and cleanup-removal health reporting;
  documentation corrected
How to run:
  $env:MTAH_DATA_DIR = "E:\mtah2027-data"
  .\.venv\Scripts\python.exe scripts\build_submission.py `
    --output outputs\submission-state-engine.csv `
    --config configs\state-engine.json `
    --health-report outputs\submission-state-engine.health.json `
    --force
Tests:
  64 passed
Warning-free tests:
  64 passed with -W error
  ruff check: pass
  ruff format --check: pass
Validator:
  project validator: pass
  official format validator: pass
Output SHA-256:
  1de6261504c7cb539a4e78f42f18011c692b9bd148ea3e77fbca44df9c0b9401
Rows:
  199319, frames 0..199318
Label counts:
  H=79250, A=73608, D=5999, X=40462
Forced-dead block result:
  frames 110808..113741: 2934/2934 D
Segment summary:
  H: count=161, mean=19.689 s, shortest=1.04 s, longest=218.28 s
  A: count=170, mean=17.320 s, shortest=0.28 s, longest=247.16 s
  D: count=20, mean=11.998 s, shortest=0.08 s, longest=117.72 s
Observation quality:
  observed=113488, interpolated=108, missing=85723
  graded: observed=94214, interpolated=39, missing=64604
Transition summary:
  H->A=157, A->H=154, H->D=4, A->D=14, D->H=7, D->A=13
Cleanup removals:
  H=0, A=0, D=0
Input hashes:
  atd_meta=327e35e32e46a647389b88f883d4f9a2ab931e3e6148aef2fcf8f22b1e93c43a
  atd_raw=f130e350d2bfdf734b7e32f072931fccc6d015c1e837d082064875fe0a700431
Parameters changed and source:
  every value, unit, source and rationale is recorded in configs/state-engine.json;
  defaults use official facts, general football priors and frozen engineering assumptions
Known limitations:
  public smoke macroF1=0.4998, spellF1=0.3897, D F1=0; possession continuity
  improved, but general dead-ball recognition remains incomplete; ball rest can
  confuse shielding with a stoppage; local evidence can fail in a crowded box;
  optional Smart Tagging, restart-zone and reachability features are disabled
Public smoke result, if run once:
  macroF1=0.4998, spellF1=0.3897, D F1=0. No parameter changed afterward.
Blockers:
  none. The pull request is open against dev.
```

## Verification notes

- Repeat generation produced the same bytes and SHA-256.
- H+A+D equals all 158,857 graded frames; X equals all 40,462 configured ungraded frames.
- Frames 110808..113741 are 100% D, including after cleanup.
- The DP-001 through DP-004 fallback rebuild retained its prior SHA-256
  `caf42b0775d695e29859f775c67d42162a92d32655facb202c548b3b59fb220f`.
- No competition file or generated CSV is tracked by Git.
- The public five-minute possession answer was not used to choose or compare DP-005 variants.
- One post-v1.2 public smoke run occurred only after parameter freeze and produced no parameter change.

