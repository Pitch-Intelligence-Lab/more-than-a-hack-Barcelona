#!/usr/bin/env python3
"""Record independent-validation source access and pinned-tree preflight."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DATASET_ID = "atomscott/soccertrack-v2"
REVISION = "v1.2"
RESOLVED_SHA = "325bd4c57ee8e135ab652f3921d274526ada496b"
DATASET_API = f"https://huggingface.co/api/datasets/{DATASET_ID}"
TREE_URL = f"{DATASET_API}/tree/{REVISION}?recursive=true&expand=true"
README_URL = f"https://huggingface.co/datasets/{DATASET_ID}/resolve/{REVISION}/README.md"
GATED_FILE = "ball/128057_1st_ball.npz"
GATED_FILE_URL = f"https://huggingface.co/datasets/{DATASET_ID}/resolve/{REVISION}/{GATED_FILE}"
EXPECTED_TREE_ENTRIES = 244
EXPECTED_TREE_BYTES = 144_847_069_949


def _request(url: str, *, method: str = "GET") -> tuple[int, bytes, str]:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    headers = {"Accept": "application/json", "User-Agent": "MTAH-independent-validation-audit"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(url, headers=headers, method=method), timeout=30) as response:
            return response.status, response.read(), response.headers.get("Link", "")
    except HTTPError as error:
        return error.code, b"", error.headers.get("Link", "")
    except URLError:
        return 0, b"", ""


def _next_link(link_header: str) -> str | None:
    match = re.search(r"<([^>]+)>;\s*rel=\"next\"", link_header)
    return match.group(1) if match else None


def fetch_remote_tree() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    url: str | None = TREE_URL
    while url:
        status, body, link = _request(url)
        if status != 200:
            raise RuntimeError(f"Hugging Face tree request returned HTTP {status}")
        page = json.loads(body)
        if not isinstance(page, list):
            raise RuntimeError("Hugging Face tree response is not a list")
        entries.extend(page)
        url = _next_link(link)
    return entries


def summarize_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    files = [entry for entry in entries if entry.get("type") != "directory"]
    folder_totals: Counter[str] = Counter()
    for entry in files:
        folder = str(entry.get("path", "")).split("/", 1)[0]
        folder_totals[folder] += int(entry.get("size", 0))
    return {
        "tree_entries": len(entries),
        "file_entries": len(files),
        "tree_bytes": sum(int(entry.get("size", 0)) for entry in files),
        "folder_bytes": dict(sorted(folder_totals.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    status, dataset_body, _ = _request(DATASET_API)
    if status != 200:
        raise RuntimeError(f"Hugging Face dataset metadata returned HTTP {status}")
    dataset = json.loads(dataset_body)
    entries = fetch_remote_tree()
    summary = summarize_entries(entries)
    token_present = bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN"))
    gated_status, _, _ = _request(GATED_FILE_URL, method="HEAD")
    readme_status, _, _ = _request(README_URL, method="HEAD")
    baseline_match = (
        summary["tree_entries"] == EXPECTED_TREE_ENTRIES
        and summary["tree_bytes"] == EXPECTED_TREE_BYTES
        and dataset.get("sha") == RESOLVED_SHA
    )
    acquisition_status = (
        "PREFLIGHT_PASSED"
        if token_present and gated_status == 200 and baseline_match
        else "BLOCKED"
    )
    evidence = {
        "checked_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "dataset_id": DATASET_ID,
        "revision": REVISION,
        "dataset_reported_sha": dataset.get("sha"),
        "expected_resolved_sha": RESOLVED_SHA,
        "gated": dataset.get("gated"),
        "private": dataset.get("private"),
        "used_storage": dataset.get("usedStorage"),
        "hf_token_present": token_present,
        "gated_file": GATED_FILE,
        "gated_file_http_status": gated_status,
        "readme_http_status": readme_status,
        "expected_tree_entries": EXPECTED_TREE_ENTRIES,
        "expected_tree_bytes": EXPECTED_TREE_BYTES,
        **summary,
        "baseline_match": baseline_match,
        "acquisition_status": acquisition_status,
        "mirror_used": False,
    }
    manifest = output_dir / "REMOTE_FILE_MANIFEST.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("path", "type", "size", "oid"),
            lineterminator="\n",
        )
        writer.writeheader()
        for entry in sorted(entries, key=lambda item: str(item.get("path", ""))):
            writer.writerow(
                {
                    "path": entry.get("path", ""),
                    "type": entry.get("type", ""),
                    "size": int(entry.get("size", 0)),
                    "oid": entry.get("oid", ""),
                }
            )
    (output_dir / "PREFLIGHT_EVIDENCE.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if baseline_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
