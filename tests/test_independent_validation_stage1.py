from __future__ import annotations

from pathlib import Path

import numpy as np

from scripts.audit_soccertrack_one_match import _sequence_stats, audit_ball


def test_sequence_stats_reports_gaps_and_duplicates() -> None:
    assert _sequence_stats(np.asarray([1, 2, 4, 4, 7])) == {
        "count": 5,
        "unique": 4,
        "duplicates": 1,
        "min": 1,
        "max": 7,
        "gaps": 2,
        "missing_values": 3,
        "max_gap": 2,
    }


def test_ball_audit_supports_fixture_npz(tmp_path: Path) -> None:
    path = tmp_path / "ball.npz"
    np.savez(
        path,
        frame=np.asarray([1, 2, 4], dtype=np.int32),
        x=np.asarray([0.0, 1.0, np.nan], dtype=np.float32),
        y=np.asarray([0.0, 1.0, 2.0], dtype=np.float32),
        status=np.asarray([0, 1, 1], dtype=np.int8),
        y_flipped=np.asarray(False),
    )
    result = audit_ball(path)
    assert result["members"]["frame"] == {"shape": [3], "dtype": "int32"}
    assert result["frames"]["gaps"] == 1
    assert result["status_counts"] == {"0": 1, "1": 2}
    assert result["x"]["invalid"] == 1
