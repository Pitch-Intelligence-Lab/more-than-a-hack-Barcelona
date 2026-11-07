# External Data Audit: SkillCorner Open Data

**Status:** Gate A passed for one-match local research evaluation

**Audit date:** 2026-11-05

## Source and licence

- Repository: <https://github.com/SkillCorner/opendata>
- Audited commit: `4340d274572876239c154c90bc507a9b3250a656`
- Commit timestamp: 2026-09-14
- Repository licence: MIT
- Licence SHA-256: `3384cc66ffd008209759af5e6328677eabded72756fb1f56f4f82e68e9b3c6eb`
- README SHA-256: `c09886c6359e5f7ff3bfd71a653510caf2f674d238ca79219aa1ec9ebe6f4428`

The repository root contains an MIT licence, GitHub reports the repository licence as MIT, and the official README explicitly states that the repository contains the data and that the data has been open sourced. No separate data licence file was found.

This is sufficient for the internal research evaluation performed here, but the licence wording refers to software and associated documentation. The team must not redistribute the external data or claim additional data rights beyond the repository statement. The data remains outside Git at `E:\external-data\skillcorner`.

## Audited match

- Match ID: `2017461`
- Competition: A-League 2024/25
- Match: Melbourne Victory FC (`868`) vs Auckland FC (`4177`)
- Retrieval scope: one match only; no body-pose data, video or full collection
- Rate: 10 FPS
- Tracking frames: 71,451, frame 0 through 71450
- Declared periods:
  - Period 1: frames 2510 through 30209, 27,700 declared frames
  - Period 2: frames 39670 through 70419, 30,750 declared frames
  - Frames outside periods: 13,001, mapped to X
- Pitch: 105 x 68 m
- Coordinate convention: metres, centre origin; x follows the long axis

## File checksums

| Role | Bytes | SHA-256 |
|---|---:|---|
| tracking extrapolated JSONL | 89,543,442 | `59cfa5588efee041da439f44df5b5b92f2b7305571dc831164e3d05f7415787a` |
| phases of play CSV | 118,313 | `5331495ecea48056df56dc843864bf36f366f7bca3898d82273eba7a3a54eba5` |
| match metadata JSON | 28,545 | `db27759bf734dc8e3d9e56f047965cc7c74833bc3d0345ee3821ab97681ce4b9` |

## Tracking structure

The first record was parsed in memory without logging player coordinates. Its aggregate schema is:

- frame integer
- timestamp string or null
- period integer or null
- ball data object or null
- possession object with player ID and group
- image-corner array
- player-observation array

Across the full match:

- 71,451 tracking rows and 71,451 present frames
- Timestamps on all 58,452 in-period records use `HH:MM:SS.xx` strings, with 0.1-second increments
- 12,999 outside-period records have null timestamps
- 888,888 player observations: 454,715 detected and 434,173 extrapolated
- 40,404 ball observations with finite coordinates: 31,875 detected and 8,529 present but not detected
- 0 unknown player IDs after mapping the tracking `player_id` to the public roster `id`

The adapter uses detected positions only. Extrapolated positions remain represented in the external source but are excluded from the state-engine input, which is the conservative choice.

## Possession observations

Observed `possession.group` values:

- `home team`: 17,796
- `away team`: 11,092
- null: 42,563
- unrecognized: 0

The group maps to H/A. A null group is not automatically D.

## Phases of play

- 433 phase rows
- 28,610 frames covered by at least one phase
- Phase intervals use half-open `[frame_start, frame_end)` boundaries
- Phases are documented as in-play tactical phases only, with no phase when the ball is out of play
- 29,840 frames inside declared periods are not covered by a phase

Phase gaps and possession observations do not align exactly: 1,234 phase-gap frames still have an explicit possession group. Therefore, using every phase gap as forced D would create false D. This is reported as a candidate limitation rather than silently assuming equivalence.

## H/A/D/X proxy mapping

The external target is a diagnostic proxy, not organiser ground truth.

| Case | Proxy | Source |
|---|---|---|
| `possession.group=home team` | H | `possession_group_home` |
| `possession.group=away team` | A | `possession_group_away` |
| No row for a frame | X | `missing_tracking_frame` |
| Outside declared period | X | `outside_declared_period` |
| Missing possession inside an active phase | X | `missing_possession_inside_phase` |
| Missing possession with no active phase inside a period | D | `no_possession_and_no_phase` |
| Unrecognized possession group | X | `unrecognized_possession_group` |

Resulting counts:

- H: 17,796
- A: 11,092
- D: 28,606
- X: 13,957
  - outside periods: 13,001
  - missing possession inside phases: 956

## Match-level split

Only one match was downloaded under Gate A:

- Development: `2017461`
- Validation: empty
- Holdout: empty
- Status: `diagnostic_only`

No random frame-level split was used. Because no untouched validation or holdout match exists, this audit cannot establish generalisation and cannot alone select the final competition candidate.

## Aggregate reports

The untracked local reports are:

- `outputs/external-data-audit.json`
- `outputs/external-dp006-development.json`

They contain counts, metrics and hashes only. Raw external observations, coordinates and generated labels remain outside Git.
