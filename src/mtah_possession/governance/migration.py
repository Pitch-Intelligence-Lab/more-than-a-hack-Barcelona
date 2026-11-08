"""Verified, audit-only migration receipts backed by Git objects."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from mtah_possession.governance.artifacts import compute_freeze_hashes
from mtah_possession.governance.holdout import FreezeHashes
from mtah_possession.governance.policy import PolicyError
from mtah_possession.governance.source import (
    SourceIdentity,
    SourceIdentitySet,
    build_single_source_identity_set,
    build_source_identity,
    build_source_identity_set,
    source_identity_from_dict,
    source_identity_set_from_dict,
)

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
        "source_config_sha256",
        "old_holdout_manifest_sha256",
        "target_model_identity",
        "target_evaluation_identity",
        "target_split_manifest_sha256",
        "target_holdout_manifest_sha256",
        "target_source_identity",
        "target_source_identity_set",
        "governance_identity_digest",
        "approver",
        "approval_evidence_ids",
        "reason",
        "previous_record_sha256",
    }
)


@dataclass(frozen=True)
class VerifiedMigration:
    receipt: dict[str, Any]
    model_freeze: FreezeHashes
    source_identity: SourceIdentity
    source_identity_set: SourceIdentitySet


def validate_migration_receipt(receipt: Any) -> dict[str, Any]:
    _validate_receipt_shape(receipt)
    return receipt


def load_verified_migration_receipt(
    *,
    repo_root: str | os.PathLike[str],
    approval_commit: str,
    migration_commit: str,
    receipt_path: str | os.PathLike[str],
    freeze_spec_path: str | os.PathLike[str],
    split_manifest_path: str | os.PathLike[str],
    holdout_manifest_path: str | os.PathLike[str],
    policy_path: str | os.PathLike[str],
    source_config_path: str | os.PathLike[str],
    source_set_path: str | os.PathLike[str] | None,
    expected: dict[str, Any],
) -> VerifiedMigration:
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
    _require_ancestor(root, migration_commit, approval_commit, "approval")
    _require_ancestor(root, old_code_commit, migration_commit, "old code")
    tool_sha256 = hashlib.sha256(committed_tool).hexdigest()
    if receipt["migration_tool_sha256"] != tool_sha256:
        raise PolicyError("migration tool SHA-256 does not match the receipt")
    verified = _verify_git_targets(
        root=root,
        migration_commit=migration_commit,
        receipt=receipt,
        freeze_spec_path=freeze_spec_path,
        split_manifest_path=split_manifest_path,
        holdout_manifest_path=holdout_manifest_path,
        policy_path=policy_path,
        source_config_path=source_config_path,
        source_set_path=source_set_path,
    )
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise PolicyError(f"migration receipt does not match approved {key}")
    return verified


def _verify_git_targets(
    *,
    root: Path,
    migration_commit: str,
    receipt: dict[str, Any],
    freeze_spec_path: str | os.PathLike[str],
    split_manifest_path: str | os.PathLike[str],
    holdout_manifest_path: str | os.PathLike[str],
    policy_path: str | os.PathLike[str],
    source_config_path: str | os.PathLike[str],
    source_set_path: str | os.PathLike[str] | None,
) -> VerifiedMigration:
    freeze_spec = _relative_path(freeze_spec_path)
    split_manifest = _relative_path(split_manifest_path)
    holdout_manifest = _relative_path(holdout_manifest_path)
    policy = _relative_path(policy_path)
    source_config = _relative_path(source_config_path)
    archive = _git_bytes(root, "archive", "--format=tar", migration_commit)
    with tempfile.TemporaryDirectory() as temporary:
        archive_root = Path(temporary)
        _extract_archive(archive, archive_root)
        git_freeze_spec = archive_root / freeze_spec
        if not git_freeze_spec.is_file():
            raise PolicyError("migration commit is missing target freeze spec")
        try:
            git_model_freeze = compute_freeze_hashes(git_freeze_spec)
        except (OSError, ValueError) as error:
            raise PolicyError(
                "could not recompute target identities from migration commit"
            ) from error
        git_source_config = archive_root / source_config
        if not git_source_config.is_file():
            raise PolicyError("migration commit is missing source config")
        git_source_identity = build_source_identity(git_source_config)
        git_holdout_path = archive_root / holdout_manifest
        try:
            holdout_values = json.loads(git_holdout_path.read_text(encoding="utf-8"))
            holdout_matches = tuple(str(item) for item in holdout_values["matches"])
        except (KeyError, TypeError, OSError, json.JSONDecodeError) as error:
            raise PolicyError("migration target Holdout Manifest is invalid") from error
        if source_set_path is not None:
            git_source_set = build_source_identity_set(
                archive_root / _relative_path(source_set_path),
                provider=git_source_identity.provider,
                holdout_matches=holdout_matches,
                source_root=archive_root,
            )
        else:
            if len(holdout_matches) != 1:
                raise PolicyError("multi-match migration requires a source-set descriptor")
            git_source_set = build_single_source_identity_set(
                provider=git_source_identity.provider,
                match_id=git_source_identity.match_id,
                source_config=git_source_config,
            )
        git_split_sha = _sha256_committed_file(archive_root, split_manifest)
        git_holdout_sha = _sha256_committed_file(archive_root, holdout_manifest)
        git_policy_sha = _sha256_committed_file(archive_root, policy)
        git_freeze_spec_sha = hashlib.sha256(git_freeze_spec.read_bytes()).hexdigest()
        _compare_receipt_targets(
            receipt=receipt,
            model_freeze=git_model_freeze,
            source_identity=git_source_identity,
            source_set=git_source_set,
            split_sha=git_split_sha,
            holdout_sha=git_holdout_sha,
            policy_sha=git_policy_sha,
            freeze_spec_sha=git_freeze_spec_sha,
        )

    current_freeze_spec = root / freeze_spec
    try:
        current_model_freeze = compute_freeze_hashes(current_freeze_spec)
        current_source_identity = build_source_identity(root / source_config)
        current_source_set = (
            build_source_identity_set(
                root / _relative_path(source_set_path),
                provider=current_source_identity.provider,
                holdout_matches=holdout_matches,
                source_root=root,
            )
            if source_set_path is not None
            else build_single_source_identity_set(
                provider=current_source_identity.provider,
                match_id=current_source_identity.match_id,
                source_config=root / source_config,
            )
        )
    except (OSError, ValueError) as error:
        raise PolicyError("could not recompute current target identities") from error
    if current_model_freeze != git_model_freeze:
        raise PolicyError("current worktree artifacts differ from migration commit")
    if current_source_identity != git_source_identity:
        raise PolicyError("current Source Identity differs from migration commit")
    if current_source_set != git_source_set:
        raise PolicyError("current SourceIdentitySet differs from migration commit")
    current_split_sha = _sha256_file(root / split_manifest)
    current_holdout_sha = _sha256_file(root / holdout_manifest)
    current_policy_sha = _sha256_file(root / policy)
    if (
        current_split_sha != git_split_sha
        or current_holdout_sha != git_holdout_sha
        or current_policy_sha != git_policy_sha
        or _sha256_file(current_freeze_spec) != git_freeze_spec_sha
    ):
        raise PolicyError("current worktree target files differ from migration commit")
    return VerifiedMigration(
        receipt=receipt,
        model_freeze=git_model_freeze,
        source_identity=git_source_identity,
        source_identity_set=git_source_set,
    )


def _compare_receipt_targets(
    *,
    receipt: dict[str, Any],
    model_freeze: FreezeHashes,
    source_identity: SourceIdentity,
    source_set: SourceIdentitySet,
    split_sha: str,
    holdout_sha: str,
    policy_sha: str,
    freeze_spec_sha: str,
) -> None:
    expected_model = {
        "model": model_freeze.model,
        "feature_set": model_freeze.feature_set,
        "configuration": model_freeze.configuration,
        "hyperparameters": model_freeze.hyperparameters,
    }
    expected_evaluation = {
        "evaluation_script": model_freeze.evaluation_script,
        "metric_contract_version": model_freeze.metric_contract_version,
    }
    comparisons = {
        "target_model_identity": expected_model,
        "target_evaluation_identity": expected_evaluation,
        "target_source_identity": source_identity.to_dict(),
        "target_source_identity_set": source_set.to_dict(),
        "target_split_manifest_sha256": split_sha,
        "target_holdout_manifest_sha256": holdout_sha,
        "policy_sha256": policy_sha,
        "source_config_sha256": source_identity.source_config_sha256,
        "model_freeze_spec_sha256": freeze_spec_sha,
        "evaluation_freeze_spec_sha256": freeze_spec_sha,
    }
    for key, expected in comparisons.items():
        if receipt.get(key) != expected:
            raise PolicyError(f"migration commit artifacts do not match receipt {key}")


def _require_ancestor(
    root: Path,
    ancestor: str,
    descendant: str,
    label: str,
) -> None:
    result = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, descendant],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise PolicyError(f"{label} commit is not an ancestor of migration commit")


def _extract_archive(archive: bytes, destination: Path) -> None:
    try:
        with tarfile.open(fileobj=BytesIO(archive), mode="r:") as handle:
            handle.extractall(destination, filter="data")
    except (OSError, tarfile.TarError) as error:
        raise PolicyError("could not extract migration commit artifacts") from error


def _sha256_committed_file(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        raise PolicyError(f"migration commit is missing target artifact: {relative}")
    return _sha256_file(path)


def _sha256_file(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise PolicyError(f"target artifact is unreadable: {path}") from error
    return hashlib.sha256(data).hexdigest()


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
        "source_config_sha256",
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
    source_identity = source_identity_from_dict(receipt["target_source_identity"])
    if source_identity.source_config_sha256 != receipt["source_config_sha256"]:
        raise PolicyError("migration source identity does not match source config")
    source_set = source_identity_set_from_dict(receipt["target_source_identity_set"])
    if source_set.provider != source_identity.provider:
        raise PolicyError("migration SourceIdentitySet provider is invalid")
    if source_identity.match_id not in source_set.identity_digests:
        raise PolicyError("migration Source Identity is not in SourceIdentitySet")
    if (
        source_set.identity_digests[source_identity.match_id]
        != source_identity.source_identity_sha256
    ):
        raise PolicyError("migration Source Identity map does not match source identity")
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
