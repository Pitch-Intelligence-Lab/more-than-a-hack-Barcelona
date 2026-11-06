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
- Result: 199,319 rows; H=71,228, A=61,607, D=26,022, X=40,462
- Segments: H=220 mean 12.951 s; A=216 mean 11.409 s; D=69 mean 15.085 s
- Emission: valid=170,485, invalid=28,834; Smart Tagging conflicts=8,964
- D provenance: Smart Tagging-only=19,203; forced-only=2,643; out-of-bounds-only=784; ball-rest-only=358; no current source=2,014
- Smart Tagging dead evidence: 24,091 frames; overlap with tracking H/A=1,887
- Output SHA-256: `866f02601da425e9545e073cf1c37de1146bd2b4b19d604173cbc14c834490a7`
- Validator: project validator pass; official-format validator pass at commit
  `f8f2629ff1e0985f81d7e59d8413678514ee1530` (CRLF script SHA-256 matches
  `d716bf6fce9c8a8d334a9258a3bfca63b8153ae9cd98a4bf80fe0d04693af914`)
- Generalisation: `GENERALISATION NOT ESTABLISHED`
- Decision: engineering candidate is runnable; no model-performance or generalisation claim

## E-B-004: Repeatability

- Date: 2026-11-07
- Run command: repeat E-B-003 to `outputs/candidate-b-repeat.csv`
- Result: byte-identical output
- SHA-256: `866f02601da425e9545e073cf1c37de1146bd2b4b19d604173cbc14c834490a7`
- Decision: deterministic for the frozen input and configuration
