import numpy as np
import pytest

from mtah_possession.evaluation.external import aggregate_external_metrics, evaluate_predictions


def test_perfect_transitions_have_transition_f1_one() -> None:
    labels = np.asarray(list("HHHAAADDDAA"), dtype="<U1")
    metrics = evaluate_predictions(
        labels,
        labels.copy(),
        fps=10,
        transition_tolerance_frames=0,
    )
    assert metrics.transition_precision == 1.0
    assert metrics.transition_recall == 1.0
    assert metrics.transition_f1 == 1.0


def test_zero_matched_transitions_have_transition_f1_zero() -> None:
    target = np.asarray(list("HHHAA"), dtype="<U1")
    prediction = np.asarray(list("HHHHH"), dtype="<U1")
    metrics = evaluate_predictions(
        target,
        prediction,
        fps=10,
        transition_tolerance_frames=0,
    )
    assert metrics.transition_precision == 0.0
    assert metrics.transition_recall == 0.0
    assert metrics.transition_f1 == 0.0


def test_transition_f1_is_harmonic_mean_when_noise_exists() -> None:
    target = np.asarray(list("HHHAAADDDAA"), dtype="<U1")
    prediction = np.asarray(list("HHAHAADDDAA"), dtype="<U1")
    metrics = evaluate_predictions(
        target,
        prediction,
        fps=10,
        transition_tolerance_frames=0,
    )
    assert metrics.transition_f1 == pytest.approx(
        2
        * metrics.transition_precision
        * metrics.transition_recall
        / (metrics.transition_precision + metrics.transition_recall)
    )


def test_cross_match_macro_and_micro_aggregation_are_defined() -> None:
    first = evaluate_predictions(
        np.asarray(list("HHAA"), dtype="<U1"),
        np.asarray(list("HHAA"), dtype="<U1"),
        fps=10,
        transition_tolerance_frames=0,
    )
    second = evaluate_predictions(
        np.asarray(list("HHDD"), dtype="<U1"),
        np.asarray(list("HHDD"), dtype="<U1"),
        fps=10,
        transition_tolerance_frames=0,
    )
    aggregate = aggregate_external_metrics([first, second])
    assert aggregate.match_count == 2
    assert aggregate.macro_f1_across_matches == pytest.approx(2.0 / 3.0)
    assert aggregate.micro_macro_f1 == 1.0
    assert aggregate.micro_transition_f1 == 1.0
