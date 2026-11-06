from pathlib import Path

import numpy as np

from mtah_possession.data.observations import BallObservations, BallQuality
from mtah_possession.pipeline.health import build_health_report
from mtah_possession.validation.submission import ValidationReport


def test_health_reports_forced_dead_block_and_cleanup_removals() -> None:
    labels = np.asarray(["H", "H", "D", "D", "H", "H"])
    observations = BallObservations(
        positions=np.full((6, 2), 0.5, dtype=np.float32),
        quality=np.full(6, BallQuality.OBSERVED, dtype=np.int8),
        observed_mask=np.ones(6, dtype=bool),
    )
    validation = ValidationReport(
        path=Path("submission.csv"),
        rows=6,
        sha256="abc",
        label_counts={"H": 4, "A": 0, "D": 2, "X": 0},
    )
    report = build_health_report(
        labels=labels,
        observations=observations,
        reasons=np.asarray(["persist", "persist", "forced", "forced", "persist", "persist"]),
        validation=validation,
        input_sha256={"atd_raw": "def"},
        fps=25,
        cleanup_removed_label_counts={"H": 0, "A": 0, "D": 0},
        forced_dead_mask=np.asarray([False, False, True, True, False, False]),
    )
    assert report.forced_dead_frames == 2
    assert report.forced_dead_label_counts == {"H": 0, "A": 0, "D": 2, "X": 0}
    assert report.forced_dead_all_d is True
    assert report.cleanup_removed_label_counts == {"H": 0, "A": 0, "D": 0}
