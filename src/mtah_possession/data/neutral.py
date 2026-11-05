"""Provider-neutral tracking, possession proxy and phase representation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

import numpy as np
from numpy.typing import NDArray

from mtah_possession.data.tracking import FrameAlignment, TrackingData


class TeamSide(IntEnum):
    HOME = 0
    AWAY = 1
    UNKNOWN = -1


@dataclass(frozen=True)
class PeriodSpan:
    period: int
    start_frame: int
    end_frame: int


@dataclass(frozen=True)
class PhaseSpan:
    start_frame: int
    end_frame: int
    period: int
    kind: str
    team: TeamSide = TeamSide.UNKNOWN
    restart: bool = False
    dead_ball: bool = False
    source: str = "phase"


@dataclass(frozen=True)
class NeutralMatch:
    match_id: str
    fps: int
    frame_count: int
    pitch_length_m: float
    pitch_width_m: float
    coordinate_convention: str
    home_team_id: int
    away_team_id: int
    home_team_name: str
    away_team_name: str
    player_ids: tuple[int, ...]
    team_by_slot: NDArray[np.int8]
    slot_positions: NDArray[np.float32]
    slot_detected: NDArray[np.bool_]
    ball_positions: NDArray[np.float32]
    ball_detected: NDArray[np.bool_]
    frame_present: NDArray[np.bool_]
    possession_side: NDArray[np.int8]
    possession_status: NDArray[np.int8]
    periods: tuple[PeriodSpan, ...]
    phases: tuple[PhaseSpan, ...]
    source_checksums: dict[str, str]
    source_metadata: dict[str, Any]

    @property
    def slot_count(self) -> int:
        return len(self.player_ids)

    def period_for_frame(self, frame: int) -> int | None:
        for period in self.periods:
            if period.start_frame <= frame < period.end_frame:
                return period.period
        return None

    def in_period_mask(self) -> NDArray[np.bool_]:
        output = np.zeros(self.frame_count, dtype=bool)
        for period in self.periods:
            output[period.start_frame : period.end_frame] = True
        return output


@dataclass(frozen=True)
class ProxyTarget:
    labels: NDArray[np.str_]
    sources: NDArray[np.str_]
    counts: dict[str, int]
    source_counts: dict[str, int]


def map_proxy_target(match: NeutralMatch) -> ProxyTarget:
    """Map neutral possession and phases to an explicit diagnostic proxy."""
    labels = np.full(match.frame_count, "X", dtype="<U1")
    sources = np.full(match.frame_count, "unknown", dtype="<U32")
    in_period = match.in_period_mask()
    phase_present = np.zeros(match.frame_count, dtype=bool)
    for phase in match.phases:
        phase_present[phase.start_frame : phase.end_frame] = True

    home = match.possession_side == TeamSide.HOME
    away = match.possession_side == TeamSide.AWAY
    labels[home] = "H"
    sources[home] = "possession_group_home"
    labels[away] = "A"
    sources[away] = "possession_group_away"

    missing_row = ~match.frame_present
    labels[missing_row] = "X"
    sources[missing_row] = "missing_tracking_frame"

    outside_period = ~in_period & match.frame_present
    labels[outside_period] = "X"
    sources[outside_period] = "outside_declared_period"

    unrecognized = match.frame_present & (match.possession_status == 2)
    labels[unrecognized] = "X"
    sources[unrecognized] = "unrecognized_possession_group"

    no_possession = match.frame_present & in_period & (match.possession_status == 1)
    no_possession_in_phase = no_possession & phase_present
    labels[no_possession_in_phase] = "X"
    sources[no_possession_in_phase] = "missing_possession_inside_phase"

    dead = no_possession & ~phase_present
    labels[dead] = "D"
    sources[dead] = "no_possession_and_no_phase"

    values, counts = np.unique(labels, return_counts=True)
    source_values, source_counts = np.unique(sources, return_counts=True)
    return ProxyTarget(
        labels=labels,
        sources=sources,
        counts={str(value): int(count) for value, count in zip(values, counts, strict=True)},
        source_counts={
            str(value): int(count)
            for value, count in zip(source_values, source_counts, strict=True)
        },
    )


def neutral_to_tracking(match: NeutralMatch) -> TrackingData:
    """Convert provider-neutral metres to the engine's normalised corner origin."""
    if match.coordinate_convention != "metres-center-origin":
        raise ValueError(f"unsupported coordinate convention: {match.coordinate_convention}")
    slot_positions = match.slot_positions.astype(np.float64, copy=True)
    slot_positions[~match.slot_detected] = np.nan
    slot_positions[..., 0] = slot_positions[..., 0] / match.pitch_length_m + 0.5
    slot_positions[..., 1] = slot_positions[..., 1] / match.pitch_width_m + 0.5

    ball_positions = match.ball_positions.astype(np.float64, copy=True)
    ball_positions[~match.ball_detected] = np.nan
    ball_positions[..., 0] = ball_positions[..., 0] / match.pitch_length_m + 0.5
    ball_positions[..., 1] = ball_positions[..., 1] / match.pitch_width_m + 0.5

    speeds = np.full(match.slot_positions.shape[:2], np.nan, dtype=np.float32)
    if match.frame_count > 1:
        delta = match.slot_positions[1:].astype(np.float64) - match.slot_positions[:-1].astype(
            np.float64
        )
        valid = match.slot_detected[1:] & match.slot_detected[:-1] & np.isfinite(delta).all(axis=2)
        speed_values = np.sqrt(np.square(delta).sum(axis=2)) * match.fps
        speeds[1:][valid] = speed_values[valid]

    return TrackingData(
        frame_count=match.frame_count,
        home_team=match.home_team_name,
        away_team=match.away_team_name,
        team_by_slot=match.team_by_slot.copy(),
        ball_positions=ball_positions.astype(np.float32),
        slot_positions=slot_positions.astype(np.float32),
        alignment=FrameAlignment(match.frame_count, 1, match.frame_count, True),
        slot_speeds=speeds,
    )


def blocks_from_mask(mask: NDArray[np.bool_]) -> tuple[tuple[int, int], ...]:
    """Convert a boolean frame mask to sorted inclusive half-open block pairs."""
    if mask.ndim != 1:
        raise ValueError("mask must be one-dimensional")
    padded = np.concatenate(([False], mask.astype(bool), [False]))
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    return tuple(
        (int(start), int(end - 1)) for start, end in zip(changes[::2], changes[1::2], strict=True)
    )
