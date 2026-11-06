"""Synthetic tests for the candidate-A dead-ball evidence."""

from pathlib import Path

import numpy as np
import pytest

from mtah_possession.algorithm_config import load_algorithm_config
from mtah_possession.data.observations import prepare_ball_observations
from mtah_possession.data.tracking import FrameAlignment, TrackingData
from mtah_possession.features.ball import AWAY, HOME
from mtah_possession.features.dead_ball import (
    out_of_play_evidence,
    team_motion_evidence,
)
from mtah_possession.features.evidence import build_evidence_series

ROOT = Path(__file__).resolve().parents[1]


def test_out_of_play_uses_a_metric_margin():
    positions = np.asarray(
        [[0.5, 0.5], [1.001, 0.5], [1.01, 0.5], [-0.01, 0.5]],
        dtype=np.float32,
    )
    usable = np.ones(4, dtype=bool)
    flags = out_of_play_evidence(
        positions,
        usable,
        pitch_length_m=100.0,
        pitch_width_m=60.0,
        margin_m=0.5,
    )
    # 0.1 m over the line is inside the margin; 1.0 m is outside.
    assert flags.tolist() == [False, False, True, True]


def test_out_of_play_ignores_a_missing_ball():
    positions = np.asarray([[np.nan, np.nan]], dtype=np.float32)
    flags = out_of_play_evidence(
        positions,
        np.asarray([False]),
        pitch_length_m=100.0,
        pitch_width_m=60.0,
        margin_m=0.5,
    )
    assert flags.tolist() == [False]


def test_team_motion_is_the_mean_tracked_speed():
    speeds = np.asarray(
        [[2.0, np.nan, 0.0], [np.nan, np.nan, np.nan]],
        dtype=np.float32,
    )
    motion = team_motion_evidence(speeds)
    assert motion[0] == pytest.approx(1.0)
    assert np.isnan(motion[1])


def test_team_motion_accepts_no_speed_channel():
    motion = team_motion_evidence(None, frame_count=3)
    assert motion.shape == (3,)
    assert np.isnan(motion).all()


def _tracking(
    *,
    ball: list[list[float]],
    slots: list[list[list[float]]],
    teams: list[int],
    speeds: list[list[float]] | None = None,
) -> TrackingData:
    count = len(ball)
    slot_speeds = None if speeds is None else np.asarray(speeds, dtype=np.float32)
    return TrackingData(
        frame_count=count,
        home_team="H",
        away_team="A",
        team_by_slot=np.asarray(teams, dtype=np.int8),
        ball_positions=np.asarray(ball, dtype=np.float32),
        slot_positions=np.asarray(slots, dtype=np.float32),
        alignment=FrameAlignment(count, 1, count, True),
        slot_speeds=slot_speeds,
    )


def _evidence(config_name: str, data: TrackingData):
    config = load_algorithm_config(ROOT / "configs" / config_name)
    observations = prepare_ball_observations(
        data,
        fps=25,
        max_interpolation_gap_s=0.4,
    )
    return build_evidence_series(data, observations, config)


def test_candidate_config_marks_out_of_play_dead():
    data = _tracking(
        ball=[[0.5, 0.5], [1.01, 0.5]],
        slots=[
            [[0.5, 0.5], [0.9, 0.5]],
            [[0.5, 0.5], [0.9, 0.5]],
        ],
        teams=[HOME, AWAY],
    )
    evidence = _evidence("candidate-a.json", data)
    assert evidence.dead_ball_evidence.tolist() == [False, True]


def test_frozen_config_does_not_mark_out_of_play_dead():
    data = _tracking(
        ball=[[0.5, 0.5], [1.01, 0.5]],
        slots=[
            [[0.5, 0.5], [0.9, 0.5]],
            [[0.5, 0.5], [0.9, 0.5]],
        ],
        teams=[HOME, AWAY],
    )
    evidence = _evidence("state-engine.json", data)
    assert not evidence.dead_ball_evidence[1]


def test_candidate_team_motion_with_rest_is_dead():
    n_frames = 50
    data = _tracking(
        ball=[[0.5, 0.5]] * n_frames,
        slots=[[[0.5, 0.5], [0.9, 0.5]]] * n_frames,
        teams=[HOME, AWAY],
        speeds=[[0.2, 0.2]] * n_frames,
    )
    evidence = _evidence("candidate-a.json", data)
    assert evidence.dead_ball_evidence[-1]
