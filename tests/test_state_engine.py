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
        restart_evidence=np.ones(count, dtype=bool),
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


def test_short_flicker_is_cleaned_but_distinct_neighbors_are_preserved() -> None:
    labels = np.asarray(list("HHHDDHHH") + ["A"] * 20 + list("HHH"), dtype="<U1")
    result = apply_structural_cleanup(labels, CONFIG)
    assert result.labels[3:5].tolist() == ["H", "H"]
    assert result.labels[8:28].tolist() == ["A"] * 20


def test_cleanup_never_bridges_x_boundaries() -> None:
    labels = np.asarray(list("HHXDXHH"), dtype="<U1")
    result = apply_structural_cleanup(labels, CONFIG)
    assert result.labels.tolist() == list("HHXDXHH")
