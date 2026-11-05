"""Small, independently testable possession evidence signals."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from mtah_possession.algorithm_config import StateEngineConfig
from mtah_possession.data.observations import BallObservations, BallQuality
from mtah_possession.data.tracking import TrackingData
from mtah_possession.features.ball import AWAY, HOME, NO_CANDIDATE

_DISTANCE_TOLERANCE_M2 = 1e-6


@dataclass(frozen=True)
class NearestTeamEvidence:
    candidate: NDArray[np.int8]
    home_distance_m: NDArray[np.float64]
    away_distance_m: NDArray[np.float64]
    distance_gap_m: NDArray[np.float64]


@dataclass(frozen=True)
class NearPlayerVoteEvidence:
    candidate: NDArray[np.int8]
    home_votes: NDArray[np.int16]
    away_votes: NDArray[np.int16]


@dataclass(frozen=True)
class BallMotionEvidence:
    speed_mps: NDArray[np.float64]
    rest_duration_s: NDArray[np.float64]
    resting_now: NDArray[np.bool_]


@dataclass(frozen=True)
class ReachabilityEvidence:
    home_time_s: NDArray[np.float64]
    away_time_s: NDArray[np.float64]


@dataclass(frozen=True)
class TaggingInterval:
    start_frame: int
    end_frame: int
    team: str | None = None
    dead_ball: bool = False
    restart: bool = False


@dataclass(frozen=True)
class SmartTaggingEvidence:
    team_prior: NDArray[np.int8]
    dead_ball_evidence: NDArray[np.bool_]
    restart_evidence: NDArray[np.bool_]


@dataclass(frozen=True)
class EvidenceSeries:
    nearest: NearestTeamEvidence
    near_player_vote: NearPlayerVoteEvidence
    ball_motion: BallMotionEvidence
    restart_zone_distance_m: NDArray[np.float64]
    reachability: ReachabilityEvidence
    team_candidate: NDArray[np.int8]
    dead_ball_evidence: NDArray[np.bool_]
    restart_evidence: NDArray[np.bool_]
    ungraded_mask: NDArray[np.bool_]


def nearest_team_evidence(
    tracking: TrackingData,
    ball_positions: NDArray[np.float32],
    usable_ball: NDArray[np.bool_],
    *,
    pitch_length_m: float,
    pitch_width_m: float,
) -> NearestTeamEvidence:
    """Find the nearest visible player per team in metres."""

    count = tracking.frame_count
    home_distance = np.full(count, np.nan, dtype=np.float64)
    away_distance = np.full(count, np.nan, dtype=np.float64)
    gap = np.full(count, np.nan, dtype=np.float64)
    candidate = np.full(count, NO_CANDIDATE, dtype=np.int8)
    if not usable_ball.any():
        return NearestTeamEvidence(candidate, home_distance, away_distance, gap)

    deltas = tracking.slot_positions[usable_ball].astype(np.float64) - ball_positions[
        usable_ball, None, :
    ].astype(np.float64)
    deltas[..., 0] *= pitch_length_m
    deltas[..., 1] *= pitch_width_m
    distances_sq = np.square(deltas, dtype=np.float64).sum(axis=2)
    distances_sq[~np.isfinite(distances_sq)] = np.inf

    home_mask = tracking.team_by_slot == HOME
    away_mask = tracking.team_by_slot == AWAY
    home_min_sq = np.min(distances_sq[:, home_mask], axis=1, initial=np.inf)
    away_min_sq = np.min(distances_sq[:, away_mask], axis=1, initial=np.inf)
    home_min = np.sqrt(home_min_sq)
    away_min = np.sqrt(away_min_sq)
    both = np.isfinite(home_min) & np.isfinite(away_min)
    frame_gap = away_min - home_min
    frame_candidate = np.full(int(usable_ball.sum()), NO_CANDIDATE, dtype=np.int8)
    # Candidate values are encoded as squared distances for the same tolerance
    # used by the verified baseline.
    frame_candidate[both & ((home_min_sq - away_min_sq) < -_DISTANCE_TOLERANCE_M2)] = HOME
    frame_candidate[both & ((away_min_sq - home_min_sq) < -_DISTANCE_TOLERANCE_M2)] = AWAY

    home_distance[usable_ball] = home_min
    away_distance[usable_ball] = away_min
    gap[usable_ball] = frame_gap
    candidate[usable_ball] = frame_candidate
    return NearestTeamEvidence(candidate, home_distance, away_distance, gap)


def visible_near_player_vote(
    tracking: TrackingData,
    ball_positions: NDArray[np.float32],
    usable_ball: NDArray[np.bool_],
    *,
    pitch_length_m: float,
    pitch_width_m: float,
    k: int,
) -> NearPlayerVoteEvidence:
    """Count team labels among the k closest visible slots."""

    if k <= 0:
        raise ValueError("k must be positive")
    candidate = np.full(tracking.frame_count, NO_CANDIDATE, dtype=np.int8)
    home_votes = np.zeros(tracking.frame_count, dtype=np.int16)
    away_votes = np.zeros(tracking.frame_count, dtype=np.int16)
    if not usable_ball.any():
        return NearPlayerVoteEvidence(candidate, home_votes, away_votes)

    deltas = tracking.slot_positions[usable_ball].astype(np.float64) - ball_positions[
        usable_ball, None, :
    ].astype(np.float64)
    deltas[..., 0] *= pitch_length_m
    deltas[..., 1] *= pitch_width_m
    distances = np.sqrt(np.square(deltas, dtype=np.float64).sum(axis=2))
    distances[~np.isfinite(distances)] = np.inf

    selected_home = []
    selected_away = []
    for row in distances:
        visible = np.flatnonzero(np.isfinite(row))
        nearest = visible[np.argsort(row[visible], kind="stable")[:k]]
        selected_home.append(int(np.sum(tracking.team_by_slot[nearest] == HOME)))
        selected_away.append(int(np.sum(tracking.team_by_slot[nearest] == AWAY)))
    home_counts = np.asarray(selected_home, dtype=np.int16)
    away_counts = np.asarray(selected_away, dtype=np.int16)
    frame_candidate = np.full(home_counts.shape, NO_CANDIDATE, dtype=np.int8)
    frame_candidate[home_counts > away_counts] = HOME
    frame_candidate[away_counts > home_counts] = AWAY

    home_votes[usable_ball] = home_counts
    away_votes[usable_ball] = away_counts
    candidate[usable_ball] = frame_candidate
    return NearPlayerVoteEvidence(candidate, home_votes, away_votes)


def ball_motion_evidence(
    observations: BallObservations,
    *,
    fps: int,
    pitch_length_m: float,
    pitch_width_m: float,
    rest_speed_threshold_mps: float,
) -> BallMotionEvidence:
    """Estimate observed-frame speed and sustained rest duration."""

    count = observations.quality.size
    speeds = np.full(count, np.nan, dtype=np.float64)
    rest_duration = np.zeros(count, dtype=np.float64)
    resting_now = np.zeros(count, dtype=bool)
    observed = observations.quality == BallQuality.OBSERVED
    if count >= 2:
        both_observed = observed[1:] & observed[:-1]
        delta = observations.positions[1:].astype(np.float64) - observations.positions[:-1].astype(
            np.float64
        )
        delta[:, 0] *= pitch_length_m
        delta[:, 1] *= pitch_width_m
        speeds[1:][both_observed] = np.sqrt(np.square(delta[both_observed]).sum(axis=1)) * fps

    previous_rest = 0.0
    for frame, speed in enumerate(speeds):
        if observed[frame] and np.isfinite(speed) and speed <= rest_speed_threshold_mps:
            previous_rest += 1.0 / fps
            resting_now[frame] = True
        elif observed[frame]:
            previous_rest = 0.0
        rest_duration[frame] = previous_rest
    return BallMotionEvidence(speeds, rest_duration, resting_now)


def restart_zone_distance(
    ball_positions: NDArray[np.float32],
    usable_ball: NDArray[np.bool_],
    *,
    pitch_length_m: float,
    pitch_width_m: float,
) -> NDArray[np.float64]:
    """Metres to generic corner, goal-line-midpoint and halfway restart anchors."""

    anchors = np.asarray(
        [
            (0.0, 0.0),
            (0.0, 1.0),
            (1.0, 0.0),
            (1.0, 1.0),
            (0.0, 0.5),
            (1.0, 0.5),
            (0.5, 0.0),
            (0.5, 1.0),
            (0.5, 0.5),
        ],
        dtype=np.float64,
    )
    anchors[:, 0] *= pitch_length_m
    anchors[:, 1] *= pitch_width_m
    output = np.full(ball_positions.shape[0], np.nan, dtype=np.float64)
    if not usable_ball.any():
        return output
    points = ball_positions[usable_ball].astype(np.float64)
    points[:, 0] *= pitch_length_m
    points[:, 1] *= pitch_width_m
    distances = np.sqrt(np.square(points[:, None, :] - anchors[None, :, :]).sum(axis=2))
    output[usable_ball] = np.min(distances, axis=1)
    return output


def optimistic_reachability(
    tracking: TrackingData,
    ball_positions: NDArray[np.float32],
    usable_ball: NDArray[np.bool_],
    *,
    pitch_length_m: float,
    pitch_width_m: float,
    extra_speed_mps: float,
) -> ReachabilityEvidence:
    """Estimate seconds if every player runs at their observed speed plus a bonus."""

    count = tracking.frame_count
    home_time = np.full(count, np.nan, dtype=np.float64)
    away_time = np.full(count, np.nan, dtype=np.float64)
    if not usable_ball.any():
        return ReachabilityEvidence(home_time, away_time)

    deltas = tracking.slot_positions[usable_ball].astype(np.float64) - ball_positions[
        usable_ball, None, :
    ].astype(np.float64)
    deltas[..., 0] *= pitch_length_m
    deltas[..., 1] *= pitch_width_m
    distances = np.sqrt(np.square(deltas, dtype=np.float64).sum(axis=2))
    distances[~np.isfinite(distances)] = np.inf
    if tracking.slot_speeds is None:
        speeds = np.zeros_like(distances)
    else:
        speeds = tracking.slot_speeds[usable_ball].astype(np.float64)
        speeds[~np.isfinite(speeds)] = 0.0
    reach_time = distances / np.maximum(speeds + extra_speed_mps, 1e-6)

    home_mask = tracking.team_by_slot == HOME
    away_mask = tracking.team_by_slot == AWAY
    home_time[usable_ball] = np.min(reach_time[:, home_mask], axis=1, initial=np.inf)
    away_time[usable_ball] = np.min(reach_time[:, away_mask], axis=1, initial=np.inf)
    return ReachabilityEvidence(home_time, away_time)


def smart_tagging_evidence(
    frame_count: int,
    intervals: Sequence[TaggingInterval],
) -> SmartTaggingEvidence:
    """Convert optional phase intervals into weak team/dead-ball evidence."""

    team_prior = np.full(frame_count, NO_CANDIDATE, dtype=np.int8)
    dead = np.zeros(frame_count, dtype=bool)
    restart = np.zeros(frame_count, dtype=bool)
    for interval in intervals:
        if not 0 <= interval.start_frame < interval.end_frame <= frame_count:
            raise ValueError("tagging intervals must be non-empty and inside the frame range")
        team = interval.team.strip().lower() if interval.team else None
        if team in {"h", "home", "barcelona"}:
            value = HOME
        elif team in {"a", "away", "athletic club", "atletic club"}:
            value = AWAY
        elif team in {None, "", "n/a"}:
            value = NO_CANDIDATE
        else:
            raise ValueError(f"unsupported tagging team: {interval.team!r}")
        sl = slice(interval.start_frame, interval.end_frame)
        existing = team_prior[sl]
        conflict = (existing != NO_CANDIDATE) & (value != NO_CANDIDATE) & (existing != value)
        if conflict.any():
            raise ValueError("overlapping tagging intervals disagree on team")
        if value != NO_CANDIDATE:
            team_prior[sl] = value
        dead[sl] |= interval.dead_ball
        restart[sl] |= interval.restart
    return SmartTaggingEvidence(team_prior, dead, restart)


def build_evidence_series(
    tracking: TrackingData,
    observations: BallObservations,
    config: StateEngineConfig,
    *,
    tagging: SmartTaggingEvidence | None = None,
) -> EvidenceSeries:
    """Assemble independent evidence signals without hiding their provenance."""

    usable = observations.usable_mask
    nearest = nearest_team_evidence(
        tracking,
        observations.positions,
        usable,
        pitch_length_m=config.pitch_length_m,
        pitch_width_m=config.pitch_width_m,
    )
    vote = visible_near_player_vote(
        tracking,
        observations.positions,
        usable,
        pitch_length_m=config.pitch_length_m,
        pitch_width_m=config.pitch_width_m,
        k=config.integer("near_player_vote_k"),
    )
    motion = ball_motion_evidence(
        observations,
        fps=config.fps,
        pitch_length_m=config.pitch_length_m,
        pitch_width_m=config.pitch_width_m,
        rest_speed_threshold_mps=config.number("ball_rest_speed_mps"),
    )
    restart_distance = restart_zone_distance(
        observations.positions,
        usable,
        pitch_length_m=config.pitch_length_m,
        pitch_width_m=config.pitch_width_m,
    )
    reachability = optimistic_reachability(
        tracking,
        observations.positions,
        usable,
        pitch_length_m=config.pitch_length_m,
        pitch_width_m=config.pitch_width_m,
        extra_speed_mps=config.number("reachability_extra_speed_mps"),
    )

    candidate = nearest.candidate.copy()
    if config.flag("use_visible_team_vote"):
        replace = candidate == NO_CANDIDATE
        candidate[replace] = vote.candidate[replace]
        conflict = (candidate != NO_CANDIDATE) & (vote.candidate != NO_CANDIDATE)
        conflict &= candidate != vote.candidate
        candidate[conflict] = NO_CANDIDATE

    dead = np.zeros(tracking.frame_count, dtype=bool)
    if config.flag("use_ball_rest_dead_ball"):
        dead |= motion.resting_now & (motion.rest_duration_s >= config.number("ball_rest_min_s"))
    restart_evidence = np.zeros(tracking.frame_count, dtype=bool)
    if config.flag("enable_restart_zone"):
        restart_evidence |= np.isfinite(restart_distance) & (
            restart_distance <= config.number("restart_zone_radius_m")
        )

    if tagging is not None and config.flag("enable_smart_tagging"):
        replace = candidate == NO_CANDIDATE
        candidate[replace] = tagging.team_prior[replace]
        conflict = (candidate != NO_CANDIDATE) & (tagging.team_prior != NO_CANDIDATE)
        conflict &= candidate != tagging.team_prior
        candidate[conflict] = NO_CANDIDATE
        dead |= tagging.dead_ball_evidence
        restart_evidence |= tagging.restart_evidence

    ungraded = ungraded_mask(tracking.frame_count, config.ungraded_blocks)
    return EvidenceSeries(
        nearest=nearest,
        near_player_vote=vote,
        ball_motion=motion,
        restart_zone_distance_m=restart_distance,
        reachability=reachability,
        team_candidate=candidate,
        dead_ball_evidence=dead,
        restart_evidence=restart_evidence,
        ungraded_mask=ungraded,
    )


def ungraded_mask(
    frame_count: int,
    blocks: Sequence[tuple[int, int]],
) -> NDArray[np.bool_]:
    output = np.zeros(frame_count, dtype=bool)
    for first, last in blocks:
        output[first : last + 1] = True
    return output
