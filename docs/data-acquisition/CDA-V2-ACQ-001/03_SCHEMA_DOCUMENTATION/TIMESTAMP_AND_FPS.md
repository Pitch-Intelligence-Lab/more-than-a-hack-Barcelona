# Timestamp and FPS

| Source | Timing |
|---|---|
| SkillCorner | 10 FPS; integer frame, timestamp and period |
| IDSSE | 25 FPS (0.04 s frame cadence); frame number and ISO EventTime |
| StatsBomb | Event minute/second/timestamp; no fixed frame rate |
| Wyscout | Event `matchPeriod` and seconds within period; no fixed frame rate |

Only SkillCorner and IDSSE contain continuous tracking timelines in this package.
