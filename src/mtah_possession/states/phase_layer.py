"""Separate phase, restart and confirmed dead-ball evidence layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray

from mtah_possession.states.possession_state import duration_to_frames


class PhaseKind(StrEnum):
    IN_PLAY = "in_play"
    KICKOFF = "kickoff"
    THROW_IN = "throw_in"
    FREE_KICK = "free_kick"
    CORNER = "corner"
    GOAL_KICK = "goal_kick"
    HALFTIME = "halftime"
    EMERGENCY_STOPPAGE = "emergency_stoppage"
    RESTART = "restart"


@dataclass(frozen=True)
class PhaseDirective:
    start_frame: int
    end_frame: int
    kind: PhaseKind
    confirmed_dead: bool = False
    restart: bool = False
    source: str = "synthetic-phase"


@dataclass(frozen=True)
class PhaseLayerEvidence:
    forced_dead_mask: NDArray[np.bool_]
    restart_evidence: NDArray[np.bool_]
    source_codes: NDArray[np.str_]

    @property
    def forced_dead_frames(self) -> int:
        return int(self.forced_dead_mask.sum())

    @property
    def restart_frames(self) -> int:
        return int(self.restart_evidence.sum())


def compile_phase_evidence(
    frame_count: int,
    fps: int,
    directives: tuple[PhaseDirective, ...],
    *,
    restart_window_s: float = 0.5,
) -> PhaseLayerEvidence:
    if frame_count <= 0:
        raise ValueError("frame_count must be positive")
    if restart_window_s < 0:
        raise ValueError("restart_window_s must be non-negative")
    restart_frames = max(1, duration_to_frames(restart_window_s, fps))
    forced_dead = np.zeros(frame_count, dtype=bool)
    restart = np.zeros(frame_count, dtype=bool)
    source_codes = np.full(frame_count, "phase-none", dtype="<U48")

    for directive in directives:
        if not 0 <= directive.start_frame < directive.end_frame <= frame_count:
            raise ValueError("phase directive lies outside the match")
        if directive.confirmed_dead:
            sl = slice(directive.start_frame, directive.end_frame)
            forced_dead[sl] = True
            source_codes[sl] = f"dead:{directive.kind}:{directive.source}"
        if directive.restart:
            start = directive.start_frame
            end = min(frame_count, start + restart_frames)
            restart[start:end] = True
            empty = source_codes[start:end] == "phase-none"
            source_codes[start:end][empty] = f"restart:{directive.kind}:{directive.source}"
    return PhaseLayerEvidence(forced_dead, restart, source_codes)


def derive_gap_dead_directives(
    periods: tuple[tuple[int, int], ...],
    in_play_intervals: tuple[tuple[int, int], ...],
    *,
    source: str,
) -> tuple[PhaseDirective, ...]:
    """Treat only inter-phase gaps inside declared periods as confirmed dead."""
    sorted_play = sorted(in_play_intervals)
    directives: list[PhaseDirective] = []
    for period_start, period_end in periods:
        if period_end <= period_start:
            raise ValueError("period boundaries must be increasing")
        cursor = period_start
        for first, end in sorted_play:
            if end <= period_start or first >= period_end:
                continue
            overlap_start = max(first, period_start)
            overlap_end = min(end, period_end)
            if overlap_start > cursor:
                directives.append(
                    PhaseDirective(
                        cursor,
                        overlap_start,
                        PhaseKind.EMERGENCY_STOPPAGE,
                        confirmed_dead=True,
                        source=source,
                    )
                )
            cursor = max(cursor, overlap_end)
        if cursor < period_end:
            directives.append(
                PhaseDirective(
                    cursor,
                    period_end,
                    PhaseKind.EMERGENCY_STOPPAGE,
                    confirmed_dead=True,
                    source=source,
                )
            )
    return tuple(directives)
