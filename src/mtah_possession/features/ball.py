"""Nearest-player team candidates in metric pitch coordinates."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from mtah_possession.data.tracking import TrackingData

NO_CANDIDATE = -1
HOME = 0
AWAY = 1
_DISTANCE_TOLERANCE_M2 = 1e-6


def nearest_team_candidates(
    tracking: TrackingData,
    *,
    pitch_length_m: float,
    pitch_width_m: float,
) -> NDArray[np.int8]:
    """Return H/A/NO_CANDIDATE for every frame.

    Normalised ATD coordinates are converted to metres before distance is
    computed. If the closest home and away players are tied, the algorithm
    returns ``NO_CANDIDATE`` rather than applying an order-dependent tie-break.
    """

    if pitch_length_m <= 0 or pitch_width_m <= 0:
        raise ValueError("pitch dimensions must be positive")

    candidates = np.full(tracking.frame_count, NO_CANDIDATE, dtype=np.int8)
    ball_visible = tracking.ball_visible
    if not ball_visible.any():
        return candidates

    deltas = tracking.slot_positions[ball_visible].astype(np.float64) - tracking.ball_positions[
        ball_visible, None, :
    ].astype(np.float64)
    deltas[..., 0] *= pitch_length_m
    deltas[..., 1] *= pitch_width_m
    distances_sq = np.square(deltas, dtype=np.float64).sum(axis=2)

    home_mask = tracking.team_by_slot == HOME
    away_mask = tracking.team_by_slot == AWAY
    home_distances = distances_sq[:, home_mask]
    away_distances = distances_sq[:, away_mask]
    home_min = (
        np.min(np.where(np.isfinite(home_distances), home_distances, np.inf), axis=1)
        if home_distances.shape[1]
        else np.full(int(ball_visible.sum()), np.inf)
    )
    away_min = (
        np.min(np.where(np.isfinite(away_distances), away_distances, np.inf), axis=1)
        if away_distances.shape[1]
        else np.full(int(ball_visible.sum()), np.inf)
    )

    frame_codes = np.full(int(ball_visible.sum()), NO_CANDIDATE, dtype=np.int8)
    both_visible = np.isfinite(home_min) & np.isfinite(away_min)
    distance_gap = np.full(both_visible.shape, np.inf)
    np.subtract(home_min, away_min, out=distance_gap, where=both_visible)
    home_closer = both_visible & (distance_gap < -_DISTANCE_TOLERANCE_M2)
    away_closer = both_visible & (distance_gap > _DISTANCE_TOLERANCE_M2)
    frame_codes[home_closer] = HOME
    frame_codes[away_closer] = AWAY
    candidates[ball_visible] = frame_codes
    return candidates
