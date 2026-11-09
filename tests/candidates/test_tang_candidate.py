from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from helpers import make_data_root

from mtah_possession.candidates.tang.adapter import build_candidate
from mtah_possession.candidates.tang.config import load_candidate_config
from mtah_possession.candidates.tang.decoder import (
    _filter_low_confidence_short_segments,
    decode,
)
from mtah_possession.candidates.tang.emission import Emission, build_emission
from mtah_possession.candidates.tang.features import FrameFeatures, build_features
from mtah_possession.candidates.tang.smart_tagging import (
    SmartEvidence,
    build_smart_evidence,
    load_tags,
)
from mtah_possession.candidates.tang.velocity import compute_time_to_ball
from mtah_possession.data.observations import prepare_ball_observations
from mtah_possession.data.tracking import FrameAlignment, TrackingData
from mtah_possession.features.ball import AWAY, HOME, NO_CANDIDATE

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "candidates" / "tang" / "candidate-b.json"
NO_SMART_CONFIG_PATH = ROOT / "configs" / "candidates" / "tang" / "candidate-b-no-smart.json"
HYSTERESIS_CONFIG_PATH = ROOT / "configs" / "candidates" / "tang" / "candidate-b-hysteresis.json"
PRESSURE_CONFIG_PATH = ROOT / "configs" / "candidates" / "tang" / "candidate-b-pressure.json"
QUALITY_CONFIG_PATH = ROOT / "configs" / "candidates" / "tang" / "candidate-b-quality.json"


def small_config(tmp_path: Path, frames: int = 40, *, graded_only: bool = False):
    values = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    values["expected_frames"] = frames
    values["parameters"]["emission_smoothing_half_width_frames"]["value"] = 2
    values["parameters"]["dead_smoothing_half_width_frames"]["value"] = 2
    values["parameters"]["dwell_frames"]["value"] = 0
    values["parameters"]["dwell_penalty"]["value"] = 0.0
    values["ungraded_blocks"] = [] if graded_only else [[0, 4], [frames - 5, frames - 1]]
    values["forced_dead_blocks"] = []
    path = tmp_path / "candidate-small.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    return load_candidate_config(path)


def tracking(
    ball: list[list[float]],
    slots: list[list[list[float] | None]],
    teams: list[int],
) -> TrackingData:
    slot_positions = np.asarray(
        [[[np.nan, np.nan] if point is None else point for point in frame] for frame in slots],
        dtype=np.float32,
    )
    return TrackingData(
        frame_count=len(ball),
        home_team="H",
        away_team="A",
        team_by_slot=np.asarray(teams, dtype=np.int8),
        ball_positions=np.asarray(ball, dtype=np.float32),
        slot_positions=slot_positions,
        alignment=FrameAlignment(len(ball), 1, len(ball), True),
    )


def features_stub(
    count: int,
    *,
    tracking_candidate: list[int] | None = None,
    smart_restart: list[bool] | None = None,
    smart_dead: list[bool] | None = None,
    out_of_bounds: list[bool] | None = None,
    ball_rest: list[float] | None = None,
) -> FrameFeatures:
    return FrameFeatures(
        usable_ball=np.ones(count, dtype=bool),
        home_distance_m=np.full(count, np.nan),
        away_distance_m=np.full(count, np.nan),
        home_votes=np.zeros(count, dtype=np.int16),
        away_votes=np.zeros(count, dtype=np.int16),
        tracking_candidate=np.asarray(
            tracking_candidate if tracking_candidate is not None else [NO_CANDIDATE] * count,
            dtype=np.int8,
        ),
        ball_speed_mps=np.full(count, np.nan),
        ball_rest_s=np.asarray(ball_rest or [0.0] * count),
        time_advantage_s=np.zeros(count, dtype=np.float64),
        time_valid=np.zeros(count, dtype=bool),
        pressure_advantage_5m=np.zeros(count, dtype=np.float64),
        pressure_valid=np.zeros(count, dtype=bool),
        tracking_anomaly=np.zeros(count, dtype=bool),
        out_of_bounds=np.asarray(out_of_bounds or [False] * count),
        contested=np.zeros(count, dtype=bool),
        loose_ball=np.zeros(count, dtype=bool),
        smart_team=np.full(count, NO_CANDIDATE, dtype=np.int8),
        smart_restart=np.asarray(smart_restart or [False] * count),
        smart_dead=np.asarray(smart_dead or [False] * count),
        smart_conflict=np.zeros(count, dtype=bool),
    )


