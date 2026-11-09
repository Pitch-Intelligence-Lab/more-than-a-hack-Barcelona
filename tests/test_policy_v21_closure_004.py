import json
from pathlib import Path

import pytest
from test_holdout_gates import (
    _ledger_records,
    _new_ledger,
    fake_evaluator,
    prepare_snapshot_promotion,
    run_snapshot_match,
)
from test_policy_v21_closure_002 import NOW, _diagnostic_split, _scoped_policy

import mtah_possession.evaluation.runner as runner_module
from mtah_possession.evaluation.external import EvaluationPlan
from mtah_possession.evaluation.splits import EvaluationMode
from mtah_possession.governance.authorization import authorize_external_run
from mtah_possession.governance.exposure import (
    ExposureLevel,
    create_exposure_seal,
    reseal_exposure_register,
)
from mtah_possession.governance.ledger import LedgerEvent
from mtah_possession.governance.policy import (
    AuthorizationBasis,
    DataUse,
    PolicyError,
)

SOURCE_REVISION = "4340d274572876239c154c90bc507a9b3250a656"


def _read_register(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _set_exposure_level(path: Path, level: ExposureLevel) -> None:
    values = _read_register(path)
    values["records"][0]["exposure_level"] = level.value
    values["records"][0]["notes"] = f"synthetic Closure 004 update to {level.value}"
    path.write_text(json.dumps(values), encoding="utf-8")


def _fail_evaluator(*_args, **_kwargs):
    raise RuntimeError("synthetic retryable evaluation failure")


def _record_ledger_bytes(ledger_dir: Path) -> bytes:
    paths = list(ledger_dir.glob("*.jsonl"))
    assert len(paths) == 1
    return paths[0].read_bytes()


def test_pb35_hold_use_empty_evidence_allows_scoped_internal_risk(
    tmp_path: Path,
) -> None:
    authorized = authorize_external_run(
        policy_path=_scoped_policy(tmp_path),
        provider="skillcorner",
        source_revision=SOURCE_REVISION,
        requested_uses=(DataUse.READ_PREPROCESS,),
        label_profile_ids=(),
        split_manifest=_diagnostic_split(),
        match_id="101",
        split="development",
        mode=EvaluationMode.DIAGNOSTIC,
        now=NOW,
    )
    assert authorized.use_bases[DataUse.READ_PREPROCESS] == (
        AuthorizationBasis.SCOPED_INTERNAL_RISK
    )


def test_pb36_hold_use_unregistered_evidence_is_denied(
    tmp_path: Path,
) -> None:
    path = _scoped_policy(tmp_path)
    values = json.loads(path.read_text(encoding="utf-8"))
    values["providers"][0]["uses"]["read_preprocess"]["evidence_ids"] = ["EV-HOLD-NOT-REGISTERED"]
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(PolicyError, match="not registered"):
        authorize_external_run(
            policy_path=path,
            provider="skillcorner",
            source_revision=SOURCE_REVISION,
            requested_uses=(DataUse.READ_PREPROCESS,),
            label_profile_ids=(),
            split_manifest=_diagnostic_split(),
            match_id="101",
            split="development",
            mode=EvaluationMode.DIAGNOSTIC,
            now=NOW,
        )


def test_pb37_failed_ledger_is_rejected_after_register_reseal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_snapshot_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", _fail_evaluator)
    with pytest.raises(RuntimeError, match="retryable"):
        run_snapshot_match(fixture, "101")
    assert _ledger_records(fixture["ledger_dir"])[-1]["event_type"] == "EVALUATION_FAILED"

    _set_exposure_level(
        fixture["exposure_register_path"],
        ExposureLevel.METADATA_SEEN,
    )
    seal = reseal_exposure_register(
        register_path=fixture["exposure_register_path"],
        anchor_path=fixture["exposure_anchor_path"],
        trust_root_path=fixture["exposure_trust_root_path"],
        expected_trust_root_sha256=fixture["exposure_trust_root_sha256"],
        reseal_id="CLOSURE-004-PB37",
        approved_by="policy-owner",
        approved_at="2026-11-10T00:00:00+00:00",
        reason="synthetic monotonic reseal after failed evaluation",
        approval_evidence=("Closure 004 PB37 approval",),
    )
    fixture["exposure_trust_root_sha256"] = seal.trust_root_sha256
    before = _record_ledger_bytes(fixture["ledger_dir"])
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    with pytest.raises(PolicyError, match="Exposure Identity has changed"):
        run_snapshot_match(fixture, "101", loader=forbidden_loader)
    assert calls == 0
    assert _record_ledger_bytes(fixture["ledger_dir"]) == before


def test_pb38_failed_ledger_is_rejected_after_anchor_and_trust_root_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_snapshot_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", _fail_evaluator)
    with pytest.raises(RuntimeError, match="retryable"):
        run_snapshot_match(fixture, "101")

    rotated = create_exposure_seal(
        register_path=fixture["exposure_register_path"],
        anchor_path=fixture["exposure_anchor_path"],
        trust_root_path=fixture["exposure_trust_root_path"],
        holdout_provider="skillcorner",
        holdout_match_ids=("101",),
        approved_by="policy-owner",
        approved_at="2026-11-10T00:00:00+00:00",
        approval_evidence=("Closure 004 PB38 explicit anchor rotation",),
        reseal_id="CLOSURE-004-PB38",
    )
    fixture["exposure_trust_root_sha256"] = rotated.trust_root_sha256
    before = _record_ledger_bytes(fixture["ledger_dir"])
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    with pytest.raises(PolicyError, match="Exposure Identity has changed"):
        run_snapshot_match(fixture, "101", loader=forbidden_loader)
    assert calls == 0
    assert _record_ledger_bytes(fixture["ledger_dir"]) == before


def test_pb39_completed_ledger_remains_permanently_non_reusable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_snapshot_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    run_snapshot_match(fixture, "101")
    before = _record_ledger_bytes(fixture["ledger_dir"])
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="already completed"):
        run_snapshot_match(fixture, "101", loader=forbidden_loader)
    assert calls == 0
    assert _record_ledger_bytes(fixture["ledger_dir"]) == before


