---
pretty_name: "IDSSE — Integrated Dataset of Synchronized Spatiotemporal and Event Data in Elite Soccer"
license: cc-by-4.0
tags:
  - sports
  - soccer
  - football
  - tracking-data
  - event-data
  - geospatial
  - timeseries
  - bundesliga
task_categories:
  - other
---

# IDSSE — Sportec Open Tracking & Event Data

Mirror of the IDSSE dataset, originally hosted on Figshare, re-hosted here for stable and fast access via [kloppy](https://github.com/PySport/kloppy) and related tools.

## Contents

7 complete matches from the German Bundesliga season 2022/23 (1st and 2nd division), collected by [Sportec Solutions](https://sportec-solutions.de) using TRACAB optical tracking technology.

Each match includes:
- **Tracking data** — position of all players and the ball at 25 fps
- **Event data** — synchronized match events (passes, shots, duels, …)
- **Metadata** — teams, players, pitch dimensions

## Load with kloppy

```python
from kloppy import sportec

tracking = sportec.load_open_tracking_data(match_id="J03WPY")
events = sportec.load_open_event_data(match_id="J03WPY")
```

Available match IDs: `J03WPY`, `J03WMX`, `J03WN1`, `J03WOH`, `J03WOY`, `J03WPF`, `J03WQF`

## Original source

| | |
|---|---|
| **Figshare DOI** | https://doi.org/10.6084/m9.figshare.28196177 |
| **Paper DOI** | https://doi.org/10.1038/s41597-025-04505-y |
| **Data owner** | Deutsche Fußball Liga (DFL) |
| **License** | [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/) |

## Citation

```bibtex
@article{bassek2025idsse,
  title   = {An integrated dataset of synchronized spatiotemporal and event data in elite soccer},
  author  = {Bassek, M. and others},
  journal = {Scientific Data},
  volume  = {12},
  number  = {1},
  pages   = {195},
  year    = {2025},
  doi     = {10.1038/s41597-025-04505-y}
}
```
