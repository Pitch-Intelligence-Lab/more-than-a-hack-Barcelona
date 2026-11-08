"""Verified, audit-only migration receipts backed by Git objects."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from mtah_possession.governance.policy import PolicyError

MIGRATION_TOOL_PATH = "scripts/migrate_holdout_ledger.py"
MIGRATION_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "event_type",
        "status",
        "promotion_authorized",
        "source_provider",
        "source_holdout_id",
        "source_match_ids",
        "source_protocol_version",
        "source_ledger_head_sha256",
        "legacy_combined_freeze",
        "old_code_commit",
        "migration_commit",
        "migration_tool_sha256",
        "migration_rule_version",
        "model_freeze_spec_sha256",
        "evaluation_freeze_spec_sha256",
        "policy_sha256",
        "old_holdout_manifest_sha256",
        "target_model_identity",
        "target_evaluation_identity",
        "target_split_manifest_sha256",
        "target_holdout_manifest_sha256",
        "governance_identity_digest",
        "approver",
        "approval_evidence_ids",
        "reason",
        "previous_record_sha256",
    }
)


def validate_migration_receipt(receipt: Any) -> dict[str, Any]:
    _validate_receipt_shape(receipt)
    return receipt


def load_verified_migration_receipt(
    *,
    repo_root: str | os.PathLike[str],
    approval_commit: str,
    migration_commit: str,
    receipt_path: str | os.PathLike[str],
    expected: dict[str, Any],
) -> dict[str, Any]:
    root = Path(repo_root).resolve(strict=True)
    relative_receipt = _relative_path(receipt_path)
    resolved_approval_commit = _git(
        root,
        "rev-parse",
        "--verify",
        f"{approval_commit}^{{commit}}",
    ).strip()
    if resolved_approval_commit != approval_commit:
        raise PolicyError("approval commit is not a full repository commit")
    resolved_commit = _git(
        root,
        "rev-parse",
        "--verify",
        f"{migration_commit}^{{commit}}",
    ).strip()
    if resolved_commit != migration_commit:
        raise PolicyError("migration commit is not a full repository commit")
    committed_receipt = _git_bytes(
        root,
        "show",
        f"{approval_commit}:{relative_receipt}",
    )
    current_receipt_path = root / relative_receipt
    try:
        current_receipt = current_receipt_path.read_bytes()
    except OSError as error:
        raise PolicyError("migration approval receipt is missing") from error
    if current_receipt != committed_receipt:
        raise PolicyError("migration approval receipt differs from the approval commit")
    committed_tool = _git_bytes(
        root,
        "show",
        f"{migration_commit}:{MIGRATION_TOOL_PATH}",
    )
    current_tool_path = root / MIGRATION_TOOL_PATH
    try:
        current_tool = current_tool_path.read_bytes()
    except OSError as error:
        raise PolicyError("migration tool is missing") from error
    if current_tool != committed_tool:
        raise PolicyError("migration tool differs from the migration commit")
    try:
        receipt = json.loads(committed_receipt)
    except json.JSONDecodeError as error:
        raise PolicyError("migration approval receipt is not valid JSON") from error
    _validate_receipt_shape(receipt)
    if receipt["migration_commit"] != migration_commit:
        raise PolicyError("migration receipt commit does not match the supplied commit")
    old_code_commit = _git(
        root,
        "rev-parse",
        "--verify",
        f"{receipt['old_code_commit']}^{{commit}}",
    ).strip()
    if old_code_commit != receipt["old_code_commit"]:
        raise PolicyError("old code commit is not present in the repository")
    tool_sha256 = hashlib.sha256(committed_tool).hexdigest()
    if receipt["migration_tool_sha256"] != tool_sha256:
        raise PolicyError("migration tool SHA-256 does not match the receipt")
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise PolicyError(f"migration receipt does not match approved {key}")
    return receipt


def _validate_receipt_shape(receipt: Any) -> None:
    if not isinstance(receipt, dict) or set(receipt) != MIGRATION_RECEIPT_FIELDS:
        raise PolicyError("migration receipt has missing or unknown fields")
    if receipt["schema_version"] != "1.0":
        raise PolicyError("migration receipt schema version is unsupported")
    if receipt["event_type"] != "FREEZE_PROTOCOL_MIGRATED":
        raise PolicyError("migration receipt event type is invalid")
    if receipt["status"] != "MIGRATED_AUDIT_ONLY":
        raise PolicyError("migration receipt status must be MIGRATED_AUDIT_ONLY")
    if receipt["promotion_authorized"] is not False:
        raise PolicyError("migration receipt cannot authorize Promotion")
    if receipt["source_protocol_version"] != "combined-policy-model-v1":
        raise PolicyError("migration source protocol is unsupported")
    if receipt["migration_rule_version"] != "1.0":
        raise PolicyError("migration rule version is unsupported")
    source_matches = receipt["source_match_ids"]
    if (
        not isinstance(source_matches, list)
        or not source_matches
        or not all(isinstance(match_id, str) and match_id for match_id in source_matches)
        or source_matches != sorted(set(source_matches))
    ):
        raise PolicyError("migration source match IDs are invalid")
    evidence_ids = receipt["approval_evidence_ids"]
    if (
        not isinstance(evidence_ids, list)
        or not evidence_ids
        or not all(isinstance(item, str) and item for item in evidence_ids)
        or evidence_ids != sorted(set(evidence_ids))
    ):
        raise PolicyError("migration approval evidence IDs are invalid")
    for field in (
        "source_ledger_head_sha256",
        "migration_tool_sha256",
        "model_freeze_spec_sha256",
        "evaluation_freeze_spec_sha256",
        "policy_sha256",
        "old_holdout_manifest_sha256",
        "target_split_manifest_sha256",
        "target_holdout_manifest_sha256",
        "governance_identity_digest",
        "previous_record_sha256",
    ):
        _validate_sha256(receipt[field], field)
    for field in ("old_code_commit", "migration_commit"):
        _validate_commit(receipt[field], field)
    if not isinstance(receipt["approver"], str) or not receipt["approver"].strip():
        raise PolicyError("migration approver is required")
    if not isinstance(receipt["reason"], str) or not receipt["reason"].strip():
        raise PolicyError("migration reason is required")
    model_identity = receipt["target_model_identity"]
    if not isinstance(model_identity, dict) or set(model_identity) != {
        "model",
        "feature_set",
        "configuration",
        "hyperparameters",
    }:
        raise PolicyError("migration target model identity is invalid")
    for field, value in model_identity.items():
        _validate_sha256(value, field)
    evaluation_identity = receipt["target_evaluation_identity"]
    if not isinstance(evaluation_identity, dict) or set(evaluation_identity) != {
        "evaluation_script",
        "metric_contract_version",
    }:
        raise PolicyError("migration target evaluation identity is invalid")
    _validate_sha256(evaluation_identity["evaluation_script"], "evaluation script")
    if (
        not isinstance(evaluation_identity["metric_contract_version"], str)
        or not evaluation_identity["metric_contract_version"].strip()
    ):
        raise PolicyError("migration target metric contract is invalid")
    legacy_freeze = receipt["legacy_combined_freeze"]
    if not isinstance(legacy_freeze, dict) or not all(
        isinstance(value, str) and value for value in legacy_freeze.values()
    ):
        raise PolicyError("migration legacy combined freeze is invalid")


def _relative_path(path: str | os.PathLike[str]) -> str:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PolicyError("migration receipt path must be repository-relative")
    return candidate.as_posix()


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise PolicyError("could not invoke Git for migration verification") from error
    if result.returncode != 0:
        raise PolicyError(f"Git verification failed: {result.stderr.strip()}")
    return result.stdout


def _git_bytes(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise PolicyError("could not invoke Git for migration verification") from error
    if result.returncode != 0:
        raise PolicyError("Git object is missing for migration verification")
    return result.stdout


def _validate_sha256(value: Any, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PolicyError(f"migration {label} is invalid")


def _validate_commit(value: Any, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PolicyError(f"migration {label} is invalid")
