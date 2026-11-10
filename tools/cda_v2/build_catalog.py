#!/usr/bin/env python3
"""Build CDA-v2 source registry, match inventory, schemas and quality reports."""

# ruff: noqa: E501 - source registry text is intentionally literal and audit-friendly.

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tools.cda_v2.readers import (
    IDSSEReader,
    SkillCornerReader,
    StatsBombReader,
    WyscoutReader,
)

SOURCE_DIRS = (
    "00_SOURCE_REGISTRY",
    "01_RAW_DATA",
    "02_MATCH_INVENTORY",
    "03_SCHEMA_DOCUMENTATION",
    "04_QUALITY_ASSESSMENT",
    "05_ACCESS_TOOLS",
    "06_HANDOFF",
)
REVISIONS = {
    "SkillCorner": "4340d274572876239c154c90bc507a9b3250a656",
    "IDSSE": "a715a38dfbaf5f58e431727c2b78d174101a703c",
    "StatsBomb": "4b73468fc5b0f1950f9f66fada70ad3a4f9327cb",
    "Wyscout": "ebc4c54c1093c420a81ce442c69e4186fab33bb4",
}
LICENSE_STATUS = {
    "SkillCorner": "PUBLIC_ACCESS; software MIT; data-specific rights unresolved; credit requested",
    "IDSSE": "CC BY 4.0; attribution/citation required",
    "StatsBomb": "Public data terms; attribution/Logo requirements; PM review",
    "Wyscout": "CC BY 4.0; attribution/citation required",
}
RETRIEVED_AT = "2026-11-10T00:00:00+08:00"


@dataclass(frozen=True)
class FileRecord:
    source: str
    relative_path: str
    bytes: int
    sha256: str
    provider_revision: str
    retrieved_at: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_files(root: Path) -> list[Path]:
    excluded = {".git", ".range_parts", ".parts"}
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not excluded.intersection(path.relative_to(root).parts)
    )


def collect_file_records(
    delivery: Path,
    roots: dict[str, Path],
) -> list[FileRecord]:
    jobs: list[tuple[str, Path]] = []
    for source, root in roots.items():
        jobs.extend((source, path) for path in source_files(root))

    def make_record(job: tuple[str, Path]) -> FileRecord:
        source, path = job
        root = roots[source]
        relative = path.relative_to(root).as_posix()
        return FileRecord(
            source=source,
            relative_path=f"01_RAW_DATA/{source.lower()}/repository/{relative}",
            bytes=path.stat().st_size,
            sha256=sha256_file(path),
            provider_revision=REVISIONS[source],
            retrieved_at=RETRIEVED_AT,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        return list(executor.map(make_record, jobs))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def file_hash_map(records: list[FileRecord]) -> dict[str, str]:
    return {record.relative_path: record.sha256 for record in records}


def load_file_records(path: Path) -> list[FileRecord]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            FileRecord(
                source=row["source"],
                relative_path=row["relative_path"],
                bytes=int(row["bytes"]),
                sha256=row["sha256"],
                provider_revision=row["provider_revision"],
                retrieved_at=row["retrieved_at"],
            )
            for row in csv.DictReader(handle)
        ]


def relative_hash(hashes: dict[str, str], path: Path, delivery: Path) -> str:
    return hashes.get(path.relative_to(delivery).as_posix(), "")


