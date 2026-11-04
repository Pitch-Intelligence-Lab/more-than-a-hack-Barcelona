# Technical Report: Tactical Nearest-Player Baseline

**Team:** Pitch Intelligence Lab

**Status:** DP-001 through DP-004 implementation; not the final algorithm

**Code repository:** <https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona>

## Scope and status

This report covers engineering milestone 1 only: DP-001, DP-002, DP-003, and DP-004. It is not the final competition algorithm. The rule-based H/A/D/X state machine and Smart Tagging evidence layer are deferred because their football semantics require PM and QA decisions.

## Inputs used

- Tactical FIFA/EPTS metadata (`BAR-ATH_tactical_atd.xml`)
- Tactical raw ATD (`BAR-ATH_tactical_atd.txt`)
- Public official documentation for file structure, timebase, and the nearest-player baseline

Assets deliberately not used:

- Tactical or broadcast video
- Broadcast ATD
- Homography
- Smart Tagging
- Public five-minute possession ground truth
- Private ground truth, event data, or external labelled data

## Method

The metadata defines two team IDs and assigns each of the 46 player slots to one of them. The code treats the first metadata team as home and second as away. ATD records are required to be contiguous from `frame_id=1`; submission frame is the ATD frame minus one.

For each visible ball, every visible player slot is transformed from normalised to metric pitch coordinates. Squared Euclidean distances are compared separately for home and away. The closer team is the raw candidate. A distance tie, a missing ball, or no visible player produces an internal no-candidate state.

A centred majority vote then produces `H` or `A`. A frame with no votes or an exact H/A vote tie is `D`. This intentionally has no `X` path in milestone 1.

## Training and parameter selection

No machine-learning model is trained. No labelled match data is used for training, validation, or parameter fitting.

The 25 FPS and frame-count contract come from public competition documentation. The 105.3 x 68.0 m pitch and 50-frame majority half-width are explicit pre-registered settings, not values chosen by comparing outputs with this match's public or private ground truth.

## Possession and dead-ball rules

This milestone reproduces the published nearest-player baseline. It does not claim a football-semantic dead-ball detector: missing ball observations become `D`. It does not model controlled possession, loose balls, or restart ownership. Those rules remain open for DP-005 and DP-006 after team review.

## Determinism

- The JSON configuration contains every numeric algorithm parameter.
- Inputs are required in contiguous frame order.
- No random operation is used.
- Candidate ties have an explicit no-candidate outcome.
- CSV uses UTF-8 and LF line endings.
- The final path is replaced only after full contract validation.
- Repeated runs with the same code, configuration, and inputs should produce identical bytes and SHA-256.

## Reproduction

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest
$env:MTAH_DATA_DIR = "E:\mtah2027-data"
.\.venv\Scripts\python scripts\build_submission.py `
  --output outputs\submission.csv `
  --config configs\baseline.json
.\.venv\Scripts\python scripts\validate_submission.py outputs\submission.csv
```

Team QA must run the real-data builder, run the official validator, repeat generation, compare hashes, and scan the repository for match assets.

The team-local run passed. The output contained 199,319 rows with H=72,553, A=53,918, D=72,848 and X=0. The official validator passed, and a second independent build produced the identical SHA-256 `caf42b0775d695e29859f775c67d42162a92d32655facb202c548b3b59fb220f`.

As an implementation check after freezing this baseline, the official public five-minute scorer reported macroF1 0.6209 and spellF1 0.3256. No parameter was changed in response to that result.

## Validation

The project validator checks:

- exact `frame,label` header;
- exactly 199,319 data rows;
- frame sequence 0 through 199318;
- labels limited to H, A, D and X;
- no blank fields;
- SHA-256 and per-label aggregate counts.

## Known failure modes

- Ball occlusion is confused with dead ball.
- A fixed time window can over-smooth short but real possessions.
- Smart Tagging restart evidence is not incorporated yet.
- The nearest team can be wrong when tracks duplicate, drift, or disappear near a contested ball.
- The first integrated version exposed this failure: missing slots contaminated nearest-distance aggregation and made every frame a no-candidate. The regression fix ignores non-finite slot positions and includes a synthetic test for mixed missing and visible players.

## Compliance statement

No competition video or data was uploaded to a cloud AI service. No manual labels or manual corrections were used. The implementation does not read broadcast data, video, or possession ground truth.
