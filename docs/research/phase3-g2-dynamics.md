# Phase-3 G2 Causal Dynamics

## Scope

The G2 layer adds causal 5-frame and 25-frame differences to the accepted
`P2-FS-0.1` feature table. It does not replace or change the base schema.

Input:

```text
features.csv.gz
metadata.json
```

Output:

```text
g2_features.csv.gz
g2_metadata.json
```

The input `features.csv.gz` must carry the exact P2 schema version
`P2-FS-0.1`; its SHA-256 must match the input metadata. The derivations use only
past rows in the same continuous run and never read `reference.csv.gz`, provider
status/possession, events or ground truth.

## CLI

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m mtah_possession.research.phase2.g2_cli derive-g2 `
  --features outputs\phase2\features\J03WMX-p2\features.csv.gz `
  --output-dir outputs\phase3\g2\J03WMX
```

The input metadata path defaults to the sibling `metadata.json` and can be
overridden with `--metadata`. Existing output directories are rejected unless
`--overwrite` is explicit.

## Definition

The following P2 features receive `delta5__` and `delta25__` columns:

```text
nearest_home_m
nearest_away_m
nearest_team_delta_m
second_home_m
second_away_m
players_within_2m_home
players_within_2m_away
players_within_5m_home
players_within_5m_away
centroid_distance_m
home_width_m
away_width_m
home_depth_m
away_depth_m
ball_home_centroid_delta_m
```

A run starts at input row 0, whenever `game_section` changes, or whenever
`frame_number` is not exactly the previous frame plus one. Differences never
cross these run boundaries. The first `lag` rows of each run are empty, as are
all differences whose current or historical source value is empty.

Output columns are fixed as:

```text
match_id, frame_number, game_section,
delta5__<15 features>,
delta25__<15 features>
```

CSV uses UTF-8/LF and gzip uses `mtime=0`. Outputs are staged and published
atomically. `g2_metadata.json` records input/output hashes, input schema,
feature and lag lists, run boundaries, missing counts, runtime and source
provenance.

This layer is a feature-engineering artifact only. It does not train, select or
score a model.
