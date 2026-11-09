import json
import subprocess
import sys
from dataclasses import fields, replace
from datetime import datetime
from pathlib import Path

import pytest
from test_holdout_gates import (
    fake_evaluator,
    prepare_snapshot_promotion,
    run_snapshot_match,
)
from test_neutral_adapter import authorized_run, neutral

import mtah_possession.evaluation.runner as runner_module
from mtah_possession.data.neutral import (
    PhaseSpan,
    TeamSide,
    prediction_source_from_match,
)
from mtah_possession.evaluation.external import (
    EvaluationPlan,
    ExternalPredictionBatch,
    evaluate_external_match,
    predict_external_candidates,
)
from mtah_possession.evaluation.splits import (
    EvaluationMode,
    SplitManifest,
)
from mtah_possession.governance.authorization import authorize_external_run
from mtah_possession.governance.exposure import create_exposure_seal
from mtah_possession.governance.ledger import HoldoutLedgerState, load_existing_ledger
from mtah_possession.governance.policy import (
    AuthorizationBasis,
    DataUse,
    PolicyError,
    PolicyStatus,
    load_policy,
    require_scoped_internal_risk,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "4340d274572876239c154c90bc507a9b3250a656"
NOW = datetime.fromisoformat("2026-11-15T00:00:00+00:00")


def _scoped_policy(
    tmp_path: Path,
    *,
    match_ids: list[str] | None = None,
    allowed_uses: list[str] | None = None,
    accepted_at: str = "2026-11-01T00:00:00+00:00",
    review_at: str = "2026-12-01T00:00:00+00:00",
    risk_owner: str = "project-owner",
    restrictions: list[str] | None = None,
    source_revision: str = SOURCE_REVISION,
) -> Path:
    values = json.loads(
        (ROOT / "configs" / "policy" / "external-data-policy-v2.1.json").read_text(encoding="utf-8")
    )
    values["providers"][0]["project_risk_acceptances"] = [
        {
            "scope_id": "RISK-INTERNAL-CLOSURE-002",
            "provider": "skillcorner",
            "source_revision": source_revision,
            "match_ids": ["101"] if match_ids is None else match_ids,
            "allowed_uses": (
                [DataUse.READ_PREPROCESS.value] if allowed_uses is None else allowed_uses
            ),
            "restrictions": (
                ["internal inspection only; no publication or redistribution"]
                if restrictions is None
                else restrictions
            ),
            "risk_owner": risk_owner,
            "accepted_at": accepted_at,
            "review_at": review_at,
            "status": "PROJECT_RISK_ACCEPTED_INTERNAL",
        }
    ]
    path = tmp_path / "scoped-policy.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


def _diagnostic_split() -> SplitManifest:
    return SplitManifest(
        development=frozenset({"101"}),
        validation=frozenset(),
        holdout=frozenset(),
        status="diagnostic_only",
    )


@pytest.mark.parametrize(
    "plan",
    [
        EvaluationPlan.tracking_only(),
        EvaluationPlan.prediction_phase_only(),
    ],
)
def test_pb16_prediction_only_promotion_is_rejected_without_side_effects(
    tmp_path: Path,
    plan: EvaluationPlan,
) -> None:
    fixture = prepare_snapshot_promotion(tmp_path)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="scored evaluation plan"):
        run_snapshot_match(
            fixture,
            "101",
            loader=forbidden_loader,
            evaluation_plan=plan,
        )
    assert calls == 0
    assert not fixture["ledger_dir"].exists()

    output = tmp_path / "cli-output.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "evaluate_external.py"),
            "--config",
            str(fixture["sources"]["101"]["config"]),
            "--splits",
            str(fixture["splits_path"]),
            "--policy",
            str(fixture["policy_path"]),
            "--holdout-manifest",
            str(fixture["holdout_path"]),
            "--freeze-spec",
            str(fixture["freeze_spec_path"]),
            "--holdout-ledger-dir",
            str(fixture["ledger_dir"]),
            "--mode",
            "promotion",
            "--split",
            "holdout",
            "--evaluation-plan",
            "tracking-only",
            "--code-commit",
            fixture["code_commit"],
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "scored evaluation plan" in result.stderr
    assert not output.exists()
    assert not fixture["ledger_dir"].exists()


