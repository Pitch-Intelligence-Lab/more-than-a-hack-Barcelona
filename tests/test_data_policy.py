import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from helpers import write_skillcorner_source

from mtah_possession.data.skillcorner import (
    create_skillcorner_manifest_snapshot,
)
from mtah_possession.governance.policy import (
    DataUse,
    PolicyError,
    PolicyStatus,
    load_policy,
    require_allowed,
    require_source_identity,
)
from mtah_possession.governance.source import (
    build_source_identity,
    build_source_identity_from_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "configs" / "policy" / "external-data-policy-v2.json"
SOURCE_REVISION = "4340d274572876239c154c90bc507a9b3250a656"

spec = importlib.util.spec_from_file_location(
    "audit_external_script",
    ROOT / "scripts" / "audit_external.py",
)
assert spec is not None and spec.loader is not None
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


def write_modified_policy(tmp_path: Path, mutate) -> Path:
    values = json.loads(POLICY.read_text(encoding="utf-8"))
    mutate(values)
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


def write_audit_allowed_policy(tmp_path: Path) -> Path:
    def mutate(values):
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
        for use in ("read_preprocess", "evaluation_reference"):
            provider["uses"][use] = {
                "status": "PASS",
                "evidence_ids": ["EV-AUTH-SC-README"],
                "conditions": [],
            }
        for profile in provider["label_profiles"]:
            profile["status"] = "PASS"

    return write_modified_policy(tmp_path, mutate)


def prepare_audit_fixture(
    tmp_path: Path,
    *,
    match_ids: tuple[str, ...] = ("101",),
) -> dict:
    data_root = tmp_path / "external"
    sources = {
        match_id: write_skillcorner_source(
            data_root=data_root,
            config_path=tmp_path / f"source-{match_id}.json",
            match_id=match_id,
            source_revision=SOURCE_REVISION,
        )
        for match_id in match_ids
    }
    split_path = tmp_path / "splits.json"
    split_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "split_unit": "match",
                "development": list(match_ids),
                "validation": ["validation-1"],
                "holdout": ["holdout-1"],
                "status": "diagnostic_only",
                "reason": "audit snapshot fixture",
            }
        ),
        encoding="utf-8",
    )
    return {
        "sources": sources,
        "root": data_root,
        "splits": split_path,
        "policy": write_audit_allowed_policy(tmp_path),
    }


def run_audit(
    fixture: dict,
    output: Path,
    *,
    match_id: str = "101",
) -> int:
    return audit_module.main(
        [
            "--config",
            str(fixture["sources"][match_id]["config"]),
            "--splits",
            str(fixture["splits"]),
            "--policy",
            str(fixture["policy"]),
            "--external-root",
            str(fixture["root"]),
            "--output",
            str(output),
        ]
    )


def test_policy_loads_provider_and_use_axes_separately() -> None:
    policy = load_policy(POLICY)
    assert policy.policy_version == "DP-006-POLICY-v2"
    assert set(policy.providers) == {"skillcorner", "metrica", "soccertrack_v2"}
    skillcorner = policy.provider("skillcorner")
    assert skillcorner.statuses["PUBLIC_SOURCE_VERIFIED"] == PolicyStatus.PASS
    assert skillcorner.statuses["LICENSE_VERIFIED"] == PolicyStatus.HOLD
    assert skillcorner.uses[DataUse.READ_PREPROCESS].status == PolicyStatus.HOLD
    assert skillcorner.overall_status == PolicyStatus.HOLD


def test_skillcorner_hold_fails_before_use(tmp_path: Path) -> None:
    policy = load_policy(POLICY)
    with pytest.raises(PolicyError, match="is not allowed"):
        require_allowed(
            policy,
            "skillcorner",
            DataUse.READ_PREPROCESS,
            source_revision="4340d274572876239c154c90bc507a9b3250a656",
        )


def test_missing_status_axis_fails(tmp_path: Path) -> None:
    path = write_modified_policy(
        tmp_path,
        lambda values: values["providers"][0]["statuses"].pop("LICENSE_VERIFIED"),
    )
    with pytest.raises(PolicyError, match="status axes"):
        load_policy(path)


def test_unpinned_provider_revision_fails(tmp_path: Path) -> None:
    path = write_modified_policy(
        tmp_path,
        lambda values: values["providers"][0].__setitem__("source_revision", ""),
    )
    with pytest.raises(PolicyError, match="revision is not pinned"):
        load_policy(path)


