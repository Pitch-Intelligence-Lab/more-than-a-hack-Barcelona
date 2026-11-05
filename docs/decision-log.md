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

## D-014: DP-005 uses explicit observation quality

- Date: 2026-11-05
- Status: accepted
- Decision: Ball observations are classified as observed, interpolated or missing. Only internally bracketed gaps up to 0.4 seconds are interpolated.
- Reason: The ball is missing on a large fraction of graded frames. Carrying a quality flag prevents interpolation from being mistaken for a real observation.

## D-015: Missing ball is not a dead-ball label

- Date: 2026-11-05
- Status: accepted
- Decision: A missing ball freezes or weakens possession evidence but does not itself force D.
- Reason: Occlusion and tracking loss are not equivalent to a referee stoppage. The verified baseline conflated the two.

## D-016: Team possession changes can be direct

- Date: 2026-11-05
- Status: accepted
- Decision: H to A and A to H are valid direct transitions. D is never inserted as a required bridge.
- Reason: Controlled possession can transfer directly in open play; a synthetic D segment would create a false stoppage.

## D-017: State changes require persistent evidence

- Date: 2026-11-05
- Status: accepted
- Decision: An in-play team change requires 0.8 seconds of persistent opposing evidence. The nearest team and visible three-player neighbourhood must not conflict.
- Reason: A touch, deflection or rapid pass near an opponent should not immediately change possession.

## D-018: Dead-ball evidence is explicit and sustained

- Date: 2026-11-05
- Status: provisional engineering assumption
- Decision: D requires explicit evidence for 0.8 seconds. The enabled default evidence is an observed ball remaining below 0.5 m/s for at least 1.5 seconds.
- Reason: This provides a deterministic first D trigger without equating missing data with stoppage. Ball rest may also occur during shielding, so this rule still needs external validation.

## D-019: Restarts may recover faster than open-play switches

- Date: 2026-11-05
- Status: engineering assumption
- Decision: A 0.4-second team candidate is sufficient to leave D.
- Reason: The restart itself provides clearer transition context than loose open-play evidence.

## D-020: Structural cleanup is separate and conservative

- Date: 2026-11-05
- Status: accepted
- Decision: Enabled cleanup absorbs only a short segment bracketed by the same state; it never bridges X. Minimum-segment and isolated-D cleanup are disabled.
- Reason: Cleanup must not erase deliberate short possessions or real dead-ball evidence without external support.

## D-021: X is restricted to known ungraded blocks

- Date: 2026-11-05
- Status: accepted
- Decision: Emit X only for the published pre-match, halftime and post-match frame blocks. Every known graded frame is H, A or D.
- Reason: This preserves scoring semantics and prevents broad abstention from masquerading as a model.

## D-022: Every algorithm parameter carries provenance

- Date: 2026-11-05
- Status: accepted
- Decision: The state-engine configuration records unit, source and rationale for every numeric or boolean parameter.
- Reason: The match ground truth cannot be used for parameter selection, so the repository must make the basis of each default inspectable.

## D-023: Forced dead blocks override inference and cleanup

- Date: 2026-11-05
- Status: accepted
- Decision: Frames 110808 through 113741 are configured as a forced-dead block, separate from ungraded X blocks. State inference and every cleanup step must preserve D on those frames.
- Reason: The official second half starts at 110808, but the actual restart is at 113742. The previous output incorrectly inferred H/A in this interval. This is an official boundary fact, not a public-score choice.

## D-024: Restart evidence may shorten only D-to-team confirmation

- Date: 2026-11-05
- Status: engineering assumption
- Decision: Active restart evidence can reduce D-to-team confirmation from 0.4 to 0.2 seconds. With no active or enabled restart evidence, the previous 0.4-second behavior is unchanged.
- Reason: Leaving a calculated restart signal unused made the feature misleading. Restricting its effect to leaving D avoids changing open-play possession transitions.

## D-025: Preserve D in short-flicker cleanup by default

- Date: 2026-11-05
- Status: accepted
- Decision: Short-flicker absorption applies only to H/A segments. Isolated-D removal remains separately configurable and disabled by default.
- Reason: No external validation currently supports erasing a short D interval. Default D preservation avoids converting possible stoppages into possession.

## D-026: Missing-team comparisons use finite-only arithmetic

- Date: 2026-11-05
- Status: accepted
- Decision: Team distance margins are computed with masked subtraction only where both team minima are finite. A fully missing team always retains the no-candidate state.
- Reason: Direct subtraction of two `inf` values creates an undefined gap and a runtime warning. The state should remain explicitly unresolved instead.

## D-027: External data access is limited to one audited match

- Date: 2026-11-05
- Status: accepted
- Decision: Download and evaluate only SkillCorner match `2017461`.
- Reason: Gate A allows one audited match before licence, schema and proxy semantics are understood. Downloading the full collection would exceed the approved scope.

## D-028: SkillCorner possession is a proxy, not ground truth

- Date: 2026-11-05
- Status: accepted
- Decision: External metrics use a documented H/A/D/X proxy and do not claim equivalence to organiser labels.
- Reason: SkillCorner possession semantics, broadcast tracking and phase definitions differ from the target data.

## D-029: Null possession is classified by context

- Date: 2026-11-05
- Status: accepted
- Decision: Missing possession inside an active phase maps to X. Missing possession with no phase inside a declared period maps to D with an explicit source. Outside-period and missing-row frames map to X.
- Reason: Absence of a possession ID alone is insufficient evidence of a stoppage.

## D-030: External splits are match-level

- Date: 2026-11-05
- Status: accepted
- Decision: Match `2017461` is development only; validation and holdout are explicitly empty.
- Reason: A frame-level split would leak match-specific structure. One available match cannot establish generalisation.

## D-031: DP-006 phase evidence remains separate

- Date: 2026-11-05
- Status: accepted
- Decision: Phase, restart and confirmed-dead evidence are compiled in a separate layer and protected from cleanup.
- Reason: Dead-ball semantics should be inspectable and testable independently from team possession inference.

## D-032: DP-006 is not automatically selected

- Date: 2026-11-05
- Status: accepted
- Decision: Keep DP-005 v1.2 as the provisional target candidate. Do not promote the phase-proxy DP-006 candidate without an equivalent target phase source and an untouched external holdout.
- Reason: DP-006's development advantage uses a phase source that also defines much of the proxy's D class. The result is diagnostic and structurally coupled, not independent generalisation evidence.

## D-033: Possession labels are evaluation-only

- Date: 2026-11-05
- Status: accepted for DP-006A local draft
- Decision: Possession labels and status must not change `neutral_to_tracking` output or appear in the state-engine input type.
- Reason: A model that sees the evaluation proxy cannot be independently compared against it.

## D-034: Transition F1 is reported with precision and recall

- Date: 2026-11-05
- Status: accepted for DP-006A local draft
- Decision: External metrics include transition F1 as the harmonic mean of transition precision and recall while retaining both components.
- Reason: The F1 provides a compact comparison without hiding missed or spurious transitions.

## D-035: One-match split cannot be promoted

- Date: 2026-11-05
- Status: accepted for DP-006A local draft
- Decision: Promotion requires non-empty development, validation and holdout splits plus status `ready_for_validation`.
- Reason: A one-match diagnostic cannot establish cross-match generalisation.

## D-036: Diagnostic and promotion modes are explicit

- Date: 2026-11-05
- Status: accepted for DP-006A local draft
- Decision: The one-match development workflow remains available in diagnostic mode. Promotion mode checks split readiness before reading external match data.
- Reason: Research iteration should remain possible without weakening the final selection gate.
