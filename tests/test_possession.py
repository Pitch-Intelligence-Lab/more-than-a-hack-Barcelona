import numpy as np

from mtah_possession.data.tracking import FrameAlignment, TrackingData
from mtah_possession.features.ball import AWAY, HOME, NO_CANDIDATE, nearest_team_candidates
from mtah_possession.features.possession import majority_vote_labels


def tracking(
    *,
    ball: list[list[float | None]],
    slots: list[list[list[float | None]]],
    teams: list[int],
) -> TrackingData:
    count = len(ball)
    ball_array = np.asarray(
        [[np.nan if value is None else value for value in row] for row in ball],
        dtype=np.float32,
    )
    slot_array = np.asarray(
        [
            [[np.nan if value is None else value for value in point] for point in frame]
            for frame in slots
        ],
        dtype=np.float32,
    )
    return TrackingData(
        frame_count=count,
        home_team="H",
        away_team="A",
        team_by_slot=np.asarray(teams, dtype=np.int8),
        ball_positions=ball_array,
        slot_positions=slot_array,
        alignment=FrameAlignment(count, 1, count, True),
    )


def test_metric_distance_handles_non_square_pitch() -> None:
    data = tracking(
        ball=[[0.5, 0.5]],
        slots=[[[0.55, 0.5], [0.5, 0.55]]],
        teams=[HOME, AWAY],
    )
    result = nearest_team_candidates(data, pitch_length_m=105.3, pitch_width_m=68.0)
    assert result.tolist() == [AWAY]


def test_equal_home_and_away_distance_is_no_candidate() -> None:
    data = tracking(
        ball=[[0.5, 0.5]],
        slots=[[[0.25, 0.5], [0.75, 0.5]]],
        teams=[HOME, AWAY],
    )
    result = nearest_team_candidates(data, pitch_length_m=100.0, pitch_width_m=60.0)
    assert result.tolist() == [NO_CANDIDATE]


def test_missing_ball_and_missing_players_are_no_candidate() -> None:
    data = tracking(
        ball=[[None, None], [0.5, 0.5]],
        slots=[
            [[0.1, 0.1], [0.9, 0.9]],
            [[None, None], [None, None]],
        ],
        teams=[HOME, AWAY],
    )
    result = nearest_team_candidates(data, pitch_length_m=105.0, pitch_width_m=68.0)
    assert result.tolist() == [NO_CANDIDATE, NO_CANDIDATE]


def test_missing_slot_does_not_hide_other_visible_players() -> None:
    data = tracking(
        ball=[[0.5, 0.5]],
        slots=[[[None, None], [0.51, 0.5], [0.8, 0.8]]],
        teams=[HOME, HOME, AWAY],
    )
    result = nearest_team_candidates(data, pitch_length_m=105.0, pitch_width_m=68.0)
    assert result.tolist() == [HOME]


def test_team_mapping_uses_metadata_slots() -> None:
    data = tracking(
        ball=[[0.5, 0.5], [0.5, 0.5]],
        slots=[
            [[0.51, 0.5], [0.1, 0.1]],
            [[0.1, 0.1], [0.51, 0.5]],
        ],
        teams=[AWAY, HOME],
    )
    result = nearest_team_candidates(data, pitch_length_m=105.0, pitch_width_m=68.0)
    assert result.tolist() == [AWAY, HOME]


def test_majority_vote_preserves_frame_count_and_output_domain() -> None:
    candidates = np.asarray([HOME, HOME, AWAY, NO_CANDIDATE, NO_CANDIDATE], dtype=np.int8)
    labels = majority_vote_labels(candidates, window_half_width_frames=2)
    assert labels.tolist() == ["H", "H", "H", "D", "A"]
    assert labels.shape == candidates.shape
    assert set(labels).issubset(set("HADX"))


def test_ties_and_no_votes_become_dead_ball() -> None:
    candidates = np.asarray([HOME, AWAY, NO_CANDIDATE], dtype=np.int8)
    labels = majority_vote_labels(candidates, window_half_width_frames=1)
    assert labels.tolist() == ["D", "D", "A"]
