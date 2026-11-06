"""Evaluation report versioning and deterministic report identity."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

SOURCE_ADAPTER_VERSION = "1.1.0"
EVALUATION_CONTRACT_VERSION = "1.1.0"


def report_with_identity(
    payload: dict[str, Any],
    *,
    code_commit: str,
    config_version: str,
) -> dict[str, Any]:
    if not code_commit.strip():
        raise ValueError("code_commit is required")
    report = deepcopy(payload)
    report_hash = hashlib.sha256(
        json.dumps(
            report,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    prediction_hashes = {
        name: result["metrics"]["prediction_sha256"]
        for name, result in report.get("candidates", {}).items()
    }
    report["provenance"] = {
        "code_commit": code_commit,
        "source_adapter_version": SOURCE_ADAPTER_VERSION,
        "config_version": config_version,
        "evaluation_contract_version": EVALUATION_CONTRACT_VERSION,
        "input_sha256": dict(report.get("source_checksums", {})),
        "prediction_sha256": prediction_hashes,
        "report_sha256": report_hash,
    }
    return report
