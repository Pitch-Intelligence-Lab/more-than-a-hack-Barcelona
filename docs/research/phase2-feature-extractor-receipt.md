# CDA Phase-2 Feature Extractor Engineer Receipt

## 1. Delivery identity

```yaml
task_id: MTAH-PHASE2-FEATURE-EXTRACTOR-001
repository: Pitch-Intelligence-Lab/more-than-a-hack-Barcelona
branch: feature/MTAH-PHASE2-FEATURE-EXTRACTOR-001
baseline: c4b80a99695fa89f97d9a4a8296f249493bdd278
implementation_commit: d19e7c4ad91163bb4e3bd9e994c58aa1dd8a573b
test_regression_commit: 338baacb1c4702d8b414950199de5b14705c1573
pull_request: https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona/pull/11
worktree_clean_after_finalization: true
merge: withheld
training: not started
phase2_acceptance: pending PM independent review
```

The documentation commit is the final commit containing this receipt. It changes
no implementation logic after the two-match production run.

## 2. Implemented scope

```text
feature families: G0 geometry + G1 team shape
CLI: extract-idss and smoke-idss
runner: Expat streaming XML parser with compact NumPy frame aggregates
output schema: P2-FS-0.1
split manifest: checked-in match-level development / operational_lockbox split
```

The extractor joins ball and player data by `Frame@N`, not XML element order.
It preserves both halves and their independent player FrameSets, rejects
non-contiguous ball frames within a half, and records the single half-boundary
frame jump.

Provider `BallStatus` and `BallPossession` occur only in `reference.csv.gz`.
`features.csv.gz` contains no provider status, provider possession, speed,
acceleration, touch, restart, direction, blackout or identity features.

## 3. Validation

```text
pytest -q -W error: 78 passed
ruff check .: PASS
ruff format --check .: PASS
seven-match inventory/metadata/file identity smoke: PASS
features/reference frame alignment: PASS for both full matches
repeated gzip SHA-256: identical
```

New synthetic regression coverage includes:

- ball/home/away metadata join and negative tracking X;
- distance, 2 m/5 m counts and second-nearest behavior;
- invalid ball geometry masking only ball-dependent fields;
- same player IDs across independent half FrameSets;
- strict contiguous ball ordering within each half;
- provider reference mapping and fail-closed invalid values;
- exact home/away swap and signed-delta symmetry;
- marker attributes not filtering players;
- event coordinate conversion;
- match-level split configuration;
- fixed gzip mtime and byte-identical repeated output;
- overwrite refusal without `--overwrite`.

## 4. Full real-data runs

Both runs used:

```text
Package: E:\mtah2027-data\CDA-V2-ACQ-001\package
Code commit in metadata: d19e7c4ad91163bb4e3bd9e994c58aa1dd8a573b
Inventory SHA-256: 1db6ee74491b6f385fb63198f71a904e070471f0bac1dbd91d5817a3c0ef63cd
```

| Match | Frames / rows | Empty nearest | Invalid ball geometry | Home tracked | Away tracked | Elapsed | Peak memory |
|---|---:|---:|---:|---|---|---:|---:|
| `DFL-MAT-J03WMX` | 145,967 | 6,750 | 6,750 | 11 for all frames | 11 for all frames | 44.903 s | 593,248,256 bytes |
| `DFL-MAT-J03WOH` | 137,214 | 1,421 | 1,421 | 11 for all frames | 11 for all frames | 39.860 s | 574,017,536 bytes |

`DFL-MAT-J03WMX` also recorded 9,274 player coordinates outside the nominal
tracking envelope. They were counted but retained in team-shape calculations.
`DFL-MAT-J03WOH` recorded 6,992 such rows.

## 5. Output identities

| Match | Artifact | Rows | Bytes | SHA-256 |
|---|---|---:|---:|---|
| `J03WMX` | `features.csv.gz` | 145,967 | 9,110,663 | `bf6b65ea6237d57101931f8d59b4f2c36af24e982ff76da4662214697c05918a` |
| `J03WMX` | `reference.csv.gz` | 145,967 | 359,503 | `ad56bb80e52618779c019b258f31880791a80edd785eb5c7aa6f6eab49b28677` |
| `J03WMX` | `metadata.json` | 1 | 3,049 | `4a863619d92bdf7c452d45585ecaaede96bb15e7c667b6a477f9f70f17b17029` |
| `J03WMX` | `split_manifest.json` | 1 | 7,393 | `94af926d479176546043bf270c06a1610e27441e58a8e1253eca3ad55e1b0708` |
| `J03WOH` | `features.csv.gz` | 137,214 | 8,658,798 | `26145906e483bcfebbb1e2b5873fa760093f9e3802d1d0fd2ad7a9e2cd80f97f` |
| `J03WOH` | `reference.csv.gz` | 137,214 | 335,379 | `5d799aeaa3fd0150c034f18f7ea2c0ceb40b522f5f96e90c7b994c44482a3fd7` |
| `J03WOH` | `metadata.json` | 1 | 3,052 | `232e00de29bc083802cf701a6c2909fdd73ede3f521fe9bc9de49eb74cd8b1cf` |
| `J03WOH` | `split_manifest.json` | 1 | 7,393 | `94af926d479176546043bf270c06a1610e27441e58a8e1253eca3ad55e1b0708` |

The outputs remain under ignored `outputs/phase2/features/`; no source or
derived match rows are committed.

## 6. Five-match smoke checks

Each listed match passed metadata parsing plus actual file size/SHA-256 checks
for metadata, tracking and event files against the canonical inventory:

| Match | Split role | Result |
|---|---|---|
| `DFL-MAT-J03WOY` | development | PASS |
| `DFL-MAT-J03WPY` | development | PASS |
| `DFL-MAT-J03WQQ` | development | PASS |
| `DFL-MAT-J03WN1` | operational_lockbox | PASS |
| `DFL-MAT-J03WR9` | operational_lockbox | PASS |

## 7. Schema

`features.csv.gz` has 28 columns in fixed order:

```text
match_id, frame_number, timestamp_utc, game_section,
home_team_id, away_team_id, home_tracked_n, away_tracked_n,
ball_geometry_valid, nearest_home_m, nearest_away_m,
nearest_team_delta_m, second_home_m, second_away_m,
players_within_2m_home, players_within_2m_away,
players_within_5m_home, players_within_5m_away,
home_centroid_x, home_centroid_y, away_centroid_x, away_centroid_y,
centroid_distance_m, home_width_m, away_width_m,
home_depth_m, away_depth_m, ball_home_centroid_delta_m
```

`reference.csv.gz` has exactly:

```text
match_id, frame_number, provider_alive, provider_home_possession
```

## 8. Known limitations

- IDSSE has no independent ball-visibility mask; coordinate presence is not
  treated as a visibility signal.
- Provider status and possession are research references, not official
  frame-level H/A/D/X truth.
- The lockbox is operational rather than pristine because aggregate tracking,
  event structure and labels were inspected before the split was frozen.
- Seven matches cover two competitions and one season; five 2. Bundesliga
  matches include the same club.
- This delivery establishes feature-extraction correctness only. It does not
  establish model quality or Phase-2 acceptance.

## 9. Decision requested

```text
implementation complete for PM review
merge: withheld
training: not started
real-data research: HOLD
phase2 acceptance: pending PM independent review
```
