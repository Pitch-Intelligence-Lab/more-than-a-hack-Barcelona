"""Read FIFA/EPTS tactical tracking and align it to submission rows."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from mtah_possession.config import (
    DEFAULT_MATCH_STEM,
    EXPECTED_TACTICAL_FRAMES,
    load_settings,
    require_tactical_assets,
)

FloatArray = NDArray[np.float32]
IntArray = NDArray[np.int8]


class TrackingDataError(ValueError):
    """Raised for a structurally invalid metadata or raw tracking file."""


@dataclass(frozen=True)
class FrameAlignment:
    """Proof that ATD frame IDs form the expected 1-based contiguous sequence."""

    expected_frames: int
    first_frame_id: int
    last_frame_id: int
    contiguous: bool

    @property
    def video_frame_range(self) -> tuple[int, int]:
        return self.first_frame_id - 1, self.last_frame_id - 1


@dataclass(frozen=True)
class TrackingData:
    """Synthetic or tactical tracking in submission-frame coordinates."""

    frame_count: int
    home_team: str
    away_team: str
    team_by_slot: IntArray
    ball_positions: FloatArray
    slot_positions: FloatArray
    alignment: FrameAlignment
    slot_speeds: FloatArray | None = None

    @property
    def slot_count(self) -> int:
        return int(self.team_by_slot.size)

    @property
    def ball_visible(self) -> NDArray[np.bool_]:
        return ~np.isnan(self.ball_positions).any(axis=1)

    @property
    def player_visible(self) -> NDArray[np.bool_]:
        return ~np.isnan(self.slot_positions).any(axis=2)


def _parse_metadata(meta_path: Path) -> tuple[str, str, IntArray]:
    try:
        root = ET.parse(meta_path).getroot()
    except (ET.ParseError, OSError) as error:
        raise TrackingDataError(f"could not parse ATD metadata at {meta_path}") from error

    teams = list(root.iter("Team"))
    if len(teams) != 2:
        raise TrackingDataError(f"ATD metadata at {meta_path} must contain exactly 2 teams")

    team_ids = [team.get("id") for team in teams]
    if any(team_id is None for team_id in team_ids) or len(set(team_ids)) != 2:
        raise TrackingDataError(f"ATD metadata at {meta_path} has invalid team IDs")
    names = [team.findtext("Name") for team in teams]
    if any(not name or not name.strip() for name in names):
        raise TrackingDataError(f"ATD metadata at {meta_path} has a blank team name")

    players = list(root.iter("Player"))
    if not players:
        raise TrackingDataError(f"ATD metadata at {meta_path} has no Player entries")

    id_to_team = {team_ids[0]: 0, team_ids[1]: 1}
    mapping: list[int] = []
    for player in players:
        team_id = player.get("teamId")
        if team_id not in id_to_team:
            raise TrackingDataError(
                f"ATD metadata at {meta_path} assigns a Player to an unknown team"
            )
        mapping.append(id_to_team[team_id])

    return names[0].strip(), names[1].strip(), np.asarray(mapping, dtype=np.int8)


def _is_missing(group: str) -> bool:
    return group[:3].lower() == "nan"


def _parse_object(group: str, *, context: str) -> tuple[float, float, float]:
    if _is_missing(group):
        return float("nan"), float("nan"), float("nan")
    fields = group.split(",")
    if len(fields) != 3:
        raise TrackingDataError(f"malformed {context}: expected x,y,speed")
    try:
        x, y, speed = float(fields[0]), float(fields[1]), float(fields[2])
    except ValueError as error:
        raise TrackingDataError(f"non-numeric {context} coordinates") from error
    if not np.isfinite(x) or not np.isfinite(y):
        raise TrackingDataError(f"non-finite {context} coordinates")
    return x, y, speed


def _parse_raw(
    raw_path: Path,
    *,
    slot_count: int,
    expected_frames: int,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    positions = np.full((expected_frames, slot_count, 2), np.nan, dtype=np.float32)
    speeds = np.full((expected_frames, slot_count), np.nan, dtype=np.float32)
    ball = np.full((expected_frames, 2), np.nan, dtype=np.float32)

    try:
        handle = raw_path.open("r", encoding="utf-8", newline="")
    except OSError as error:
        raise TrackingDataError(f"could not open ATD raw tracking at {raw_path}") from error

    with handle:
        for expected_frame_id, line in enumerate(handle, start=1):
            if expected_frame_id > expected_frames:
                raise TrackingDataError(
                    f"ATD raw tracking at {raw_path} has more than {expected_frames} records"
                )
            record = line.rstrip("\r\n")
            if not record:
                raise TrackingDataError(
                    f"ATD raw tracking at {raw_path} has a blank record at frame_id "
                    f"{expected_frame_id}"
                )

            parts = record.split(":")
            if len(parts) != 3:
                raise TrackingDataError(
                    f"ATD raw tracking at {raw_path} has a malformed record at frame_id "
                    f"{expected_frame_id}"
                )
            try:
                frame_id = int(parts[0])
            except ValueError as error:
                raise TrackingDataError(
                    f"ATD raw tracking at {raw_path} has a non-integer frame_id"
                ) from error
            if frame_id != expected_frame_id:
                raise TrackingDataError(
                    f"ATD frame alignment failed at row {expected_frame_id}: "
                    f"expected frame_id {expected_frame_id}, found {frame_id}"
                )

            groups = parts[1].split(";")
            if len(groups) != slot_count:
                raise TrackingDataError(
                    f"ATD raw tracking at {raw_path} has {len(groups)} player slots at "
                    f"frame_id {frame_id}; metadata expects {slot_count}"
                )

            row_index = frame_id - 1
            for slot, group in enumerate(groups):
                x, y, speed = _parse_object(group, context="player slot")
                positions[row_index, slot] = (x, y)
                speeds[row_index, slot] = speed
            ball_x, ball_y, _ball_speed = _parse_object(parts[2], context="ball")
            ball[row_index] = (ball_x, ball_y)

    if expected_frames and (
        positions.shape[0] != expected_frames or ball.shape[0] != expected_frames
    ):
        raise TrackingDataError("internal tracking array length mismatch")
    return positions, speeds, ball


def _validate_record_count(raw_path: Path, expected_frames: int) -> int:
    try:
        with raw_path.open("r", encoding="utf-8", newline="") as handle:
            count = sum(1 for _line in handle)
    except (OSError, UnicodeDecodeError) as error:
        raise TrackingDataError(f"could not read ATD raw tracking at {raw_path}") from error
    if count != expected_frames:
        raise TrackingDataError(
            f"ATD raw tracking at {raw_path} has {count} records; expected {expected_frames}"
        )
    return count


def load_tactical_tracking(
    data_root: str | Path | None = None,
    *,
    expected_frames: int = EXPECTED_TACTICAL_FRAMES,
    match_id: str = DEFAULT_MATCH_STEM,
) -> TrackingData:
    """Load tactical ATD only, mapped to video frames ``0..expected_frames-1``."""

    settings = load_settings(data_root, match_id=match_id)
    paths = require_tactical_assets(settings, ("atd_meta", "atd_raw"))
    home_team, away_team, team_by_slot = _parse_metadata(paths["atd_meta"])
    # The metadata gives the authoritative slot count. Count records once before
    # allocating frame-by-slot arrays so a broadcast or truncated file fails clearly.
    _validate_record_count(paths["atd_raw"], expected_frames)
    slot_positions, slot_speeds, ball_positions = _parse_raw(
        paths["atd_raw"],
        slot_count=int(team_by_slot.size),
        expected_frames=expected_frames,
    )
    alignment = FrameAlignment(
        expected_frames=expected_frames,
        first_frame_id=1,
        last_frame_id=expected_frames,
        contiguous=True,
    )
    return TrackingData(
        frame_count=expected_frames,
        home_team=home_team,
        away_team=away_team,
        team_by_slot=team_by_slot,
        ball_positions=ball_positions,
        slot_positions=slot_positions,
        alignment=alignment,
        slot_speeds=slot_speeds,
    )
