"""Compute trusted freeze hashes from real artifact files."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from mtah_possession.governance.holdout import FreezeHashes
from mtah_possession.governance.policy import PolicyError

ARTIFACT_CATEGORIES = (
    "model",
    "feature_set",
    "configuration",
    "hyperparameters",
    "evaluation_script",
    "metric_contract",
)


def compute_freeze_hashes(spec_path: str | os.PathLike[str]) -> FreezeHashes:
    path = Path(spec_path).resolve(strict=False)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyError(f"could not read artifact freeze spec: {path}") from error
    required = {"schema_version", "artifact_root", "artifacts", "metric_contract_version"}
    if not isinstance(raw, dict) or set(raw) != required:
        raise PolicyError("artifact freeze spec has missing or unknown fields")
    if raw["schema_version"] != "1.0":
        raise PolicyError("artifact freeze schema_version must be 1.0")
    artifacts = raw["artifacts"]
    if not isinstance(artifacts, dict) or set(artifacts) != set(ARTIFACT_CATEGORIES):
        raise PolicyError("artifact freeze spec categories are incomplete")
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
    for category in ARTIFACT_CATEGORIES:
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
        category_hashes[category] = _combined_hash(category, files)

    version = raw["metric_contract_version"]
    if not isinstance(version, str) or not version.strip():
        raise PolicyError("metric_contract_version is missing")
    return FreezeHashes(
        model=category_hashes["model"],
        feature_set=category_hashes["feature_set"],
        configuration=category_hashes["configuration"],
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
