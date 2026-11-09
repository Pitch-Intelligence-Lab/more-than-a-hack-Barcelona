"""Relative-distance and time-to-ball evidence for Candidate B."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from mtah_possession.data.tracking import TrackingData
from mtah_possession.features.ball import AWAY, HOME


@dataclass(frozen=True)
class TimeToBall:
    home_time_s: NDArray[np.float64]
    away_time_s: NDArray[np.float64]
    advantage_s: NDArray[np.float64]
    valid: NDArray[np.bool_]


def _velocity(
    positions: NDArray[np.float32 | np.float64],
    *,
    fps: int,
    pitch_length_m: float,
    pitch_width_m: float,
) -> NDArray[np.float64]:
    values = positions.astype(np.float64, copy=True)
    velocity = np.full_like(values, np.nan, dtype=np.float64)
    if values.shape[0] < 2:
        return velocity
    delta = np.diff(values, axis=0)
    delta[..., 0] *= pitch_length_m
    delta[..., 1] *= pitch_width_m
    valid = np.isfinite(delta).all(axis=-1)
    velocity[1:][valid] = delta[valid] * fps
    return velocity


def compute_time_to_ball(
    tracking: TrackingData,
    ball_positions: NDArray[np.float32],
    usable_ball: NDArray[np.bool_],
    *,
    fps: int,
    pitch_length_m: float,
    pitch_width_m: float,
    min_closing_speed_mps: float,
    max_time_s: float,
) -> TimeToBall:
    count = tracking.frame_count
    home_time = np.full(count, np.nan, dtype=np.float64)
    away_time = np.full(count, np.nan, dtype=np.float64)
    if count == 0:
        return TimeToBall(home_time, away_time, home_time.copy(), np.zeros(0, dtype=bool))

    positions = tracking.slot_positions.astype(np.float64, copy=False)
    player_velocity = _velocity(
        positions,
        fps=fps,
        pitch_length_m=pitch_length_m,
        pitch_width_m=pitch_width_m,
    )
    ball_velocity = _velocity(
        ball_positions,
        fps=fps,
        pitch_length_m=pitch_length_m,
        pitch_width_m=pitch_width_m,
    )
    deltas = positions - ball_positions[:, None, :].astype(np.float64)
    deltas[..., 0] *= pitch_length_m
    deltas[..., 1] *= pitch_width_m
    distances = np.sqrt(np.square(deltas).sum(axis=2))
    distances[~np.isfinite(distances)] = np.inf
    distances[~usable_ball] = np.inf

    for team, output in ((HOME, home_time), (AWAY, away_time)):
        team_slots = np.flatnonzero(tracking.team_by_slot == team)
        if team_slots.size == 0:
            continue
        team_distances = distances[:, team_slots]
        nearest_offset = np.argmin(team_distances, axis=1)
        nearest_slot = team_slots[nearest_offset]
        frames = np.arange(count)
        nearest_distance = team_distances[frames, nearest_offset]
        player_delta = ball_positions.astype(np.float64) - positions[frames, nearest_slot]
        player_delta[:, 0] *= pitch_length_m
        player_delta[:, 1] *= pitch_width_m
        player_velocity_to_ball = player_velocity[frames, nearest_slot]
        ball_velocity_now = ball_velocity[frames]
        relative_velocity = player_velocity_to_ball - ball_velocity_now
        with np.errstate(divide="ignore", invalid="ignore"):
            closing_speed = np.sum(relative_velocity * player_delta, axis=1) / nearest_distance
        time = np.where(
            np.isfinite(closing_speed) & (closing_speed >= min_closing_speed_mps),
            nearest_distance / np.maximum(closing_speed, min_closing_speed_mps),
            max_time_s,
        )
        invalid = ~np.isfinite(nearest_distance) | ~np.isfinite(closing_speed)
        time[invalid] = np.nan
        output[:] = time

    valid = np.isfinite(home_time) & np.isfinite(away_time)
    advantage = away_time - home_time
    return TimeToBall(home_time, away_time, advantage, valid)
