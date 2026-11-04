"""Build and atomically replace a validated tactical possession CSV."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mtah_possession.config import (
    ConfigurationError,
    load_settings,
    require_tactical_assets,
)
from mtah_possession.data.tracking import TrackingData, TrackingDataError, load_tactical_tracking
from mtah_possession.features.ball import nearest_team_candidates
from mtah_possession.features.possession import majority_vote_labels
from mtah_possession.validation.submission import (
    SubmissionValidationError,
    validate_submission,
)

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "baseline.json"


class BuildError(RuntimeError):
    """Raised when a submission cannot be built safely."""


@dataclass(frozen=True)
class AlgorithmConfig:
    expected_frames: int
    window_half_width_frames: int
    pitch_length_m: float
    pitch_width_m: float

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> AlgorithmConfig:
        required = {
            "expected_frames",
            "window_half_width_frames",
            "pitch_length_m",
            "pitch_width_m",
        }
        missing = required.difference(values)
        unknown = set(values).difference(required)
        if missing:
            raise BuildError(f"configuration is missing keys: {sorted(missing)}")
        if unknown:
            raise BuildError(f"configuration has unknown keys: {sorted(unknown)}")

        try:
            expected_frames = int(values["expected_frames"])
            window = int(values["window_half_width_frames"])
            length = float(values["pitch_length_m"])
            width = float(values["pitch_width_m"])
        except (TypeError, ValueError) as error:
            raise BuildError("configuration values must be numeric") from error
        if expected_frames <= 0:
            raise BuildError("expected_frames must be positive")
        if window < 0:
            raise BuildError("window_half_width_frames must be non-negative")
        if length <= 0 or width <= 0:
            raise BuildError("pitch dimensions must be positive")
        return cls(expected_frames, window, length, width)


def load_algorithm_config(path: str | os.PathLike[str]) -> AlgorithmConfig:
    config_path = Path(path)
    try:
        values = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BuildError(f"could not read configuration at {config_path}") from error
    if not isinstance(values, dict):
        raise BuildError("configuration root must be a JSON object")
    return AlgorithmConfig.from_mapping(values)


def build_labels(tracking: TrackingData, config: AlgorithmConfig):
    if tracking.frame_count != config.expected_frames:
        raise BuildError(
            f"tracking has {tracking.frame_count} frames; "
            f"configuration expects {config.expected_frames}"
        )
    candidates = nearest_team_candidates(
        tracking,
        pitch_length_m=config.pitch_length_m,
        pitch_width_m=config.pitch_width_m,
    )
    return majority_vote_labels(
        candidates,
        window_half_width_frames=config.window_half_width_frames,
    )


def _write_rows(handle, labels) -> None:
    handle.write("frame,label\n")
    for frame, label in enumerate(labels):
        handle.write(f"{frame},{label}\n")


def write_submission_atomic(
    output_path: str | os.PathLike[str],
    labels,
    *,
    expected_frames: int,
):
    """Validate a sibling temporary file, then replace the destination."""

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            _write_rows(handle, labels)
            handle.flush()
            os.fsync(handle.fileno())
        validate_submission(temporary_path, expected_rows=expected_frames)
        os.replace(temporary_path, destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return destination


def _confirm_overwrite(path: Path, force: bool) -> None:
    if not path.exists() or force:
        return
    if not sys.stdin.isatty():
        raise BuildError(f"output already exists: {path}; rerun with --force to replace it")
    answer = input(f"Output exists at {path}. Replace it? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        raise BuildError("overwrite declined")


def build_submission(
    *,
    output_path: str | os.PathLike[str],
    data_root: str | os.PathLike[str] | None = None,
    config_path: str | os.PathLike[str] = DEFAULT_CONFIG_PATH,
):
    config = load_algorithm_config(config_path)
    settings = load_settings(data_root)
    require_tactical_assets(settings, ("atd_meta", "atd_raw"))
    tracking = load_tactical_tracking(
        settings.root,
        expected_frames=config.expected_frames,
    )
    labels = build_labels(tracking, config)
    destination = write_submission_atomic(
        output_path,
        labels,
        expected_frames=config.expected_frames,
    )
    report = validate_submission(destination, expected_rows=config.expected_frames)
    return tracking, labels, report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a validated tactical possession CSV.")
    parser.add_argument("--output", required=True, help="destination CSV path")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="algorithm JSON")
    parser.add_argument("--data-dir", default=None, help="overrides MTAH_DATA_DIR")
    parser.add_argument("--force", action="store_true", help="replace an existing output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    destination = Path(args.output)
    try:
        _confirm_overwrite(destination, args.force)
        tracking, _labels, report = build_submission(
            output_path=destination,
            data_root=args.data_dir,
            config_path=args.config,
        )
    except (
        ConfigurationError,
        TrackingDataError,
        SubmissionValidationError,
        BuildError,
        OSError,
    ) as error:
        print(f"FAIL  {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("FAIL  interrupted", file=sys.stderr)
        return 130

    counts = ", ".join(f"{label}={report.label_counts[label]}" for label in "HADX")
    print(f"OK    wrote {report.rows} frames to {report.path}")
    print(f"      ball visible on {int(tracking.ball_visible.sum())} frames")
    print(f"      labels: {counts}")
    print(f"      sha256: {report.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
