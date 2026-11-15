"""Deterministic causal short-window G2 feature derivation."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import os
import platform
import shutil
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from mtah_possession.research.phase2.constants import (
    FEATURE_COLUMNS,
    OUTPUT_SCHEMA_VERSION,
)
from mtah_possession.research.phase2.extractor import collect_source_identity

TASK_ID = "MTAH-PHASE3-G2-EXTRACTOR-001"
G2_SCHEMA_VERSION = "P2-G2-0.1"
LAGS = (5, 25)
DYNAMIC_FEATURES = (
    "nearest_home_m",
    "nearest_away_m",
    "nearest_team_delta_m",
    "second_home_m",
    "second_away_m",
    "players_within_2m_home",
    "players_within_2m_away",
    "players_within_5m_home",
    "players_within_5m_away",
    "centroid_distance_m",
    "home_width_m",
    "away_width_m",
    "home_depth_m",
    "away_depth_m",
    "ball_home_centroid_delta_m",
)
G2_COLUMNS = (
    "match_id",
    "frame_number",
    "game_section",
    *(f"delta{lag}__{feature}" for lag in LAGS for feature in DYNAMIC_FEATURES),
)


class G2Error(RuntimeError):
    """Raised when G2 input identity or schema invariants fail."""


@dataclass(frozen=True)
class FeatureTable:
    match_id: str
    frame_numbers: np.ndarray
    game_sections: list[str]
    values: np.ndarray
    run_ranges: list[tuple[int, int]]
    section_boundary_count: int
    frame_gap_count: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def _open_gzip_text(path: Path):
    with (
        gzip.open(path, mode="rb") as raw,
        io.TextIOWrapper(raw, encoding="utf-8", newline="") as text,
    ):
        yield text


def _window_columns() -> dict[str, int]:
    return {name: index for index, name in enumerate(FEATURE_COLUMNS)}


def _read_header(path: Path) -> list[str]:
    with _open_gzip_text(path) as text:
        reader = csv.reader(text)
        try:
            return next(reader)
        except StopIteration as error:
            raise G2Error(f"features file is empty: {path}") from error


def _count_rows(path: Path) -> int:
    count = 0
    with _open_gzip_text(path) as text:
        reader = csv.reader(text)
        next(reader)
        for _row in reader:
            count += 1
    return count


def _parse_number(value: str | None) -> float:
    if value is None or value == "":
        return math.nan
    try:
        parsed = float(value)
    except ValueError as error:
        raise G2Error(f"non-numeric G2 base feature value: {value!r}") from error
    if not math.isfinite(parsed):
        raise G2Error(f"non-finite G2 base feature value: {value!r}")
    return parsed


def load_feature_table(features_path: Path) -> FeatureTable:
    header = _read_header(features_path)
    if tuple(header) != FEATURE_COLUMNS:
        raise G2Error(
            "input feature schema mismatch: "
            f"expected {len(FEATURE_COLUMNS)} P2-FS-0.1 columns, found {len(header)}"
        )
    row_count = _count_rows(features_path)
    positions = _window_columns()
    values = np.full((row_count, len(DYNAMIC_FEATURES)), np.nan, dtype=np.float64)
    frame_numbers = np.empty(row_count, dtype=np.int64)
    game_sections: list[str] = []
    match_id: str | None = None
    with _open_gzip_text(features_path) as text:
        reader = csv.DictReader(text)
        for expected_index, row in enumerate(reader):
            if expected_index >= row_count:
                raise G2Error("features row count changed between validation scans")
            current_match = row["match_id"]
            if match_id is None:
                match_id = current_match
            elif current_match != match_id:
                raise G2Error("G2 input contains more than one match_id")
            try:
                frame_numbers[expected_index] = int(row["frame_number"])
            except (TypeError, ValueError) as error:
                raise G2Error(f"invalid frame_number at input row {expected_index + 2}") from error
            section = row["game_section"]
            if section not in {"firstHalf", "secondHalf"}:
                raise G2Error(f"unexpected game_section: {section!r}")
            game_sections.append(section)
            for feature_index, feature in enumerate(DYNAMIC_FEATURES):
                values[expected_index, feature_index] = _parse_number(
                    row[FEATURE_COLUMNS[positions[feature]]]
                )
    if match_id is None:
        raise G2Error(f"features file has no data rows: {features_path}")
    run_starts = [0]
    section_boundary_count = 0
    frame_gap_count = 0
    for index in range(1, row_count):
        section_changed = game_sections[index] != game_sections[index - 1]
        frame_gap = int(frame_numbers[index]) != int(frame_numbers[index - 1]) + 1
        section_boundary_count += section_changed
        frame_gap_count += frame_gap and not section_changed
        if section_changed or frame_gap:
            run_starts.append(index)
    run_starts.append(row_count)
    run_ranges = list(zip(run_starts[:-1], run_starts[1:], strict=True))
    return FeatureTable(
        match_id=match_id,
        frame_numbers=frame_numbers,
        game_sections=game_sections,
        values=values,
        run_ranges=run_ranges,
        section_boundary_count=section_boundary_count,
        frame_gap_count=frame_gap_count,
    )


def derive_columns(table: FeatureTable) -> tuple[np.ndarray, list[str]]:
    columns = []
    names = []
    for lag in LAGS:
        for feature_index, feature in enumerate(DYNAMIC_FEATURES):
            result = np.full(len(table.frame_numbers), np.nan, dtype=np.float64)
            for start, stop in table.run_ranges:
                if stop - start <= lag:
                    continue
                current = table.values[start + lag : stop, feature_index]
                historical = table.values[start : stop - lag, feature_index]
                result[start + lag : stop] = current - historical
            columns.append(result)
            names.append(f"delta{lag}__{feature}")
    return np.column_stack(columns), names


def _format_number(value: float) -> str:
    if not math.isfinite(value):
        return ""
    rendered = f"{value:.6f}"
    return "0.000000" if rendered == "-0.000000" else rendered


def _open_output_gzip(path: Path):
    raw = path.open("wb")
    compressed = gzip.GzipFile(fileobj=raw, filename="", mode="wb", compresslevel=9, mtime=0)
    text = io.TextIOWrapper(compressed, encoding="utf-8", newline="")
    return raw, compressed, text


def write_g2_features(path: Path, table: FeatureTable) -> dict[str, Any]:
    derived, names = derive_columns(table)
    if tuple(names) != G2_COLUMNS[3:]:
        raise AssertionError("G2 derived column order mismatch")
    missing_counts = {name: 0 for name in names}
    first_25_missing = {name: 0 for name in names}
    raw, compressed, text = _open_output_gzip(path)
    try:
        writer = csv.writer(text, lineterminator="\n")
        writer.writerow(G2_COLUMNS)
        for index, frame_number in enumerate(table.frame_numbers.tolist()):
            rendered = []
            for column_index, name in enumerate(names):
                value = float(derived[index, column_index])
                if not math.isfinite(value):
                    missing_counts[name] += 1
                    if index < 25:
                        first_25_missing[name] += 1
                rendered.append(_format_number(value))
            writer.writerow(
                (
                    table.match_id,
                    frame_number,
                    table.game_sections[index],
                    *rendered,
                )
            )
        text.flush()
    finally:
        text.close()
        if not compressed.closed:
            compressed.close()
        raw.close()
    return {
        "rows": len(table.frame_numbers),
        "run_ranges": [
            {"start_row": start, "stop_row_exclusive": stop} for start, stop in table.run_ranges
        ],
        "run_count": len(table.run_ranges),
        "section_boundary_count": table.section_boundary_count,
        "frame_gap_count": table.frame_gap_count,
        "missing_counts": missing_counts,
        "first_25_missing_counts": first_25_missing,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _publish_staging(staging: Path, output_dir: Path, *, overwrite: bool) -> None:
    if output_dir.exists() and not overwrite:
        raise G2Error(f"output directory already exists: {output_dir}")
    if not output_dir.exists():
        os.replace(staging, output_dir)
        return
    backup = output_dir.with_name(f".{output_dir.name}.backup-{os.getpid()}")
    if backup.exists():
        raise G2Error(f"stale output backup exists: {backup}")
    os.replace(output_dir, backup)
    try:
        os.replace(staging, output_dir)
    except Exception:
        os.replace(backup, output_dir)
        raise
    shutil.rmtree(backup)


def _validate_input_metadata(
    metadata_path: Path,
    *,
    features_path: Path,
    features_sha256: str,
) -> dict[str, Any]:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G2Error(f"cannot read input metadata: {metadata_path}: {error}") from error
    if metadata.get("output_schema_version") != OUTPUT_SCHEMA_VERSION:
        raise G2Error(
            "input metadata schema mismatch: "
            f"expected {OUTPUT_SCHEMA_VERSION}, found {metadata.get('output_schema_version')!r}"
        )
    recorded = metadata.get("outputs", {}).get("features.csv.gz", {}).get("sha256")
    if recorded != features_sha256:
        raise G2Error(
            "input features SHA-256 does not match metadata: "
            f"actual {features_sha256}, metadata {recorded}"
        )
    if not metadata.get("match_id"):
        raise G2Error("input metadata lacks match_id")
    return metadata


def derive_g2(
    *,
    features_path: Path,
    output_dir: Path,
    metadata_path: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    features_path = features_path.resolve()
    metadata_path = (
        metadata_path.resolve()
        if metadata_path is not None
        else features_path.with_name("metadata.json")
    )
    output_dir = output_dir.resolve()
    if output_dir.exists() and not overwrite:
        raise G2Error(f"output directory already exists: {output_dir}")
    features_sha256 = sha256_file(features_path)
    input_metadata = _validate_input_metadata(
        metadata_path,
        features_path=features_path,
        features_sha256=features_sha256,
    )
    table = load_feature_table(features_path)
    if table.match_id != input_metadata["match_id"]:
        raise G2Error(
            "features match_id does not match metadata: "
            f"features {table.match_id}, metadata {input_metadata['match_id']}"
        )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        output_path = staging / "g2_features.csv.gz"
        summary = write_g2_features(output_path, table)
        output_sha256 = sha256_file(output_path)
        repository_root = Path(__file__).resolve().parents[4]
        source_identity = collect_source_identity(repository_root)
        metadata_payload = {
            "task_id": TASK_ID,
            "g2_schema_version": G2_SCHEMA_VERSION,
            "match_id": table.match_id,
            "input": {
                "features_path": str(features_path),
                "features_sha256": features_sha256,
                "features_bytes": features_path.stat().st_size,
                "metadata_path": str(metadata_path),
                "metadata_sha256": sha256_file(metadata_path),
                "schema_version": input_metadata["output_schema_version"],
            },
            "lags": list(LAGS),
            "features": list(DYNAMIC_FEATURES),
            "output_columns": list(G2_COLUMNS),
            **summary,
            "outputs": {
                "g2_features.csv.gz": {
                    "bytes": output_path.stat().st_size,
                    "sha256": output_sha256,
                }
            },
            "runtime": {
                "started_at_utc": datetime.now(UTC)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z"),
                "elapsed_seconds": round(time.perf_counter() - started, 6),
                "python_version": platform.python_version(),
                "platform": platform.platform(),
            },
            **source_identity,
            "code_commit": source_identity["repository_head"],
        }
        _write_json(staging / "g2_metadata.json", metadata_payload)
        _publish_staging(staging, output_dir, overwrite=overwrite)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {
        "status": "PASS",
        "match_id": table.match_id,
        "output_dir": str(output_dir),
        "rows": summary["rows"],
        "run_count": summary["run_count"],
        "output_sha256": output_sha256,
        "elapsed_seconds": metadata_payload["runtime"]["elapsed_seconds"],
    }
