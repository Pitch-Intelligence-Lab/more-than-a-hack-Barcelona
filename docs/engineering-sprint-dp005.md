# DP-005 Engineering Sprint

## Objective

Turn the verified DP-001 through DP-004 nearest-player baseline into a configurable temporal possession-state engine without using the provided match video or possession ground truth for training or tuning.

## Fixed workspace and delivery

- Work in `E:\mtah2027-code`.
- Start from `origin/dev` on `feature/DP-005-general-state-machine`.
- Read competition data only through `MTAH_DATA_DIR`.
- Commit and push the feature branch. Do not deliver a ZIP or patch.
- Do not push directly to `main` or `dev`.

## Required scope

### 1. General configuration

- Make FPS, frame count, pitch dimensions, match identifier and optional assets configurable.
- Measure durations in seconds internally.
- Keep the final target contract at 199,319 rows and frame range 0 through 199318.
- Preserve support for the current tactical ATD input.

### 2. Quality-aware observations

Add explicit states for:

- observed ball;
- interpolated ball;
- missing ball.

When ball and player observations are incomplete, use only visible player slots. Missing observations may weaken evidence but must not by themselves force D.

### 3. Evidence features

Implement small, independently testable features:

- nearest-team distance;
- visible near-player vote;
- ball-motion and rest duration;
- restart-zone proximity;
- simple reachability estimate where its assumptions are explicit;
- optional Smart Tagging prior.

Every feature must have a defined missing-value policy and source tag.

### 4. State engine

- Support H, A and D as graded states.
- Use X only for known ungraded frames.
- Permit direct H to A and A to H transitions.
- Permit H to D and D to H/A transitions.
- Never require a synthetic D interval merely to change teams.
- Keep pass-by and long-gap artifact guards disabled by default until validated.

### 5. Structural cleanup

- Remove very short flicker only with an explicit, tested duration.
- Preserve deliberate short possessions unless evidence justifies removal.
- Keep cleanup separate from the scoring model.

### 6. Output and health report

Report at least:

- row count;
- label counts;
- number of H/A/D segments;
- mean, shortest and longest segment duration;
- observed/interpolated/missing ball counts;
- number of state transitions by type;
- input and output SHA-256.

## Test requirements

Add deterministic synthetic tests for:

1. brief ball occlusion inside one possession;
2. long missing-ball gap without dead-ball evidence;
3. direct H to A possession change;
4. direct A to H possession change;
5. dead-ball interval and restart;
6. ball passing near a player at speed without a possession change;
7. short flicker absorbed without merging distinct real segments;
8. ungraded frames emitted as X;
9. missing slots do not erase visible team traces;
10. identical input produces byte-identical output.

All existing tests must continue to pass.

## Data and rule constraints

- Do not read video pixels or broadcast in this sprint.
- Do not use or inspect provided possession ground truth to choose parameters.
- Do not use the public five-minute ground truth to compare design variants.
- Public scoring may be run once after the implementation is frozen, as a smoke test.
- Do not train or tune on any provided match asset.
- Do not hand-label or manually alter frames.

## Deliverables

- Code changes under `src/mtah_possession/`.
- Configuration with parameter-source metadata.
- Unit and integration tests.
- Updated decision, experiment and technical documents.
- One locally generated but untracked target CSV.
- Branch commit and pull-request summary containing test results and hashes.

## Acceptance gate

The sprint is not complete until:

1. all tests and Ruff checks pass;
2. the target output has 199,319 valid rows;
3. the project and official validators pass;
4. repeat generation yields the same SHA-256;
5. repository scans find no competition data;
6. the previous DP-001 through DP-004 output remains available as a fallback;
7. the technical report records every changed rule and parameter source.
