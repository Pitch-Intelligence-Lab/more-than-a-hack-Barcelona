"""Aggregate-only output health reporting."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from mtah_possession.data.observations import BallObservations, BallQuality
from mtah_possession.states.cleanup import label_segments
from mtah_possession.validation.submission import ValidationReport


@dataclass(frozen=True)
class HealthReport:
    input_sha256: Mapping[str, str]
    output_sha256: str
    rows: int
    frame_range: tuple[int, int]
    label_counts: Mapping[str, int]
    segments_by_label: Mapping[str, int]
    segment_duration_s: Mapping[str, Mapping[str, float | int]]
    observation_quality_counts: Mapping[str, int]
    graded_observation_quality_counts: Mapping[str, int]
    transition_counts: Mapping[str, int]
    reason_counts: Mapping[str, int]
    validator_status: str
    cleanup_steps: tuple[str, ...]
    cleanup_removed_label_counts: Mapping[str, int]
    forced_dead_frames: int
    forced_dead_label_counts: Mapping[str, int]
    forced_dead_all_d: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_sha256": dict(self.input_sha256),
            "output_sha256": self.output_sha256,
            "rows": self.rows,
            "frame_range": list(self.frame_range),
            "label_counts": dict(self.label_counts),
            "segments_by_label": dict(self.segments_by_label),
            "segment_duration_s": {
                label: dict(summary) for label, summary in self.segment_duration_s.items()
            },
            "observation_quality_counts": dict(self.observation_quality_counts),
            "graded_observation_quality_counts": dict(self.graded_observation_quality_counts),
            "transition_counts": dict(self.transition_counts),
            "reason_counts": dict(self.reason_counts),
            "validator_status": self.validator_status,
            "cleanup_steps": list(self.cleanup_steps),
            "cleanup_removed_label_counts": dict(self.cleanup_removed_label_counts),
            "forced_dead_frames": self.forced_dead_frames,
            "forced_dead_label_counts": dict(self.forced_dead_label_counts),
            "forced_dead_all_d": self.forced_dead_all_d,
        }


def build_health_report(
    *,
    labels: NDArray[np.str_],
    observations: BallObservations,
    reasons: NDArray[np.str_],
    validation: ValidationReport,
    input_sha256: Mapping[str, str],
    fps: int,
    cleanup_steps: tuple[str, ...] = (),
    cleanup_removed_label_counts: Mapping[str, int] | None = None,
    forced_dead_mask: NDArray[np.bool_] | None = None,
) -> HealthReport:
    if fps <= 0:
        raise ValueError("fps must be positive")
    segments = label_segments(labels)
    by_label: dict[str, list[int]] = {"H": [], "A": [], "D": []}
    for start, end, value in segments:
        if value in by_label:
            by_label[value].append(end - start)

    duration_summary: dict[str, dict[str, float | int]] = {}
    all_durations: list[int] = []
    for label, durations in by_label.items():
        all_durations.extend(durations)
        duration_summary[label] = _duration_stats(durations, fps)
    duration_summary["overall"] = _duration_stats(all_durations, fps)

    ungraded = labels == "X"
    graded_quality = observations.quality[~ungraded]
    graded_counts = {
        "observed": int(np.sum(graded_quality == BallQuality.OBSERVED)),
        "interpolated": int(np.sum(graded_quality == BallQuality.INTERPOLATED)),
        "missing": int(np.sum(graded_quality == BallQuality.MISSING)),
    }
    reason_values, reason_counts = np.unique(reasons, return_counts=True)
    if forced_dead_mask is None:
        forced_dead_mask = np.zeros(labels.shape, dtype=bool)
    if forced_dead_mask.shape != labels.shape:
        raise ValueError("forced_dead_mask must match labels shape")
    forced_labels = labels[forced_dead_mask]
    forced_dead_label_counts = {
        label: int(np.sum(forced_labels == label)) for label in ("H", "A", "D", "X")
    }
    return HealthReport(
        input_sha256=dict(input_sha256),
        output_sha256=validation.sha256,
        rows=validation.rows,
        frame_range=(0, validation.rows - 1),
        label_counts=dict(validation.label_counts),
        segments_by_label={label: len(values) for label, values in by_label.items()},
        segment_duration_s=duration_summary,
        observation_quality_counts=observations.counts(),
        graded_observation_quality_counts=graded_counts,
        transition_counts=transition_counts(labels),
        reason_counts={
            str(value): int(count)
            for value, count in zip(reason_values, reason_counts, strict=True)
        },
        validator_status="pass",
        cleanup_steps=cleanup_steps,
        cleanup_removed_label_counts=dict(cleanup_removed_label_counts or {}),
        forced_dead_frames=int(forced_dead_mask.sum()),
        forced_dead_label_counts=forced_dead_label_counts,
        forced_dead_all_d=bool(forced_dead_mask.any() and np.all(forced_labels == "D")),
    )


def transition_counts(labels: NDArray[np.str_]) -> dict[str, int]:
    output: dict[str, int] = {}
    previous: str | None = None
    for value in labels:
        label = str(value)
        if label == "X":
            previous = None
            continue
        if previous is not None and previous != label:
            key = f"{previous}->{label}"
            output[key] = output.get(key, 0) + 1
        previous = label
    return output


def write_health_report(
    path: str | os.PathLike[str],
    report: HealthReport,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(report.to_dict(), handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return destination


def _duration_stats(durations: list[int], fps: int) -> dict[str, float | int]:
    if not durations:
        return {"count": 0, "mean_s": 0.0, "shortest_s": 0.0, "longest_s": 0.0}
    seconds = np.asarray(durations, dtype=np.float64) / float(fps)
    return {
        "count": len(durations),
        "mean_s": round(float(seconds.mean()), 3),
        "shortest_s": round(float(seconds.min()), 3),
        "longest_s": round(float(seconds.max()), 3),
    }
