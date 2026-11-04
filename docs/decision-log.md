# Decision Log

Record durable project decisions here. Do not record private competition data.

## D-001: Use tactical data as the first path

- Date: 2026-11-04
- Status: accepted
- Decision: Build on the tactical timeline first.
- Reason: Submission rows are indexed to tactical video; broadcast is optional and unsynchronised.

## D-002: Keep code and data in separate roots

- Date: 2026-11-04
- Status: accepted
- Decision: Open code tools only on the code repository and point code to data through `MTAH_DATA_DIR`.
- Reason: Prevent accidental upload, indexing or git tracking of competition data.

## D-003: Do not train or tune on the provided match

- Date: 2026-11-04
- Status: accepted
- Decision: Any learned model or tuned parameter must use appropriately licensed external data.
- Reason: Organiser clarification dated 2026-11-03 takes precedence.

## D-004: Defer video and broadcast

- Date: 2026-11-04
- Status: accepted
- Decision: First implementation uses tactical tracking and Smart Tagging only.
- Reason: Reduce memory, compute and compliance risk while establishing a valid baseline.

## D-005: Automated checks only

- Date: 2026-11-04
- Status: accepted
- Decision: Do not compare generated labels with the video by hand.
- Reason: Explicitly prohibited by the latest organiser clarification.
