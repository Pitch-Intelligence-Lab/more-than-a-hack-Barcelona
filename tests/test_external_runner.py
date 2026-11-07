import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import mtah_possession.evaluation.runner as runner_module
from mtah_possession.algorithm_config import load_algorithm_config
from mtah_possession.data.neutral import ProxyTarget
from mtah_possession.evaluation.external import ExternalMatchEvaluation
from mtah_possession.evaluation.runner import run_external_evaluation
from mtah_possession.evaluation.splits import EvaluationMode, SplitManifestError
from mtah_possession.governance.policy import PolicyError

ROOT = Path(__file__).resolve().parents[1]


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
            match_loader=forbidden_loader,
        )
    assert calls == 0


def test_holdout_selection_is_used_in_report_and_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
                "reason": "synthetic promotion test",
            }
        ),
        encoding="utf-8",
    )
    policy_values = json.loads(
        (ROOT / "configs" / "policy" / "external-data-policy-v2.json").read_text(encoding="utf-8")
    )
    provider = policy_values["providers"][0]
    for axis in (
        "PUBLIC_SOURCE_VERIFIED",
        "LICENSE_VERIFIED",
        "INTERNAL_RESEARCH_AUTHORIZED",
        "EVALUATION_AUTHORIZED",
    ):
        provider["statuses"][axis] = "PASS"
    for use in ("read_preprocess", "evaluation_reference"):
        provider["uses"][use] = {
            "status": "PASS",
            "evidence_ids": ["EV-AUTH-SC-README"],
            "conditions": [],
        }
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy_values), encoding="utf-8")
    match = SimpleNamespace(
        match_id="2017461",
        fps=10,
        source_checksums={"tracking": "abc"},
        source_metadata={"tracking_aggregate": {}},
    )
    observed_split = []

    def fake_evaluator(_match, _config, *, split: str):
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
        split="holdout",
        mode=EvaluationMode.PROMOTION,
        code_commit="abcdef0123456789",
        policy_path=policy_path,
        match_loader=lambda *_args: match,
        state_config_loader=lambda _path: load_algorithm_config(
            ROOT / "configs" / "state-engine.json"
        ),
    )
    assert observed_split == ["holdout"]
    assert result.report["split"] == "holdout"
    provenance = result.report["provenance"]
    assert provenance["source_adapter_version"] == "1.1.0"
    assert provenance["evaluation_contract_version"] == "1.1.0"
    assert provenance["code_commit"] == "abcdef0123456789"
    assert result.report["policy_identity"]["policy_version"] == "DP-006-POLICY-v2"


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
