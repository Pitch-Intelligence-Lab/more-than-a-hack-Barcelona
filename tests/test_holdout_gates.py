import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import mtah_possession.evaluation.runner as runner_module
from mtah_possession.algorithm_config import load_algorithm_config
from mtah_possession.data.neutral import ProxyTarget
from mtah_possession.evaluation.external import (
    ExternalCandidateResult,
    ExternalMatchEvaluation,
    evaluate_predictions,
)
from mtah_possession.evaluation.runner import run_external_evaluation
from mtah_possession.evaluation.splits import EvaluationMode
from mtah_possession.governance.artifacts import compute_freeze_hashes
from mtah_possession.governance.ledger import (
    HoldoutLedgerState,
    LedgerEvent,
    create_ledger,
    load_existing_ledger,
    reduce_holdout_state,
)
from mtah_possession.governance.policy import PolicyError
from mtah_possession.validation.submission import sha256_file

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "4340d274572876239c154c90bc507a9b3250a656"


def allowed_policy(tmp_path: Path) -> Path:
    values = json.loads(
        (ROOT / "configs" / "policy" / "external-data-policy-v2.json").read_text(encoding="utf-8")
    )
    provider = values["providers"][0]
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
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


def artifact_spec(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    artifact_root = tmp_path / "artifacts"
    paths = {
        "model": artifact_root / "model.py",
        "feature_set": artifact_root / "features.py",
        "configuration": artifact_root / "state.json",
        "hyperparameters": artifact_root / "hyperparameters.json",
        "evaluation_script": artifact_root / "evaluate.py",
        "metric_contract": artifact_root / "contract.md",
    }
    artifact_root.mkdir(exist_ok=True)
    for name, path in paths.items():
        path.write_text(f"{name}=1\n", encoding="utf-8")
    spec = {
        "schema_version": "1.0",
        "artifact_root": "artifacts",
        "artifacts": {name: [path.name] for name, path in paths.items()},
        "metric_contract_version": "1.1.0",
    }
    spec_path = tmp_path / "freeze.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    return spec_path, paths


def external_config(tmp_path: Path, match_id: str = "holdout-1") -> Path:
    path = tmp_path / "external.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "provider": "skillcorner",
                "repository": "fixture",
                "commit": SOURCE_REVISION,
                "repository_software_license": "MIT",
                "data_license_status": "HOLD",
                "data_license_evidence": ["EV-AUTH-SC-LICENSE"],
                "license_file": "LICENSE",
                "license_sha256": "a" * 64,
                "readme_sha256": "b" * 64,
                "retrieval_date": "2026-11-08",
                "match_id": match_id,
                "fps": 10,
                "home_team_id": 1,
                "away_team_id": 2,
                "pitch_length_m": 105.0,
                "pitch_width_m": 68.0,
                "coordinate_convention": "metres-center-origin",
                "files": {
                    "tracking": {"path": "tracking", "sha256": "c" * 64},
                    "phases": {"path": "phases", "sha256": "d" * 64},
                    "match": {"path": "match", "sha256": "e" * 64},
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def split_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "splits.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "split_unit": "match",
                "development": ["dev-1"],
                "validation": ["val-1"],
                "holdout": ["holdout-1"],
                "status": "ready_for_promotion_review",
                "reason": "synthetic promotion",
            }
        ),
        encoding="utf-8",
    )
    return path


def holdout_manifest(tmp_path: Path, freeze, matches: list[str]) -> Path:
    path = tmp_path / "holdout.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "status": "sealed",
                "matches": matches,
                "model_freeze_sha256": freeze.model,
                "feature_set_sha256": freeze.feature_set,
                "config_freeze_sha256": freeze.configuration,
                "hyperparameter_set_sha256": freeze.hyperparameters,
                "evaluation_script_sha256": freeze.evaluation_script,
                "metric_contract_version": freeze.metric_contract_version,
                "unseal_log": [],
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        (["../outside.py"], "escapes the artifact root"),
        (["missing.py"], "missing or unreadable"),
        ([], "non-empty path list"),
    ],
)
def test_freeze_spec_rejects_unsafe_or_incomplete_artifacts(
    tmp_path: Path,
    replacement: list[str],
    message: str,
) -> None:
    spec_path, _paths = artifact_spec(tmp_path)
    values = json.loads(spec_path.read_text(encoding="utf-8"))
    values["artifacts"]["model"] = replacement
    spec_path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(PolicyError, match=message):
        compute_freeze_hashes(spec_path)


