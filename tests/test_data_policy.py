import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mtah_possession.governance.policy import (
    DataUse,
    PolicyError,
    PolicyStatus,
    load_policy,
    require_allowed,
    require_source_identity,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "configs" / "policy" / "external-data-policy-v2.json"


def write_modified_policy(tmp_path: Path, mutate) -> Path:
    values = json.loads(POLICY.read_text(encoding="utf-8"))
    mutate(values)
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


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
