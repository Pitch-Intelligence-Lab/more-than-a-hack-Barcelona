# DP-006 Final Assurance TOCTOU Remediation Evidence

**Task:** `DP-006-FINAL-ASSURANCE-TOCTOU-001`

**Code review baseline:** `4a8a96aba8f9ec547e8950db55e998605b9c86bc`

**Docs baseline:** `0ef1cb89afc46ebb581335ff1da73aac81f78f66`

**Implementation commit:** `5f1108d8d67ef27680a812c9b9ec2d2dd4cf7c77`

**Branch:** `feature/DP-006-POLICY-v2`

**PR:** #9

**Requested gate:** complete DP-006 Final Assurance rerun

## Status

```text
A2 Source Integrity TOCTOU: FIX CANDIDATE
P1 compromised trigger identity: FIX CANDIDATE
P1 match-event identity binding: FIX CANDIDATE

TO-01 through TO-12: PASS
CL-01 through CL-16: PASS
TC-01 through TC-12: PASS
RC-01 through RC-17: PASS
R6-01 through R6-12: PASS
RP5-01 through RP5-09: PASS

Policy implementation final acceptance: HOLD
Final Assurance: MUST RERUN
PR #9: OPEN, UNMERGED, HOLD
Real-data research: HOLD
REPAIR-007: NOT APPROVED
```

This is engineer evidence only. It does not declare Final Assurance PASS,
Policy implementation PASS, authorize merge or authorize real-data research.

## Immutable source path

Production order is now:

```text
config path read once
  -> immutable config bytes + parsed manifest snapshot
  -> Source Identity built from the same manifest
  -> governance authorization
  -> one read of each license/readme/tracking/phases/match file
  -> checksum and parser consume the same immutable bytes
  -> loader returns actual Source Identity + actual checksums + snapshot digest
  -> runner checks sealed/actual identity and checksums
  -> evaluator
```

The loader API no longer receives a mutable config path. It receives
`SkillCornerManifestSnapshot`; injectable loaders must return a
`LoadedSkillCornerSource` object with the actual identity and checksums.

## Before remediation

Reproduced by independent Final Assurance:

```text
sealed_source_identity=7f10d18880c480a7752e1c1f9c3b98ba5d6a88ddbba846e2ed846696f45181e3
source_after_loader_swap=57c5357e4aa25525ce783a78ea8d774e8b68e4d7ec81ddc70005b8d8ddab0ffb
source_changed=True
events=SEALED_VERIFIED,UNSEALED,EVALUATION_STARTED,EVALUATION_FAILED,
       EVALUATION_STARTED,EVALUATION_COMPLETED
```

The old loader re-read the mutable config path after validation and completed
evaluation against another source.

## After remediation

Production-path probe:

```text
sealed_source_identity=04b867df86da7f2163640aa6ac408d1b4a61a41e7447ab57948946c2e3b1b05b
loader_actual_identity=04b867df86da7f2163640aa6ac408d1b4a61a41e7447ab57948946c2e3b1b05b
snapshot_digest=d1afb2b72d2d9bd44433e2e25f989b26d9dcc4aa80ed6c4539f99b93876cf93c
config_match_after_attempt=102
loader_calls=1
evaluation_completed_written=True
ledger_sha256_after_start=ca8cd09805bcbeda9ca0b33d4814220c12e30ba30a2f08f53d35d74bb6da2926
ledger_sha256_after_complete=daa92456bdd79a0697e6f701545f0fa095c5f3d2f2889ba66f8b88afa5b8d313
```

The config path was replaced with `match_id=102` after the snapshot. The sealed
snapshot, loader actual identity and completed ledger record remained
`match_id=101`.

Actual checksums:

```text
license=3d40a71f046a83d57d5f4e5d7bf7158d193f9471e623bd3d4da8cbb169b61fb1
readme=8130eef76fb1184b5c7ecb95078605089a2cbe1be450aa8118df8dc2c0d537cf
tracking=64ae08408cfdb762a2e7127e0c3e35c4d3212d3c7ac6c8254ac518fac166e681
phases=b92d8b5d0753a30291e18b4527df434a187c850f37281222405c29b7cf67fba3
match=352c74b52bff4521157959a2e82f8775c44f0029d7391527b5dee23589e60f27
```

## Failure behavior

- a changed data path is rejected by checksum mismatch;
- loader actual checksums differing from the seal fail before evaluator and do
  not write `EVALUATION_COMPLETED`;
- mismatch failures persist `EVALUATION_FAILED`;
- the resulting ledger remains hash-chain-valid and has no partial line;
- config/data replacement after the relevant bytes have been read cannot alter
  parsing;
- source-set and lifecycle regressions remain covered.

## P1 fixes

### Compromised trigger identity

Before:

```text
trigger_match_id=holdout-1
COMPROMISED.source_identity.match_id=holdout-2
```

After:

```text
trigger_match_id=101
trigger_prediction_sha256=59f1c53487f9a8db59fdf6e5c1e63154707b6b22da802280b9b3648e5f1a3a49
COMPROMISED.match_id=None
COMPROMISED.source_identity.match_id=101
COMPROMISED.prediction_sha256=59f1c53487f9a8db59fdf6e5c1e63154707b6b22da802280b9b3648e5f1a3a49
```

### Match-event identity binding

For `EVALUATION_STARTED`, `EVALUATION_FAILED` and `EVALUATION_COMPLETED`, the
ledger now enforces:

```text
event.match_id == event.source_identity.match_id
```

An intentional mismatch is rejected before the candidate record is written and
the ledger bytes remain unchanged.

## TO test results

| Test | Result |
|---|---|
| TO-01 | Config replaced after snapshot; sealed snapshot remains authoritative |
| TO-02 | Data-file replacement rejected by checksum mismatch |
| TO-03 | Loader checksum mismatch cannot write `EVALUATION_COMPLETED` |
| TO-04 | Normal source completes with sealed/actual identity equality |
| TO-05 | Both multi-match members use their corresponding snapshot identity |
| TO-06 | Failure ledger is hash-chain-valid with no partial record |
| TO-07 | Config path replacement is not consumed |
| TO-08 | Data path replacement after read does not change parsed bytes |
| TO-09 | Match/source identity mismatch rejected before append |
| TO-10 | Partial tuning `COMPROMISED` uses trigger-member identity |
| TO-11 | Single-match Holdout remains compatible |
| TO-12 | Failed retry preserves the same Source Identity |

## Quality gates

```text
pytest -q -W error: 263 passed
invalid MTAH_EXTERNAL_DATA_DIR: 263 passed
Ruff check: PASS
Ruff format --check: PASS
Task package validation: PASS
task_package_sha256=943C7CA232B3071A70EAD3BEC8FAF3069AF5A8DFF56E5305961954E44D0F41AD
External data accessed: NO
Real evaluation run: NO
Training or tuning run: NO
Tracked external-data files: 0
```

## Baseline and review boundary

```text
Stable tag: foundation-stable-dp005-v1.2.0-2026-11-06
Stable commit: c4b80a99695fa89f97d9a4a8296f249493bdd278
Research tag: foundation-research-dp006a-v1.1.0-2026-11-06
Research commit: cdfeaf3d1f06914a255c291859315f766eb8a945
Frozen data package expected SHA-256: 8b053decd116b0f7913c6bc234cc82c48eb03a4ac93241ed632f975c9fe896b4
```

No DP-005, R5, frozen data package, stable tag or research tag is changed.
The prior Final Assurance conclusion cannot be reused; a complete Final
Assurance rerun is required against the new frozen HEAD.
