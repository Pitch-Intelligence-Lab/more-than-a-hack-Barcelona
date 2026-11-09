#!/usr/bin/env python3
"""Print a StatsBomb match and event count."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from tools.cda_v2.readers import StatsBombReader
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "SOURCE_READERS"))
    from cda_v2.readers import StatsBombReader  # type: ignore[no-redef]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("match_id", type=int)
    args = parser.parse_args()
    reader = StatsBombReader(args.repository)
    events = reader.read_json_list(reader.events_path(args.match_id))
    print(json.dumps({"match_id": args.match_id, "event_count": len(events)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
