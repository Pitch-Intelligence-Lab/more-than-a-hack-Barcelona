"""Typed algorithm configuration with explicit parameter provenance."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AlgorithmConfigError(ValueError):
    """Raised when an algorithm configuration is missing or invalid."""


PARAMETER_SOURCES = frozenset(
    {
        "official-fact",
        "official-rule",
        "general-football-prior",
        "engineering-assumption",
        "external-data",
        "synthetic-test",
    }
)


@dataclass(frozen=True)
class Parameter:
    value: float | int | bool
    unit: str
    source: str
    rationale: str


@dataclass(frozen=True)
class BaselineConfig:
    expected_frames: int
    window_half_width_frames: int
    pitch_length_m: float
    pitch_width_m: float
    match_id: str = "BAR-ATH"

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> BaselineConfig:
        required = {
            "expected_frames",
            "window_half_width_frames",
            "pitch_length_m",
            "pitch_width_m",
        }
        missing = required.difference(values)
        permitted = required | {"algorithm", "match_id"}
        unknown = set(values).difference(permitted)
        if missing:
            raise AlgorithmConfigError(f"configuration is missing keys: {sorted(missing)}")
        if unknown:
            raise AlgorithmConfigError(f"configuration has unknown keys: {sorted(unknown)}")

        try:
            expected_frames = int(values["expected_frames"])
            window = int(values["window_half_width_frames"])
            length = float(values["pitch_length_m"])
            width = float(values["pitch_width_m"])
        except (TypeError, ValueError) as error:
            raise AlgorithmConfigError("configuration values must be numeric") from error
        if expected_frames <= 0:
            raise AlgorithmConfigError("expected_frames must be positive")
        if window < 0:
            raise AlgorithmConfigError("window_half_width_frames must be non-negative")
        if length <= 0 or width <= 0:
            raise AlgorithmConfigError("pitch dimensions must be positive")
        match_id = str(values.get("match_id", "BAR-ATH"))
        return cls(expected_frames, window, length, width, match_id)


@dataclass(frozen=True)
class StateEngineConfig:
    match_id: str
    fps: int
    expected_frames: int
    pitch_length_m: float
    pitch_width_m: float
    coordinate_representation: str
    team_mapping_source: str
    ungraded_blocks: tuple[tuple[int, int], ...]
    optional_assets: Mapping[str, bool]
    parameters: Mapping[str, Parameter]

    def number(self, name: str) -> float:
        return float(self.parameters[name].value)

    def integer(self, name: str) -> int:
        return int(self.parameters[name].value)

    def flag(self, name: str) -> bool:
        value = self.parameters[name].value
        if not isinstance(value, bool):
            raise AlgorithmConfigError(f"parameter {name!r} must be boolean")
        return value

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> StateEngineConfig:
        required_top = {
            "schema_version",
            "algorithm",
            "match_id",
            "fps",
            "expected_frames",
            "pitch",
            "coordinate_representation",
            "team_mapping_source",
            "ungraded_blocks",
            "ungraded_blocks_source",
            "optional_assets",
            "parameters",
        }
        missing = required_top.difference(values)
        unknown = set(values).difference(required_top)
        if missing:
            raise AlgorithmConfigError(f"configuration is missing keys: {sorted(missing)}")
        if unknown:
            raise AlgorithmConfigError(f"configuration has unknown keys: {sorted(unknown)}")
        if values["schema_version"] != "2.0":
            raise AlgorithmConfigError("state-engine schema_version must be '2.0'")
        if values["algorithm"] != "state_engine":
            raise AlgorithmConfigError("state-engine algorithm must be 'state_engine'")

        fps = _positive_integer(values["fps"], "fps")
        expected_frames = _positive_integer(values["expected_frames"], "expected_frames")
        match_id = values["match_id"]
        if not isinstance(match_id, str) or not match_id.strip():
            raise AlgorithmConfigError("match_id must be a non-empty string")

        coordinate = values["coordinate_representation"]
        if coordinate != "normalized-origin-corner":
            raise AlgorithmConfigError(
                "coordinate_representation must be 'normalized-origin-corner'"
            )
        team_source = values["team_mapping_source"]
        if team_source != "atd-metadata-order":
            raise AlgorithmConfigError("team_mapping_source must be 'atd-metadata-order'")

        pitch = values["pitch"]
        if not isinstance(pitch, dict):
            raise AlgorithmConfigError("pitch must be an object")
        pitch_length = _positive_number(pitch.get("length_m"), "pitch.length_m")
        pitch_width = _positive_number(pitch.get("width_m"), "pitch.width_m")

        optional_assets = values["optional_assets"]
        if not isinstance(optional_assets, dict) or not all(
            isinstance(key, str) and isinstance(value, bool)
            for key, value in optional_assets.items()
        ):
            raise AlgorithmConfigError("optional_assets must map asset names to booleans")
        required_assets = {"smart_tagging", "homography", "broadcast", "video"}
        if set(optional_assets) != required_assets:
            raise AlgorithmConfigError(
                f"optional_assets must contain exactly {sorted(required_assets)}"
            )
        enabled_assets = sorted(name for name, enabled in optional_assets.items() if enabled)
        if enabled_assets:
            raise AlgorithmConfigError(
                f"optional assets are not wired into the CLI build: {enabled_assets}"
            )

        raw_parameters = values["parameters"]
        if not isinstance(raw_parameters, dict):
            raise AlgorithmConfigError("parameters must be an object")
        parameters = {name: _parse_parameter(name, raw) for name, raw in raw_parameters.items()}
        missing_parameters = REQUIRED_PARAMETERS.difference(parameters)
        unknown_parameters = set(parameters).difference(REQUIRED_PARAMETERS)
        if missing_parameters:
            raise AlgorithmConfigError(
                f"missing state-engine parameters: {sorted(missing_parameters)}"
            )
        if unknown_parameters:
            raise AlgorithmConfigError(
                f"unknown state-engine parameters: {sorted(unknown_parameters)}"
            )
        _validate_parameter_types(parameters)

        ungraded_blocks = _parse_ungraded_blocks(
            values["ungraded_blocks"],
            expected_frames=expected_frames,
        )
        if values["ungraded_blocks_source"] not in PARAMETER_SOURCES:
            raise AlgorithmConfigError("ungraded_blocks_source is not recognized")

        return cls(
            match_id=match_id,
            fps=fps,
            expected_frames=expected_frames,
            pitch_length_m=pitch_length,
            pitch_width_m=pitch_width,
            coordinate_representation=coordinate,
            team_mapping_source=team_source,
            ungraded_blocks=ungraded_blocks,
            optional_assets=dict(optional_assets),
            parameters=parameters,
        )


AlgorithmConfig = BaselineConfig | StateEngineConfig


def load_algorithm_config(path: str | os.PathLike[str]) -> AlgorithmConfig:
    config_path = Path(path)
    try:
        values = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AlgorithmConfigError(f"could not read configuration at {config_path}") from error
    if not isinstance(values, dict):
        raise AlgorithmConfigError("configuration root must be a JSON object")
    if values.get("schema_version") == "2.0":
        return StateEngineConfig.from_mapping(values)
    return BaselineConfig.from_mapping(values)


def _positive_integer(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise AlgorithmConfigError(f"{name} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise AlgorithmConfigError(f"{name} must be a positive integer") from error
    if parsed != value or parsed <= 0:
        raise AlgorithmConfigError(f"{name} must be a positive integer")
    return parsed


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise AlgorithmConfigError(f"{name} must be positive")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise AlgorithmConfigError(f"{name} must be positive") from error
    if parsed <= 0:
        raise AlgorithmConfigError(f"{name} must be positive")
    return parsed


def _parse_parameter(name: str, raw: Any) -> Parameter:
    if not isinstance(raw, dict):
        raise AlgorithmConfigError(f"parameter {name!r} must be an object")
    required = {"value", "unit", "source", "rationale"}
    if set(raw) != required:
        raise AlgorithmConfigError(f"parameter {name!r} must contain exactly {sorted(required)}")
    source = raw["source"]
    if source not in PARAMETER_SOURCES:
        raise AlgorithmConfigError(f"parameter {name!r} has unknown source {source!r}")
    if not isinstance(raw["unit"], str) or not raw["unit"]:
        raise AlgorithmConfigError(f"parameter {name!r} needs a non-empty unit")
    if not isinstance(raw["rationale"], str) or not raw["rationale"].strip():
        raise AlgorithmConfigError(f"parameter {name!r} needs a rationale")
    value = raw["value"]
    if not isinstance(value, (bool, int, float)):
        raise AlgorithmConfigError(f"parameter {name!r} has a non-scalar value")
    return Parameter(
        value=value,
        unit=raw["unit"],
        source=source,
        rationale=raw["rationale"].strip(),
    )


def _parse_ungraded_blocks(
    raw: Any,
    *,
    expected_frames: int,
) -> tuple[tuple[int, int], ...]:
    if not isinstance(raw, list):
        raise AlgorithmConfigError("ungraded_blocks must be a list")
    blocks: list[tuple[int, int]] = []
    previous_end = -1
    for item in raw:
        if not isinstance(item, list) or len(item) != 2:
            raise AlgorithmConfigError("each ungraded block must be [first_frame, last_frame]")
        try:
            first, last = int(item[0]), int(item[1])
        except (TypeError, ValueError) as error:
            raise AlgorithmConfigError("ungraded block frames must be integers") from error
        if first != item[0] or last != item[1]:
            raise AlgorithmConfigError("ungraded block frames must be integers")
        if first < 0 or last < first or last >= expected_frames:
            raise AlgorithmConfigError(f"invalid ungraded block: {item!r}")
        if first <= previous_end:
            raise AlgorithmConfigError("ungraded blocks must be sorted and non-overlapping")
        blocks.append((first, last))
        previous_end = last
    return tuple(blocks)


def _validate_parameter_types(parameters: Mapping[str, Parameter]) -> None:
    for name in BOOLEAN_PARAMETERS:
        if not isinstance(parameters[name].value, bool):
            raise AlgorithmConfigError(f"parameter {name!r} must be boolean")
    for name in INTEGER_PARAMETERS:
        value = parameters[name].value
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise AlgorithmConfigError(f"parameter {name!r} must be a positive integer")
    for name in NON_NEGATIVE_SECONDS_PARAMETERS:
        value = parameters[name].value
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise AlgorithmConfigError(f"parameter {name!r} must be a non-negative number")
    for name in POSITIVE_NUMBER_PARAMETERS:
        value = parameters[name].value
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise AlgorithmConfigError(f"parameter {name!r} must be positive")


BOOLEAN_PARAMETERS = frozenset(
    {
        "use_visible_team_vote",
        "use_ball_rest_dead_ball",
        "enable_restart_zone",
        "enable_reachability",
        "enable_smart_tagging",
        "enable_short_flicker_cleanup",
        "enable_minimum_segment_cleanup",
        "enable_isolated_dead_ball_cleanup",
    }
)
INTEGER_PARAMETERS = frozenset({"near_player_vote_k"})
NON_NEGATIVE_SECONDS_PARAMETERS = frozenset(
    {
        "ball_interpolation_max_s",
        "candidate_confirmation_s",
        "restart_confirmation_s",
        "dead_ball_confirmation_s",
        "ball_rest_min_s",
        "cleanup_short_flicker_max_s",
        "cleanup_minimum_segment_s",
        "cleanup_isolated_dead_ball_max_s",
    }
)
POSITIVE_NUMBER_PARAMETERS = frozenset(
    {
        "ball_rest_speed_mps",
        "restart_zone_radius_m",
        "reachability_extra_speed_mps",
    }
)
REQUIRED_PARAMETERS = (
    BOOLEAN_PARAMETERS
    | INTEGER_PARAMETERS
    | NON_NEGATIVE_SECONDS_PARAMETERS
    | POSITIVE_NUMBER_PARAMETERS
)