def emission_stub(probabilities: list[list[float]], valid: list[bool] | None = None) -> Emission:
    probs = np.asarray(probabilities, dtype=np.float64)
    return Emission(
        probabilities=probs,
        valid=np.asarray(valid if valid is not None else [True] * len(probabilities)),
        confidence=probs.max(axis=1),
        smart_conflict=np.zeros(len(probabilities), dtype=bool),
    )


def test_tracking_candidate_wins_conflicting_smart_prior() -> None:
    config = load_candidate_config(CONFIG_PATH)
    data = tracking(
        ball=[[0.5, 0.5]],
        slots=[[[0.49, 0.5], [0.51, 0.5], [0.9, 0.5]]],
        teams=[HOME, HOME, AWAY],
    )
    observations = prepare_ball_observations(data, fps=25, max_interpolation_gap_s=0.0)
    smart = SmartEvidence(
        team_prior=np.asarray([AWAY], dtype=np.int8),
        restart=np.zeros(1, dtype=bool),
        dead=np.zeros(1, dtype=bool),
    )

    features = build_features(data, observations, smart, config)
    emission = build_emission(features, config)

    assert features.tracking_candidate.tolist() == [HOME]
    assert features.smart_conflict.tolist() == [True]
    assert emission.probabilities[0, HOME] > emission.probabilities[0, AWAY]


def test_smart_tagging_ablation_config_is_explicit() -> None:
    config = load_candidate_config(NO_SMART_CONFIG_PATH)

    assert config.enable_smart_tagging is False


def test_missing_ball_is_not_dead_by_itself() -> None:
    config = load_candidate_config(CONFIG_PATH)
    data = tracking(
        ball=[[np.nan, np.nan]],
        slots=[[None, None]],
        teams=[HOME, AWAY],
    )
    observations = prepare_ball_observations(data, fps=25, max_interpolation_gap_s=0.0)
    smart = SmartEvidence(
        team_prior=np.asarray([NO_CANDIDATE], dtype=np.int8),
        restart=np.zeros(1, dtype=bool),
        dead=np.zeros(1, dtype=bool),
    )

    features = build_features(data, observations, smart, config)
    emission = build_emission(features, config)

    assert emission.valid.tolist() == [False]
    assert emission.probabilities[0, 2] == pytest.approx(1.0 / 3.0)


def test_split_contest_has_no_forced_team_candidate() -> None:
    config = load_candidate_config(CONFIG_PATH)
    data = tracking(
        ball=[[0.5, 0.5]],
        slots=[[[0.49, 0.5], [0.51, 0.5]]],
        teams=[HOME, AWAY],
    )
    observations = prepare_ball_observations(data, fps=25, max_interpolation_gap_s=0.0)
    smart = SmartEvidence(
        team_prior=np.asarray([NO_CANDIDATE], dtype=np.int8),
        restart=np.zeros(1, dtype=bool),
        dead=np.zeros(1, dtype=bool),
    )

    features = build_features(data, observations, smart, config)
    emission = build_emission(features, config)

    assert features.contested.tolist() == [True]
    assert features.tracking_candidate.tolist() == [NO_CANDIDATE]
    assert emission.valid.tolist() == [False]


def test_out_of_bounds_is_geometric_dead_evidence() -> None:
    config = load_candidate_config(CONFIG_PATH)
    data = tracking(
        ball=[[1.2, 0.5]],
        slots=[[[0.5, 0.5], [0.9, 0.5]]],
        teams=[HOME, AWAY],
    )
    observations = prepare_ball_observations(data, fps=25, max_interpolation_gap_s=0.0)
    smart = SmartEvidence(
        team_prior=np.asarray([NO_CANDIDATE], dtype=np.int8),
        restart=np.zeros(1, dtype=bool),
        dead=np.zeros(1, dtype=bool),
    )

    emission = build_emission(build_features(data, observations, smart, config), config)

    assert emission.probabilities[0, 2] > emission.probabilities[0, HOME]
    assert emission.probabilities[0, 2] > emission.probabilities[0, AWAY]


