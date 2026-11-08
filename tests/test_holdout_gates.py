import hashlib
import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import mtah_possession.evaluation.runner as runner_module
import mtah_possession.governance.ledger as ledger_module
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
from mtah_possession.governance.authorization import build_governance_identity
from mtah_possession.governance.ledger import (
    HoldoutLedgerState,
    LedgerEvent,
    create_ledger,
    load_existing_ledger,
    migrate_legacy_ledger,
    reduce_holdout_state,
    sha256_path_identity,
    stable_holdout_identity,
)
from mtah_possession.governance.policy import PolicyError
from mtah_possession.governance.source import (
    build_single_source_identity_set,
    build_source_identity,
    build_source_identity_set,
)
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


def external_config(
    tmp_path: Path,
    match_id: str = "holdout-1",
    filename: str = "external.json",
) -> Path:
    path = tmp_path / filename
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
        match_id=getattr(_match, "match_id", "holdout-1"),
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
        match_id=fixture.get("match_id", "holdout-1"),
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
        source_set_path=fixture.get("source_set_path"),
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


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("status", "HOLDOUT_SEAL_VERIFIED"), "HOLDOUT_SEAL_VERIFIED=HOLD"),
        (("use", "evaluation_reference"), "evaluation_reference"),
    ],
)
def test_fr01_fr02_permission_revocation_preserves_model_freeze(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: tuple[str, str],
    message: str,
) -> None:
    fixture = prepare_separated_promotion(tmp_path)
    freeze_before = compute_freeze_hashes(fixture["freeze_spec_path"])
    identity_before = build_governance_identity(
        policy_path=fixture["policy_path"],
        provider="skillcorner",
        source_revision=SOURCE_REVISION,
    )
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)

    def failing_loader(*_args, **_kwargs):
        raise RuntimeError("first attempt stops after ledger start")

    with pytest.raises(RuntimeError, match="first attempt"):
        run_prepared_promotion(fixture, loader=failing_loader)
    state_before_denial = load_existing_ledger(
        fixture["ledger_dir"],
        provider="skillcorner",
        match_ids=("holdout-1",),
    ).state

    values = json.loads(fixture["policy_path"].read_text(encoding="utf-8"))
    if change[0] == "status":
        values["providers"][0]["statuses"][change[1]] = "HOLD"
    else:
        values["providers"][0]["uses"][change[1]]["status"] = "HOLD"
    fixture["policy_path"].write_text(json.dumps(values), encoding="utf-8")

    freeze_after = compute_freeze_hashes(fixture["freeze_spec_path"])
    identity_after = build_governance_identity(
        policy_path=fixture["policy_path"],
        provider="skillcorner",
        source_revision=SOURCE_REVISION,
    )
    assert freeze_after == freeze_before
    assert identity_after.authorization_status_digest != (
        identity_before.authorization_status_digest
    )

    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match=message):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    records = _ledger_records(fixture["ledger_dir"])
    assert records[-1]["event_type"] == "AUTHORIZATION_DENIED"
    assert "COMPROMISED" not in {record["event_type"] for record in records}
    state_after_denial = load_existing_ledger(
        fixture["ledger_dir"],
        provider="skillcorner",
        match_ids=("holdout-1",),
    ).state
    assert state_after_denial == state_before_denial
    assert records[-1]["governance_identity"]["authorization_status_digest"] == (
        identity_after.authorization_status_digest
    )


def test_fr03_permission_restoration_reuses_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_separated_promotion(tmp_path)
    values = json.loads(fixture["policy_path"].read_text(encoding="utf-8"))
    values["providers"][0]["statuses"]["HOLDOUT_SEAL_VERIFIED"] = "HOLD"
    fixture["policy_path"].write_text(json.dumps(values), encoding="utf-8")
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="HOLDOUT_SEAL_VERIFIED=HOLD"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    path = next(fixture["ledger_dir"].glob("*.jsonl"))
    assert _ledger_records(fixture["ledger_dir"])[0]["event_type"] == "AUTHORIZATION_DENIED"

    values = json.loads(fixture["policy_path"].read_text(encoding="utf-8"))
    values["providers"][0]["statuses"]["HOLDOUT_SEAL_VERIFIED"] = "PASS"
    fixture["policy_path"].write_text(json.dumps(values), encoding="utf-8")
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    run_prepared_promotion(fixture)

    assert list(fixture["ledger_dir"].glob("*.jsonl")) == [path]
    records = _ledger_records(fixture["ledger_dir"])
    assert records[0]["event_type"] == "AUTHORIZATION_DENIED"
    assert [record["event_type"] for record in records[1:]] == [
        "SEALED_VERIFIED",
        "UNSEALED",
        "EVALUATION_STARTED",
        "EVALUATION_COMPLETED",
    ]
    assert "COMPROMISED" not in {record["event_type"] for record in records}


def test_fr04_predictive_artifact_change_changes_freeze_and_compromises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_separated_promotion(tmp_path)
    freeze_before = compute_freeze_hashes(fixture["freeze_spec_path"])
    artifact_paths = fixture["artifact_paths"]
    artifact_paths["prediction_code"].write_text("prediction=2\n", encoding="utf-8")
    freeze_after = compute_freeze_hashes(fixture["freeze_spec_path"])
    assert freeze_after.model != freeze_before.model
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="does not match"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    records = _ledger_records(fixture["ledger_dir"])
    assert [record["event_type"] for record in records] == ["COMPROMISED"]


