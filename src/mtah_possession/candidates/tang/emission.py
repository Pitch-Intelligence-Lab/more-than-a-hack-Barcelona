"""L2 per-frame H/A/D emission probabilities."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from mtah_possession.features.ball import AWAY, HOME, NO_CANDIDATE

from .config import CandidateConfig
from .features import FrameFeatures

D = 2
SCORE_SEMANTICS = "normalized_probability"


@dataclass(frozen=True)
class Emission:
    probabilities: NDArray[np.float64]
    valid: NDArray[np.bool_]
    confidence: NDArray[np.float64]
    smart_conflict: NDArray[np.bool_]


def build_emission(features: FrameFeatures, config: CandidateConfig) -> Emission:
    """Fuse weak and strong evidence into uncalibrated H/A/D probabilities."""

    count = features.tracking_candidate.shape[0]
    logits = np.zeros((count, 3), dtype=np.float64)
    home_valid = np.isfinite(features.home_distance_m)
    away_valid = np.isfinite(features.away_distance_m)
    scale = config.number("distance_scale_m")
    logits[home_valid, HOME] += -features.home_distance_m[home_valid] / scale
    logits[away_valid, AWAY] += -features.away_distance_m[away_valid] / scale

    total_votes = features.home_votes.astype(np.float64) + features.away_votes
    voted = total_votes > 0
    vote_weight = config.number("vote_weight")
    logits[voted, HOME] += vote_weight * features.home_votes[voted] / total_votes[voted]
    logits[voted, AWAY] += vote_weight * features.away_votes[voted] / total_votes[voted]

    tracking_bonus = config.number("tracking_bonus")
    logits[features.tracking_candidate == HOME, HOME] += tracking_bonus
    logits[features.tracking_candidate == AWAY, AWAY] += tracking_bonus

    smart_team_weight = config.number("smart_team_weight")
    smart_fill = (features.tracking_candidate == NO_CANDIDATE) & (
        features.smart_team != NO_CANDIDATE
    )
    logits[smart_fill & (features.smart_team == HOME), HOME] += smart_team_weight
    logits[smart_fill & (features.smart_team == AWAY), AWAY] += smart_team_weight

    rest_min = config.number("ball_rest_min_s")
    rest_fraction = np.clip(features.ball_rest_s / rest_min, 0.0, 1.0)
    rest_fraction = np.where(features.usable_ball, rest_fraction, 0.0)
    logits[:, D] += config.number("ball_rest_weight") * rest_fraction
    logits[:, D] += config.number("out_of_bounds_weight") * features.out_of_bounds
    logits[:, D] += config.number("smart_dead_weight") * features.smart_dead
    logits[:, D] -= config.number("restart_suppression") * features.smart_restart

    valid = (
        home_valid
        | away_valid
        | voted
        | (features.tracking_candidate != NO_CANDIDATE)
        | (features.smart_team != NO_CANDIDATE)
        | features.smart_dead
        | features.out_of_bounds
        | (features.ball_rest_s > 0)
    )
    logits[~valid] = 0.0
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    probabilities = exp / exp.sum(axis=1, keepdims=True)
    probabilities[~valid] = 1.0 / 3.0
    confidence = probabilities.max(axis=1)
    return Emission(
        probabilities=probabilities,
        valid=valid,
        confidence=confidence,
        smart_conflict=features.smart_conflict,
    )
