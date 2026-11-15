"""Frozen Phase-2 extractor schema and split boundaries."""

from __future__ import annotations

TASK_ID = "MTAH-PHASE2-FEATURE-EXTRACTOR-001"
OUTPUT_SCHEMA_VERSION = "P2-FS-0.1"
IDSSE_FPS = 25.0

FEATURE_COLUMNS = (
    "match_id",
    "frame_number",
    "timestamp_utc",
    "game_section",
    "home_team_id",
    "away_team_id",
    "home_tracked_n",
    "away_tracked_n",
    "ball_geometry_valid",
    "nearest_home_m",
    "nearest_away_m",
    "nearest_team_delta_m",
    "second_home_m",
    "second_away_m",
    "players_within_2m_home",
    "players_within_2m_away",
    "players_within_5m_home",
    "players_within_5m_away",
    "home_centroid_x",
    "home_centroid_y",
    "away_centroid_x",
    "away_centroid_y",
    "centroid_distance_m",
    "home_width_m",
    "away_width_m",
    "home_depth_m",
    "away_depth_m",
    "ball_home_centroid_delta_m",
)

REFERENCE_COLUMNS = (
    "match_id",
    "frame_number",
    "provider_alive",
    "provider_home_possession",
)

TRACKING_X_LIMIT_M = 54.5
TRACKING_Y_LIMIT_M = 36.0
TRACKING_COORDINATE_BOUNDS = (-54.5, 54.5, -36.0, 36.0)
EVENT_COORDINATE_BOUNDS = (0.0, 105.0, 0.0, 68.0)

DEVELOPMENT_MATCH_IDS = (
    "DFL-MAT-J03WMX",
    "DFL-MAT-J03WOH",
    "DFL-MAT-J03WOY",
    "DFL-MAT-J03WPY",
    "DFL-MAT-J03WQQ",
)
OPERATIONAL_LOCKBOX_MATCH_IDS = (
    "DFL-MAT-J03WN1",
    "DFL-MAT-J03WR9",
)
ALL_MATCH_IDS = DEVELOPMENT_MATCH_IDS + OPERATIONAL_LOCKBOX_MATCH_IDS
