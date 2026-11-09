#!/usr/bin/env python3
"""Build Tang Candidate B through the independent adapter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mtah_possession.candidates.tang.adapter import build_candidate  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Tang Candidate B possession CSV.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--health-report", default=None)
    parser.add_argument("--decision-log", default=None)
    parser.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = Path(args.output)
    if output.exists() and not args.force:
        print(f"output already exists: {output}; rerun with --force", file=sys.stderr)
        return 1
    try:
        result = build_candidate(
            output_path=output,
            data_root=args.data_dir,
            config_path=args.config,
            health_report=args.health_report,
            decision_log=args.decision_log,
        )
    except Exception as error:
        print(f"candidate build failed: {error}", file=sys.stderr)
        return 1
    health = result.health
    print(f"OK    wrote {health['rows']} frames to {output}")
    print(f"      labels: {health['label_counts']}")
    print(f"      segments: {health['segments_by_label']}")
    print(
        "      emission valid/invalid: "
        f"{health['emission_valid_frames']}/{health['emission_invalid_frames']}"
    )
    print(f"      smart conflicts: {health['smart_conflict_frames']}")
    print(f"      sha256: {health['output_sha256']}")
    print(f"      generalisation: {health['generalisation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
