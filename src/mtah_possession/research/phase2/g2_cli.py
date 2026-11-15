"""CLI for deterministic G2 short-window feature derivation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mtah_possession.research.phase2.g2 import G2Error, derive_g2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    derive = subparsers.add_parser("derive-g2", help="derive G2 from one P2 feature file")
    derive.add_argument("--features", type=Path, required=True)
    derive.add_argument("--metadata", type=Path)
    derive.add_argument("--output-dir", type=Path, required=True)
    derive.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = derive_g2(
            features_path=args.features,
            metadata_path=args.metadata,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
    except (G2Error, OSError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
