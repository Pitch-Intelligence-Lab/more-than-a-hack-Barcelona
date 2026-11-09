"""Per-slot tracking anomaly detection and optional filtering."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray

from mtah_possession.data.tracking import TrackingData


@dataclass(frozen=True)
class TrackingQuality:
    tracking: TrackingData
    anomaly_slots: NDArray[np.bool_]
    anomaly_frames: NDArray[np.bool_]


def filter_tracking_anomalies(
    tracking: TrackingData,
    *,
    fps: int,
    pitch_length_m: float,
    pitch_width_m: float,
    speed_threshold_mps: float,
    accel_threshold_mps2: float,
    enabled: bool,
) -> TrackingQuality:
    positions = tracking.slot_positions.astype(np.float64, copy=True)
    count, slots, _ = positions.shape
    anomaly = np.zeros((count, slots), dtype=bool)
    if enabled and count >= 2:
        delta = np.diff(positions, axis=0)
        delta[..., 0] *= pitch_length_m
        delta[..., 1] *= pitch_width_m
        valid = np.isfinite(delta).all(axis=2)
        speed = np.full((count - 1, slots), np.nan, dtype=np.float64)
        speed[valid] = np.sqrt(np.square(delta).sum(axis=2))[valid] * fps
        anomaly[1:] |= np.isfinite(speed) & (speed > speed_threshold_mps)
        if count >= 3:
            accel = np.abs(np.diff(speed, axis=0)) * fps
            valid_accel = np.isfinite(accel)
            anomaly[2:] |= valid_accel & (accel > accel_threshold_mps2)
    filtered = positions.copy()
    filtered[anomaly] = np.nan
    return TrackingQuality(
        tracking=replace(tracking, slot_positions=filtered.astype(np.float32)),
        anomaly_slots=anomaly,
        anomaly_frames=anomaly.any(axis=1),
    )
