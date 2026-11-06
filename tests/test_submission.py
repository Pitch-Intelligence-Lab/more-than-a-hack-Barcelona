from pathlib import Path

import numpy as np
import pytest

from mtah_possession.features.possession import majority_vote_labels
from mtah_possession.pipeline.build_submission import write_submission_atomic
from mtah_possession.validation.submission import (
    SubmissionValidationError,
    sha256_file,
    validate_submission,
)


def write_csv(path: Path, rows: int = 3, *, header: str = "frame,label") -> Path:
    lines = [header]
    for frame in range(rows):
        lines.append(f"{frame},X")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_valid_file_reports_counts_and_hash(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "ok.csv")
    report = validate_submission(path, expected_rows=3)
    assert report.rows == 3
    assert report.label_counts == {"H": 0, "A": 0, "D": 0, "X": 3}
    assert report.sha256 == sha256_file(path)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("frame,label\n0,X\n1,X\n", "expected 3 data rows"),
        ("label,frame\n0,X\n1,X\n2,X\n", "header must be exactly"),
        ("frame,label\n0,X\n2,X\n3,X\n", "frame sequence failed"),
        ("frame,label\n0,X\n1,Z\n2,X\n", "invalid label"),
        ("frame,label\n0,X\n1,\n2,X\n", "blank cell"),
        ("frame,label\n0,X,extra\n1,X\n2,X\n", "exactly 2 cells"),
    ],
)
def test_each_contract_failure_has_clear_reason(
    tmp_path: Path,
    content: str,
    message: str,
) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(SubmissionValidationError, match=message):
        validate_submission(path, expected_rows=3)


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SubmissionValidationError, match="does not exist"):
        validate_submission(tmp_path / "absent.csv", expected_rows=3)


def test_atomic_writer_builds_exact_official_length(tmp_path: Path) -> None:
    labels = majority_vote_labels(
        np.zeros(199_319, dtype=np.int8),
        window_half_width_frames=50,
    )
    destination = write_submission_atomic(
        tmp_path / "submission.csv",
        labels,
        expected_frames=199_319,
    )
    report = validate_submission(destination)
    assert report.rows == 199_319
    assert report.label_counts["H"] == 199_319


def test_writer_failure_leaves_no_final_or_temporary_file(tmp_path: Path) -> None:
    labels = np.asarray(["H"], dtype="<U1")
    with pytest.raises(SubmissionValidationError, match="expected 2 data rows"):
        write_submission_atomic(
            tmp_path / "submission.csv",
            labels,
            expected_frames=2,
        )
    assert list(tmp_path.iterdir()) == []


def test_deterministic_output_bytes(tmp_path: Path) -> None:
    candidates = np.asarray([0, 1, -1, 0, 1, 1, 0], dtype=np.int8)
    labels = majority_vote_labels(candidates, window_half_width_frames=1)
    first = write_submission_atomic(tmp_path / "first.csv", labels, expected_frames=7)
    second = write_submission_atomic(tmp_path / "second.csv", labels, expected_frames=7)
    assert first.read_bytes() == second.read_bytes()
