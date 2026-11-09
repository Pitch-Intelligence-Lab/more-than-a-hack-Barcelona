# DP-006 Integration Execution Receipt

## 1. Execution identity

```text
Task ID: DP-006-INTEGRATION-EXECUTION-001
Integration verdict: PASS
Policy implementation: ACCEPTED
Baseline: 165f170a7cea662e7a746485865cd39b36e427ff
Repository: https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona.git
Branch: feature/DP-006A-leakage-promotion-gate
Integration receipt commit: 165f170a7cea662e7a746485865cd39b36e427ff
```

This file is the current integration receipt. The REPAIR-006 historical receipt
remains at `06_工程师交付回执.md` and is not replaced by this document.

## 2. PR #8 / main restore

```text
PR number: 8
PR title: repair(repo): restore frozen DP-005 foundation on main
PR state: closed
PR merged: true
PR merge_commit_sha: 59046022e2121f0c29ac29898a9c0202b82bb007
PR mergedAt: 2026-11-09T05:02:34Z
PR headRefOid: 59046022e2121f0c29ac29898a9c0202b82bb007
PR baseRefName: main
origin/main: 59046022e2121f0c29ac29898a9c0202b82bb007
origin/main tree: 599125166450341dc19a922772acc48c48ff9f57
Stable commit: c4b80a99695fa89f97d9a4a8296f249493bdd278
Stable tag tree: 599125166450341dc19a922772acc48c48ff9f57
Formal closure method: merged PR #8
Tree equality: PASS
Force push performed: no
History rewritten: no
```

## 3. PR #9 integration

```text
PR number: 9
PR URL: https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona/pull/9
Initial source head: 75690bb6c8cb0bd077ea257c5c186327cb6a5353
Final source head: 479e0b663df3d38eb29a72b463399744fb8361f9
Target branch: feature/DP-006A-leakage-promotion-gate
Research base: cdfeaf3d1f06914a255c291859315f766eb8a945
Target head before merge: cdfeaf3d1f06914a255c291859315f766eb8a945
PR merged: true
merge_commit_sha: 2bfcff41e1900ef087d611da02272d36983379d8
mergedAt: 2026-11-09T05:13:45Z
Research branch head after merge: 2bfcff41e1900ef087d611da02272d36983379d8
Research branch final head for this receipt: 165f170a7cea662e7a746485865cd39b36e427ff
Merge method: merge commit
```

PR #9 was merged only into `feature/DP-006A-leakage-promotion-gate`.
No squash, rebase, force push, main merge or dev merge was used.

## 4. CI and verification

```text
Strict pytest: PASS
Strict pytest count: 271 passed
Invalid external root: PASS
Invalid external root count: 271 passed
Ruff check: PASS
Ruff format --check: PASS
CI run ID: 42565983320
CI run URL: https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona/actions/runs/42565983320
CI conclusion: success
```

The CI run passed:

```text
Synthetic tests with warnings as errors
Synthetic tests with invalid external root
Ruff check
Ruff format check
```

The invalid external root did not exist before the local test and was not
created by the test.

## 5. PR #9 integration payload

```text
Range: cdfeaf3d1f06914a255c291859315f766eb8a945..479e0b663df3d38eb29a72b463399744fb8361f9
Changed files: 78
```

This is the normal DP-006 Policy v2 payload accepted by Final Assurance. It
includes Policy configuration/documents, Runner, Audit, Holdout, Ledger,
Source Identity, migration, schemas, split configuration and synthetic tests.

These 78 files were not all modified during integration execution. They are the
complete content carried by PR #9 from the research base to its final source
head.

## 6. Integration execution delta

### Policy accepted head to PR source head

```text
Range: 75690bb6c8cb0bd077ea257c5c186327cb6a5353..479e0b663df3d38eb29a72b463399744fb8361f9
Changed file: .github/workflows/tests.yml
```

This delta only strengthened CI:

- `pytest -q -W error`;
- second run with a nonexistent external root;
- explicit Ruff check and format steps.

### Merge commit to integration receipt

```text
Range: 2bfcff41e1900ef087d611da02272d36983379d8..165f170a7cea662e7a746485865cd39b36e427ff
Changed file: docs/policy/06_工程师交付回执.md
```

That commit contained the integration receipt at the historical `06` path. The
metadata-correction task moves the current integration receipt to this `09`
file, while restoring `06` to its original REPAIR-006 historical receipt.

## 7. Freeze and safety

```text
Stable tag: foundation-stable-dp005-v1.2.0-2026-11-06
Stable commit: c4b80a99695fa89f97d9a4a8296f249493bdd278
Stable tag unchanged: YES
Research tag: foundation-research-dp006a-v1.1.0-2026-11-06
Research commit: cdfeaf3d1f06914a255c291859315f766eb8a945
Research tag unchanged: YES
Frozen data package SHA-256: 8b053decd116b0f7913c6bc234cc82c48eb03a4ac93241ed632f975c9fe896b4
Frozen data package unchanged: YES
Tracked restricted files: 0
Real external data accessed: no
Real evaluation run: no
Training or tuning run: no
Final model selected: no
REPAIR-007 started: no
```

## 8. Current state

```text
Final Assurance: PASS
Policy implementation: ACCEPTED
PR #9 integration: COMPLETE
Real-data research: HOLD
REPAIR-007: NOT AUTHORIZED
Next owner: PM memory update and engineering-track closure
```

The integration merge does not authorize real external data access, real
evaluation, training, tuning, active Holdout or final competition-model
selection.
