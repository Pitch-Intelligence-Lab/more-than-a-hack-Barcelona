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
- Result: 17 candidate tests passed
- Coverage: tracking-vs-Smart-Tagging conflict, missing ball, out-of-bounds D, split contest, loose-ball control limit, low-confidence segment filtering, high-confidence quick-switch preservation, evidence-strength hysteresis, hysteresis weak-flicker suppression, dwell strong-switch preservation, dwell weak-flicker suppression, dwell dead-ball transition, direct H/A switch, missing-ball persistence, dead/restart, X/forced blocks, Smart Tagging pre-restart/restart separation, adapter determinism
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
- Result: 81 passed, including 64 frozen tests and 17 candidate tests
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
- Result: 199,319 rows; H=70,172, A=59,055, D=29,630, X=40,462
- Segments: H=195 mean 14.394 s; A=189 mean 12.498 s; D=96 mean 12.346 s
- Emission: valid=115,166, invalid=84,153; contested=24,989; loose-ball=29,815; Smart Tagging conflicts=4,400
- D provenance: Smart Tagging-only=20,056; forced-only=2,643; out-of-bounds-only=1,579; ball-rest-only=927; no current source=3,270
- Smart Tagging dead evidence: 24,091 frames; overlap with tracking H/A=1,887
- Output SHA-256: `db2400dc0de196e814438401797326c358c1d8c2486e0cd22c24aab182127b69`
- Validator: project validator pass; official-format validator pass at commit
  `f8f2629ff1e0985f81d7e59d8413678514ee1530` (CRLF script SHA-256 matches
  `d716bf6fce9c8a8d334a9258a3bfca63b8153ae9cd98a4bf80fe0d04693af914`)
  The official validator reports 384 possessions of mean 13.5 s; this is a format check only.
- Generalisation: `GENERALISATION NOT ESTABLISHED`
- Decision: engineering candidate is runnable; no model-performance or generalisation claim

## E-B-004: Repeatability

- Date: 2026-11-07
- Run command: repeat E-B-003 to `outputs/candidate-b-repeat.csv`
- Result: byte-identical output
- SHA-256: `db2400dc0de196e814438401797326c358c1d8c2486e0cd22c24aab182127b69`
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
  - + low-confidence segment filtering: unchanged at 406 H/A, 101 D, SHA `42e0…` (the filter did not fire on real data; residual short segments were high-confidence)
  - + 5 m control-zone limit: 384 H/A, 96 D, H/A mean 13.5 s, D mean 12.3 s, SHA `db24…`
- Interpretation: the contest gate and control-zone limit reduce forced team decisions; separate D smoothing reduces sub-second dead-ball flicker. The control-zone limit raises invalid/uncertain frames from 64,443 to 84,153, so the smoother structure is a trade-off, not proof of better accuracy.

## E-B-006: Smart Tagging ablation

- Date: 2026-11-07
- Configuration: `configs/candidates/tang/candidate-b-no-smart.json`
- Data: local tactical ATD only; Smart Tagging disabled
- Ground truth: not read; public scoring not run
- Result: H=74,122, A=72,761, D=11,974, X=40,462
- Segments: H=167, A=166, D=72; H/A mean 17.6 s; D mean 6.7 s
- Output SHA-256: `8f2a248e3b5e63b64a458b7e67409ddd4a691cc23d652562a7fe5c4b7d40acba`
- Interpretation: without Smart Tagging, dead-ball frames fall from 29,630 to 11,974 and D mean duration falls from 12.3 s to 6.7 s. Smart Tagging is materially contributing to D in this dataset, but the ablation cannot establish accuracy or generalisation.

## E-B-007: Literature-informed control-zone and segment filtering

- Date: 2026-11-07
- References: R-01 `arXiv:2202.00804`, R-02 `arXiv:2005.04020`, R-03 `arXiv:2311.18028`, R-04 `arXiv:2206.10926`
- Use: method ideas only; no code, labels, videos or external match data copied
- Control-zone experiment: nearest-player distance above 5 m leaves the team unresolved; this is a noise-tolerant adaptation of the paper's 0.5-1 m possession zone, not a reproduction of their threshold.
- Segment-filter experiment: short low-confidence H/A or D segments between the same team may be merged; high-confidence quick switches are preserved.
- Synthetic result: 13 candidate tests passed, including low-confidence segment merge, high-confidence quick-switch preservation, control-zone abstention, contest abstention, missing-ball persistence and deterministic adapter output.
- Real-data result: the segment filter did not alter the output; the 5 m control zone changed H/A from 406 to 384 possessions and increased uncertain frames to 84,153. This is a structural trade-off, not accuracy evidence.

## E-B-008: Duration-aware Viterbi sensitivity

- Date: 2026-11-07
- Reference: R-03 filtered semi-Markov / segment-level duration modeling
- Implementation: age-augmented Viterbi where a state carries a dwell age; leaving H/A before the dwell horizon pays a decaying extra cost. D is exempt because dead-ball entry/exit has its own costs.
- Experimental configurations: `candidate-b-dwell15.json` (0.6 s dwell, 1.5 penalty) and `candidate-b-dwell30.json` (1.2 s dwell, 2.5 penalty, 3.5 switch penalty)
- Synthetic tests: strong quick H→A switch preserved; weak 5-frame A flicker suppressed; D transition still occurs under dwell.
- Dwell15 real output: 384 H/A possessions, 96 D segments, SHA `4cd5…` (same segment counts as the main non-dwell path; only boundary frames shifted).
- Dwell30 real output: 377 H/A possessions, 186 D segments, SHA `ab90…` (D fragmentation doubles; not acceptable).
- Main decision: keep `dwell_frames=0` in `candidate-b.json`, use the proven simple Viterbi path, and retain dwell configs as experiments only.

## E-B-009: Evidence-strength hysteresis

- Date: 2026-11-07
- Motivation: replace fixed dwell with a transition discount proportional to the H/A probability margin.
- Implementation: when the destination team probability exceeds the source team probability, the H/A transition cost is discounted by `min(hysteresis_max_boost, hysteresis_gain * margin)`.
- Experimental configuration: `candidate-b-hysteresis.json` with gain 2.0 and max boost 2.0.
- Synthetic result: strong H→A evidence switches; a weak five-frame A flicker is suppressed.
- Real output: 384 H/A possessions and 96 D segments, unchanged from the stable candidate; SHA `8a3f…`.
- Decision: keep as an experimental config; the stable main remains `hysteresis_gain=0`.
