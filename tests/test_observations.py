import numpy as np

from mtah_possession.data.observations import (
    BallQuality,
    prepare_ball_observations,
)
from mtah_possession.data.tracking import FrameAlignment, TrackingData


def tracking(ball: list[list[float] | None]) -> TrackingData:
    positions = np.asarray(
        [[np.nan, np.nan] if point is None else point for point in ball],
        dtype=np.float32,
    )
    count = len(ball)
    slots = np.full((count, 2, 2), np.nan, dtype=np.float32)
    return TrackingData(
        frame_count=count,
        home_team="H",
        away_team="A",
        team_by_slot=np.asarray([0, 1], dtype=np.int8),
        ball_positions=positions,
        slot_positions=slots,
        alignment=FrameAlignment(count, 1, count, True),
    )


def test_short_gap_is_interpolated_and_long_gap_remains_missing() -> None:
    data = tracking(
        [
            [0.1, 0.1],
            None,
            None,
            [0.4, 0.4],
            None,
            None,
            None,
            [0.8, 0.8],
        ]
    )
    observations = prepare_ball_observations(
        data,
        fps=25,
        max_interpolation_gap_s=0.1,
    )
    assert observations.quality.tolist() == [
        BallQuality.OBSERVED,
        BallQuality.INTERPOLATED,
        BallQuality.INTERPOLATED,
        BallQuality.OBSERVED,
        BallQuality.MISSING,
        BallQuality.MISSING,
        BallQuality.MISSING,
        BallQuality.OBSERVED,
    ]
    assert observations.counts() == {"observed": 3, "interpolated": 2, "missing": 3}
    np.testing.assert_allclose(
        observations.positions[1:3],
        [[0.2, 0.2], [0.3, 0.3]],
        atol=1e-6,
    )


def test_edges_are_not_extrapolated() -> None:
    data = tracking([None, [0.2, 0.2], None])
    observations = prepare_ball_observations(data, fps=25, max_interpolation_gap_s=1.0)
    assert observations.quality.tolist() == [
        BallQuality.MISSING,
        BallQuality.OBSERVED,
        BallQuality.MISSING,
    ]
