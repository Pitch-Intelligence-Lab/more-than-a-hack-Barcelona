# One-Match 128057 Quality Report

## Status

```text
BLOCKED
```

The selected 23-file scope totals `12,823,435,353` bytes. Stage 1 contains 20
non-video files (`5,768,542,573` bytes); Stage 2 contains 3 video files
(`7,054,892,780` bytes).

No selected payload file was downloaded in this run. The automation environment
has no approved HF token, and the gated file probe returned HTTP 401. The
browser download was not reused as an automation credential.

## Available data

- The selected remote manifest supplied by the task package.
- Existing public preflight metadata for the pinned SoccerTrack tree.

## Available labels

```text
NONE payload-verified
```

## Usable supervision for H/A/D

```text
NONE
```

No GSR, ball, BAS, raw event, MOT or video file was parsed. No semantic label,
frame alignment, tracking identity, visibility or temporal claim is established
by this run.

## Not available

- 20 Stage 1 non-video files;
- 3 Stage 2 video files;
- GSR streaming schema/quality audit;
- ball NPZ state/coordinate/alignment audit;
- BAS/raw event class/team/actor audit;
- raw calibration/map/nodes/tracker audit;
- video codec/FPS/duration/decode checks;
- cross-source timing and frame alignment;
- local SHA-256 hashes and decoder performance metrics.

## Licence and truth boundary

SoccerTrack data is CC BY 4.0 and its code is MIT; access remains gated.
Afriskaut remains deferred and Metrica remains
`LICENSE_UNRESOLVED / ACQUISITION_DEFERRED`.

BAS events, ball tracks, video evidence, raw events and any future external
labels are not H/A/D/X controlled-possession truth. No official frame-level
H/A/D/X truth has been established.

## Recommendation

Do not proceed to more matches or model/feature work from this blocked sample.
Resume only after an approved HF token or approved staged files become
available, then rerun all Stage 1 integrity/parsing checks before Stage 2 video
acquisition.
