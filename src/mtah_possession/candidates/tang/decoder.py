"""L3 Viterbi decoder with explicit H/A/D temporal constraints."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from mtah_possession.features.ball import AWAY, HOME
from mtah_possession.features.evidence import frame_block_mask

from .config import CandidateConfig
from .emission import Emission
from .features import FrameFeatures

D = 2
LABELS = ("H", "A", "D")


@dataclass(frozen=True)
class Decoded:
    labels: NDArray[np.str_]
    confidence: NDArray[np.float64]


def _transitions(config: CandidateConfig, restart: bool) -> NDArray[np.float64]:
    transition = np.zeros((3, 3), dtype=np.float64)
    transition[HOME, AWAY] = -config.number("switch_penalty")
    transition[AWAY, HOME] = -config.number("switch_penalty")
    transition[HOME, D] = -config.number("dead_enter_penalty")
    transition[AWAY, D] = -config.number("dead_enter_penalty")
    transition[D, HOME] = -config.number("restart_penalty")
    transition[D, AWAY] = -config.number("restart_penalty")
    if restart:
        transition[D, HOME] += config.number("restart_boost")
        transition[D, AWAY] += config.number("restart_boost")
    return transition


def _smooth_probabilities(
    probabilities: NDArray[np.float64],
    half_width: int,
) -> NDArray[np.float64]:
    if half_width <= 0 or probabilities.shape[0] == 1:
        return probabilities
    padded = np.pad(probabilities, ((half_width, half_width), (0, 0)), mode="edge")
    cumulative = np.vstack([np.zeros((1, 3), dtype=np.float64), np.cumsum(padded, axis=0)])
    indices = np.arange(probabilities.shape[0])
    window = 2 * half_width + 1
    smoothed = (cumulative[indices + window] - cumulative[indices]) / window
    smoothed /= smoothed.sum(axis=1, keepdims=True)
    return smoothed


def _decode_block(
    emission: Emission,
    features: FrameFeatures,
    forced: NDArray[np.bool_],
    start: int,
    stop: int,
    config: CandidateConfig,
) -> tuple[NDArray[np.int8], NDArray[np.float64]]:
    length = stop - start
    probabilities = emission.probabilities[start:stop].copy()
    probabilities[~emission.valid[start:stop]] = 1.0 / 3.0
    probabilities = _smooth_probabilities(
        probabilities,
        config.integer("emission_smoothing_half_width_frames"),
    )
    logp = np.log(np.clip(probabilities, 1e-12, 1.0))
    dp = np.full((length, 3), -np.inf, dtype=np.float64)
    back = np.zeros((length, 3), dtype=np.int8)

    if forced[start]:
        dp[0] = np.asarray([-np.inf, -np.inf, 0.0])
    else:
        dp[0] = logp[0]

    for index in range(1, length):
        frame = start + index
        transition = _transitions(config, bool(features.smart_restart[frame]))
        for to_state in range(3):
            candidates = dp[index - 1] + transition[:, to_state] + logp[index, to_state]
            if forced[frame] and to_state != D:
                candidates[:] = -np.inf
            back[index, to_state] = int(np.argmax(candidates))
            dp[index, to_state] = candidates[back[index, to_state]]

    state = int(np.argmax(dp[-1]))
    states = np.empty(length, dtype=np.int8)
    for index in range(length - 1, -1, -1):
        states[index] = state
        state = int(back[index, state])

    confidence = emission.confidence[start:stop].copy()
    confidence[forced[start:stop]] = 1.0
    return states, confidence


def _absorb_short_flicker(labels: NDArray[np.str_], min_frames: int) -> None:
    if min_frames <= 0:
        return
    index = 0
    while index < labels.size:
        if labels[index] == "X":
            index += 1
            continue
        stop = index + 1
        while stop < labels.size and labels[stop] == labels[index]:
            stop += 1
        if (
            labels[index] in {"H", "A"}
            and stop - index < min_frames
            and index > 0
            and stop < labels.size
            and labels[index - 1] == labels[stop]
            and labels[index - 1] in {"H", "A"}
        ):
            labels[index:stop] = labels[index - 1]
        index = stop


def decode(emission: Emission, features: FrameFeatures, config: CandidateConfig) -> Decoded:
    count = emission.probabilities.shape[0]
    labels = np.full(count, "X", dtype="<U1")
    confidence = np.zeros(count, dtype=np.float64)
    ungraded = frame_block_mask(count, config.ungraded_blocks)
    forced = frame_block_mask(count, config.forced_dead_blocks)

    index = 0
    while index < count:
        if ungraded[index]:
            index += 1
            continue
        stop = index + 1
        while stop < count and not ungraded[stop]:
            stop += 1
        states, block_confidence = _decode_block(
            emission,
            features,
            forced,
            index,
            stop,
            config,
        )
        for offset, state in enumerate(states):
            labels[index + offset] = LABELS[int(state)]
        confidence[index:stop] = block_confidence
        index = stop

    _absorb_short_flicker(labels, config.integer("min_flicker_frames"))
    return Decoded(labels=labels, confidence=confidence)
