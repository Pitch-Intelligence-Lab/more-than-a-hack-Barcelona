#!/usr/bin/env python3
"""Bounded Stage-1 audit for SoccerTrack match 128057."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

import ijson
import numpy as np


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sequence_stats(values: np.ndarray) -> dict[str, Any]:
    unique, counts = np.unique(values, return_counts=True)
    sorted_values = np.sort(unique)
    gaps = np.diff(sorted_values) - 1 if len(sorted_values) > 1 else np.asarray([], dtype=int)
    return {
        "count": int(len(values)),
        "unique": int(len(unique)),
        "duplicates": int(np.count_nonzero(counts > 1)),
        "min": int(sorted_values[0]) if len(sorted_values) else None,
        "max": int(sorted_values[-1]) if len(sorted_values) else None,
        "gaps": int(np.count_nonzero(gaps)),
        "missing_values": int(gaps.sum()),
        "max_gap": int(gaps.max()) if len(gaps) else 0,
    }


def _range_stats(values: list[float]) -> dict[str, Any]:
    finite = [value for value in values if math.isfinite(value)]
    return {
        "count": len(values),
        "invalid": len(values) - len(finite),
        "min": min(finite) if finite else None,
        "max": max(finite) if finite else None,
    }


def audit_gsr(path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    with path.open("rb") as handle:
        info = next(ijson.items(handle, "info", use_float=True))
    image_ids: set[str] = set()
    file_frames: list[int] = []
    image_heights: Counter[int] = Counter()
    image_widths: Counter[int] = Counter()
    with path.open("rb") as handle:
        for image in ijson.items(handle, "images.item", use_float=True):
            image_ids.add(str(image.get("image_id")))
            file_name = str(image.get("file_name", ""))
            if file_name.endswith(".jpg") and file_name[:-4].isdigit():
                file_frames.append(int(file_name[:-4]))
            image_heights[int(image.get("height", 0))] += 1
            image_widths[int(image.get("width", 0))] += 1
    annotation_count = 0
    categories: Counter[str] = Counter()
    supercategories: Counter[str] = Counter()
    track_ids: set[int] = set()
    player_ids: set[str] = set()
    roles: Counter[str] = Counter()
    teams: Counter[str] = Counter()
    jerseys: Counter[str] = Counter()
    missing_image_links = 0
    pitch_x: list[float] = []
    pitch_y: list[float] = []
    image_with_object: set[str] = set()
    with path.open("rb") as handle:
        for annotation in ijson.items(handle, "annotations.item", use_float=True):
            annotation_count += 1
            image_id = str(annotation.get("image_id"))
            if image_id not in image_ids:
                missing_image_links += 1
            supercategory = str(annotation.get("supercategory", ""))
            supercategories[supercategory] += 1
            if supercategory != "object":
                continue
            image_with_object.add(image_id)
            attributes = annotation.get("attributes") or {}
            categories[str(annotation.get("category_id"))] += 1
            if attributes.get("role") is not None:
                roles[str(attributes["role"])] += 1
            if attributes.get("team") is not None:
                teams[str(attributes["team"])] += 1
            if attributes.get("jersey") is not None:
                jerseys[str(attributes["jersey"])] += 1
            if attributes.get("player_id") is not None:
                player_ids.add(str(attributes["player_id"]))
            if annotation.get("track_id") is not None:
                track_ids.add(int(annotation["track_id"]))
            bbox = annotation.get("bbox_pitch") or {}
            for key, values in (("x_bottom_middle", pitch_x), ("y_bottom_middle", pitch_y)):
                if key in bbox:
                    try:
                        values.append(float(bbox[key]))
                    except (TypeError, ValueError):
                        values.append(float("nan"))
    frame_stats = _sequence_stats(np.asarray(file_frames, dtype=np.int64))
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "info": info,
        "images": {
            "count": len(image_ids),
            "frames": frame_stats,
            "heights": dict(image_heights),
            "widths": dict(image_widths),
        },
        "annotations": {
            "count": annotation_count,
            "supercategories": dict(supercategories),
            "object_categories": dict(categories),
            "object_track_ids": len(track_ids),
            "object_player_ids": len(player_ids),
            "roles": dict(roles),
            "teams": dict(teams),
            "jerseys_present": len(jerseys),
            "images_with_object": len(image_with_object),
            "missing_image_links": missing_image_links,
            "pitch_x": _range_stats(pitch_x),
            "pitch_y": _range_stats(pitch_y),
        },
    }


def audit_ball(path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    with np.load(path, allow_pickle=False) as archive:
        members = {
            name: {"shape": list(archive[name].shape), "dtype": str(archive[name].dtype)}
            for name in archive.files
        }
        frames = np.asarray(archive["frame"])
        status = np.asarray(archive["status"])
        x = np.asarray(archive["x"], dtype=np.float64)
        y = np.asarray(archive["y"], dtype=np.float64)
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "members": members,
        "frames": _sequence_stats(frames.astype(np.int64)),
        "status_counts": {
            str(key): int(value)
            for key, value in zip(*np.unique(status, return_counts=True), strict=False)
        },
        "x": _range_stats(x.tolist()),
        "y": _range_stats(y.tolist()),
        "status_zero": int(np.count_nonzero(status == 0)),
    }


def audit_json_events(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    actions = data.get("actions", []) if isinstance(data, dict) else []
    labels = Counter(str(action.get("label")) for action in actions)
    teams = Counter(str(action.get("team")) for action in actions)
    frames = [int(action["frame"]) for action in actions if "frame" in action]
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "top_level_keys": sorted(data) if isinstance(data, dict) else None,
        "event_count": len(actions),
        "labels": dict(labels),
        "teams": dict(teams),
        "frame_range": [min(frames), max(frames)] if frames else None,
        "missing_player_id": sum(not action.get("player_id") for action in actions),
    }


def audit_support(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    result: dict[str, Any] = {"path": str(path), "bytes": path.stat().st_size}
    if suffix == ".npz":
        with np.load(path, allow_pickle=False) as archive:
            result["arrays"] = {
                name: {"shape": list(archive[name].shape), "dtype": str(archive[name].dtype)}
                for name in archive.files
            }
    elif suffix == ".npy":
        array = np.load(path, allow_pickle=False)
        result["array"] = {
            "shape": list(array.shape),
            "dtype": str(array.dtype),
            "finite": int(np.isfinite(array).sum()),
            "nonfinite": int((~np.isfinite(array)).sum()),
        }
    elif suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            result["header"] = next(reader, [])
            result["sample_rows"] = [row for _, row in zip(range(3), reader, strict=False)]
    elif suffix == ".xml":
        tag_counts: Counter[str] = Counter()
        root = None
        for event, element in ET.iterparse(path, events=("start", "end")):
            if root is None:
                root = element
            if event == "start":
                tag_counts[element.tag.rsplit("}", 1)[-1]] += 1
            element.clear()
        result["root"] = root.tag.rsplit("}", 1)[-1] if root is not None else None
        result["tag_counts"] = dict(tag_counts.most_common(20))
    elif suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        result["type"] = type(data).__name__
        result["keys"] = sorted(data)[:50] if isinstance(data, dict) else None
    return result


def audit_mot(path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    rows = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip():
                rows.append(line.strip().split(","))
            if len(rows) >= 100000:
                break
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "sampled_or_full_rows": len(rows),
        "field_counts": dict(Counter(len(row) for row in rows)),
        "sample": rows[:3],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    outputs = {
        "gsr": [
            audit_gsr(root / "gsr/128057/128057_1st.json"),
            audit_gsr(root / "gsr/128057/128057_2nd.json"),
        ],
        "ball": [
            audit_ball(root / "ball/128057_1st_ball.npz"),
            audit_ball(root / "ball/128057_2nd_ball.npz"),
        ],
        "events": audit_json_events(root / "bas/128057/128057_12_class_events.json"),
        "mot": audit_mot(root / "mot/128057.txt"),
        "support": [
            audit_support(path)
            for path in sorted((root / "raw/128057").iterdir())
            if path.is_file()
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(outputs, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(outputs, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