def fake_evaluator(_match, _config, *, authorization, split: str):
    assert authorization.freeze_hashes is not None
    target = np.asarray(list("HHAA"), dtype="<U1")
    metrics = evaluate_predictions(
        target,
        target,
        fps=10,
        transition_tolerance_frames=0,
    )
    candidate = ExternalCandidateResult(
        name="fixture",
        labels=target,
        sources=np.asarray(["fixture"] * 4),
        metrics=metrics,
    )
    proxy = ProxyTarget(
        labels=target,
        sources=np.asarray(["fixture"] * 4),
        counts={"H": 2, "A": 2, "D": 0, "X": 0},
        source_counts={"fixture": 4},
    )
    return ExternalMatchEvaluation(
        match_id="holdout-1",
        split=split,
        proxy=proxy,
        candidates={"fixture": candidate},
        source_checksums={"tracking": "fixture"},
        external_aggregate={},
    )


def prepare_promotion(
    tmp_path: Path,
    *,
    holdout_matches: list[str] | None = None,
    holdout_status: str = "PASS",
    modify_after_freeze: Path | None = None,
) -> dict:
    spec_path, artifact_paths = artifact_spec(tmp_path)
    freeze = compute_freeze_hashes(spec_path)
    if modify_after_freeze is not None:
        modify_after_freeze.write_text("changed\n", encoding="utf-8")
    holdout_path = holdout_manifest(
        tmp_path,
        freeze,
        ["holdout-1"] if holdout_matches is None else holdout_matches,
    )
    policy_path = allowed_policy(tmp_path)
    values = json.loads(policy_path.read_text(encoding="utf-8"))
    values["providers"][0]["statuses"]["HOLDOUT_SEAL_VERIFIED"] = holdout_status
    policy_path.write_text(json.dumps(values), encoding="utf-8")
    return {
        "config_path": external_config(tmp_path),
        "splits_path": split_manifest(tmp_path),
        "policy_path": policy_path,
        "holdout_path": holdout_path,
        "freeze_spec_path": spec_path,
        "ledger_dir": tmp_path / "ledger",
        "code_commit": "abcdef0123456789abcdef0123456789abcdef01",
    }


def run_prepared_promotion(fixture: dict, *, loader=None):
    match = SimpleNamespace(
        match_id="holdout-1",
        fps=10,
        source_checksums={"tracking": "fixture"},
        source_metadata={"tracking_aggregate": {}},
    )
    return run_external_evaluation(
        config_path=fixture["config_path"],
        state_config_path=ROOT / "configs" / "state-engine.json",
        splits_path=fixture["splits_path"],
        external_root=fixture["ledger_dir"].parent / "external",
        split="holdout",
        mode=EvaluationMode.PROMOTION,
        code_commit=fixture["code_commit"],
        policy_path=fixture["policy_path"],
        holdout_manifest_path=fixture["holdout_path"],
        freeze_spec_path=fixture["freeze_spec_path"],
        ledger_dir=fixture["ledger_dir"],
        match_loader=loader or (lambda *_args: match),
        state_config_loader=lambda _path: load_algorithm_config(
            ROOT / "configs" / "state-engine.json"
        ),
    )


