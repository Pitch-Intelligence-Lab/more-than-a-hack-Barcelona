# SoccerTrack v2 Field Audit

## Status

```text
REMOTE TREE: VERIFIED
PAYLOAD DOWNLOAD: BLOCKED
FIELD-LEVEL DATA INSPECTION: NOT PERFORMED
REASON: Hugging Face gate/token check failed; gated file returned HTTP 401
```

## Verified remote identity

```text
Dataset: atomscott/soccertrack-v2
Revision: v1.2
Resolved SHA: 325bd4c57ee8e135ab652f3921d274526ada496b
Tree entries: 244
File entries: 197
Tree bytes: 144,847,069,949
```

Folder totals recorded from the pinned public tree:

```text
videos: 82,680,552,357
gsr:    55,953,634,621
mot:     3,592,616,363
raw:     2,613,085,912
bas:         4,559,863
ball:        2,596,443
```

These are remote-tree facts, not local-file measurements.

## Required field checks

The shipped GSR/BAS/ball data were not downloaded, so no field values were
inspected. The expected audit fields are recorded as `NOT_VERIFIED_BLOCKED` in
`SOCCERTRACK_FIELD_AUDIT.csv`:

- GSR image/frame identifier, pitch x/y, player/track identity, jersey, role and
  team side;
- BAS time/half, class, team, actor identity and visibility;
- ball-track provenance and interpolation status;
- presence or absence of H/A/D/X controlled-possession truth.

No claim is made that these fields are available in shipped data. The 10-match,
20-half count and 12-class BAS documentation remain documentation claims until
the gated payload is acquired and audited.

## GSR schema warning

The supplied audit package flags a documented-versus-shipped GSR schema mismatch.
Because no GSR file was downloaded, this run cannot independently confirm the
mismatch or quantify its impact. No naive whole-file JSON load is permitted in a
future attempt; the next acquisition must use streaming or bounded parsing.

## Ball track boundary

The ball track must not be described as raw per-frame measurement. It is
expected to be anchored/interpolated reconstruction. This claim also remains
unverified until the gated payload is available.

## Label boundary

SoccerTrack must not be represented as providing official H/A/D/X controlled
possession truth. Event labels, BAS events and interpolated ball positions are
separate evidence and require a future task-specific review.
