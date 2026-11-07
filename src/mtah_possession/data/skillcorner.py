"""SkillCorner Open Data adapter.

Provider-specific field names are confined to this module. Callers receive a
provider-neutral match representation and aggregate metadata only.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from mtah_possession.data.neutral import (
    NeutralMatch,
    PeriodSpan,
    PhaseSpan,
    SourceQuality,
    TeamSide,
)


class SkillCornerDataError(ValueError):
    """Raised when the audited external input does not match its manifest."""


def load_skillcorner_manifest(
    config_path: str | os.PathLike[str],
) -> dict[str, Any]:
    path = Path(config_path)
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SkillCornerDataError(f"could not read SkillCorner manifest at {path}") from error
    if not isinstance(values, dict) or values.get("provider") != "skillcorner":
        raise SkillCornerDataError("SkillCorner manifest must declare provider=skillcorner")
    required = {
        "schema_version",
        "provider",
        "repository",
        "commit",
        "repository_software_license",
        "data_license_status",
        "data_license_evidence",
        "license_file",
        "license_sha256",
        "readme_sha256",
        "retrieval_date",
        "match_id",
        "fps",
        "home_team_id",
        "away_team_id",
        "pitch_length_m",
        "pitch_width_m",
        "coordinate_convention",
        "files",
    }
    missing = required.difference(values)
    unknown = set(values).difference(required)
    if missing:
        raise SkillCornerDataError(f"manifest is missing keys: {sorted(missing)}")
    if unknown:
        raise SkillCornerDataError(f"manifest has unknown keys: {sorted(unknown)}")
    if values["schema_version"] != "1.0":
        raise SkillCornerDataError("SkillCorner manifest schema_version must be '1.0'")
    if values["repository_software_license"] != "MIT":
        raise SkillCornerDataError("repository software license must be MIT")
    if values["data_license_status"] not in {"PASS", "HOLD", "FAIL"}:
        raise SkillCornerDataError("invalid data_license_status")
    if values["data_license_status"] == "MIT":
        raise SkillCornerDataError("data_license_status cannot reuse the software license")
    if not isinstance(values["data_license_evidence"], list) or not all(
        isinstance(item, str) and item for item in values["data_license_evidence"]
    ):
        raise SkillCornerDataError("data_license_evidence must be a non-empty string list")
    if values["coordinate_convention"] != "metres-center-origin":
        raise SkillCornerDataError("unexpected coordinate convention")
    files = values["files"]
    if not isinstance(files, dict) or set(files) != {
        "tracking",
        "phases",
        "match",
    }:
        raise SkillCornerDataError("files must define tracking, phases and match")
    for role, entry in files.items():
        if (
            not isinstance(entry, dict)
            or set(entry) != {"path", "sha256"}
            or not isinstance(entry["path"], str)
            or not isinstance(entry["sha256"], str)
        ):
            raise SkillCornerDataError(f"invalid manifest entry for {role}")
    return values


def load_skillcorner_match(
    config_path: str | os.PathLike[str],
    external_root: str | os.PathLike[str],
) -> NeutralMatch:
    manifest = load_skillcorner_manifest(config_path)
    root = Path(external_root).resolve(strict=False)
    files = {role: root / entry["path"] for role, entry in manifest["files"].items()}
    checksums: dict[str, str] = {}
    for role, relative, expected in (
        ("license", manifest["license_file"], manifest["license_sha256"]),
        ("readme", "README.md", manifest["readme_sha256"]),
    ):
        path = root / relative
        if not path.is_file():
            raise SkillCornerDataError(f"audited {role} file is missing: {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise SkillCornerDataError(
                f"audited {role} checksum mismatch: expected {expected}, found {actual}"
            )
        checksums[role] = actual
    for role, path in files.items():
        if not path.is_file():
            raise SkillCornerDataError(f"external {role} file is missing: {path}")
        actual = sha256_file(path)
        expected = manifest["files"][role]["sha256"]
        if actual != expected:
            raise SkillCornerDataError(
                f"external {role} checksum mismatch: expected {expected}, found {actual}"
            )
        checksums[role] = actual

    try:
        match_data = json.loads(files["match"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SkillCornerDataError("could not parse external match metadata") from error
    periods = _parse_periods(match_data, manifest["match_id"])
    if not periods:
        raise SkillCornerDataError("external match has no declared periods")
    frame_count = max(
        max(period.end_frame for period in periods),
        _max_tracking_frame(files["tracking"]) + 1,
    )

    home_team_id = int(manifest["home_team_id"])
    away_team_id = int(manifest["away_team_id"])
    home_name = _team_name(match_data, "home_team", home_team_id)
    away_name = _team_name(match_data, "away_team", away_team_id)
    player_ids, team_by_slot = _parse_players(
        match_data,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
    )
    id_to_slot = {player_id: slot for slot, player_id in enumerate(player_ids)}

    slot_positions = np.full((frame_count, len(player_ids), 2), np.nan, dtype=np.float32)
    slot_detected = np.zeros((frame_count, len(player_ids)), dtype=bool)
    slot_source_quality = np.full(
        (frame_count, len(player_ids)),
        SourceQuality.MISSING,
        dtype=np.int8,
    )
    ball_positions = np.full((frame_count, 2), np.nan, dtype=np.float32)
    ball_detected = np.zeros(frame_count, dtype=bool)
    ball_source_quality = np.full(frame_count, SourceQuality.MISSING, dtype=np.int8)
    frame_present = np.zeros(frame_count, dtype=bool)
    possession_side = np.full(frame_count, TeamSide.UNKNOWN, dtype=np.int8)
    possession_status = np.full(frame_count, 1, dtype=np.int8)
    aggregate = {
        "tracking_rows": 0,
        "possession_home": 0,
        "possession_away": 0,
        "possession_missing": 0,
        "possession_unrecognized": 0,
        "player_observations": 0,
        "player_detected": 0,
        "player_extrapolated": 0,
        "ball_detected": 0,
        "ball_present_but_not_detected": 0,
        "unknown_player_ids": 0,
        "out_of_range_rows": 0,
        "possession_group_values": {},
        "period_values": {},
    }

    with files["tracking"].open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                frame = int(record["frame"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                raise SkillCornerDataError("malformed external tracking record") from error
            aggregate["tracking_rows"] += 1
            if not 0 <= frame < frame_count:
                aggregate["out_of_range_rows"] += 1
                continue
            frame_present[frame] = True

            group = (record.get("possession") or {}).get("group")
            group_key = "<null>" if group is None else str(group)
            group_counts = aggregate["possession_group_values"]
            group_counts[group_key] = group_counts.get(group_key, 0) + 1
            side = _side_from_group(group, home_team_id, away_team_id)
            possession_side[frame] = side
            if side == TeamSide.HOME:
                aggregate["possession_home"] += 1
                possession_status[frame] = 0
            elif side == TeamSide.AWAY:
                aggregate["possession_away"] += 1
                possession_status[frame] = 0
            elif group is None:
                aggregate["possession_missing"] += 1
            else:
                aggregate["possession_unrecognized"] += 1
                possession_status[frame] = 2

            ball = record.get("ball_data")
            if isinstance(ball, dict):
                point = _finite_point(ball)
                if point is not None:
                    ball_positions[frame] = point
                    ball_detected[frame] = bool(ball.get("is_detected"))
                    ball_source_quality[frame] = (
                        SourceQuality.DETECTED
                        if ball_detected[frame]
                        else SourceQuality.EXTRAPOLATED
                    )
                    aggregate["ball_detected"] += int(ball_detected[frame])
                    aggregate["ball_present_but_not_detected"] += int(not ball_detected[frame])

            for player in record.get("player_data") or []:
                aggregate["player_observations"] += 1
                player_id = player.get("player_id")
                slot = id_to_slot.get(player_id)
                if slot is None:
                    aggregate["unknown_player_ids"] += 1
                    continue
                point = _finite_point(player)
                if point is None:
                    continue
                slot_positions[frame, slot] = point
                detected = bool(player.get("is_detected"))
                slot_detected[frame, slot] = detected
                slot_source_quality[frame, slot] = (
                    SourceQuality.DETECTED if detected else SourceQuality.EXTRAPOLATED
                )
                aggregate["player_detected"] += int(detected)
                aggregate["player_extrapolated"] += int(not detected)

            period = record.get("period")
            period_key = "<null>" if period is None else str(period)
            period_counts = aggregate["period_values"]
            period_counts[period_key] = period_counts.get(period_key, 0) + 1

    phases = _parse_phases(
        files["phases"],
        frame_count=frame_count,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
    )
    return NeutralMatch(
        match_id=str(manifest["match_id"]),
        fps=int(manifest["fps"]),
        frame_count=frame_count,
        pitch_length_m=float(manifest["pitch_length_m"]),
        pitch_width_m=float(manifest["pitch_width_m"]),
        coordinate_convention=manifest["coordinate_convention"],
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_team_name=home_name,
        away_team_name=away_name,
        player_ids=player_ids,
        team_by_slot=team_by_slot,
        slot_positions=slot_positions,
        slot_detected=slot_detected,
        ball_positions=ball_positions,
        ball_detected=ball_detected,
        frame_present=frame_present,
        possession_side=possession_side,
        possession_status=possession_status,
        periods=periods,
        phases=phases,
        source_checksums=checksums,
        slot_source_quality=slot_source_quality,
        ball_source_quality=ball_source_quality,
        source_metadata={
            "repository": manifest["repository"],
            "commit": manifest["commit"],
            "repository_software_license": manifest["repository_software_license"],
            "data_license_status": manifest["data_license_status"],
            "data_license_evidence": list(manifest["data_license_evidence"]),
            "retrieval_date": manifest["retrieval_date"],
            "tracking_aggregate": aggregate,
        },
    )


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_periods(match_data: Mapping[str, Any], match_id: Any) -> tuple[PeriodSpan, ...]:
    if int(match_data.get("id", -1)) != int(match_id):
        raise SkillCornerDataError("match metadata ID does not match the manifest")
    periods = []
    for item in match_data.get("match_periods") or []:
        period = int(item["period"])
        first = int(item["start_frame"])
        end = int(item["end_frame"])
        if first < 0 or end <= first:
            raise SkillCornerDataError(f"invalid period boundary for period {period}")
        periods.append(PeriodSpan(period, first, end))
    return tuple(sorted(periods, key=lambda value: value.start_frame))


def _parse_players(
    match_data: Mapping[str, Any],
    *,
    home_team_id: int,
    away_team_id: int,
) -> tuple[tuple[int, ...], np.ndarray]:
    player_ids: list[int] = []
    sides: list[int] = []
    seen: set[int] = set()
    for player in match_data.get("players") or []:
        # The tracking JSONL uses the roster player ID in ``player_id``.
        tracked_player_id = player.get("id")
        team_id = player.get("team_id")
        if tracked_player_id is None or team_id is None:
            continue
        player_id = int(tracked_player_id)
        if player_id in seen:
            raise SkillCornerDataError("duplicate external trackable object")
        if int(team_id) == home_team_id:
            side = TeamSide.HOME
        elif int(team_id) == away_team_id:
            side = TeamSide.AWAY
        else:
            raise SkillCornerDataError("external player has an unknown team")
        seen.add(player_id)
        player_ids.append(player_id)
        sides.append(int(side))
    if not player_ids:
        raise SkillCornerDataError("external match has no trackable players")
    return tuple(player_ids), np.asarray(sides, dtype=np.int8)


def _parse_phases(
    path: Path,
    *,
    frame_count: int,
    home_team_id: int,
    away_team_id: int,
) -> tuple[PhaseSpan, ...]:
    phases: list[PhaseSpan] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            first = int(row["frame_start"])
            end = int(row["frame_end"])
            if not 0 <= first < end <= frame_count:
                raise SkillCornerDataError("external phase lies outside declared periods")
            team_id = int(row["team_in_possession_id"])
            if team_id == home_team_id:
                side = TeamSide.HOME
            elif team_id == away_team_id:
                side = TeamSide.AWAY
            else:
                raise SkillCornerDataError("external phase has an unknown team")
            phases.append(
                PhaseSpan(
                    start_frame=first,
                    end_frame=end,
                    period=int(row["period"]),
                    kind=str(row["team_in_possession_phase_type"]),
                    team=side,
                    restart=False,
                    dead_ball=False,
                    source="phases_of_play",
                )
            )
    return tuple(phases)


def _team_name(match_data: Mapping[str, Any], key: str, expected_id: int) -> str:
    team = match_data.get(key) or {}
    if int(team.get("id", -1)) != expected_id:
        raise SkillCornerDataError(f"external {key} ID does not match the manifest")
    name = team.get("short_name") or team.get("name")
    if not name:
        raise SkillCornerDataError(f"external {key} has no name")
    return str(name)


def _side_from_group(group: Any, home_team_id: int, away_team_id: int) -> TeamSide:
    if group is None:
        return TeamSide.UNKNOWN
    normalized = str(group).strip().lower()
    if normalized in {"home", "home team", str(home_team_id)}:
        return TeamSide.HOME
    if normalized in {"away", "away team", str(away_team_id)}:
        return TeamSide.AWAY
    return TeamSide.UNKNOWN


def _finite_point(values: Mapping[str, Any]) -> tuple[float, float] | None:
    try:
        x = float(values["x"])
        y = float(values["y"])
    except (KeyError, TypeError, ValueError):
        return None
    if not np.isfinite(x) or not np.isfinite(y):
        return None
    return x, y


def _max_tracking_frame(path: Path) -> int:
    """Read only the tail of a JSONL file to find its final frame number."""
    size = path.stat().st_size
    with path.open("rb") as handle:
        handle.seek(max(0, size - 1024 * 1024))
        lines = handle.read().decode("utf-8").splitlines()
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            return int(json.loads(line)["frame"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise SkillCornerDataError("could not parse the final external frame") from error
    raise SkillCornerDataError("external tracking file has no records")
