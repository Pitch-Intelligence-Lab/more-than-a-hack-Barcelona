"""Explicit model-input boundary separated from evaluation labels."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from mtah_possession.data.neutral import PredictionSource, neutral_to_tracking
from mtah_possession.data.tracking import TrackingData
from mtah_possession.governance.roles import (
    model_input_field_names,
    validate_model_input_fields,
)
from mtah_possession.governance.temporal import TemporalFieldPolicy
from mtah_possession.states.phase_layer import PhaseLayerEvidence


@dataclass(frozen=True)
class AllowedEventEvidence:
    forced_dead_mask: NDArray[np.bool_]
    restart_evidence: NDArray[np.bool_]
    source_codes: NDArray[np.str_]
    ungraded_mask: NDArray[np.bool_]
    temporal_fields: tuple[TemporalFieldPolicy, ...] = ()

    @classmethod
    def empty(
        cls,
        frame_count: int,
        ungraded_mask: NDArray[np.bool_] | None = None,
    ) -> AllowedEventEvidence:
        return cls(
            forced_dead_mask=np.zeros(frame_count, dtype=bool),
            restart_evidence=np.zeros(frame_count, dtype=bool),
            source_codes=np.full(frame_count, "phase-none", dtype="<U48"),
            ungraded_mask=(
                np.zeros(frame_count, dtype=bool) if ungraded_mask is None else ungraded_mask.copy()
            ),
            temporal_fields=(),
        )


@dataclass(frozen=True)
class ModelInput:
    match_id: str
    fps: int
    pitch_length_m: float
    pitch_width_m: float
    tracking: TrackingData
    event_evidence: AllowedEventEvidence


def build_model_input(
    match: PredictionSource,
    event_evidence: PhaseLayerEvidence | None = None,
) -> ModelInput:
    tracking = neutral_to_tracking(match)
    allowed = (
        AllowedEventEvidence.empty(match.frame_count, ~match.in_period_mask())
        if event_evidence is None
        else AllowedEventEvidence(
            forced_dead_mask=event_evidence.forced_dead_mask.copy(),
            restart_evidence=event_evidence.restart_evidence.copy(),
            source_codes=event_evidence.source_codes.copy(),
            ungraded_mask=(~match.in_period_mask()).copy(),
            temporal_fields=event_evidence.temporal_fields,
        )
    )
    model_input = ModelInput(
        match_id=match.match_id,
        fps=match.fps,
        pitch_length_m=match.pitch_length_m,
        pitch_width_m=match.pitch_width_m,
        tracking=tracking,
        event_evidence=allowed,
    )
    validate_model_input_fields(model_input_field_names(model_input))
    return model_input


def with_event_evidence(
    model_input: ModelInput,
    event_evidence: PhaseLayerEvidence,
) -> ModelInput:
    if event_evidence.forced_dead_mask.shape != (model_input.tracking.frame_count,):
        raise ValueError("event evidence must match the model frame count")
    model_input = ModelInput(
        match_id=model_input.match_id,
        fps=model_input.fps,
        pitch_length_m=model_input.pitch_length_m,
        pitch_width_m=model_input.pitch_width_m,
        tracking=model_input.tracking,
        event_evidence=AllowedEventEvidence(
            forced_dead_mask=event_evidence.forced_dead_mask.copy(),
            restart_evidence=event_evidence.restart_evidence.copy(),
            source_codes=event_evidence.source_codes.copy(),
            ungraded_mask=model_input.event_evidence.ungraded_mask.copy(),
            temporal_fields=event_evidence.temporal_fields,
        ),
    )
    validate_model_input_fields(model_input_field_names(model_input))
    return model_input
