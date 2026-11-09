"""Candidate-B configuration with explicit parameter provenance."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CandidateConfigError(ValueError):
    """Raised when the candidate configuration is incomplete or invalid."""


@dataclass(frozen=True)
class CandidateParameter:
    value: float | int | bool
    unit: str
    source: str
    rationale: str


@dataclass(frozen=True)
class CandidateConfig:
    match_id: str
    fps: int
    expected_frames: int
    pitch_length_m: float
    pitch_width_m: float
    ungraded_blocks: tuple[tuple[int, int], ...]
    forced_dead_blocks: tuple[tuple[int, int], ...]
    enable_smart_tagging: bool
    parameters: dict[str, CandidateParameter]

    def number(self, name: str) -> float:
        value = self.parameters[name].value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CandidateConfigError(f"parameter {name!r} is not numeric")
        return float(value)

    def integer(self, name: str) -> int:
        value = self.number(name)
        if value != int(value):
            raise CandidateConfigError(f"parameter {name!r} is not an integer")
        return int(value)


REQUIRED_PARAMETERS = frozenset(
    {
        "ball_interpolation_max_s",
        "distance_scale_m",
        "vote_weight",
        "tracking_bonus",
        "smart_team_weight",
        "near_player_vote_k",
        "contest_margin_m",
        "max_control_distance_m",
        "min_closing_speed_mps",
        "max_time_to_ball_s",
        "time_advantage_cap_s",
        "time_to_ball_weight",
        "ball_rest_weight",
        "ball_rest_speed_mps",
        "ball_rest_min_s",
        "out_of_bounds_weight",
        "smart_dead_weight",
        "restart_suppression",
        "switch_penalty",
        "dead_enter_penalty",
        "restart_penalty",
        "restart_boost",
        "hysteresis_gain",
        "hysteresis_max_boost",
        "dwell_frames",
        "dwell_penalty",
        "min_flicker_frames",
        "short_segment_frames",
        "short_segment_confidence",
        "short_dead_frames",
        "short_dead_confidence",
        "smart_restart_offset_s",
        "smart_dead_lookback_s",
        "smart_dead_speed_mps",
        "smart_dead_gap_s",
        "emission_smoothing_half_width_frames",
        "dead_smoothing_half_width_frames",
    }
)


def _positive(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise CandidateConfigError(f"{name} must be positive")
    return float(value)


def _non_negative(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise CandidateConfigError(f"{name} must be non-negative")
    return float(value)


def _blocks(value: Any, expected_frames: int, name: str) -> tuple[tuple[int, int], ...]:
    if not isinstance(value, list):
        raise CandidateConfigError(f"{name} must be a list")
    blocks: list[tuple[int, int]] = []
    previous_last = -1
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            raise CandidateConfigError(f"{name} entries must be [first, last]")
        first, last = item
        if (
            isinstance(first, bool)
            or isinstance(last, bool)
            or not isinstance(first, int)
            or not isinstance(last, int)
        ):
            raise CandidateConfigError(f"{name} entries must be integer frames")
        if first < 0 or last < first or last >= expected_frames:
            raise CandidateConfigError(f"{name} entry is outside the frame contract")
        if first <= previous_last:
            raise CandidateConfigError(f"{name} must be sorted and non-overlapping")
        blocks.append((first, last))
        previous_last = last
    return tuple(blocks)


def load_candidate_config(path: str | Path) -> CandidateConfig:
    source = Path(path)
    try:
        values = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CandidateConfigError(f"could not read candidate config at {source}") from error
    if not isinstance(values, dict):
        raise CandidateConfigError("candidate config root must be an object")
    if values.get("schema_version") != "candidate-b-1":
        raise CandidateConfigError("schema_version must be 'candidate-b-1'")

    fps = values.get("fps")
    expected_frames = values.get("expected_frames")
    if not isinstance(fps, int) or fps <= 0:
        raise CandidateConfigError("fps must be a positive integer")
    if not isinstance(expected_frames, int) or expected_frames <= 0:
        raise CandidateConfigError("expected_frames must be a positive integer")
    pitch = values.get("pitch")
    if not isinstance(pitch, dict):
        raise CandidateConfigError("pitch must be an object")
    pitch_length = _positive(pitch.get("length_m"), "pitch.length_m")
    pitch_width = _positive(pitch.get("width_m"), "pitch.width_m")

    raw_parameters = values.get("parameters")
    if not isinstance(raw_parameters, dict):
        raise CandidateConfigError("parameters must be an object")
    missing = REQUIRED_PARAMETERS.difference(raw_parameters)
    unknown = set(raw_parameters).difference(REQUIRED_PARAMETERS)
    if missing:
        raise CandidateConfigError(f"missing candidate parameters: {sorted(missing)}")
    if unknown:
        raise CandidateConfigError(f"unknown candidate parameters: {sorted(unknown)}")

    parameters: dict[str, CandidateParameter] = {}
    for name, raw in raw_parameters.items():
        if not isinstance(raw, dict):
            raise CandidateConfigError(f"parameter {name!r} must be an object")
        unit = raw.get("unit")
        source_name = raw.get("source")
        rationale = raw.get("rationale")
        if not isinstance(unit, str) or not unit.strip():
            raise CandidateConfigError(f"parameter {name!r} has no unit")
        if not isinstance(source_name, str) or not source_name.strip():
            raise CandidateConfigError(f"parameter {name!r} has no source")
        if not isinstance(rationale, str) or not rationale.strip():
            raise CandidateConfigError(f"parameter {name!r} has no rationale")
        parameters[name] = CandidateParameter(
            value=raw.get("value"),
            unit=unit,
            source=source_name,
            rationale=rationale,
        )

    for name in REQUIRED_PARAMETERS.difference({"min_flicker_frames"}):
        _non_negative(parameters[name].value, name)
    _positive(parameters["distance_scale_m"].value, "distance_scale_m")
    _positive(parameters["ball_rest_speed_mps"].value, "ball_rest_speed_mps")
    _positive(parameters["ball_rest_min_s"].value, "ball_rest_min_s")
    _positive(parameters["smart_dead_speed_mps"].value, "smart_dead_speed_mps")
    _positive(parameters["smart_restart_offset_s"].value, "smart_restart_offset_s")
    _positive(parameters["smart_dead_lookback_s"].value, "smart_dead_lookback_s")
    flicker = parameters["min_flicker_frames"].value
    if isinstance(flicker, bool) or not isinstance(flicker, int) or flicker < 0:
        raise CandidateConfigError("min_flicker_frames must be a non-negative integer")
    vote_k = parameters["near_player_vote_k"].value
    if isinstance(vote_k, bool) or not isinstance(vote_k, int) or vote_k <= 0:
        raise CandidateConfigError("near_player_vote_k must be a positive integer")
    _positive(parameters["contest_margin_m"].value, "contest_margin_m")
    _positive(parameters["max_control_distance_m"].value, "max_control_distance_m")
    _positive(parameters["min_closing_speed_mps"].value, "min_closing_speed_mps")
    _positive(parameters["max_time_to_ball_s"].value, "max_time_to_ball_s")
    _positive(parameters["time_advantage_cap_s"].value, "time_advantage_cap_s")
    _non_negative(parameters["time_to_ball_weight"].value, "time_to_ball_weight")
    smoothing = parameters["emission_smoothing_half_width_frames"].value
    if isinstance(smoothing, bool) or not isinstance(smoothing, int) or smoothing < 0:
        raise CandidateConfigError(
            "emission_smoothing_half_width_frames must be a non-negative integer"
        )
    dead_smoothing = parameters["dead_smoothing_half_width_frames"].value
    if (
        isinstance(dead_smoothing, bool)
        or not isinstance(dead_smoothing, int)
        or dead_smoothing < 0
    ):
        raise CandidateConfigError(
            "dead_smoothing_half_width_frames must be a non-negative integer"
        )
    for name in ("short_segment_frames", "short_dead_frames"):
        value = parameters[name].value
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise CandidateConfigError(f"{name} must be a non-negative integer")
    for name in ("short_segment_confidence", "short_dead_confidence"):
        value = _non_negative(parameters[name].value, name)
        if value > 1:
            raise CandidateConfigError(f"{name} must be between 0 and 1")
    dwell_frames = parameters["dwell_frames"].value
    if isinstance(dwell_frames, bool) or not isinstance(dwell_frames, int) or dwell_frames < 0:
        raise CandidateConfigError("dwell_frames must be a non-negative integer")
    if dwell_frames > 120:
        raise CandidateConfigError("dwell_frames must not exceed 120")
    _non_negative(parameters["dwell_penalty"].value, "dwell_penalty")
    _non_negative(parameters["hysteresis_gain"].value, "hysteresis_gain")
    _non_negative(parameters["hysteresis_max_boost"].value, "hysteresis_max_boost")

    match_id = values.get("match_id")
    if not isinstance(match_id, str) or not match_id.strip():
        raise CandidateConfigError("match_id must be a non-empty string")
    enable_smart_tagging = values.get("enable_smart_tagging", True)
    if not isinstance(enable_smart_tagging, bool):
        raise CandidateConfigError("enable_smart_tagging must be boolean")

    ungraded = _blocks(values.get("ungraded_blocks"), expected_frames, "ungraded_blocks")
    forced = _blocks(values.get("forced_dead_blocks"), expected_frames, "forced_dead_blocks")
    for first, last in forced:
        for other_first, other_last in ungraded:
            if first <= other_last and other_first <= last:
                raise CandidateConfigError("forced_dead_blocks cannot overlap ungraded_blocks")

    return CandidateConfig(
        match_id=match_id,
        fps=fps,
        expected_frames=expected_frames,
        pitch_length_m=pitch_length,
        pitch_width_m=pitch_width,
        ungraded_blocks=ungraded,
        forced_dead_blocks=forced,
        enable_smart_tagging=enable_smart_tagging,
        parameters=parameters,
    )
