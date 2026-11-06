"""Extra synthetic scenarios for candidate A.

Every sequence is constructed from scratch; no competition ground truth is read.
"""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from mtah_possession.algorithm_config import load_algorithm_config
from mtah_possession.data.observations import prepare_ball_observations
from mtah_possession.data.tracking import FrameAlignment, TrackingData
from mtah_possession.features.ball import AWAY, HOME
from mtah_possession.features.dead_ball import out_of_play_evidence
from mtah_possession.features.evidence import (
    BallMotionEvidence,
    EvidenceSeries,
    NearestTeamEvidence,
    NearPlayerVoteEvidence,
    ReachabilityEvidence,
    build_evidence_series,
)
from mtah_possession.states.possession_state import run_state_engine

ROOT = Path(__file__).resolve().parents[1]


def _config(**overrides):
    config = load_algorithm_config(ROOT / "configs" / "candidate-a.json")
    parameters = dict(config.parameters)
    for name, value in overrides.items():
        parameters[name] = replace(parameters[name], value=value)
    return replace(
        config,
        parameters=parameters,
        ungraded_blocks=(),
        forced_dead_blocks=(),
    )


def _tracking(
    *,
    ball: np.ndarray,
    slots: np.ndarray,
    teams: list[int],
    speeds: np.ndarray | None = None,
) -> TrackingData:
    count = int(ball.shape[0])
    return TrackingData(
        frame_count=count,
        home_team="H",
        away_team="A",
        team_by_slot=np.asarray(teams, dtype=np.int8),
        ball_positions=np.asarray(ball, dtype=np.float32),
        slot_positions=np.asarray(slots, dtype=np.float32),
        alignment=FrameAlignment(count, 1, count, True),
        slot_speeds=None if speeds is None else np.asarray(speeds, dtype=np.float32),
    )


def _evidence(config, data: TrackingData):
    observations = prepare_ball_observations(
        data,
        fps=25,
        max_interpolation_gap_s=0.4,
    )
    return build_evidence_series(data, observations, config)


def _series(candidates: list[int], *, dead: list[bool] | None = None) -> EvidenceSeries:
    count = len(candidates)
    candidate_array = np.asarray(candidates, dtype=np.int8)
    zeros = np.zeros(count, dtype=np.float64)
    votes = np.zeros(count, dtype=np.int16)
    return EvidenceSeries(
        nearest=NearestTeamEvidence(
            candidate_array,
            zeros.copy(),
            zeros.copy(),
            zeros.copy(),
        ),
        near_player_vote=NearPlayerVoteEvidence(
            candidate_array.copy(),
            votes,
            votes.copy(),
        ),
        ball_motion=BallMotionEvidence(
            np.full(count, np.nan),
            zeros.copy(),
            np.zeros(count, dtype=bool),
        ),
        restart_zone_distance_m=zeros.copy(),
        reachability=ReachabilityEvidence(zeros.copy(), zeros.copy()),
        team_candidate=candidate_array,
        dead_ball_evidence=np.asarray(dead or [False] * count, dtype=bool),
        restart_evidence=np.zeros(count, dtype=bool),
        forced_dead_mask=np.zeros(count, dtype=bool),
        ungraded_mask=np.zeros(count, dtype=bool),
    )


def test_out_of_play_y_axis_and_exact_line():
    positions = np.asarray(
        [[0.5, 1.01], [0.5, -0.01], [0.5, 1.0]],
        dtype=np.float32,
    )
    flags = out_of_play_evidence(
        positions,
        np.ones(3, dtype=bool),
        pitch_length_m=100.0,
        pitch_width_m=60.0,
        margin_m=0.5,
    )
    assert flags.tolist() == [True, True, False]


def test_out_of_play_then_return_recovers():
    n_frames = 80
    ball = np.tile(np.asarray([0.5, 0.5], dtype=np.float32), (n_frames, 1))
    ball[20:40] = (1.02, 0.5)
    ball[40:] = np.stack(
        [
            0.8 + 0.002 * np.arange(40, dtype=np.float32),
            np.full(40, 0.5, dtype=np.float32),
        ],
        axis=1,
    )
    slots = np.tile(
        np.asarray([[0.6, 0.5], [0.9, 0.5]], dtype=np.float32),
        (n_frames, 1, 1),
    )
    data = _tracking(ball=ball, slots=slots, teams=[HOME, AWAY])
    config = _config()
    labels = run_state_engine(_evidence(config, data), config).labels
    assert labels[39] == "D"
    assert labels[-1] != "D"


@pytest.mark.parametrize(
    "candidates",
    [
        [HOME] * 30 + [AWAY] * 30,
        [AWAY] * 30 + [HOME] * 30,
    ],
)
def test_candidate_config_keeps_direct_team_changes(candidates):
    result = run_state_engine(_series(candidates), _config())
    assert "D" not in result.labels
    assert any(item.previous != item.current for item in result.transitions)


