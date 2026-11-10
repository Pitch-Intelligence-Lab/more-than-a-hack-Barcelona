#!/usr/bin/env python3
"""Verify source files using portable tree identities, without requiring .git."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

SOURCE_KEYS = {
    "SkillCorner": "skillcorner",
    "IDSSE": "idsse",
    "StatsBomb": "statsbomb",
    "Wyscout": "wyscout",
}


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    digest = hashlib.sha1()
    digest.update(f"blob {len(data)}\0".encode())
    digest.update(data)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head(repository: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def verify_file(item: dict[str, Any], root: Path) -> str | None:
    path = root / item["path"]
    if not path.is_file():
        return f"missing: {item['path']}"
    if path.stat().st_size != item["size"]:
        return f"size mismatch: {item['path']}"
    if item.get("sha256"):
        if sha256_file(path) != item["sha256"]:
            return f"SHA-256 mismatch: {item['path']}"
    elif item.get("lfs_sha256"):
        if sha256_file(path) != item["lfs_sha256"]:
            return f"LFS SHA-256 mismatch: {item['path']}"
    elif git_blob_sha1(path) != item["git_blob_sha1"]:
        return f"Git blob SHA-1 mismatch: {item['path']}"
    return None


def verify_portable_tree(
    source: str,
    package_root: Path,
    tree_path: Path,
) -> dict[str, Any]:
    identity = json.loads(tree_path.read_text(encoding="utf-8"))
    root = package_root / "01_RAW_DATA" / SOURCE_KEYS[source] / "repository"
    with ThreadPoolExecutor(max_workers=8) as executor:
        errors = [
            error
            for error in executor.map(
                lambda item: verify_file(item, root),
                identity["tree"],
            )
            if error is not None
        ]
    return {
        "source_url": identity["source_url"],
        "ref": identity["ref"],
        "commit": identity["commit"],
        "checked": len(identity["tree"]),
        "errors": errors[:50],
        "error_count": len(errors),
        "status": "PASS" if not errors else "FAIL",
    }


def verify_optional_git(source: str, package_root: Path, expected: str) -> dict[str, Any]:
    repository = package_root / "01_RAW_DATA" / SOURCE_KEYS[source] / "repository"
    if not (repository / ".git").exists():
        return {"status": "SKIPPED", "reason": ".git is absent"}
    actual = git_head(repository)
    return {
        "status": "PASS" if actual == expected else "FAIL",
        "actual": actual,
        "expected": expected,
    }


def verify(package_root: Path, *, include_git: bool = False) -> dict[str, Any]:
    registry_root = package_root / "00_SOURCE_REGISTRY"
    identities = json.loads(
        (registry_root / "PORTABLE_SOURCE_IDENTITIES.json").read_text(encoding="utf-8")
    )
    results = {}
    for source in SOURCE_KEYS:
        tree = registry_root / "PORTABLE_TREES" / f"{source.lower()}.json"
        results[source] = verify_portable_tree(source, package_root, tree)
        if include_git:
            results[source]["git"] = verify_optional_git(
                source,
                package_root,
                identities[source]["commit"],
            )
    results["status"] = (
        "PASS" if all(item["status"] == "PASS" for item in results.values()) else "FAIL"
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_root", type=Path)
    parser.add_argument("--include-git", action="store_true")
    args = parser.parse_args()
    package_root = args.package_root.resolve()
    result = verify(package_root, include_git=args.include_git)
    output = package_root / "04_QUALITY_ASSESSMENT" / "SOURCE_INTEGRITY_VERIFICATION.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
