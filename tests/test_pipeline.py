import json
from pathlib import Path

from helpers import make_data_root

from mtah_possession.pipeline.build_submission import build_submission, main
from mtah_possession.validation.submission import validate_submission

ROOT = Path(__file__).resolve().parents[1]


def make_config(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "expected_frames": 2,
                "window_half_width_frames": 0,
                "pitch_length_m": 105.3,
                "pitch_width_m": 68.0,
            }
        ),
        encoding="utf-8",
    )
    return path


def make_root(tmp_path: Path) -> Path:
    return make_data_root(
        tmp_path / "data",
        records=[
            [(0.10, 0.10), (0.40, 0.40), (0.90, 0.90), (0.80, 0.80)],
            [(0.40, 0.40), (0.10, 0.10), (0.80, 0.80), (0.90, 0.90)],
        ],
        ball=[(0.12, 0.10), (0.12, 0.10)],
    )


def test_end_to_end_build_and_repeatable_hash(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    config = make_config(tmp_path / "config.json")
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"

    first_result = build_submission(
        output_path=first,
        data_root=root,
        config_path=config,
    )
    second_result = build_submission(
        output_path=second,
        data_root=root,
        config_path=config,
    )

    assert first_result.labels.tolist() == ["H", "H"]
    assert first_result.validation.rows == 2
    assert first_result.validation.sha256 == second_result.validation.sha256
    assert first.read_bytes() == second.read_bytes()


def test_cli_overwrite_requires_force(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    config = make_config(tmp_path / "config.json")
    output = tmp_path / "submission.csv"
    arguments = [
        "--output",
        str(output),
        "--config",
        str(config),
        "--data-dir",
        str(root),
    ]

    assert main(arguments) == 0
    assert validate_submission(output, expected_rows=2).rows == 2
    assert main(arguments) == 1
    assert main([*arguments, "--force"]) == 0


def test_state_engine_end_to_end_reports_quality_and_segments(tmp_path: Path) -> None:
    root = make_data_root(
        tmp_path / "state-data",
        records=[[(0.10, 0.10), (0.40, 0.40), (0.90, 0.90), (0.80, 0.80)] for _ in range(30)],
        ball=[(0.12, 0.10)] * 30,
    )
    values = json.loads((ROOT / "configs" / "state-engine.json").read_text(encoding="utf-8"))
    values["expected_frames"] = 30
    values["ungraded_blocks"] = [[0, 4], [25, 29]]
    config = tmp_path / "state-config.json"
    config.write_text(json.dumps(values), encoding="utf-8")

    result = build_submission(
        output_path=tmp_path / "state-submission.csv",
        data_root=root,
        config_path=config,
    )
    repeated = build_submission(
        output_path=tmp_path / "state-submission-repeat.csv",
        data_root=root,
        config_path=config,
    )

    assert result.validation.rows == 30
    assert result.labels[:5].tolist() == ["X"] * 5
    assert result.labels[-5:].tolist() == ["X"] * 5
    assert result.health.label_counts == {"H": 20, "A": 0, "D": 0, "X": 10}
    assert result.health.segments_by_label == {"H": 1, "A": 0, "D": 0}
    assert result.health.observation_quality_counts == {
        "observed": 30,
        "interpolated": 0,
        "missing": 0,
    }
    assert result.health.graded_observation_quality_counts["observed"] == 20
    assert result.health.transition_counts == {}
    assert result.evidence is not None
    assert set(result.health.input_sha256) == {"atd_meta", "atd_raw"}
    assert result.health.validator_status == "pass"
    assert result.validation.sha256 == repeated.validation.sha256
