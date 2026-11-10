#!/usr/bin/env python3
"""Verify CDA-v2 file manifest, required layout, and every ZIP archive."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from pathlib import Path

REQUIRED = (
    "README.md",
    "MANIFEST.sha256",
    "00_SOURCE_REGISTRY/DATA_SOURCE_MASTER.csv",
    "00_SOURCE_REGISTRY/ACCESS_AND_LICENSE.csv",
    "00_SOURCE_REGISTRY/EXCLUDED_AND_DEFERRED.csv",
    "02_MATCH_INVENTORY/MATCH_INVENTORY.csv",
    "03_SCHEMA_DOCUMENTATION/DATA_SCHEMA.md",
    "04_QUALITY_ASSESSMENT/QUALITY_ASSESSMENT.csv",
    "04_QUALITY_ASSESSMENT/QUALITY_REPORT.md",
    "04_QUALITY_ASSESSMENT/FILE_INVENTORY.csv",
    "05_ACCESS_TOOLS/SOURCE_READERS/cda_v2/readers.py",
    "05_ACCESS_TOOLS/BASIC_EXAMPLES/inspect_sources.py",
    "06_HANDOFF/RESEARCHER_QUICKSTART.md",
    "06_HANDOFF/ACQUISITION_LOG.md",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_root", type=Path)
    parser.add_argument("--archive-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.package_root.resolve()
    archive_root = args.archive_root.resolve()
    missing = [relative for relative in REQUIRED if not (root / relative).exists()]
    manifest_errors = []
    manifest_count = 0
    with (root / "MANIFEST.sha256").open(encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            manifest_count += 1
            digest, relative = line.split("  ", 1)
            path = root / relative
            if not path.exists():
                manifest_errors.append(f"missing: {relative}")
            elif sha256_file(path) != digest:
                manifest_errors.append(f"sha mismatch: {relative}")
    zip_results = []
    with (root / "archives" / "ZIP_INDEX.csv").open(encoding="utf-8", newline="") as handle:
        archive_rows = list(csv.DictReader(handle))
    for row in archive_rows:
        archive_path = archive_root / row["archive"]
        with zipfile.ZipFile(archive_path) as archive:
            bad = archive.testzip()
            zip_results.append(
                {
                    "archive": archive_path.name,
                    "members": len(archive.namelist()),
                    "testzip": bad,
                    "sha256_matches": sha256_file(archive_path) == row["sha256"],
                }
            )
    cache_files = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and (
            "__pycache__" in path.relative_to(root).parts or path.suffix.lower() in {".pyc", ".pyo"}
        )
    ]
    result = {
        "status": "PASS"
        if not missing
        and not manifest_errors
        and all(item["testzip"] is None for item in zip_results)
        and all(item["sha256_matches"] for item in zip_results)
        and not cache_files
        else "FAIL",
        "missing_required": missing,
        "manifest_entries": manifest_count,
        "manifest_errors": manifest_errors,
        "cache_files": cache_files,
        "zip_results": zip_results,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
