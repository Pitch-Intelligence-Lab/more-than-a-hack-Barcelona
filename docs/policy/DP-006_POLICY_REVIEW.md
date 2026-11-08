# DP-006 POLICY REVIEW

**Policy version:** DP-006-POLICY-v2

**Official rule revision:** `f8f2629ff1e0985f81d7e59d8413678514ee1530`

**Status:** DP-006 Final Assurance PASS; PM Policy signature pending

## Scope

This policy separates official competition rules, provider rights, internal authorization, technical controls, label roles and match-level holdout integrity.

## Official rules

- External games, external human labels and pretrained models may be used when organizers can inspect the method and rights are respected.
- Labels or private ground truth for the provided match are prohibited.
- The public five-minute target ground truth is limited to automated pipeline-correctness checks.
- Target-provided data must not be uploaded to third-party cloud services.
- Reproduction remains mandatory.

## Label roles

```text
MODEL_INPUT
TRAINING_TARGET
AUXILIARY_TRAINING_TARGET
EVALUATION_REFERENCE
POST_INFERENCE_DIAGNOSTIC
```

Possession labels, player possession IDs, evaluation references and future event outcomes are prohibited from `ModelInput`.

## Provider rights

| Provider | Public source | Data licence | Research | Training | Evaluation |
|---|---|---|---|---|---|
| SkillCorner | PASS | HOLD | HOLD | HOLD | HOLD |
| Metrica | PASS | HOLD | HOLD | HOLD | HOLD |
| SoccerTrack v2 | PASS | HOLD | HOLD | HOLD | HOLD |

Official permission does not substitute for provider rights or internal authorization.

## Technical controls

- Machine-readable provider × use × status policy.
- Fail-closed external loader gate.
- `ModelInput` allowlist and label-role registry.
- Dynamic-event temporal availability contract.
- Phase semantics and phase-team leak controls.
- Cross-provider label definition IDs and mapping versions.
- Match-level split and holdout seal lifecycle.

## Decision

```text
Policy design: PASS
R3 model/governance identity separation: PASS
R3 audit-only legacy migration: PASS
R3 Holdout Manifest immutability: PASS
R3 Source Identity seal coverage: PASS
R3 Migration Git-object verification: PASS
R3 Migration atomicity: PASS
R3 Multi-match SourceIdentitySet: PASS
R3 Governance/Source separation: PASS
R3 Multi-match production lifecycle: PASS
R3 Partial-completion tuning contamination: PASS
R3 Contamination/start linearization: PASS
R5 Temporal integration: PASS within Final Assurance scope
REPAIR-006 Re-review: PASS
Final Assurance A1 Authorization: PASS
Final Assurance A2 Source Integrity: PASS
Final Assurance A3 Identity Integrity: PASS
Final Assurance A4 Lifecycle Integrity: PASS
Final Assurance A5 Reproducibility: PASS
Audit production snapshot gate: PASS
P1 compromised trigger identity: PASS
P1 match-event identity binding: PASS
Policy implementation final acceptance: HOLD
PR #9: open, unmerged, PM/QA review required
Final Assurance: PASS
REPAIR-007: not authorized
Official rule traceability: PASS
SkillCorner rights: HOLD
Metrica rights: HOLD
SoccerTrack access: HOLD
Real-data research activation: HOLD
```

