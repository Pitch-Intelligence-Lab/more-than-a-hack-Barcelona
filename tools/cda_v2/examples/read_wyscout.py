#!/usr/bin/env python3
"""Print a Wyscout processed match summary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from tools.cda_v2.readers import WyscoutReader
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "SOURCE_READERS"))
    from cda_v2.readers import WyscoutReader  # type: ignore[no-redef]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("match_id", type=int)
    args = parser.parse_args()
    match = WyscoutReader(args.repository).read_match(args.match_id)
    print(
        json.dumps(
            {
                "match_id": args.match_id,
                "events": len(match["events"]),
                "teams": len(match["teams"]),
                "players": len(match["players"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