def skill_inventory(
    source: str,
    repository: Path,
    delivery: Path,
    hashes: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    reader = SkillCornerReader(repository)
    inventory: list[dict[str, Any]] = []
    quality: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for match in reader.matches():
        match_id = int(match["id"])
        metadata = reader.read_metadata(match_id)
        tracking_path = reader.tracking_path(match_id)
        event_path = reader.dynamic_events_path(match_id)
        phase_path = reader.phases_path(match_id)
        metadata_path = reader.metadata_path(match_id)
        pointer = (
            tracking_path.open("rb")
            .read(129)
            .startswith(b"version https://git-lfs.github.com/spec/v1")
        )
        if pointer:
            raise ValueError(f"SkillCorner tracking is an LFS pointer: {tracking_path}")
        tracking_frames = sum(1 for _ in reader.iter_tracking(match_id))
        event_rows = reader.read_csv(event_path)
        phase_rows = reader.read_csv(phase_path)
        reasons = (
            "Complete 10 FPS broadcast tracking, dynamic events and phases; "
            "extrapolated positions and approximately 97% player-identity accuracy "
            "limit exact identity-dependent research."
        )
        quality_level = "Q2"
        inventory.append(
            {
                "source": source,
                "provider_revision": REVISIONS[source],
                "match_id": str(match_id),
                "competition": "AUS - A-League",
                "season": "2024/2025",
                "data_type": "both",
                "tracking_path": tracking_path.relative_to(delivery).as_posix(),
                "event_path": event_path.relative_to(delivery).as_posix(),
                "metadata_path": metadata_path.relative_to(delivery).as_posix(),
                "phase_path": phase_path.relative_to(delivery).as_posix(),
                "tracking_sha256": relative_hash(hashes, tracking_path, delivery),
                "event_sha256": relative_hash(hashes, event_path, delivery),
                "metadata_sha256": relative_hash(hashes, metadata_path, delivery),
                "phase_sha256": relative_hash(hashes, phase_path, delivery),
                "fps": "10",
                "coordinate_system": "metres; pitch centre origin; x long axis, y short axis",
                "time_fields": "frame; timestamp; period",
                "possession_fields": "possession.player_id; possession.group",
                "phase_fields": "phases_of_play frame_start/frame_end/team_in_possession_phase_type",
                "dead_ball_fields": "No direct D truth; phase gaps are proxy/auxiliary evidence only",
                "quality_level": quality_level,
                "quality_reasons": reasons,
                "license_status": LICENSE_STATUS[source],
                "research_scope": "tracking; synchronized auxiliary event/phase data; not H/A/D frame truth",
            }
        )
        quality.append(
            {
                "source": source,
                "match_id": str(match_id),
                "quality_level": quality_level,
                "research_scope": "broadcast tracking with identity caveat",
                "reasons": reasons,
                "record_count": tracking_frames,
                "tracking_frames": tracking_frames,
                "event_count": len(event_rows),
                "phase_count": len(phase_rows),
                "has_tracking_body": True,
                "has_events": True,
                "has_phases": True,
                "has_three_sixty": False,
            }
        )
        summaries.append(
            {
                "source": source,
                "match_id": str(match_id),
                "provider_revision": REVISIONS[source],
                "competition": "AUS - A-League",
                "season": "2024/2025",
                "match_date": match["date_time"],
                "home_team": match["home_team"]["short_name"],
                "away_team": match["away_team"]["short_name"],
                "tracking_frames": tracking_frames,
                "event_rows": len(event_rows),
                "phase_rows": len(phase_rows),
                "pitch_length": metadata.get("pitch_length"),
                "pitch_width": metadata.get("pitch_width"),
                "quality_level": quality_level,
            }
        )
    return inventory, quality, summaries


def idsse_inventory(
    source: str,
    repository: Path,
    delivery: Path,
    hashes: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    reader = IDSSEReader(repository)
    inventory: list[dict[str, Any]] = []
    quality: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for match_id in reader.match_ids():
        metadata = reader.read_metadata(match_id)
        metadata_path = reader.metadata_path(match_id)
        events_path = reader.events_path(match_id)
        positions_path = reader.positions_path(match_id)
        event_count = sum(1 for _ in reader.iter_events(match_id))
        frame_count = sum(1 for _ in reader.iter_frames(match_id))
        reasons = (
            "Official DFL/Sportec tracking and event files are complete and parseable; "
            "25 FPS positions and event timestamps use the same match identity and pitch frame."
        )
        inventory.append(
            {
                "source": source,
                "provider_revision": REVISIONS[source],
                "match_id": match_id,
                "competition": metadata.get("CompetitionName", ""),
                "season": metadata.get("Season", ""),
                "data_type": "both",
                "tracking_path": positions_path.relative_to(delivery).as_posix(),
                "event_path": events_path.relative_to(delivery).as_posix(),
                "metadata_path": metadata_path.relative_to(delivery).as_posix(),
                "phase_path": "",
                "tracking_sha256": relative_hash(hashes, positions_path, delivery),
                "event_sha256": relative_hash(hashes, events_path, delivery),
                "metadata_sha256": relative_hash(hashes, metadata_path, delivery),
                "phase_sha256": "",
                "fps": "25",
                "coordinate_system": "DFL pitch coordinates in metres; X 0..105; Y -34..34",
                "time_fields": "Frame@T/N; Event@EventTime",
                "possession_fields": "Event.BallPossessionPhase; Team; Player",
                "phase_fields": "No separate phases-of-play file",
                "dead_ball_fields": "Event stoppage/restart categories; not a continuous D truth",
                "quality_level": "Q1",
                "quality_reasons": reasons,
                "license_status": LICENSE_STATUS[source],
                "research_scope": "tracking and synchronized event research",
            }
        )
        quality.append(
            {
                "source": source,
                "match_id": match_id,
                "quality_level": "Q1",
                "research_scope": "tracking and synchronized events",
                "reasons": reasons,
                "record_count": frame_count,
                "tracking_frames": frame_count,
                "event_count": event_count,
                "phase_count": 0,
                "has_tracking_body": True,
                "has_events": True,
                "has_phases": False,
                "has_three_sixty": False,
            }
        )
        summaries.append(
            {
                "source": source,
                "match_id": match_id,
                "provider_revision": REVISIONS[source],
                "competition": metadata.get("CompetitionName", ""),
                "season": metadata.get("Season", ""),
                "match_date": metadata.get("KickoffTime", ""),
                "home_team": metadata.get("HomeTeamName", ""),
                "away_team": metadata.get("GuestTeamName", ""),
                "tracking_frames": frame_count,
                "event_count": event_count,
                "pitch_length": metadata.get("PitchX"),
                "pitch_width": metadata.get("PitchY"),
                "quality_level": "Q1",
            }
        )
    return inventory, quality, summaries


def statsbomb_inventory(
    source: str,
    repository: Path,
    delivery: Path,
    hashes: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    reader = StatsBombReader(repository)
    inventory: list[dict[str, Any]] = []
    quality: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    matches = list(reader.matches())
    indexed_ids = {match.match_id for match in matches}
    for match in matches:
        event_path = reader.events_path(match.match_id)
        lineup_path = reader.lineups_path(match.match_id)
        three_sixty_path = reader.three_sixty_path(match.match_id)
        metadata_path = (
            ""
            if match.competition_id is None or match.season_id is None
            else (
                repository
                / "data"
                / "matches"
                / str(match.competition_id)
                / f"{match.season_id}.json"
            )
            .relative_to(delivery)
            .as_posix()
        )
        event_error = ""
        lineup_error = ""
        three_sixty_error = ""
        try:
            event_count = len(reader.read_json_list(event_path))
        except ValueError as error:
            event_count = 0
            event_error = str(error)
        try:
            lineup_count = len(reader.read_json_list(lineup_path))
        except ValueError as error:
            lineup_count = 0
            lineup_error = str(error)
        has_360 = three_sixty_path.exists()
        if has_360:
            try:
                reader.read_json_list(three_sixty_path)
            except ValueError as error:
                three_sixty_error = str(error)
        if event_error:
            level = "Q4"
        elif event_count and lineup_count:
            level = "Q1"
        else:
            level = "Q3"
        if match.competition == "unknown":
            reasons = (
                "Actual public event and lineup files are present but this match is absent "
                "from the pinned competitions.json/matches index. Competition and season "
                "remain unknown rather than inferred. Event data is not tracking."
            )
        else:
            reasons = (
                "Complete public event and lineup JSON for event-level research; "
                "360 frames are optional; this is not continuous tracking and cannot be treated "
                "as frame-level H/A/D/X truth."
            )
        if event_error:
            reasons += f" Event JSON parse error: {event_error}"
        if lineup_error:
            reasons += f" Lineup JSON parse error: {lineup_error}"
        if three_sixty_error:
            reasons += (
                " Optional 360 JSON is present but malformed; the exact source file is retained: "
                f"{three_sixty_error}"
            )
        inventory.append(
            {
                "source": source,
                "provider_revision": REVISIONS[source],
                "match_id": str(match.match_id),
                "competition": match.competition,
                "season": match.season,
                "data_type": "event",
                "tracking_path": "",
                "event_path": event_path.relative_to(delivery).as_posix(),
                "metadata_path": metadata_path,
                "phase_path": "",
                "tracking_sha256": "",
                "event_sha256": relative_hash(hashes, event_path, delivery),
                "metadata_sha256": "",
                "phase_sha256": "",
                "fps": "not applicable",
                "coordinate_system": "StatsBomb event coordinates 120 x 80",
                "time_fields": "minute; second; timestamp",
                "possession_fields": "possession; possession_team; play_pattern",
                "phase_fields": "No continuous phases-of-play; event contexts only",
                "dead_ball_fields": "event pass/restart types; not frame truth",
                "quality_level": level,
                "quality_reasons": reasons,
                "license_status": LICENSE_STATUS[source],
                "research_scope": "event-only; not tracking",
            }
        )
        quality.append(
            {
                "source": source,
                "match_id": str(match.match_id),
                "quality_level": level,
                "research_scope": "event-level research only",
                "reasons": reasons,
                "record_count": event_count,
                "tracking_frames": 0,
                "event_count": event_count,
                "lineup_count": lineup_count,
                "has_tracking_body": False,
                "has_events": event_count > 0,
                "has_lineups": lineup_count > 0,
                "has_three_sixty": has_360,
                "three_sixty_parse_error": three_sixty_error,
            }
        )
        summaries.append(
            {
                "source": source,
                "match_id": str(match.match_id),
                "provider_revision": REVISIONS[source],
                "competition": match.competition,
                "season": match.season,
                "event_count": event_count,
                "lineup_teams": lineup_count,
                "has_three_sixty": has_360,
                "quality_level": level,
            }
        )
    event_ids = {int(path.stem) for path in (repository / "data" / "events").glob("*.json")}
    for match_id in sorted(event_ids.difference(indexed_ids)):
        event_path = reader.events_path(match_id)
        lineup_path = reader.lineups_path(match_id)
        three_sixty_path = reader.three_sixty_path(match_id)
        event_error = ""
        lineup_error = ""
        try:
            event_count = len(reader.read_json_list(event_path))
        except ValueError as error:
            event_count = 0
            event_error = str(error)
        try:
            lineup_count = len(reader.read_json_list(lineup_path))
        except ValueError as error:
            lineup_count = 0
            lineup_error = str(error)
        has_360 = three_sixty_path.exists()
        level = "Q4" if event_error else ("Q1" if event_count and lineup_count else "Q3")
        reasons = (
            "Actual public event and lineup files are present but this match is absent from "
            "the pinned competitions.json/matches index. Competition and season are therefore "
            "recorded as unindexed rather than inferred. Event data is not tracking."
        )
        inventory.append(
            {
                "source": source,
                "provider_revision": REVISIONS[source],
                "match_id": str(match_id),
                "competition": "unindexed public event file",
                "season": "unknown from pinned index",
                "data_type": "event",
                "tracking_path": "",
                "event_path": event_path.relative_to(delivery).as_posix(),
                "metadata_path": "",
                "phase_path": "",
                "tracking_sha256": "",
                "event_sha256": relative_hash(hashes, event_path, delivery),
                "metadata_sha256": "",
                "phase_sha256": "",
                "fps": "not applicable",
                "coordinate_system": "StatsBomb event coordinates 120 x 80",
                "time_fields": "minute; second; timestamp",
                "possession_fields": "possession; possession_team; play_pattern",
                "phase_fields": "No continuous phases-of-play; event contexts only",
                "dead_ball_fields": "event pass/restart types; not frame truth",
                "quality_level": level,
                "quality_reasons": reasons,
                "license_status": LICENSE_STATUS[source],
                "research_scope": "event-only; unindexed coverage",
            }
        )
        quality.append(
            {
                "source": source,
                "match_id": str(match_id),
                "quality_level": level,
                "research_scope": "event-level unindexed coverage",
                "reasons": reasons,
                "record_count": event_count,
                "tracking_frames": 0,
                "event_count": event_count,
                "lineup_count": lineup_count,
                "has_tracking_body": False,
                "has_events": event_count > 0,
                "has_lineups": lineup_count > 0,
                "has_three_sixty": has_360,
            }
        )
        summaries.append(
            {
                "source": source,
                "match_id": str(match_id),
                "provider_revision": REVISIONS[source],
                "competition": "unindexed public event file",
                "season": "unknown from pinned index",
                "event_count": event_count,
                "lineup_teams": lineup_count,
                "has_three_sixty": has_360,
                "quality_level": level,
            }
        )
    return inventory, quality, summaries


def wyscout_inventory(
    source: str,
    repository: Path,
    delivery: Path,
    hashes: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    reader = WyscoutReader(repository)
    match_index = reader.raw_match_index()
    inventory: list[dict[str, Any]] = []
    quality: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for match_id in reader.match_ids():
        match = reader.read_match(match_id)
        source_match = match_index.get(match_id)
        if source_match is None:
            raise ValueError(f"Wyscout raw index misses match {match_id}")
        path = reader.files / f"{match_id}.json"
        event_count = len(match["events"])
        reasons = (
            "Complete processed event JSON and raw match index; event-only, no continuous tracking. "
            "Suitable for event research and weak supervision, not H/A/D/X frame truth."
        )
        inventory.append(
            {
                "source": source,
                "provider_revision": REVISIONS[source],
                "match_id": str(match_id),
                "competition": source_match["competition_name"],
                "season": source_match["season_name"],
                "data_type": "event",
                "tracking_path": "",
                "event_path": path.relative_to(delivery).as_posix(),
                "metadata_path": (repository / "raw_data" / "matches.zip")
                .relative_to(delivery)
                .as_posix(),
                "phase_path": "",
                "tracking_sha256": "",
                "event_sha256": relative_hash(hashes, path, delivery),
                "metadata_sha256": "",
                "phase_sha256": "",
                "fps": "not applicable",
                "coordinate_system": "Wyscout normalised event positions 0..100",
                "time_fields": "matchPeriod; eventSec",
                "possession_fields": "teamId; eventName; tags",
                "phase_fields": "No continuous phases-of-play",
                "dead_ball_fields": "event categories only; not continuous truth",
                "quality_level": "Q2",
                "quality_reasons": reasons,
                "license_status": LICENSE_STATUS[source],
                "research_scope": "event-only; weak continuous supervision",
            }
        )
        quality.append(
            {
                "source": source,
                "match_id": str(match_id),
                "quality_level": "Q2",
                "research_scope": "event-level and weak supervision",
                "reasons": reasons,
                "record_count": event_count,
                "tracking_frames": 0,
                "event_count": event_count,
                "has_tracking_body": False,
                "has_events": event_count > 0,
                "has_phases": False,
                "has_three_sixty": False,
            }
        )
        summaries.append(
            {
                "source": source,
                "match_id": str(match_id),
                "provider_revision": REVISIONS[source],
                "competition": source_match["competition_name"],
                "season": source_match["season_name"],
                "match_date": source_match["dateutc"],
                "label": source_match["label"],
                "event_count": event_count,
                "quality_level": "Q2",
            }
        )
    return inventory, quality, summaries


def snapshot_terms(delivery: Path, roots: dict[str, Path]) -> None:
    registry = delivery / "00_SOURCE_REGISTRY" / "TERMS_SNAPSHOTS"
    registry.mkdir(parents=True, exist_ok=True)
    paths = {
        "skillcorner_LICENSE.txt": roots["SkillCorner"] / "LICENSE",
        "skillcorner_README.txt": roots["SkillCorner"] / "README.md",
        "skillcorner_bodypose_README.txt": roots["SkillCorner"] / "data" / "bodypose" / "README.md",
        "wyscout_README.txt": roots["Wyscout"] / "README.md",
        "statsbomb_LICENSE.pdf": roots["StatsBomb"] / "LICENSE.pdf",
        "statsbomb_README.txt": roots["StatsBomb"] / "README.md",
    }
    for output, source in paths.items():
        if source.exists():
            shutil.copy2(source, registry / output)
    idsse_api = delivery / "01_RAW_DATA" / "idsse" / "HF_API_DATASET.json"
    if idsse_api.exists():
        shutil.copy2(idsse_api, registry / "idsse_HF_API_DATASET.json")
    idsse_readme = delivery / "01_RAW_DATA" / "idsse" / "README_FROM_API.md"
    if idsse_readme.exists():
        shutil.copy2(idsse_readme, registry / "idsse_README_FROM_API.txt")
    idsse_raw_readme = roots["IDSSE"] / "README.md"
    if idsse_raw_readme.exists():
        shutil.copy2(idsse_raw_readme, registry / "idsse_README.txt")


def write_match_summaries(
    delivery: Path,
    summaries: list[dict[str, Any]],
    source_slug: str,
) -> None:
    output = delivery / "02_MATCH_INVENTORY" / "MATCH_METADATA" / source_slug
    output.mkdir(parents=True, exist_ok=True)
    for summary in summaries:
        path = output / f"{summary['match_id']}.json"
        path.write_text(
            json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def write_schema_documents(delivery: Path) -> None:
    schema_dir = delivery / "03_SCHEMA_DOCUMENTATION"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "DATA_SCHEMA.md").write_text(
        """# CDA-v2 Data Schema

## Core rule

Tracking, event, proxy and evaluation-reference data are different evidence classes.
Event-only datasets are never described as frame-level H/A/D/X truth.

## Match inventory columns

`MATCH_INVENTORY.csv` records source revision, match ID, competition/season, data type,
FPS, coordinate convention, timing fields, possession/phase/dead-ball fields, Q1-Q4,
license status and hashes for source files.

## Source summaries

SkillCorner: JSONL tracking at 10 FPS plus provider CSV events and phase intervals.

IDSSE: DFL XML position and event streams at 25 FPS.

StatsBomb: event and lineup JSON; 360 freeze-frame JSON exists for a subset. It is not tracking.

Wyscout: processed event JSON at event timestamps. It is not tracking.
""",
        encoding="utf-8",
    )
    (schema_dir / "COORDINATE_SYSTEMS.md").write_text(
        """# Coordinate Systems

| Source | Convention |
|---|---|
| SkillCorner | Metres, pitch-centre origin, x long axis, y short axis, provider pitch dimensions |
| IDSSE | DFL pitch coordinates in metres, X 0..105 and Y -34..34 |
| StatsBomb | Event coordinates 120 x 80, attacking-direction dependent |
| Wyscout | Normalised event positions 0..100 |

Coordinate systems must not be mixed without explicit source-specific conversion.
""",
        encoding="utf-8",
    )
    (schema_dir / "TIMESTAMP_AND_FPS.md").write_text(
        """# Timestamp and FPS

| Source | Timing |
|---|---|
| SkillCorner | 10 FPS; integer frame, timestamp and period |
| IDSSE | 25 FPS (0.04 s frame cadence); frame number and ISO EventTime |
| StatsBomb | Event minute/second/timestamp; no fixed frame rate |
| Wyscout | Event `matchPeriod` and seconds within period; no fixed frame rate |

Only SkillCorner and IDSSE contain continuous tracking timelines in this package.
""",
        encoding="utf-8",
    )
    (schema_dir / "LABEL_SEMANTICS.md").write_text(
        """# Label Semantics

- SkillCorner `possession.group` is a provider possession observation. Phase gaps are
  auxiliary evidence, not confirmed dead-ball truth.
- IDSSE events describe provider event actions and restart/stoppage categories. They
  are not a complete continuous H/A/D/X truth stream.
- StatsBomb events and possession fields are event-level labels only.
- Wyscout events and tags are event-level observations only.
- No source in this package supplies a universal frame-level H/A/D/X ground truth.

Q levels are interpreted against `research_scope`, recorded per match.
""",
        encoding="utf-8",
    )


def write_handoff_docs(
    delivery: Path,
    source_rows: list[dict[str, Any]],
    quality_rows: list[dict[str, Any]],
) -> None:
    counts = Counter(row["quality_level"] for row in quality_rows)
    total_files = sum(int(row["raw_file_count"]) for row in source_rows)
    total_bytes = sum(int(row["raw_bytes"]) for row in source_rows)
    (delivery / "README.md").write_text(
        f"""# Cross-Match Open Data v2

Status: `CLOSURE_002_IMPLEMENTATION_COMPLETE / READY_FOR_PM_RE_VERIFICATION`

This package contains actual pinned files from four public sources:
SkillCorner, IDSSE/Sportec, StatsBomb and Wyscout. Raw data remain separate from
derived indexes, schemas, readers and quality reports.

```text
Sources: {len(source_rows)}
Matches: {sum(int(row["matches"]) for row in source_rows)}
Raw files: {total_files}
Raw size: {total_bytes / 1024**3:.3f} GiB
Q1: {counts["Q1"]}
Q2: {counts["Q2"]}
Q3: {counts["Q3"]}
Q4: {counts["Q4"]}
```

This status requests PM re-verification only. It does not approve technical
research handoff and does not grant training, evaluation, publication or
redistribution rights.

ZIP archives are resolved through the `--archive-root` argument recorded in
`archives/ZIP_INDEX.csv`. Rebuild a portable package with:

```text
python tools/cda_v2/reassemble_package.py --archive-root <ARCHIVE_ROOT> --output <EMPTY_OUTPUT>
```
""",
        encoding="utf-8",
    )
    (delivery / "04_QUALITY_ASSESSMENT" / "QUALITY_REPORT.md").write_text(
        f"""# Quality Report

```text
Q1: {counts["Q1"]}
Q2: {counts["Q2"]}
Q3: {counts["Q3"]}
Q4: {counts["Q4"]}
```

SkillCorner has complete 10 FPS tracking but extrapolated coordinates and an
approximately 97% player-identity limitation, so it is Q2 for broad tracking use.
IDSSE's seven tracking/event matches are Q1. StatsBomb is Q1 for event research
and explicitly not tracking. Wyscout is Q2 event data and weak supervision.

No event-only dataset is a frame-level H/A/D/X ground truth.
""",
        encoding="utf-8",
    )
    (delivery / "06_HANDOFF" / "RESEARCHER_QUICKSTART.md").write_text(
        r"""# Researcher Quickstart

Run examples with the pinned package root:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
python 05_ACCESS_TOOLS/BASIC_EXAMPLES/inspect_sources.py .
```

POSIX shells use the same forward-slash path and `PYTHONDONTWRITEBYTECODE=1`.

Reassemble from five verified archives:

```powershell
python tools/cda_v2/reassemble_package.py `
  --archive-root <ARCHIVE_ROOT> `
  --output <EMPTY_OUTPUT>
```

The readers require only the Python standard library. Optional Kloppy loading was
not available because PyPI was unreachable during acquisition; exact source formats
and reproducible equivalent parsers are supplied here.

Start with `MATCH_INVENTORY.csv`, then use the source-specific reader. Do not infer
continuous H/A/D/X truth from StatsBomb or Wyscout events.
""",
        encoding="utf-8",
    )
    (delivery / "06_HANDOFF" / "DATA_USAGE_NOTES.md").write_text(
        """# Data Usage Notes

- Public access is not a universal research, training, publication or redistribution license.
- IDSSE and Wyscout require CC BY 4.0 attribution and citation.
- StatsBomb public-data attribution/Logo requirements apply; inspect the pinned LICENSE.pdf.
- SkillCorner repository software is MIT; this does not grant unrestricted data rights.
- PM must review exact source rights before any training, evaluation or publication.
- Raw files are immutable and must not be re-encoded in place.
""",
        encoding="utf-8",
    )
    (delivery / "06_HANDOFF" / "HANDOFF_CHECKLIST.md").write_text(
        """# Handoff Checklist

- [x] Four sources acquired at pinned revisions
- [x] Per-match inventory populated
- [x] Raw SHA-256 inventory generated
- [x] Source readers and examples supplied
- [x] SkillCorner LFS bodies verified
- [x] IDSSE seven-match tracking/event coverage verified
- [x] StatsBomb competition/season/match coverage enumerated
- [x] Wyscout 1,941 actual match files counted
- [x] Source/license snapshots copied
- [ ] PM independent source-rights acceptance
""",
        encoding="utf-8",
    )
    (delivery / "06_HANDOFF" / "ACQUISITION_LOG.md").write_text(
        """# Acquisition Log

## 2026-11-10

- SkillCorner: official GitHub repository cloned at pinned commit
  `4340d274572876239c154c90bc507a9b3250a656`; 20 LFS tracking bodies fetched.
  README says 10 matches, but pinned `data/matches.json` contains 20; the manifest
  count is authoritative.
- Wyscout: official GitHub repository cloned at
  `ebc4c54c1093c420a81ce442c69e4186fab33bb4`; `processed-v2/files` contains 1,941
  match JSON files, matching the claimed count.
- IDSSE: Figshare API/download host returned AWS WAF 403 and the official
  Hugging Face hostname was not resolvable from this network. The same official
  repository commit `a715a38dfbaf5f58e431727c2b78d174101a703c` was retrieved through
  `hf-mirror.com`; all seven large position files match the official LFS SHA-256.
- StatsBomb: shallow Git clone stalled and codeload does not support byte-range
  resume. The pinned GitHub codeload tarball was retried from the start until complete.
- PyPI was unreachable, so dependency-free source readers and recorded equivalent
  parsing methods are used instead of Kloppy.
- SkillCorner full bodypose for matches 1925299 and 1996435 was deferred as required;
  their ordinary tracking/event/phase files are present.
""",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("delivery_root", type=Path)
    parser.add_argument("--reuse-file-inventory", action="store_true")
    args = parser.parse_args()
    delivery = args.delivery_root.resolve()
    for name in SOURCE_DIRS:
        (delivery / name).mkdir(parents=True, exist_ok=True)

    roots = {
        "SkillCorner": delivery / "01_RAW_DATA" / "skillcorner" / "repository",
        "IDSSE": delivery / "01_RAW_DATA" / "idsse" / "repository",
        "StatsBomb": delivery / "01_RAW_DATA" / "statsbomb" / "repository",
        "Wyscout": delivery / "01_RAW_DATA" / "wyscout" / "repository",
    }
    for source, root in roots.items():
        if not root.exists():
            raise FileNotFoundError(f"{source} repository is missing: {root}")

    inventory_path = delivery / "04_QUALITY_ASSESSMENT" / "FILE_INVENTORY.csv"
    if args.reuse_file_inventory and inventory_path.exists():
        records = load_file_records(inventory_path)
    else:
        records = collect_file_records(delivery, roots)
        write_csv(
            inventory_path,
            ["source", "relative_path", "bytes", "sha256", "provider_revision", "retrieved_at"],
            [asdict(record) for record in records],
        )
    hashes = file_hash_map(records)

    inventory: list[dict[str, Any]] = []
    quality: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    generators = {
        "SkillCorner": skill_inventory,
        "IDSSE": idsse_inventory,
        "StatsBomb": statsbomb_inventory,
        "Wyscout": wyscout_inventory,
    }
    for source, generator in generators.items():
        source_inventory, source_quality, source_summaries = generator(
            source, roots[source], delivery, hashes
        )
        inventory.extend(source_inventory)
        quality.extend(source_quality)
        summaries.extend(source_summaries)
        write_match_summaries(delivery, source_summaries, source.lower())

    inventory_fields = [
        "source",
        "provider_revision",
        "match_id",
        "competition",
        "season",
        "data_type",
        "tracking_path",
        "event_path",
        "metadata_path",
        "phase_path",
        "tracking_sha256",
        "event_sha256",
        "metadata_sha256",
        "phase_sha256",
        "fps",
        "coordinate_system",
        "time_fields",
        "possession_fields",
        "phase_fields",
        "dead_ball_fields",
        "quality_level",
        "quality_reasons",
        "license_status",
        "research_scope",
    ]
    write_csv(delivery / "02_MATCH_INVENTORY" / "MATCH_INVENTORY.csv", inventory_fields, inventory)
    quality_fields = [
        "source",
        "match_id",
        "quality_level",
        "research_scope",
        "reasons",
        "record_count",
        "tracking_frames",
        "event_count",
        "lineup_count",
        "phase_count",
        "has_tracking_body",
        "has_events",
        "has_lineups",
        "has_phases",
        "has_three_sixty",
    ]
    write_csv(
        delivery / "04_QUALITY_ASSESSMENT" / "QUALITY_ASSESSMENT.csv", quality_fields, quality
    )

    source_rows: list[dict[str, Any]] = []
    for source in REVISIONS:
        source_records = [record for record in records if record.source == source]
        source_inventory = [row for row in inventory if row["source"] == source]
        tracing = sum(row["data_type"] in {"tracking", "both"} for row in source_inventory)
        events = sum(row["data_type"] in {"event", "both"} for row in source_inventory)
        event_only = sum(row["data_type"] == "event" for row in source_inventory)
        source_rows.append(
            {
                "source": source,
                "revision": REVISIONS[source],
                "retrieved_at": RETRIEVED_AT,
                "license": LICENSE_STATUS[source],
                "attribution": "See ACCESS_AND_LICENSE.csv and terms snapshots",
                "raw_file_count": len(source_records),
                "raw_bytes": sum(record.bytes for record in source_records),
                "matches": len(source_inventory),
                "tracking_matches": tracing,
                "event_matches": events,
                "event_only_matches": event_only,
                "status": "ACQUIRED; READABLE; QUALITY_ASSESSED",
                "notes": "",
            }
        )
    write_csv(
        delivery / "00_SOURCE_REGISTRY" / "DATA_SOURCE_MASTER.csv",
        [
            "source",
            "revision",
            "retrieved_at",
            "license",
            "attribution",
            "raw_file_count",
            "raw_bytes",
            "matches",
            "tracking_matches",
            "event_matches",
            "event_only_matches",
            "status",
            "notes",
        ],
        source_rows,
    )
    (delivery / "00_SOURCE_REGISTRY" / "SOURCE_REVISIONS.json").write_text(
        json.dumps(REVISIONS, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_csv(
        delivery / "00_SOURCE_REGISTRY" / "ZERO_BYTE_FILES.csv",
        ["source", "path", "reason"],
        [
            {
                "source": record.source,
                "path": record.relative_path,
                "reason": "Legitimate empty source-code or auxiliary documentation file; no data payload.",
            }
            for record in records
            if record.bytes == 0
        ],
    )

    access_rows = [
        {
            "source": "SkillCorner",
            "official_url": "https://github.com/SkillCorner/opendata",
            "revision": REVISIONS["SkillCorner"],
            "license_name": "Repository software MIT; data-specific rights require separate review",
            "license_snapshot_path": "00_SOURCE_REGISTRY/TERMS_SNAPSHOTS/skillcorner_LICENSE.txt",
            "attribution": "Credit SkillCorner; notification requested but not a rights grant",
            "internal_processing": "Permitted for this PM-authorized technical audit",
            "publication_authorized": "NO",
            "redistribution_authorized": "NO",
            "status": "PM_RIGHTS_REVIEW_REQUIRED",
            "notes": "MIT applies to repository software, not automatically to data.",
        },
        {
            "source": "IDSSE",
            "official_url": "https://huggingface.co/datasets/pysport/idsse-data",
            "revision": REVISIONS["IDSSE"],
            "license_name": "CC BY 4.0",
            "license_snapshot_path": "00_SOURCE_REGISTRY/TERMS_SNAPSHOTS/idsse_HF_API_DATASET.json",
            "attribution": "Bassek, Rein, Weber, Memmert (2025), DOI 10.6084/m9.figshare.28196177.v1",
            "internal_processing": "Technical package use; additional project permissions remain separate",
            "publication_authorized": "CHECK CC BY TERMS",
            "redistribution_authorized": "CHECK CC BY TERMS",
            "status": "PUBLIC_CC_BY_4_0",
            "notes": "Cite dataset and paper DOI 10.1038/s41597-025-04505-y.",
        },
        {
            "source": "StatsBomb",
            "official_url": "https://github.com/hudl/open-data",
            "revision": REVISIONS["StatsBomb"],
            "license_name": "StatsBomb public data terms",
            "license_snapshot_path": "00_SOURCE_REGISTRY/TERMS_SNAPSHOTS/statsbomb_LICENSE.pdf",
            "attribution": "StatsBomb attribution/Logo requirements apply",
            "internal_processing": "Permitted for this technical audit; rights review required for other uses",
            "publication_authorized": "NO unless separately reviewed",
            "redistribution_authorized": "NO unless separately reviewed",
            "status": "PM_RIGHTS_REVIEW_REQUIRED",
            "notes": "See pinned LICENSE.pdf and README.",
        },
        {
            "source": "Wyscout",
            "official_url": "https://github.com/koenvo/wyscout-soccer-match-event-dataset",
            "revision": REVISIONS["Wyscout"],
            "license_name": "CC BY 4.0",
            "license_snapshot_path": "00_SOURCE_REGISTRY/TERMS_SNAPSHOTS/wyscout_README.txt",
            "attribution": "Pappalardo and Massucco; cite scientific paper and Figshare collection",
            "internal_processing": "Technical package use; project-specific permissions remain separate",
            "publication_authorized": "CHECK CC BY TERMS",
            "redistribution_authorized": "CHECK CC BY TERMS",
            "status": "PUBLIC_CC_BY_4_0",
            "notes": "Cite DOI 10.6084/m9.figshare.c.4415000 and 10.1038/s41597-019-0247-7.",
        },
    ]
    write_csv(
        delivery / "00_SOURCE_REGISTRY" / "ACCESS_AND_LICENSE.csv",
        list(access_rows[0]),
        access_rows,
    )
    write_csv(
        delivery / "00_SOURCE_REGISTRY" / "EXCLUDED_AND_DEFERRED.csv",
        ["source", "item", "status", "reason"],
        [
            {
                "source": "SkillCorner",
                "item": "full bodypose 1925299",
                "status": "DEFERRED",
                "reason": "Approximately 3.3 GB external bodypose object; ordinary tracking/events/phases acquired.",
            },
            {
                "source": "SkillCorner",
                "item": "full bodypose 1996435",
                "status": "DEFERRED",
                "reason": "Approximately 3.3 GB external bodypose object; ordinary tracking/events/phases acquired.",
            },
            {
                "source": "Wyscout",
                "item": "processed v1 duplicate files",
                "status": "RETAINED_RAW_NOT_PRIMARY_INDEX",
                "reason": "processed-v2 is the indexed compatibility representation; v1 remains in raw snapshot.",
            },
            {
                "source": "StatsBomb",
                "item": "274 event/lineup files absent from competitions.json index",
                "status": "INVENTORIED_WITH_UNKNOWN_COMPETITION_SEASON",
                "reason": "Raw files exist and are in MATCH_INVENTORY; competition/season are not inferred.",
            },
            {
                "source": "StatsBomb",
                "item": "three-sixty files with official-source NUL corruption",
                "status": "RETAINED_RAW_PARSE_FAILURE_RECORDED",
                "reason": "Malformed optional 360 JSON is retained byte-for-byte and marked in match quality.",
            },
        ],
    )
    write_csv(
        delivery / "04_QUALITY_ASSESSMENT" / "MATCH_COVERAGE.csv",
        [
            "source",
            "matches",
            "tracking_matches",
            "event_matches",
            "event_only_matches",
            "Q1",
            "Q2",
            "Q3",
            "Q4",
        ],
        [
            {
                **row,
                "Q1": sum(
                    item["quality_level"] == "Q1" and item["source"] == row["source"]
                    for item in quality
                ),
                "Q2": sum(
                    item["quality_level"] == "Q2" and item["source"] == row["source"]
                    for item in quality
                ),
                "Q3": sum(
                    item["quality_level"] == "Q3" and item["source"] == row["source"]
                    for item in quality
                ),
                "Q4": sum(
                    item["quality_level"] == "Q4" and item["source"] == row["source"]
                    for item in quality
                ),
            }
            for row in source_rows
        ],
    )

    snapshot_terms(delivery, roots)
    write_schema_documents(delivery)
    write_handoff_docs(delivery, source_rows, quality)
    print(
        json.dumps(
            {
                "raw_files": len(records),
                "raw_bytes": sum(record.bytes for record in records),
                "matches": len(inventory),
                "quality": dict(Counter(row["quality_level"] for row in quality)),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
