"""Dependency-free readers for the four CDA-v2 public data sources."""

from __future__ import annotations

import csv
import json
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


class DataReadError(ValueError):
    """Raised when a pinned source file cannot be read as documented."""


class SkillCornerReader:
    def __init__(self, repository: str | Path) -> None:
        self.repository = Path(repository)
        self.matches_path = self.repository / "data" / "matches.json"

    def matches(self) -> list[dict[str, Any]]:
        try:
            values = json.loads(self.matches_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise DataReadError(f"could not read SkillCorner matches: {error}") from error
        if not isinstance(values, list):
            raise DataReadError("SkillCorner matches.json must contain a list")
        return values

    def match_dir(self, match_id: int | str) -> Path:
        return self.repository / "data" / "matches" / str(match_id)

    def tracking_path(self, match_id: int | str) -> Path:
        directory = self.match_dir(match_id)
        return directory / f"{match_id}_tracking_extrapolated.jsonl"

    def metadata_path(self, match_id: int | str) -> Path:
        directory = self.match_dir(match_id)
        return directory / f"{match_id}_match.json"

    def dynamic_events_path(self, match_id: int | str) -> Path:
        directory = self.match_dir(match_id)
        return directory / f"{match_id}_dynamic_events.csv"

    def phases_path(self, match_id: int | str) -> Path:
        directory = self.match_dir(match_id)
        return directory / f"{match_id}_phases_of_play.csv"

    def read_metadata(self, match_id: int | str) -> dict[str, Any]:
        path = self.metadata_path(match_id)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise DataReadError(f"could not read SkillCorner metadata {path}: {error}") from error
        if not isinstance(value, dict):
            raise DataReadError(f"SkillCorner metadata {path} must be an object")
        return value

    def iter_tracking(self, match_id: int | str) -> Iterator[dict[str, Any]]:
        path = self.tracking_path(match_id)
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    if line_number == 1 and line.startswith(
                        "version https://git-lfs.github.com/spec/v1"
                    ):
                        raise DataReadError(f"SkillCorner tracking is still an LFS pointer: {path}")
                    frame = json.loads(line)
                    if not isinstance(frame, dict):
                        raise DataReadError(
                            f"SkillCorner tracking frame {line_number} is not an object"
                        )
                    yield frame
        except OSError as error:
            raise DataReadError(f"could not read SkillCorner tracking {path}: {error}") from error
        except json.JSONDecodeError as error:
            raise DataReadError(f"invalid SkillCorner tracking JSONL {path}: {error}") from error

    def read_csv(self, path: str | Path) -> list[dict[str, str]]:
        try:
            with Path(path).open("r", encoding="utf-8", newline="") as handle:
                return list(csv.DictReader(handle))
        except OSError as error:
            raise DataReadError(f"could not read SkillCorner CSV {path}: {error}") from error


class IDSSEReader:
    _MATCH_ID = re.compile(r"(DFL-MAT-[A-Z0-9]+)")

    def __init__(self, repository: str | Path) -> None:
        self.repository = Path(repository)
        self._files = list(self.repository.glob("DFL_*.xml"))

    def match_ids(self) -> tuple[str, ...]:
        values = {
            match.group(1)
            for path in self._files
            if (match := self._MATCH_ID.search(path.name)) is not None
        }
        return tuple(sorted(values))

    def _find(self, prefix: str, match_id: str) -> Path:
        matches = sorted(self.repository.glob(f"{prefix}*{match_id}.xml"))
        if len(matches) != 1:
            raise DataReadError(f"expected one {prefix} file for {match_id}, found {len(matches)}")
        return matches[0]

    def metadata_path(self, match_id: str) -> Path:
        return self._find("DFL_02_01_matchinformation_", match_id)

    def events_path(self, match_id: str) -> Path:
        return self._find("DFL_03_02_events_raw_", match_id)

    def positions_path(self, match_id: str) -> Path:
        return self._find("DFL_04_03_positions_raw_observed_", match_id)

    def read_metadata(self, match_id: str) -> dict[str, str]:
        try:
            root = ElementTree.parse(self.metadata_path(match_id)).getroot()
        except (OSError, ElementTree.ParseError) as error:
            raise DataReadError(f"could not parse IDSSE metadata {match_id}: {error}") from error
        general = root.find(".//General")
        if general is None:
            raise DataReadError(f"IDSSE metadata has no General element: {match_id}")
        return dict(general.attrib)

    def iter_events(self, match_id: str) -> Iterator[dict[str, Any]]:
        path = self.events_path(match_id)
        try:
            for _event, element in ElementTree.iterparse(path, events=("end",)):
                if element.tag != "Event":
                    continue
                children = list(element)
                yield {
                    **dict(element.attrib),
                    "event_type": children[0].tag if children else None,
                    "event_details": dict(children[0].attrib) if children else {},
                }
                element.clear()
        except (OSError, ElementTree.ParseError) as error:
            raise DataReadError(f"could not parse IDSSE events {path}: {error}") from error

    def iter_frames(self, match_id: str) -> Iterator[dict[str, Any]]:
        path = self.positions_path(match_id)
        current_identity: dict[str, str] = {}
        try:
            for event, element in ElementTree.iterparse(path, events=("start", "end")):
                if event == "start" and element.tag == "FrameSet":
                    current_identity = {
                        "game_section": element.attrib.get("GameSection", ""),
                        "team_id": element.attrib.get("TeamId", ""),
                        "person_id": element.attrib.get("PersonId", ""),
                    }
                elif event == "end" and element.tag == "Frame":
                    yield {**dict(element.attrib), **current_identity}
                    element.clear()
                elif event == "end" and element.tag == "FrameSet":
                    current_identity = {}
                    element.clear()
        except (OSError, ElementTree.ParseError) as error:
            raise DataReadError(f"could not parse IDSSE positions {path}: {error}") from error


@dataclass(frozen=True)
class StatsBombMatch:
    match_id: int
    competition_id: int
    season_id: int
    competition: str
    season: str


class StatsBombReader:
    def __init__(self, repository: str | Path) -> None:
        self.repository = Path(repository)
        self.data = self.repository / "data"

    def competitions(self) -> list[dict[str, Any]]:
        try:
            values = json.loads((self.data / "competitions.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise DataReadError(f"could not read StatsBomb competitions: {error}") from error
        if not isinstance(values, list):
            raise DataReadError("StatsBomb competitions.json must contain a list")
        return values

    def matches(self) -> Iterator[StatsBombMatch]:
        for competition in self.competitions():
            path = (
                self.data
                / "matches"
                / str(competition["competition_id"])
                / f"{competition['season_id']}.json"
            )
            try:
                values = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise DataReadError(f"could not read StatsBomb matches {path}: {error}") from error
            for match in values:
                yield StatsBombMatch(
                    match_id=int(match["match_id"]),
                    competition_id=int(competition["competition_id"]),
                    season_id=int(competition["season_id"]),
                    competition=str(competition["competition_name"]),
                    season=str(competition["season_name"]),
                )

    def events_path(self, match_id: int) -> Path:
        return self.data / "events" / f"{match_id}.json"

    def lineups_path(self, match_id: int) -> Path:
        return self.data / "lineups" / f"{match_id}.json"

    def three_sixty_path(self, match_id: int) -> Path:
        return self.data / "three-sixty" / f"{match_id}.json"

    def read_json_list(self, path: str | Path) -> list[Any]:
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise DataReadError(f"could not read StatsBomb JSON {path}: {error}") from error
        if not isinstance(value, list):
            raise DataReadError(f"StatsBomb file must contain a list: {path}")
        return value


class WyscoutReader:
    _COMPETITIONS = {
        "matches_England.json": ("Premier League", "2017/18"),
        "matches_France.json": ("Ligue 1", "2017/18"),
        "matches_Germany.json": ("Bundesliga", "2017/18"),
        "matches_Italy.json": ("Serie A", "2017/18"),
        "matches_Spain.json": ("La Liga", "2017/18"),
        "matches_World_Cup.json": ("FIFA World Cup", "2018"),
        "matches_European_Championship.json": ("UEFA Euro", "2016"),
    }

    def __init__(self, repository: str | Path) -> None:
        self.repository = Path(repository)
        self.files = self.repository / "processed-v2" / "files"

    def match_ids(self) -> tuple[int, ...]:
        return tuple(sorted(int(path.stem) for path in self.files.glob("*.json")))

    def read_match(self, match_id: int) -> dict[str, Any]:
        path = self.files / f"{match_id}.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise DataReadError(f"could not read Wyscout match {match_id}: {error}") from error
        if not isinstance(value, dict) or set(value) != {"events", "players", "teams"}:
            raise DataReadError(f"unexpected Wyscout match structure: {path}")
        return value

    def raw_match_index(self) -> dict[int, dict[str, Any]]:
        archive = self.repository / "raw_data" / "matches.zip"
        derived = self.repository.parents[2] / "02_MATCH_INVENTORY" / "WYSCOUT_RAW_MATCH_INDEX.json"
        output: dict[int, dict[str, Any]] = {}
        try:
            if archive.exists():
                with zipfile.ZipFile(archive) as handle:
                    for name in handle.namelist():
                        competition, season = self._COMPETITIONS[name]
                        for match in json.loads(handle.read(name)):
                            output[int(match["wyId"])] = {
                                **match,
                                "competition_name": competition,
                                "season_name": season,
                            }
            else:
                values = json.loads(derived.read_text(encoding="utf-8"))
                output = {int(key): value for key, value in values.items()}
        except (OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as error:
            raise DataReadError(f"could not read Wyscout raw match index: {error}") from error
        return output