def test_pb17_scored_promotion_preserves_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_snapshot_promotion(tmp_path)
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    result = run_snapshot_match(
        fixture,
        "101",
        evaluation_plan=EvaluationPlan.full_scored(),
    )
    assert not isinstance(result.evaluation, ExternalPredictionBatch)
    ledger = load_existing_ledger(
        fixture["ledger_dir"],
        provider="skillcorner",
        match_ids=("101",),
    )
    assert ledger.state == HoldoutLedgerState.COMPLETED
    assert [event["event_type"] for event in ledger.records()] == [
        "SEALED_VERIFIED",
        "UNSEALED",
        "EVALUATION_STARTED",
        "EVALUATION_COMPLETED",
    ]


def test_pb18_scoped_risk_is_a_production_authorization_basis(
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
    assert authorized.scope_ids[DataUse.READ_PREPROCESS] == "RISK-INTERNAL-CLOSURE-002"
    assert authorized.governance_identity.license_status == PolicyStatus.HOLD.value
    authorization_record = authorized.to_authorization_record()
    assert authorization_record["uses"]["read_preprocess"] == {
        "authorization_basis": "SCOPED_INTERNAL_RISK",
        "scope_id": "RISK-INTERNAL-CLOSURE-002",
    }


@pytest.mark.parametrize(
    "policy_kwargs",
    [
        {
            "accepted_at": "2026-10-01T00:00:00+00:00",
            "review_at": "2026-11-10T00:00:00+00:00",
        },
        {
            "accepted_at": "2026-11-20T00:00:00+00:00",
            "review_at": "2026-12-20T00:00:00+00:00",
        },
        {"source_revision": "1111111111111111111111111111111111111111"},
        {"match_ids": ["999"]},
        {"allowed_uses": [DataUse.TRACKING_MODEL_INPUT.value]},
        {"risk_owner": ""},
    ],
)
def test_pb19_scoped_risk_boundary_mismatches_fail(
    tmp_path: Path,
    policy_kwargs: dict,
) -> None:
    path = _scoped_policy(tmp_path, **policy_kwargs)
    with pytest.raises(PolicyError):
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


@pytest.mark.parametrize(
    "use",
    [
        DataUse.PUBLICATION,
        DataUse.SOURCE_REDISTRIBUTION,
        DataUse.DERIVED_REDISTRIBUTION,
    ],
)
def test_pb20_scoped_risk_never_authorizes_publication_or_redistribution(
    tmp_path: Path,
    use: DataUse,
) -> None:
    path = _scoped_policy(
        tmp_path,
        allowed_uses=[
            DataUse.READ_PREPROCESS.value,
            DataUse.PUBLICATION.value,
            DataUse.SOURCE_REDISTRIBUTION.value,
            DataUse.DERIVED_REDISTRIBUTION.value,
        ],
    )
    with pytest.raises(PolicyError):
        authorize_external_run(
            policy_path=path,
            provider="skillcorner",
            source_revision=SOURCE_REVISION,
            requested_uses=(use,),
            label_profile_ids=(),
            split_manifest=_diagnostic_split(),
            match_id="101",
            split="development",
            mode=EvaluationMode.DIAGNOSTIC,
            now=NOW,
        )

    policy = load_policy(path)
    with pytest.raises(PolicyError, match="cannot authorize final_candidate"):
        require_scoped_internal_risk(
            policy,
            provider_name="skillcorner",
            source_revision=SOURCE_REVISION,
            match_id="101",
            use="final_candidate",
            now=NOW,
        )


@pytest.mark.parametrize(
    "level",
    [
        "TRACKING_SEEN",
        "EVENTS_SEEN",
        "PHASES_SEEN",
        "MODEL_EXPERIMENT_USED",
        "EVALUATION_REFERENCE_SEEN",
        "HOLDOUT_RESULT_SEEN",
    ],
)
def test_pb12_high_exposure_is_bound_to_production_split(
    tmp_path: Path,
    level: str,
) -> None:
    fixture = prepare_snapshot_promotion(tmp_path, exposure_level=level)
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="historically exposed"):
        run_snapshot_match(fixture, "101", loader=forbidden_loader)
    assert calls == 0


