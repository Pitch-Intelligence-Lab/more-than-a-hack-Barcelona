#!/usr/bin/env python3
"""Inspect one representative record from each CDA-v2 source."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from tools.cda_v2.readers import (
        IDSSEReader,
        SkillCornerReader,
        StatsBombReader,
        WyscoutReader,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "SOURCE_READERS"))
    from cda_v2.readers import (  # type: ignore[no-redef]
        IDSSEReader,
        SkillCornerReader,
        StatsBombReader,
        WyscoutReader,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_root", type=Path)
    args = parser.parse_args()
    root = args.package_root.resolve()
    raw = root / "01_RAW_DATA"

    skill = SkillCornerReader(raw / "skillcorner" / "repository")
    skill_match = skill.matches()[0]
    skill_frame = next(skill.iter_tracking(skill_match["id"]))
    skill_result = {
        "matches": len(skill.matches()),
        "match_id": skill_match["id"],
        "first_frame": skill_frame["frame"],
    }

    idsse = IDSSEReader(raw / "idsse" / "repository")
    idsse_match = idsse.match_ids()[0]
    idsse_result = {
        "matches": len(idsse.match_ids()),
        "match_id": idsse_match,
        "metadata": idsse.read_metadata(idsse_match),
        "first_event": next(idsse.iter_events(idsse_match)),
    }

    statsbomb = StatsBombReader(raw / "statsbomb" / "repository")
    stats_match = next(statsbomb.matches())
    stats_events = statsbomb.read_json_list(statsbomb.events_path(stats_match.match_id))
    stats_result = {
        "competition": stats_match.competition,
        "season": stats_match.season,
        "match_id": stats_match.match_id,
        "events": len(stats_events),
        "first_event": stats_events[0],
    }

    wyscout = WyscoutReader(raw / "wyscout" / "repository")
    wyscout_match_id = wyscout.match_ids()[0]
    wyscout_match = wyscout.read_match(wyscout_match_id)
    wyscout_result = {
        "matches": len(wyscout.match_ids()),
        "match_id": wyscout_match_id,
        "events": len(wyscout_match["events"]),
        "first_event": wyscout_match["events"][0],
    }

    print(
        json.dumps(
            {
                "SkillCorner": skill_result,
                "IDSSE": idsse_result,
                "StatsBomb": stats_result,
                "Wyscout": wyscout_result,
            },
            indent=2,
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
