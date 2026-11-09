"""L1 evidence extraction for Candidate B."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from mtah_possession.data.observations import BallObservations
from mtah_possession.data.tracking import TrackingData
from mtah_possession.features.ball import NO_CANDIDATE
from mtah_possession.features.evidence import (
    ball_motion_evidence,
    nearest_team_evidence,
    visible_near_player_vote,
)

from .config import CandidateConfig
from .pressure import compute_pressure
from .quality import filter_tracking_anomalies
from .smart_tagging import SmartEvidence
from .velocity import compute_time_to_ball


@dataclass(frozen=True)
class FrameFeatures:
    usable_ball: NDArray[np.bool_]
    home_distance_m: NDArray[np.float64]
    away_distance_m: NDArray[np.float64]
    home_votes: NDArray[np.int16]
    away_votes: NDArray[np.int16]
    tracking_candidate: NDArray[np.int8]
    ball_speed_mps: NDArray[np.float64]
    ball_rest_s: NDArray[np.float64]
    time_advantage_s: NDArray[np.float64]
    time_valid: NDArray[np.bool_]
    pressure_advantage_5m: NDArray[np.float64]
    pressure_valid: NDArray[np.bool_]
    tracking_anomaly: NDArray[np.bool_]
    out_of_bounds: NDArray[np.bool_]
    contested: NDArray[np.bool_]
    loose_ball: NDArray[np.bool_]
    smart_team: NDArray[np.int8]
    smart_restart: NDArray[np.bool_]
    smart_dead: NDArray[np.bool_]
    smart_conflict: NDArray[np.bool_]


def build_features(
    tracking: TrackingData,
    observations: BallObservations,
    smart: SmartEvidence,
    config: CandidateConfig,
) -> FrameFeatures:
    quality = filter_tracking_anomalies(
        tracking,
        fps=config.fps,
        pitch_length_m=config.pitch_length_m,
        pitch_width_m=config.pitch_width_m,
        speed_threshold_mps=config.number("tracking_anomaly_speed_mps"),
        accel_threshold_mps2=config.number("tracking_anomaly_accel_mps2"),
        enabled=config.enable_tracking_anomaly_gating,
    )
    effective_tracking = quality.tracking
    usable = observations.usable_mask
    nearest = nearest_team_evidence(
        effective_tracking,
        observations.positions,
        usable,
        pitch_length_m=config.pitch_length_m,
        pitch_width_m=config.pitch_width_m,
    )
    vote = visible_near_player_vote(
        effective_tracking,
        observations.positions,
        usable,
        pitch_length_m=config.pitch_length_m,
        pitch_width_m=config.pitch_width_m,
        k=config.integer("near_player_vote_k"),
    )
    candidate = nearest.candidate.copy()
    replace = candidate == NO_CANDIDATE
    candidate[replace] = vote.candidate[replace]
    conflict = (candidate != NO_CANDIDATE) & (vote.candidate != NO_CANDIDATE)
    conflict &= candidate != vote.candidate
    candidate[conflict] = NO_CANDIDATE
    both_teams = np.isfinite(nearest.home_distance_m) & np.isfinite(nearest.away_distance_m)
    distance_gap = np.abs(nearest.home_distance_m - nearest.away_distance_m)
    vote_gap = np.abs(vote.home_votes.astype(np.int16) - vote.away_votes)
    contested = (
        both_teams
        & (distance_gap < config.number("contest_margin_m"))
        & (vote_gap <= 1)
        & ((vote.home_votes + vote.away_votes) > 0)
    )
    candidate[contested] = NO_CANDIDATE
    nearest_distance = np.fmin(nearest.home_distance_m, nearest.away_distance_m)
    loose_ball = np.isfinite(nearest_distance) & (
        nearest_distance > config.number("max_control_distance_m")
    )
    candidate[loose_ball] = NO_CANDIDATE

    motion = ball_motion_evidence(
        observations,
        fps=config.fps,
        pitch_length_m=config.pitch_length_m,
        pitch_width_m=config.pitch_width_m,
        rest_speed_threshold_mps=config.number("ball_rest_speed_mps"),
    )
    timing = compute_time_to_ball(
        effective_tracking,
        observations.positions,
        usable,
        fps=config.fps,
        pitch_length_m=config.pitch_length_m,
        pitch_width_m=config.pitch_width_m,
        min_closing_speed_mps=config.number("min_closing_speed_mps"),
        max_time_s=config.number("max_time_to_ball_s"),
    )
    pressure = compute_pressure(
        effective_tracking,
        observations.positions,
        usable,
        pitch_length_m=config.pitch_length_m,
        pitch_width_m=config.pitch_width_m,
        radius_m=config.number("pressure_radius_m"),
    )
    positions = observations.positions
    out_of_bounds = usable & (
        (positions[:, 0] < 0)
        | (positions[:, 0] > 1)
        | (positions[:, 1] < 0)
        | (positions[:, 1] > 1)
    )
    smart_conflict = (
        (candidate != NO_CANDIDATE)
        & (smart.team_prior != NO_CANDIDATE)
        & (candidate != smart.team_prior)
    )
    return FrameFeatures(
        usable_ball=usable,
        home_distance_m=nearest.home_distance_m,
        away_distance_m=nearest.away_distance_m,
        home_votes=vote.home_votes,
        away_votes=vote.away_votes,
        tracking_candidate=candidate,
        ball_speed_mps=motion.speed_mps,
        ball_rest_s=motion.rest_duration_s,
        time_advantage_s=timing.advantage_s,
        time_valid=timing.valid,
        pressure_advantage_5m=pressure.advantage_5m,
        pressure_valid=pressure.valid,
        tracking_anomaly=quality.anomaly_frames,
        out_of_bounds=out_of_bounds,
        contested=contested,
        loose_ball=loose_ball,
        smart_team=smart.team_prior,
        smart_restart=smart.restart,
        smart_dead=smart.dead,
        smart_conflict=smart_conflict,
    )
