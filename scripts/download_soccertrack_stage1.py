#!/usr/bin/env python3
"""Download only the authorized SoccerTrack 128057 Stage 1 files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DATASET = "atomscott/soccertrack-v2"
REVISION = "v1.2"
RESOLVE_ROOT = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/"
STAGE = "1_NON_VIDEO"
EXPECTED_FILES = 20
EXPECTED_BYTES = 5_768_542_573
CHUNK_SIZE = 4 * 1024 * 1024
LOCAL_COLUMNS = (
    "path",
    "type",
    "expected_size",
    "oid",
    "stage",
    "local_path",
    "local_bytes",
    "sha256",
    "status",
)


class DownloadError(RuntimeError):
    """Raised when a Stage 1 download or manifest check fails."""


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    stage_rows = [row for row in rows if row["stage"] == STAGE]
    if len(stage_rows) != EXPECTED_FILES:
        raise DownloadError(
            f"Stage 1 manifest must contain {EXPECTED_FILES} files; found {len(stage_rows)}"
        )
    if sum(int(row["expected_size"]) for row in stage_rows) != EXPECTED_BYTES:
        raise DownloadError("Stage 1 manifest byte total differs from authorized total")
    if any(row["path"].startswith(("videos/", "mot/clips/")) for row in stage_rows):
        raise DownloadError("Stage 1 manifest contains a forbidden video path")
    return rows


def _destination(row: dict[str, str], *, annotations_root: Path, metadata_root: Path) -> Path:
    path = row["path"]
    if path in {"README.md"} or path.startswith("CHANGES_"):
        return metadata_root / path
    return annotations_root / path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(row: dict[str, str], destination: Path, token: str) -> tuple[int, str]:
    expected = int(row["expected_size"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f"{destination.name}.part")
    max_attempts = 8
    for attempt in range(1, max_attempts + 1):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > expected:
            raise DownloadError(f"{row['path']}: partial file is larger than expected")
        if offset == expected:
            break
        headers = {
            "Accept": "application/octet-stream",
            "User-Agent": "MTAH-STAGE1-AUDIT",
            "Authorization": f"Bearer {token}",
        }
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = Request(RESOLVE_ROOT + row["path"], headers=headers)
        try:
            with urlopen(request, timeout=120) as response:
                status = response.status
                if offset and status == 206:
                    mode = "ab"
                elif status == 200:
                    mode = "wb"
                else:
                    raise DownloadError(f"unexpected HTTP status {status}")
                with partial.open(mode) as handle:
                    for chunk in iter(lambda: response.read(CHUNK_SIZE), b""):
                        handle.write(chunk)
        except HTTPError as error:
            if error.code == 416 and partial.exists() and partial.stat().st_size == expected:
                break
            if attempt == max_attempts:
                raise DownloadError(f"{row['path']}: HTTP {error.code}") from error
        except (TimeoutError, URLError, OSError) as error:
            if attempt == max_attempts:
                raise DownloadError(f"{row['path']}: network failure") from error
            time.sleep(min(2 * attempt, 10))
    actual = partial.stat().st_size
    if actual != expected:
        raise DownloadError(f"{row['path']}: local bytes {actual} != expected bytes {expected}")
    os.replace(partial, destination)
    return actual, _sha256(destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--annotations-root", type=Path, required=True)
    parser.add_argument("--metadata-root", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        raise DownloadError("HF_TOKEN is not present in the execution environment")
    rows = _read_rows(args.manifest)
    started = time.perf_counter()
    completed_bytes = 0
    for index, row in enumerate(
        (item for item in rows if item["stage"] == STAGE),
        start=1,
    ):
        destination = _destination(
            row,
            annotations_root=args.annotations_root,
            metadata_root=args.metadata_root,
        )
        row["local_path"] = str(destination)
        row["local_bytes"] = ""
        row["sha256"] = ""
        if destination.is_file() and destination.stat().st_size == int(row["expected_size"]):
            actual = destination.stat().st_size
            digest = _sha256(destination)
            row["status"] = "REUSED"
        else:
            row["status"] = "DOWNLOADING"
            actual, digest = _download(row, destination, token)
            row["status"] = "DOWNLOADED"
        completed_bytes += actual
        row["local_bytes"] = str(actual)
        row["sha256"] = digest
        print(
            f"[{index}/{EXPECTED_FILES}] {row['path']} {actual} bytes sha256={digest}",
            flush=True,
        )
    if completed_bytes != EXPECTED_BYTES:
        raise DownloadError(f"completed bytes {completed_bytes} != authorized {EXPECTED_BYTES}")
    with args.manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=LOCAL_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"stage1 complete: files={EXPECTED_FILES} bytes={completed_bytes} "
        f"elapsed_seconds={time.perf_counter() - started:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
