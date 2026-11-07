from dataclasses import fields, replace
from pathlib import Path

import numpy as np
import pytest

from mtah_possession.algorithm_config import load_algorithm_config
from mtah_possession.data.model_input import (
    AllowedEventEvidence,
    ModelInput,
    build_model_input,
    with_event_evidence,
)
from mtah_possession.data.neutral import (
    NeutralMatch,
    PeriodSpan,
    PhaseSpan,
    SourceQuality,
    TeamSide,
    blocks_from_mask,
    map_proxy_target,
    neutral_to_tracking,
)
from mtah_possession.data.observations import prepare_ball_observations
from mtah_possession.data.tracking import TrackingData
from mtah_possession.evaluation.external import (
    evaluate_external_match,
    predict_model_input,
)
from mtah_possession.features.evidence import build_evidence_series
from mtah_possession.governance.authorization import (
    EVALUATION_PHASE_PROFILE,
    EVALUATION_POSSESSION_PROFILE,
    AuthorizedExternalRun,
)
from mtah_possession.governance.policy import (
    DataUse,
    PolicyError,
    PolicyStatus,
    UsePermission,
    load_policy,
)
from mtah_possession.governance.temporal import TemporalFieldPolicy
from mtah_possession.states.phase_layer import (
    PhaseDirective,
    PhaseKind,
    compile_phase_evidence,
)
from mtah_possession.states.possession_state import run_state_engine

ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = load_algorithm_config(ROOT / "configs" / "state-engine.json")


def authorized_run() -> AuthorizedExternalRun:
    policy = load_policy(ROOT / "configs" / "policy" / "external-data-policy-v2.json")
    provider = policy.provider("skillcorner")
    profiles = tuple(
        replace(profile, status=PolicyStatus.PASS) for profile in provider.label_profiles
    )
    selected_profiles = {
        EVALUATION_POSSESSION_PROFILE: next(
            profile
            for profile in profiles
            if profile.provider_label_definition_id == EVALUATION_POSSESSION_PROFILE
        ),
        EVALUATION_PHASE_PROFILE: next(
            profile
            for profile in profiles
            if profile.provider_label_definition_id == EVALUATION_PHASE_PROFILE
        ),
    }
    permissions = {
        use: UsePermission(PolicyStatus.PASS, ("EV-AUTH-SC-README",), ())
        for use in (
            DataUse.TRACKING_MODEL_INPUT,
            DataUse.PHASE_MODEL_INPUT,
            DataUse.EVALUATION_REFERENCE,
        )
    }
    return AuthorizedExternalRun(
        policy=policy,
        provider=replace(provider, label_profiles=profiles),
        use_permissions=permissions,
        label_profiles=selected_profiles,
        freeze_hashes=None,
    )


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
    profiles = authorized_run().label_profiles
    proxy = map_proxy_target(
        data,
        possession_profile=profiles[EVALUATION_POSSESSION_PROFILE],
        phase_profile=profiles[EVALUATION_PHASE_PROFILE],
    )
    assert proxy.labels.tolist() == ["X", "D", "X", "H", "A", "X", "X"]
    assert proxy.sources[0] == "outside_declared_period"
    assert proxy.sources[1] == "no_possession_and_no_phase"
    assert proxy.sources[2] == "missing_possession_inside_phase"
    assert proxy.sources[5] == "missing_tracking_frame"
    assert proxy.sources[6] == "unrecognized_possession_group"
    assert proxy.label_profiles[EVALUATION_PHASE_PROFILE]["label_kind"] == "proxy"
    assert proxy.label_profiles[EVALUATION_PHASE_PROFILE]["target_mapping_id"]
    assert proxy.label_profiles[EVALUATION_PHASE_PROFILE]["mapping_version"]


def test_phase_gap_proxy_requires_pass_label_profile() -> None:
    data = neutral(
        frame_count=3,
        frame_present=[True] * 3,
        possession_side=[-1] * 3,
        possession_status=[1] * 3,
    )
    profiles = authorized_run().label_profiles
    with pytest.raises(PolicyError, match="is HOLD"):
        map_proxy_target(
            data,
            possession_profile=profiles[EVALUATION_POSSESSION_PROFILE],
            phase_profile=replace(
                profiles[EVALUATION_PHASE_PROFILE],
                status=PolicyStatus.HOLD,
            ),
        )


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


