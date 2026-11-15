# Phase-2 Feature Extractor P2 Delivery Receipt

## 1. Delivery identity

```yaml
task_id: MTAH-PHASE2-FEATURE-EXTRACTOR-P2-001
branch: feature/MTAH-PHASE2-FEATURE-EXTRACTOR-001
baseline: b42aef00ff7bbbd90fc0f1fff98323e5d97150c0
implementation_commit: f51c093dec2e959d270141f4d409545150f4ec8d
pull_request: https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona/pull/11
repository_head_at_wmx_run: f51c093dec2e959d270141f4d409545150f4ec8d
implementation_commit_at_wmx_run: f51c093dec2e959d270141f4d409545150f4ec8d
source_tree_dirty_at_wmx_run: false
merge: withheld
training: not started
```

PR #11 advances to the final docs-only commit containing this receipt.

### Identity note

The repair prompt's illustrative acceptance values were:

```text
repository_head=b42aef00ff7bbbd90fc0f1fff98323e5d97150c0
implementation_commit=d19e7c4ad91163bb4e3bd9e994c58aa1dd8a573b
source_tree_dirty=false
```

Those were the clean pre-repair identities. P2-A necessarily changes
`src/mtah_possession/research/phase2/extractor.py`, so after the repair is
committed the task's required definitions necessarily produce the new commit as
both `repository_head` and `implementation_commit`. Reporting the old values from
a clean repaired tree would be inaccurate.

The extractor therefore reports the actual values:

```text
repository_head=f51c093dec2e959d270141f4d409545150f4ec8d
implementation_commit=f51c093dec2e959d270141f4d409545150f4ec8d
source_tree_dirty=false
code_commit=f51c093dec2e959d270141f4d409545150f4ec8d
```

`code_commit` remains only as a compatibility alias for `repository_head`.

## 2. Modified files

| File | Reason |
|---|---|
| `src/mtah_possession/research/phase2/extractor.py` | enforce player/ball section consistency, smoke identity, and separate provenance fields |
| `tests/research/phase2/test_phase2_extractor.py` | add P2 fail-closed and provenance regression coverage |
| `docs/research/phase2-feature-extractor.md` | document repository/implementation/dirty identity semantics |
| `docs/research/phase2-feature-extractor-p2-receipt.md` | record bounded P2 delivery evidence |

No feature formula, coordinate boundary, output schema, split membership, model,
training or policy artifact was changed.

## 3. New tests

```text
test_player_section_must_match_ball_section
test_smoke_rejects_metadata_match_id_mismatch
test_source_identity_clean_repository_returns_two_commits
test_source_identity_marks_implementation_or_test_changes_dirty
test_source_identity_git_unavailable_fails_closed
```

The dirty-tree regression is parameterized over both an implementation-path edit
and a phase2 test-path edit.

## 4. Tests

```text
pytest -q -W error: 84 passed
ruff check .: PASS
ruff format --check .: PASS (57 files)
git diff --check: PASS
section mismatch rejection: PASS
smoke metadata mismatch rejection: PASS
provenance clean/dirty/unavailable tests: PASS
```

## 5. WMX full rerun

```text
Output: outputs\phase2\features\J03WMX-p2
Rows: 145,967
Elapsed: 42.667 s
Peak memory: 592,228,352 bytes
```

| Artifact | Old SHA-256 | New SHA-256 | Match |
|---|---|---|---|
| `features.csv.gz` | `bf6b65ea6237d57101931f8d59b4f2c36af24e982ff76da4662214697c05918a` | `bf6b65ea6237d57101931f8d59b4f2c36af24e982ff76da4662214697c05918a` | PASS |
| `reference.csv.gz` | `ad56bb80e52618779c019b258f31880791a80edd785eb5c7aa6f6eab49b28677` | `ad56bb80e52618779c019b258f31880791a80edd785eb5c7aa6f6eab49b28677` | PASS |
| `split_manifest.json` | `94af926d479176546043bf270c06a1610e27441e58a8e1253eca3ad55e1b0708` | `94af926d479176546043bf270c06a1610e27441e58a8e1253eca3ad55e1b0708` | PASS |

The prior `J03WMX` and `J03WOH` evidence directories were retained unchanged.

## 6. Worktree and decision

```text
worktree after final docs commit: clean
PR #11: open, unmerged
P2 implementation complete for PM review
merge: withheld
training: not started
real-data research: HOLD
```
