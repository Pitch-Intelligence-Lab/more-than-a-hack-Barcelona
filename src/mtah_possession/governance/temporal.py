"""Temporal availability checks for event-derived model fields."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mtah_possession.governance.policy import PolicyError


class TemporalStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    FAIL = "FAIL"


FUTURE_ONLY_FIELD_FRAGMENTS = (
    "end_x",
    "end_y",
    "event_result",
    "reception_result",
    "lead_to_goal",
    "lead_to_shot",
)


@dataclass(frozen=True)
class TemporalFieldPolicy:
    field_name: str
    event_time: float | None
    interval_start: float | None
    interval_end: float | None
    available_at: float | None
    availability_source: str

    @property
    def status(self) -> TemporalStatus:
        if not self.availability_source.strip() or self.available_at is None:
            return TemporalStatus.HOLD
        if any(
            fragment in self.field_name.lower() for fragment in FUTURE_ONLY_FIELD_FRAGMENTS
        ) and self.available_at < (self.interval_end or self.event_time or float("inf")):
            return TemporalStatus.FAIL
        return TemporalStatus.PASS

    def available_for(self, current_time: float) -> bool:
        if self.status != TemporalStatus.PASS or self.available_at is None:
            return False
        return self.available_at <= current_time


def require_available(field: TemporalFieldPolicy, current_time: float) -> None:
    if field.status == TemporalStatus.HOLD:
        raise PolicyError(f"temporal availability is HOLD for {field.field_name}")
    if not field.available_for(current_time):
        raise PolicyError(f"future field {field.field_name} is unavailable at {current_time}")


def convert_interval(
    first_frame: int,
    end_frame: int,
    *,
    source_fps: int,
    target_fps: int,
) -> tuple[int, int]:
    if first_frame < 0 or end_frame <= first_frame:
        raise ValueError("invalid source interval")
    if source_fps <= 0 or target_fps <= 0:
        raise ValueError("fps values must be positive")
    first_seconds = first_frame / source_fps
    end_seconds = end_frame / source_fps
    converted = (round(first_seconds * target_fps), round(end_seconds * target_fps))
    if abs((converted[1] - converted[0]) / target_fps - (end_seconds - first_seconds)) > (
        1.0 / target_fps
    ):
        raise PolicyError("frame conversion changed duration semantics")
    return converted


def phase_gap_target(gap_frames: int) -> None:
    """A phase gap has no automatic target label."""
    if gap_frames < 0:
        raise ValueError("gap_frames must be non-negative")
    return None
