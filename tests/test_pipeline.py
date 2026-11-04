import json
from pathlib import Path

from helpers import make_data_root

from mtah_possession.pipeline.build_submission import build_submission, main
from mtah_possession.validation.submission import validate_submission


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

    _, labels, first_report = build_submission(
        output_path=first,
        data_root=root,
        config_path=config,
    )
    _, _, second_report = build_submission(
        output_path=second,
        data_root=root,
        config_path=config,
    )

    assert labels.tolist() == ["H", "H"]
    assert first_report.rows == 2
    assert first_report.sha256 == second_report.sha256
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
