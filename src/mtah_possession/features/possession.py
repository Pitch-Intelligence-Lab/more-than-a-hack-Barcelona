"""Temporal majority-vote smoothing for nearest-player candidates."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from mtah_possession.features.ball import AWAY, HOME


def majority_vote_labels(
    candidates: NDArray[np.int8],
    *,
    window_half_width_frames: int,
) -> NDArray[np.str_]:
    """Return H/A/D labels over a centred majority-vote window.

    Missing candidates do not vote. A frame with no votes, or an exact H/A
    tie, is labelled D. No label is chosen using this match's ground truth.
    """

    if candidates.ndim != 1:
        raise ValueError("candidates must be a one-dimensional array")
    if window_half_width_frames < 0:
        raise ValueError("window_half_width_frames must be non-negative")
    if not np.isin(candidates, (HOME, AWAY, -1)).all():
        raise ValueError("candidates must contain only 0, 1, or -1")

    if window_half_width_frames == 0:
        labels = np.full(candidates.shape, "D", dtype="<U1")
        labels[candidates == HOME] = "H"
        labels[candidates == AWAY] = "A"
        return labels

    home_prefix = np.concatenate(([0], np.cumsum(candidates == HOME, dtype=np.int64)))
    away_prefix = np.concatenate(([0], np.cumsum(candidates == AWAY, dtype=np.int64)))
    indices = np.arange(candidates.size)
    low = np.maximum(0, indices - window_half_width_frames)
    high = np.minimum(candidates.size, indices + window_half_width_frames + 1)
    home_votes = home_prefix[high] - home_prefix[low]
    away_votes = away_prefix[high] - away_prefix[low]

    labels = np.full(candidates.shape, "D", dtype="<U1")
    labels[home_votes > away_votes] = "H"
    labels[away_votes > home_votes] = "A"
    return labels