def test_possession_labels_cannot_change_end_to_end_prediction() -> None:
    left = neutral(
        frame_count=30,
        frame_present=[True] * 30,
        possession_side=[0] * 30,
        possession_status=[0] * 30,
    )
    right = replace(
        left,
        possession_side=np.full(30, -1, dtype=np.int8),
        possession_status=np.full(30, 1, dtype=np.int8),
    )
    parameters = dict(BASE_CONFIG.parameters)
    rest = parameters["use_ball_rest_dead_ball"]
    parameters["use_ball_rest_dead_ball"] = replace(rest, value=False)
    config = replace(
        BASE_CONFIG,
        fps=10,
        expected_frames=30,
        pitch_length_m=100.0,
        pitch_width_m=60.0,
        ungraded_blocks=(),
        forced_dead_blocks=(),
        parameters=parameters,
    )
    left_input = build_model_input(left)
    right_input = build_model_input(right)
    left_prediction = predict_model_input(left_input, config)
    right_prediction = predict_model_input(right_input, config)
    assert left_prediction.labels.tolist() == right_prediction.labels.tolist()
    assert left_prediction.reasons.tolist() == right_prediction.reasons.tolist()
    assert left_prediction.prediction_sha256 == right_prediction.prediction_sha256
    for model_type in (ModelInput, AllowedEventEvidence, TrackingData):
        assert not any("possession" in field.name for field in fields(model_type))


def test_phase_evidence_changes_only_approved_dead_and_restart_behavior() -> None:
    data = replace(
        neutral(
            frame_count=30,
            frame_present=[True] * 30,
            possession_side=[-1] * 30,
            possession_status=[1] * 30,
        ),
        periods=(PeriodSpan(1, 0, 30),),
    )
    parameters = dict(BASE_CONFIG.parameters)
    rest = parameters["use_ball_rest_dead_ball"]
    parameters["use_ball_rest_dead_ball"] = replace(rest, value=False)
    config = replace(
        BASE_CONFIG,
        fps=10,
        expected_frames=30,
        pitch_length_m=100.0,
        pitch_width_m=60.0,
        ungraded_blocks=(),
        forced_dead_blocks=(),
        parameters=parameters,
    )
    base_input = build_model_input(data)
    phase_evidence = compile_phase_evidence(
        30,
        10,
        (
            PhaseDirective(5, 10, PhaseKind.THROW_IN, confirmed_dead=True),
            PhaseDirective(10, 15, PhaseKind.RESTART, restart=True),
        ),
        restart_window_s=0.2,
    )
    phase_input = with_event_evidence(base_input, phase_evidence)
    temporal_fields = phase_input.event_evidence.temporal_fields
    assert {field.field_name for field in temporal_fields} == {
        "forced_dead_mask",
        "restart_evidence",
        "source_codes",
    }
    assert all(len(field.per_frame_available_at) == 30 for field in temporal_fields)
    assert all(field.available_at is None for field in temporal_fields)
    baseline = predict_model_input(base_input, config)
    phase_aware = predict_model_input(phase_input, config)
    assert baseline.labels.tolist() == ["H"] * 30
    assert phase_aware.labels[5:11].tolist() == ["D"] * 6
    assert phase_aware.labels[11:].tolist() == ["H"] * 19


def test_nonempty_phase_evidence_without_temporal_metadata_fails() -> None:
    data = replace(
        neutral(
            frame_count=20,
            frame_present=[True] * 20,
            possession_side=[-1] * 20,
            possession_status=[1] * 20,
        ),
        periods=(PeriodSpan(1, 0, 20),),
    )
    base_input = build_model_input(data)
    phase = compile_phase_evidence(
        20,
        10,
        (PhaseDirective(5, 10, PhaseKind.CORNER, confirmed_dead=True),),
    )
    injected = with_event_evidence(base_input, phase)
    invalid = replace(injected, event_evidence=replace(injected.event_evidence, temporal_fields=()))
    with pytest.raises(PolicyError, match="requires temporal metadata"):
        predict_model_input(
            invalid,
            replace(
                BASE_CONFIG,
                fps=10,
                expected_frames=20,
                ungraded_blocks=(),
                forced_dead_blocks=(),
            ),
        )


