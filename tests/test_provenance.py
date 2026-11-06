import pytest

from mtah_possession.evaluation.provenance import (
    EVALUATION_CONTRACT_VERSION,
    SOURCE_ADAPTER_VERSION,
    report_with_identity,
)


def test_report_identity_contains_versions_inputs_predictions_and_hash() -> None:
    payload = {
        "source_checksums": {"tracking": "abc"},
        "candidates": {
            "candidate": {"metrics": {"prediction_sha256": "def"}},
        },
    }
    report = report_with_identity(
        payload,
        code_commit="0123456789abcdef",
        config_version="1.0",
    )
    provenance = report["provenance"]
    assert provenance["code_commit"] == "0123456789abcdef"
    assert provenance["source_adapter_version"] == SOURCE_ADAPTER_VERSION
    assert provenance["evaluation_contract_version"] == EVALUATION_CONTRACT_VERSION
    assert provenance["config_version"] == "1.0"
    assert provenance["input_sha256"] == {"tracking": "abc"}
    assert provenance["prediction_sha256"] == {"candidate": "def"}
    assert len(provenance["report_sha256"]) == 64


def test_report_identity_requires_code_commit() -> None:
    with pytest.raises(ValueError, match="code_commit"):
        report_with_identity({}, code_commit="", config_version="1.0")