def test_fr05_governance_code_change_does_not_change_model_freeze(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_separated_promotion(tmp_path)
    freeze_before = compute_freeze_hashes(fixture["freeze_spec_path"])
    governance_file: Path = fixture["governance_file"]
    governance_file.write_text("decision='changed'\n", encoding="utf-8")
    freeze_after = compute_freeze_hashes(fixture["freeze_spec_path"])
    assert freeze_after == freeze_before
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    run_prepared_promotion(fixture)
    records = _ledger_records(fixture["ledger_dir"])
    assert "COMPROMISED" not in {record["event_type"] for record in records}

    real_spec = json.loads(
        (ROOT / "configs" / "policy" / "artifact-freeze-v2.json").read_text(encoding="utf-8")
    )
    paths = [path for category_paths in real_spec["artifacts"].values() for path in category_paths]
    assert not any("governance" in path for path in paths)
    assert "configs/policy/external-data-policy-v2.json" not in paths


def test_mg01_legacy_clean_ledger_is_migrated_in_place(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    records_before = _ledger_records(fixture["ledger_dir"])
    path_before = next(fixture["ledger_dir"].glob("*.jsonl"))
    holdout_id_before = records_before[0]["holdout_id"]
    ledger = _migrate_fixture(fixture)
    records = ledger.records()
    assert ledger.path == path_before
    assert ledger.holdout_id == holdout_id_before
    assert records[0] == records_before[0]
    migration = records[1]
    assert migration["event_type"] == "FREEZE_PROTOCOL_MIGRATED"
    receipt = migration["migration_receipt"]
    assert receipt["legacy_combined_freeze"] == records_before[0]["freeze_hashes"]
    assert receipt["target_model_identity"]["model"] == fixture["model_freeze"].model
    assert receipt["governance_identity_digest"] == (
        fixture["governance_identity"].authorization_status_digest
    )
    assert receipt["old_code_commit"] == fixture["code_commit"]
    assert receipt["migration_commit"] == fixture["migration_commit"]
    assert receipt["approver"] == "qa-lead"
    assert ledger.state == HoldoutLedgerState.MIGRATED_AUDIT_ONLY

    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="audit-only"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0


def test_mg02_legacy_compromised_ledger_cannot_be_migrated_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_legacy_migration(tmp_path, compromised=True)
    path = next(fixture["ledger_dir"].glob("*.jsonl"))
    before = path.read_text(encoding="utf-8")
    with pytest.raises(PolicyError, match="COMPROMISED"):
        _migrate_fixture(fixture)
    assert path.read_text(encoding="utf-8") == before
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="permanently COMPROMISED"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0


def test_mg03_missing_or_tampered_migration_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = prepare_legacy_migration(tmp_path / "missing")
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="requires explicit freeze migration"):
        run_prepared_promotion(missing, loader=forbidden_loader)
    assert calls == 0

    tampered = prepare_legacy_migration(tmp_path / "tampered")
    _migrate_fixture(tampered)
    path = next(tampered["ledger_dir"].glob("*.jsonl"))
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[1]["migration_receipt"]["governance_identity_digest"] = "0" * 64
    path.write_text(
        "".join(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n" for record in records
        ),
        encoding="utf-8",
    )
    calls = 0
    with pytest.raises(PolicyError, match="governance identity digest"):
        run_prepared_promotion(tampered, loader=forbidden_loader)
    assert calls == 0


def test_migration_cli_appends_explicit_protocol_event(tmp_path: Path) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "migrate_holdout_ledger.py"),
            "--ledger-dir",
            str(fixture["ledger_dir"]),
            "--provider",
            "skillcorner",
            "--match-id",
            "holdout-1",
            "--freeze-spec",
            str(fixture["freeze_spec_path"]),
            "--policy",
            str(fixture["policy_path"]),
            "--source-revision",
            SOURCE_REVISION,
            "--source-config",
            str(fixture["config_path"]),
            "--target-holdout-manifest",
            str(fixture["holdout_path"]),
            "--split-manifest",
            str(fixture["splits_path"]),
            "--approval-receipt",
            fixture["approval_receipt_path"],
            "--approval-commit",
            fixture["approval_commit"],
            "--repo-root",
            str(fixture["repo_root"]),
            "--migration-commit",
            fixture["migration_commit"],
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    records = _ledger_records(fixture["ledger_dir"])
    assert records[-1]["event_type"] == "FREEZE_PROTOCOL_MIGRATED"
    assert records[-1]["migration_receipt"]["approver"] == "qa-lead"
    assert records[-1]["migration_receipt"]["status"] == "MIGRATED_AUDIT_ONLY"


def test_rp5_01_migrated_ledger_is_audit_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    ledger = _migrate_fixture(fixture)
    assert ledger.state == HoldoutLedgerState.MIGRATED_AUDIT_ONLY
    before = ledger.path.read_bytes()
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="audit-only"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    assert ledger.path.read_bytes() == before


def test_rp5_02_modified_model_cannot_be_migrated(
    tmp_path: Path,
) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    path = next(fixture["ledger_dir"].glob("*.jsonl"))
    before = path.read_bytes()
    fixture["artifact_paths"]["prediction_code"].write_text(
        "prediction=changed\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyError, match="worktree artifacts differ"):
        _migrate_fixture(fixture)
    assert path.read_bytes() == before


def test_rp5_03_missing_or_mismatched_migration_commit_is_rejected(
    tmp_path: Path,
) -> None:
    missing = prepare_legacy_migration(tmp_path / "missing-commit")
    path = next(missing["ledger_dir"].glob("*.jsonl"))
    before = path.read_bytes()
    with pytest.raises(PolicyError, match="Git verification failed"):
        _migrate_fixture(missing, migration_commit="f" * 40)
    assert path.read_bytes() == before

    mismatched = prepare_legacy_migration(tmp_path / "mismatched-content")
    receipt_path = mismatched["repo_root"] / mismatched["approval_receipt_path"]
    receipt_path.write_text("{}\n", encoding="utf-8")
    path = next(mismatched["ledger_dir"].glob("*.jsonl"))
    before = path.read_bytes()
    with pytest.raises(PolicyError, match="differs from the approval commit"):
        _migrate_fixture(mismatched)
    assert path.read_bytes() == before


def test_rp5_04_self_reported_target_hashes_are_not_trusted(
    tmp_path: Path,
) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    receipt_path = fixture["repo_root"] / fixture["approval_receipt_path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["target_model_identity"]["model"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    _git(fixture["repo_root"], "add", "--", fixture["approval_receipt_path"])
    _git(fixture["repo_root"], "commit", "-m", "incorrect self-reported target")
    approval_commit = _git(fixture["repo_root"], "rev-parse", "HEAD").strip()
    path = next(fixture["ledger_dir"].glob("*.jsonl"))
    before = path.read_bytes()
    with pytest.raises(PolicyError, match="target_model_identity"):
        _migrate_fixture(fixture, approval_commit=approval_commit)
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("status", "unsealed"),
        ("unseal_log", ["changed-after-seal"]),
        ("model_freeze_sha256", "0" * 64),
        ("metric_contract_version", "9.9.9:replacement"),
        ("matches", ["holdout-1", "other-match"]),
    ],
)
def test_rp5_05_manifest_change_after_seal_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement,
) -> None:
    fixture = prepare_separated_promotion(tmp_path / field)
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)

    def failing_loader(*_args, **_kwargs):
        raise RuntimeError("seal established before failure")

    with pytest.raises(RuntimeError, match="seal established"):
        run_prepared_promotion(fixture, loader=failing_loader)
    ledger_path = next(fixture["ledger_dir"].glob("*.jsonl"))
    before = ledger_path.read_bytes()
    assert _ledger_records(fixture["ledger_dir"])[0]["split_manifest_sha256"] == (
        sha256_file(fixture["splits_path"])
    )
    manifest = json.loads(fixture["holdout_path"].read_text(encoding="utf-8"))
    manifest[field] = replacement
    fixture["holdout_path"].write_text(json.dumps(manifest), encoding="utf-8")
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    assert ledger_path.read_bytes() == before