def test_pass_does_not_propagate_to_other_use(tmp_path: Path) -> None:
    def mutate(values):
        provider = values["providers"][0]
        for axis in (
            "PUBLIC_SOURCE_VERIFIED",
            "LICENSE_VERIFIED",
            "INTERNAL_RESEARCH_AUTHORIZED",
        ):
            provider["statuses"][axis] = "PASS"
        provider["uses"]["read_preprocess"] = {
            "status": "PASS",
            "evidence_ids": ["EV-AUTH-SC-README"],
            "conditions": [],
        }

    path = write_modified_policy(tmp_path, mutate)
    policy = load_policy(path)
    revision = "4340d274572876239c154c90bc507a9b3250a656"
    require_allowed(policy, "skillcorner", DataUse.READ_PREPROCESS, source_revision=revision)
    with pytest.raises(PolicyError, match="EVALUATION_AUTHORIZED=HOLD"):
        require_allowed(
            policy,
            "skillcorner",
            DataUse.EVALUATION_REFERENCE,
            source_revision=revision,
        )


def test_pass_use_without_evidence_id_fails(tmp_path: Path) -> None:
    def mutate(values):
        provider = values["providers"][0]
        for axis in (
            "PUBLIC_SOURCE_VERIFIED",
            "LICENSE_VERIFIED",
            "INTERNAL_RESEARCH_AUTHORIZED",
        ):
            provider["statuses"][axis] = "PASS"
        provider["uses"]["read_preprocess"] = {
            "status": "PASS",
            "evidence_ids": [],
            "conditions": [],
        }

    path = write_modified_policy(tmp_path, mutate)
    policy = load_policy(path)
    with pytest.raises(PolicyError, match="no evidence IDs"):
        require_allowed(
            policy,
            "skillcorner",
            DataUse.READ_PREPROCESS,
            source_revision="4340d274572876239c154c90bc507a9b3250a656",
        )


def test_source_revision_mismatch_fails() -> None:
    policy = load_policy(POLICY)
    with pytest.raises(PolicyError, match="revision mismatch"):
        require_source_identity(policy, "skillcorner", "different-revision")


def test_label_profile_missing_definition_or_mapping_evidence_fails(tmp_path: Path) -> None:
    path = write_modified_policy(
        tmp_path,
        lambda values: values["providers"][0]["label_profiles"][0].pop(
            "provider_label_definition_id"
        ),
    )
    with pytest.raises(PolicyError, match="label profile"):
        load_policy(path)

    path = write_modified_policy(
        tmp_path,
        lambda values: values["providers"][0]["label_profiles"][0].__setitem__(
            "mapping_evidence", []
        ),
    )
    with pytest.raises(PolicyError, match="mapping evidence"):
        load_policy(path)


def test_label_profile_cannot_declare_model_input_role(tmp_path: Path) -> None:
    path = write_modified_policy(
        tmp_path,
        lambda values: values["providers"][0]["label_profiles"][0]["roles"].append("MODEL_INPUT"),
    )
    with pytest.raises(PolicyError, match="cannot include MODEL_INPUT"):
        load_policy(path)


@pytest.mark.parametrize(
    ("provider", "revision"),
    [
        ("metrica", "e706dd506b360d69d9d123d5b8026e7294b13996"),
        ("soccertrack_v2", "325bd4c57ee8e135ab652f3921d274526ada496b"),
    ],
)
def test_other_real_providers_are_hold(provider: str, revision: str) -> None:
    policy = load_policy(POLICY)
    with pytest.raises(PolicyError):
        require_allowed(
            policy,
            provider,
            DataUse.READ_PREPROCESS,
            source_revision=revision,
        )


def test_real_audit_cli_fails_policy_before_external_root(tmp_path: Path) -> None:
    environment = dict(os.environ)
    environment["MTAH_EXTERNAL_DATA_DIR"] = str(tmp_path / "nonexistent")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "audit_external.py"),
            "--output",
            str(tmp_path / "audit.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert result.returncode == 1
    assert "is not allowed" in result.stderr
    assert "missing" not in result.stderr.lower()
    assert not (tmp_path / "audit.json").exists()


def test_audit_evaluation_hold_fails_before_output(tmp_path: Path) -> None:
    def mutate(values):
        provider = values["providers"][0]
        for axis in (
            "PUBLIC_SOURCE_VERIFIED",
            "LICENSE_VERIFIED",
            "INTERNAL_RESEARCH_AUTHORIZED",
        ):
            provider["statuses"][axis] = "PASS"
        provider["uses"]["read_preprocess"] = {
            "status": "PASS",
            "evidence_ids": ["EV-AUTH-SC-README"],
            "conditions": [],
        }

    policy_path = write_modified_policy(tmp_path, mutate)
    output = tmp_path / "audit.json"
    environment = dict(os.environ)
    environment["MTAH_EXTERNAL_DATA_DIR"] = str(tmp_path / "nonexistent")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "audit_external.py"),
            "--policy",
            str(policy_path),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert result.returncode == 1
    assert "evaluation_reference" in result.stderr
    assert not output.exists()


