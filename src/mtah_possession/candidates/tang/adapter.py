"""Candidate-B adapter: frozen L0/L4 in, candidate B diagnostics out."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from mtah_possession.config import load_settings, require_tactical_assets
from mtah_possession.data.observations import prepare_ball_observations
from mtah_possession.data.tracking import load_tactical_tracking
from mtah_possession.features.ball import NO_CANDIDATE
from mtah_possession.features.evidence import frame_block_mask
from mtah_possession.pipeline.build_submission import write_submission_atomic
from mtah_possession.states.cleanup import label_segments
from mtah_possession.validation.submission import sha256_file, validate_submission

from .config import CandidateConfig, load_candidate_config
from .decoder import decode
from .emission import Emission, build_emission
from .features import FrameFeatures, build_features
from .smart_tagging import SmartEvidence, build_smart_evidence, load_tags


@dataclass(frozen=True)
class CandidateBuildResult:
    labels: NDArray[np.str_]
    confidence: NDArray[np.float64]
    emission: Emission
    features: FrameFeatures
    config: CandidateConfig
    health: dict[str, Any]


def _duration_stats(durations: list[int], fps: int) -> dict[str, float | int]:
    if not durations:
        return {"count": 0, "mean_s": 0.0, "shortest_s": 0.0, "longest_s": 0.0}
    values = np.asarray(durations, dtype=np.float64) / fps
    return {
        "count": len(durations),
        "mean_s": float(values.mean()),
        "shortest_s": float(values.min()),
        "longest_s": float(values.max()),
    }


def _source_counts(
    labels: NDArray[np.str_],
    features: FrameFeatures,
    forced: NDArray[np.bool_],
    config: CandidateConfig,
) -> dict[str, int]:
    final_d = labels == "D"
    ball_rest = features.usable_ball & (features.ball_rest_s >= config.number("ball_rest_min_s"))
    sources = (forced, ball_rest, features.out_of_bounds, features.smart_dead)
    names = ("forced", "ball_rest", "out_of_bounds", "smart_tagging")
    codes = np.zeros(labels.size, dtype=np.uint8)
    for bit, active in enumerate(sources):
        codes |= active.astype(np.uint8) << bit
    values, counts = np.unique(codes[final_d], return_counts=True)
    result: dict[str, int] = {}
    for value, count in zip(values.tolist(), counts.tolist(), strict=True):
        active_names = [names[bit] for bit in range(len(names)) if value & (1 << bit)]
        result["+".join(active_names) if active_names else "none"] = count
    return dict(sorted(result.items(), key=lambda item: -item[1]))


def _health(
    labels: NDArray[np.str_],
    emission: Emission,
    features: FrameFeatures,
    config: CandidateConfig,
    output_path: Path,
    input_sha256: dict[str, str],
    validation,
) -> dict[str, Any]:
    durations: dict[str, list[int]] = {"H": [], "A": [], "D": []}
    for start, stop, value in label_segments(labels):
        if value in durations:
            durations[value].append(stop - start)
    all_durations = [length for values in durations.values() for length in values]
    transitions: Counter[str] = Counter()
    previous = None
    for value in labels:
        label = str(value)
        if label == "X":
            previous = None
            continue
        if previous is not None and previous != label:
            transitions[f"{previous}->{label}"] += 1
        previous = label
    forced = frame_block_mask(labels.size, config.forced_dead_blocks)
    forced_labels = labels[forced]
    return {
        "candidate": "tang-candidate-b",
        "rows": int(labels.size),
        "frame_range": [0, int(labels.size) - 1],
        "label_counts": dict(validation.label_counts),
        "segments_by_label": {label: len(values) for label, values in durations.items()},
        "segment_duration_s": {
            label: _duration_stats(values, config.fps) for label, values in durations.items()
        }
        | {"overall": _duration_stats(all_durations, config.fps)},
        "transition_counts": dict(sorted(transitions.items())),
        "validator_status": "pass",
        "input_sha256": input_sha256,
        "output_sha256": sha256_file(output_path),
        "emission_valid_frames": int(emission.valid.sum()),
        "emission_invalid_frames": int((~emission.valid).sum()),
        "emission_mean_confidence": float(emission.confidence.mean()),
        "smart_conflict_frames": int(features.smart_conflict.sum()),
        "contested_frames": int(features.contested.sum()),
        "loose_ball_frames": int(features.loose_ball.sum()),
        "time_valid_frames": int(features.time_valid.sum()),
        "time_mean_advantage_s": (
            float(np.nanmean(features.time_advantage_s[features.time_valid]))
            if features.time_valid.any()
            else None
        ),
        "pressure_valid_frames": int(features.pressure_valid.sum()),
        "pressure_mean_advantage_5m": (
            float(np.mean(features.pressure_advantage_5m[features.pressure_valid]))
            if features.pressure_valid.any()
            else None
        ),
        "smart_dead_frames": int(features.smart_dead.sum()),
        "smart_restart_frames": int(features.smart_restart.sum()),
        "smart_dead_tracking_overlap": int(
            (features.smart_dead & (features.tracking_candidate != NO_CANDIDATE)).sum()
        ),
        "final_d_frames": int((labels == "D").sum()),
        "d_source_counts": _source_counts(labels, features, forced, config),
        "forced_dead_frames": int(forced.sum()),
        "forced_dead_all_d": bool(forced.any() and np.all(forced_labels == "D")),
        "generalisation": "GENERALISATION NOT ESTABLISHED",
    }


def _write_decision_log(
    path: str | Path,
    labels: NDArray[np.str_],
    confidence: NDArray[np.float64],
    emission: Emission,
    features: FrameFeatures,
    config: CandidateConfig,
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    forced = frame_block_mask(labels.size, config.forced_dead_blocks)
    ungraded = frame_block_mask(labels.size, config.ungraded_blocks)
    team_names = {-1: "none", 0: "H", 1: "A"}
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "frame",
                "label",
                "confidence",
                "valid",
                "tracking_candidate",
                "ball_usable",
                "contested",
                "loose_ball",
                "time_advantage_s",
                "time_valid",
                "pressure_advantage_5m",
                "smart_team",
                "smart_dead",
                "smart_restart",
                "forced_dead",
                "ungraded",
                "reason",
            ]
        )
        for frame in range(labels.size):
            if ungraded[frame]:
                reason = "ungraded"
            elif forced[frame]:
                reason = "forced_dead"
            elif labels[frame] == "D" and features.smart_dead[frame]:
                reason = "dead_evidence"
            elif features.tracking_candidate[frame] != NO_CANDIDATE:
                reason = "tracking_candidate"
            elif features.contested[frame]:
                reason = "contested_uncertain"
            elif features.loose_ball[frame]:
                reason = "loose_ball_uncertain"
            elif features.smart_team[frame] != NO_CANDIDATE:
                reason = "smart_team_prior"
            elif not emission.valid[frame]:
                reason = "decoder_persistence"
            else:
                reason = "emission_evidence"
            writer.writerow(
                [
                    frame,
                    str(labels[frame]),
                    f"{confidence[frame]:.6f}",
                    int(bool(emission.valid[frame])),
                    team_names[int(features.tracking_candidate[frame])],
                    int(bool(features.usable_ball[frame])),
                    int(bool(features.contested[frame])),
                    int(bool(features.loose_ball[frame])),
                    (
                        f"{features.time_advantage_s[frame]:.6f}"
                        if features.time_valid[frame]
                        else ""
                    ),
                    int(bool(features.time_valid[frame])),
                    (
                        f"{features.pressure_advantage_5m[frame]:.0f}"
                        if features.pressure_valid[frame]
                        else ""
                    ),
                    team_names[int(features.smart_team[frame])],
                    int(bool(features.smart_dead[frame])),
                    int(bool(features.smart_restart[frame])),
                    int(bool(forced[frame])),
                    int(bool(ungraded[frame])),
                    reason,
                ]
            )


def build_candidate(
    *,
    output_path: str | Path,
    data_root: str | Path | None,
    config_path: str | Path,
    health_report: str | Path | None = None,
    decision_log: str | Path | None = None,
) -> CandidateBuildResult:
    config = load_candidate_config(config_path)
    settings = load_settings(data_root, match_id=config.match_id)
    asset_names = ["atd_meta", "atd_raw"]
    if config.enable_smart_tagging:
        asset_names.append("smart_tagging")
    paths = require_tactical_assets(settings, tuple(asset_names))
    tracking = load_tactical_tracking(
        settings.root,
        expected_frames=config.expected_frames,
        match_id=config.match_id,
    )
    observations = prepare_ball_observations(
        tracking,
        fps=config.fps,
        max_interpolation_gap_s=config.number("ball_interpolation_max_s"),
    )
    if config.enable_smart_tagging:
        tags = load_tags(
            paths["smart_tagging"],
            fps=config.fps,
            frame_count=tracking.frame_count,
        )
        smart = build_smart_evidence(
            tracking.frame_count,
            tags,
            observations,
            fps=config.fps,
            pitch_length_m=config.pitch_length_m,
            pitch_width_m=config.pitch_width_m,
            restart_offset_s=config.number("smart_restart_offset_s"),
            dead_lookback_s=config.number("smart_dead_lookback_s"),
            dead_speed_mps=config.number("smart_dead_speed_mps"),
            dead_gap_s=config.number("smart_dead_gap_s"),
        )
    else:
        smart = SmartEvidence(
            team_prior=np.full(tracking.frame_count, -1, dtype=np.int8),
            restart=np.zeros(tracking.frame_count, dtype=bool),
            dead=np.zeros(tracking.frame_count, dtype=bool),
        )
    features = build_features(tracking, observations, smart, config)
    emission = build_emission(features, config)
    decoded = decode(emission, features, config)

    destination = write_submission_atomic(
        output_path,
        decoded.labels,
        expected_frames=config.expected_frames,
    )
    validation = validate_submission(destination, expected_rows=config.expected_frames)
    input_sha256 = {name: sha256_file(paths[name]) for name in asset_names}
    health = _health(
        decoded.labels,
        emission,
        features,
        config,
        Path(destination),
        input_sha256,
        validation,
    )
    if health_report is not None:
        report = Path(health_report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(health, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if decision_log is not None:
        _write_decision_log(
            decision_log,
            decoded.labels,
            decoded.confidence,
            emission,
            features,
            config,
        )
    return CandidateBuildResult(
        labels=decoded.labels,
        confidence=decoded.confidence,
        emission=emission,
        features=features,
        config=config,
        health=health,
    )
