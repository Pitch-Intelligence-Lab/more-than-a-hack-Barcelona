"""Command-line entrypoint for the bounded Phase-2 extractor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mtah_possession.research.phase2.extractor import (
    ExtractionError,
    extract_idss,
    smoke_idss,
)


def _default_split_config() -> Path:
    return (
        Path(__file__).resolve().parents[4] / "configs" / "research" / "phase2" / "idss_split.json"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract-idss", help="extract one approved IDSSE match")
    extract.add_argument("--package-root", type=Path, required=True)
    extract.add_argument("--match-id", required=True)
    extract.add_argument("--output-dir", type=Path, required=True)
    extract.add_argument("--split-config", type=Path, default=_default_split_config())
    extract.add_argument("--overwrite", action="store_true")

    smoke = subparsers.add_parser(
        "smoke-idss",
        help="verify metadata and file identities without frame extraction",
    )
    smoke.add_argument("--package-root", type=Path, required=True)
    smoke.add_argument("--match-id", action="append", dest="match_ids")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "extract-idss":
            result = extract_idss(
                package_root=args.package_root,
                match_id=args.match_id,
                output_dir=args.output_dir,
                split_config_path=args.split_config,
                overwrite=args.overwrite,
            )
        else:
            result = smoke_idss(
                package_root=args.package_root,
                match_ids=args.match_ids,
            )
    except (ExtractionError, OSError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