def run_promotion(
    tmp_path: Path,
    *,
    holdout_matches: list[str] | None = None,
    holdout_status: str = "PASS",
    modify_after_freeze: Path | None = None,
    loader=None,
):
    fixture = prepare_promotion(
        tmp_path,
        holdout_matches=holdout_matches,
        holdout_status=holdout_status,
        modify_after_freeze=modify_after_freeze,
    )
    return run_prepared_promotion(fixture, loader=loader)


def test_holtl01_holdout_seal_hold_blocks_before_loader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="HOLDOUT_SEAL_VERIFIED=HOLD"):
        run_promotion(
            tmp_path,
            holdout_status="HOLD",
            loader=forbidden_loader,
        )
    assert calls == 0


def test_holtl02_empty_holdout_matches_fail_before_loader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="match set is empty"):
        run_promotion(tmp_path, holdout_matches=[], loader=forbidden_loader)
    assert calls == 0


def test_holtl03_wrong_match_and_split_mismatch_fail_before_loader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="do not equal split"):
        run_promotion(
            tmp_path,
            holdout_matches=["other-match"],
            loader=forbidden_loader,
        )
    assert calls == 0


def test_holtl04_actual_artifact_change_is_compromised_before_loader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changed = tmp_path / "artifacts" / "state.json"
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="does not match"):
        run_promotion(
            tmp_path,
            modify_after_freeze=changed,
            loader=forbidden_loader,
        )
    assert calls == 0
    records = [
        json.loads(line)
        for path in (tmp_path / "ledger").glob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert any(record["event_type"] == "COMPROMISED" for record in records)


def test_holtl05_unseal_and_result_are_persisted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    result = run_promotion(tmp_path)
    paths = list((tmp_path / "ledger").glob("*.jsonl"))
    assert len(paths) == 1
    records = [json.loads(line) for line in paths[0].read_text(encoding="utf-8").splitlines()]
    events = [record["event_type"] for record in records]
    assert events == [
        "SEALED_VERIFIED",
        "UNSEALED",
        "EVALUATION_STARTED",
        "EVALUATION_COMPLETED",
    ]
    assert records[-1]["prediction_sha256"]
    assert records[1]["freeze_hashes"] == records[-1]["freeze_hashes"]
    assert result.report["provenance"]["report_sha256"]


def test_sm01_authorization_denial_does_not_compromise_holdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_promotion(tmp_path, holdout_status="HOLD")
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="HOLDOUT_SEAL_VERIFIED=HOLD"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    records = _ledger_records(fixture["ledger_dir"])
    assert [record["event_type"] for record in records] == ["AUTHORIZATION_DENIED"]
    assert "COMPROMISED" not in {record["event_type"] for record in records}
    ledger = load_existing_ledger(
        fixture["ledger_dir"],
        provider="skillcorner",
        match_ids=("holdout-1",),
    )
    assert ledger.state == HoldoutLedgerState.SEALED


def test_sm02_existing_compromised_is_terminal_before_loader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_promotion(tmp_path)
    ledger = _new_ledger(fixture)
    ledger.append(LedgerEvent.COMPROMISED, reason="explicit contamination")
    before = ledger.path.read_text(encoding="utf-8")
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="permanently COMPROMISED"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    assert ledger.path.read_text(encoding="utf-8") == before
    assert ledger.state == HoldoutLedgerState.COMPROMISED


def test_sm03_manifest_change_does_not_reset_compromised_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_promotion(tmp_path)
    ledger = _new_ledger(fixture)
    ledger.append(LedgerEvent.COMPROMISED, reason="result used for model selection")
    original_path = ledger.path
    values = json.loads(fixture["holdout_path"].read_text(encoding="utf-8"))
    values["unseal_log"] = ["modified-after-compromise"]
    fixture["holdout_path"].write_text(json.dumps(values), encoding="utf-8")
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="permanently COMPROMISED"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    assert list(fixture["ledger_dir"].glob("*.jsonl")) == [original_path]
    assert ledger.state == HoldoutLedgerState.COMPROMISED


def test_sm04_normal_completion_reduces_to_completed_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    run_prepared_promotion(fixture)
    ledger = load_existing_ledger(
        fixture["ledger_dir"],
        provider="skillcorner",
        match_ids=("holdout-1",),
    )
    assert [record["event_type"] for record in ledger.records()] == [
        "SEALED_VERIFIED",
        "UNSEALED",
        "EVALUATION_STARTED",
        "EVALUATION_COMPLETED",
    ]
    assert ledger.state == HoldoutLedgerState.EVALUATION_COMPLETED


def test_sm05_failed_evaluation_can_retry_without_compromise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def failing_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("synthetic loader failure")

    with pytest.raises(RuntimeError, match="synthetic loader failure"):
        run_prepared_promotion(fixture, loader=failing_loader)
    records = _ledger_records(fixture["ledger_dir"])
    assert records[-1]["event_type"] == "EVALUATION_FAILED"
    assert "COMPROMISED" not in {record["event_type"] for record in records}
    run_prepared_promotion(fixture)
    records = _ledger_records(fixture["ledger_dir"])
    assert records[-2]["event_type"] == "EVALUATION_STARTED"
    assert records[-1]["event_type"] == "EVALUATION_COMPLETED"
    assert calls == 1


def test_sm06_tuning_cli_marks_completed_holdout_compromised(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    run_prepared_promotion(fixture)
    completed = _ledger_records(fixture["ledger_dir"])[-1]
    prediction_sha256 = completed["prediction_sha256"]
    assert prediction_sha256
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "mark_holdout_used_for_tuning.py"),
            "--ledger-dir",
            str(fixture["ledger_dir"]),
            "--provider",
            "skillcorner",
            "--match-id",
            "holdout-1",
            "--prediction-sha256",
            prediction_sha256,
            "--reason",
            "result used for hyperparameter tuning",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "state=COMPROMISED" in result.stdout
    records = _ledger_records(fixture["ledger_dir"])
    assert records[-1]["event_type"] == "COMPROMISED"
    assert records[-1]["prediction_sha256"] == prediction_sha256
    assert records[-1]["reason"] == "result used for hyperparameter tuning"
    before = (fixture["ledger_dir"] / f"{completed['holdout_id']}.jsonl").read_text(
        encoding="utf-8"
    )
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="permanently COMPROMISED"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    assert (fixture["ledger_dir"] / f"{completed['holdout_id']}.jsonl").read_text(
        encoding="utf-8"
    ) == before


def test_sm07_corrupt_ledger_fails_closed_without_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    run_prepared_promotion(fixture)
    path = next(fixture["ledger_dir"].glob("*.jsonl"))
    corrupted = "{not-json\n"
    path.write_text(corrupted, encoding="utf-8")
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="could not read holdout ledger"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    assert path.read_text(encoding="utf-8") == corrupted


def test_sm08_indeterminate_event_order_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_promotion(tmp_path)
    ledger = _new_ledger(fixture)
    ledger.append(LedgerEvent.SEALED_VERIFIED)
    ledger.append(LedgerEvent.UNSEALED)
    unsealed = ledger.records()[-1]
    unsealed["previous_record_sha256"] = None
    ledger.path.write_text(
        json.dumps(unsealed, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="invalid UNSEALED transition"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    with pytest.raises(PolicyError, match="invalid UNSEALED transition"):
        reduce_holdout_state(({"event_type": LedgerEvent.UNSEALED.value},))


def _new_ledger(fixture: dict):
    freeze = compute_freeze_hashes(fixture["freeze_spec_path"])
    return create_ledger(
        fixture["ledger_dir"],
        provider="skillcorner",
        match_ids=("holdout-1",),
        freeze_hashes=freeze,
        holdout_manifest_sha256=sha256_file(fixture["holdout_path"]),
        code_commit=fixture["code_commit"],
    )


def _ledger_records(ledger_dir: Path) -> list[dict]:
    paths = list(ledger_dir.glob("*.jsonl"))
    assert len(paths) == 1
    return [
        json.loads(line)
        for line in paths[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
