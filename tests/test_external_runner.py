import json
from pathlib import Path

import numpy as np
import pytest
from helpers import loaded_source_result

import mtah_possession.evaluation.runner as runner_module
from mtah_possession.algorithm_config import load_algorithm_config
from mtah_possession.data.neutral import ProxyTarget
from mtah_possession.evaluation.external import ExternalMatchEvaluation
from mtah_possession.evaluation.runner import run_external_evaluation
from mtah_possession.evaluation.splits import EvaluationMode, SplitManifestError
from mtah_possession.governance.policy import PolicyError

ROOT = Path(__file__).resolve().parents[1]


def write_allowed_policy(tmp_path: Path) -> Path:
    policy_values = json.loads(
        (ROOT / "configs" / "policy" / "external-data-policy-v2.json").read_text(encoding="utf-8")
    )
    provider = policy_values["providers"][0]
    for axis in (
        "PUBLIC_SOURCE_VERIFIED",
        "LICENSE_VERIFIED",
        "INTERNAL_RESEARCH_AUTHORIZED",
        "EVALUATION_AUTHORIZED",
        "TEMPORAL_AVAILABILITY_VERIFIED",
        "PHASE_SEMANTICS_VERIFIED",
        "LABEL_SEMANTICS_ALIGNED",
        "HOLDOUT_SEAL_VERIFIED",
    ):
        provider["statuses"][axis] = "PASS"
    for use in (
        "read_preprocess",
        "tracking_model_input",
        "phase_model_input",
        "evaluation_reference",
    ):
        provider["uses"][use] = {
            "status": "PASS",
            "evidence_ids": ["EV-AUTH-SC-README"],
            "conditions": [],
        }
    for profile in provider["label_profiles"]:
        profile["status"] = "PASS"
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy_values), encoding="utf-8")
    return policy_path


def test_promotion_precheck_fails_closed_before_external_loader(tmp_path: Path) -> None:
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("external loader must not be called")

    with pytest.raises(SplitManifestError, match="promotion gate failed"):
        run_external_evaluation(
            config_path=ROOT / "configs" / "external-skillcorner.json",
            state_config_path=ROOT / "configs" / "state-engine.json",
            splits_path=ROOT / "configs" / "external-splits.json",
            external_root=tmp_path / "external",
            split="holdout",
            mode=EvaluationMode.PROMOTION,
            code_commit="fixture",
            policy_path=write_allowed_policy(tmp_path),
            ledger_dir=tmp_path / "ledger",
            match_loader=forbidden_loader,
        )
    assert calls == 0


def test_diagnostic_selection_is_used_in_report_and_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    split_path = tmp_path / "splits.json"
    split_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "split_unit": "match",
                "development": ["2017461"],
                "validation": ["val-1"],
                "holdout": ["holdout-1"],
                "status": "diagnostic_only",
                "reason": "synthetic diagnostic test",
            }
        ),
        encoding="utf-8",
    )
    policy_path = write_allowed_policy(tmp_path)
    observed_split = []

    def fake_evaluator(_match, _config, *, authorization, split: str):
        assert authorization is not None
        observed_split.append(split)
        proxy = ProxyTarget(
            labels=np.asarray(["H"]),
            sources=np.asarray(["fixture"]),
            counts={"H": 1, "A": 0, "D": 0, "X": 0},
            source_counts={"fixture": 1},
        )
        return ExternalMatchEvaluation(
            match_id="2017461",
            split=split,
            proxy=proxy,
            candidates={},
            source_checksums={"tracking": "abc"},
            external_aggregate={},
        )

    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    result = run_external_evaluation(
        config_path=ROOT / "configs" / "external-skillcorner.json",
        state_config_path=ROOT / "configs" / "state-engine.json",
        splits_path=split_path,
        external_root=tmp_path / "external",
        split="development",
        mode=EvaluationMode.DIAGNOSTIC,
        code_commit="abcdef0123456789",
        policy_path=policy_path,
        match_loader=lambda snapshot, _root, identity: loaded_source_result(
            snapshot,
            identity,
            "2017461",
        ),
        state_config_loader=lambda _path: load_algorithm_config(
            ROOT / "configs" / "state-engine.json"
        ),
    )
    assert observed_split == ["development"]
    assert result.report["split"] == "development"
    provenance = result.report["provenance"]
    assert provenance["source_adapter_version"] == "1.1.0"
    assert provenance["evaluation_contract_version"] == "1.1.0"
    assert provenance["code_commit"] == "abcdef0123456789"
    assert result.report["policy_identity"]["policy_version"] == "DP-006-POLICY-v2"


def test_2017461_in_holdout_fails_before_external_loader(tmp_path: Path) -> None:
    split_path = tmp_path / "splits.json"
    split_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "split_unit": "match",
                "development": ["dev-1"],
                "validation": ["val-1"],
                "holdout": ["2017461"],
                "status": "ready_for_promotion_review",
                "reason": "counterexample",
            }
        ),
        encoding="utf-8",
    )
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("external loader must not be called")

    with pytest.raises(PolicyError, match="development-only"):
        run_external_evaluation(
            config_path=ROOT / "configs" / "external-skillcorner.json",
            state_config_path=ROOT / "configs" / "state-engine.json",
            splits_path=split_path,
            external_root=tmp_path / "external",
            split="holdout",
            mode=EvaluationMode.PROMOTION,
            code_commit="fixture",
            policy_path=write_allowed_policy(tmp_path),
            holdout_manifest_path=ROOT / "configs" / "policy" / "holdout-manifest-v2.json",
            ledger_dir=tmp_path / "ledger",
            match_loader=forbidden_loader,
        )
    assert calls == 0


