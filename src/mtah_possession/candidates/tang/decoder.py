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


def _rolling_mean(
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
    return smoothed


def _smooth_probabilities(
    probabilities: NDArray[np.float64],
    half_width: int,
    dead_half_width: int,
) -> NDArray[np.float64]:
    if half_width <= 0 and dead_half_width <= 0:
        return probabilities
    smoothed = _rolling_mean(probabilities, half_width)
    dead_smoothed = _rolling_mean(probabilities, dead_half_width)
    # D has its own, much shorter time scale: sub-second flicker is removed,
    # while an out-of-bounds or restart boundary stays sharp.
    smoothed[:, D] = dead_smoothed[:, D]
    smoothed /= smoothed.sum(axis=1, keepdims=True)
    return smoothed


def dead_evidence_support(
    features: FrameFeatures,
    config: CandidateConfig,
    forced: NDArray[np.bool_],
) -> NDArray[np.bool_]:
    """Return where explicit D evidence or its local smoothing halo exists."""

    rest_min = config.number("ball_rest_min_s")
    ball_rest = features.usable_ball & (features.ball_rest_s >= rest_min)
    explicit = forced | ball_rest | features.out_of_bounds | features.smart_dead
    half_width = config.integer("dead_smoothing_half_width_frames")
    if half_width <= 0:
        return explicit
    supported = explicit.copy()
    for offset in range(1, half_width + 1):
        supported[offset:] |= explicit[:-offset]
        supported[:-offset] |= explicit[offset:]
    return supported


def _decode_block_simple(
    logp: NDArray[np.float64],
    probabilities: NDArray[np.float64],
    emission: Emission,
    features: FrameFeatures,
    forced: NDArray[np.bool_],
    dead_supported: NDArray[np.bool_],
    start: int,
    stop: int,
    config: CandidateConfig,
) -> tuple[NDArray[np.int8], NDArray[np.float64]]:
    length = stop - start
    dp = np.full((length, 3), -np.inf, dtype=np.float64)
    back = np.zeros((length, 3), dtype=np.int8)
    if forced[start]:
        dp[0] = np.asarray([-np.inf, -np.inf, 0.0])
    else:
        dp[0] = logp[0]
        if not dead_supported[start]:
            dp[0, D] = -np.inf
    for index in range(1, length):
        frame = start + index
        transition = _transitions(config, bool(features.smart_restart[frame]))
        for to_state in range(3):
            candidates = dp[index - 1] + transition[:, to_state] + logp[index, to_state]
            if to_state in (HOME, AWAY):
                for previous_state in (HOME, AWAY):
                    margin = max(
                        0.0,
                        probabilities[index, to_state] - probabilities[index, previous_state],
                    )
                    boost = min(
                        config.number("hysteresis_max_boost"),
                        config.number("hysteresis_gain") * margin,
                    )
                    candidates[previous_state] += boost
            if forced[frame] and to_state != D:
                candidates[:] = -np.inf
            if to_state == D and not dead_supported[frame]:
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


def _decode_block(
    emission: Emission,
    features: FrameFeatures,
    forced: NDArray[np.bool_],
    dead_supported: NDArray[np.bool_],
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
        config.integer("dead_smoothing_half_width_frames"),
    )
    logp = np.log(np.clip(probabilities, 1e-12, 1.0))
    max_age = config.integer("dwell_frames")
    if max_age == 0:
        return _decode_block_simple(
            logp,
            probabilities,
            emission,
            features,
            forced,
            dead_supported,
            start,
            stop,
            config,
        )
    dwell_penalty = config.number("dwell_penalty")
    dp = np.full((3, max_age + 1), -np.inf, dtype=np.float64)
    back_label = np.full((length, 3, max_age + 1), -1, dtype=np.int8)
    back_age = np.full((length, 3, max_age + 1), -1, dtype=np.int16)

    if forced[start]:
        dp[D, 0] = 0.0
    else:
        for state in range(3):
            if state != D or dead_supported[start]:
                dp[state, 0] = logp[0, state]

    for index in range(1, length):
        frame = start + index
        transition = _transitions(config, bool(features.smart_restart[frame]))
        forced_frame = bool(forced[frame])
        new_dp = np.full_like(dp, -np.inf)
        for current in range(3):
            if forced_frame and current != D:
                continue
            if current == D and not dead_supported[frame]:
                continue
            emission_score = logp[index, current]
            # Staying in the same state increases its age.
            for previous_age in range(max_age + 1):
                value = dp[current, previous_age]
                if not np.isfinite(value):
                    continue
                age = min(previous_age + 1, max_age)
                score = value + emission_score
                if score > new_dp[current, age]:
                    new_dp[current, age] = score
                    back_label[index, current, age] = current
                    back_age[index, current, age] = previous_age
            # Switching states resets the age and pays the dwell penalty.
            for previous in range(3):
                if previous == current:
                    continue
                for previous_age in range(max_age + 1):
                    value = dp[previous, previous_age]
                    if not np.isfinite(value):
                        continue
                    extra = (
                        dwell_penalty * (1.0 - previous_age / max_age)
                        if max_age > 0 and previous_age < max_age
                        else 0.0
                    )
                    # D has its own entry/restart costs. The dwell model
                    # targets H/A flicker, not dead-ball detection.
                    if previous == D or current == D:
                        extra = 0.0
                    boost = 0.0
                    if previous in (HOME, AWAY) and current in (HOME, AWAY):
                        margin = max(
                            0.0,
                            probabilities[index, current] - probabilities[index, previous],
                        )
                        boost = min(
                            config.number("hysteresis_max_boost"),
                            config.number("hysteresis_gain") * margin,
                        )
                    score = value + transition[previous, current] + boost - extra + emission_score
                    if score > new_dp[current, 0]:
                        new_dp[current, 0] = score
                        back_label[index, current, 0] = previous
                        back_age[index, current, 0] = previous_age
        dp = new_dp

    flat_index = int(np.argmax(dp.reshape(-1)))
    state = flat_index // (max_age + 1)
    age = flat_index % (max_age + 1)
    states = np.empty(length, dtype=np.int8)
    for index in range(length - 1, -1, -1):
        states[index] = state
        if index == 0:
            break
        previous = int(back_label[index, state, age])
        previous_age = int(back_age[index, state, age])
        if previous < 0 or previous_age < 0:
            break
        state = previous
        age = previous_age

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


def _filter_low_confidence_short_segments(
    labels: NDArray[np.str_],
    confidence: NDArray[np.float64],
    forced: NDArray[np.bool_],
    config: CandidateConfig,
) -> None:
    """Filter short low-confidence segments using segment-level evidence."""

    for _ in range(3):
        changed = False
        index = 0
        while index < labels.size:
            if labels[index] == "X":
                index += 1
                continue
            label = labels[index]
            stop = index + 1
            while stop < labels.size and labels[stop] == label:
                stop += 1
            if label in {"H", "A"}:
                limit = config.integer("short_segment_frames")
                threshold = config.number("short_segment_confidence")
            elif label == "D":
                limit = config.integer("short_dead_frames")
                threshold = config.number("short_dead_confidence")
            else:
                index = stop
                continue
            if (
                limit > 0
                and stop - index < limit
                and not forced[index:stop].any()
                and float(confidence[index:stop].mean()) < threshold
                and index > 0
                and stop < labels.size
                and labels[index - 1] == labels[stop]
                and labels[index - 1] in {"H", "A"}
            ):
                labels[index:stop] = labels[index - 1]
                changed = True
            index = stop
        if not changed:
            break


def decode(emission: Emission, features: FrameFeatures, config: CandidateConfig) -> Decoded:
    count = emission.probabilities.shape[0]
    labels = np.full(count, "X", dtype="<U1")
    confidence = np.zeros(count, dtype=np.float64)
    ungraded = frame_block_mask(count, config.ungraded_blocks)
    forced = frame_block_mask(count, config.forced_dead_blocks)
    if config.enforce_dead_evidence_support:
        dead_supported = dead_evidence_support(features, config, forced)
    else:
        dead_supported = np.ones(count, dtype=bool)

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
            dead_supported,
            index,
            stop,
            config,
        )
        for offset, state in enumerate(states):
            labels[index + offset] = LABELS[int(state)]
        confidence[index:stop] = block_confidence
        index = stop

    _absorb_short_flicker(labels, config.integer("min_flicker_frames"))
    _filter_low_confidence_short_segments(
        labels,
        confidence,
        forced,
        config,
    )
    _absorb_short_flicker(labels, config.integer("min_flicker_frames"))
    return Decoded(labels=labels, confidence=confidence)
