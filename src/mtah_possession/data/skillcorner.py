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
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from mtah_possession.data.neutral import (
    EvaluationReference,
    NeutralMatch,
    PeriodSpan,
    PhaseSpan,
    SourceQuality,
    TeamSide,
)


class SkillCornerDataError(ValueError):
    """Raised when the audited external input does not match its manifest."""


@dataclass(frozen=True)
class SkillCornerManifestSnapshot:
    source_path: str
    config_bytes: bytes
    manifest: Mapping[str, Any]
    config_sha256: str
    snapshot_digest: str
    created_at: str


@dataclass(frozen=True)
class ImmutableFileSnapshot:
    role: str
    path: str
    expected_sha256: str
    actual_sha256: str
    data: bytes


@dataclass(frozen=True)
class LoadedSkillCornerSource:
    match: NeutralMatch
    manifest_snapshot: SkillCornerManifestSnapshot
    files: Mapping[str, ImmutableFileSnapshot]
    actual_checksums: Mapping[str, str]
    actual_source_identity: Any
    snapshot_digest: str
    external_root: str = ""
    read_roles: tuple[str, ...] = ()


def create_skillcorner_manifest_snapshot(
    config_path: str | os.PathLike[str],
) -> SkillCornerManifestSnapshot:
    path = Path(config_path)
    try:
        config_bytes = path.read_bytes()
    except OSError as error:
        raise SkillCornerDataError(f"could not read SkillCorner manifest at {path}") from error
    manifest = parse_skillcorner_manifest_bytes(config_bytes, source=str(path))
    config_sha256 = hashlib.sha256(config_bytes).hexdigest()
    snapshot_digest = hashlib.sha256(
        _canonical_json(
            {
                "config_sha256": config_sha256,
                "manifest": manifest,
            }
        )
    ).hexdigest()
    return SkillCornerManifestSnapshot(
        source_path=str(path.resolve(strict=True)),
        config_bytes=config_bytes,
        manifest=_deep_freeze(manifest),
        config_sha256=config_sha256,
        snapshot_digest=snapshot_digest,
        created_at=datetime.now(UTC).isoformat(),
    )


def load_skillcorner_manifest(
    config_path: str | os.PathLike[str],
) -> dict[str, Any]:
    path = Path(config_path)
    try:
        config_bytes = path.read_bytes()
    except OSError as error:
        raise SkillCornerDataError(f"could not read SkillCorner manifest at {path}") from error
    return dict(parse_skillcorner_manifest_bytes(config_bytes, source=str(path)))


