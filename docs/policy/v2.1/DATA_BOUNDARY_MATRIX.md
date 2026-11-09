# DP-006 Policy v2.1 P0 Data-Boundary Matrix

**Baseline:** `b6f61a475600498ae7993b352ecb8b94e19c77ec`

## DATA_BOUNDARY_MATRIX

| object | current_fields | prediction_allowed | training_target | evaluation_reference | phase_input | future_leakage_risk | required_action |
|---|---|---|---|---|---|---|---|
| match metadata | match ID, fps, coordinate convention, team IDs/names, pitch | yes | no | yes for grouping/context | no | low when frozen before prediction | copy only metadata into `PredictionSource` |
| tracking geometry | slot positions/detection, ball positions/detection, frame presence | yes | no | structural reference | no | none for current frame geometry | retain in `PredictionSource` |
| observation quality | detected/extrapolated/missing source quality | yes | no | quality audit | no | low | retain in `PredictionSource` |
| periods | declared half-open frame spans | yes | no | evaluation grouping | no | high if future period boundaries leak beyond game-time availability | retain only declared periods; validate temporal availability |
| possession side/status | possession group-derived H/A/missing/unrecognized | no | yes if authorized | yes | no | direct label leakage | move exclusively to `EvaluationReference` |
| possession player ID | player possession reference | no | auxiliary target if authorized | diagnostic | no | direct label leakage | never expose in prediction projection |
| phases | possession phase intervals/type/team | only approved/temporally evidenced phase features | auxiliary target if authorized | evaluation phase truth/proxy | yes | semantic/future leakage | load only when phase candidate declares use; reference copy only after prediction |
| evaluation target | proxy H/A/D/X labels | no | if target training explicitly separate | yes | phase-dependent | direct answer leakage | construct after prediction hash fixed |
| source checksums | license/readme/tracking/phases/match hashes | yes as provenance | no | provenance | no | none | preserve same-snapshot identity across projections |
| source identity | revision, teams, pitch, files, checksums, snapshot digest | yes as metadata/provenance | no | provenance | no | none | do not rewrite; compare both projections |
| future event outcome | future phase/event result fields | no | no | no before settlement | no | future leakage | omit from both projections unless explicitly available at prediction time |

## PredictionSource projection

Allowed:

```text
match metadata
periods
tracking geometry
observation quality
approved phase/event evidence with temporal metadata
source identity/checksums
```

Forbidden:

```text
possession group/player reference
evaluation reference labels
future event outcomes
```

## EvaluationReference projection

Allowed after prediction hash:

```text
possession group/player evaluation fields
evaluation phase truth
proxy mapping evidence
reference identity tied to the same snapshot/checksums
```

## Freeze impact

Source Identity schema and checksum fields remain unchanged. The two views are
derived from one immutable manifest/file snapshot. No Holdout ledger migration or
DP-005 algorithm change is required.
