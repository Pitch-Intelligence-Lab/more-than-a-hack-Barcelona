# DP-006 Policy Remediation 005 Evidence

**Task:** DP-006-POLICY-REMEDIATION-005

**Base commit:** `c8c0661943008e0b73b6e0ab506ad589a3642144`

**Branch:** `feature/DP-006-POLICY-v2`

**PR:** #9

**Result:** audit-only migration, immutable seal and Evaluation/Split identity
candidate for PM/QA review

## Status

```text
R5.1 Migration audit-only: FIX CANDIDATE
R5.2 No implicit model replacement: FIX CANDIDATE
R5.3 Verified migration provenance: FIX CANDIDATE
R5.4 Manifest immutability: FIX CANDIDATE
R5.5 Evaluation Identity coverage: FIX CANDIDATE
R5.6 Split Identity coverage: FIX CANDIDATE
R5.7 Compromised remains terminal: FIX CANDIDATE
R5.8 Existing authorization/state-machine repairs: PRESERVED

Policy implementation final acceptance: HOLD
Real-data research: HOLD
Merge: DENIED
```

## P0 before remediation

The independent review reproduced model replacement through migration:

```text
legacy_model=2247f4a988ede9aca6f1308a0090f22e4b3eff981cdf8454647c6ba1a17af9ea
changed_model=0224e06086c5477db53a3984bcd8bb6a8d3121494fe9e85073af567762785dde
holdout_manifest_model=2247f4a988ede9aca6f1308a0090f22e4b3eff981cdf8454647c6ba1a17af9ea
migration_new_model=0224e06086c5477db53a3984bcd8bb6a8d3121494fe9e85073af567762785dde
final_events=SEALED_VERIFIED,FREEZE_PROTOCOL_MIGRATED,UNSEALED,
             EVALUATION_STARTED,EVALUATION_COMPLETED
```

Manifest mutability before:

```text
sealed_manifest_sha256=e1c7fbf0260cab6fe37a3efcbfeee81103e6429471798f8086387e2e30e6d6c0
changed_manifest_sha256=1849ba48c76201ff8c0a96c4c9aa6512be989a3bc85aa16fbd9ca2d9c194a43e
```

The same ledger accepted both Manifest identities.

## P0-1 after remediation: migration is audit-only

```text
state=MIGRATED_AUDIT_ONLY
events=SEALED_VERIFIED,FREEZE_PROTOCOL_MIGRATED
promotion=REJECTED: migrated holdout ledger is audit-only and cannot promote
loader_calls=0

ledger_sha256_before=46c235ce0b04fdd9602be7f8f1e62f689f26bd83f44bf6f4b8e705829127a19c
ledger_sha256_after_migration=1a96317ff410f75149278993407da0855a7266f144d46b735a8f40afc7ee36d9
ledger_sha256_after_rejection=1a96317ff410f75149278993407da0855a7266f144d46b735a8f40afc7ee36d9
```

The migration event appends an immutable audit record and does not make the
ledger eligible for Promotion.

## Verified migration receipt

Migration verification requires:

- an existing full Git migration commit;
- a full Git old-code commit;
- an approval receipt committed in a separate real Git approval commit;
- migration tool bytes matching the migration commit;
- current receipt bytes matching the approval commit;
- current model/evaluation/split artifacts matching approved target identities;
- old ledger byte SHA-256 and old record-head hash;
- old combined freeze and old/new Manifest hashes;
- approval evidence IDs, approver, reason and rule version.

CLI-reported hashes alone do not satisfy these checks.

## P0-2 after remediation: immutable Manifest

```text
sealed_manifest_sha256=b14561bb7f283a02f9932db905d0e51b48dcac04565ddce7be397f9004389512
observed_manifest_sha256=fc1f6bdeaea37c241fd784fba46c89e515db9b5b448839900c210edb04d2bb3e
outcome=REJECTED: sealed Holdout Manifest SHA-256 has changed
loader_calls=0

ledger_sha256_before=2fb8e3b867fffa48d7c9d80c5e5f632e536caad3e9180f1f66f7e50da7c71203
ledger_sha256_after=2fb8e3b867fffa48d7c9d80c5e5f632e536caad3e9180f1f66f7e50da7c71203
```

The first `SEALED_VERIFIED` binds Manifest SHA, Manifest path identity, split
manifest SHA and all lifecycle events. Later content or path changes fail before
the loader and do not append or overwrite ledger events.

