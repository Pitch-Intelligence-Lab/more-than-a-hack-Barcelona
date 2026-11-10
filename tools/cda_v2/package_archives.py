#!/usr/bin/env python3
"""Copy readers/examples and create per-source ZIPs plus a unified manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

EXCLUDED_CACHE_NAMES = {"__pycache__"}
EXCLUDED_CACHE_SUFFIXES = {".pyc", ".pyo"}

SOURCE_ROOTS = {
    "SkillCorner": Path("01_RAW_DATA/skillcorner/repository"),
    "IDSSE": Path("01_RAW_DATA/idsse/repository"),
    "StatsBomb": Path("01_RAW_DATA/statsbomb/repository"),
    "Wyscout": Path("01_RAW_DATA/wyscout/repository"),
}
EXCLUDED_PARTS = {".git", ".range_parts", ".parts"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and not EXCLUDED_PARTS.intersection(path.relative_to(root).parts)
        and not is_cache_path(path.relative_to(root))
    )


def is_cache_path(relative_path: str | Path) -> bool:
    parts = Path(relative_path).parts
    return any(part in EXCLUDED_CACHE_NAMES for part in parts) or (
        bool(parts) and Path(parts[-1]).suffix.lower() in EXCLUDED_CACHE_SUFFIXES
    )


def remove_cache_artifacts(root: Path) -> int:
    removed = 0
    for path in sorted(root.rglob("*"), reverse=True):
        if not path.exists():
            continue
        relative = path.relative_to(root)
        if path.is_dir() and path.name in EXCLUDED_CACHE_NAMES:
            shutil.rmtree(path)
            removed += 1
        elif path.is_file() and is_cache_path(relative):
            path.unlink()
            removed += 1
    return removed


def copy_tools(delivery: Path, tools_source: Path) -> None:
    readers_dest = delivery / "05_ACCESS_TOOLS" / "SOURCE_READERS" / "cda_v2"
    examples_dest = delivery / "05_ACCESS_TOOLS" / "BASIC_EXAMPLES"
    if readers_dest.exists():
        shutil.copytree(
            tools_source,
            readers_dest,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "examples"),
        )
    else:
        shutil.copytree(
            tools_source,
            readers_dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "examples"),
        )
    shutil.copytree(
        tools_source / "examples",
        examples_dest,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(
        tools_source / "requirements.txt", delivery / "05_ACCESS_TOOLS" / "requirements.txt"
    )
    remove_cache_artifacts(delivery / "05_ACCESS_TOOLS")


def create_source_zip(
    delivery: Path,
    source: str,
    archive_dir: Path,
) -> tuple[Path, int]:
    root = delivery / SOURCE_ROOTS[source]
    output = archive_dir / f"CDA_V2_{source}.zip"
    count = 0
    compression = zipfile.ZIP_STORED if source == "StatsBomb" else zipfile.ZIP_DEFLATED
    compresslevel = None if compression == zipfile.ZIP_STORED else 6
    with zipfile.ZipFile(
        output,
        "w",
        compression=compression,
        compresslevel=compresslevel,
        allowZip64=True,
    ) as archive:
        for path in source_files(root):
            arcname = f"{source}/{path.relative_to(root).as_posix()}"
            archive.write(path, arcname)
            count += 1
    return output, count


def create_metadata_zip(delivery: Path, archive_dir: Path) -> tuple[Path, int]:
    archive_dir.mkdir(parents=True, exist_ok=True)
    output = archive_dir / "CDA_V2_Metadata_and_Tools.zip"
    roots = [
        delivery / "00_SOURCE_REGISTRY",
        delivery / "02_MATCH_INVENTORY",
        delivery / "03_SCHEMA_DOCUMENTATION",
        delivery / "04_QUALITY_ASSESSMENT",
        delivery / "05_ACCESS_TOOLS",
        delivery / "06_HANDOFF",
    ]
    root_files = [
        delivery / "README.md",
        delivery / "06_工程师交付回执.md",
        delivery / "archives" / "ZIP_INDEX.csv",
        delivery / "archives" / "ARCHIVE_LOCATION.md",
    ]
    count = 0
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
        allowZip64=True,
    ) as archive:
        for path in root_files:
            if path.exists():
                archive.write(path, path.relative_to(delivery).as_posix())
                count += 1
        for root in roots:
            for path in sorted(
                item
                for item in root.rglob("*")
                if item.is_file() and not is_cache_path(item.relative_to(delivery))
            ):
                archive.write(path, path.relative_to(delivery).as_posix())
                count += 1
    return output, count


def write_manifest(delivery: Path) -> int:
    output = delivery / "MANIFEST.sha256"
    entries: list[tuple[str, str]] = []
    for path in sorted(
        item
        for item in delivery.rglob("*")
        if item.is_file()
        and item != output
        and not EXCLUDED_PARTS.intersection(item.relative_to(delivery).parts)
        and not is_cache_path(item.relative_to(delivery))
    ):
        entries.append((sha256_file(path), path.relative_to(delivery).as_posix()))
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for digest, relative in entries:
            handle.write(f"{digest}  {relative}\n")
    return len(entries)


def write_archive_location(delivery: Path) -> None:
    (delivery / "archives" / "ARCHIVE_LOCATION.md").write_text(
        """# External ZIP Location

