# DP-006 Policy v2.1 P0 Call-Chain Matrix

**Baseline:** `b6f61a475600498ae7993b352ecb8b94e19c77ec`

**P0 verdict:** PASS - bounded separation is feasible without Source Identity,
Holdout, DP-005 or frozen-data rewrites.

## CALL_CHAIN_MATRIX

| entrypoint | function | source_path | line_start | line_end | read_roles | requested_use | actual_use | label_exposure | prediction_order | proposed_change |
|---|---|---:|---:|---:|---|---|---|---|---|---|
| evaluation CLI | `run_external_evaluation` | `src/mtah_possession/evaluation/runner.py` | 83 | 411 | match, tracking, phases, license, readme | READ, TRACKING, PHASE, EVALUATION | all uses fixed regardless of requested run mode | full `NeutralMatch`, including possession, before prediction | load -> authorization -> prediction/evaluation in one evaluator call | request uses from `EvaluationPlan`; load prediction projection first, reference only for scored modes |
| evaluation CLI helper | `run_external_evaluation` | `src/mtah_possession/evaluation/runner.py` | 259 | 275 | policy, split, freeze, holdout, governance | fixed four uses | evaluation-reference authorization occurs before prediction | none at authorization time | authorization before loader | derive required uses from declared candidates/score mode |
| source loader | `load_skillcorner_match_from_snapshot` | `src/mtah_possession/data/skillcorner.py` | 187 | 432 | license, readme, tracking, phases, match | invoked after all-use authorization | reads and parses tracking possession and phases eagerly | `NeutralMatch.possession_side`, `possession_status`, `phases` | before `build_model_input` and prediction | split tracking-only prediction loader and post-prediction reference projection from same bytes |
| tracking parser | `load_skillcorner_match_from_snapshot` | `src/mtah_possession/data/skillcorner.py` | 298 | 367 | tracking | TRACKING + EVALUATION | reads `record.possession.group` into reference arrays | possession group/status | before prediction | prediction pass ignores possession; reference pass parses it only after prediction hash |
| phase parser | `_parse_phases_stream` | `src/mtah_possession/data/skillcorner.py` | 505 | 537 | phases | PHASE + EVALUATION | eager phase load | phase truth available before prediction | before candidate selection | load phases only when candidate plan declares phase input; reference pass may reuse bytes |
| model input | `build_model_input` | `src/mtah_possession/data/model_input.py` | 55 | 80 | tracking, periods, approved evidence | TRACKING (+PHASE if declared) | consumes `NeutralMatch` and converts tracking | possession not copied into `ModelInput`, but present in source object | before prediction | accept `PredictionSource` projection; preserve ModelInput field allowlist |
| candidate evaluation | `evaluate_external_match` | `src/mtah_possession/evaluation/external.py` | 150 | 228 | tracking, phases, possession | TRACKING + PHASE + EVALUATION | always computes baseline, DP-005 and DP-006; proxy before candidate metrics | possession exposed before prediction | build input -> baseline/DP005/DP006 -> proxy -> metrics | split prediction candidates from scoring; construct reference after prediction hashes |
| phase candidate | `evaluate_external_match` / `predict_model_input` | `src/mtah_possession/evaluation/external.py` | 177 | 205 | phases + temporal evidence | PHASE | DP-006 phase gap directives always constructed | phase truth before all candidate outputs | currently before metrics | only request/load phases when `uses_phase_model_input=true` |
| proxy reference | `map_proxy_target` | `src/mtah_possession/data/neutral.py` | 131 | 205 | possession + phases | EVALUATION | builds target from possession/period/phase | full evaluation labels | currently before candidate metric loop | invoke only after predictions fixed and reference loaded |
| metrics | `evaluate_predictions` | `src/mtah_possession/evaluation/external.py` | 231 | 280 | target + prediction arrays | EVALUATION | metric computation after prediction arrays exist | evaluation target | after prediction label production | retain ordering but isolate scored path |
| structure audit | `main` | `scripts/audit_external.py` | 91 | 213 | match, tracking, phases | READ + EVALUATION + label profiles | one path requests evaluation and both label profiles | possession proxy built before report | authorize -> load -> proxy -> structure report | add structural mode with no evaluation use or proxy; retain proxy mode separately |
| proxy audit | `main` | `scripts/audit_external.py` | 117 | 184 | possession + phases + label profiles | EVALUATION + label profiles | proxy target generated in same path as structure | full labels | before audit report | require evaluation reference and profiles only in explicit proxy mode |
| policy overview | `ProviderPolicy.overall_status` | `src/mtah_possession/governance/policy.py` | 91 | 112 | none | none | test/display aggregate only | none | not in prediction order | document as non-gate; no production caller found |

## Production entrypoint resolution

```text
Production evaluator: scripts/evaluate_external.py -> run_external_evaluation
Production audit: scripts/audit_external.py
Loader: load_skillcorner_match_from_snapshot
Prediction construction: build_model_input -> predict_model_input
Evaluation proxy: map_proxy_target
overall_status production calls: 0
```

## P0 gate result

- All production entrypoints identified.
- Fixed four-use request located.
- Possession/phases currently exposed before prediction.
- Structure/proxy audit can be separated without changing Source Identity.
- `overall_status` has no production caller; only a test uses it.
- No active/sealed Holdout is represented by the current manifest.
- DP-005 and frozen data do not need modification.
- P1 may proceed within the allowed modules.