def test_pb40_new_seal_and_new_ledger_record_exposure_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_snapshot_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", _fail_evaluator)
    with pytest.raises(RuntimeError, match="retryable"):
        run_snapshot_match(fixture, "101")

    _set_exposure_level(
        fixture["exposure_register_path"],
        ExposureLevel.METADATA_SEEN,
    )
    seal = reseal_exposure_register(
        register_path=fixture["exposure_register_path"],
        anchor_path=fixture["exposure_anchor_path"],
        trust_root_path=fixture["exposure_trust_root_path"],
        expected_trust_root_sha256=fixture["exposure_trust_root_sha256"],
        reseal_id="CLOSURE-004-PB40",
        approved_by="policy-owner",
        approved_at="2026-11-10T00:00:00+00:00",
        reason="synthetic legal new seal",
        approval_evidence=("Closure 004 PB40 approval",),
    )
    fixture["exposure_trust_root_sha256"] = seal.trust_root_sha256
    fixture["ledger_dir"] = tmp_path / "ledger-after-reseal"
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    result = run_snapshot_match(
        fixture,
        "101",
        evaluation_plan=EvaluationPlan.full_scored(),
    )
    records = _ledger_records(fixture["ledger_dir"])
    assert all(record["schema_version"] == "7.0" for record in records)
    assert all(record["exposure_reseal_id"] == "CLOSURE-004-PB40" for record in records)
    assert all(record["exposure_trust_root_sha256"] == seal.trust_root_sha256 for record in records)
    integrity = result.report["policy_identity"]["authorization"]["exposure_integrity"]
    assert integrity["reseal_id"] == "CLOSURE-004-PB40"
    assert integrity["trust_root_sha256"] == seal.trust_root_sha256


def test_pb41_v6_ledger_without_exposure_identity_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_snapshot_promotion(tmp_path)
    ledger = _new_ledger(fixture, with_exposure=False)
    ledger.append(LedgerEvent.SEALED_VERIFIED)
    ledger.append(LedgerEvent.UNSEALED)
    ledger.append(LedgerEvent.EVALUATION_STARTED, match_id="101")
    ledger.append(LedgerEvent.EVALUATION_FAILED, match_id="101", reason="synthetic")
    before = _record_ledger_bytes(fixture["ledger_dir"])
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    with pytest.raises(PolicyError, match="V6 holdout ledger"):
        run_snapshot_match(fixture, "101", loader=forbidden_loader)
    assert calls == 0
    assert _record_ledger_bytes(fixture["ledger_dir"]) == before
