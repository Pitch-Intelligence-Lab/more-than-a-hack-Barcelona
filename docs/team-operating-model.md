# Team Operating Model

## Purpose

Coordinate a 3-5 person team without creating unnecessary meetings or management layers. Every task has one owner, one measurable acceptance condition and one evidence link.

## Source of truth

- GitHub: code, decisions, experiments and final documentation.
- Notion: task status, owner, deadline and blocker.
- Local data directory: competition assets; never uploaded or committed.

If sources conflict, merged GitHub content wins.

## Roles

| Role | Outcome | Owner |
|---|---|---|
| PM and integration | Scope, risk, integration and submission | TBD |
| Data and tracking | Data contract, alignment and features | TBD |
| Algorithm and state machine | Dead-ball and possession transitions | TBD |
| QA and reproducibility | Tests, validation, hashes and clean runs | TBD |
| Football semantics and docs | Rule interpretation, limitations and report | TBD |

Combine roles for a smaller team. A person may hold multiple roles, but a task has only one owner.

## Cadence

- Daily async update: completed, next, blocker.
- Daily 15-minute dependency sync.
- Integration every 2-3 days.
- Rule audit before each integration and before submission.

## Definition of done

1. The change is merged.
2. The acceptance condition is demonstrated.
3. The command is reproducible.
4. No competition data entered Git, CI, Notion or a cloud AI service.
5. Another member has reviewed the change.

## Branching

- `main`: stable and presentable.
- `dev`: integration branch.
- `feature-*`: one task or hypothesis.
- `fix-*`: defect repair.
- `docs-*`: documentation.

Open a pull request for every meaningful change. Require one reviewer before merging to `dev`; require QA review before releasing to `main`.

## Escalation

Escalate a blocker when it prevents another member from starting work, threatens the internal deadline, or touches a rule boundary. Record the question, impact and decision in the decision log.