def test_crowded_box_does_not_trigger_dead():
    n_frames = 20
    ball = np.stack(
        [
            0.4 + 0.01 * np.arange(n_frames, dtype=np.float32),
            np.full(n_frames, 0.5, dtype=np.float32),
        ],
        axis=1,
    )
    slots = np.tile(
        np.asarray([[0.45, 0.5], [0.55, 0.5]], dtype=np.float32),
        (n_frames, 1, 1),
    )
    speeds = np.full((n_frames, 2), 4.0, dtype=np.float32)
    data = _tracking(ball=ball, slots=slots, teams=[HOME, AWAY], speeds=speeds)
    evidence = _evidence(_config(), data)
    assert not evidence.dead_ball_evidence.any()


def test_still_ball_with_fast_team_is_not_dead_by_motion():
    config = _config(
        use_ball_rest_dead_ball=False,
        enable_out_of_play_dead_ball=False,
        use_restart_zone_dead_ball=False,
        use_team_motion_dead_ball=True,
    )
    n_frames = 50
    ball = np.tile(np.asarray([0.5, 0.5], dtype=np.float32), (n_frames, 1))
    slots = np.tile(
        np.asarray([[0.5, 0.5], [0.9, 0.5]], dtype=np.float32),
        (n_frames, 1, 1),
    )
    speeds = np.full((n_frames, 2), 4.0, dtype=np.float32)
    evidence = _evidence(
        config, _tracking(ball=ball, slots=slots, teams=[HOME, AWAY], speeds=speeds)
    )
    assert not evidence.dead_ball_evidence.any()


def test_still_ball_with_slow_team_is_dead_by_motion():
    config = _config(
        use_ball_rest_dead_ball=False,
        enable_out_of_play_dead_ball=False,
        use_restart_zone_dead_ball=False,
        use_team_motion_dead_ball=True,
    )
    n_frames = 50
    ball = np.tile(np.asarray([0.5, 0.5], dtype=np.float32), (n_frames, 1))
    slots = np.tile(
        np.asarray([[0.5, 0.5], [0.9, 0.5]], dtype=np.float32),
        (n_frames, 1, 1),
    )
    speeds = np.full((n_frames, 2), 0.2, dtype=np.float32)
    evidence = _evidence(
        config, _tracking(ball=ball, slots=slots, teams=[HOME, AWAY], speeds=speeds)
    )
    assert evidence.dead_ball_evidence[-1]


def test_moving_ball_with_slow_team_is_not_dead_by_motion():
    config = _config(
        use_ball_rest_dead_ball=False,
        enable_out_of_play_dead_ball=False,
        use_restart_zone_dead_ball=False,
        use_team_motion_dead_ball=True,
    )
    n_frames = 30
    ball = np.stack(
        [
            0.4 + 0.01 * np.arange(n_frames, dtype=np.float32),
            np.full(n_frames, 0.5, dtype=np.float32),
        ],
        axis=1,
    )
    slots = np.tile(
        np.asarray([[0.5, 0.5], [0.9, 0.5]], dtype=np.float32),
        (n_frames, 1, 1),
    )
    speeds = np.full((n_frames, 2), 0.2, dtype=np.float32)
    evidence = _evidence(
        config, _tracking(ball=ball, slots=slots, teams=[HOME, AWAY], speeds=speeds)
    )
    assert not evidence.dead_ball_evidence.any()


def test_short_ball_loss_is_not_out_of_play_or_dead():
    n_frames = 60
    ball = np.tile(np.asarray([0.5, 0.5], dtype=np.float32), (n_frames, 1))
    ball[30:33] = np.nan
    slots = np.tile(
        np.asarray([[0.5, 0.5], [0.9, 0.5]], dtype=np.float32),
        (n_frames, 1, 1),
    )
    evidence = _evidence(_config(), _tracking(ball=ball, slots=slots, teams=[HOME, AWAY]))
    assert not evidence.dead_ball_evidence[30:33].any()


def test_long_ball_loss_is_not_treated_as_out_of_play():
    n_frames = 80
    ball = np.tile(np.asarray([0.5, 0.5], dtype=np.float32), (n_frames, 1))
    ball[20:60] = np.nan
    slots = np.tile(
        np.asarray([[0.5, 0.5], [0.9, 0.5]], dtype=np.float32),
        (n_frames, 1, 1),
    )
    evidence = _evidence(_config(), _tracking(ball=ball, slots=slots, teams=[HOME, AWAY]))
    assert not evidence.dead_ball_evidence[20:60].any()


def test_restart_zone_requires_proximity_and_rest():
    config = _config(
        use_ball_rest_dead_ball=False,
        enable_out_of_play_dead_ball=False,
        use_restart_zone_dead_ball=True,
        use_team_motion_dead_ball=False,
    )
    n_frames = 50
    slots = np.tile(
        np.asarray([[0.1, 0.1], [0.9, 0.9]], dtype=np.float32),
        (n_frames, 1, 1),
    )
    corner = np.tile(np.asarray([0.0, 0.0], dtype=np.float32), (n_frames, 1))
    corner_evidence = _evidence(
        config,
        _tracking(ball=corner, slots=slots, teams=[HOME, AWAY]),
    )
    assert corner_evidence.dead_ball_evidence[-1]

    open_play = np.tile(np.asarray([0.25, 0.25], dtype=np.float32), (n_frames, 1))
    open_evidence = _evidence(
        config,
        _tracking(ball=open_play, slots=slots, teams=[HOME, AWAY]),
    )
    assert not open_evidence.dead_ball_evidence.any()
