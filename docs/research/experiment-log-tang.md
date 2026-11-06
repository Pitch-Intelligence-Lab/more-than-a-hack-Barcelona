# Tang Candidate B Experiment Log

Never paste competition rows, video frames or screenshots into this file.

## E-B-001: Synthetic L1/L2/L3 interface tests

- Date: 2026-11-07
- Research question: Can the evidence, emission and Viterbi layers preserve the frozen contract while handling noisy/missing evidence?
- Data source: synthetic tracking and synthetic Smart Tagging XML only
- License/use: synthetic test data generated in the repository
- Train/validation/holdout: none
- Code version: `research/tang/independent-v1` working tree
- Configuration: `configs/candidates/tang/candidate-b.json` with small synthetic frame counts
- Run command: `.venv/bin/python -m pytest tests/candidates -q`
- Result: 8 candidate tests passed
- Coverage: tracking-vs-Smart-Tagging conflict, missing ball, out-of-bounds D, direct H/A switch, missing-ball persistence, dead/restart, X/forced blocks, Smart Tagging pre-restart/restart separation, adapter determinism
- Evaluation metric: interface and behavior assertions, not model accuracy
- Failure types: none in this run
- Reproducibility: deterministic synthetic inputs
- SHA-256: not applicable to synthetic assertions

## E-B-002: Frozen regression with Candidate B present

- Date: 2026-11-07
- Research question: Did Candidate B preserve the frozen base?
- Data source: frozen repository tests
- Ground truth: not read
- Run command: `.venv/bin/python -m pytest && .venv/bin/python -m pytest -W error`
- Result: 72 passed, including 64 frozen tests and 8 candidate tests
- Ruff: check and format check passed
- Frozen DP-005 baseline: reproduced separately with SHA-256 `1de6261504c7cb539a4e78f42f18011c692b9bd148ea3e77fbca44df9c0b9401`
- Decision: candidate is isolated in new modules; no frozen L0/L4 or stable config changes

## E-B-003: Real local aggregate build

- Date: 2026-11-07
- Research question: Does the complete Candidate B adapter run end-to-end on the local tactical input?
- Data source: local tactical ATD and Smart Tagging through `MTAH_DATA_DIR`
- Ground truth: not read
- Public scoring: not run
- Train/validation/holdout: none
- Code version: `research/tang/independent-v1` working tree
- Configuration: `configs/candidates/tang/candidate-b.json`
- Run command: `MTAH_DATA_DIR=/mnt/d/mtah2027-data .venv/bin/python scripts/build_candidate_tang.py --output outputs/candidate-b.csv --config configs/candidates/tang/candidate-b.json --health-report outputs/candidate-b.health.json --force`
- Result: 199,319 rows; H=70,469, A=60,093, D=28,295, X=40,462
- Segments: H=207 mean 13.617 s; A=199 mean 12.079 s; D=101 mean 11.206 s
- Emission: valid=134,876, invalid=64,443; contested=24,989; Smart Tagging conflicts=7,120
- D provenance: Smart Tagging-only=19,984; forced-only=2,643; out-of-bounds-only=1,144; ball-rest-only=436; no current source=3,009
- Smart Tagging dead evidence: 24,091 frames; overlap with tracking H/A=1,887
- Output SHA-256: `42e0469e45b4bb825d20c3c1a79930601ef4be651e9e08594203d5224fee7531`
- Validator: project validator pass; official-format validator pass at commit
  `f8f2629ff1e0985f81d7e59d8413678514ee1530` (CRLF script SHA-256 matches
  `d716bf6fce9c8a8d334a9258a3bfca63b8153ae9cd98a4bf80fe0d04693af914`)
  The official validator reports 406 possessions of mean 12.9 s; this is a format check only.
- Generalisation: `GENERALISATION NOT ESTABLISHED`
- Decision: engineering candidate is runnable; no model-performance or generalisation claim

## E-B-004: Repeatability

- Date: 2026-11-07
- Run command: repeat E-B-003 to `outputs/candidate-b-repeat.csv`
- Result: byte-identical output
- SHA-256: `42e0469e45b4bb825d20c3c1a79930601ef4be651e9e08594203d5224fee7531`
- Decision: deterministic for the frozen input and configuration

## E-B-005: Structural optimization iterations

- Date: 2026-11-07
- Ground truth: not read; public scoring not run
- Optimization 1: split-contest gate (`contest_margin_m=1.5`) and stricter emission validity. If both teams are within the margin and the visible vote is split, the frame has no forced team candidate.
- Optimization 2: H/A smoothing remains 50 frames, but D is kept sharper; sub-second D flicker is handled by a separate 5-frame dead-ball smoothing window.
- Iteration results:
  - Initial emission/Viterbi: 436 H/A possessions, 69 D segments, H/A mean 12.2 s, D mean 15.1 s, SHA `866f…`
  - + contest gate + validity cleanup + D sharpening: 410 H/A, 107 D, H/A mean 12.7 s, D mean 10.6 s, SHA `3ec2…`
  - + D short smoothing: 406 H/A, 101 D, H/A mean 12.9 s, D mean 11.2 s, SHA `42e0…`
- Interpretation: the contest gate reduces forced team decisions; separate D smoothing reduces sub-second dead-ball flicker without blurring H/A. These are structural observations, not accuracy evidence.

## E-B-006: Smart Tagging ablation

- Date: 2026-11-07
- Configuration: `configs/candidates/tang/candidate-b-no-smart.json`
- Data: local tactical ATD only; Smart Tagging disabled
- Ground truth: not read; public scoring not run
- Result: H=76,213, A=73,054, D=9,590, X=40,462
- Segments: H=175, A=177, D=81; H/A mean 16.9 s; D mean 4.7 s
- Output SHA-256: `a11aece78192b27486e7de1298bc9722c69bc499c77a9b46af7e7431ac11ec6b`
- Interpretation: without Smart Tagging, dead-ball frames collapse from 28,295 to 9,590 and D mean duration falls from 11.2 s to 4.7 s. Smart Tagging is materially contributing to D in this dataset, but the ablation cannot establish accuracy or generalisation.