def test_ball_outside_control_radius_has_no_forced_team_candidate() -> None:
    config = load_candidate_config(CONFIG_PATH)
    data = tracking(
        ball=[[0.5, 0.5]],
        slots=[[[0.9, 0.5], [0.8, 0.5]]],
        teams=[HOME, AWAY],
    )
    observations = prepare_ball_observations(data, fps=25, max_interpolation_gap_s=0.0)
    smart = SmartEvidence(
        team_prior=np.asarray([NO_CANDIDATE], dtype=np.int8),
        restart=np.zeros(1, dtype=bool),
        dead=np.zeros(1, dtype=bool),
    )

    features = build_features(data, observations, smart, config)
    emission = build_emission(features, config)

    assert features.loose_ball.tolist() == [True]
    assert features.tracking_candidate.tolist() == [NO_CANDIDATE]
    assert emission.valid.tolist() == [False]


def test_time_to_ball_favours_closing_team() -> None:
    data = tracking(
        ball=[[0.5, 0.5], [0.5, 0.5]],
        slots=[
            [[0.48, 0.5], [0.52, 0.5]],
            [[0.49, 0.5], [0.53, 0.5]],
        ],
        teams=[HOME, AWAY],
    )
    observations = prepare_ball_observations(data, fps=25, max_interpolation_gap_s=0.0)

    timing = compute_time_to_ball(
        data,
        observations.positions,
        observations.usable_mask,
        fps=25,
        pitch_length_m=105.3,
        pitch_width_m=68.0,
        min_closing_speed_mps=0.5,
        max_time_s=5.0,
    )

    assert timing.valid.tolist() == [False, True]
    assert timing.home_time_s[1] < timing.away_time_s[1]
    assert timing.advantage_s[1] > 0


def test_time_to_ball_invalid_when_ball_is_missing() -> None:
    data = tracking(
        ball=[[np.nan, np.nan], [np.nan, np.nan]],
        slots=[
            [[0.48, 0.5], [0.52, 0.5]],
            [[0.49, 0.5], [0.53, 0.5]],
        ],
        teams=[HOME, AWAY],
    )
    observations = prepare_ball_observations(data, fps=25, max_interpolation_gap_s=0.0)

    timing = compute_time_to_ball(
        data,
        observations.positions,
        observations.usable_mask,
        fps=25,
        pitch_length_m=105.3,
        pitch_width_m=68.0,
        min_closing_speed_mps=0.5,
        max_time_s=5.0,
    )

    assert not timing.valid.any()


def test_pressure_advantage_can_resolve_contested_frame() -> None:
    config = load_candidate_config(PRESSURE_CONFIG_PATH)
    data = tracking(
        ball=[[0.5, 0.5]],
        slots=[
            [
                [0.48, 0.5],
                [0.49, 0.5],
                [0.51, 0.5],
                [0.52, 0.5],
                [0.53, 0.5],
            ]
        ],
        teams=[HOME, HOME, HOME, AWAY, AWAY],
    )
    observations = prepare_ball_observations(data, fps=25, max_interpolation_gap_s=0.0)
    smart = SmartEvidence(
        team_prior=np.asarray([NO_CANDIDATE], dtype=np.int8),
        restart=np.zeros(1, dtype=bool),
        dead=np.zeros(1, dtype=bool),
    )

    features = build_features(data, observations, smart, config)
    emission = build_emission(features, config)

    assert features.contested.tolist() == [True]
    assert features.pressure_advantage_5m.tolist() == [1.0]
    assert emission.probabilities[0, HOME] > emission.probabilities[0, AWAY]


def test_tracking_anomaly_gating_removes_implausible_slot() -> None:
    data = tracking(
        ball=[[0.5, 0.5], [0.5, 0.5]],
        slots=[
            [[0.1, 0.5], [0.53, 0.5]],
            [[0.51, 0.5], [0.53, 0.5]],
        ],
        teams=[HOME, AWAY],
    )
    observations = prepare_ball_observations(data, fps=25, max_interpolation_gap_s=0.0)
    smart = SmartEvidence(
        team_prior=np.full(2, NO_CANDIDATE, dtype=np.int8),
        restart=np.zeros(2, dtype=bool),
        dead=np.zeros(2, dtype=bool),
    )

    main_features = build_features(data, observations, smart, load_candidate_config(CONFIG_PATH))
    quality_features = build_features(
        data,
        observations,
        smart,
        load_candidate_config(QUALITY_CONFIG_PATH),
    )

    assert main_features.tracking_candidate[1] == HOME
    assert quality_features.tracking_anomaly[1]
    assert quality_features.tracking_candidate[1] == AWAY


