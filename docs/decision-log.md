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

## D-008: Milestone 1 uses tactical ATD only

- Date: 2026-11-05
- Status: accepted for milestone 1
- Decision: DP-001 through DP-004 use tactical ATD metadata and raw tracking only.
- Reason: The tactical timeline matches the submission. Broadcast, video, homography and Smart Tagging add risks that are unnecessary for the first working baseline.

## D-009: Nearest-player distance ties create no candidate

- Date: 2026-11-05
- Status: accepted
- Decision: Equal closest distances for home and away produce an internal no-candidate value.
- Reason: Resolving a tie by tracker ordering is arbitrary.

## D-010: Provisional 50-frame majority-vote preset

- Date: 2026-11-05
- Status: provisional
- Decision: The first milestone uses a centred 50-frame half-width.
- Reason: It is a pre-registered continuity setting derived from the published baseline approach, not selected by comparing outputs on this match. PM and QA must review it before later milestones.

## D-011: Milestone 1 maps unresolved windows to D

- Date: 2026-11-05
- Status: accepted for milestone 1
- Decision: Unresolved smoothed windows become D rather than widespread X.
- Reason: The future state machine should justify selective abstention. The first milestone intentionally reproduces the published baseline and does not claim a semantic dead-ball detector.

## D-012: Build and validate atomically

- Date: 2026-11-05
- Status: accepted
- Decision: Write a sibling temporary file, validate the complete contract, then atomically replace the final path.
- Reason: A failed build must not leave a complete-looking partial submission.

## D-013: Missing slots do not invalidate visible traces

- Date: 2026-11-05
- Status: accepted
- Decision: Ignore non-finite player positions when finding the closest visible player for each team.
- Reason: Real tactical data has missing slots in most frames. Taking a raw minimum over NaN values made every frame look as though both teams had no visible player and produced an all-D output. A regression test now covers a missing slot alongside valid home and away traces.
