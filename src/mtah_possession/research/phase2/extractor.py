"""Streaming, deterministic IDSSE Phase-2 extraction."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import xml.parsers.expat
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from mtah_possession.research.phase2.constants import (
    ALL_MATCH_IDS,
    DEVELOPMENT_MATCH_IDS,
    EVENT_COORDINATE_BOUNDS,
    FEATURE_COLUMNS,
    IDSSE_FPS,
    OPERATIONAL_LOCKBOX_MATCH_IDS,
    OUTPUT_SCHEMA_VERSION,
    REFERENCE_COLUMNS,
    TASK_ID,
    TRACKING_COORDINATE_BOUNDS,
)
from mtah_possession.research.phase2.geometry import euclidean_distance

IDSSE_REPOSITORY_RELATIVE = Path("01_RAW_DATA/idsse/repository")
INVENTORY_RELATIVE = Path("04_QUALITY_ASSESSMENT/FILE_INVENTORY.csv")
SECTIONS = ("firstHalf", "secondHalf")


class ExtractionError(RuntimeError):
    """Raised when source identity or extraction invariants fail."""


@dataclass(frozen=True)
class MatchMetadata:
    match_id: str
    competition: str
    season: str
    home_team_id: str
    away_team_id: str
    pitch_length_m: float
    pitch_width_m: float


@dataclass(frozen=True)
class SourceFiles:
    metadata: Path
    tracking: Path
    events: Path


@dataclass(frozen=True)
class BallTimeline:
    frame_numbers: np.ndarray
    timestamps_utc: list[str]
    game_sections: list[str]
    x: np.ndarray
    y: np.ndarray
    ball_status: np.ndarray
    ball_possession: np.ndarray
    section_frame_counts: dict[str, int]
    half_boundary_frame_jump: int


@dataclass
class TeamAggregates:
    tracked_n: np.ndarray
    sum_x: np.ndarray
    sum_y: np.ndarray
    min_x: np.ndarray
    max_x: np.ndarray
    min_y: np.ndarray
    max_y: np.ndarray
    nearest_m: np.ndarray
    second_m: np.ndarray
    within_2m: np.ndarray
    within_5m: np.ndarray
    coordinate_out_of_bounds: int
    invalid_coordinate_rows: int
    player_frame_rows: int


def normalize_match_id(value: str) -> str:
    normalized = value.strip().upper()
    match_id = normalized if normalized.startswith("DFL-MAT-") else f"DFL-MAT-{normalized}"
    if match_id not in ALL_MATCH_IDS:
        raise ExtractionError(f"match is outside the approved IDSSE split: {value}")
    return match_id


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_inventory(package_root: Path) -> tuple[Path, str, dict[str, dict[str, str]]]:
    path = package_root / INVENTORY_RELATIVE
    if not path.is_file():
        raise ExtractionError(f"package inventory is missing: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = {
            row["relative_path"]: row for row in csv.DictReader(handle) if row["source"] == "IDSSE"
        }
    return path, sha256_file(path), rows


def locate_source_files(package_root: Path, match_id: str) -> SourceFiles:
    repository = package_root / IDSSE_REPOSITORY_RELATIVE
    if not repository.is_dir():
        raise ExtractionError(f"IDSSE repository is missing: {repository}")
    matches = sorted(repository.glob(f"*_{match_id}.xml"))
    metadata = [path for path in matches if "_matchinformation_" in path.name]
    tracking = [path for path in matches if "_positions_raw_observed_" in path.name]
    events = [path for path in matches if "_events_raw_" in path.name]
    for kind, paths in (
        ("metadata", metadata),
        ("tracking", tracking),
        ("events", events),
    ):
        if len(paths) != 1:
            raise ExtractionError(
                f"expected exactly one {kind} file for {match_id}; found {len(paths)}"
            )
    return SourceFiles(metadata=metadata[0], tracking=tracking[0], events=events[0])


def _parse_match_metadata(path: Path) -> MatchMetadata:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        raise ExtractionError(f"invalid metadata XML: {path}: {error}") from error
    general = root.find(".//General")
    environment = root.find(".//Environment")
    if general is None or environment is None:
        raise ExtractionError(f"metadata lacks General or Environment: {path}")
    teams = {
        team.attrib.get("Role", ""): team.attrib.get("TeamId", "")
        for team in root.findall(".//Teams/Team")
    }
    required = {
        "MatchId": general.attrib.get("MatchId"),
        "CompetitionName": general.attrib.get("CompetitionName"),
        "Season": general.attrib.get("Season"),
        "home": teams.get("home"),
        "away": teams.get("guest"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ExtractionError(f"metadata fields are missing: {', '.join(missing)}")
    try:
        pitch_length = float(environment.attrib["PitchX"])
        pitch_width = float(environment.attrib["PitchY"])
    except (KeyError, ValueError) as error:
        raise ExtractionError(f"metadata pitch dimensions are invalid: {path}") from error
    return MatchMetadata(
        match_id=required["MatchId"],
        competition=required["CompetitionName"],
        season=required["Season"],
        home_team_id=required["home"],
        away_team_id=required["away"],
        pitch_length_m=pitch_length,
        pitch_width_m=pitch_width,
    )


def _scan_tracking(
    path: Path,
    frame_handler,
) -> None:
    current: dict[str, str] | None = None
    frame_set_index = [-1]
    parser = xml.parsers.expat.ParserCreate()

    def start_element(name: str, attributes: dict[str, str]) -> None:
        nonlocal current
        if name == "FrameSet":
            frame_set_index[0] += 1
            current = dict(attributes)
        elif name == "Frame":
            if current is not None:
                frame_handler(frame_set_index[0], current, dict(attributes))

    def end_element(name: str) -> None:
        nonlocal current
        if name == "FrameSet":
            current = None

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(4 * 1024 * 1024):
                parser.Parse(chunk, False)
        parser.Parse(b"", True)
    except xml.parsers.expat.ExpatError as error:
        raise ExtractionError(f"invalid positions XML: {path}: {error}") from error


def _utc_timestamp(value: str, *, match_id: str, frame_number: int) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ExtractionError(
            f"match {match_id} frame {frame_number} has invalid timestamp {value!r}"
        ) from error
    if parsed.tzinfo is None:
        raise ExtractionError(f"match {match_id} frame {frame_number} timestamp has no timezone")
    return parsed.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def read_ball_timeline(path: Path, expected_match_id: str) -> BallTimeline:
    records: list[tuple[int, str, str, float, float, int, int]] = []
    previous_by_section: dict[str, int] = {}
    section_order: list[str] = []

    def consume(_frame_set_index: int, frame_set: dict[str, str], frame: dict[str, str]) -> None:
        if frame_set.get("TeamId", "").upper() != "BALL":
            return
        match_id = frame_set.get("MatchId", "")
        if match_id != expected_match_id:
            raise ExtractionError(
                f"positions match ID {match_id!r} does not equal {expected_match_id!r}"
            )
        section = frame_set.get("GameSection", "")
        if section not in SECTIONS:
            raise ExtractionError(f"unexpected GameSection {section!r}")
        if not section_order or section_order[-1] != section:
            section_order.append(section)
        try:
            frame_number = int(frame["N"])
            timestamp = _utc_timestamp(
                frame["T"],
                match_id=expected_match_id,
                frame_number=frame_number,
            )
            x = float(frame["X"])
            y = float(frame["Y"])
            ball_status_raw = frame["BallStatus"]
            ball_possession_raw = frame["BallPossession"]
        except (KeyError, ValueError) as error:
            raise ExtractionError(
                f"match {expected_match_id} has malformed ball frame: {frame!r}"
            ) from error
        if not math.isfinite(x) or not math.isfinite(y):
            raise ExtractionError(
                f"match {expected_match_id} frame {frame_number} has non-finite ball coordinates"
            )
        if ball_status_raw not in {"0", "1"}:
            raise ExtractionError(
                f"match {expected_match_id} frame {frame_number} "
                f"invalid BallStatus={ball_status_raw}"
            )
        if ball_possession_raw not in {"1", "2"}:
            raise ExtractionError(
                f"match {expected_match_id} frame {frame_number} "
                f"invalid BallPossession={ball_possession_raw}"
            )
        previous = previous_by_section.get(section)
        if previous is not None and frame_number != previous + 1:
            raise ExtractionError(
                f"match {expected_match_id} has a non-contiguous frame sequence "
                f"within {section}: {previous} then {frame_number}"
            )
        previous_by_section[section] = frame_number
        records.append(
            (
                frame_number,
                timestamp,
                section,
                x,
                y,
                int(ball_status_raw),
                int(ball_possession_raw),
            )
        )

    _scan_tracking(path, consume)
    if not records:
        raise ExtractionError(f"no ball frames found in {path}")
    if tuple(section_order) != SECTIONS:
        raise ExtractionError(f"expected sections {SECTIONS}; found {tuple(section_order)}")
    section_counts = Counter(record[2] for record in records)
    first_half_last = max(record[0] for record in records if record[2] == "firstHalf")
    second_half_first = min(record[0] for record in records if record[2] == "secondHalf")
    if second_half_first <= first_half_last:
        raise ExtractionError("second-half frame numbers do not follow the first half")
    half_boundary_frame_jump = second_half_first - first_half_last - 1
    return BallTimeline(
        frame_numbers=np.asarray([record[0] for record in records], dtype=np.int64),
        timestamps_utc=[record[1] for record in records],
        game_sections=[record[2] for record in records],
        x=np.asarray([record[3] for record in records], dtype=np.float64),
        y=np.asarray([record[4] for record in records], dtype=np.float64),
        ball_status=np.asarray([record[5] for record in records], dtype=np.int8),
        ball_possession=np.asarray([record[6] for record in records], dtype=np.int8),
        section_frame_counts=dict(section_counts),
        half_boundary_frame_jump=half_boundary_frame_jump,
    )


def _empty_aggregates(size: int) -> TeamAggregates:
    return TeamAggregates(
        tracked_n=np.zeros((2, size), dtype=np.int32),
        sum_x=np.zeros((2, size), dtype=np.float64),
        sum_y=np.zeros((2, size), dtype=np.float64),
        min_x=np.full((2, size), np.inf, dtype=np.float64),
        max_x=np.full((2, size), -np.inf, dtype=np.float64),
        min_y=np.full((2, size), np.inf, dtype=np.float64),
        max_y=np.full((2, size), -np.inf, dtype=np.float64),
        nearest_m=np.full((2, size), np.inf, dtype=np.float64),
        second_m=np.full((2, size), np.inf, dtype=np.float64),
        within_2m=np.zeros((2, size), dtype=np.int32),
        within_5m=np.zeros((2, size), dtype=np.int32),
        coordinate_out_of_bounds=0,
        invalid_coordinate_rows=0,
        player_frame_rows=0,
    )


def aggregate_team_frames(
    path: Path,
    *,
    metadata: MatchMetadata,
    ball: BallTimeline,
) -> TeamAggregates:
    aggregates = _empty_aggregates(len(ball.frame_numbers))
    frame_index = {
        int(frame_number): index for index, frame_number in enumerate(ball.frame_numbers)
    }
    if len(frame_index) != len(ball.frame_numbers):
        raise ExtractionError("ball timeline contains duplicate frame numbers")
    ball_valid = (ball.x >= -54.5) & (ball.x <= 54.5) & (ball.y >= -36.0) & (ball.y <= 36.0)
    team_index = {
        metadata.home_team_id: 0,
        metadata.away_team_id: 1,
    }
    seen_player_frames: set[tuple[str, str, str, int]] = set()
    previous_by_frame_set: dict[int, int] = {}

    def consume(frame_set_index: int, frame_set: dict[str, str], frame: dict[str, str]) -> None:
        team_id = frame_set.get("TeamId", "")
        person_id = frame_set.get("PersonId", "")
        if team_id not in team_index:
            return
        if frame_set.get("MatchId", "") != metadata.match_id:
            raise ExtractionError("player FrameSet match ID differs from metadata")
        section = frame_set.get("GameSection", "")
        side = team_index[team_id]
        try:
            frame_number = int(frame["N"])
        except (KeyError, ValueError) as error:
            raise ExtractionError(f"malformed player frame: {frame!r}") from error
        frame_identity = (section, team_id, person_id, frame_number)
        if frame_identity in seen_player_frames:
            raise ExtractionError(f"duplicate player frame: {frame_identity}")
        seen_player_frames.add(frame_identity)
        previous = previous_by_frame_set.get(frame_set_index)
        if previous is not None and frame_number <= previous:
            raise ExtractionError(
                "player FrameSet frame numbers are not strictly increasing: "
                f"{section}/{team_id}/{person_id}"
            )
        previous_by_frame_set[frame_set_index] = frame_number
        aggregates.player_frame_rows += 1
        index = frame_index.get(frame_number)
        if index is None:
            raise ExtractionError(
                f"player frame {frame_number} has no matching ball frame for {metadata.match_id}"
            )
        if section != ball.game_sections[index]:
            raise ExtractionError(
                f"match {metadata.match_id} section {section} frame {frame_number} "
                f"does not match ball section {ball.game_sections[index]}"
            )
        try:
            x = float(frame["X"])
            y = float(frame["Y"])
        except (KeyError, ValueError):
            aggregates.invalid_coordinate_rows += 1
            return
        if not math.isfinite(x) or not math.isfinite(y):
            aggregates.invalid_coordinate_rows += 1
            return
        if x < -54.5 or x > 54.5 or y < -36.0 or y > 36.0:
            aggregates.coordinate_out_of_bounds += 1
        aggregates.tracked_n[side, index] += 1
        aggregates.sum_x[side, index] += x
        aggregates.sum_y[side, index] += y
        aggregates.min_x[side, index] = min(aggregates.min_x[side, index], x)
        aggregates.max_x[side, index] = max(aggregates.max_x[side, index], x)
        aggregates.min_y[side, index] = min(aggregates.min_y[side, index], y)
        aggregates.max_y[side, index] = max(aggregates.max_y[side, index], y)
        if not ball_valid[index]:
            return
        distance = euclidean_distance((x, y), (float(ball.x[index]), float(ball.y[index])))
        if distance < aggregates.nearest_m[side, index]:
            aggregates.second_m[side, index] = aggregates.nearest_m[side, index]
            aggregates.nearest_m[side, index] = distance
        elif distance < aggregates.second_m[side, index]:
            aggregates.second_m[side, index] = distance
        if distance <= 2.0:
            aggregates.within_2m[side, index] += 1
        if distance <= 5.0:
            aggregates.within_5m[side, index] += 1

    _scan_tracking(path, consume)
    return aggregates


def _format_number(value: float) -> str:
    if not math.isfinite(value):
        return ""
    rendered = f"{value:.6f}"
    return "0.000000" if rendered == "-0.000000" else rendered


def _team_centroid(aggregates: TeamAggregates, side: int) -> tuple[np.ndarray, np.ndarray]:
    counts = aggregates.tracked_n[side]
    with np.errstate(divide="ignore", invalid="ignore"):
        x = np.where(counts > 0, aggregates.sum_x[side] / counts, np.nan)
        y = np.where(counts > 0, aggregates.sum_y[side] / counts, np.nan)
    return x, y


def _open_text_gzip(path: Path):
    raw = path.open("wb")
    compressed = gzip.GzipFile(fileobj=raw, filename="", mode="wb", compresslevel=9, mtime=0)
    text = io.TextIOWrapper(compressed, encoding="utf-8", newline="")
    return raw, compressed, text


def write_features(
    path: Path,
    *,
    metadata: MatchMetadata,
    ball: BallTimeline,
    aggregates: TeamAggregates,
) -> dict[str, Any]:
    home_centroid_x, home_centroid_y = _team_centroid(aggregates, 0)
    away_centroid_x, away_centroid_y = _team_centroid(aggregates, 1)
    ball_valid = (ball.x >= -54.5) & (ball.x <= 54.5) & (ball.y >= -36.0) & (ball.y <= 36.0)
    empty_nearest = 0
    invalid_ball = 0
    tracked_distribution = {"home": Counter(), "away": Counter()}
    raw, compressed, text = _open_text_gzip(path)
    try:
        writer = csv.writer(text, lineterminator="\n")
        writer.writerow(FEATURE_COLUMNS)
        for index, frame_number in enumerate(ball.frame_numbers.tolist()):
            valid = bool(ball_valid[index])
            home_count = int(aggregates.tracked_n[0, index])
            away_count = int(aggregates.tracked_n[1, index])
            tracked_distribution["home"][home_count] += 1
            tracked_distribution["away"][away_count] += 1
            if not valid:
                invalid_ball += 1
            nearest_home = float(aggregates.nearest_m[0, index]) if valid else math.inf
            nearest_away = float(aggregates.nearest_m[1, index]) if valid else math.inf
            second_home = float(aggregates.second_m[0, index]) if valid else math.inf
            second_away = float(aggregates.second_m[1, index]) if valid else math.inf
            if not math.isfinite(nearest_home) or not math.isfinite(nearest_away):
                empty_nearest += 1
            centroid_distance = math.inf
            if math.isfinite(home_centroid_x[index]) and math.isfinite(away_centroid_x[index]):
                centroid_distance = euclidean_distance(
                    (float(home_centroid_x[index]), float(home_centroid_y[index])),
                    (float(away_centroid_x[index]), float(away_centroid_y[index])),
                )
            nearest_delta = math.inf
            if math.isfinite(nearest_home) and math.isfinite(nearest_away):
                nearest_delta = nearest_away - nearest_home
            ball_home_delta = math.inf
            if (
                valid
                and math.isfinite(home_centroid_x[index])
                and math.isfinite(away_centroid_x[index])
            ):
                ball_home_delta = euclidean_distance(
                    (float(ball.x[index]), float(ball.y[index])),
                    (float(home_centroid_x[index]), float(home_centroid_y[index])),
                ) - euclidean_distance(
                    (float(ball.x[index]), float(ball.y[index])),
                    (float(away_centroid_x[index]), float(away_centroid_y[index])),
                )
            writer.writerow(
                (
                    metadata.match_id,
                    frame_number,
                    ball.timestamps_utc[index],
                    ball.game_sections[index],
                    metadata.home_team_id,
                    metadata.away_team_id,
                    home_count,
                    away_count,
                    str(valid).lower(),
                    _format_number(nearest_home),
                    _format_number(nearest_away),
                    _format_number(nearest_delta),
                    _format_number(second_home),
                    _format_number(second_away),
                    int(aggregates.within_2m[0, index]) if valid else "",
                    int(aggregates.within_2m[1, index]) if valid else "",
                    int(aggregates.within_5m[0, index]) if valid else "",
                    int(aggregates.within_5m[1, index]) if valid else "",
                    _format_number(float(home_centroid_x[index])),
                    _format_number(float(home_centroid_y[index])),
                    _format_number(float(away_centroid_x[index])),
                    _format_number(float(away_centroid_y[index])),
                    _format_number(centroid_distance),
                    _format_number(float(aggregates.max_y[0, index] - aggregates.min_y[0, index]))
                    if home_count
                    else "",
                    _format_number(float(aggregates.max_y[1, index] - aggregates.min_y[1, index]))
                    if away_count
                    else "",
                    _format_number(float(aggregates.max_x[0, index] - aggregates.min_x[0, index]))
                    if home_count
                    else "",
                    _format_number(float(aggregates.max_x[1, index] - aggregates.min_x[1, index]))
                    if away_count
                    else "",
                    _format_number(ball_home_delta),
                )
            )
        text.flush()
    finally:
        text.close()
        if not compressed.closed:
            compressed.close()
        raw.close()
    return {
        "rows": len(ball.frame_numbers),
        "invalid_ball_geometry": invalid_ball,
        "empty_nearest_frames": empty_nearest,
        "tracked_player_count_distribution": {
            side: {str(count): occurrences for count, occurrences in sorted(values.items())}
            for side, values in tracked_distribution.items()
        },
    }


def write_reference(path: Path, *, match_id: str, ball: BallTimeline) -> None:
    raw, compressed, text = _open_text_gzip(path)
    try:
        writer = csv.writer(text, lineterminator="\n")
        writer.writerow(REFERENCE_COLUMNS)
        for index, frame_number in enumerate(ball.frame_numbers.tolist()):
            writer.writerow(
                (
                    match_id,
                    frame_number,
                    str(bool(ball.ball_status[index])).lower(),
                    str(int(ball.ball_possession[index]) == 1).lower(),
                )
            )
        text.flush()
    finally:
        text.close()
        if not compressed.closed:
            compressed.close()
        raw.close()


def load_split_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExtractionError(f"cannot read split config: {path}: {error}") from error
    if config.get("split_unit") != "match" or config.get("random_frame_split") is not False:
        raise ExtractionError("split config must be match-level with no random frame split")
    entries = config.get("matches")
    if not isinstance(entries, list):
        raise ExtractionError("split config matches must be a list")
    by_id = {entry.get("match_id"): entry for entry in entries if isinstance(entry, dict)}
    if set(by_id) != set(ALL_MATCH_IDS) or len(by_id) != len(entries):
        raise ExtractionError("split config match IDs differ from the approved seven-match set")
    expected_roles = {
        **{match_id: "development" for match_id in DEVELOPMENT_MATCH_IDS},
        **{match_id: "operational_lockbox" for match_id in OPERATIONAL_LOCKBOX_MATCH_IDS},
    }
    for match_id, role in expected_roles.items():
        if by_id[match_id].get("split_role") != role:
            raise ExtractionError(f"split role mismatch for {match_id}")
    return config


def build_split_manifest(
    package_root: Path,
    *,
    split_config_path: Path,
    inventory: dict[str, dict[str, str]],
) -> dict[str, Any]:
    config = load_split_config(split_config_path)
    repository_root = Path(__file__).resolve().parents[4]
    try:
        displayed_config_path = split_config_path.resolve().relative_to(repository_root).as_posix()
    except ValueError:
        displayed_config_path = split_config_path.name
    matches = []
    for entry in config["matches"]:
        match_id = entry["match_id"]
        sources = locate_source_files(package_root, match_id)
        source_records = []
        for role, path in (
            ("metadata", sources.metadata),
            ("tracking", sources.tracking),
            ("events", sources.events),
        ):
            relative = path.relative_to(package_root).as_posix()
            inventory_row = inventory.get(relative)
            if inventory_row is None:
                raise ExtractionError(f"inventory lacks {relative}")
            source_records.append(
                {
                    "role": role,
                    "path": relative,
                    "sha256": inventory_row["sha256"],
                    "bytes": int(inventory_row["bytes"]),
                }
            )
        matches.append(
            {
                "match_id": match_id,
                "competition": entry["competition"],
                "season": entry["season"],
                "split_role": entry["split_role"],
                "sources": source_records,
            }
        )
    return {
        "schema_version": config["schema_version"],
        "split_unit": "match",
        "random_frame_split": False,
        "historical_exposure": config["historical_exposure"],
        "split_config": {
            "path": displayed_config_path,
            "sha256": sha256_file(split_config_path),
        },
        "matches": matches,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _peak_memory_bytes() -> int | None:
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class ProcessMemoryCounters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            process = kernel32.GetCurrentProcess()
            psapi = ctypes.WinDLL("psapi")
            psapi.GetProcessMemoryInfo.argtypes = (
                wintypes.HANDLE,
                ctypes.POINTER(ProcessMemoryCounters),
                wintypes.DWORD,
            )
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            if psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
                return int(counters.PeakWorkingSetSize)
        except (AttributeError, OSError):
            return None
    try:
        import resource

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    except (ImportError, OSError):
        return None


def collect_source_identity(
    repository_root: Path,
    *,
    git_executable: str = "git",
) -> dict[str, str | bool]:
    unavailable: dict[str, str | bool] = {
        "repository_head": "unavailable",
        "implementation_commit": "unavailable",
        "source_tree_dirty": True,
    }
    try:
        repository_head = subprocess.run(
            [git_executable, "-C", str(repository_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        implementation_commit = subprocess.run(
            [
                git_executable,
                "-C",
                str(repository_root),
                "log",
                "-1",
                "--format=%H",
                "--",
                "src/mtah_possession/research/phase2",
                "configs/research/phase2",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty_output = subprocess.run(
            [
                git_executable,
                "-C",
                str(repository_root),
                "status",
                "--porcelain",
                "--",
                "src/mtah_possession/research/phase2",
                "configs/research/phase2",
                "tests/research/phase2",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return unavailable
    if not re.fullmatch(r"[0-9a-f]{40}", repository_head) or not re.fullmatch(
        r"[0-9a-f]{40}", implementation_commit
    ):
        return unavailable
    return {
        "repository_head": repository_head,
        "implementation_commit": implementation_commit,
        "source_tree_dirty": bool(dirty_output.strip()),
    }


def _source_record(path: Path, package_root: Path, inventory: dict[str, dict[str, str]]) -> dict:
    relative = path.relative_to(package_root).as_posix()
    row = inventory.get(relative)
    if row is None:
        raise ExtractionError(f"inventory lacks {relative}")
    actual_sha256 = sha256_file(path)
    if actual_sha256 != row["sha256"]:
        raise ExtractionError(f"source SHA-256 mismatch: {relative}")
    if path.stat().st_size != int(row["bytes"]):
        raise ExtractionError(f"source byte-size mismatch: {relative}")
    return {
        "path": relative,
        "bytes": int(row["bytes"]),
        "sha256": actual_sha256,
        "matches_inventory": True,
    }


def _publish_staging(staging: Path, output_dir: Path, *, overwrite: bool) -> None:
    if output_dir.exists() and not overwrite:
        raise ExtractionError(f"output directory already exists: {output_dir}")
    if not output_dir.exists():
        os.replace(staging, output_dir)
        return
    backup = output_dir.with_name(f".{output_dir.name}.backup-{os.getpid()}")
    if backup.exists():
        raise ExtractionError(f"stale output backup exists: {backup}")
    os.replace(output_dir, backup)
    try:
        os.replace(staging, output_dir)
    except Exception:
        os.replace(backup, output_dir)
        raise
    shutil.rmtree(backup)


def extract_idss(
    *,
    package_root: Path,
    match_id: str,
    output_dir: Path,
    split_config_path: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    started_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    package_root = package_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir.is_relative_to(package_root):
        raise ExtractionError("output directory must be outside the frozen package")
    if output_dir.exists() and not overwrite:
        raise ExtractionError(f"output directory already exists: {output_dir}")
    normalized_match_id = normalize_match_id(match_id)
    _inventory_path, inventory_sha256, inventory = load_inventory(package_root)
    source_files = locate_source_files(package_root, normalized_match_id)
    metadata = _parse_match_metadata(source_files.metadata)
    if metadata.match_id != normalized_match_id:
        raise ExtractionError("metadata match ID differs from requested match")
    source_records = {
        role: _source_record(path, package_root, inventory)
        for role, path in (
            ("metadata", source_files.metadata),
            ("tracking", source_files.tracking),
            ("events", source_files.events),
        )
    }
    split_manifest = build_split_manifest(
        package_root,
        split_config_path=split_config_path.resolve(),
        inventory=inventory,
    )
    ball = read_ball_timeline(source_files.tracking, normalized_match_id)
    aggregates = aggregate_team_frames(
        source_files.tracking,
        metadata=metadata,
        ball=ball,
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        features_path = staging / "features.csv.gz"
        reference_path = staging / "reference.csv.gz"
        split_path = staging / "split_manifest.json"
        feature_summary = write_features(
            features_path,
            metadata=metadata,
            ball=ball,
            aggregates=aggregates,
        )
        write_reference(reference_path, match_id=normalized_match_id, ball=ball)
        _write_json(split_path, split_manifest)
        output_hashes = {
            path.name: {
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in (features_path, reference_path, split_path)
        }
        repository_root = Path(__file__).resolve().parents[4]
        source_identity = collect_source_identity(repository_root)
        elapsed = time.perf_counter() - started
        metadata_payload = {
            "task_id": TASK_ID,
            "match_id": normalized_match_id,
            "competition": metadata.competition,
            "season": metadata.season,
            "home_team_id": metadata.home_team_id,
            "away_team_id": metadata.away_team_id,
            "coordinate_system": "centered_pitch_metres",
            "coordinate_contract": {
                "tracking": {
                    "bounds": list(TRACKING_COORDINATE_BOUNDS),
                    "origin": "pitch_centre",
                    "units": "metres",
                },
                "event": {
                    "bounds": list(EVENT_COORDINATE_BOUNDS),
                    "origin": "pitch_corner",
                    "units": "metres",
                    "usage": "not_joined_to_tracking",
                },
            },
            "fps": IDSSE_FPS,
            "frame_counts": {
                "total": len(ball.frame_numbers),
                **ball.section_frame_counts,
                "half_boundary_frame_jump": ball.half_boundary_frame_jump,
            },
            "output_schema_version": OUTPUT_SCHEMA_VERSION,
            "source": {
                "package_relative_root": IDSSE_REPOSITORY_RELATIVE.as_posix(),
                "inventory_path": INVENTORY_RELATIVE.as_posix(),
                "inventory_sha256": inventory_sha256,
                "files": source_records,
            },
            "missing_and_invalid": {
                **feature_summary,
                "invalid_player_coordinate_rows": aggregates.invalid_coordinate_rows,
                "player_coordinate_out_of_bounds_rows": aggregates.coordinate_out_of_bounds,
                "player_frame_rows": aggregates.player_frame_rows,
            },
            "runtime": {
                "started_at_utc": started_at,
                "elapsed_seconds": round(elapsed, 6),
                "peak_memory_bytes": _peak_memory_bytes(),
                "python_version": platform.python_version(),
                "platform": platform.platform(),
            },
            "outputs": output_hashes,
            **source_identity,
            "code_commit": source_identity["repository_head"],
        }
        _write_json(staging / "metadata.json", metadata_payload)
        _publish_staging(staging, output_dir, overwrite=overwrite)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {
        "status": "PASS",
        "match_id": normalized_match_id,
        "output_dir": str(output_dir),
        "rows": len(ball.frame_numbers),
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "outputs": metadata_payload["outputs"],
    }


def smoke_idss(
    *,
    package_root: Path,
    match_ids: list[str] | None = None,
) -> dict[str, Any]:
    package_root = package_root.resolve()
    _, inventory_sha256, inventory = load_inventory(package_root)
    requested = [normalize_match_id(match_id) for match_id in match_ids or ALL_MATCH_IDS]
    results = []
    for match_id in requested:
        sources = locate_source_files(package_root, match_id)
        metadata = _parse_match_metadata(sources.metadata)
        if metadata.match_id != match_id:
            raise ExtractionError(
                f"smoke match identity mismatch: requested {match_id}, "
                f"metadata declares {metadata.match_id}"
            )
        file_records = {
            role: _source_record(path, package_root, inventory)
            for role, path in (
                ("metadata", sources.metadata),
                ("tracking", sources.tracking),
                ("events", sources.events),
            )
        }
        results.append(
            {
                "match_id": match_id,
                "competition": metadata.competition,
                "season": metadata.season,
                "home_team_id": metadata.home_team_id,
                "away_team_id": metadata.away_team_id,
                "files": file_records,
                "status": "PASS",
            }
        )
    return {
        "status": "PASS",
        "inventory_sha256": inventory_sha256,
        "matches": results,
    }