def test_ta01_audit_uses_authorized_snapshot_after_config_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_audit_fixture(tmp_path, match_ids=("101", "102"))
    output = tmp_path / "audit.json"
    config_path = fixture["sources"]["101"]["config"]
    original_loader = audit_module.load_skillcorner_match_from_snapshot

    def swapping_loader(snapshot, external_root, expected_identity):
        config_path.write_text(
            fixture["sources"]["102"]["config"].read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return original_loader(snapshot, external_root, expected_identity)

    monkeypatch.setattr(
        audit_module,
        "load_skillcorner_match_from_snapshot",
        swapping_loader,
    )
    assert run_audit(fixture, output) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["match_id"] == "101"
    assert report["source_integrity"]["source_identity_sha256"]
    assert json.loads(config_path.read_text(encoding="utf-8"))["match_id"] == "102"


def test_ta02_audit_rejects_data_file_replacement_after_authorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_audit_fixture(tmp_path)
    output = tmp_path / "audit.json"
    tracking_path = fixture["sources"]["101"]["tracking"]
    original_loader = audit_module.load_skillcorner_match_from_snapshot

    def swapping_loader(snapshot, external_root, expected_identity):
        tracking_path.write_text('{"frame":0}\n', encoding="utf-8")
        return original_loader(snapshot, external_root, expected_identity)

    monkeypatch.setattr(
        audit_module,
        "load_skillcorner_match_from_snapshot",
        swapping_loader,
    )
    assert run_audit(fixture, output) == 1
    assert not output.exists()


def test_ta03_audit_rejects_actual_identity_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_audit_fixture(tmp_path, match_ids=("101", "102"))
    output = tmp_path / "audit.json"
    original_loader = audit_module.load_skillcorner_match_from_snapshot
    other_identity = build_source_identity(fixture["sources"]["102"]["config"])

    def mismatched_loader(snapshot, external_root, expected_identity):
        loaded = original_loader(snapshot, external_root, expected_identity)
        return replace(loaded, actual_source_identity=other_identity)

    monkeypatch.setattr(
        audit_module,
        "load_skillcorner_match_from_snapshot",
        mismatched_loader,
    )
    assert run_audit(fixture, output) == 1
    assert not output.exists()


def test_ta04_normal_audit_records_snapshot_provenance(tmp_path: Path) -> None:
    fixture = prepare_audit_fixture(tmp_path)
    output = tmp_path / "audit.json"
    assert run_audit(fixture, output) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["match_id"] == "101"
    assert set(report["source_integrity"]["actual_checksums"]) == {
        "license",
        "readme",
        "tracking",
        "phases",
        "match",
    }
    assert len(report["source_integrity"]["source_identity_sha256"]) == 64
    assert len(report["source_integrity"]["source_snapshot_digest"]) == 64


def test_ta05_runner_and_audit_share_snapshot_identity(tmp_path: Path) -> None:
    fixture = prepare_audit_fixture(tmp_path)
    output = tmp_path / "audit.json"
    assert run_audit(fixture, output) == 0
    snapshot = create_skillcorner_manifest_snapshot(fixture["sources"]["101"]["config"])
    identity = build_source_identity_from_manifest(snapshot.manifest)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["source_integrity"]["source_identity_sha256"] == (identity.source_identity_sha256)


def test_ta06_production_scripts_do_not_use_mutable_loader() -> None:
    for path in sorted((ROOT / "scripts").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "load_skillcorner_match(" not in source, path
    audit_source = (ROOT / "scripts" / "audit_external.py").read_text(encoding="utf-8")
    assert "create_skillcorner_manifest_snapshot(" in audit_source
    assert "load_skillcorner_match_from_snapshot(" in audit_source


def test_ta07_failed_audit_leaves_no_success_or_partial_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepare_audit_fixture(tmp_path)
    output = tmp_path / "audit.json"
    output.write_text('{"sentinel":true}\n', encoding="utf-8")
    before = output.read_bytes()
    original_loader = audit_module.load_skillcorner_match_from_snapshot

    def mismatched_loader(snapshot, external_root, expected_identity):
        loaded = original_loader(snapshot, external_root, expected_identity)
        checksums = dict(loaded.actual_checksums)
        checksums["tracking"] = "0" * 64
        return replace(loaded, actual_checksums=checksums)

    monkeypatch.setattr(
        audit_module,
        "load_skillcorner_match_from_snapshot",
        mismatched_loader,
    )
    assert run_audit(fixture, output) == 1
    assert output.read_bytes() == before


def test_ta08_handoff_documents_have_no_pending_head_placeholders() -> None:
    for name in (
        "07_工程师交付回执.md",
        "DP-006_FINAL_ASSURANCE_HANDOFF.md",
    ):
        text = (ROOT / "docs" / "policy" / name).read_text(encoding="utf-8")
        assert "PENDING_PUSH" not in text
        assert "PENDING_FINAL" not in text
