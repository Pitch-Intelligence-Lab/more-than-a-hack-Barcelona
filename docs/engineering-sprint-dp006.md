# DP-006 Engineering Package: Generalisation And Dead-Ball

## Status

- Base branch: `dev`
- Base commit: `c4b80a99695fa89f97d9a4a8296f249493bdd278`
- Work branch: `feature/DP-006-generalisation-dead-ball`
- PR #1 is approved and merged into `dev`
- DP-005 is an experimental milestone, not the final submission model

## Objective

Determine whether the possession-state engine can generalise beyond the provided match, improve dead-ball evidence without tuning on the target answer, and establish a defensible selection process for the final submission.

The sprint does not assume DP-006 will become the final model. The final candidate is selected only after comparison under the conditions below.

## Fixed locations

```text
Code repository:       E:\mtah2027-code
Target data root:      E:\mtah2027-data
External data root:    E:\external-data\skillcorner
Generated outputs:     E:\mtah2027-code\outputs
```

External data must remain outside the repository. Do not commit videos, tracking JSON, frames, generated external labels, or dataset archives.

## Required reading

1. `AGENTS.md`
2. `README.md`
3. `docs/engineering-sprint-dp005.md`
4. `docs/decision-log.md`
5. `docs/experiment-log.md`
6. `docs/technical-report.md`
7. `docs/reference-register.md`
8. Existing `src/mtah_possession/` and `tests/`

## Gate A: external data due diligence

No fitting, calibration, or training may start before Gate A passes.

Scope:

- one SkillCorner Open Data match only;
- repository metadata and source files;
- no bulk download of the full collection;
- no body-pose data;
- no video.

Required audit:

1. Record repository URL, exact commit, licence text and retrieval date.
2. Determine whether the licence covers the data files as well as source code.
3. Record the match ID and source file checksums.
4. Parse one tracking record without logging raw player coordinates.
5. Document:
   - frame rate;
   - timestamp units;
   - period boundaries;
   - coordinate units and origin;
   - `possession.group` values;
   - null or missing possession behavior;
   - phases-of-play coverage and semantics;
   - tracking-missing behavior.
6. Determine whether a defensible H/A/D proxy can be constructed.
7. Explicitly classify each no-possession case as D, X, unknown, or excluded. Do not treat absence of a possession ID as automatic D.

Deliverables:

- `docs/external-data-audit.md`;
- `configs/external-skillcorner.json`;
- a synthetic-only adapter test;
- an aggregate audit report containing counts and hashes, not raw coordinates.

Stop condition:

- if the data licence is not demonstrably sufficient, do not download more matches and do not use external data for fitting or calibration;
- continue only with synthetic tests and forced-engine rules if the licence remains unclear.

## Gate B: provider-neutral input adapter

Build a provider-neutral representation that can consume more than the current tactical ATD.

Required concepts:

- match identifier;
- FPS;
- frame count or time range;
- coordinate convention;
- team identities;
- player observations;
- ball observations;
- possession proxy;
- missing-quality flags;
- phase or restart intervals;
- source metadata and checksums.

Requirements:

- use seconds for transition and confirmation parameters;
- convert frames from declared FPS rather than assuming 25 FPS;
- preserve the current tactical path;
- do not hard-code SkillCorner field names in state inference;
- keep the adapter deterministic and testable with small synthetic fixtures.

Acceptance:

- existing tactical tests pass unchanged;
- adapter tests run without real competition data;
- a 10 FPS synthetic sequence and a 25 FPS synthetic sequence with equivalent durations produce equivalent state-transition timing;
- no external field name leaks into the state engine.

## Gate C: proxy target and evaluation

Define how external possession observations map to the target state space.

Required outputs:

- per-frame H/A/D/X proxy mapping;
- a source for every forced D or X;
- counts of mapped, unknown and excluded frames;
- a match-level manifest;
- external metrics by match.

Minimum external metrics:

- possession-segment F1 or the closest valid proxy;
- H/A/D macro F1 if proxy labels are sufficiently comparable;
- state-transition precision/recall or matched-transition count;
- false-D duration;
- missed-dead-ball duration;
- number of team switches;
- mean possession duration;
- deterministic output hash.

Do not claim exact equivalence between SkillCorner possession and the organiser ground truth. The report must state that the external labels are proxy targets.

## Gate D: match-level evaluation split

Split by match before any parameter selection.

Recommended split:

```text
development: rules and parameters
validation: compare frozen candidates
holdout: final generalisation check only
```

Rules:

- no random frame-level split within a match;
- no holdout use during development;
- record the exact match IDs assigned to each split;
- freeze parameter values before evaluating the holdout;
- if only a small number of external matches is usable, preserve at least one untouched holdout.

## Gate E: dead-ball and phase improvements

Only after Gate A passes, implement a separate phase/restart/dead-ball layer.

Inputs may include:

- declared period boundaries;
- kickoff/restart evidence;
- Smart Tagging set-piece and team tags;
- ball and player observation quality;
- ball motion;
- team-control evidence;
- state continuity.

Rules:

- missing ball is not D;
- ball rest is not sufficient by itself to prove D;
- H/A direct changes remain valid;
- D should not be inserted to bridge possession changes;
- output X only for known ungraded gaps or explicitly justified unknown frames;
- no target-video tuning.

Acceptance:

- existing forced-dead and restart tests pass;
- new synthetic tests cover kickoff, throw-in, free kick, corner, goal kick, halftime and emergency stoppage patterns;
- no state cannot leave D when valid restart evidence appears;
- no cleanup removes a confirmed or forced D interval.

## Gate F: candidate comparison and freeze

Candidates:

- baseline DP-001 through DP-004;
- current DP-005;
- DP-006 external-data candidate, if Gate A passes.

Selection criteria:

1. rule and licence compliance;
2. reproducible output;
3. external development and validation performance;
4. no unacceptable regression;
5. demonstrated reduction of a concrete baseline failure;
6. final holdout result;
7. documented limitations.

The highest target smoke score alone is not a selection criterion. The final target run happens only after parameters are frozen.

## Non-goals

- video-pixel processing;
- broadcast timeline alignment;
- training a large vision model;
- training on the provided match;
- using public five-minute labels to choose parameters;
- copying competitor repositories without a licence and compliance review;
- committing external data or generated submissions.

## Required tests

- existing 64 tests;
- provider-neutral adapter tests;
- 10 FPS versus 25 FPS duration equivalence;
- missing possession mapped to the correct D/X/unknown category;
- match-level split integrity;
- forced-dead, kickoff and restart sequences;
- no-D removal by cleanup;
- repeatability and warning-free execution.

## Deliverables

- external-data audit;
- provider-neutral adapter;
- external proxy mapping;
- evaluation harness and match split manifest;
- phase/restart/dead-ball improvements;
- synthetic scenario tests;
- updated README, decision log, experiment log and technical report;
- comparison of baseline, DP-005 and DP-006 under the same valid external protocol;
- final recommendation, not an automatic claim that DP-006 wins.

## Delivery rules

- Work directly in `E:\mtah2027-code`.
- Commit to `feature/DP-006-generalisation-dead-ball`.
- Do not push directly to `main` or `dev`.
- Update the feature branch and return a commit hash and PR link.
- Return only aggregate data, validation results and hashes.
- Do not create a standalone ZIP or patch.

## Handoff template

```text
Task: DP-006
Branch:
Commit:
Pull request:
External data licence:
External match IDs and split:
Proxy mapping:
Tests:
Warning-free tests:
External validation results:
Target smoke result, if run once:
Checksums:
Changed files:
Known limitations:
Recommended final candidate:
Open questions:
```
