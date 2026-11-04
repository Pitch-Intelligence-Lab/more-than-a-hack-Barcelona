from pathlib import Path

import numpy as np
import pytest
from helpers import make_data_root

from mtah_possession.data.tracking import TrackingDataError, load_tactical_tracking


def test_loads_metadata_raw_tracking_and_zero_based_frames(tmp_path: Path) -> None:
    root = make_data_root(
        tmp_path,
        records=[
            [(0.1, 0.1), (0.2, 0.2), (0.8, 0.8), (0.9, 0.9)],
            [(0.3, 0.4), (0.4, 0.5), (0.6, 0.6), (0.7, 0.7)],
        ],
        ball=[(0.15, 0.15), None],
    )
    tracking = load_tactical_tracking(root, expected_frames=2)

    assert tracking.frame_count == 2
    assert tracking.home_team == "Home FC"
    assert tracking.away_team == "Away FC"
    assert tracking.team_by_slot.tolist() == [0, 0, 1, 1]
    assert tracking.alignment.first_frame_id == 1
    assert tracking.alignment.video_frame_range == (0, 1)
    assert tracking.ball_visible.tolist() == [True, False]
    np.testing.assert_allclose(tracking.ball_positions[0], [0.15, 0.15], atol=1e-6)


def test_missing_player_values_are_nan(tmp_path: Path) -> None:
    root = make_data_root(
        tmp_path,
        records=[[(0.1, 0.1), (float("nan"), float("nan")), (0.8, 0.8), (0.9, 0.9)]],
        ball=[None],
    )
    path = root / "tactical" / "BAR-ATH_tactical_atd.txt"
    path.write_text("1:0.1,0.1,1;NaN,NaN,0;0.8,0.8,1;0.9,0.9,1:NaN,NaN,0\n", encoding="utf-8")
    tracking = load_tactical_tracking(root, expected_frames=1)
    assert tracking.player_visible.tolist() == [[True, False, True, True]]


def test_wrong_slot_count_is_rejected(tmp_path: Path) -> None:
    root = make_data_root(
        tmp_path,
        records=[[(0.1, 0.1), (0.8, 0.8)]],
        ball=[(0.1, 0.1)],
    )
    with pytest.raises(TrackingDataError, match="metadata expects 4"):
        load_tactical_tracking(root, expected_frames=1)


def test_non_contiguous_frame_ids_are_rejected(tmp_path: Path) -> None:
    root = make_data_root(
        tmp_path,
        records=[
            [(0.1, 0.1), (0.2, 0.2), (0.8, 0.8), (0.9, 0.9)],
            [(0.1, 0.1), (0.2, 0.2), (0.8, 0.8), (0.9, 0.9)],
        ],
        ball=[None, None],
    )
    path = root / "tactical" / "BAR-ATH_tactical_atd.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1] = "3" + lines[1][1:]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(TrackingDataError, match="frame alignment failed"):
        load_tactical_tracking(root, expected_frames=2)


def test_truncated_tracking_is_rejected(tmp_path: Path) -> None:
    root = make_data_root(
        tmp_path,
        records=[[(0.1, 0.1), (0.2, 0.2), (0.8, 0.8), (0.9, 0.9)]],
        ball=[None],
    )
    with pytest.raises(TrackingDataError, match="has 1 records; expected 2"):
        load_tactical_tracking(root, expected_frames=2)
