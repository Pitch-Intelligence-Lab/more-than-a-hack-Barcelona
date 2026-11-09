#!/usr/bin/env python3
"""Print IDSSE metadata and the first synchronized event."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from tools.cda_v2.readers import IDSSEReader
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "SOURCE_READERS"))
    from cda_v2.readers import IDSSEReader  # type: ignore[no-redef]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("match_id")
    args = parser.parse_args()
    reader = IDSSEReader(args.repository)
    print(
        json.dumps(
            {
                "metadata": reader.read_metadata(args.match_id),
                "first_event": next(reader.iter_events(args.match_id)),
            },
            indent=2,
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
