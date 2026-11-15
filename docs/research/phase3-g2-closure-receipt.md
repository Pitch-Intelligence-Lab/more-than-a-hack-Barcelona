# Phase-3 G2 Closure Receipt

## 1. Delivery identity

```yaml
task_id: MTAH-PHASE3-G2-CLOSURE-001
branch: feature/MTAH-PHASE3-G2-DYNAMICS
baseline: e7d1872faa484205d81ce76ae3fc9fbfc5dcf05a
implementation_commit: 1df76a8f6eb216dcf0c3d31e637632dcd5cdeab6
pull_request: https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona/pull/12
base_branch: dev
pr_number: 12
pr_state_before_closure: open
draft: false
mergeable: true
worktree_clean: true
code_changed_in_closure: false
```

## 2. Change scope

The PR contains only G2 implementation, tests, README and documentation:

```text
src/mtah_possession/research/phase2/g2.py
src/mtah_possession/research/phase2/g2_cli.py
tests/research/phase2/test_g2_extractor.py
docs/research/phase3-g2-dynamics.md
docs/research/phase3-g2-dynamics-receipt.md
README.md
```

This closure adds documentation only. No G2 definition, P2 schema, split,
decoder, training artifact, policy artifact or frozen data was changed.

## 3. Local verification

```text
pytest -q -W error: 94 passed
ruff check .: PASS
ruff format --check .: PASS (64 files)
git diff --check: PASS
```

The five development G2 outputs were regenerated/validated from the accepted
P2 inputs:

| Match | Rows | Runs | Output SHA-256 |
|---|---:|---:|---|
| `J03WMX` | 145,967 | 2 | `0e53f751c948ae94b9fd6ce7e823343468dab4a15e1c765fb222991f46869e60` |
| `J03WOH` | 137,214 | 2 | `5b5b51e761a89db3ab58f1cd43dfb289bf0c347d2144552755ed6703f6e0d504` |
| `J03WOY` | 142,536 | 2 | `737fcc9b175d98e71172cbf6e727153f3f418b43313e377205201ba98d0e24f4` |
| `J03WPY` | 146,211 | 2 | `d7386e07709840f48104cb713bb662c00403bd101b86b72b21dde3218aadacfc` |
| `J03WQQ` | 142,345 | 2 | `c6a4fbcc0162109764a16ae2ebd45fd03045cad92f3be9194dd431b3ae35f701` |

## 4. CI evidence

```text
workflow: tests
run id: 43738520387
head SHA: e7d1872faa484205d81ce76ae3fc9fbfc5dcf05a
event: pull_request
status: completed
conclusion: success
```

URL: https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona/actions/runs/43738520387

## 5. Decision

```text
G2 implementation accepted by independent audit
closure evidence complete
merge target: dev
merge method: merge commit
merge: withheld until final PR-head CI
training: not started
lockbox evaluation: HOLD
final model: NOT SELECTED
```
