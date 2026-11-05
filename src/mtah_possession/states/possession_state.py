"""Deterministic H/A/D temporal possession state engine."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray

from mtah_possession.algorithm_config import StateEngineConfig
from mtah_possession.features.ball import HOME, NO_CANDIDATE
from mtah_possession.features.evidence import EvidenceSeries


class TransitionReason(StrEnum):
    INITIAL_HOME = "initial_home"
    INITIAL_AWAY = "initial_away"
    PERSIST = "persist"
    DIRECT_HOME_TO_AWAY = "direct_home_to_away"
    DIRECT_AWAY_TO_HOME = "direct_away_to_home"
    DEAD_BALL_CONFIRMED = "dead_ball_confirmed"
    RESTART_TO_HOME = "restart_to_home"
    RESTART_TO_AWAY = "restart_to_away"
    NO_OBSERVATION_PERSIST = "no_observation_persist"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    UNGRADED = "ungraded"


@dataclass(frozen=True)
class StateTransition:
    frame: int
    previous: str
    current: str
    reason: TransitionReason


@dataclass(frozen=True)
class StateEngineResult:
    labels: NDArray[np.str_]
    reasons: NDArray[np.str_]
    transitions: tuple[StateTransition, ...]

    @property
    def reason_counts(self) -> dict[str, int]:
        values, counts = np.unique(self.reasons, return_counts=True)
        return {str(value): int(count) for value, count in zip(values, counts, strict=True)}


def duration_to_frames(seconds: float, fps: int) -> int:
    if seconds < 0:
        raise ValueError("seconds must be non-negative")
    if fps <= 0:
        raise ValueError("fps must be positive")
    return int(math.ceil(seconds * fps))


def run_state_engine(
    evidence: EvidenceSeries,
    config: StateEngineConfig,
) -> StateEngineResult:
    """Convert evidence into H/A/D labels with direct team changes allowed."""

    frame_count = evidence.team_candidate.size
    labels = np.full(frame_count, "D", dtype="<U1")
    reasons = np.full(frame_count, TransitionReason.AWAITING_CONFIRMATION, dtype="<U32")
    transitions: list[StateTransition] = []

    switch_frames = duration_to_frames(config.number("candidate_confirmation_s"), config.fps)
    restart_frames = duration_to_frames(config.number("restart_confirmation_s"), config.fps)
    dead_frames = duration_to_frames(config.number("dead_ball_confirmation_s"), config.fps)

    current: str | None = None
    pending_candidate = NO_CANDIDATE
    pending_frames = 0
    dead_frames_run = 0

    for frame, candidate in enumerate(evidence.team_candidate):
        if evidence.ungraded_mask[frame]:
            labels[frame] = "X"
            reasons[frame] = TransitionReason.UNGRADED
            current = None
            pending_candidate = NO_CANDIDATE
            pending_frames = 0
            dead_frames_run = 0
            continue

        dead = bool(evidence.dead_ball_evidence[frame])
        if dead:
            dead_frames_run += 1
        else:
            dead_frames_run = 0
        if dead_frames_run >= dead_frames:
            if current != "D":
                transitions.append(
                    StateTransition(
                        frame=frame,
                        previous=current or "D",
                        current="D",
                        reason=TransitionReason.DEAD_BALL_CONFIRMED,
                    )
                )
            current = "D"
            labels[frame] = "D"
            reasons[frame] = TransitionReason.DEAD_BALL_CONFIRMED
            pending_candidate = NO_CANDIDATE
            pending_frames = 0
            continue

        if candidate == NO_CANDIDATE:
            labels[frame] = current or "D"
            reasons[frame] = (
                TransitionReason.NO_OBSERVATION_PERSIST
                if current is not None
                else TransitionReason.AWAITING_CONFIRMATION
            )
            pending_candidate = NO_CANDIDATE
            pending_frames = 0
            continue

        if candidate == pending_candidate:
            pending_frames += 1
        else:
            pending_candidate = candidate
            pending_frames = 1
        candidate_label = "H" if candidate == HOME else "A"

        if current is None:
            current = candidate_label
            reason = (
                TransitionReason.INITIAL_HOME
                if candidate == HOME
                else TransitionReason.INITIAL_AWAY
            )
            transitions.append(StateTransition(frame, "D", current, reason))
            labels[frame] = current
            reasons[frame] = reason
            continue

        if current == candidate_label:
            labels[frame] = current
            reasons[frame] = TransitionReason.PERSIST
            pending_frames = 0
            pending_candidate = NO_CANDIDATE
            continue

        if current == "D":
            if pending_frames >= restart_frames:
                current = candidate_label
                reason = (
                    TransitionReason.RESTART_TO_HOME
                    if candidate == HOME
                    else TransitionReason.RESTART_TO_AWAY
                )
                transitions.append(StateTransition(frame, "D", current, reason))
                labels[frame] = current
                reasons[frame] = reason
                pending_frames = 0
                pending_candidate = NO_CANDIDATE
            else:
                labels[frame] = "D"
                reasons[frame] = TransitionReason.AWAITING_CONFIRMATION
            continue

        if pending_frames >= switch_frames:
            previous = current
            current = candidate_label
            reason = (
                TransitionReason.DIRECT_HOME_TO_AWAY
                if previous == "H"
                else TransitionReason.DIRECT_AWAY_TO_HOME
            )
            transitions.append(StateTransition(frame, previous, current, reason))
            labels[frame] = current
            reasons[frame] = reason
            pending_frames = 0
            pending_candidate = NO_CANDIDATE
        else:
            labels[frame] = current
            reasons[frame] = TransitionReason.AWAITING_CONFIRMATION

    return StateEngineResult(labels, reasons, tuple(transitions))
