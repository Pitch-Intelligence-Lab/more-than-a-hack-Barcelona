# One-Match 128057 Quality Report

## Status

```text
STAGE1_FAIL
```

The selected 23-file scope totals `12,823,435,353` bytes. Stage 1 contains 20
non-video files (`5,768,542,573` bytes); Stage 2 contains 3 video files
(`7,054,892,780` bytes).

The HF gate preflight passed with an authenticated token and returned HTTP 200
for the gated ball file. Five Stage 1 files were downloaded completely:
two ball NPZ files and the BAS JSON plus `CHANGES_v1_1.md` and
`CHANGES_v1_2.md`. The first GSR file remains an unaccepted `.part` file and
the remaining Stage 1 files were not downloaded; Stage 1 therefore fails.

## Available data

- Complete downloaded ball NPZ files and BAS events.
- Downloaded `CHANGES_v1_1.md` and `CHANGES_v1_2.md`.
- Public pinned-tree preflight metadata.

## Available labels

```text
NONE payload-verified
```

## Usable supervision for H/A/D

```text
NONE
```

Ball NPZ structure and BAS event fields were inspected. GSR was not accepted or
parsed; raw events, MOT, calibration files and video were not acquired.

Ball observations:

```text
First half: 67,625 unique frames; status counts {0:19715, 1:17356, 2:25216, 3:5338}
Second half: 70,350 unique frames; status counts {0:22294, 1:20575, 2:23846, 3:3635}
```

BAS observations:

```text
1,932 actions; 12 labels; left=1,023 right=909; missing player_id=9
```

The shipped BAS action objects do not expose a visibility field in the sampled
schema. GSR/ball/video temporal alignment cannot be established.

## Not available

- 14 remaining Stage 1 non-video files;
- complete first and second GSR JSON files;
- 3 Stage 2 video files;
- GSR streaming schema/quality audit;
- ball NPZ state/coordinate/alignment audit;
- BAS/raw event class/team/actor audit;
- raw calibration/map/nodes/tracker audit;
- video codec/FPS/duration/decode checks;
- cross-source timing and frame alignment;
- complete Stage 1 local SHA-256 manifest and decoder performance metrics.

## Licence and truth boundary

SoccerTrack data is CC BY 4.0 and its code is MIT; access remains gated.
Afriskaut remains deferred and Metrica remains
`LICENSE_UNRESOLVED / ACQUISITION_DEFERRED`.

BAS events, ball tracks, video evidence, raw events and any future external
labels are not H/A/D/X controlled-possession truth. No official frame-level
H/A/D/X truth has been established. Four ball status classes were observed;
their semantics must not be equated with H/A/D/X truth.

## Recommendation

Do not proceed to more matches or model/feature work from this failed sample.
Resume Stage 1 acquisition only after the network/download issue is resolved,
then rerun all integrity and parsing checks before Stage 2 video acquisition.
