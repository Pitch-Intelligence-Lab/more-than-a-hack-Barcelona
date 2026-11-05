"""Optional whole-interval structural cleanup, separate from state inference."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from mtah_possession.algorithm_config import StateEngineConfig
from mtah_possession.states.possession_state import duration_to_frames


@dataclass(frozen=True)
class CleanupResult:
    labels: NDArray[np.str_]
    changed: NDArray[np.bool_]
    applied_steps: tuple[str, ...]
    removed_label_counts: Mapping[str, int]


def apply_structural_cleanup(
    labels: NDArray[np.str_],
    config: StateEngineConfig,
    *,
    protected_mask: NDArray[np.bool_] | None = None,
) -> CleanupResult:
    if protected_mask is None:
        protected_mask = np.zeros(labels.shape, dtype=bool)
    if protected_mask.shape != labels.shape:
        raise ValueError("protected_mask must match labels shape")
    output = labels.copy()
    changed = np.zeros(labels.shape, dtype=bool)
    applied: list[str] = []

    if config.flag("enable_short_flicker_cleanup"):
        _absorb_flicker(
            output,
            changed,
            max_frames=duration_to_frames(
                config.number("cleanup_short_flicker_max_s"),
                config.fps,
            ),
            labels_to_absorb={"H", "A"},
            protected_mask=protected_mask,
        )
        applied.append("short_flicker_absorption")

    if config.flag("enable_minimum_segment_cleanup"):
        _absorb_flicker(
            output,
            changed,
            max_frames=max(
                0,
                duration_to_frames(config.number("cleanup_minimum_segment_s"), config.fps) - 1,
            ),
            labels_to_absorb={"H", "A"},
            protected_mask=protected_mask,
        )
        applied.append("minimum_segment_duration")

    if config.flag("enable_isolated_dead_ball_cleanup"):
        _absorb_flicker(
            output,
            changed,
            max_frames=duration_to_frames(
                config.number("cleanup_isolated_dead_ball_max_s"),
                config.fps,
            ),
            labels_to_absorb={"D"},
            protected_mask=protected_mask,
        )
        applied.append("isolated_dead_ball_removal")

    removed_label_counts = {
        label: int(np.sum((labels == label) & (output != label))) for label in ("H", "A", "D")
    }
    return CleanupResult(output, changed, tuple(applied), removed_label_counts)


def label_segments(labels: NDArray[np.str_]) -> list[tuple[int, int, str]]:
    """Return half-open ``(start, end, label)`` runs; X terminates a run."""

    if labels.ndim != 1:
        raise ValueError("labels must be one-dimensional")
    if labels.size == 0:
        return []
    segments: list[tuple[int, int, str]] = []
    start = 0
    current = str(labels[0])
    for frame in range(1, labels.size):
        value = str(labels[frame])
        if value != current:
            segments.append((start, frame, current))
            start = frame
            current = value
    segments.append((start, labels.size, current))
    return segments


def _absorb_flicker(
    output: NDArray[np.str_],
    changed: NDArray[np.bool_],
    *,
    max_frames: int,
    labels_to_absorb: set[str],
    protected_mask: NDArray[np.bool_],
) -> None:
    if max_frames <= 0:
        return
    segments = label_segments(output)
    for index in range(1, len(segments) - 1):
        start, end, value = segments[index]
        if value not in labels_to_absorb or end - start > max_frames:
            continue
        if protected_mask[start:end].any():
            continue
        previous = segments[index - 1][2]
        following = segments[index + 1][2]
        if previous == following and previous != "X":
            output[start:end] = previous
            changed[start:end] = True
