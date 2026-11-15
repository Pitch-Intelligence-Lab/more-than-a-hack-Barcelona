"""Home/away-safe coordinate and feature helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from mtah_possession.research.phase2.constants import (
    TRACKING_X_LIMIT_M,
    TRACKING_Y_LIMIT_M,
)

Point = tuple[float, float]


def euclidean_distance(first: Point, second: Point) -> float:
    return math.hypot(first[0] - second[0], first[1] - second[1])


def is_valid_ball_geometry(ball: Point) -> bool:
    return (
        -TRACKING_X_LIMIT_M <= ball[0] <= TRACKING_X_LIMIT_M
        and -TRACKING_Y_LIMIT_M <= ball[1] <= TRACKING_Y_LIMIT_M
    )


def event_xy_to_centered(
    x: float,
    y: float,
    *,
    pitch_length_m: float = 105.0,
    pitch_width_m: float = 68.0,
) -> Point:
    """Convert event 0..pitch coordinates to the centre-origin pitch frame."""

    return x - pitch_length_m / 2.0, y - pitch_width_m / 2.0


def _swap_side_value(name: str, value: Any) -> Any:
    if value is None:
        return None
    if name == "nearest_team_delta_m" or name == "ball_home_centroid_delta_m":
        return -float(value)
    return value


def swap_feature_sides(features: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact home/away counterpart of one feature row."""

    swapped = dict(features)
    pairs = (
        ("home_team_id", "away_team_id"),
        ("home_tracked_n", "away_tracked_n"),
        ("nearest_home_m", "nearest_away_m"),
        ("second_home_m", "second_away_m"),
        ("players_within_2m_home", "players_within_2m_away"),
        ("players_within_5m_home", "players_within_5m_away"),
        ("home_centroid_x", "away_centroid_x"),
        ("home_centroid_y", "away_centroid_y"),
        ("home_width_m", "away_width_m"),
        ("home_depth_m", "away_depth_m"),
    )
    for home_name, away_name in pairs:
        if home_name not in features and away_name not in features:
            continue
        swapped[home_name] = _swap_side_value(home_name, features.get(away_name))
        swapped[away_name] = _swap_side_value(away_name, features.get(home_name))
    if "nearest_team_delta_m" in features and features["nearest_team_delta_m"] is not None:
        swapped["nearest_team_delta_m"] = -float(features["nearest_team_delta_m"])
    if (
        "ball_home_centroid_delta_m" in features
        and features["ball_home_centroid_delta_m"] is not None
    ):
        swapped["ball_home_centroid_delta_m"] = -float(features["ball_home_centroid_delta_m"])
    return swapped
