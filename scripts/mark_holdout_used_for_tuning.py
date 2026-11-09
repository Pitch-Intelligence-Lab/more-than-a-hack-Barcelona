#!/usr/bin/env python3
"""Permanently compromise a completed holdout used for tuning."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mtah_possession.governance.ledger import (  # noqa: E402
    mark_holdout_used_for_tuning,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger-dir",
        default=str(ROOT / "outputs" / "holdout"),
    )
    parser.add_argument("--provider", required=True)
    parser.add_argument(
        "--match-id",
        dest="match_ids",
        action="append",
        required=True,
        help="Holdout match ID; repeat for a multi-match holdout.",
    )
    parser.add_argument("--prediction-sha256", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args(argv)

    try:
        ledger = mark_holdout_used_for_tuning(
            args.ledger_dir,
            provider=args.provider,
            match_ids=tuple(args.match_ids),
            prediction_sha256=args.prediction_sha256,
            reason=args.reason,
        )
    except (OSError, ValueError) as error:
        print(f"FAIL  {error}", file=sys.stderr)
        return 1

    print(f"holdout_id={ledger.holdout_id}")
    print(f"state={ledger.state.value}")
    print(f"ledger={ledger.path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
