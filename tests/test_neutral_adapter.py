from dataclasses import fields, replace
from pathlib import Path

import numpy as np

from mtah_possession.algorithm_config import load_algorithm_config
from mtah_possession.data.neutral import (
    NeutralMatch,
    PeriodSpan,
    PhaseSpan,
    TeamSide,
    blocks_from_mask,
    map_proxy_target,
    neutral_to_tracking,
)
from mtah_possession.data.observations import prepare_ball_observations
from mtah_possession.data.tracking import TrackingData
from mtah_possession.features.evidence import build_evidence_series
from mtah_possession.states.possession_state import run_state_engine

ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = load_algorithm_config(ROOT / "configs" / "state-engine.json")


def neutral(
    *,
    frame_count: int,
    possession_side: list[int],
    possession_status: list[int],
    frame_present: list[bool],
    phases: tuple[PhaseSpan, ...] = (),
) -> NeutralMatch:
    positions = np.zeros((frame_count, 2, 2), dtype=np.float32)
    positions[:, 0] = (-1.0, 0.0)
    positions[:, 1] = (10.0, 0.0)
    ball = np.zeros((frame_count, 2), dtype=np.float32)
    return NeutralMatch(
        match_id="neutral",
        fps=10,
        frame_count=frame_count,
        pitch_length_m=100.0,
        pitch_width_m=60.0,
        coordinate_convention="metres-center-origin",
        home_team_id=1,
        away_team_id=2,
        home_team_name="Home",
        away_team_name="Away",
        player_ids=(101, 201),
        team_by_slot=np.asarray([0, 1], dtype=np.int8),
        slot_positions=positions,
        slot_detected=np.ones((frame_count, 2), dtype=bool),
        ball_positions=ball,
        ball_detected=np.ones(frame_count, dtype=bool),
        frame_present=np.asarray(frame_present),
        possession_side=np.asarray(possession_side, dtype=np.int8),
        possession_status=np.asarray(possession_status, dtype=np.int8),
        periods=(PeriodSpan(1, 1, frame_count),),
        phases=phases,
        source_checksums={"fixture": "abc"},
        source_metadata={},
    )


def test_proxy_maps_missing_cases_explicitly() -> None:
    data = neutral(
        frame_count=7,
        frame_present=[True, True, True, True, True, False, True],
        possession_side=[-1, -1, -1, 0, 1, -1, -1],
        possession_status=[1, 1, 1, 0, 0, 1, 2],
        phases=(PhaseSpan(2, 4, 1, "build_up"),),
    )
    proxy = map_proxy_target(data)
    assert proxy.labels.tolist() == ["X", "D", "X", "H", "A", "X", "X"]
    assert proxy.sources[0] == "outside_declared_period"
    assert proxy.sources[1] == "no_possession_and_no_phase"
    assert proxy.sources[2] == "missing_possession_inside_phase"
    assert proxy.sources[5] == "missing_tracking_frame"
    assert proxy.sources[6] == "unrecognized_possession_group"


def test_neutral_metres_convert_to_engine_normalised_coordinates() -> None:
    data = neutral(
        frame_count=1,
        frame_present=[True],
        possession_side=[0],
        possession_status=[0],
    )
    tracking = neutral_to_tracking(data)
    np.testing.assert_allclose(tracking.ball_positions[0], [0.5, 0.5], atol=1e-6)
    np.testing.assert_allclose(tracking.slot_positions[0, 0], [0.49, 0.5], atol=1e-6)


def test_possession_labels_cannot_change_model_input_or_leak_into_type() -> None:
    left = neutral(
        frame_count=4,
        frame_present=[True] * 4,
        possession_side=[0, 0, 1, 1],
        possession_status=[0] * 4,
    )
    right = replace(
        left,
        possession_side=np.asarray([1, 1, 0, 0], dtype=np.int8),
        possession_status=np.asarray([2, 1, 0, 0], dtype=np.int8),
    )
    left_tracking = neutral_to_tracking(left)
    right_tracking = neutral_to_tracking(right)
    for field in fields(TrackingData):
        left_value = getattr(left_tracking, field.name)
        right_value = getattr(right_tracking, field.name)
        if isinstance(left_value, np.ndarray):
            np.testing.assert_allclose(left_value, right_value, equal_nan=True)
        else:
            assert left_value == right_value
    model_fields = {field.name for field in fields(TrackingData)}
    assert not any("possession" in name for name in model_fields)


def test_blocks_from_mask_uses_inclusive_frame_pairs() -> None:
    mask = np.asarray([False, True, True, False, True], dtype=bool)
    assert blocks_from_mask(mask) == ((1, 2), (4, 4))


def test_10_and_25_fps_equivalent_sequences_switch_at_same_seconds() -> None:
    transitions = []
    for fps in (10, 25):
        first = fps
        count = fps * 3
        candidates = np.full(count, TeamSide.HOME, dtype=np.int8)
        candidates[first:] = TeamSide.AWAY
        positions = np.zeros((count, 2, 2), dtype=np.float32)
        ball = np.zeros((count, 2), dtype=np.float32)
        for frame, candidate in enumerate(candidates):
            if candidate == TeamSide.HOME:
                positions[frame, 0] = (-0.1, 0.0)
                positions[frame, 1] = (10.0, 0.0)
            else:
                positions[frame, 0] = (-10.0, 0.0)
                positions[frame, 1] = (0.1, 0.0)
        data = replace(
            neutral(
                frame_count=count,
                frame_present=[True] * count,
                possession_side=[0] * count,
                possession_status=[0] * count,
            ),
            fps=fps,
            periods=(PeriodSpan(1, 0, count),),
            slot_positions=positions,
            ball_positions=ball,
        )
        parameters = dict(BASE_CONFIG.parameters)
        rest = parameters["use_ball_rest_dead_ball"]
        parameters["use_ball_rest_dead_ball"] = replace(rest, value=False)
        config = replace(
            BASE_CONFIG,
            fps=fps,
            expected_frames=count,
            pitch_length_m=100.0,
            pitch_width_m=60.0,
            ungraded_blocks=(),
            forced_dead_blocks=(),
            parameters=parameters,
        )
        tracking = neutral_to_tracking(data)
        observations = prepare_ball_observations(
            tracking,
            fps=fps,
            max_interpolation_gap_s=config.number("ball_interpolation_max_s"),
        )
        evidence = build_evidence_series(tracking, observations, config)
        result = run_state_engine(evidence, config)
        switch = next(item for item in result.transitions if item.previous == "H")
        transitions.append(switch.frame / fps)
    assert abs(transitions[0] - transitions[1]) <= 0.1
    assert all(abs(value - 1.73) <= 0.1 for value in transitions)
