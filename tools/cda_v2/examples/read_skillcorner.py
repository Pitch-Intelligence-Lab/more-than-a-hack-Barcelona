#!/usr/bin/env python3
"""Print the first SkillCorner tracking frame."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from tools.cda_v2.readers import SkillCornerReader
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "SOURCE_READERS"))
    from cda_v2.readers import SkillCornerReader  # type: ignore[no-redef]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("match_id")
    args = parser.parse_args()
    reader = SkillCornerReader(args.repository)
    print(json.dumps(next(reader.iter_tracking(args.match_id)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