def test_decoder_direct_team_switch_and_missing_ball_persistence(tmp_path: Path) -> None:
    config = small_config(tmp_path, 40, graded_only=True)
    tracking_candidate = [HOME] * 20 + [AWAY] * 20
    features = features_stub(40, tracking_candidate=tracking_candidate)
    probabilities = [[0.8, 0.1, 0.1]] * 20 + [[0.1, 0.8, 0.1]] * 20
    result = decode(emission_stub(probabilities), features, config)

    assert result.labels[0] == "H"
    assert result.labels[-1] == "A"
    assert "H" in result.labels and "A" in result.labels

    missing = features_stub(
        40,
        tracking_candidate=[HOME] * 15 + [NO_CANDIDATE] * 10 + [HOME] * 15,
    )
    missing_probs = [[0.8, 0.1, 0.1]] * 15 + [[1 / 3, 1 / 3, 1 / 3]] * 10 + [[0.8, 0.1, 0.1]] * 15
    missing_result = decode(
        emission_stub(missing_probs, valid=[True] * 15 + [False] * 10 + [True] * 15),
        missing,
        config,
    )
    assert missing_result.labels[5:35].tolist() == ["H"] * 30


def test_decoder_dead_ball_and_restart(tmp_path: Path) -> None:
    config = small_config(tmp_path, 60, graded_only=True)
    features = features_stub(
        60,
        smart_restart=[False] * 40 + [True] * 20,
        smart_dead=[False] * 20 + [True] * 20 + [False] * 20,
    )
    probabilities = [[0.8, 0.1, 0.1]] * 20 + [[0.1, 0.1, 0.8]] * 20 + [[0.8, 0.1, 0.1]] * 20
    result = decode(emission_stub(probabilities), features, config)

    assert result.labels[25] == "D"
    assert result.labels[-1] == "H"


def test_decoder_does_not_invent_dead_ball_without_dead_evidence(tmp_path: Path) -> None:
    config = small_config(tmp_path, 60, graded_only=True)
    features = features_stub(60, tracking_candidate=[HOME] * 60)
    probabilities = [[0.8, 0.1, 0.1]] * 20 + [[0.05, 0.05, 0.9]] * 20 + [[0.8, 0.1, 0.1]] * 20

    result = decode(emission_stub(probabilities), features, config)

    assert "D" not in result.labels


def test_dead_ball_labels_stay_within_explicit_evidence_halo(tmp_path: Path) -> None:
    config = small_config(tmp_path, 80, graded_only=True)
    features = features_stub(
        80,
        tracking_candidate=[HOME] * 80,
        smart_dead=[False] * 30 + [True] * 20 + [False] * 30,
    )
    probabilities = [[0.8, 0.1, 0.1]] * 30 + [[0.05, 0.05, 0.9]] * 20 + [[0.8, 0.1, 0.1]] * 30

    result = decode(emission_stub(probabilities), features, config)
    dead_frames = np.flatnonzero(result.labels == "D")

    assert dead_frames.size > 0
    assert dead_frames.min() >= 28
    assert dead_frames.max() < 52


def test_dwell_model_preserves_strong_quick_switch(tmp_path: Path) -> None:
    values = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    values["expected_frames"] = 60
    values["ungraded_blocks"] = []
    values["forced_dead_blocks"] = []
    values["parameters"]["emission_smoothing_half_width_frames"]["value"] = 0
    values["parameters"]["dead_smoothing_half_width_frames"]["value"] = 0
    values["parameters"]["dwell_frames"]["value"] = 15
    values["parameters"]["dwell_penalty"]["value"] = 1.5
    path = tmp_path / "dwell.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    config = load_candidate_config(path)
    features = features_stub(60, tracking_candidate=[HOME] * 20 + [AWAY] * 40)
    probabilities = [[0.7, 0.3, 0.0]] * 20 + [[0.01, 0.99, 0.0]] * 40

    result = decode(emission_stub(probabilities), features, config)

    assert result.labels[0] == "H"
    assert result.labels[-1] == "A"


