"""Compute trusted freeze hashes from real artifact files."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from mtah_possession.governance.holdout import FreezeHashes
from mtah_possession.governance.policy import PolicyError

LEGACY_ARTIFACT_CATEGORIES = (
    "model",
    "feature_set",
    "configuration",
    "hyperparameters",
    "evaluation_script",
    "metric_contract",
)
SEPARATED_ARTIFACT_CATEGORIES = (
    "prediction_code",
    "feature_set",
    "data_transform",
    "algorithm_configuration",
    "hyperparameters",
    "evaluation_script",
    "metric_contract",
)
GOVERNANCE_ONLY_PREFIXES = (
    "src/mtah_possession/governance/",
    "configs/policy/",
    "outputs/holdout/",
)


def compute_freeze_hashes(spec_path: str | os.PathLike[str]) -> FreezeHashes:
    path = Path(spec_path).resolve(strict=False)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyError(f"could not read artifact freeze spec: {path}") from error
    if not isinstance(raw, dict):
        raise PolicyError("artifact freeze spec root must be an object")
    schema_version = raw.get("schema_version")
    if schema_version == "1.0":
        required = {"schema_version", "artifact_root", "artifacts", "metric_contract_version"}
        categories = LEGACY_ARTIFACT_CATEGORIES
    elif schema_version == "2.0":
        required = {
            "schema_version",
            "artifact_root",
            "artifacts",
            "category_reasons",
            "metric_contract_version",
        }
        categories = SEPARATED_ARTIFACT_CATEGORIES
    else:
        raise PolicyError("artifact freeze schema_version must be 1.0 or 2.0")
    if set(raw) != required:
        raise PolicyError("artifact freeze spec has missing or unknown fields")
    artifacts = raw["artifacts"]
    if not isinstance(artifacts, dict) or set(artifacts) != set(categories):
        raise PolicyError("artifact freeze spec categories are incomplete")
    if schema_version == "2.0":
        reasons = raw["category_reasons"]
        if (
            not isinstance(reasons, dict)
            or set(reasons) != set(categories)
            or not all(isinstance(reason, str) and reason.strip() for reason in reasons.values())
        ):
            raise PolicyError("artifact freeze category reasons are incomplete")
    raw_root = path.parent / str(raw["artifact_root"])
    if raw_root.is_symlink():
        raise PolicyError("symlink artifact roots are not allowed")
    try:
        root = raw_root.resolve(strict=True)
    except OSError as error:
        raise PolicyError("artifact root is missing or unreadable") from error
    if not root.is_dir():
        raise PolicyError("artifact root must be a directory")

    category_hashes: dict[str, str] = {}
    category_files: dict[str, list[tuple[str, str]]] = {}
    for category in categories:
        paths = artifacts[category]
        if (
            not isinstance(paths, list)
            or not paths
            or not all(isinstance(item, str) and item for item in paths)
        ):
            raise PolicyError(f"artifact category {category} must be a non-empty path list")
        files: list[tuple[str, str]] = []
        for relative in paths:
            try:
                files.extend(_expand_and_hash(root, relative))
            except OSError as error:
                raise PolicyError(f"artifact path is missing or unreadable: {relative}") from error
        if not files:
            raise PolicyError(f"artifact category {category} contains no files")
        category_files[category] = files
        category_hashes[category] = _combined_hash(category, files)
    if schema_version == "2.0":
        _validate_separated_paths(category_files)

    version = raw["metric_contract_version"]
    if not isinstance(version, str) or not version.strip():
        raise PolicyError("metric_contract_version is missing")
    if schema_version == "1.0":
        return FreezeHashes(
            model=category_hashes["model"],
            feature_set=category_hashes["feature_set"],
            configuration=category_hashes["configuration"],
            hyperparameters=category_hashes["hyperparameters"],
            evaluation_script=category_hashes["evaluation_script"],
            metric_contract_version=f"{version}:{category_hashes['metric_contract']}",
        )
    return FreezeHashes(
        model=_combined_hash(
            "model",
            [
                ("prediction_code", category_hashes["prediction_code"]),
                ("data_transform", category_hashes["data_transform"]),
            ],
        ),
        feature_set=category_hashes["feature_set"],
        configuration=_combined_hash(
            "configuration",
            [("algorithm_configuration", category_hashes["algorithm_configuration"])],
        ),
        hyperparameters=category_hashes["hyperparameters"],
        evaluation_script=category_hashes["evaluation_script"],
        metric_contract_version=f"{version}:{category_hashes['metric_contract']}",
    )


def _expand_and_hash(root: Path, relative: str) -> list[tuple[str, str]]:
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise PolicyError(f"artifact path escapes the artifact root: {relative}")
    unresolved = root / relative_path
    if _contains_symlink(root, unresolved):
        raise PolicyError(f"symlink artifacts are not allowed: {relative}")
    candidate = unresolved.resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise PolicyError(f"artifact path escapes the artifact root: {relative}") from error
    if candidate.is_file():
        return [(candidate.relative_to(root).as_posix(), _sha256(candidate))]
    if not candidate.is_dir():
        raise PolicyError(f"artifact is not a regular file or directory: {relative}")

    files: list[tuple[str, str]] = []
    for child in sorted(candidate.rglob("*")):
        if child.is_symlink():
            raise PolicyError(f"symlink artifact escapes are not allowed: {child}")
        if not child.is_file() or "__pycache__" in child.parts or child.suffix == ".pyc":
            continue
        files.append((child.relative_to(root).as_posix(), _sha256(child)))
    return files


def _contains_symlink(root: Path, candidate: Path) -> bool:
    current = candidate
    while current != root:
        if current.is_symlink():
            return True
        current = current.parent
    return root.is_symlink()


def _combined_hash(category: str, files: list[tuple[str, str]]) -> str:
    payload: dict[str, Any] = {
        "category": category,
        "files": [{"path": path, "sha256": digest} for path, digest in sorted(files)],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _validate_separated_paths(
    category_files: dict[str, list[tuple[str, str]]],
) -> None:
    for category, files in category_files.items():
        for path, _digest in files:
            if any(path.startswith(prefix) for prefix in GOVERNANCE_ONLY_PREFIXES):
                raise PolicyError(
                    f"governance-only artifact {path} is not allowed in model freeze "
                    f"category {category}"
                )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
