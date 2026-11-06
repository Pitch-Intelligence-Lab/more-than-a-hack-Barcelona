# External Reference Register

Record other public competition repositories here before adopting code or design ideas. A public URL is not proof that a method, model, weights, or data are permitted for reuse.

## Review rules

- Read the repository licence before reusing code.
- Determine whether the repository contains or depends on competition data.
- Do not copy weights or labels trained on the provided match video or ground truth.
- Do not assume a published score is comparable unless its evaluation scope and data are documented.
- Prefer comparing design ideas to copying full implementations.
- Record any adopted dependency or method in the technical report.

## Review stages

| Stage | Allowed work |
|---|---|
| `candidate` | Save URL, owner and short description only |
| `shallow-audit` | Read README, licence and claimed method; no data or weights downloaded |
| `deep-audit` | Review selected code after licence and compliance review |
| `adopt` | Reimplement or integrate only the reviewed, permitted component |
| `rejected` | Record why it cannot be used |

## Register

| ID | Repository | Licence | Stage | Relevant idea | Data/model risk | Decision |
|---|---|---|---|---|---|---|
| REF-001 | <https://barcainnovationhub.fcbarcelona.com/ca/blog/ipurdiar-chatbot-analisi-futbol/> | Public interview | shallow-audit | Combines tracking, events and audio narration to answer tactical questions | Open-ended 2026 project, not the same fixed per-frame scoring task | Learn from multi-source evidence and explanation; do not copy scope |
| REF-002 | <https://github.com/SkillCorner/opendata> | Repository MIT; confirm data terms before use | shallow-audit | Ten matches of broadcast tracking with per-frame possession group and phases of play | Broadcast tracking at 10 FPS; possession semantics may differ from the organiser ground truth | Best candidate for external robustness checks if data rights are confirmed |
| REF-003 | <https://github.com/metrica-sports/sample-data> | Not yet verified | candidate | Open tracking and event examples | Does not publish a clearly equivalent frame-by-frame possession target | Possibly useful for loader and continuity tests; not assumed suitable for tuning |
| REF-004 | <https://github.com/statsbomb/open-data> | Check StatsBomb terms | candidate | Event possession and tactical context | Event data only; no frame-level tracking | Use only for football semantics or event-derived features if permitted |

## Timing policy

A shallow audit is reasonable when it answers a specific question. Deep review should happen when:

1. our baseline is stable and validated;
2. a concrete state-machine or evaluation bottleneck is identified; or
3. the deadline requires choosing between competing approaches.

Do not browse competitor outputs as a substitute for defining rules from public documentation and external licensed data.

## Current assessment

The 2026 IpurdIAr interview describes an open-ended tactical chatbot that fuses tracking, events and audio narration. The 2027 challenge is narrower and automatically scored on per-frame possession state. The transferable idea is evidence fusion, not chatbot scope.

The single provided match is enough to run and integrate a submission, but it cannot establish generalisation, and the rules prohibit tuning on its video or possession labels. External matches can fill that gap only if their licences and possession semantics are compatible. A rule-based state machine can be built without machine learning, but its thresholds still need a defensible source and preferably external validation.
