# Quality Report

```text
Q1: 4242
Q2: 1961
Q3: 0
Q4: 0
```

SkillCorner has complete 10 FPS tracking but extrapolated coordinates and an
approximately 97% player-identity limitation, so it is Q2 for broad tracking use.
IDSSE's seven tracking/event matches are Q1. StatsBomb is Q1 for event research
and explicitly not tracking. Wyscout is Q2 event data and weak supervision.

No event-only dataset is a frame-level H/A/D/X ground truth.

Pinned revision integrity verification is in
`SOURCE_INTEGRITY_VERIFICATION.json`: all 8,988 StatsBomb files match Git blob
SHA-1 and expected size; all 23 IDSSE files match the pinned tree (including
seven LFS SHA-256 objects); SkillCorner has 20 real tracking bodies and zero LFS
pointers; Wyscout contains 1,941 match JSON files.

Known source-level anomalies:

- StatsBomb has 274 event/lineup files absent from `competitions.json`; they are
  inventoried with unknown competition/season rather than inferred.
- StatsBomb optional `three-sixty/3845506.json` is malformed in the official
  pinned Git blob (NUL corruption). The raw bytes match the official Git object
  and remain unchanged; event quality is unaffected because 360 is optional.
- Five zero-byte official files are legitimate empty `__init__.py` or auxiliary
  README placeholders, not data payloads.
