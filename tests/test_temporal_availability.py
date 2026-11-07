import pytest

from mtah_possession.governance.policy import PolicyError
from mtah_possession.governance.temporal import (
    TemporalFieldPolicy,
    TemporalStatus,
    convert_interval,
    phase_gap_target,
    require_available,
)


def test_current_field_is_available_only_after_available_at() -> None:
    field = TemporalFieldPolicy(
        field_name="ball_x",
        event_time=1.0,
        interval_start=1.0,
        interval_end=2.0,
        available_at=1.0,
        availability_source="frame clock",
    )
    assert field.status == TemporalStatus.PASS
    assert not field.available_for(0.9)
    assert field.available_for(1.0)
    require_available(field, 1.0)


def test_future_result_and_endpoint_fail() -> None:
    field = TemporalFieldPolicy(
        field_name="event_end_x",
        event_time=1.0,
        interval_start=1.0,
        interval_end=5.0,
        available_at=4.0,
        availability_source="event export",
    )
    assert field.status == TemporalStatus.FAIL
    with pytest.raises(PolicyError, match="unavailable"):
        require_available(field, 2.0)


def test_future_field_without_interval_end_is_hold() -> None:
    field = TemporalFieldPolicy(
        field_name="event_end_x",
        event_time=1.0,
        interval_start=1.0,
        interval_end=None,
        available_at=1.0,
        availability_source="event export",
    )
    assert field.status == TemporalStatus.HOLD
    with pytest.raises(PolicyError, match="HOLD"):
        require_available(field, 1.0)


def test_missing_available_at_is_hold() -> None:
    field = TemporalFieldPolicy(
        field_name="ball_x",
        event_time=1.0,
        interval_start=1.0,
        interval_end=2.0,
        available_at=None,
        availability_source="missing",
    )
    assert field.status == TemporalStatus.HOLD
    with pytest.raises(PolicyError, match="HOLD"):
        require_available(field, 2.0)


def test_phase_conversion_preserves_seconds_and_gap_has_no_label() -> None:
    converted_10 = convert_interval(0, 30, source_fps=10, target_fps=25)
    converted_25 = convert_interval(0, 75, source_fps=25, target_fps=10)
    assert converted_10 == (0, 75)
    assert converted_25 == (0, 30)
    assert phase_gap_target(20) is None