def parse_skillcorner_manifest_bytes(
    config_bytes: bytes,
    *,
    source: str,
) -> dict[str, Any]:
    try:
        values = json.loads(config_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SkillCornerDataError(f"could not parse SkillCorner manifest at {source}") from error
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
    """Legacy compatibility helper; production entrypoints must use snapshot APIs."""
    snapshot = create_skillcorner_manifest_snapshot(config_path)
    return load_skillcorner_match_from_snapshot(
        snapshot,
        external_root,
        None,
    ).match


def load_skillcorner_match_from_snapshot(
    snapshot: SkillCornerManifestSnapshot,
    external_root: str | os.PathLike[str],
    expected_source_identity: Any | None,
    *,
    read_roles: tuple[str, ...] | None = None,
    parse_reference: bool = True,
) -> LoadedSkillCornerSource:
    manifest = snapshot.manifest
    root = Path(external_root).resolve(strict=False)
    file_snapshots: dict[str, ImmutableFileSnapshot] = {}
    requested_roles = (
        ("license", "readme", "tracking", "phases", "match") if read_roles is None else read_roles
    )
    allowed_roles = {"license", "readme", "tracking", "phases", "match"}
    if not set(requested_roles) <= allowed_roles:
        raise SkillCornerDataError("unsupported source read role")
    specs = {
        "license": (manifest["license_file"], manifest["license_sha256"]),
        "readme": ("README.md", manifest["readme_sha256"]),
        "tracking": (
            manifest["files"]["tracking"]["path"],
            manifest["files"]["tracking"]["sha256"],
        ),
        "phases": (
            manifest["files"]["phases"]["path"],
            manifest["files"]["phases"]["sha256"],
        ),
        "match": (
            manifest["files"]["match"]["path"],
            manifest["files"]["match"]["sha256"],
        ),
    }
    for role in requested_roles:
        relative, expected = specs[role]
        path = root / relative
        try:
            data = path.read_bytes()
        except OSError as error:
            raise SkillCornerDataError(f"audited {role} file is missing: {path}") from error
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise SkillCornerDataError(
                f"audited {role} checksum mismatch: expected {expected}, found {actual}"
            )
        file_snapshots[role] = ImmutableFileSnapshot(
            role=role,
            path=str(path),
            expected_sha256=str(expected),
            actual_sha256=actual,
            data=data,
        )
    checksums = {role: snapshot.actual_sha256 for role, snapshot in file_snapshots.items()}
    for role in allowed_roles.difference(checksums):
        checksums[role] = str(specs[role][1])
    actual_source_identity = None
    if expected_source_identity is not None:
        from mtah_possession.governance.source import build_source_identity_from_manifest

        actual_source_identity = build_source_identity_from_manifest(
            manifest,
            actual_file_sha256={
                "tracking": checksums["tracking"],
                "phases": checksums["phases"],
                "match": checksums["match"],
            },
            actual_license_sha256=checksums["license"],
            actual_readme_sha256=checksums["readme"],
        )
        if actual_source_identity != expected_source_identity:
            raise SkillCornerDataError("loader actual Source Identity does not match the seal")
    source_snapshot_digest = hashlib.sha256(
        _canonical_json(
            {
                "manifest_snapshot_digest": snapshot.snapshot_digest,
                "actual_checksums": checksums,
            }
        )
    ).hexdigest()

    try:
        match_data = json.loads(file_snapshots["match"].data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SkillCornerDataError("could not parse external match metadata") from error
    periods = _parse_periods(match_data, manifest["match_id"])
    if not periods:
        raise SkillCornerDataError("external match has no declared periods")
    frame_count = max(
        max(period.end_frame for period in periods),
        _max_tracking_frame_bytes(file_snapshots["tracking"].data) + 1,
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

    try:
        tracking_handle = StringIO(file_snapshots["tracking"].data.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise SkillCornerDataError("could not decode external tracking data") from error
    for line in tracking_handle:
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

        if parse_reference:
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
                    SourceQuality.DETECTED if ball_detected[frame] else SourceQuality.EXTRAPOLATED
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

    try:
        phases_handle = StringIO(file_snapshots["phases"].data.decode("utf-8"), newline="")
        phases = _parse_phases_stream(
            phases_handle,
            frame_count=frame_count,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
        )
    except (KeyError, UnicodeDecodeError) as error:
        if "phases" in requested_roles:
            raise SkillCornerDataError("could not decode external phase data") from error
        phases = ()
    match = NeutralMatch(
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
            "source_identity_sha256": (
                actual_source_identity.source_identity_sha256
                if actual_source_identity is not None
                else None
            ),
            "source_snapshot_digest": source_snapshot_digest,
        },
    )
    return LoadedSkillCornerSource(
        match=match,
        manifest_snapshot=snapshot,
        files=MappingProxyType(dict(file_snapshots)),
        actual_checksums=MappingProxyType(dict(checksums)),
        actual_source_identity=actual_source_identity,
        snapshot_digest=source_snapshot_digest,
        external_root=str(root),
        read_roles=(
            (*tuple(requested_roles), "possession_reference")
            if parse_reference
            else tuple(requested_roles)
        ),
    )


def load_skillcorner_evaluation_reference(
    loaded: LoadedSkillCornerSource,
    *,
    include_phases: bool = True,
) -> EvaluationReference:
    """Construct evaluation-only fields after predictions are fixed."""
    tracking_snapshot = loaded.files.get("tracking")
    if tracking_snapshot is None:
        raise SkillCornerDataError("prediction snapshot is missing tracking bytes")
    manifest = loaded.manifest_snapshot.manifest
    frame_count = loaded.match.frame_count
    possession_side = np.full(frame_count, TeamSide.UNKNOWN, dtype=np.int8)
    possession_status = np.full(frame_count, 1, dtype=np.int8)
    try:
        tracking_handle = StringIO(tracking_snapshot.data.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise SkillCornerDataError("could not decode evaluation tracking bytes") from error
    for line in tracking_handle:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            frame = int(record["frame"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise SkillCornerDataError("malformed evaluation possession record") from error
        if not 0 <= frame < frame_count:
            continue
        group = (record.get("possession") or {}).get("group")
        side = _side_from_group(
            group,
            int(manifest["home_team_id"]),
            int(manifest["away_team_id"]),
        )
        possession_side[frame] = side
        if side in {TeamSide.HOME, TeamSide.AWAY}:
            possession_status[frame] = 0
        elif group is not None:
            possession_status[frame] = 2

    checksums = dict(loaded.actual_checksums)
    phases: tuple[PhaseSpan, ...] = ()
    if include_phases:
        phase_snapshot = loaded.files.get("phases")
        if phase_snapshot is None:
            phase_path = Path(loaded.external_root) / manifest["files"]["phases"]["path"]
            try:
                phase_data = phase_path.read_bytes()
            except OSError as error:
                raise SkillCornerDataError("evaluation phase file is missing") from error
            actual = hashlib.sha256(phase_data).hexdigest()
            if actual != manifest["files"]["phases"]["sha256"]:
                raise SkillCornerDataError("evaluation phase checksum mismatch")
            checksums["phases"] = actual
            phase_bytes = phase_data
        else:
            phase_bytes = phase_snapshot.data
        try:
            phase_handle = StringIO(phase_bytes.decode("utf-8"), newline="")
        except UnicodeDecodeError as error:
            raise SkillCornerDataError("could not decode evaluation phase bytes") from error
        phases = _parse_phases_stream(
            phase_handle,
            frame_count=frame_count,
            home_team_id=int(manifest["home_team_id"]),
            away_team_id=int(manifest["away_team_id"]),
        )
    return EvaluationReference(
        match_id=str(manifest["match_id"]),
        frame_count=frame_count,
        player_ids=loaded.match.player_ids,
        periods=loaded.match.periods,
        phases=phases,
        frame_present=loaded.match.frame_present.copy(),
        possession_side=possession_side,
        possession_status=possession_status,
        source_checksums=checksums,
        source_metadata=dict(loaded.match.source_metadata),
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
    with path.open("r", encoding="utf-8", newline="") as handle:
        return _parse_phases_stream(
            handle,
            frame_count=frame_count,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
        )


def _parse_phases_stream(
    handle: Any,
    *,
    frame_count: int,
    home_team_id: int,
    away_team_id: int,
) -> tuple[PhaseSpan, ...]:
    phases: list[PhaseSpan] = []
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


def _max_tracking_frame_bytes(data: bytes) -> int:
    try:
        lines = data[-1024 * 1024 :].decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise SkillCornerDataError("could not decode external tracking data") from error
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            return int(json.loads(line)["frame"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise SkillCornerDataError("could not parse the final external frame") from error
    raise SkillCornerDataError("external tracking file has no records")


def _canonical_json(values: Mapping[str, Any]) -> bytes:
    return json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    return value
