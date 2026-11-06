# Agent Working Instructions

These instructions apply to every coding agent working in this repository.

## Fixed locations

- Code repository: `E:\mtah2027-code`
- Local data root: `E:\mtah2027-data`
- Generated submissions: `E:\mtah2027-code\outputs`

Do not create a second code repository or a separate delivery folder. Make changes directly in the repository working tree.

Do not read, copy, commit, log, upload, or inspect competition videos, tracking files, homography files, Smart Tagging source files, screenshots, or extracted rows. Programs may read tactical ATD through `MTAH_DATA_DIR` only when the task explicitly requires a local run.

## Start of every task

1. Run `git status --short --branch`.
2. Do not discard uncommitted work.
3. Fetch `origin`.
4. Start new work from `origin/dev`.
5. Create or switch to the assigned `feature/<task-id>-short-name` branch.
6. Confirm that the task has a measurable acceptance condition.

## Delivery

- Edit files directly in `E:\mtah2027-code`.
- Do not send a standalone ZIP or patch when repository access is available.
- Add or update tests for behavior changes.
- Run `python -m pytest`, `ruff check .`, and `ruff format --check .`.
- Commit only to the assigned feature branch.
- Never push directly to `main` or `dev`.
- Push the feature branch and provide its commit hash and pull-request link.
- Keep generated CSVs under `outputs/`; they are ignored.

## Rules

- Do not hand-label or manually correct the provided match.
- Do not compare generated output with the video by hand.
- Do not train, fit, or tune on the provided video or ground truth.
- Training and parameter tuning require appropriately licensed external data.
- Do not use competition data in Notion, CI, cloud AI, or public repository files.
- Stop and ask PM/QA when a football-semantic rule is ambiguous.
