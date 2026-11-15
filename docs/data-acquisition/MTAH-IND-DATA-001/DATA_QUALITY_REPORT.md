# Independent Validation Data Quality Report

## Executive status

```text
ACQUISITION STATUS: BLOCKED
BLOCKER: Hugging Face dataset gate/token unavailable
```

The pinned SoccerTrack v2 remote tree was readable and matched the supplied
baseline:

```text
244 tree entries
197 files
144,847,069,949 bytes
resolved SHA 325bd4c57ee8e135ab652f3921d274526ada496b
```

However, the gated ball probe returned HTTP 401 and no Hugging Face token was
present. The public README returned HTTP 200. No unverified mirror was used.

## Available data

- Public dataset metadata and pinned tree metadata.
- Public README status.
- Source register and licence statements supplied by the PM package.

## Available labels

No payload-verified labels are available in this run.

## Usable supervision for our H/A/D task

```text
NONE
```

The remote documentation may describe tracking, BAS events and ball tracks, but
this run did not verify shipped fields or label semantics. BAS, ball tracks,
Metrica events and Afriskaut events must not be treated as H/A/D/X truth.

## Not available

- SoccerTrack GSR, MOT, BAS, ball, raw and video payloads.
- SoccerTrack field-level schema inspection.
- Video FPS, duration, decodability and 10-match/20-half file confirmation.
- GSR streaming parse and documented-versus-shipped schema comparison.
- Afriskaut ZIP and Event Map review.
- Any H/A/D/X controlled-possession truth.

## Licence restrictions

- SoccerTrack dataset: CC BY 4.0, gated access; code MIT.
- Afriskaut: Apache-2.0; acquisition deferred by the task's dependency order.
- Metrica: `LICENSE_UNRESOLVED`, acquisition deferred; no data acquired.

Public access does not grant training, publication or redistribution rights.

## Quality conclusion

No data-quality claims can be made for the blocked payloads. The only verified
quality facts are remote tree identity/counts, public metadata visibility, gated
file denial and the absence of a token in this environment.
