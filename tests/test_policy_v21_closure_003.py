import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_holdout_gates import (
    exposure_register,
    fake_evaluator,
    prepare_snapshot_promotion,
)
from test_policy_v21_closure_002 import NOW, _diagnostic_split, _scoped_policy

import mtah_possession.evaluation.runner as runner_module
from mtah_possession.algorithm_config import load_algorithm_config
from mtah_possession.evaluation.external import EvaluationPlan
from mtah_possession.evaluation.runner import run_external_evaluation
from mtah_possession.evaluation.splits import EvaluationMode, load_split_manifest
from mtah_possession.governance.artifacts import compute_freeze_hashes
from mtah_possession.governance.authorization import (
    APPROVED_EXPOSURE_TRUST_ROOT_SHA256,
    DEFAULT_EXPOSURE_ANCHOR_PATH,
    DEFAULT_EXPOSURE_REGISTER_PATH,
    DEFAULT_EXPOSURE_TRUST_ROOT_PATH,
    EVALUATION_PHASE_PROFILE,
    EVALUATION_POSSESSION_PROFILE,
    authorize_external_run,
    build_governance_identity,
)
from mtah_possession.governance.exposure import (
    EXPOSURE_RANK,
    ExposureLevel,
    load_exposure_trust_root,
    load_verified_exposure_snapshot,
    reseal_exposure_register,
    sha256_file,
)
from mtah_possession.governance.holdout import load_holdout_manifest
from mtah_possession.governance.policy import (
    AuthorizationBasis,
    DataUse,
    PolicyError,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "4340d274572876239c154c90bc507a9b3250a656"
_UNSET = object()


def _authorize_fixture(
    fixture: dict,
    *,
    register_path=_UNSET,
    anchor_path=_UNSET,
    trust_root_path=_UNSET,
    trust_root_sha256=_UNSET,
):
    splits = load_split_manifest(fixture["splits_path"])
    holdout = load_holdout_manifest(fixture["holdout_path"])
    freeze = compute_freeze_hashes(fixture["freeze_spec_path"])
    identity = build_governance_identity(
        policy_path=fixture["policy_path"],
        provider="skillcorner",
        source_revision=SOURCE_REVISION,
    )
    return authorize_external_run(
        policy_path=fixture["policy_path"],
        provider="skillcorner",
        source_revision=SOURCE_REVISION,
        requested_uses=EvaluationPlan.full_scored().requested_uses,
        label_profile_ids=(
            EVALUATION_POSSESSION_PROFILE,
            EVALUATION_PHASE_PROFILE,
        ),
        required_status_axes=("PHASE_SEMANTICS_VERIFIED",),
        split_manifest=splits,
        match_id="101",
        split="holdout",
        mode=EvaluationMode.PROMOTION,
        holdout_manifest=holdout,
        freeze_hashes=freeze,
        governance_identity=identity,
        exposure_register_path=(
            fixture["exposure_register_path"] if register_path is _UNSET else register_path
        ),
        exposure_anchor_path=(
            fixture["exposure_anchor_path"] if anchor_path is _UNSET else anchor_path
        ),
        exposure_trust_root_path=(
            fixture["exposure_trust_root_path"] if trust_root_path is _UNSET else trust_root_path
        ),
        exposure_trust_root_sha256=(
            fixture["exposure_trust_root_sha256"]
            if trust_root_sha256 is _UNSET
            else trust_root_sha256
        ),
        now=NOW,
    )


def _run_fixture(
    fixture: dict,
    *,
    trust_root_sha256: str,
    loader=None,
):
    def default_loader(snapshot, external_root, expected_identity, **kwargs):
        from mtah_possession.data.skillcorner import load_skillcorner_match_from_snapshot

        return load_skillcorner_match_from_snapshot(
            snapshot,
            external_root,
            expected_identity,
            **kwargs,
        )

    return run_external_evaluation(
        config_path=fixture["sources"]["101"]["config"],
        state_config_path=ROOT / "configs" / "state-engine.json",
        splits_path=fixture["splits_path"],
        external_root=fixture["external_root"],
        split="holdout",
        mode=EvaluationMode.PROMOTION,
        code_commit=fixture["code_commit"],
        policy_path=fixture["policy_path"],
        holdout_manifest_path=fixture["holdout_path"],
        freeze_spec_path=fixture["freeze_spec_path"],
        ledger_dir=fixture["ledger_dir"],
        source_set_path=fixture["source_set_path"],
        evaluation_plan=EvaluationPlan.full_scored(),
        exposure_register_path=fixture["exposure_register_path"],
        exposure_anchor_path=fixture["exposure_anchor_path"],
        exposure_trust_root_path=fixture["exposure_trust_root_path"],
        exposure_trust_root_sha256=trust_root_sha256,
        match_loader=loader or default_loader,
        state_config_loader=lambda _path: load_algorithm_config(
            ROOT / "configs" / "state-engine.json"
        ),
    )


def _set_read_permission(policy_path: Path, *, evidence_ids: list[str]) -> None:
    values = json.loads(policy_path.read_text(encoding="utf-8"))
    provider = values["providers"][0]
    for axis in (
        "PUBLIC_SOURCE_VERIFIED",
        "LICENSE_VERIFIED",
        "INTERNAL_RESEARCH_AUTHORIZED",
    ):
        provider["statuses"][axis] = "PASS"
    provider["uses"]["read_preprocess"] = {
        "status": "PASS",
        "evidence_ids": evidence_ids,
        "conditions": [],
    }
    policy_path.write_text(json.dumps(values), encoding="utf-8")


def test_pb24_pass_use_with_empty_evidence_and_scope_is_denied(
    tmp_path: Path,
) -> None:
    path = _scoped_policy(tmp_path)
    _set_read_permission(path, evidence_ids=[])
    with pytest.raises(PolicyError, match="requires evidence"):
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


def test_pb25_pass_use_with_unregistered_evidence_and_scope_is_denied(
    tmp_path: Path,
) -> None:
    path = _scoped_policy(tmp_path)
    _set_read_permission(path, evidence_ids=["EV-NOT-REGISTERED"])
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


def test_pb26_valid_hold_use_remains_allowed_with_scoped_basis(
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


def test_pb27_malformed_policy_cannot_fall_back_to_scoped_risk(
    tmp_path: Path,
) -> None:
    path = _scoped_policy(tmp_path)
    values = json.loads(path.read_text(encoding="utf-8"))
    values["providers"][0].pop("provider")
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(PolicyError, match="missing or unknown"):
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


def test_scoped_fallback_does_not_mask_permission_fail_with_hold_status(
    tmp_path: Path,
) -> None:
    path = _scoped_policy(tmp_path)
    values = json.loads(path.read_text(encoding="utf-8"))
    values["providers"][0]["uses"]["read_preprocess"]["status"] = "FAIL"
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(PolicyError, match="FAIL"):
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


def test_pb28_direct_register_downgrade_is_denied(tmp_path: Path) -> None:
    fixture = prepare_snapshot_promotion(
        tmp_path,
        exposure_level=ExposureLevel.TRACKING_SEEN.value,
    )
    values = json.loads(fixture["exposure_register_path"].read_text(encoding="utf-8"))
    values["records"][0]["exposure_level"] = ExposureLevel.ID_ONLY.value
    fixture["exposure_register_path"].write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(PolicyError, match="SHA-256"):
        _authorize_fixture(fixture)


def test_pb29_alternate_register_path_is_denied(tmp_path: Path) -> None:
    fixture = prepare_snapshot_promotion(tmp_path)
    alternate = exposure_register(
        tmp_path,
        ["101"],
        filename="alternate-exposure.json",
    )
    with pytest.raises(PolicyError, match="path identity"):
        _authorize_fixture(fixture, register_path=alternate["register"])

    cli = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "evaluate_external.py"),
            "--split",
            "development",
            "--exposure-register",
            str(alternate["register"]),
            "--output",
            str(tmp_path / "must-not-exist.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cli.returncode == 2
    assert "unrecognized arguments" in cli.stderr
    assert not (tmp_path / "must-not-exist.json").exists()


def test_pb30_sealed_register_hash_change_is_denied(tmp_path: Path) -> None:
    fixture = prepare_snapshot_promotion(tmp_path)
    _authorize_fixture(fixture)
    values = json.loads(fixture["exposure_register_path"].read_text(encoding="utf-8"))
    values["records"][0]["notes"] = "post-seal mutation"
    fixture["exposure_register_path"].write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(PolicyError, match="SHA-256"):
        _authorize_fixture(fixture)


def test_pb31_reseal_cannot_lower_high_water_mark(tmp_path: Path) -> None:
    fixture = prepare_snapshot_promotion(
        tmp_path,
        exposure_level=ExposureLevel.TRACKING_SEEN.value,
    )
    values = json.loads(fixture["exposure_register_path"].read_text(encoding="utf-8"))
    values["records"][0]["exposure_level"] = ExposureLevel.ID_ONLY.value
    fixture["exposure_register_path"].write_text(json.dumps(values), encoding="utf-8")
    anchor_before = fixture["exposure_anchor_path"].read_bytes()
    root_before = fixture["exposure_trust_root_path"].read_bytes()
    with pytest.raises(PolicyError, match="cannot lower"):
        reseal_exposure_register(
            register_path=fixture["exposure_register_path"],
            anchor_path=fixture["exposure_anchor_path"],
            trust_root_path=fixture["exposure_trust_root_path"],
            expected_trust_root_sha256=fixture["exposure_trust_root_sha256"],
            reseal_id="ILLEGAL-DOWNGRADE",
            approved_by="fixture-owner",
            approved_at="2026-11-10T00:00:00+00:00",
            reason="attempted downgrade",
            approval_evidence=("illegal downgrade probe",),
        )
    assert fixture["exposure_anchor_path"].read_bytes() == anchor_before
    assert fixture["exposure_trust_root_path"].read_bytes() == root_before


@pytest.mark.parametrize("missing", ["register", "anchor", "trust_root", "trust_hash"])
def test_pb32_missing_register_anchor_or_trust_root_is_denied(
    tmp_path: Path,
    missing: str,
) -> None:
    fixture = prepare_snapshot_promotion(tmp_path)
    with pytest.raises(PolicyError, match="requires|trust root|does not match"):
        _authorize_fixture(
            fixture,
            register_path=None if missing == "register" else fixture["exposure_register_path"],
            anchor_path=None if missing == "anchor" else fixture["exposure_anchor_path"],
            trust_root_path=(
                None if missing == "trust_root" else fixture["exposure_trust_root_path"]
            ),
            trust_root_sha256=(
                "0" * 64 if missing == "trust_hash" else fixture["exposure_trust_root_sha256"]
            ),
        )


def test_pb33_replacing_register_and_anchor_cannot_replace_trusted_root(
    tmp_path: Path,
) -> None:
    fixture = prepare_snapshot_promotion(tmp_path)
    alternate = exposure_register(
        tmp_path,
        ["101"],
        filename="replacement-exposure.json",
        exposure_level=ExposureLevel.METADATA_SEEN.value,
    )
    fixture["exposure_register_path"].write_bytes(alternate["register"].read_bytes())
    fixture["exposure_anchor_path"].write_bytes(alternate["anchor"].read_bytes())
    with pytest.raises(PolicyError, match="anchor SHA-256"):
        _authorize_fixture(fixture)


def test_pb34_legitimate_monotonic_reseal_preserves_audit_and_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_snapshot_promotion(tmp_path)
    old_root_sha256 = fixture["exposure_trust_root_sha256"]
    values = json.loads(fixture["exposure_register_path"].read_text(encoding="utf-8"))
    values["records"][0]["exposure_level"] = ExposureLevel.METADATA_SEEN.value
    values["records"][0]["notes"] = "approved monotonic reseal"
    fixture["exposure_register_path"].write_text(json.dumps(values), encoding="utf-8")
    seal = reseal_exposure_register(
        register_path=fixture["exposure_register_path"],
        anchor_path=fixture["exposure_anchor_path"],
        trust_root_path=fixture["exposure_trust_root_path"],
        expected_trust_root_sha256=old_root_sha256,
        reseal_id="EXPOSURE-RESEAL-003-001",
        approved_by="policy-owner",
        approved_at="2026-11-10T00:00:00+00:00",
        reason="record an additional approved metadata exposure",
        approval_evidence=("owner approval for monotonic exposure update",),
    )
    trust_root = load_exposure_trust_root(fixture["exposure_trust_root_path"])
    assert seal.trust_root_sha256 == sha256_file(fixture["exposure_trust_root_path"])
    assert len(trust_root.reseals) == 1
    record = trust_root.reseals[0]
    assert record.reseal_id == "EXPOSURE-RESEAL-003-001"
    assert record.old_register_sha256 != record.new_register_sha256
    assert record.old_anchor_sha256 != record.new_anchor_sha256
    assert record.approved_by == "policy-owner"
    assert record.approval_evidence == ("owner approval for monotonic exposure update",)
    assert (
        EXPOSURE_RANK[record.highest_exposure_by_match_after["101"]]
        >= EXPOSURE_RANK[record.highest_exposure_by_match_before["101"]]
    )

    monkeypatch.setattr(runner_module, "evaluate_external_match", fake_evaluator)
    result = _run_fixture(fixture, trust_root_sha256=seal.trust_root_sha256)
    authorization = result.report["policy_identity"]["authorization"]
    disclosure = authorization["exposure_disclosure"]
    integrity = authorization["exposure_integrity"]
    assert disclosure[0]["exposure_level"] == ExposureLevel.METADATA_SEEN.value
    assert integrity["trust_root_sha256"] == seal.trust_root_sha256
    assert integrity["reseal_id"] == "EXPOSURE-RESEAL-003-001"


def test_default_exposure_register_anchor_and_trust_root_are_consistent() -> None:
    snapshot = load_verified_exposure_snapshot(
        register_path=DEFAULT_EXPOSURE_REGISTER_PATH,
        anchor_path=DEFAULT_EXPOSURE_ANCHOR_PATH,
        trust_root_path=DEFAULT_EXPOSURE_TRUST_ROOT_PATH,
        expected_trust_root_sha256=APPROVED_EXPOSURE_TRUST_ROOT_SHA256,
        provider="skillcorner",
        source_revision=SOURCE_REVISION,
        match_ids=(),
    )
    assert snapshot.register_sha256 == (
        "5c1579495502bad3d3a75af6addd54148d272beaa15f42a84eb43506da5d7376"
    )
    assert snapshot.anchor_sha256 == (
        "1f1c927e7e2892c9e8ecde978251134da453fee2e03e3f66db2cdc30f3ef7be8"
    )
    assert snapshot.trust_root_sha256 == APPROVED_EXPOSURE_TRUST_ROOT_SHA256
    assert snapshot.anchor.highest_exposure_by_match["2017461"] == (ExposureLevel.TRACKING_SEEN)
