from dataclasses import replace
from pathlib import Path

import numpy as np

from mtah_possession.algorithm_config import load_algorithm_config
from mtah_possession.features.ball import AWAY, HOME, NO_CANDIDATE
from mtah_possession.features.evidence import (
    BallMotionEvidence,
    EvidenceSeries,
    NearestTeamEvidence,
    NearPlayerVoteEvidence,
    ReachabilityEvidence,
    frame_block_mask,
)
from mtah_possession.states.cleanup import apply_structural_cleanup
from mtah_possession.states.possession_state import run_state_engine

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_algorithm_config(ROOT / "configs" / "state-engine.json")


def evidence(
    candidates: list[int],
    *,
    dead: list[bool] | None = None,
    ungraded: list[bool] | None = None,
    speeds: list[float] | None = None,
    restart: list[bool] | None = None,
    forced_dead: list[bool] | None = None,
) -> EvidenceSeries:
    count = len(candidates)
    candidate_array = np.asarray(candidates, dtype=np.int8)
    zeros_float = np.zeros(count, dtype=np.float64)
    zeros_votes = np.zeros(count, dtype=np.int16)
    return EvidenceSeries(
        nearest=NearestTeamEvidence(
            candidate_array,
            zeros_float.copy(),
            zeros_float.copy(),
            zeros_float.copy(),
        ),
        near_player_vote=NearPlayerVoteEvidence(
            candidate_array.copy(),
            zeros_votes,
            zeros_votes.copy(),
        ),
        ball_motion=BallMotionEvidence(
            np.asarray(speeds if speeds is not None else [np.nan] * count),
            zeros_float.copy(),
            np.zeros(count, dtype=bool),
        ),
        restart_zone_distance_m=zeros_float.copy(),
        reachability=ReachabilityEvidence(zeros_float.copy(), zeros_float.copy()),
        team_candidate=candidate_array,
        dead_ball_evidence=np.asarray(dead or [False] * count, dtype=bool),
        restart_evidence=np.asarray(restart or [False] * count, dtype=bool),
        forced_dead_mask=np.asarray(forced_dead or [False] * count, dtype=bool),
        ungraded_mask=np.asarray(ungraded or [False] * count, dtype=bool),
    )


def test_short_ball_occlusion_preserves_current_possession() -> None:
    candidates = [HOME] * 25 + [NO_CANDIDATE] * 5 + [HOME] * 10
    result = run_state_engine(evidence(candidates), CONFIG)
    assert "A" not in result.labels
    assert result.labels[24:35].tolist() == ["H"] * 11


def test_long_missing_ball_without_dead_evidence_preserves_state() -> None:
    candidates = [HOME] * 25 + [NO_CANDIDATE] * 200
    result = run_state_engine(evidence(candidates), CONFIG)
    assert result.labels[-1] == "H"


def test_direct_home_to_away_does_not_require_dead_ball() -> None:
    candidates = [HOME] * 30 + [AWAY] * 30
    result = run_state_engine(evidence(candidates), CONFIG)
    assert "H->A" in {f"{item.previous}->{item.current}" for item in result.transitions}
    assert "D" not in result.labels


def test_direct_away_to_home_does_not_require_dead_ball() -> None:
    candidates = [AWAY] * 30 + [HOME] * 30
    result = run_state_engine(evidence(candidates), CONFIG)
    assert "A->H" in {f"{item.previous}->{item.current}" for item in result.transitions}
    assert "D" not in result.labels


def test_dead_ball_interval_and_restart() -> None:
    candidates = [HOME] * 30 + [NO_CANDIDATE] * 30 + [AWAY] * 30
    dead = [False] * 30 + [True] * 30 + [False] * 30
    result = run_state_engine(evidence(candidates, dead=dead), CONFIG)
    assert result.labels[29] == "H"
    assert result.labels[49] == "D"
    assert result.labels[-1] == "A"
    assert "D->A" in {f"{item.previous}->{item.current}" for item in result.transitions}


def test_rapid_one_frame_pass_near_opponent_does_not_switch() -> None:
    candidates = [HOME] * 30 + [AWAY] + [HOME] * 30
    speeds = [0.2] * 30 + [25.0] + [0.2] * 30
    result = run_state_engine(evidence(candidates, speeds=speeds), CONFIG)
    assert set(result.labels) == {"H"}


def test_fps_changes_confirmation_frames_but_not_seconds() -> None:
    config_10_fps = replace(CONFIG, fps=10)
    candidates = [HOME] * 10 + [AWAY] * 10
    result = run_state_engine(evidence(candidates), config_10_fps)
    assert result.labels[16] == "H"
    assert result.labels[17] == "A"


