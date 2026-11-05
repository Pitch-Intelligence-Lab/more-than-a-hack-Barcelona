import pytest

from mtah_possession.states.phase_layer import (
    PhaseDirective,
    PhaseKind,
    compile_phase_evidence,
    derive_gap_dead_directives,
)


@pytest.mark.parametrize(
    "kind",
    [
        PhaseKind.KICKOFF,
        PhaseKind.THROW_IN,
        PhaseKind.FREE_KICK,
        PhaseKind.CORNER,
        PhaseKind.GOAL_KICK,
        PhaseKind.HALFTIME,
        PhaseKind.EMERGENCY_STOPPAGE,
    ],
)
def test_dead_phase_types_are_protected_and_restartable(kind: PhaseKind) -> None:
    evidence = compile_phase_evidence(
        40,
        10,
        (
            PhaseDirective(10, 20, kind, confirmed_dead=True),
            PhaseDirective(20, 21, PhaseKind.RESTART, restart=True),
        ),
        restart_window_s=0.5,
    )
    assert evidence.forced_dead_mask[10:20].all()
    assert evidence.restart_evidence[20:25].all()
    assert evidence.source_codes[10].startswith("dead:")


def test_gap_between_phases_is_dead_but_outside_period_is_not() -> None:
    directives = derive_gap_dead_directives(
        ((0, 100),),
        ((10, 20), (40, 50)),
        source="fixture",
    )
    evidence = compile_phase_evidence(110, 10, directives)
    assert evidence.forced_dead_mask[0:10].all()
    assert not evidence.forced_dead_mask[10:20].any()
    assert evidence.forced_dead_mask[20:40].all()
    assert not evidence.forced_dead_mask[100:].any()
