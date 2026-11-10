#!/usr/bin/env python3
"""Build Git/HF-independent source tree identities for portable verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def git_tree(repository: Path, *, lfs: bool) -> list[dict[str, Any]]:
    output = subprocess.run(
        ["git", "-C", str(repository), "ls-tree", "-r", "--long", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    records = []
    for line in output.splitlines():
        metadata, path = line.split("\t", 1)
        _mode, _kind, object_id, size = metadata.split()
        record: dict[str, Any] = {
            "path": path,
            "size": int(size),
            "git_blob_sha1": object_id,
        }
        file_path = repository / path
        if lfs and file_path.exists():
            head = file_path.open("rb").read(256)
            if head.startswith(b"version https://git-lfs.github.com/spec/v1"):
                text = head.decode("ascii", errors="ignore")
                oid = re.search(r"oid sha256:([0-9a-f]{64})", text)
                pointer_size = re.search(r"size (\d+)", text)
                if oid is None or pointer_size is None:
                    raise ValueError(f"invalid LFS pointer: {file_path}")
                record["size"] = file_path.stat().st_size
                record["pointer_size"] = int(pointer_size.group(1))
                record["lfs_sha256"] = oid.group(1)
        records.append(record)
    return sorted(records, key=lambda item: item["path"])


def hf_tree(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for item in raw:
        if item["type"] != "file":
            continue
        record = {
            "path": item["path"],
            "size": item["size"],
        }
        if item.get("lfs"):
            record["lfs_sha256"] = item["lfs"]["oid"]
            record["pointer_size"] = item["lfs"]["pointerSize"]
        else:
            record["git_blob_sha1"] = item["oid"]
        records.append(record)
    return records


def github_tree(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return sorted(
        (
            {
                "path": item["path"],
                "size": item["size"],
                "git_blob_sha1": item["sha"],
            }
            for item in raw["tree"]
            if item["type"] == "blob"
        ),
        key=lambda item: item["path"],
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def attach_working_hashes(records: list[dict[str, Any]], root: Path) -> None:
    def update(record: dict[str, Any]) -> None:
        path = root / record["path"]
        if path.exists():
            record["size"] = path.stat().st_size
            record["sha256"] = sha256_file(path)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(update, records))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_root", type=Path)
    args = parser.parse_args()
    root = args.package_root.resolve()
    raw = root / "01_RAW_DATA"
    output = root / "00_SOURCE_REGISTRY" / "PORTABLE_TREES"
    source_registry = {
        "SkillCorner": {
            "source_url": "https://github.com/SkillCorner/opendata",
            "ref": "refs/heads/master",
            "commit": "4340d274572876239c154c90bc507a9b3250a656",
            "tree": git_tree(raw / "skillcorner" / "repository", lfs=True),
        },
        "IDSSE": {
            "source_url": "https://huggingface.co/datasets/pysport/idsse-data",
            "ref": "main",
            "commit": "a715a38dfbaf5f58e431727c2b78d174101a703c",
            "tree": hf_tree(raw / "idsse" / "HF_TREE.json"),
        },
        "StatsBomb": {
            "source_url": "https://github.com/hudl/open-data",
            "ref": "refs/heads/master",
            "commit": "4b73468fc5b0f1950f9f66fada70ad3a4f9327cb",
            "tree": github_tree(raw / "statsbomb" / "GITHUB_TREE_RAW.json"),
        },
        "Wyscout": {
            "source_url": "https://github.com/koenvo/wyscout-soccer-match-event-dataset",
            "ref": "refs/heads/main",
            "commit": "ebc4c54c1093c420a81ce442c69e4186fab33bb4",
            "tree": git_tree(raw / "wyscout" / "repository", lfs=False),
        },
    }
    summaries = {}
    for source, values in source_registry.items():
        attach_working_hashes(
            values["tree"],
            raw / SOURCE_KEYS[source] / "repository",
        )
        payload = {
            "schema_version": "1.0",
            "source": source,
            **values,
        }
        write_json(output / f"{source.lower()}.json", payload)
        summaries[source] = {
            "source_url": values["source_url"],
            "ref": values["ref"],
            "commit": values["commit"],
            "files": len(values["tree"]),
            "portable_tree": f"00_SOURCE_REGISTRY/PORTABLE_TREES/{source.lower()}.json",
        }
    write_json(root / "00_SOURCE_REGISTRY" / "PORTABLE_SOURCE_IDENTITIES.json", summaries)
    print(json.dumps(summaries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