## P0-3 after remediation: Evaluation / Split coverage

Production Evaluation Identity includes:

```text
scripts/evaluate_external.py
src/mtah_possession/evaluation/external.py
src/mtah_possession/evaluation/provenance.py
src/mtah_possession/evaluation/runner.py
src/mtah_possession/evaluation/splits.py
docs/evaluation-contract.md
```

Measured changes:

```text
evaluation_identity_before=bf040bd24ecaa23cf65e8392d03497890f7635d4340b21e0cf0add4fa283fe42
after_runner_change=a6eb9cd3fc293ff98cfa0a9d15344e703f6d7fafd2f261b35dcb53b71a49c81b
runner_change_detected=True

after_splits_change=62537fbf8cc5e9cbfd2878cedca3060b399ea572c730f6311bbab4841a1cb599
splits_change_detected=True

split_manifest_sha256_before=3e5156f813fddba6df99ed0134cddab6012cf4f5ccfc20a62484a584f2b5ce7a
split_manifest_sha256_after=946acbf9d39c9a803fe6c82ae70382d88da2bb706120b7bbb97076a1aa8e9970
split_manifest_change_detected=True

production_split_manifest_sha256=0d971d324f260110905587fc09f434fb3a58892d5890156020f88a88426b9525
production_holdout_manifest_sha256=0f58b53681e2c6920efa5a34dff9d565fd2f586d38d4d73a5e55a219ae49d708
```

Current production model/evaluation freeze:

```text
model=752a8a9a092222961824c309facc41e6c07f97377f71e797b1bc77d15a0a8440
feature_set=2d1ac11c13cacb303b139dda5d0d2cad82fefc0c35b33bb47a720ee28c07ec2e
configuration=94c06802da803878ee7a2248af3f213e7f2cb1cfd7c852ca055efc10af6eacac
hyperparameters=0712e6e94145ff7445d4c06f08769a24144f5d641287893ed8f59d612a9db3f5
evaluation_script=ed416ecd2b84cbce1d1626771d47da29d9691347a102f1e5a508d8bd40dff50e
metric_contract_version=1.1.0:25ec4f45bd0e01cde9bd61fa4e7463b2adb42e5aef484e154f639aa768444a49
```

## RP5 results

| Test | Result |
|---|---|
| RP5-01 | Migrated Clean ledger is `MIGRATED_AUDIT_ONLY`; Promotion rejected; loader `0` |
| RP5-02 | Modified model cannot be migrated; original ledger bytes retained |
| RP5-03 | Missing/mismatched migration commit rejected; no event |
| RP5-04 | Self-reported target hash cannot replace committed approval/actual artifact verification |
| RP5-05 | status/unseal_log/hashes/matches changes after seal rejected; ledger unchanged; loader `0` |
| RP5-06 | runner change changes Evaluation Identity and invalidates seal; loader `0` |
| RP5-07 | splits change changes Evaluation Identity and invalidates seal; loader `0` |
| RP5-08 | split manifest change changes Split Identity; rejected before loader |
| RP5-09 | compromised match set cannot migrate, re-seal or obtain a clean stable identity |

## Quality gates

```text
pytest -q -W error: 187 passed
invalid MTAH_EXTERNAL_DATA_DIR: 187 passed
Ruff check: PASS
Ruff format --check: PASS
Review task package validation: PASS
External data accessed: NO
Real evaluation run: NO
Training or tuning run: NO
Tracked external-data files: 0
```

## Baseline integrity

```text
Task ZIP SHA-256: 2D4F004FC5B2016D055676146A3C237D8EE02B4CA708F3EB6A6920B03D1B615F
Stable tag: foundation-stable-dp005-v1.2.0-2026-11-06
Stable commit: c4b80a99695fa89f97d9a4a8296f249493bdd278
Research tag: foundation-research-dp006a-v1.1.0-2026-11-06
Research commit: cdfeaf3d1f06914a255c291859315f766eb8a945
Frozen data package expected SHA-256: 8b053decd116b0f7913c6bc234cc82c48eb03a4ac93241ed632f975c9fe896b4
```

The frozen-package value matches the reviewed baseline manifest. Package bytes
were not read or recomputed because real external-data access is prohibited.
R5 temporal, DP-005, split/freeze data, stable tags and historical DP-006
documents remain outside this remediation.

## Review boundary

The engineer does not declare Policy implementation PASS and does not merge
PR #9. PM/QA owns final acceptance, merge approval and real-data authorization.
