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

## D-006: Notion is management-only

- Date: 2026-11-05
- Status: accepted
- Decision: Use Notion for tasks, owners, deadlines and blockers; keep engineering evidence in GitHub and competition data local.
- Reason: A readable task board is useful, but it must not become a second or less-secure data store.

## D-007: Codex leads; Cursor and DeepSeek are optional

- Date: 2026-11-05
- Status: accepted
- Decision: Use Codex as the primary engineering and integration environment. Keep Cursor as an optional editor without paying for a model upgrade at this stage. Use DeepSeek only for scoped subagent tasks with explicit review.
- Reason: The project needs working code, tests and a reproducible submission more than another tool subscription.
