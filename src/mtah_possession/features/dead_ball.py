"""Candidate-A dead-ball evidence: out of play and team motion.

These signals are independent of the frozen DP-005 ball-rest trigger. They are opt-in through
candidate configuration and must not change the frozen state-engine defaults.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def out_of_play_evidence(
    positions: NDArray[np.float32],
    usable: NDArray[np.bool_],
    *,
    pitch_length_m: float,
    pitch_width_m: float,
    margin_m: float,
) -> NDArray[np.bool_]:
    """Ball centre beyond the touchline/goal line by a metric margin.

    Coordinates are normalised to ``0..1``; the margin is converted per axis so a 0.3 m
    allowance means the same physical distance on both axes.
    """
    if pitch_length_m <= 0 or pitch_width_m <= 0:
        raise ValueError("pitch dimensions must be positive")
    if margin_m < 0:
        raise ValueError("margin_m must be non-negative")
    if positions.ndim != 2 or positions.shape[1] != 2:
        raise ValueError("positions must have shape (frames, 2)")

    flags = np.zeros(positions.shape[0], dtype=bool)
    if positions.size == 0 or not usable.any():
        return flags

    margin_x = margin_m / pitch_length_m
    margin_y = margin_m / pitch_width_m
    x = positions[:, 0].astype(np.float64)
    y = positions[:, 1].astype(np.float64)
    outside = (x < -margin_x) | (x > 1.0 + margin_x) | (y < -margin_y) | (y > 1.0 + margin_y)
    flags[usable] = outside[usable]
    return flags


def team_motion_evidence(
    slot_speeds: NDArray[np.float32] | None,
    *,
    frame_count: int | None = None,
) -> NDArray[np.float64]:
    """Mean tracked speed of every visible slot, per frame.

    NaN slots are excluded from the mean; a frame with no finite speed returns NaN rather than
    inventing a value.
    """
    if slot_speeds is None:
        count = 0 if frame_count is None else frame_count
        return np.full(count, np.nan, dtype=np.float64)

    speeds = np.asarray(slot_speeds, dtype=np.float64)
    if speeds.ndim != 2:
        raise ValueError("slot_speeds must have shape (frames, slots)")
    finite = np.isfinite(speeds)
    counts = finite.sum(axis=1)
    motion = np.full(speeds.shape[0], np.nan, dtype=np.float64)
    rows = counts > 0
    if rows.any():
        motion[rows] = np.where(finite, speeds, 0.0)[rows].sum(axis=1) / counts[rows]
    return motion