def test_dwell_model_suppresses_weak_state_flicker(tmp_path: Path) -> None:
    values = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    values["expected_frames"] = 60
    values["ungraded_blocks"] = []
    values["forced_dead_blocks"] = []
    values["parameters"]["emission_smoothing_half_width_frames"]["value"] = 0
    values["parameters"]["dead_smoothing_half_width_frames"]["value"] = 0
    values["parameters"]["dwell_frames"]["value"] = 15
    values["parameters"]["dwell_penalty"]["value"] = 1.5
    path = tmp_path / "dwell-weak.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    config = load_candidate_config(path)
    features = features_stub(60, tracking_candidate=[HOME] * 60)
    probabilities = [[0.6, 0.4, 0.0]] * 40 + [[0.35, 0.65, 0.0]] * 5 + [[0.6, 0.4, 0.0]] * 15

    result = decode(emission_stub(probabilities), features, config)

    assert "A" not in result.labels


def test_dwell_penalty_does_not_block_dead_ball_transition(tmp_path: Path) -> None:
    values = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    values["expected_frames"] = 60
    values["ungraded_blocks"] = []
    values["forced_dead_blocks"] = []
    values["parameters"]["emission_smoothing_half_width_frames"]["value"] = 0
    values["parameters"]["dead_smoothing_half_width_frames"]["value"] = 0
    values["parameters"]["dwell_frames"]["value"] = 15
    values["parameters"]["dwell_penalty"]["value"] = 2.5
    path = tmp_path / "dwell-dead.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    config = load_candidate_config(path)
    features = features_stub(
        60,
        smart_dead=[False] * 20 + [True] * 20 + [False] * 20,
        smart_restart=[False] * 40 + [True] * 20,
    )
    probabilities = [[0.8, 0.1, 0.1]] * 20 + [[0.05, 0.05, 0.9]] * 20 + [[0.8, 0.1, 0.1]] * 20

    result = decode(emission_stub(probabilities), features, config)

    assert "D" in result.labels
    assert result.labels[-1] == "H"


def test_evidence_hysteresis_allows_strong_switch_and_suppresses_weak_flicker(
    tmp_path: Path,
) -> None:
    values = json.loads(HYSTERESIS_CONFIG_PATH.read_text(encoding="utf-8"))
    values["expected_frames"] = 60
    values["ungraded_blocks"] = []
    values["forced_dead_blocks"] = []
    values["parameters"]["emission_smoothing_half_width_frames"]["value"] = 0
    values["parameters"]["dead_smoothing_half_width_frames"]["value"] = 0
    path = tmp_path / "hysteresis.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    config = load_candidate_config(path)
    features = features_stub(60, tracking_candidate=[HOME] * 60)

    strong = [[0.55, 0.45, 0.0]] * 20 + [[0.05, 0.95, 0.0]] * 40
    strong_result = decode(emission_stub(strong), features, config)
    assert strong_result.labels[-1] == "A"

    weak = [[0.55, 0.45, 0.0]] * 20 + [[0.4, 0.6, 0.0]] * 5 + [[0.55, 0.45, 0.0]] * 35
    weak_result = decode(emission_stub(weak), features, config)
    assert "A" not in weak_result.labels


def test_decoder_respects_ungraded_and_forced_blocks(tmp_path: Path) -> None:
    values = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    values["expected_frames"] = 40
    values["ungraded_blocks"] = [[0, 4], [35, 39]]
    values["forced_dead_blocks"] = [[10, 14]]
    values["parameters"]["emission_smoothing_half_width_frames"]["value"] = 2
    values["parameters"]["dead_smoothing_half_width_frames"]["value"] = 2
    path = tmp_path / "forced.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    config = load_candidate_config(path)
    features = features_stub(40, tracking_candidate=[HOME] * 40)
    result = decode(emission_stub([[0.8, 0.1, 0.1]] * 40), features, config)

    assert result.labels[:5].tolist() == ["X"] * 5
    assert result.labels[-5:].tolist() == ["X"] * 5
    assert result.labels[10:15].tolist() == ["D"] * 5


def test_low_confidence_short_segments_are_filtered(tmp_path: Path) -> None:
    config = small_config(tmp_path, 25, graded_only=True)
    labels = np.asarray(["H"] * 10 + ["D"] * 5 + ["H"] * 10, dtype="<U1")
    confidence = np.full(25, 0.8, dtype=np.float64)
    confidence[10:15] = 0.4
    _filter_low_confidence_short_segments(
        labels,
        confidence,
        np.zeros(25, dtype=bool),
        config,
    )
    assert "D" not in labels

    labels = np.asarray(["H"] * 10 + ["A"] * 5 + ["H"] * 10, dtype="<U1")
    confidence = np.full(25, 0.8, dtype=np.float64)
    confidence[10:15] = 0.4
    _filter_low_confidence_short_segments(
        labels,
        confidence,
        np.zeros(25, dtype=bool),
        config,
    )
    assert "A" not in labels


