from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

from mtah_possession.data.skillcorner import (
    LoadedSkillCornerSource,
    SkillCornerManifestSnapshot,
)


def loaded_source_result(
    snapshot: SkillCornerManifestSnapshot,
    identity,
    match_id: str,
) -> LoadedSkillCornerSource:
    checksums = {
        "license": identity.license_sha256,
        "readme": identity.readme_sha256,
        "tracking": identity.files["tracking"]["sha256"],
        "phases": identity.files["phases"]["sha256"],
        "match": identity.files["match"]["sha256"],
    }
    match = SimpleNamespace(
        match_id=match_id,
        fps=10,
        source_checksums=checksums,
        source_metadata={"tracking_aggregate": {}},
    )
    return LoadedSkillCornerSource(
        match=match,
        manifest_snapshot=snapshot,
        files=MappingProxyType({}),
        actual_checksums=MappingProxyType(dict(checksums)),
        actual_source_identity=identity,
        snapshot_digest=snapshot.snapshot_digest,
    )


def write_skillcorner_source(
    *,
    data_root: Path,
    config_path: Path,
    match_id: str,
    source_revision: str,
) -> dict[str, Path]:
    match_dir = data_root / f"match-{match_id}"
    match_dir.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)
    license_path = match_dir / "LICENSE"
    readme_path = data_root / "README.md"
    tracking_path = match_dir / "tracking.jsonl"
    phases_path = match_dir / "phases.csv"
    match_path = match_dir / "match.json"

    license_path.write_text(f"license {match_id}", encoding="utf-8")
    readme_path.write_text("fixture readme", encoding="utf-8")
    numeric_match_id = int(match_id)
    home_player = numeric_match_id * 100 + 1
    away_player = numeric_match_id * 100 + 2
    match_path.write_text(
        json.dumps(
            {
                "id": numeric_match_id,
                "home_team": {"id": 1, "short_name": "Home"},
                "away_team": {"id": 2, "short_name": "Away"},
                "match_periods": [{"period": 1, "start_frame": 0, "end_frame": 3}],
                "players": [
                    {"id": home_player, "team_id": 1},
                    {"id": away_player, "team_id": 2},
                ],
            }
        ),
        encoding="utf-8",
    )
    tracking_path.write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {
                    "frame": 0,
                    "ball_data": {"x": 0.0, "y": 0.0, "z": 0.0, "is_detected": True},
                    "possession": {"group": "home team"},
                    "player_data": [
                        {"player_id": home_player, "x": 1.0, "y": 0.0, "is_detected": True}
                    ],
                    "period": 1,
                },
                {
                    "frame": 1,
                    "ball_data": {"x": 0.0, "y": 0.0, "z": 0.0, "is_detected": True},
                    "possession": {"group": "away team"},
                    "player_data": [
                        {"player_id": away_player, "x": 1.0, "y": 0.0, "is_detected": True}
                    ],
                    "period": 1,
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )
    phases_path.write_text(
        "frame_start,frame_end,period,team_in_possession_id,team_in_possession_phase_type\n"
        "0,3,1,1,build_up\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "1.0",
        "provider": "skillcorner",
        "repository": "fixture",
        "commit": source_revision,
        "repository_software_license": "MIT",
        "data_license_status": "HOLD",
        "data_license_evidence": ["EV-AUTH-SC-LICENSE"],
        "license_file": license_path.relative_to(data_root).as_posix(),
        "license_sha256": hashlib.sha256(license_path.read_bytes()).hexdigest(),
        "readme_sha256": hashlib.sha256(readme_path.read_bytes()).hexdigest(),
        "retrieval_date": "2026-11-09",
        "match_id": match_id,
        "fps": 10,
        "home_team_id": 1,
        "away_team_id": 2,
        "pitch_length_m": 105.0,
        "pitch_width_m": 68.0,
        "coordinate_convention": "metres-center-origin",
        "files": {
            "tracking": {
                "path": tracking_path.relative_to(data_root).as_posix(),
                "sha256": hashlib.sha256(tracking_path.read_bytes()).hexdigest(),
            },
            "phases": {
                "path": phases_path.relative_to(data_root).as_posix(),
                "sha256": hashlib.sha256(phases_path.read_bytes()).hexdigest(),
            },
            "match": {
                "path": match_path.relative_to(data_root).as_posix(),
                "sha256": hashlib.sha256(match_path.read_bytes()).hexdigest(),
            },
        },
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(manifest), encoding="utf-8")
    return {
        "config": config_path,
        "license": license_path,
        "readme": readme_path,
        "tracking": tracking_path,
        "phases": phases_path,
        "match": match_path,
    }


def write_metadata(
    path: Path,
    *,
    home_slots: int = 2,
    away_slots: int = 2,
    home_name: str = "Home FC",
    away_name: str = "Away FC",
) -> int:
    root = ET.Element("Game")
    teams = ET.SubElement(root, "Teams")
    home = ET.SubElement(teams, "Team", id="home-id")
    ET.SubElement(home, "Name").text = home_name
    away = ET.SubElement(teams, "Team", id="away-id")
    ET.SubElement(away, "Name").text = away_name

    players = ET.SubElement(root, "Players")
    slot = 0
    for team_id in ("home-id", "away-id"):
        count = home_slots if team_id == "home-id" else away_slots
        for _ in range(count):
            ET.SubElement(players, "Player", id=str(slot), teamId=team_id)
            slot += 1
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return slot


def player_group(x: float, y: float) -> str:
    return f"{x},{y},4.0"


def missing_group() -> str:
    return "NaN,NaN,0"


def write_raw(path: Path, records: list[str]) -> None:
    path.write_text("\n".join(records) + "\n", encoding="utf-8")


def make_data_root(
    root: Path,
    records: list[list[tuple[float, float]]],
    *,
    ball: list[tuple[float, float] | None],
    home_slots: int = 2,
    away_slots: int = 2,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    tactical = root / "tactical"
    tactical.mkdir()
    (root / "broadcast").mkdir()
    write_metadata(
        tactical / "BAR-ATH_tactical_atd.xml",
        home_slots=home_slots,
        away_slots=away_slots,
    )
    lines = []
    for index, players in enumerate(records, start=1):
        groups = ";".join(player_group(x, y) for x, y in players)
        ball_group = missing_group() if ball[index - 1] is None else player_group(*ball[index - 1])
        lines.append(f"{index}:{groups}:{ball_group}")
    write_raw(tactical / "BAR-ATH_tactical_atd.txt", lines)
    return root