def test_nonempty_phase_evidence_requires_temporal_metadata_for_each_field() -> None:
    data = replace(
        neutral(
            frame_count=20,
            frame_present=[True] * 20,
            possession_side=[-1] * 20,
            possession_status=[1] * 20,
        ),
        periods=(PeriodSpan(1, 0, 20),),
    )
    model_input = build_model_input(data)
    phase = compile_phase_evidence(
        20,
        10,
        (PhaseDirective(5, 10, PhaseKind.CORNER, confirmed_dead=True),),
    )
    injected = with_event_evidence(model_input, phase)
    partial = replace(
        injected.event_evidence,
        temporal_fields=tuple(
            field
            for field in injected.event_evidence.temporal_fields
            if field.field_name != "source_codes"
        ),
    )
    with pytest.raises(PolicyError, match="lack temporal metadata: source_codes"):
        predict_model_input(
            replace(injected, event_evidence=partial),
            replace(
                BASE_CONFIG,
                fps=10,
                expected_frames=20,
                ungraded_blocks=(),
                forced_dead_blocks=(),
            ),
        )


def test_synthetic_external_evaluation_preserves_requested_split() -> None:
    data = replace(
        neutral(
            frame_count=60,
            frame_present=[True] * 60,
            possession_side=[0] * 60,
            possession_status=[0] * 60,
        ),
        periods=(PeriodSpan(1, 0, 60),),
    )
    evaluation = evaluate_external_match(
        data,
        BASE_CONFIG,
        authorization=authorized_run(),
        split="validation",
    )
    assert evaluation.split == "validation"
    assert set(evaluation.candidates) == {
        "dp001_004_baseline",
        "dp005",
        "dp006_phase_proxy",
    }
    for candidate in evaluation.candidates.values():
        assert candidate.labels.shape == (60,)


def test_future_event_field_is_rejected_by_real_model_path() -> None:
    data = replace(
        neutral(
            frame_count=10,
            frame_present=[True] * 10,
            possession_side=[-1] * 10,
            possession_status=[1] * 10,
        ),
        periods=(PeriodSpan(1, 0, 10),),
    )
    model_input = build_model_input(data)
    invalid_events = replace(
        model_input.event_evidence,
        temporal_fields=(
            TemporalFieldPolicy(
                field_name="event_end_x",
                event_time=0.1,
                interval_start=0.1,
                interval_end=None,
                available_at=0.1,
                availability_source="event export",
                semantics_version="DP-006-POLICY-v2",
            ),
        ),
    )
    with pytest.raises(PolicyError, match="event fields are not registered"):
        predict_model_input(
            replace(model_input, event_evidence=invalid_events),
            replace(
                BASE_CONFIG,
                fps=10,
                expected_frames=10,
                ungraded_blocks=(),
                forced_dead_blocks=(),
            ),
        )


def test_blocks_from_mask_uses_inclusive_frame_pairs() -> None:
    mask = np.asarray([False, True, True, False, True], dtype=bool)
    assert blocks_from_mask(mask) == ((1, 2), (4, 4))


def test_source_quality_keeps_detected_extrapolated_and_missing_distinct() -> None:
    data = replace(
        neutral(
            frame_count=1,
            frame_present=[True],
            possession_side=[-1],
            possession_status=[1],
        ),
        slot_source_quality=np.asarray(
            [[SourceQuality.EXTRAPOLATED, SourceQuality.DETECTED]],
            dtype=np.int8,
        ),
        ball_source_quality=np.asarray(
            [SourceQuality.MISSING],
            dtype=np.int8,
        ),
        slot_detected=np.asarray([[False, True]]),
        ball_detected=np.asarray([False]),
    )
    assert data.source_quality_counts() == {
        "players": {"detected": 1, "extrapolated": 1, "missing": 0},
        "ball": {"detected": 0, "extrapolated": 0, "missing": 1},
    }
    tracking = neutral_to_tracking(data)
    assert np.isnan(tracking.slot_positions[0, 0]).all()
    assert np.isfinite(tracking.slot_positions[0, 1]).all()


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