The `.zip` files are stored outside the Git repository to preserve the
repository safety test that forbids ZIP assets in the checkout.

```text
Index: archives/ZIP_INDEX.csv
Archive files are resolved relative to the supplied `--archive-root`.
```
""",
        encoding="utf-8",
    )


def index_rows_for_existing(archive_dir: Path) -> list[dict[str, object]]:
    expected = {
        "CDA_V2_SkillCorner.zip": ("SkillCorner", 139),
        "CDA_V2_IDSSE.zip": ("IDSSE", 23),
        "CDA_V2_StatsBomb.zip": ("StatsBomb", 8988),
        "CDA_V2_Wyscout.zip": ("Wyscout", 3892),
    }
    rows = []
    for name, (scope, count) in expected.items():
        path = archive_dir / name
        if not path.exists():
            raise FileNotFoundError(path)
        rows.append(
            {
                "archive": name,
                "scope": scope,
                "contents": count,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("delivery_root", type=Path)
    parser.add_argument("--tools-source", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()
    delivery = args.delivery_root.resolve()
    archive_dir = args.archive_root.resolve()
    archive_dir.mkdir(parents=True, exist_ok=True)
    copy_tools(delivery, args.tools_source.resolve())
    remove_cache_artifacts(delivery)

    if args.metadata_only:
        index_rows = index_rows_for_existing(archive_dir)
    else:
        index_rows = []
        for source in SOURCE_ROOTS:
            archive, count = create_source_zip(delivery, source, archive_dir)
            index_rows.append(
                {
                    "archive": archive.name,
                    "scope": source,
                    "contents": count,
                    "bytes": archive.stat().st_size,
                    "sha256": sha256_file(archive),
                }
            )
    metadata_archive, metadata_count = create_metadata_zip(delivery, archive_dir)
    index_rows.append(
        {
            "archive": metadata_archive.name,
            "scope": "metadata_and_tools",
            "contents": metadata_count,
            "bytes": metadata_archive.stat().st_size,
            "sha256": sha256_file(metadata_archive),
        }
    )
    with (delivery / "archives" / "ZIP_INDEX.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "archive",
                "scope",
                "contents",
                "bytes",
                "sha256",
            ],
        )
        writer.writeheader()
        writer.writerows(index_rows)
    write_archive_location(delivery)
    manifest_count = write_manifest(delivery)
    print(
        json.dumps(
            {
                "manifest_entries": manifest_count,
                "archives": index_rows,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
