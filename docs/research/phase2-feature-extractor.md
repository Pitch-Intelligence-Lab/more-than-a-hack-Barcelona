# Phase-2 IDSSE Feature Extractor

## Scope

`MTAH-PHASE2-FEATURE-EXTRACTOR-001` implements the approved `G0` geometry and
`G1` team-shape feature families for one IDSSE match at a time.

The extractor does not train, tune, select a model or score a lockbox. It does
not use event coordinates, provider possession/status inside `features`, public
ground truth or competition video.

## Input package

The authorized source package is:

```text
E:\mtah2027-data\CDA-V2-ACQ-001\package
```

The extractor resolves the selected match through the canonical
`04_QUALITY_ASSESSMENT/FILE_INVENTORY.csv` and verifies metadata, tracking and
event file sizes and SHA-256 values before extraction.

## Coordinate contracts

```text
tracking: centre-origin metres, approximately X=-52.5..52.5, Y=-34..34
event: pitch-corner metres, X=0..105, Y=0..68
```

Tracking and event coordinates are never mixed. The event conversion helper
subtracts half the pitch dimensions explicitly; event coordinates are not used
by the v0.1 feature table.

## Streaming join

The positions XML is processed twice with an Expat event parser:

1. read and validate the ball FrameSet timeline and provider reference values;
2. stream home/away player FrameSets into compact NumPy per-frame aggregates.

The ball and player streams are joined by `Frame@N`, not XML element order.
Every half is validated independently. The extractor records the single
half-boundary frame jump and preserves one row per ball frame.

## Outputs

### `features.csv.gz`

Contains the fixed `P2-FS-0.1` geometry/team-shape schema. It does not contain
`BallStatus`, `BallPossession`, provider speed, possession history, speed,
acceleration, touch, restart, direction, blackout or identity features.

If the ball lies outside the tracking envelope, ball-dependent fields are empty
while team shape and centroid distance remain available. Player coordinates are
not clipped or deleted; out-of-envelope rows are counted in `metadata.json`.

### `reference.csv.gz`

Contains only:

```text
match_id
frame_number
provider_alive
provider_home_possession
```

The mapping is fail-closed:

```text
BallStatus: 1=true, 0=false
BallPossession: 1=true, 2=false
```

### `metadata.json`

Records source paths and hashes, coordinate contract, FPS, frame counts, missing
and invalid counts, tracked-player distributions, runtime, environment, output
hashes and source provenance:

```text
repository_head: current git HEAD
implementation_commit: last commit touching src/mtah_possession/research/phase2
  or configs/research/phase2
source_tree_dirty: true when implementation or phase2 test paths are dirty
code_commit: compatibility alias for repository_head
```

If git provenance cannot be read reliably, `repository_head` and
`implementation_commit` are `unavailable`, and `source_tree_dirty` is `true`.
`code_commit` retains the repository-head alias for older receipts but is not the
unique implementation identity.

### `split_manifest.json`

Generated from
`configs/research/phase2/idss_split.json`. It records the five development and
two operational-lockbox matches, source identity and the honest historical
exposure statement. Frame-level random splitting is disabled.

## Determinism and publication

CSV uses UTF-8 and LF. Gzip uses `mtime=0`. Repeating the same extraction must
produce byte-identical `features.csv.gz`, `reference.csv.gz` and
`split_manifest.json`.

Artifacts are staged first and published only after all four output files are
complete. Existing output directories are rejected unless `--overwrite` is
explicitly supplied.

## Commands

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m mtah_possession.research.phase2.cli extract-idss `
  --package-root E:\mtah2027-data\CDA-V2-ACQ-001\package `
  --match-id DFL-MAT-J03WMX `
  --output-dir outputs\phase2\features\J03WMX

.\.venv\Scripts\python.exe -m mtah_possession.research.phase2.cli smoke-idss `
  --package-root E:\mtah2027-data\CDA-V2-ACQ-001\package
```

## Known limitations

- IDSSE has no independent ball-visibility mask.
- Provider status and possession are research references, not official
  frame-level H/A/D/X truth.
- The operational lockbox is not pristine: aggregate tracking, events and
  labels were inspected before the split was frozen.
- The seven matches contain only two competitions and one season.
- This extractor does not establish model performance or Phase-2 acceptance.
