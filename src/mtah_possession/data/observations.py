"""Quality-aware ball observation preparation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from numpy.typing import NDArray

from mtah_possession.data.tracking import TrackingData


class BallQuality(IntEnum):
    OBSERVED = 0
    INTERPOLATED = 1
    MISSING = 2


@dataclass(frozen=True)
class BallObservations:
    positions: NDArray[np.float32]
    quality: NDArray[np.int8]
    observed_mask: NDArray[np.bool_]

    @property
    def interpolated_mask(self) -> NDArray[np.bool_]:
        return self.quality == BallQuality.INTERPOLATED

    @property
    def missing_mask(self) -> NDArray[np.bool_]:
        return self.quality == BallQuality.MISSING

    @property
    def usable_mask(self) -> NDArray[np.bool_]:
        return self.quality != BallQuality.MISSING

    def counts(self) -> dict[str, int]:
        return {
            "observed": int(np.sum(self.quality == BallQuality.OBSERVED)),
            "interpolated": int(np.sum(self.quality == BallQuality.INTERPOLATED)),
            "missing": int(np.sum(self.quality == BallQuality.MISSING)),
        }


def prepare_ball_observations(
    tracking: TrackingData,
    *,
    fps: int,
    max_interpolation_gap_s: float,
) -> BallObservations:
    """Mark observations and linearly fill only short, internally bracketed gaps."""

    if fps <= 0:
        raise ValueError("fps must be positive")
    if max_interpolation_gap_s < 0:
        raise ValueError("max_interpolation_gap_s must be non-negative")
    if tracking.ball_positions.ndim != 2 or tracking.ball_positions.shape[1] != 2:
        raise ValueError("ball_positions must have shape (frames, 2)")

    positions = tracking.ball_positions.astype(np.float64, copy=True)
    observed = np.isfinite(positions).all(axis=1)
    quality = np.full(tracking.frame_count, BallQuality.MISSING, dtype=np.int8)
    quality[observed] = BallQuality.OBSERVED

    max_gap_frames = int(round(max_interpolation_gap_s * fps))
    observed_frames = np.flatnonzero(observed)
    if max_gap_frames > 0 and observed_frames.size >= 2:
        for left, right in zip(observed_frames[:-1], observed_frames[1:], strict=True):
            gap = int(right - left - 1)
            if gap <= 0 or gap > max_gap_frames:
                continue
            alpha = np.arange(1, gap + 1, dtype=np.float64) / float(gap + 1)
            positions[left + 1 : right] = (
                positions[left][None, :] * (1.0 - alpha[:, None])
                + positions[right][None, :] * alpha[:, None]
            )
            quality[left + 1 : right] = BallQuality.INTERPOLATED

    return BallObservations(
        positions=positions.astype(np.float32),
        quality=quality,
        observed_mask=observed,
    )
