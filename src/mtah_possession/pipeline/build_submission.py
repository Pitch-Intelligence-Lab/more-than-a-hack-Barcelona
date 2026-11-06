"""Build and atomically replace a validated tactical possession CSV."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from mtah_possession.algorithm_config import (
    AlgorithmConfigError,
    BaselineConfig,
    StateEngineConfig,
    load_algorithm_config,
)
from mtah_possession.config import (
    ConfigurationError,
    load_settings,
    require_tactical_assets,
)
from mtah_possession.data.observations import BallObservations, prepare_ball_observations
from mtah_possession.data.tracking import TrackingData, TrackingDataError, load_tactical_tracking
from mtah_possession.features.ball import nearest_team_candidates
from mtah_possession.features.evidence import EvidenceSeries, build_evidence_series
from mtah_possession.features.possession import majority_vote_labels
from mtah_possession.pipeline.health import (
    HealthReport,
    build_health_report,
    write_health_report,
)
from mtah_possession.states.cleanup import CleanupResult, apply_structural_cleanup
from mtah_possession.states.possession_state import run_state_engine
from mtah_possession.validation.submission import (
    SubmissionValidationError,
    ValidationReport,
    sha256_file,
    validate_submission,
)

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "state-engine.json"


class BuildError(RuntimeError):
    """Raised when a submission cannot be built safely."""


@dataclass(frozen=True)
class BuildResult:
    tracking: TrackingData
    labels: np.ndarray
    observations: BallObservations
    evidence: EvidenceSeries | None
    validation: ValidationReport
    health: HealthReport
    cleanup: CleanupResult | None


def build_labels(tracking: TrackingData, config: BaselineConfig):
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


def _state_engine_labels(
    tracking: TrackingData,
    config: StateEngineConfig,
) -> tuple[
    np.ndarray,
    BallObservations,
    EvidenceSeries,
    np.ndarray,
    CleanupResult,
]:
    observations = prepare_ball_observations(
        tracking,
        fps=config.fps,
        max_interpolation_gap_s=config.number("ball_interpolation_max_s"),
    )
    evidence = build_evidence_series(tracking, observations, config)
    raw = run_state_engine(evidence, config)
    cleanup = apply_structural_cleanup(
        raw.labels,
        config,
        protected_mask=evidence.forced_dead_mask,
    )
    reasons = raw.reasons.copy()
    if cleanup.changed.any():
        reasons[cleanup.changed] = "structural_cleanup"
    return cleanup.labels, observations, evidence, reasons, cleanup


def build_submission(
    *,
    output_path: str | os.PathLike[str],
    data_root: str | os.PathLike[str] | None = None,
    config_path: str | os.PathLike[str] = DEFAULT_CONFIG_PATH,
) -> BuildResult:
    config = load_algorithm_config(config_path)
    settings = load_settings(data_root, match_id=config.match_id)
    paths = require_tactical_assets(settings, ("atd_meta", "atd_raw"))
    input_hashes = {name: sha256_file(path) for name, path in paths.items()}
    tracking = load_tactical_tracking(
        settings.root,
        expected_frames=config.expected_frames,
        match_id=config.match_id,
    )
    evidence: EvidenceSeries | None = None
    cleanup: CleanupResult | None = None
    if isinstance(config, StateEngineConfig):
        labels, observations, evidence, reasons, cleanup = _state_engine_labels(
            tracking,
            config,
        )
        cleanup_steps = cleanup.applied_steps
    else:
        labels = build_labels(tracking, config)
        observations = prepare_ball_observations(
            tracking,
            fps=25,
            max_interpolation_gap_s=0.0,
        )
        reasons = np.full(tracking.frame_count, "baseline", dtype="<U16")
        cleanup_steps = ()
    destination = write_submission_atomic(
        output_path,
        labels,
        expected_frames=config.expected_frames,
    )
    validation = validate_submission(destination, expected_rows=config.expected_frames)
    health = build_health_report(
        labels=labels,
        observations=observations,
        reasons=reasons,
        validation=validation,
        input_sha256=input_hashes,
        fps=config.fps if isinstance(config, StateEngineConfig) else 25,
        cleanup_steps=cleanup_steps,
        cleanup_removed_label_counts=(
            cleanup.removed_label_counts if cleanup is not None else None
        ),
        forced_dead_mask=(
            evidence.forced_dead_mask
            if evidence is not None
            else np.zeros(tracking.frame_count, dtype=bool)
        ),
    )
    return BuildResult(
        tracking=tracking,
        labels=labels,
        observations=observations,
        evidence=evidence,
        validation=validation,
        health=health,
        cleanup=cleanup,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a validated tactical possession CSV.")
    parser.add_argument("--output", required=True, help="destination CSV path")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="algorithm JSON")
    parser.add_argument("--data-dir", default=None, help="overrides MTAH_DATA_DIR")
    parser.add_argument("--force", action="store_true", help="replace an existing output")
    parser.add_argument("--health-report", default=None, help="optional aggregate JSON report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    destination = Path(args.output)
    try:
        _confirm_overwrite(destination, args.force)
        result = build_submission(
            output_path=destination,
            data_root=args.data_dir,
            config_path=args.config,
        )
        if args.health_report:
            write_health_report(args.health_report, result.health)
    except (
        ConfigurationError,
        AlgorithmConfigError,
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

    report = result.validation
    counts = ", ".join(f"{label}={report.label_counts[label]}" for label in "HADX")
    print(f"OK    wrote {report.rows} frames to {report.path}")
    print(f"      ball visible on {int(result.tracking.ball_visible.sum())} frames")
    print(f"      labels: {counts}")
    print(
        "      segments: "
        + ", ".join(f"{label}={count}" for label, count in result.health.segments_by_label.items())
    )
    print(
        "      observations: "
        + ", ".join(
            f"{name}={count}" for name, count in result.health.observation_quality_counts.items()
        )
    )
    print(
        "      transitions: "
        + (
            ", ".join(f"{name}={count}" for name, count in result.health.transition_counts.items())
            or "none"
        )
    )
    print(
        "      forced D: "
        f"frames={result.health.forced_dead_frames}, "
        f"all_d={result.health.forced_dead_all_d}, "
        f"labels={dict(result.health.forced_dead_label_counts)}"
    )
    print(f"      cleanup removed: {dict(result.health.cleanup_removed_label_counts)}")
    print(f"      sha256: {report.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
