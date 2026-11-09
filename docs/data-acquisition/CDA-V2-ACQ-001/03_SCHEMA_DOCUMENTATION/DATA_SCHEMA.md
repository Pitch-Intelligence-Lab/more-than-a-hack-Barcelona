# CDA-v2 Data Schema

## Core rule

Tracking, event, proxy and evaluation-reference data are different evidence classes.
Event-only datasets are never described as frame-level H/A/D/X truth.

## Match inventory columns

`MATCH_INVENTORY.csv` records source revision, match ID, competition/season, data type,
FPS, coordinate convention, timing fields, possession/phase/dead-ball fields, Q1-Q4,
license status and hashes for source files.

## Source summaries

SkillCorner: JSONL tracking at 10 FPS plus provider CSV events and phase intervals.

IDSSE: DFL XML position and event streams at 25 FPS.

StatsBomb: event and lineup JSON; 360 freeze-frame JSON exists for a subset. It is not tracking.

Wyscout: processed event JSON at event timestamps. It is not tracking.
