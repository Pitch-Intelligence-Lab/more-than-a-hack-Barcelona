"""Validate the official frame,label submission contract."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from mtah_possession.config import EXPECTED_TACTICAL_FRAMES

LABELS = ("H", "A", "D", "X")
HEADER = ("frame", "label")


class SubmissionValidationError(ValueError):
    """Raised with a concise, machine-readable validation failure."""


@dataclass(frozen=True)
class ValidationReport:
    path: Path
    rows: int
    sha256: str
    label_counts: dict[str, int]


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_submission(
    path: str | Path,
    *,
    expected_rows: int = EXPECTED_TACTICAL_FRAMES,
) -> ValidationReport:
    """Validate header, row count, frame sequence, labels, and empty cells."""

    submission = Path(path)
    if not submission.is_file():
        raise SubmissionValidationError(f"file does not exist: {submission}")

    counts = {label: 0 for label in LABELS}
    rows = 0
    try:
        with submission.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if header != list(HEADER):
                raise SubmissionValidationError(
                    f"header must be exactly frame,label; found {header!r}"
                )
            for expected_frame, row in enumerate(reader):
                if len(row) != 2:
                    raise SubmissionValidationError(
                        f"CSV row {expected_frame + 2} must have exactly 2 cells"
                    )
                frame_cell, label = row
                if frame_cell == "" or label == "":
                    raise SubmissionValidationError(f"blank cell at CSV row {expected_frame + 2}")
                try:
                    frame = int(frame_cell)
                except ValueError as error:
                    raise SubmissionValidationError(
                        f"non-integer frame at CSV row {expected_frame + 2}"
                    ) from error
                if frame != expected_frame:
                    raise SubmissionValidationError(
                        f"frame sequence failed at CSV row {expected_frame + 2}: "
                        f"expected {expected_frame}, found {frame}"
                    )
                if label not in LABELS:
                    raise SubmissionValidationError(
                        f"invalid label at frame {frame}: expected H, A, D, or X"
                    )
                counts[label] += 1
                rows += 1
    except UnicodeDecodeError as error:
        raise SubmissionValidationError("submission is not valid UTF-8") from error

    if rows != expected_rows:
        raise SubmissionValidationError(f"expected {expected_rows} data rows, found {rows}")
    return ValidationReport(
        path=submission.resolve(),
        rows=rows,
        sha256=sha256_file(submission),
        label_counts=counts,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a possession submission CSV.")
    parser.add_argument("submission", help="frame,label CSV")
    parser.add_argument(
        "--rows",
        type=int,
        default=EXPECTED_TACTICAL_FRAMES,
        help="expected data row count",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    path = Path(args.submission)
    try:
        report = validate_submission(path, expected_rows=args.rows)
    except (SubmissionValidationError, OSError) as error:
        print(f"FAIL  {path.name}: {error}", file=sys.stderr)
        if path.is_file():
            print(f"      sha256: {sha256_file(path)}", file=sys.stderr)
        return 1

    print(f"OK    {report.path}")
    print(f"      rows: {report.rows}")
    print(f"      frames: 0..{report.rows - 1}")
    print("      labels: " + ", ".join(f"{label}={report.label_counts[label]}" for label in LABELS))
    print(f"      sha256: {report.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