@pytest.mark.parametrize("artifact", ["evaluation_runner", "evaluation_splits"])
def test_rp5_06_rp5_07_evaluation_artifact_change_invalidates_seal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact: str,
) -> None:
    fixture = prepare_separated_promotion(tmp_path / artifact)
    first_identity = compute_freeze_hashes(fixture["freeze_spec_path"]).evaluation_script
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)

    def failing_loader(*_args, **_kwargs):
        raise RuntimeError("seal established before failure")

    with pytest.raises(RuntimeError, match="seal established"):
        run_prepared_promotion(fixture, loader=failing_loader)
    fixture["artifact_paths"][artifact].write_text("evaluation='changed'\n", encoding="utf-8")
    second_identity = compute_freeze_hashes(fixture["freeze_spec_path"]).evaluation_script
    assert second_identity != first_identity
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="freeze identity changed"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    assert "COMPROMISED" in {
        record["event_type"] for record in _ledger_records(fixture["ledger_dir"])
    }
    production_spec = json.loads(
        (ROOT / "configs" / "policy" / "artifact-freeze-v2.json").read_text(encoding="utf-8")
    )
    evaluation_paths = production_spec["artifacts"]["evaluation_script"]
    assert "src/mtah_possession/evaluation/runner.py" in evaluation_paths
    assert "src/mtah_possession/evaluation/splits.py" in evaluation_paths


def test_rp5_08_split_manifest_change_invalidates_seal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_separated_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)

    def failing_loader(*_args, **_kwargs):
        raise RuntimeError("seal established before failure")

    with pytest.raises(RuntimeError, match="seal established"):
        run_prepared_promotion(fixture, loader=failing_loader)
    ledger_path = next(fixture["ledger_dir"].glob("*.jsonl"))
    before = ledger_path.read_bytes()
    splits = json.loads(fixture["splits_path"].read_text(encoding="utf-8"))
    splits["status"] = "promoted"
    fixture["splits_path"].write_text(json.dumps(splits), encoding="utf-8")
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="changed sealed split"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    assert ledger_path.read_bytes() == before


def test_rp5_09_compromised_match_set_cannot_be_recovered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_separated_promotion(tmp_path)
    ledger = _new_ledger(fixture)
    ledger.append(LedgerEvent.COMPROMISED, reason="permanent contamination")
    with pytest.raises(PolicyError, match="COMPROMISED"):
        ledger.append(LedgerEvent.SEALED_VERIFIED)

    manifest = json.loads(fixture["holdout_path"].read_text(encoding="utf-8"))
    manifest["matches"] = ["other-match"]
    fixture["holdout_path"].write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="do not equal split"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    provider, matches, holdout_id = stable_holdout_identity(
        "skillcorner",
        ("holdout-1",),
    )
    assert provider == "skillcorner"
    assert matches == ("holdout-1",)
    assert holdout_id == ledger.holdout_id


@pytest.mark.parametrize(
    "field",
    [
        "tracking_path",
        "tracking_sha",
        "phases_path",
        "match_sha",
        "source_revision",
        "match_id",
        "fps",
        "home_team_id",
        "away_team_id",
        "pitch_length_m",
        "pitch_width_m",
        "coordinate_convention",
    ],
)
def test_r6_01_to_r6_05_source_mutation_fails_before_loader(
    tmp_path: Path,
    field: str,
) -> None:
    fixture = prepare_separated_promotion(tmp_path)

    def failing_loader(*_args, **_kwargs):
        raise RuntimeError("source seal established")

    with pytest.raises(RuntimeError, match="source seal"):
        run_prepared_promotion(fixture, loader=failing_loader)
    ledger_path = next(fixture["ledger_dir"].glob("*.jsonl"))
    before = ledger_path.read_bytes()
    source_before = build_source_identity(fixture["config_path"])
    freeze_before = compute_freeze_hashes(fixture["freeze_spec_path"])
    values = json.loads(fixture["config_path"].read_text(encoding="utf-8"))
    if field == "tracking_path":
        values["files"]["tracking"]["path"] = "different-tracking-file.jsonl"
    elif field == "tracking_sha":
        values["files"]["tracking"]["sha256"] = "f" * 64
    elif field == "phases_path":
        values["files"]["phases"]["path"] = "different-phases.csv"
    elif field == "match_sha":
        values["files"]["match"]["sha256"] = "9" * 64
    elif field == "source_revision":
        values["commit"] = "1" * 40
    elif field == "match_id":
        values["match_id"] = "other-match"
    elif field == "fps":
        values["fps"] = 11
    elif field == "home_team_id":
        values["home_team_id"] = 9
    elif field == "away_team_id":
        values["away_team_id"] = 10
    elif field == "pitch_length_m":
        values["pitch_length_m"] = 106.0
    elif field == "pitch_width_m":
        values["pitch_width_m"] = 69.0
    elif field == "coordinate_convention":
        values["coordinate_convention"] = "different-convention"
    fixture["config_path"].write_text(json.dumps(values), encoding="utf-8")
    assert compute_freeze_hashes(fixture["freeze_spec_path"]) == freeze_before
    if field != "coordinate_convention":
        source_after = build_source_identity(fixture["config_path"])
        assert source_after.source_identity_sha256 != source_before.source_identity_sha256
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(ValueError):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    assert ledger_path.read_bytes() == before


