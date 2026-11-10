#!/usr/bin/env python3
"""Reassemble a portable CDA-v2 package from verified external ZIP archives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

SOURCE_SCOPES = {
    "SkillCorner": "skillcorner",
    "IDSSE": "idsse",
    "StatsBomb": "statsbomb",
    "Wyscout": "wyscout",
}


class ReassemblyError(ValueError):
    """Raised when archives cannot be safely and completely reassembled."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_member_path(member: str) -> PurePosixPath:
    posix = PurePosixPath(member)
    windows = PureWindowsPath(member)
    if (
        not member
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or ".." in posix.parts
        or ".." in windows.parts
        or "\\" in member
    ):
        raise ReassemblyError(f"unsafe ZIP member path: {member!r}")
    return posix


def read_index(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise ReassemblyError(f"ZIP index does not exist: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"archive", "scope", "contents", "bytes", "sha256"}
    if not rows or set(rows[0]) != required:
        raise ReassemblyError("ZIP index has missing or unknown columns")
    for row in rows:
        safe_member_path(row["archive"])
        if "/" in row["archive"] or "\\" in row["archive"]:
            raise ReassemblyError("ZIP index archive names must be relative file names")
        if len(row["sha256"]) != 64 or any(
            character not in "0123456789abcdef" for character in row["sha256"]
        ):
            raise ReassemblyError(f"invalid archive SHA-256: {row['archive']}")
    scopes = {row["scope"] for row in rows}
    expected = {*SOURCE_SCOPES, "metadata_and_tools"}
    if scopes != expected or len(rows) != 5:
        raise ReassemblyError("ZIP index must describe exactly the five expected archives")
    return rows


def verify_archives(archive_root: Path, rows: list[dict[str, str]]) -> None:
    for row in rows:
        path = archive_root / row["archive"]
        if not path.is_file():
            raise ReassemblyError(f"archive is missing: {path}")
        if path.stat().st_size != int(row["bytes"]):
            raise ReassemblyError(f"archive size mismatch: {path}")
        if sha256_file(path) != row["sha256"]:
            raise ReassemblyError(f"archive SHA-256 mismatch: {path}")
        try:
            with zipfile.ZipFile(path) as archive:
                if archive.testzip() is not None:
                    raise ReassemblyError(f"archive CRC failure: {path}")
                for member in archive.infolist():
                    safe_member_path(member.filename)
                    mode = member.external_attr >> 16
                    if mode and (mode & 0o170000) == 0o120000:
                        raise ReassemblyError(
                            f"symbolic links are forbidden in ZIP: {member.filename}"
                        )
        except zipfile.BadZipFile as error:
            raise ReassemblyError(f"invalid ZIP archive: {path}") from error


def prepare_empty_output(output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise ReassemblyError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)


def extraction_destination(
    output: Path,
    scope: str,
    member: str,
) -> tuple[Path, str]:
    relative = safe_member_path(member)
    if scope == "metadata_and_tools":
        return output.joinpath(*relative.parts), relative.as_posix()
    prefix = scope
    if not relative.parts or relative.parts[0] != prefix:
        raise ReassemblyError(f"{scope} archive member lacks source prefix: {member}")
    stripped = PurePosixPath(*relative.parts[1:])
    destination = (
        output / "01_RAW_DATA" / SOURCE_SCOPES[scope] / "repository" / Path(*stripped.parts)
    )
    return destination, stripped.as_posix()


def extract_archive(
    archive_path: Path,
    output: Path,
    scope: str,
) -> int:
    count = 0
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            destination, _relative = extraction_destination(output, scope, member.filename)
            resolved = destination.resolve()
            if not resolved.is_relative_to(output.resolve()):
                raise ReassemblyError(f"archive member escapes output: {member.filename}")
            resolved.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, resolved.open("wb") as target:
                while chunk := source.read(4 * 1024 * 1024):
                    target.write(chunk)
            count += 1
    return count


def remove_cache_artifacts(root: Path) -> int:
    removed = 0
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir() and path.name == "__pycache__":
            for child in sorted(path.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                    removed += 1
            for child in sorted(
                (item for item in path.rglob("*") if item.is_dir()),
                key=lambda item: len(item.parts),
                reverse=True,
            ):
                child.rmdir()
            path.rmdir()
        elif path.is_file() and path.suffix.lower() in {".pyc", ".pyo"}:
            path.unlink()
            removed += 1
    return removed


def reassemble(
    *,
    archive_root: Path,
    output: Path,
    index_path: Path | None = None,
) -> dict[str, Any]:
    archive_root = archive_root.resolve()
    output = output.resolve()
    rows = read_index(index_path or archive_root / "ZIP_INDEX.csv")
    verify_archives(archive_root, rows)
    prepare_empty_output(output)
    ordered = sorted(rows, key=lambda row: row["scope"] == "metadata_and_tools")
    extracted = {
        row["scope"]: extract_archive(archive_root / row["archive"], output, row["scope"])
        for row in ordered
    }
    cache_removed = remove_cache_artifacts(output)
    return {
        "archive_root": str(archive_root),
        "output": str(output),
        "five_archives_verified": True,
        "extracted_members": extracted,
        "cache_removed": cache_removed,
        "status": "PASS",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--index", type=Path)
    args = parser.parse_args(argv)
    try:
        result = reassemble(
            archive_root=args.archive_root,
            output=args.output,
            index_path=args.index,
        )
    except (OSError, zipfile.BadZipFile, ReassemblyError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
