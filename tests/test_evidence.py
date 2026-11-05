import numpy as np
import pytest

from mtah_possession.data.observations import BallObservations, BallQuality
from mtah_possession.data.tracking import FrameAlignment, TrackingData
from mtah_possession.features.ball import AWAY, HOME
from mtah_possession.features.evidence import (
    TaggingInterval,
    ball_motion_evidence,
    nearest_team_evidence,
    optimistic_reachability,
    restart_zone_distance,
    smart_tagging_evidence,
    visible_near_player_vote,
)


def tracking(
    *,
    ball: list[list[float]],
    slots: list[list[list[float] | None]],
    teams: list[int],
    speeds: list[list[float | None]] | None = None,
) -> TrackingData:
    count = len(ball)
    slot_positions = np.asarray(
        [[[np.nan, np.nan] if point is None else point for point in frame] for frame in slots],
        dtype=np.float32,
    )
    slot_speeds = None
    if speeds is not None:
        slot_speeds = np.asarray(
            [[np.nan if speed is None else speed for speed in row] for row in speeds],
            dtype=np.float32,
        )
    return TrackingData(
        frame_count=count,
        home_team="H",
        away_team="A",
        team_by_slot=np.asarray(teams, dtype=np.int8),
        ball_positions=np.asarray(ball, dtype=np.float32),
        slot_positions=slot_positions,
        alignment=FrameAlignment(count, 1, count, True),
        slot_speeds=slot_speeds,
    )


def test_visible_vote_uses_only_visible_slots() -> None:
    data = tracking(
        ball=[[0.5, 0.5]],
        slots=[[[0.5, 0.5], None, [0.9, 0.9], [0.9, 0.9]]],
        teams=[HOME, HOME, AWAY, AWAY],
    )
    result = visible_near_player_vote(
        data,
        data.ball_positions,
        np.asarray([True]),
        pitch_length_m=105.0,
        pitch_width_m=68.0,
        k=3,
    )
    assert result.home_votes.tolist() == [1]
    assert result.away_votes.tolist() == [2]
    assert result.candidate.tolist() == [AWAY]


@pytest.mark.filterwarnings("error")
def test_both_teams_fully_missing_has_no_numeric_warning() -> None:
    data = tracking(
        ball=[[0.5, 0.5]],
        slots=[[None, None]],
        teams=[HOME, AWAY],
    )
    result = nearest_team_evidence(
        data,
        data.ball_positions,
        np.asarray([True]),
        pitch_length_m=105.0,
        pitch_width_m=68.0,
    )
    assert result.candidate.tolist() == [-1]
    assert np.isnan(result.home_distance_m).all()
    assert np.isnan(result.away_distance_m).all()
    assert np.isnan(result.distance_gap_m).all()


@pytest.mark.parametrize(
    ("slots", "teams"),
    [
        ([[None, None], [0.8, 0.5]], [HOME, AWAY]),
        ([[0.2, 0.5], [None, None]], [HOME, AWAY]),
    ],
)
@pytest.mark.filterwarnings("error")
def test_one_fully_missing_team_remains_no_candidate(
    slots: list[list[float] | None],
    teams: list[int],
) -> None:
    data = tracking(
        ball=[[0.5, 0.5]],
        slots=[slots],
        teams=teams,
    )
    result = nearest_team_evidence(
        data,
        data.ball_positions,
        np.asarray([True]),
        pitch_length_m=105.0,
        pitch_width_m=68.0,
    )
    assert result.candidate.tolist() == [-1]


def test_ball_rest_duration_and_motion_speed() -> None:
    positions = np.asarray(
        [[0.5, 0.5], [0.5, 0.5], [0.6, 0.5], [0.6, 0.5]],
        dtype=np.float32,
    )
    observations = BallObservations(
        positions=positions,
        quality=np.asarray([BallQuality.OBSERVED] * 4, dtype=np.int8),
        observed_mask=np.ones(4, dtype=bool),
    )
    motion = ball_motion_evidence(
        observations,
        fps=25,
        pitch_length_m=100.0,
        pitch_width_m=60.0,
        rest_speed_threshold_mps=0.5,
    )
    assert np.isnan(motion.speed_mps[0])
    assert motion.speed_mps[1] == 0.0
    assert motion.rest_duration_s[:2].tolist() == [0.0, 0.04]
    assert motion.speed_mps[2] == pytest.approx(250.0, abs=1e-4)
    assert motion.rest_duration_s[2] == 0.0


def test_restart_zone_distance_and_reachability_are_metric() -> None:
    data = tracking(
        ball=[[0.1, 0.5]],
        slots=[[[0.2, 0.5], [0.9, 0.5]]],
        teams=[HOME, AWAY],
        speeds=[[None, 2.0]],
    )
    distance = restart_zone_distance(
        data.ball_positions,
        np.asarray([True]),
        pitch_length_m=100.0,
        pitch_width_m=60.0,
    )
    reachability = optimistic_reachability(
        data,
        data.ball_positions,
        np.asarray([True]),
        pitch_length_m=100.0,
        pitch_width_m=60.0,
        extra_speed_mps=2.0,
    )
    assert distance.tolist() == pytest.approx([10.0], abs=1e-5)
    assert reachability.home_time_s.tolist() == pytest.approx([5.0], abs=1e-5)
    assert reachability.away_time_s.tolist() == pytest.approx([20.0], abs=1e-5)


def test_smart_tagging_is_weak_prior_and_handles_na_team() -> None:
    result = smart_tagging_evidence(
        10,
        [
            TaggingInterval(1, 5, "Barcelona", restart=True),
            TaggingInterval(5, 8, "N/A", dead_ball=True),
        ],
    )
    assert result.team_prior.tolist() == [-1, 0, 0, 0, 0, -1, -1, -1, -1, -1]
    assert result.restart_evidence[1:5].tolist() == [True] * 4
    assert result.dead_ball_evidence[5:8].tolist() == [True] * 3