def test_holdout_freeze_mismatch_fails_before_external_loader(tmp_path: Path) -> None:
    config_path = tmp_path / "external.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "provider": "skillcorner",
                "repository": "fixture",
                "commit": "4340d274572876239c154c90bc507a9b3250a656",
                "repository_software_license": "MIT",
                "data_license_status": "HOLD",
                "data_license_evidence": ["EV-AUTH-SC-LICENSE"],
                "license_file": "LICENSE",
                "license_sha256": "a" * 64,
                "readme_sha256": "b" * 64,
                "retrieval_date": "2026-11-08",
                "match_id": "holdout-1",
                "fps": 10,
                "home_team_id": 1,
                "away_team_id": 2,
                "pitch_length_m": 105.0,
                "pitch_width_m": 68.0,
                "coordinate_convention": "metres-center-origin",
                "files": {
                    "tracking": {"path": "tracking.jsonl", "sha256": "c" * 64},
                    "phases": {"path": "phases.csv", "sha256": "d" * 64},
                    "match": {"path": "match.json", "sha256": "e" * 64},
                },
            }
        ),
        encoding="utf-8",
    )
    split_path = tmp_path / "splits.json"
    split_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "split_unit": "match",
                "development": ["dev-1"],
                "validation": ["val-1"],
                "holdout": ["holdout-1"],
                "status": "ready_for_promotion_review",
                "reason": "counterexample",
            }
        ),
        encoding="utf-8",
    )
    holdout_path = tmp_path / "holdout.json"
    holdout_path.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "status": "sealed",
                "matches": ["holdout-1"],
                "model_freeze_sha256": "0" * 64,
                "feature_set_sha256": "0" * 64,
                "config_freeze_sha256": "0" * 64,
                "hyperparameter_set_sha256": "0" * 64,
                "evaluation_script_sha256": "0" * 64,
                "metric_contract_version": "0",
                "unseal_log": [],
            }
        ),
        encoding="utf-8",
    )
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("external loader must not be called")

    with pytest.raises(PolicyError, match="does not match"):
        run_external_evaluation(
            config_path=config_path,
            state_config_path=ROOT / "configs" / "state-engine.json",
            splits_path=split_path,
            external_root=tmp_path / "external",
            split="holdout",
            mode=EvaluationMode.PROMOTION,
            code_commit="fixture",
            policy_path=write_allowed_policy(tmp_path),
            holdout_manifest_path=holdout_path,
            ledger_dir=tmp_path / "ledger",
            match_loader=forbidden_loader,
        )
    assert calls == 0


def test_skillcorner_hold_fails_before_external_loader(tmp_path: Path) -> None:
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("external loader must not be called")

    with pytest.raises(PolicyError, match="is not allowed"):
        run_external_evaluation(
            config_path=ROOT / "configs" / "external-skillcorner.json",
            state_config_path=ROOT / "configs" / "state-engine.json",
            splits_path=ROOT / "configs" / "external-splits.json",
            external_root=tmp_path / "external",
            split="development",
            mode=EvaluationMode.DIAGNOSTIC,
            code_commit="fixture",
            match_loader=forbidden_loader,
        )
    assert calls == 0


@pytest.mark.parametrize(
    ("use", "message"),
    [
        ("tracking_model_input", "tracking_model_input"),
        ("phase_model_input", "phase_model_input"),
    ],
)
def test_model_input_hold_blocks_before_loader(
    tmp_path: Path,
    use: str,
    message: str,
) -> None:
    policy_path = write_allowed_policy(tmp_path)
    values = json.loads(policy_path.read_text(encoding="utf-8"))
    values["providers"][0]["uses"][use]["status"] = "HOLD"
    policy_path.write_text(json.dumps(values), encoding="utf-8")
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("external loader must not be called")

    with pytest.raises(PolicyError, match=message):
        run_external_evaluation(
            config_path=ROOT / "configs" / "external-skillcorner.json",
            state_config_path=ROOT / "configs" / "state-engine.json",
            splits_path=ROOT / "configs" / "external-splits.json",
            external_root=tmp_path / "external",
            split="development",
            mode=EvaluationMode.DIAGNOSTIC,
            code_commit="fixture",
            policy_path=policy_path,
            match_loader=forbidden_loader,
        )
    assert calls == 0


def test_label_profile_hold_blocks_before_loader(tmp_path: Path) -> None:
    policy_path = write_allowed_policy(tmp_path)
    values = json.loads(policy_path.read_text(encoding="utf-8"))
    phase_profile = next(
        profile
        for profile in values["providers"][0]["label_profiles"]
        if profile["provider_label_definition_id"] == "skillcorner_phases_v1"
    )
    phase_profile["status"] = "HOLD"
    policy_path.write_text(json.dumps(values), encoding="utf-8")
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("external loader must not be called")

    with pytest.raises(PolicyError, match="label profile"):
        run_external_evaluation(
            config_path=ROOT / "configs" / "external-skillcorner.json",
            state_config_path=ROOT / "configs" / "state-engine.json",
            splits_path=ROOT / "configs" / "external-splits.json",
            external_root=tmp_path / "external",
            split="development",
            mode=EvaluationMode.DIAGNOSTIC,
            code_commit="fixture",
            policy_path=policy_path,
            match_loader=forbidden_loader,
        )
    assert calls == 0
