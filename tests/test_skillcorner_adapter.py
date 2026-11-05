import hashlib
import json
from pathlib import Path

from mtah_possession.data.skillcorner import load_skillcorner_match


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_synthetic_skillcorner_fixture_loads_without_external_dependencies(
    tmp_path: Path,
) -> None:
    root = tmp_path / "external"
    root.mkdir()
    (root / "LICENSE").write_text("MIT fixture", encoding="utf-8")
    (root / "README.md").write_text("fixture", encoding="utf-8")
    match = {
        "id": 99,
        "home_team": {"id": 1, "short_name": "Home"},
        "away_team": {"id": 2, "short_name": "Away"},
        "match_periods": [{"period": 1, "start_frame": 0, "end_frame": 3}],
        "players": [
            {"id": 101, "trackable_object": 1010, "team_id": 1},
            {"id": 201, "trackable_object": 2010, "team_id": 2},
        ],
    }
    (root / "match.json").write_text(json.dumps(match), encoding="utf-8")
    tracking_lines = [
        {
            "frame": 0,
            "ball_data": {"x": 0.0, "y": 0.0, "z": 0.0, "is_detected": True},
            "possession": {"player_id": 101, "group": "home team"},
            "player_data": [{"player_id": 101, "x": 1.0, "y": 0.0, "is_detected": True}],
        },
        {
            "frame": 1,
            "ball_data": {"x": 0.0, "y": 0.0, "z": 0.0, "is_detected": True},
            "possession": {"player_id": None, "group": None},
            "player_data": [{"player_id": 201, "x": 1.0, "y": 0.0, "is_detected": True}],
        },
    ]
    (root / "tracking.jsonl").write_text(
        "\n".join(json.dumps(row) for row in tracking_lines) + "\n",
        encoding="utf-8",
    )
    (root / "phases.csv").write_text(
        "frame_start,frame_end,period,team_in_possession_id,team_in_possession_phase_type\n"
        "1,3,1,1,build_up\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "1.0",
        "provider": "skillcorner",
        "repository": "fixture",
        "commit": "fixture",
        "license": "MIT",
        "license_file": "LICENSE",
        "license_sha256": sha(root / "LICENSE"),
        "readme_sha256": sha(root / "README.md"),
        "retrieval_date": "2026-11-05",
        "match_id": "99",
        "fps": 10,
        "home_team_id": 1,
        "away_team_id": 2,
        "pitch_length_m": 105.0,
        "pitch_width_m": 68.0,
        "coordinate_convention": "metres-center-origin",
        "files": {
            "tracking": {"path": "tracking.jsonl", "sha256": sha(root / "tracking.jsonl")},
            "phases": {"path": "phases.csv", "sha256": sha(root / "phases.csv")},
            "match": {"path": "match.json", "sha256": sha(root / "match.json")},
        },
    }
    config = tmp_path / "manifest.json"
    config.write_text(json.dumps(manifest), encoding="utf-8")

    loaded = load_skillcorner_match(config, root)
    assert loaded.match_id == "99"
    assert loaded.frame_count == 3
    assert loaded.player_ids == (101, 201)
    assert loaded.possession_side.tolist() == [0, -1, -1]
    assert loaded.possession_status.tolist() == [0, 1, 1]
    assert loaded.ball_detected.tolist() == [True, True, False]
    assert loaded.frame_present.tolist() == [True, True, False]
    assert len(loaded.phases) == 1