def test_pb12_missing_exposure_record_fails_closed_in_production(
    tmp_path: Path,
) -> None:
    fixture = prepare_snapshot_promotion(tmp_path)
    values = json.loads(fixture["exposure_register_path"].read_text(encoding="utf-8"))
    values["records"] = []
    fixture["exposure_register_path"].write_text(json.dumps(values), encoding="utf-8")
    seal = create_exposure_seal(
        register_path=fixture["exposure_register_path"],
        anchor_path=fixture["exposure_anchor_path"],
        trust_root_path=fixture["exposure_trust_root_path"],
        holdout_provider="skillcorner",
        holdout_match_ids=("101",),
        approved_by="fixture-owner",
        approved_at="2026-11-09T00:00:00+08:00",
        approval_evidence=("synthetic empty-history test",),
        reseal_id="Synthetic-empty-history",
    )
    fixture["exposure_trust_root_sha256"] = seal.trust_root_sha256
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="missing"):
        run_snapshot_match(fixture, "101", loader=forbidden_loader)
    assert calls == 0


def test_pb12_split_change_cannot_clear_exposure_history(
    tmp_path: Path,
) -> None:
    fixture = prepare_snapshot_promotion(
        tmp_path,
        exposure_level="MODEL_EXPERIMENT_USED",
    )
    split_values = json.loads(fixture["splits_path"].read_text(encoding="utf-8"))
    split_values["reason"] = "split metadata change must not clear history"
    fixture["splits_path"].write_text(json.dumps(split_values), encoding="utf-8")
    calls = 0

    def forbidden_loader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("loader must not run")

    with pytest.raises(PolicyError, match="historically exposed"):
        run_snapshot_match(fixture, "101", loader=forbidden_loader)
    assert calls == 0


@pytest.mark.parametrize("level", ["ID_ONLY", "METADATA_SEEN"])
def test_pb12_low_disclosed_exposure_can_enter_holdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    level: str,
) -> None:
    fixture = prepare_snapshot_promotion(tmp_path, exposure_level=level)
    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    result = run_snapshot_match(
        fixture,
        "101",
        evaluation_plan=EvaluationPlan.full_scored(),
    )
    disclosure = result.report["policy_identity"]["authorization"]["exposure_disclosure"]
    assert disclosure[0]["match_id"] == "101"
    assert disclosure[0]["exposure_level"] == level


def test_pb21_prediction_source_only_exposes_phase_intervals() -> None:
    source = prediction_source_from_match(
        neutral(
            frame_count=10,
            frame_present=[True] * 10,
            possession_side=[0] * 10,
            possession_status=[0] * 10,
            phases=(PhaseSpan(2, 8, 1, "build_up", team=TeamSide.HOME),),
        )
    )
    assert len(source.phases) == 1
    phase = source.phases[0]
    assert {field.name for field in fields(phase)} == {
        "start_frame",
        "end_frame",
        "period",
        "source",
    }
    assert not hasattr(phase, "team")
    assert not hasattr(phase, "kind")
    assert not hasattr(phase, "restart")
    assert not hasattr(phase, "dead_ball")


def test_pb23_observed_use_records_actual_reference_and_feature_calls() -> None:
    match = replace(
        neutral(
            frame_count=10,
            frame_present=[True] * 10,
            possession_side=[0] * 10,
            possession_status=[0] * 10,
        ),
        periods=(),
    )
    tracking = evaluate_external_match(
        match,
        runner_module.load_algorithm_config(ROOT / "configs" / "state-engine.json"),
        authorization=authorized_run(),
        plan=EvaluationPlan.tracking_only(),
    )
    assert isinstance(tracking, ExternalPredictionBatch)
    assert tracking.observed_uses.evaluation_reference_read is False
    assert tracking.observed_uses.transformed_feature_families == ("tracking_geometry",)

    calls = 0

    def reference_loader():
        nonlocal calls
        calls += 1
        return _reference_for(match)

    scored = evaluate_external_match(
        match,
        runner_module.load_algorithm_config(ROOT / "configs" / "state-engine.json"),
        authorization=authorized_run(),
        plan=EvaluationPlan.full_scored(),
        reference_loader=reference_loader,
    )
    assert calls == 1
    assert scored.observed_uses.evaluation_reference_read is True
    assert "phase_event_evidence" in scored.observed_uses.transformed_feature_families

    with pytest.raises(PolicyError, match="read roles exceed"):
        predict_external_candidates(
            prediction_source_from_match(match),
            runner_module.load_algorithm_config(ROOT / "configs" / "state-engine.json"),
            authorization=authorized_run(),
            plan=EvaluationPlan.tracking_only(),
            runtime_read_roles=("tracking", "match", "phases"),
        )


def _reference_for(match):
    from mtah_possession.data.neutral import evaluation_reference_from_match

    return evaluation_reference_from_match(match)
