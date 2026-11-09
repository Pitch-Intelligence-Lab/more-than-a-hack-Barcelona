#!/usr/bin/env python3
"""Verify source files against pinned Git/Hugging Face tree identities."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any


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


def verify_idssse(root: Path, tree_path: Path) -> dict[str, Any]:
    tree = json.loads(tree_path.read_text(encoding="utf-8"))
    errors = []
    checked = 0
    for item in tree:
        if item["type"] != "file":
            continue
        path = root / item["path"]
        checked += 1
        if not path.exists():
            errors.append(f"missing: {item['path']}")
            continue
        if path.stat().st_size != item["size"]:
            errors.append(f"size mismatch: {item['path']}")
            continue
        lfs = item.get("lfs")
        if lfs is not None:
            if sha256_file(path) != lfs["oid"]:
                errors.append(f"LFS SHA-256 mismatch: {item['path']}")
        elif git_blob_sha1(path) != item["oid"]:
            errors.append(f"Git blob SHA-1 mismatch: {item['path']}")
    return {"checked": checked, "errors": errors, "status": "PASS" if not errors else "FAIL"}


def verify_statsbomb(root: Path, tree_path: Path) -> dict[str, Any]:
    raw = json.loads(tree_path.read_text(encoding="utf-8"))
    blobs = [item for item in raw["tree"] if item["type"] == "blob"]

    def check(item: dict[str, Any]) -> str | None:
        path = root / item["path"]
        if not path.exists():
            return f"missing: {item['path']}"
        if path.stat().st_size != item["size"]:
            return f"size mismatch: {item['path']}"
        if git_blob_sha1(path) != item["sha"]:
            return f"Git blob SHA-1 mismatch: {item['path']}"
        return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        errors = [error for error in executor.map(check, blobs) if error is not None]
    return {
        "checked": len(blobs),
        "errors": errors[:50],
        "error_count": len(errors),
        "status": "PASS" if not errors else "FAIL",
    }


def verify_skillcorner(root: Path, expected_revision: str) -> dict[str, Any]:
    revision = git_head(root)
    pointer_errors = []
    tracking_files = sorted((root / "data" / "matches").glob("*/*_tracking_extrapolated.jsonl"))
    for path in tracking_files:
        if path.open("rb").read(129).startswith(b"version https://git-lfs.github.com/spec/v1"):
            pointer_errors.append(str(path.relative_to(root)))
    errors = []
    if revision != expected_revision:
        errors.append(f"revision mismatch: {revision}")
    errors.extend(f"LFS pointer: {path}" for path in pointer_errors)
    return {
        "revision": revision,
        "tracking_files": len(tracking_files),
        "lfs_pointer_count": len(pointer_errors),
        "errors": errors,
        "status": "PASS" if not errors else "FAIL",
    }


def verify_wyscout(root: Path, expected_revision: str) -> dict[str, Any]:
    revision = git_head(root)
    count = len(list((root / "processed-v2" / "files").glob("*.json")))
    errors = []
    if revision != expected_revision:
        errors.append(f"revision mismatch: {revision}")
    if count != 1941:
        errors.append(f"expected 1941 match JSON files, found {count}")
    return {
        "revision": revision,
        "match_json_files": count,
        "errors": errors,
        "status": "PASS" if not errors else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_root", type=Path)
    args = parser.parse_args()
    root = args.package_root.resolve()
    raw = root / "01_RAW_DATA"
    result = {
        "SkillCorner": verify_skillcorner(
            raw / "skillcorner" / "repository",
            "4340d274572876239c154c90bc507a9b3250a656",
        ),
        "IDSSE": verify_idssse(
            raw / "idsse" / "repository",
            raw / "idsse" / "HF_TREE.json",
        ),
        "StatsBomb": verify_statsbomb(
            raw / "statsbomb" / "repository",
            raw / "statsbomb" / "GITHUB_TREE_RAW.json",
        ),
        "Wyscout": verify_wyscout(
            raw / "wyscout" / "repository",
            "ebc4c54c1093c420a81ce442c69e4186fab33bb4",
        ),
    }
    result["status"] = (
        "PASS" if all(item["status"] == "PASS" for item in result.values()) else "FAIL"
    )
    output = root / "04_QUALITY_ASSESSMENT" / "SOURCE_INTEGRITY_VERIFICATION.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
