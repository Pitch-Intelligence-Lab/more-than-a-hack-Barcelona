from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


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
