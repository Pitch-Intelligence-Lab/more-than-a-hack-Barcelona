"""Local player-pressure evidence around the ball."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from mtah_possession.data.tracking import TrackingData
from mtah_possession.features.ball import AWAY, HOME


@dataclass(frozen=True)
class PressureEvidence:
    home_count_5m: NDArray[np.int16]
    away_count_5m: NDArray[np.int16]
    advantage_5m: NDArray[np.float64]
    valid: NDArray[np.bool_]


def compute_pressure(
    tracking: TrackingData,
    ball_positions: NDArray[np.float32],
    usable_ball: NDArray[np.bool_],
    *,
    pitch_length_m: float,
    pitch_width_m: float,
    radius_m: float = 5.0,
) -> PressureEvidence:
    count = tracking.frame_count
    home_count = np.zeros(count, dtype=np.int16)
    away_count = np.zeros(count, dtype=np.int16)
    deltas = tracking.slot_positions.astype(np.float64) - ball_positions[:, None, :].astype(
        np.float64
    )
    deltas[..., 0] *= pitch_length_m
    deltas[..., 1] *= pitch_width_m
    distances = np.sqrt(np.square(deltas).sum(axis=2))
    visible = np.isfinite(distances)
    near = visible & (distances <= radius_m) & usable_ball[:, None]
    home_slots = tracking.team_by_slot == HOME
    away_slots = tracking.team_by_slot == AWAY
    home_count[:] = near[:, home_slots].sum(axis=1)
    away_count[:] = near[:, away_slots].sum(axis=1)
    valid = usable_ball & np.isfinite(ball_positions).all(axis=1)
    advantage = (home_count.astype(np.float64) - away_count) * valid
    return PressureEvidence(home_count, away_count, advantage, valid)
