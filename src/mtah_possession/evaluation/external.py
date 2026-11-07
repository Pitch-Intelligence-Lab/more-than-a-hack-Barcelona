"""Provider-neutral candidate comparison against external proxy targets."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
from numpy.typing import NDArray

from mtah_possession.algorithm_config import StateEngineConfig
from mtah_possession.data.model_input import (
    ModelInput,
    build_model_input,
    with_event_evidence,
)
from mtah_possession.data.neutral import (
    NeutralMatch,
    ProxyTarget,
    map_proxy_target,
)
from mtah_possession.data.observations import prepare_ball_observations
from mtah_possession.features.ball import nearest_team_candidates
from mtah_possession.features.evidence import build_evidence_series
from mtah_possession.features.possession import majority_vote_labels
from mtah_possession.governance.authorization import (
    EVALUATION_PHASE_PROFILE,
    EVALUATION_POSSESSION_PROFILE,
    AuthorizedExternalRun,
)
from mtah_possession.governance.policy import DataUse, PolicyError, PolicyStatus
from mtah_possession.governance.temporal import validate_temporal_feature_path
from mtah_possession.states.cleanup import apply_structural_cleanup
from mtah_possession.states.phase_layer import (
    compile_phase_evidence,
    derive_gap_dead_directives,
)
from mtah_possession.states.possession_state import run_state_engine


@dataclass(frozen=True)
class ExternalMetrics:
    frame_count: int
    graded_frames: int
    macro_f1: float
    class_f1: dict[str, float]
    segment_f1_mean: float
    transition_precision: float
    transition_recall: float
    transition_f1: float
    matched_transitions: int
    target_transition_count: int
    predicted_transition_count: int
    false_dead_frames: int
    false_dead_duration_s: float
    missed_dead_frames: int
    missed_dead_duration_s: float
    team_switches: int
    mean_possession_duration_s: float
    prediction_sha256: str
    label_counts: dict[str, int]
    confusion_counts: dict[str, dict[str, int]]


@dataclass(frozen=True)
class AggregatedExternalMetrics:
    match_count: int
    macro_f1_across_matches: float
    micro_macro_f1: float
    micro_class_f1: dict[str, float]
    segment_f1_mean_across_matches: float
    micro_transition_precision: float
    micro_transition_recall: float
    micro_transition_f1: float
    false_dead_frames: int
    false_dead_duration_s: float
    missed_dead_frames: int
    missed_dead_duration_s: float
    mean_possession_duration_s: float


@dataclass(frozen=True)
class ExternalCandidateResult:
    name: str
    labels: NDArray[np.str_]
    sources: NDArray[np.str_]
    metrics: ExternalMetrics


@dataclass(frozen=True)
class ModelPrediction:
    labels: NDArray[np.str_]
    reasons: NDArray[np.str_]
    prediction_sha256: str


@dataclass(frozen=True)
class ExternalMatchEvaluation:
    match_id: str
    split: str
    proxy: ProxyTarget
    candidates: dict[str, ExternalCandidateResult]
    source_checksums: dict[str, str]
    external_aggregate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "split": self.split,
            "proxy_counts": dict(self.proxy.counts),
            "proxy_sources": dict(self.proxy.source_counts),
            "proxy_label_profiles": dict(self.proxy.label_profiles or {}),
            "source_checksums": dict(self.source_checksums),
            "external_aggregate": dict(self.external_aggregate),
            "candidates": {
                name: {
                    "metrics": {
                        "frame_count": result.metrics.frame_count,
                        "graded_frames": result.metrics.graded_frames,
                        "macro_f1": result.metrics.macro_f1,
                        "class_f1": dict(result.metrics.class_f1),
                        "segment_f1_mean": result.metrics.segment_f1_mean,
                        "transition_precision": result.metrics.transition_precision,
                        "transition_recall": result.metrics.transition_recall,
                        "transition_f1": result.metrics.transition_f1,
                        "matched_transitions": result.metrics.matched_transitions,
                        "target_transition_count": result.metrics.target_transition_count,
                        "predicted_transition_count": result.metrics.predicted_transition_count,
                        "false_dead_frames": result.metrics.false_dead_frames,
                        "false_dead_duration_s": result.metrics.false_dead_duration_s,
                        "missed_dead_frames": result.metrics.missed_dead_frames,
                        "missed_dead_duration_s": result.metrics.missed_dead_duration_s,
                        "team_switches": result.metrics.team_switches,
                        "mean_possession_duration_s": result.metrics.mean_possession_duration_s,
                        "prediction_sha256": result.metrics.prediction_sha256,
                        "label_counts": dict(result.metrics.label_counts),
                        "confusion_counts": {
                            target: dict(predicted)
                            for target, predicted in result.metrics.confusion_counts.items()
                        },
                    },
                    "source_counts": _value_counts(result.sources),
                }
                for name, result in self.candidates.items()
            },
        }


def evaluate_external_match(
    match: NeutralMatch,
    state_config: StateEngineConfig,
    *,
    authorization: AuthorizedExternalRun,
    split: str = "development",
    transition_tolerance_s: float = 0.5,
) -> ExternalMatchEvaluation:
    for use in (
        DataUse.TRACKING_MODEL_INPUT,
        DataUse.PHASE_MODEL_INPUT,
        DataUse.EVALUATION_REFERENCE,
    ):
        if authorization.use_permissions[use].status != PolicyStatus.PASS:
            raise PolicyError(f"{use.value} is not authorized")
    model_input = build_model_input(match)
    adapted = replace(
        state_config,
        fps=match.fps,
        expected_frames=match.frame_count,
        pitch_length_m=match.pitch_length_m,
        pitch_width_m=match.pitch_width_m,
        ungraded_blocks=(),
        forced_dead_blocks=(),
    )

    baseline = _baseline_labels(model_input)
    dp005 = _state_labels(adapted, model_input)

    dp006_params = dict(adapted.parameters)
    rest_parameter = dp006_params["use_ball_rest_dead_ball"]
    dp006_params["use_ball_rest_dead_ball"] = replace(rest_parameter, value=False)
    dp006_config = replace(adapted, parameters=dp006_params)
    phase_directives = derive_gap_dead_directives(
        tuple((period.start_frame, period.end_frame) for period in match.periods),
        tuple((phase.start_frame, phase.end_frame) for phase in match.phases),
        source="skillcorner_phases_of_play_gap",
    )
    phase_evidence = compile_phase_evidence(
        match.frame_count,
        match.fps,
        phase_directives,
    )
    dp006 = _state_labels(
        dp006_config,
        with_event_evidence(model_input, phase_evidence),
    )
    proxy = map_proxy_target(
        match,
        possession_profile=authorization.label_profiles[EVALUATION_POSSESSION_PROFILE],
        phase_profile=authorization.label_profiles[EVALUATION_PHASE_PROFILE],
    )

    tolerance_frames = max(1, round(transition_tolerance_s * match.fps))
    candidates = {}
    for name, labels, sources in (
        ("dp001_004_baseline", baseline, np.full(match.frame_count, "tracking_only", dtype="<U32")),
        ("dp005", dp005, np.full(match.frame_count, "tracking_only", dtype="<U32")),
        ("dp006_phase_proxy", dp006, phase_evidence.source_codes),
    ):
        candidates[name] = ExternalCandidateResult(
            name=name,
            labels=labels,
            sources=sources,
            metrics=evaluate_predictions(
                proxy.labels,
                labels,
                fps=match.fps,
                transition_tolerance_frames=tolerance_frames,
            ),
        )
    return ExternalMatchEvaluation(
        match_id=match.match_id,
        split=split,
        proxy=proxy,
        candidates=candidates,
        source_checksums=dict(match.source_checksums),
        external_aggregate=dict(match.source_metadata.get("tracking_aggregate", {})),
    )


def evaluate_predictions(
    target: NDArray[np.str_],
    prediction: NDArray[np.str_],
    *,
    fps: int,
    transition_tolerance_frames: int,
) -> ExternalMetrics:
    if target.shape != prediction.shape:
        raise ValueError("target and prediction must have the same shape")
    graded = target != "X"
    class_f1 = {label: _binary_f1(graded, target, prediction, label) for label in ("H", "A", "D")}
    transition_precision, transition_recall, matched = _transition_metrics(
        target,
        prediction,
        tolerance_frames=transition_tolerance_frames,
    )
    transition_f1 = _harmonic_f1(transition_precision, transition_recall)
    actual_transition_count = len(_state_change_frames(target))
    predicted_transition_count = len(_state_change_frames(prediction))
    labels, counts = np.unique(prediction, return_counts=True)
    possession_segments = _possession_segments(prediction)
    live_frames = int(np.sum(np.isin(prediction, ("H", "A"))))
    mean_duration = (
        live_frames / float(len(possession_segments)) / fps if possession_segments else 0.0
    )
    false_dead_frames = int(np.sum((prediction == "D") & np.isin(target, ("H", "A"))))
    missed_dead_frames = int(np.sum((target == "D") & np.isin(prediction, ("H", "A"))))
    confusion = _confusion_counts(target, prediction)
    return ExternalMetrics(
        frame_count=int(target.size),
        graded_frames=int(graded.sum()),
        macro_f1=float(np.mean(list(class_f1.values()))),
        class_f1=class_f1,
        segment_f1_mean=_segment_f1(target, prediction),
        transition_precision=transition_precision,
        transition_recall=transition_recall,
        transition_f1=transition_f1,
        matched_transitions=matched,
        target_transition_count=actual_transition_count,
        predicted_transition_count=predicted_transition_count,
        false_dead_frames=false_dead_frames,
        false_dead_duration_s=false_dead_frames / float(fps),
        missed_dead_frames=missed_dead_frames,
        missed_dead_duration_s=missed_dead_frames / float(fps),
        team_switches=_team_switches(prediction),
        mean_possession_duration_s=mean_duration,
        prediction_sha256=hashlib.sha256(prediction.tobytes()).hexdigest(),
        label_counts={str(value): int(count) for value, count in zip(labels, counts, strict=True)},
        confusion_counts=confusion,
    )


def aggregate_external_metrics(
    metrics: list[ExternalMetrics],
) -> AggregatedExternalMetrics:
    if not metrics:
        raise ValueError("at least one external match metric is required")
    confusion = {
        target: {predicted: 0 for predicted in ("H", "A", "D")} for target in ("H", "A", "D")
    }
    for item in metrics:
        for target, predicted_counts in item.confusion_counts.items():
            for predicted, count in predicted_counts.items():
                confusion[target][predicted] += count
    class_f1 = {label: _f1_from_confusion(confusion, label) for label in ("H", "A", "D")}
    matched = sum(item.matched_transitions for item in metrics)
    predicted_count = sum(item.predicted_transition_count for item in metrics)
    target_count = sum(item.target_transition_count for item in metrics)
    precision = matched / predicted_count if predicted_count else 0.0
    recall = matched / target_count if target_count else 0.0
    return AggregatedExternalMetrics(
        match_count=len(metrics),
        macro_f1_across_matches=float(np.mean([item.macro_f1 for item in metrics])),
        micro_macro_f1=float(np.mean(list(class_f1.values()))),
        micro_class_f1=class_f1,
        segment_f1_mean_across_matches=float(np.mean([item.segment_f1_mean for item in metrics])),
        micro_transition_precision=precision,
        micro_transition_recall=recall,
        micro_transition_f1=_harmonic_f1(precision, recall),
        false_dead_frames=sum(item.false_dead_frames for item in metrics),
        false_dead_duration_s=sum(item.false_dead_duration_s for item in metrics),
        missed_dead_frames=sum(item.missed_dead_frames for item in metrics),
        missed_dead_duration_s=sum(item.missed_dead_duration_s for item in metrics),
        mean_possession_duration_s=float(
            np.mean([item.mean_possession_duration_s for item in metrics])
        ),
    )


def _baseline_labels(model_input: ModelInput) -> NDArray[np.str_]:
    candidates = nearest_team_candidates(
        model_input.tracking,
        pitch_length_m=model_input.pitch_length_m,
        pitch_width_m=model_input.pitch_width_m,
    )
    labels = majority_vote_labels(
        candidates,
        window_half_width_frames=round(2.0 * model_input.fps),
    )
    labels[model_input.event_evidence.ungraded_mask] = "X"
    return labels


def _state_labels(
    config: StateEngineConfig,
    model_input: ModelInput,
) -> NDArray[np.str_]:
    return predict_model_input(model_input, config).labels


def predict_model_input(
    model_input: ModelInput,
    config: StateEngineConfig,
) -> ModelPrediction:
    event_evidence = model_input.event_evidence
    has_event_evidence = bool(
        event_evidence.forced_dead_mask.any()
        or event_evidence.restart_evidence.any()
        or (event_evidence.source_codes != "phase-none").any()
    )
    if has_event_evidence and not event_evidence.temporal_fields:
        raise PolicyError("non-empty phase evidence requires temporal metadata")
    temporal_names = {field.field_name for field in event_evidence.temporal_fields}
    required_temporal_names = set()
    if event_evidence.forced_dead_mask.any():
        required_temporal_names.add("forced_dead_mask")
    if event_evidence.restart_evidence.any():
        required_temporal_names.add("restart_evidence")
    if (event_evidence.source_codes != "phase-none").any():
        required_temporal_names.add("source_codes")
    missing_temporal_names = sorted(required_temporal_names - temporal_names)
    if missing_temporal_names:
        raise PolicyError(
            "phase evidence fields lack temporal metadata: " + ", ".join(missing_temporal_names)
        )
    validate_temporal_feature_path(
        event_evidence.temporal_fields,
        frame_count=model_input.tracking.frame_count,
        fps=model_input.fps,
    )
    observations = prepare_ball_observations(
        model_input.tracking,
        fps=config.fps,
        max_interpolation_gap_s=config.number("ball_interpolation_max_s"),
    )
    evidence = build_evidence_series(model_input.tracking, observations, config)
    evidence = replace(
        evidence,
        forced_dead_mask=model_input.event_evidence.forced_dead_mask,
        restart_evidence=(evidence.restart_evidence | model_input.event_evidence.restart_evidence),
        ungraded_mask=model_input.event_evidence.ungraded_mask,
    )
    result = run_state_engine(evidence, config)
    cleanup = apply_structural_cleanup(
        result.labels,
        config,
        protected_mask=evidence.forced_dead_mask,
    )
    reasons = result.reasons.copy()
    if cleanup.changed.any():
        reasons[cleanup.changed] = "structural_cleanup"
    return ModelPrediction(
        labels=cleanup.labels,
        reasons=reasons,
        prediction_sha256=hashlib.sha256(cleanup.labels.tobytes()).hexdigest(),
    )


def _binary_f1(
    graded: NDArray[np.bool_],
    target: NDArray[np.str_],
    prediction: NDArray[np.str_],
    label: str,
) -> float:
    actual = (target == label) & graded
    predicted = (prediction == label) & graded
    true_positive = int(np.sum(actual & predicted))
    false_positive = int(np.sum(~actual & predicted))
    false_negative = int(np.sum(actual & ~predicted))
    denominator = 2 * true_positive + false_positive + false_negative
    return (2.0 * true_positive / denominator) if denominator else 0.0


def _possession_segments(labels: NDArray[np.str_]) -> list[tuple[int, int, str]]:
    segments: list[tuple[int, int, str]] = []
    start: int | None = None
    current: str | None = None
    for frame, value in enumerate(labels):
        label = str(value)
        live = label in {"H", "A"}
        if live and label == current and start is not None:
            continue
        if start is not None and current is not None:
            segments.append((start, frame, current))
        if live:
            start, current = frame, label
        else:
            start, current = None, None
    if start is not None and current is not None:
        segments.append((start, labels.size, current))
    return segments


def _segment_f1(target: NDArray[np.str_], prediction: NDArray[np.str_]) -> float:
    target_segments = _possession_segments(target)
    predicted_segments = _possession_segments(prediction)
    if not target_segments or not predicted_segments:
        return 0.0
    overlaps: list[tuple[float, int, int]] = []
    for target_index, (target_start, target_end, target_label) in enumerate(target_segments):
        for predicted_index, (predicted_start, predicted_end, predicted_label) in enumerate(
            predicted_segments
        ):
            if target_label != predicted_label:
                continue
            intersection = max(
                0,
                min(target_end, predicted_end) - max(target_start, predicted_start),
            )
            if intersection == 0:
                continue
            union = max(target_end, predicted_end) - min(target_start, predicted_start)
            overlaps.append((intersection / union, target_index, predicted_index))
    scores = []
    for threshold in (0.3, 0.4, 0.5, 0.6, 0.7):
        used_target: set[int] = set()
        used_prediction: set[int] = set()
        matched = 0
        for iou, target_index, predicted_index in sorted(overlaps, reverse=True):
            if iou < threshold:
                continue
            if target_index in used_target or predicted_index in used_prediction:
                continue
            used_target.add(target_index)
            used_prediction.add(predicted_index)
            matched += 1
        scores.append(2.0 * matched / (len(target_segments) + len(predicted_segments)))
    return float(np.mean(scores))


def _state_change_frames(labels: NDArray[np.str_]) -> list[int]:
    previous = None
    frames: list[int] = []
    for frame, value in enumerate(labels):
        label = str(value)
        if label == "X":
            previous = None
            continue
        if previous is not None and previous != label:
            frames.append(frame)
        previous = label
    return frames


def _transition_metrics(
    target: NDArray[np.str_],
    prediction: NDArray[np.str_],
    *,
    tolerance_frames: int,
) -> tuple[float, float, int]:
    actual = _state_change_frames(target)
    predicted = _state_change_frames(prediction)
    if not actual or not predicted:
        return 0.0, 0.0, 0
    pairs = sorted(
        (abs(a - p), i, j)
        for i, a in enumerate(actual)
        for j, p in enumerate(predicted)
        if abs(a - p) <= tolerance_frames
    )
    used_actual: set[int] = set()
    used_predicted: set[int] = set()
    for _distance, i, j in pairs:
        if i in used_actual or j in used_predicted:
            continue
        used_actual.add(i)
        used_predicted.add(j)
    matched = len(used_actual)
    return matched / len(predicted), matched / len(actual), matched


def _team_switches(labels: NDArray[np.str_]) -> int:
    previous_team: str | None = None
    switches = 0
    for value in labels:
        label = str(value)
        if label in {"H", "A"}:
            if previous_team is not None and previous_team != label:
                switches += 1
            previous_team = label
    return switches


def _harmonic_f1(precision: float, recall: float) -> float:
    denominator = precision + recall
    return (2.0 * precision * recall / denominator) if denominator else 0.0


def _value_counts(values: NDArray[np.str_]) -> dict[str, int]:
    labels, counts = np.unique(values, return_counts=True)
    return {str(label): int(count) for label, count in zip(labels, counts, strict=True)}


def _confusion_counts(
    target: NDArray[np.str_],
    prediction: NDArray[np.str_],
) -> dict[str, dict[str, int]]:
    counts = {actual: {predicted: 0 for predicted in ("H", "A", "D")} for actual in ("H", "A", "D")}
    for actual, predicted in zip(target, prediction, strict=True):
        if actual in counts and predicted in counts[actual]:
            counts[str(actual)][str(predicted)] += 1
    return counts


def _f1_from_confusion(
    confusion: dict[str, dict[str, int]],
    label: str,
) -> float:
    true_positive = confusion[label][label]
    false_positive = sum(confusion[target][label] for target in confusion if target != label)
    false_negative = sum(
        count for predicted, count in confusion[label].items() if predicted != label
    )
    denominator = 2 * true_positive + false_positive + false_negative
    return (2.0 * true_positive / denominator) if denominator else 0.0
