"""Candidate-local SportsCode Smart Tagging reader and weak prior builder."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from mtah_possession.data.observations import BallObservations
from mtah_possession.features.ball import AWAY, HOME, NO_CANDIDATE


class SmartTaggingError(ValueError):
    """Raised when the Smart Tagging export is invalid."""


@dataclass(frozen=True)
class TagInterval:
    start_frame: int
    end_frame: int
    team: int
    set_piece: bool


@dataclass(frozen=True)
class SmartEvidence:
    team_prior: NDArray[np.int8]
    restart: NDArray[np.bool_]
    dead: NDArray[np.bool_]


def _seconds(instance: ET.Element, tag: str) -> float:
    raw = instance.findtext(tag)
    if raw is None or not raw.strip():
        raise SmartTaggingError(f"Smart Tagging instance is missing <{tag}>")
    try:
        return float(raw)
    except ValueError as error:
        raise SmartTaggingError(f"Smart Tagging <{tag}> is not numeric") from error


def _team_value(raw: str | None) -> int:
    value = (raw or "").strip().lower()
    if value in {"h", "home", "barcelona"}:
        return HOME
    if value in {"a", "away", "athletic club", "atletic club"}:
        return AWAY
    if value in {"", "n/a", "na", "none"}:
        return NO_CANDIDATE
    raise SmartTaggingError(f"unsupported Smart Tagging team: {raw!r}")


def _tags(instance: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for label in instance.findall("label"):
        group = label.findtext("group")
        text = label.findtext("text")
        if group is not None and text is not None:
            result[group.strip()] = text.strip()
    return result


def load_tags(path: str | Path, *, fps: int, frame_count: int) -> tuple[TagInterval, ...]:
    if fps <= 0 or frame_count <= 0:
        raise SmartTaggingError("fps and frame_count must be positive")
    source = Path(path)
    try:
        root = ET.parse(source).getroot()
    except (OSError, ET.ParseError) as error:
        raise SmartTaggingError(f"could not parse Smart Tagging XML at {source}") from error

    intervals: list[TagInterval] = []
    for instance in root.iter("instance"):
        start_s = _seconds(instance, "start")
        end_s = _seconds(instance, "end")
        if end_s <= start_s:
            raise SmartTaggingError("Smart Tagging interval must have end > start")
        start = int(round(start_s * fps))
        end = int(round(end_s * fps))
        if start < 0 or end > frame_count or start >= end:
            raise SmartTaggingError(
                f"Smart Tagging interval falls outside video frames: {(start, end)}"
            )
        tags = _tags(instance)
        code = (instance.findtext("code") or "").strip().lower()
        intervals.append(
            TagInterval(
                start_frame=start,
                end_frame=end,
                team=_team_value(tags.get("Team")),
                set_piece=code == "set pieces",
            )
        )
    if not intervals:
        raise SmartTaggingError("Smart Tagging XML contains no <instance> elements")
    return tuple(sorted(intervals, key=lambda item: (item.start_frame, item.end_frame)))


def _ball_speed(
    observations: BallObservations,
    *,
    fps: int,
    pitch_length_m: float,
    pitch_width_m: float,
) -> NDArray[np.float64]:
    count = observations.positions.shape[0]
    speed = np.full(count, np.nan, dtype=np.float64)
    if count < 2:
        return speed
    delta = np.diff(observations.positions.astype(np.float64), axis=0)
    valid = observations.usable_mask[1:] & observations.usable_mask[:-1]
    values = (
        np.sqrt(np.square(delta[:, 0] * pitch_length_m) + np.square(delta[:, 1] * pitch_width_m))
        * fps
    )
    speed[1:][valid] = values[valid]
    return speed


def build_smart_evidence(
    frame_count: int,
    intervals: tuple[TagInterval, ...],
    observations: BallObservations,
    *,
    fps: int,
    pitch_length_m: float,
    pitch_width_m: float,
    restart_offset_s: float,
    dead_lookback_s: float,
    dead_speed_mps: float,
    dead_gap_s: float,
) -> SmartEvidence:
    """Build weak team, restart and bounded pre-restart dead-ball evidence."""

    home_votes = np.zeros(frame_count, dtype=np.int16)
    away_votes = np.zeros(frame_count, dtype=np.int16)
    restart = np.zeros(frame_count, dtype=bool)
    dead = np.zeros(frame_count, dtype=bool)
    speed = _ball_speed(
        observations,
        fps=fps,
        pitch_length_m=pitch_length_m,
        pitch_width_m=pitch_width_m,
    )
    dead_like = ~observations.usable_mask | (np.isfinite(speed) & (speed < dead_speed_mps))
    restart_frames = int(round(restart_offset_s * fps))
    lookback_frames = int(round(dead_lookback_s * fps))
    gap_frames = int(round(dead_gap_s * fps))

    for interval in intervals:
        window = slice(interval.start_frame, interval.end_frame)
        if interval.team == HOME:
            home_votes[window] += 1
        elif interval.team == AWAY:
            away_votes[window] += 1
        if not interval.set_piece:
            continue

        restart_frame = min(interval.end_frame, interval.start_frame + restart_frames)
        lower = max(0, interval.start_frame - lookback_frames)
        dead_start = interval.start_frame
        gap = 0
        for frame in range(interval.start_frame - 1, lower - 1, -1):
            if dead_like[frame]:
                dead_start = frame
                gap = 0
            else:
                gap += 1
                if gap > gap_frames:
                    break
        dead[dead_start:restart_frame] = True
        # Pre-restart is explicitly dead-only; restart begins only at restart_frame.
        restart[restart_frame : interval.end_frame] = True

    team_prior = np.full(frame_count, NO_CANDIDATE, dtype=np.int8)
    team_prior[(home_votes > 0) & (away_votes == 0)] = HOME
    team_prior[(away_votes > 0) & (home_votes == 0)] = AWAY
    return SmartEvidence(team_prior, restart, dead)