def test_high_confidence_short_segment_is_preserved(tmp_path: Path) -> None:
    config = small_config(tmp_path, 25, graded_only=True)
    labels = np.asarray(["H"] * 10 + ["A"] * 5 + ["H"] * 10, dtype="<U1")
    confidence = np.full(25, 0.9, dtype=np.float64)
    _filter_low_confidence_short_segments(
        labels,
        confidence,
        np.zeros(25, dtype=bool),
        config,
    )
    assert labels[10:15].tolist() == ["A"] * 5


def test_smart_tagging_restart_and_dead_windows_do_not_overlap(tmp_path: Path) -> None:
    source = tmp_path / "tagging-window.xml"
    source.write_text(
        """
        <file><ALL_INSTANCES>
          <instance>
            <start>4.0</start><end>14.0</end><code>SET PIECES</code>
            <label><group>Team</group><text>Barcelona</text></label>
          </instance>
        </ALL_INSTANCES></file>
        """,
        encoding="utf-8",
    )
    frame_count = 400
    positions = np.full((frame_count, 2), np.nan, dtype=np.float32)
    positions[100:, 0] = 0.5
    positions[100:, 1] = 0.5
    observations = prepare_ball_observations(
        tracking(
            ball=positions.tolist(),
            slots=[[[0.5, 0.5], [0.8, 0.5]] for _ in range(frame_count)],
            teams=[HOME, AWAY],
        ),
        fps=25,
        max_interpolation_gap_s=0.0,
    )
    tags = load_tags(source, fps=25, frame_count=frame_count)
    evidence = build_smart_evidence(
        frame_count,
        tags,
        observations,
        fps=25,
        pitch_length_m=105.3,
        pitch_width_m=68.0,
        restart_offset_s=4.0,
        dead_lookback_s=30.0,
        dead_speed_mps=1.0,
        dead_gap_s=0.5,
    )

    restart_frame = 200
    assert evidence.dead[:restart_frame].any()
    assert not evidence.restart[:restart_frame].any()
    assert evidence.restart[restart_frame:250].all()


def test_adapter_end_to_end_and_deterministic(tmp_path: Path) -> None:
    root = make_data_root(
        tmp_path / "data",
        records=[[(0.10, 0.10), (0.40, 0.40), (0.90, 0.90), (0.80, 0.80)] for _ in range(30)],
        ball=[(0.12, 0.10)] * 30,
    )
    (root / "tactical" / "BAR-ATH_tactical_smart_tagging.xml").write_text(
        """
        <file><ALL_INSTANCES>
          <instance>
            <start>0.0</start><end>1.2</end><code>BUILD UP</code>
            <label><group>Team</group><text>Barcelona</text></label>
          </instance>
        </ALL_INSTANCES></file>
        """,
        encoding="utf-8",
    )
    values = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    values["expected_frames"] = 30
    values["ungraded_blocks"] = [[0, 4], [25, 29]]
    values["forced_dead_blocks"] = []
    values["parameters"]["emission_smoothing_half_width_frames"]["value"] = 2
    values["parameters"]["dead_smoothing_half_width_frames"]["value"] = 2
    config_path = tmp_path / "small-config.json"
    config_path.write_text(json.dumps(values), encoding="utf-8")

    first = build_candidate(
        output_path=tmp_path / "first.csv",
        data_root=root,
        config_path=config_path,
        decision_log=tmp_path / "decision-log.csv",
    )
    second = build_candidate(
        output_path=tmp_path / "second.csv",
        data_root=root,
        config_path=config_path,
    )

    assert first.health["rows"] == 30
    assert first.health["validator_status"] == "pass"
    assert first.health["output_sha256"] == second.health["output_sha256"]
    assert first.health["generalisation"] == "GENERALISATION NOT ESTABLISHED"
    decision_lines = (tmp_path / "decision-log.csv").read_text(encoding="utf-8").splitlines()
    assert len(decision_lines) == 31
    assert decision_lines[0].startswith("frame,label,")