def test_ungraded_frames_are_x_and_reset_temporal_state() -> None:
    candidates = [HOME] * 30
    ungraded = [True] * 5 + [False] * 20 + [True] * 5
    result = run_state_engine(evidence(candidates, ungraded=ungraded), CONFIG)
    assert result.labels[:5].tolist() == ["X"] * 5
    assert result.labels[-5:].tolist() == ["X"] * 5
    assert set(result.labels[5:25]) == {"H"}


def test_short_team_flicker_is_cleaned_but_d_is_preserved() -> None:
    labels = np.asarray(list("HHAAHH"), dtype="<U1")
    result = apply_structural_cleanup(labels, CONFIG)
    assert result.labels.tolist() == list("HHHHHH")
    assert result.removed_label_counts == {"H": 0, "A": 2, "D": 0}


def test_default_cleanup_preserves_h_d_h_and_a_d_a() -> None:
    labels = np.asarray(list("HDHADAH"), dtype="<U1")
    result = apply_structural_cleanup(labels, CONFIG)
    assert result.labels.tolist() == labels.tolist()
    assert result.removed_label_counts["D"] == 0


def test_optional_isolated_d_cleanup_records_removed_d_frames() -> None:
    parameters = dict(CONFIG.parameters)
    isolated = parameters["enable_isolated_dead_ball_cleanup"]
    parameters["enable_isolated_dead_ball_cleanup"] = replace(isolated, value=True)
    enabled = replace(CONFIG, parameters=parameters)
    labels = np.asarray(list("HDDH"), dtype="<U1")
    result = apply_structural_cleanup(labels, enabled)
    assert result.labels.tolist() == list("HHHH")
    assert result.removed_label_counts["D"] == 2


def test_cleanup_never_bridges_x_boundaries() -> None:
    labels = np.asarray(list("HHXDXHH"), dtype="<U1")
    result = apply_structural_cleanup(labels, CONFIG)
    assert result.labels.tolist() == list("HHXDXHH")


def test_forced_dead_block_is_d_and_resets_restart_state() -> None:
    candidates = [HOME, HOME, NO_CANDIDATE, NO_CANDIDATE] + [HOME] * 20
    forced = [False, False, True, True] + [False] * 20
    result = run_state_engine(evidence(candidates, forced_dead=forced), CONFIG)
    assert result.labels[1] == "H"
    assert result.labels[2] == "D"
    assert result.labels[3] == "D"
    assert result.labels[4:13].tolist() == ["D"] * 9
    assert result.labels[13] == "H"
    forced_reasons = [item for item in result.transitions if item.reason == "forced_dead_block"]
    assert len(forced_reasons) == 1


def test_restart_evidence_shortens_d_to_team_confirmation() -> None:
    candidates = [NO_CANDIDATE] * 5 + [HOME] * 20
    forced = [True] * 5 + [False] * 20
    with_evidence = run_state_engine(
        evidence(candidates, forced_dead=forced, restart=[False] * 5 + [True] * 20),
        CONFIG,
    )
    without_evidence = run_state_engine(
        evidence(candidates, forced_dead=forced, restart=[False] * 25),
        CONFIG,
    )
    assert with_evidence.labels[9] == "H"
    assert with_evidence.labels[8] == "D"
    assert without_evidence.labels[12] == "D"
    assert without_evidence.labels[14] == "H"


def test_cleanup_cannot_remove_protected_forced_dead_block() -> None:
    parameters = dict(CONFIG.parameters)
    isolated = parameters["enable_isolated_dead_ball_cleanup"]
    parameters["enable_isolated_dead_ball_cleanup"] = replace(isolated, value=True)
    enabled = replace(CONFIG, parameters=parameters)
    labels = np.asarray(list("HDDH"), dtype="<U1")
    protected = np.asarray([False, True, True, False])
    result = apply_structural_cleanup(labels, enabled, protected_mask=protected)
    assert result.labels.tolist() == list("HDDH")
    assert result.removed_label_counts["D"] == 0


def test_official_second_half_boundary_uses_real_frame_numbers() -> None:
    frame_count = CONFIG.expected_frames
    candidates = np.full(frame_count, NO_CANDIDATE, dtype=np.int8)
    candidates[113_742:] = HOME
    ungraded = frame_block_mask(frame_count, CONFIG.ungraded_blocks)
    forced_dead = frame_block_mask(frame_count, CONFIG.forced_dead_blocks)
    result = run_state_engine(
        evidence(
            candidates.tolist(),
            ungraded=ungraded.tolist(),
            forced_dead=forced_dead.tolist(),
        ),
        CONFIG,
    )
    assert result.labels[110_807] == "X"
    assert result.labels[110_808] == "D"
    assert result.labels[113_741] == "D"
    assert result.labels[113_742] == "D"
    assert result.labels[113_751] == "H"
    cleaned = apply_structural_cleanup(
        result.labels,
        CONFIG,
        protected_mask=forced_dead,
    )
    assert np.all(cleaned.labels[110_808:113_742] == "D")