def test_r6_06_same_source_can_retry_after_evaluation_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_separated_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)

    def failing_loader(*_args, **_kwargs):
        raise RuntimeError("retryable source evaluation failure")

    with pytest.raises(RuntimeError, match="retryable"):
        run_prepared_promotion(fixture, loader=failing_loader)
    run_prepared_promotion(fixture)
    records = _ledger_records(fixture["ledger_dir"])
    assert (
        records[0]["source_identity"]["source_identity_sha256"]
        == (records[1]["source_identity"]["source_identity_sha256"])
    )
    assert "COMPROMISED" not in {record["event_type"] for record in records}
    assert records[-1]["event_type"] == "EVALUATION_COMPLETED"


def test_r6_07_uncommitted_model_with_new_receipt_rejected(
    tmp_path: Path,
) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    fixture["artifact_paths"]["prediction_code"].write_text(
        "prediction=uncommitted-change\n",
        encoding="utf-8",
    )
    changed = compute_freeze_hashes(fixture["freeze_spec_path"])
    receipt_path = fixture["repo_root"] / fixture["approval_receipt_path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["target_model_identity"]["model"] = changed.model
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    approval_commit = _commit_current_receipt(fixture, fixture["migration_commit"])
    path = next(fixture["ledger_dir"].glob("*.jsonl"))
    before = path.read_bytes()
    with pytest.raises(PolicyError, match="migration commit artifacts"):
        _migrate_fixture(fixture, approval_commit=approval_commit)
    assert path.read_bytes() == before


def test_r6_08_receipt_artifact_mismatch_rejected(
    tmp_path: Path,
) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    receipt_path = fixture["repo_root"] / fixture["approval_receipt_path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["target_evaluation_identity"]["evaluation_script"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    approval_commit = _commit_current_receipt(fixture, fixture["migration_commit"])
    path = next(fixture["ledger_dir"].glob("*.jsonl"))
    before = path.read_bytes()
    with pytest.raises(PolicyError, match="migration commit artifacts"):
        _migrate_fixture(fixture, approval_commit=approval_commit)
    assert path.read_bytes() == before


def test_r6_09_missing_migration_commit_artifact_rejected(
    tmp_path: Path,
) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    _git(fixture["repo_root"], "rm", "--", "model-artifacts/prediction/model.py")
    _git(fixture["repo_root"], "commit", "-m", "remove target artifact")
    missing_commit = _git(fixture["repo_root"], "rev-parse", "HEAD").strip()
    receipt_path = fixture["repo_root"] / fixture["approval_receipt_path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["migration_commit"] = missing_commit
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    approval_commit = _commit_current_receipt(fixture, missing_commit)
    path = next(fixture["ledger_dir"].glob("*.jsonl"))
    before = path.read_bytes()
    with pytest.raises(PolicyError, match="missing|migration commit"):
        _migrate_fixture(
            fixture,
            approval_commit=approval_commit,
            migration_commit=missing_commit,
        )
    assert path.read_bytes() == before


def test_r6_10_approval_commit_must_descend_from_migration(
    tmp_path: Path,
) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    receipt_path = fixture["repo_root"] / fixture["approval_receipt_path"]
    _git(fixture["repo_root"], "add", "--", fixture["approval_receipt_path"])
    tree = _git(fixture["repo_root"], "write-tree").strip()
    side_approval = _git(
        fixture["repo_root"],
        "commit-tree",
        tree,
        "-m",
        "unrelated approval",
    ).strip()
    with pytest.raises(PolicyError, match="not an ancestor"):
        _migrate_fixture(fixture, approval_commit=side_approval)
    assert receipt_path.exists()


def test_r6_11_old_code_commit_must_relate_to_migration(
    tmp_path: Path,
) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    _git(fixture["repo_root"], "add", "--", fixture["approval_receipt_path"])
    tree = _git(fixture["repo_root"], "write-tree").strip()
    unrelated = _git(
        fixture["repo_root"],
        "commit-tree",
        tree,
        "-m",
        "unrelated old candidate",
    ).strip()
    ledger_path = next(fixture["ledger_dir"].glob("*.jsonl"))
    record = json.loads(ledger_path.read_text(encoding="utf-8"))
    record["code_commit"] = unrelated
    ledger_path.write_text(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    receipt_path = fixture["repo_root"] / fixture["approval_receipt_path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["old_code_commit"] = unrelated
    receipt["source_ledger_head_sha256"] = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    receipt["previous_record_sha256"] = _test_record_sha256(record)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    approval_commit = _commit_current_receipt(
        fixture,
        fixture["migration_commit"],
    )
    with pytest.raises(PolicyError, match="old code commit"):
        _migrate_fixture(fixture, approval_commit=approval_commit)


def test_r6_12_audit_only_migration_never_promotes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    ledger = _migrate_fixture(fixture)
    assert ledger.state == HoldoutLedgerState.MIGRATED_AUDIT_ONLY
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="audit-only"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0


def test_rc01_wrong_old_manifest_sha_leaves_ledger_unchanged(
    tmp_path: Path,
) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    receipt_path = fixture["repo_root"] / fixture["approval_receipt_path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["old_holdout_manifest_sha256"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    approval_commit = _commit_current_receipt(fixture, fixture["migration_commit"])
    ledger_path = next(fixture["ledger_dir"].glob("*.jsonl"))
    before = ledger_path.read_bytes()
    with pytest.raises(PolicyError, match="old_holdout_manifest"):
        _migrate_fixture(fixture, approval_commit=approval_commit)
    assert ledger_path.read_bytes() == before


def test_rc02_protocol_order_failure_does_not_write(tmp_path: Path) -> None:
    fixture = prepare_promotion(tmp_path)
    ledger = _new_ledger(fixture)
    ledger.append(LedgerEvent.SEALED_VERIFIED)
    head = ledger_module._record_sha256(ledger.records()[-1])
    before = ledger.path.read_bytes()
    receipt_fixture = prepare_legacy_migration(tmp_path / "receipt")
    receipt = json.loads(
        (receipt_fixture["repo_root"] / receipt_fixture["approval_receipt_path"]).read_text(
            encoding="utf-8"
        )
    )
    with pytest.raises(PolicyError, match="newer freeze protocol"):
        ledger.append_freeze_migration(
            migration_receipt=receipt,
            expected_head_sha256=head,
        )
    assert ledger.path.read_bytes() == before


def test_rc03_illegal_state_failure_does_not_write(tmp_path: Path) -> None:
    fixture = prepare_legacy_migration(tmp_path, compromised=True)
    ledger_path = next(fixture["ledger_dir"].glob("*.jsonl"))
    before = ledger_path.read_bytes()
    with pytest.raises(PolicyError, match="COMPROMISED"):
        _migrate_fixture(fixture)
    assert ledger_path.read_bytes() == before


def test_rc04_candidate_seal_invariant_failure_does_not_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    ledger_path = next(fixture["ledger_dir"].glob("*.jsonl"))
    before = ledger_path.read_bytes()

    def reject_candidate(_records):
        raise PolicyError("candidate seal invariant violation")

    monkeypatch.setattr(ledger_module, "_validate_seal_immutability", reject_candidate)
    with pytest.raises(PolicyError, match="candidate seal"):
        _migrate_fixture(fixture)
    assert ledger_path.read_bytes() == before


def test_rc05_stale_ledger_head_does_not_overwrite_concurrent_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    ledger_path = next(fixture["ledger_dir"].glob("*.jsonl"))
    existing = json.loads(ledger_path.read_text(encoding="utf-8"))
    concurrent = {
        **existing,
        "recorded_at": "2026-11-08T00:01:00+00:00",
        "event_type": "AUTHORIZATION_DENIED",
        "prediction_sha256": None,
        "previous_record_sha256": _test_record_sha256(existing),
        "reason": "concurrent authorization denial",
    }
    original_lock = ledger_module._ledger_lock
    injected = False

    @contextmanager
    def racing_lock(path):
        nonlocal injected
        if not injected and Path(path) == ledger_path:
            with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(concurrent, sort_keys=True, separators=(",", ":")) + "\n")
            injected = True
        with original_lock(path):
            yield

    monkeypatch.setattr(ledger_module, "_ledger_lock", racing_lock)
    with pytest.raises(PolicyError, match="head changed"):
        _migrate_fixture(fixture)
    records = _ledger_records(fixture["ledger_dir"])
    assert [record["event_type"] for record in records] == [
        "SEALED_VERIFIED",
        "AUTHORIZATION_DENIED",
    ]
    assert records[-1]["reason"] == "concurrent authorization denial"


def test_rc06_atomic_write_failure_leaves_no_partial_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_legacy_migration(tmp_path)
    ledger_path = next(fixture["ledger_dir"].glob("*.jsonl"))
    before = ledger_path.read_bytes()

    def fail_replace(_path, _payload):
        raise PolicyError("simulated atomic replace failure")

    monkeypatch.setattr(ledger_module, "_atomic_replace", fail_replace)
    with pytest.raises(PolicyError, match="atomic replace"):
        _migrate_fixture(fixture)
    assert ledger_path.read_bytes() == before
    assert len(ledger_path.read_text(encoding="utf-8").splitlines()) == 1


def test_rc07_two_match_source_set_allows_both_matches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = prepare_multi_source_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    first = {
        **base,
        "config_path": base["source_1"],
        "match_id": "holdout-1",
        "ledger_dir": tmp_path / "ledger-1",
    }
    second = {
        **base,
        "config_path": base["source_2"],
        "match_id": "holdout-2",
        "ledger_dir": tmp_path / "ledger-2",
    }
    run_prepared_promotion(first)
    run_prepared_promotion(second)
    source_set = build_source_identity_set(
        base["source_set_path"],
        provider="skillcorner",
        holdout_matches=("holdout-1", "holdout-2"),
    )
    assert set(source_set.identity_digests) == {"holdout-1", "holdout-2"}
    nested = tmp_path / "nested-descriptor"
    nested.mkdir()
    repository_relative = write_source_set_descriptor(
        tmp_path,
        json.loads(base["source_set_path"].read_text(encoding="utf-8"))["members"],
        filename="nested-descriptor/source-set.json",
    )
    assert (
        build_source_identity_set(
            repository_relative,
            provider="skillcorner",
            holdout_matches=("holdout-1", "holdout-2"),
            source_root=tmp_path,
        )
        == source_set
    )
    assert len(_ledger_records(first["ledger_dir"])) == 4
    assert len(_ledger_records(second["ledger_dir"])) == 4


def test_rc08_unknown_match_is_rejected_without_loader(
    tmp_path: Path,
) -> None:
    base = prepare_multi_source_promotion(tmp_path)
    unknown_config = external_config(tmp_path, "holdout-3", "source-3.json")
    fixture = {
        **base,
        "config_path": unknown_config,
        "match_id": "holdout-3",
        "ledger_dir": tmp_path / "ledger-unknown",
    }
    split_values = json.loads(fixture["splits_path"].read_text(encoding="utf-8"))
    split_values["holdout"].append("holdout-3")
    fixture["splits_path"].write_text(json.dumps(split_values), encoding="utf-8")
    holdout_values = json.loads(fixture["holdout_path"].read_text(encoding="utf-8"))
    holdout_values["matches"].append("holdout-3")
    fixture["holdout_path"].write_text(json.dumps(holdout_values), encoding="utf-8")
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0


def test_rc09_member_add_or_remove_is_rejected(tmp_path: Path) -> None:
    base = prepare_multi_source_promotion(tmp_path)
    source_3 = external_config(tmp_path, "holdout-3", "source-3.json")
    original = json.loads(base["source_set_path"].read_text(encoding="utf-8"))
    for members, filename in (
        (original["members"][:1], "source-set-removed.json"),
        (
            original["members"] + [{"match_id": "holdout-3", "source_config": source_3.name}],
            "source-set-added.json",
        ),
    ):
        path = write_source_set_descriptor(tmp_path, members, filename=filename)
        with pytest.raises(PolicyError, match="do not equal"):
            build_source_identity_set(
                path,
                provider="skillcorner",
                holdout_matches=("holdout-1", "holdout-2"),
            )


def test_rc10_swapped_match_identity_mapping_is_rejected(tmp_path: Path) -> None:
    base = prepare_multi_source_promotion(tmp_path)
    swapped = write_source_set_descriptor(
        tmp_path,
        [
            {"match_id": "holdout-1", "source_config": base["source_2"].name},
            {"match_id": "holdout-2", "source_config": base["source_1"].name},
        ],
        filename="source-set-swapped.json",
    )
    with pytest.raises(PolicyError, match="identity does not match"):
        build_source_identity_set(
            swapped,
            provider="skillcorner",
            holdout_matches=("holdout-1", "holdout-2"),
        )


def test_rc11_duplicate_match_id_is_rejected(tmp_path: Path) -> None:
    base = prepare_multi_source_promotion(tmp_path)
    duplicate = write_source_set_descriptor(
        tmp_path,
        [
            {"match_id": "holdout-1", "source_config": base["source_1"].name},
            {"match_id": "holdout-1", "source_config": base["source_2"].name},
        ],
        filename="source-set-duplicate.json",
    )
    with pytest.raises(PolicyError, match="duplicate"):
        build_source_identity_set(
            duplicate,
            provider="skillcorner",
            holdout_matches=("holdout-1", "holdout-2"),
        )


def test_rc12_post_seal_member_addition_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_multi_source_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)

    def failing_loader(*_args, **_kwargs):
        raise RuntimeError("seal established")

    with pytest.raises(RuntimeError, match="seal established"):
        run_prepared_promotion(fixture, loader=failing_loader)
    ledger_path = next(fixture["ledger_dir"].glob("*.jsonl"))
    before = ledger_path.read_bytes()
    source_3 = external_config(tmp_path, "holdout-3", "source-3.json")
    members = json.loads(fixture["source_set_path"].read_text(encoding="utf-8"))["members"]
    fixture["source_set_path"] = write_source_set_descriptor(
        tmp_path,
        members + [{"match_id": "holdout-3", "source_config": source_3.name}],
        filename="source-set-appended.json",
    )
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="do not equal"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    assert ledger_path.read_bytes() == before


@pytest.mark.parametrize(
    "field",
    ["data_license_status", "data_license_evidence"],
)
def test_rc14_rc15_governance_fields_do_not_change_source_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    fixture = prepare_separated_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    source_before = build_source_identity(fixture["config_path"])
    values = json.loads(fixture["config_path"].read_text(encoding="utf-8"))
    if field == "data_license_status":
        values[field] = "PASS"
    else:
        values[field] = ["EV-GOVERNANCE-ONLY"]
    fixture["config_path"].write_text(json.dumps(values), encoding="utf-8")
    source_after = build_source_identity(fixture["config_path"])
    assert source_after == source_before


def test_rc16_governance_reauthorizes_after_permission_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_separated_promotion(tmp_path)
    values = json.loads(fixture["policy_path"].read_text(encoding="utf-8"))
    values["providers"][0]["statuses"]["HOLDOUT_SEAL_VERIFIED"] = "HOLD"
    fixture["policy_path"].write_text(json.dumps(values), encoding="utf-8")
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="HOLDOUT_SEAL_VERIFIED=HOLD"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    values["providers"][0]["statuses"]["HOLDOUT_SEAL_VERIFIED"] = "PASS"
    fixture["policy_path"].write_text(json.dumps(values), encoding="utf-8")
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    run_prepared_promotion(fixture)
    records = _ledger_records(fixture["ledger_dir"])
    assert records[0]["event_type"] == "AUTHORIZATION_DENIED"
    assert records[-1]["event_type"] == "EVALUATION_COMPLETED"


def test_rc17_real_source_change_changes_identity_and_blocks_loader(
    tmp_path: Path,
) -> None:
    fixture = prepare_separated_promotion(tmp_path)

    def failing_loader(*_args, **_kwargs):
        raise RuntimeError("seal established")

    with pytest.raises(RuntimeError, match="seal established"):
        run_prepared_promotion(fixture, loader=failing_loader)
    before = build_source_identity(fixture["config_path"])
    values = json.loads(fixture["config_path"].read_text(encoding="utf-8"))
    values["files"]["phases"]["sha256"] = "7" * 64
    fixture["config_path"].write_text(json.dumps(values), encoding="utf-8")
    after = build_source_identity(fixture["config_path"])
    assert after.source_identity_sha256 != before.source_identity_sha256
    ledger_path = next(fixture["ledger_dir"].glob("*.jsonl"))
    ledger_before = ledger_path.read_bytes()
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="Source Identity"):
        run_prepared_promotion(fixture, loader=forbidden_loader)
    assert calls == 0
    assert ledger_path.read_bytes() == ledger_before


def test_rc13_single_match_source_set_remains_compatible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_separated_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    run_prepared_promotion(fixture)
    record = _ledger_records(fixture["ledger_dir"])[0]
    assert set(record["source_identity_set"]["source_identity_map"]) == {"holdout-1"}
    assert record["event_type"] == "SEALED_VERIFIED"


def _migrate_fixture(
    fixture: dict,
    *,
    approval_commit: str | None = None,
    migration_commit: str | None = None,
    approval_receipt_path: str | None = None,
    repo_root: Path | None = None,
    source_set_path: Path | None = None,
):
    return migrate_legacy_ledger(
        fixture["ledger_dir"],
        repo_root=repo_root or fixture["repo_root"],
        provider="skillcorner",
        match_ids=("holdout-1",),
        governance_identity=fixture["governance_identity"],
        holdout_manifest_path_sha256=sha256_path_identity(fixture["holdout_path"]),
        freeze_spec_path=_fixture_relative(fixture, fixture["freeze_spec_path"]),
        split_manifest_path=_fixture_relative(fixture, fixture["splits_path"]),
        target_holdout_manifest_path=_fixture_relative(fixture, fixture["holdout_path"]),
        policy_path=_fixture_relative(fixture, fixture["policy_path"]),
        source_config_path=_fixture_relative(fixture, fixture["config_path"]),
        source_set_path=(
            _fixture_relative(fixture, source_set_path or fixture["source_set_path"])
            if source_set_path is not None or fixture.get("source_set_path")
            else None
        ),
        approval_receipt_path=approval_receipt_path or fixture["approval_receipt_path"],
        approval_commit=approval_commit or fixture["approval_commit"],
        migration_commit=migration_commit or fixture["migration_commit"],
    )


def _fixture_relative(fixture: dict, path: Path) -> str:
    return path.resolve().relative_to(fixture["repo_root"].resolve()).as_posix()


def _new_ledger(fixture: dict):
    freeze = compute_freeze_hashes(fixture["freeze_spec_path"])
    governance_identity = build_governance_identity(
        policy_path=fixture["policy_path"],
        provider="skillcorner",
        source_revision=SOURCE_REVISION,
    )
    source_identity_set = build_single_source_identity_set(
        provider="skillcorner",
        match_id="holdout-1",
        source_config=fixture["config_path"],
    )
    return create_ledger(
        fixture["ledger_dir"],
        provider="skillcorner",
        match_ids=("holdout-1",),
        freeze_hashes=freeze,
        holdout_manifest_sha256=sha256_file(fixture["holdout_path"]),
        holdout_manifest_path_sha256=sha256_path_identity(fixture["holdout_path"]),
        split_manifest_sha256=sha256_file(fixture["splits_path"]),
        code_commit=fixture["code_commit"],
        governance_identity=governance_identity,
        source_identity=source_identity_set.identities["holdout-1"],
        source_identity_set=source_identity_set,
    )


def _ledger_records(ledger_dir: Path) -> list[dict]:
    paths = list(ledger_dir.glob("*.jsonl"))
    assert len(paths) == 1
    return [
        json.loads(line)
        for line in paths[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def separated_artifact_spec(
    tmp_path: Path,
) -> tuple[Path, dict[str, Path], Path]:
    artifact_root = tmp_path / "model-artifacts"
    paths = {
        "prediction_code": artifact_root / "prediction" / "model.py",
        "feature_set": artifact_root / "features" / "features.py",
        "data_transform": artifact_root / "data" / "transform.py",
        "algorithm_configuration": artifact_root / "config" / "state.json",
        "hyperparameters": artifact_root / "config" / "hyperparameters.json",
        "evaluation": artifact_root / "evaluation" / "evaluate.py",
        "evaluation_runner": artifact_root / "evaluation" / "runner.py",
        "evaluation_splits": artifact_root / "evaluation" / "splits.py",
        "metric_contract": artifact_root / "metrics" / "contract.md",
    }
    for name, path in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{name}=1\n", encoding="utf-8")
    governance_file = artifact_root / "governance" / "policy.py"
    governance_file.parent.mkdir(parents=True, exist_ok=True)
    governance_file.write_text("decision='original'\n", encoding="utf-8")
    spec = {
        "schema_version": "2.0",
        "artifact_root": "model-artifacts",
        "artifacts": {
            "prediction_code": [paths["prediction_code"].relative_to(artifact_root).as_posix()],
            "feature_set": [paths["feature_set"].relative_to(artifact_root).as_posix()],
            "data_transform": [paths["data_transform"].relative_to(artifact_root).as_posix()],
            "algorithm_configuration": [
                paths["algorithm_configuration"].relative_to(artifact_root).as_posix()
            ],
            "hyperparameters": [paths["hyperparameters"].relative_to(artifact_root).as_posix()],
            "evaluation_script": [
                paths["evaluation"].relative_to(artifact_root).as_posix(),
                paths["evaluation_runner"].relative_to(artifact_root).as_posix(),
                paths["evaluation_splits"].relative_to(artifact_root).as_posix(),
            ],
            "metric_contract": [paths["metric_contract"].relative_to(artifact_root).as_posix()],
        },
        "category_reasons": {
            name: f"synthetic {name} reason"
            for name in (
                "prediction_code",
                "feature_set",
                "data_transform",
                "algorithm_configuration",
                "hyperparameters",
                "evaluation_script",
                "metric_contract",
            )
        },
        "metric_contract_version": "1.1.0",
    }
    spec_path = tmp_path / "separated-freeze.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    return spec_path, paths, governance_file


def prepare_separated_promotion(tmp_path: Path) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    spec_path, artifact_paths, governance_file = separated_artifact_spec(tmp_path)
    freeze = compute_freeze_hashes(spec_path)
    holdout_path = holdout_manifest(tmp_path, freeze, ["holdout-1"])
    policy_path = allowed_policy(tmp_path)
    code_commit = "abcdef0123456789abcdef0123456789abcdef01"
    return {
        "config_path": external_config(tmp_path),
        "splits_path": split_manifest(tmp_path),
        "policy_path": policy_path,
        "holdout_path": holdout_path,
        "freeze_spec_path": spec_path,
        "ledger_dir": tmp_path / "ledger",
        "code_commit": code_commit,
        "artifact_paths": artifact_paths,
        "governance_file": governance_file,
        "freeze": freeze,
    }


def prepare_multi_source_promotion(tmp_path: Path) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    spec_path, artifact_paths, governance_file = separated_artifact_spec(tmp_path)
    freeze = compute_freeze_hashes(spec_path)
    source_1 = external_config(tmp_path, "holdout-1", "source-1.json")
    source_2 = external_config(tmp_path, "holdout-2", "source-2.json")
    members = [
        {"match_id": "holdout-1", "source_config": source_1.name},
        {"match_id": "holdout-2", "source_config": source_2.name},
    ]
    source_set_path = write_source_set_descriptor(tmp_path, members)
    holdout_path = holdout_manifest(
        tmp_path,
        freeze,
        ["holdout-1", "holdout-2"],
    )
    split_path = tmp_path / "splits-multi.json"
    split_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "split_unit": "match",
                "development": ["dev-1"],
                "validation": ["val-1"],
                "holdout": ["holdout-1", "holdout-2"],
                "status": "ready_for_promotion_review",
                "reason": "synthetic multi-match promotion",
            }
        ),
        encoding="utf-8",
    )
    policy_path = allowed_policy(tmp_path)
    return {
        "config_path": source_1,
        "splits_path": split_path,
        "policy_path": policy_path,
        "holdout_path": holdout_path,
        "freeze_spec_path": spec_path,
        "ledger_dir": tmp_path / "ledger",
        "code_commit": "abcdef0123456789abcdef0123456789abcdef01",
        "artifact_paths": artifact_paths,
        "governance_file": governance_file,
        "freeze": freeze,
        "source_set_path": source_set_path,
        "source_1": source_1,
        "source_2": source_2,
    }


def write_source_set_descriptor(
    tmp_path: Path,
    members: list[dict[str, str]],
    *,
    filename: str = "source-set.json",
) -> Path:
    payload = {
        "schema_version": "1.0",
        "provider": "skillcorner",
        "members": members,
    }
    path = tmp_path / filename
    path.write_text(
        json.dumps(
            {
                **payload,
                "source_set_sha256": hashlib.sha256(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    return path


def prepare_legacy_migration(
    tmp_path: Path,
    *,
    compromised: bool = False,
) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    legacy_spec_path, _legacy_paths = artifact_spec(tmp_path)
    legacy_freeze = compute_freeze_hashes(legacy_spec_path)
    holdout_path = holdout_manifest(tmp_path, legacy_freeze, ["holdout-1"])
    policy_path = allowed_policy(tmp_path)
    splits_path = split_manifest(tmp_path)
    config_path = external_config(tmp_path)
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "fixture")
    _git(tmp_path, "config", "user.email", "fixture@example.invalid")
    _git(tmp_path, "config", "core.autocrlf", "false")
    _git(
        tmp_path,
        "add",
        "--",
        "artifacts",
        "freeze.json",
        "holdout.json",
        "policy.json",
        "splits.json",
        "external.json",
    )
    _git(tmp_path, "commit", "-m", "fixture legacy candidate")
    code_commit = _git(tmp_path, "rev-parse", "HEAD").strip()
    provider, match_ids, holdout_id = stable_holdout_identity(
        "skillcorner",
        ("holdout-1",),
    )
    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir()
    ledger_path = ledger_dir / f"{holdout_id}.jsonl"
    record = {
        "recorded_at": "2026-11-08T00:00:00+00:00",
        "event_type": "COMPROMISED" if compromised else "SEALED_VERIFIED",
        "provider": provider,
        "holdout_id": holdout_id,
        "match_ids": list(match_ids),
        "freeze_hashes": {
            "model": legacy_freeze.model,
            "feature_set": legacy_freeze.feature_set,
            "configuration": legacy_freeze.configuration,
            "hyperparameters": legacy_freeze.hyperparameters,
            "evaluation_script": legacy_freeze.evaluation_script,
            "metric_contract_version": legacy_freeze.metric_contract_version,
        },
        "holdout_manifest_sha256": sha256_file(holdout_path),
        "code_commit": code_commit,
        "prediction_sha256": None,
        "previous_record_sha256": None,
        "reason": "legacy contamination" if compromised else None,
    }
    ledger_path.write_text(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    new_spec_path, artifact_paths, governance_file = separated_artifact_spec(tmp_path)
    model_freeze = compute_freeze_hashes(new_spec_path)
    governance_identity = build_governance_identity(
        policy_path=policy_path,
        provider="skillcorner",
        source_revision=SOURCE_REVISION,
    )
    source_identity = build_source_identity(config_path)
    source_identity_set = build_single_source_identity_set(
        provider=provider,
        match_id=match_ids[0],
        source_config=config_path,
    )
    script_path = tmp_path / "scripts" / "migrate_holdout_ledger.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        (ROOT / "scripts" / "migrate_holdout_ledger.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    paths_to_commit = [
        "scripts/migrate_holdout_ledger.py",
        "model-artifacts",
        "separated-freeze.json",
        "policy.json",
        "splits.json",
        "holdout.json",
    ]
    _git(tmp_path, "add", "--", *paths_to_commit)
    _git(tmp_path, "commit", "-m", "fixture migration tool")
    migration_commit = _git(tmp_path, "rev-parse", "HEAD").strip()
    receipt = {
        "schema_version": "1.0",
        "event_type": "FREEZE_PROTOCOL_MIGRATED",
        "status": "MIGRATED_AUDIT_ONLY",
        "promotion_authorized": False,
        "source_provider": provider,
        "source_holdout_id": holdout_id,
        "source_match_ids": list(match_ids),
        "source_protocol_version": "combined-policy-model-v1",
        "source_ledger_head_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        "legacy_combined_freeze": record["freeze_hashes"],
        "old_code_commit": code_commit,
        "migration_commit": migration_commit,
        "migration_tool_sha256": sha256_file(script_path),
        "migration_rule_version": "1.0",
        "model_freeze_spec_sha256": sha256_file(new_spec_path),
        "evaluation_freeze_spec_sha256": sha256_file(new_spec_path),
        "policy_sha256": sha256_file(policy_path),
        "source_config_sha256": source_identity.source_config_sha256,
        "old_holdout_manifest_sha256": sha256_file(holdout_path),
        "target_model_identity": {
            "model": model_freeze.model,
            "feature_set": model_freeze.feature_set,
            "configuration": model_freeze.configuration,
            "hyperparameters": model_freeze.hyperparameters,
        },
        "target_evaluation_identity": {
            "evaluation_script": model_freeze.evaluation_script,
            "metric_contract_version": model_freeze.metric_contract_version,
        },
        "target_split_manifest_sha256": sha256_file(tmp_path / "splits.json"),
        "target_holdout_manifest_sha256": sha256_file(holdout_path),
        "target_source_identity": source_identity.to_dict(),
        "target_source_identity_set": source_identity_set.to_dict(),
        "governance_identity_digest": governance_identity.authorization_status_digest,
        "approver": "qa-lead",
        "approval_evidence_ids": ["PM-QA-APPROVAL-005"],
        "reason": "migrate legacy combined freeze as audit-only",
        "previous_record_sha256": _test_record_sha256(record),
    }
    receipt_path = tmp_path / "approval-migration.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    _git(tmp_path, "add", "--", "approval-migration.json")
    _git(tmp_path, "commit", "-m", "approve audit migration")
    approval_commit = _git(tmp_path, "rev-parse", "HEAD").strip()
    return {
        "repo_root": tmp_path,
        "config_path": config_path,
        "splits_path": splits_path,
        "policy_path": policy_path,
        "holdout_path": holdout_path,
        "freeze_spec_path": new_spec_path,
        "ledger_dir": ledger_dir,
        "code_commit": code_commit,
        "migration_commit": migration_commit,
        "approval_commit": approval_commit,
        "approval_receipt_path": receipt_path.name,
        "model_freeze": model_freeze,
        "governance_identity": governance_identity,
        "source_identity": source_identity,
        "artifact_paths": artifact_paths,
        "governance_file": governance_file,
    }


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _test_record_sha256(record: dict) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def _commit_current_receipt(fixture: dict, parent: str | None) -> str:
    _git(fixture["repo_root"], "add", "--", fixture["approval_receipt_path"])
    tree = _git(fixture["repo_root"], "write-tree").strip()
    args = ["commit-tree", tree]
    if parent is not None:
        args.extend(["-p", parent])
    args.extend(["-m", "approval receipt update"])
    return _git(fixture["repo_root"], *args).strip()
