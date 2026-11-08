"""Canonical identity for the actual audited external source."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mtah_possession.data.skillcorner import load_skillcorner_manifest
from mtah_possession.governance.policy import PolicyError

SOURCE_IDENTITY_SCHEMA_VERSION = "1.0"
SOURCE_FILE_ROLES = ("tracking", "phases", "match")


@dataclass(frozen=True)
class SourceIdentity:
    schema_version: str
    provider: str
    source_revision: str
    match_id: str
    fps: int
    home_team_id: int
    away_team_id: int
    pitch_length_m: float
    pitch_width_m: float
    coordinate_convention: str
    license_sha256: str
    readme_sha256: str
    files: dict[str, dict[str, str]]
    source_config_sha256: str
    source_identity_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider,
            "source_revision": self.source_revision,
            "match_id": self.match_id,
            "fps": self.fps,
            "home_team_id": self.home_team_id,
            "away_team_id": self.away_team_id,
            "pitch_length_m": self.pitch_length_m,
            "pitch_width_m": self.pitch_width_m,
            "coordinate_convention": self.coordinate_convention,
            "license_sha256": self.license_sha256,
            "readme_sha256": self.readme_sha256,
            "files": self.files,
            "source_config_sha256": self.source_config_sha256,
            "source_identity_sha256": self.source_identity_sha256,
        }


@dataclass(frozen=True)
class SourceIdentitySet:
    schema_version: str
    provider: str
    members: tuple[dict[str, str], ...]
    identities: dict[str, SourceIdentity]
    identity_digests: dict[str, str]
    source_set_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider,
            "members": list(self.members),
            "source_identity_map": dict(sorted(self.identity_digests.items())),
            "source_set_sha256": self.source_set_sha256,
        }


def build_source_identity(config_path: str | os.PathLike[str]) -> SourceIdentity:
    manifest = load_skillcorner_manifest(config_path)
    return build_source_identity_from_manifest(manifest)


def build_source_identity_from_manifest(
    manifest: Mapping[str, Any],
    *,
    actual_file_sha256: Mapping[str, str] | None = None,
    actual_license_sha256: str | None = None,
    actual_readme_sha256: str | None = None,
) -> SourceIdentity:
    files = {
        role: {
            "path": _logical_path(manifest["files"][role]["path"]),
            "sha256": _required_sha256(
                (
                    actual_file_sha256[role]
                    if actual_file_sha256 is not None
                    else manifest["files"][role]["sha256"]
                ),
                f"{role} file SHA-256",
            ),
        }
        for role in SOURCE_FILE_ROLES
    }
    fps = manifest["fps"]
    home_team_id = manifest["home_team_id"]
    away_team_id = manifest["away_team_id"]
    pitch_length_m = manifest["pitch_length_m"]
    pitch_width_m = manifest["pitch_width_m"]
    if not isinstance(fps, int) or isinstance(fps, bool) or fps <= 0:
        raise PolicyError("source fps must be a positive integer")
    for label, value in (
        ("home_team_id", home_team_id),
        ("away_team_id", away_team_id),
    ):
        if not isinstance(value, int) or isinstance(value, bool):
            raise PolicyError(f"source {label} must be an integer")
    for label, value in (
        ("pitch_length_m", pitch_length_m),
        ("pitch_width_m", pitch_width_m),
    ):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise PolicyError(f"source {label} must be positive")
    source_projection = {
        "schema_version": SOURCE_IDENTITY_SCHEMA_VERSION,
        "provider": str(manifest["provider"]),
        "source_revision": _required_commit(manifest["commit"]),
        "match_id": _required_text(manifest["match_id"], "source match ID"),
        "fps": fps,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "pitch_length_m": float(pitch_length_m),
        "pitch_width_m": float(pitch_width_m),
        "coordinate_convention": _required_text(
            manifest["coordinate_convention"],
            "coordinate convention",
        ),
        "license_sha256": _required_sha256(
            (
                actual_license_sha256
                if actual_license_sha256 is not None
                else manifest["license_sha256"]
            ),
            "license SHA-256",
        ),
        "readme_sha256": _required_sha256(
            (
                actual_readme_sha256
                if actual_readme_sha256 is not None
                else manifest["readme_sha256"]
            ),
            "README SHA-256",
        ),
        "files": files,
    }
    source_config_sha256 = hashlib.sha256(_canonical_json(source_projection)).hexdigest()
    payload = {
        **source_projection,
        "source_config_sha256": source_config_sha256,
    }
    return SourceIdentity(
        schema_version=payload["schema_version"],
        provider=payload["provider"],
        source_revision=payload["source_revision"],
        match_id=payload["match_id"],
        fps=payload["fps"],
        home_team_id=payload["home_team_id"],
        away_team_id=payload["away_team_id"],
        pitch_length_m=payload["pitch_length_m"],
        pitch_width_m=payload["pitch_width_m"],
        coordinate_convention=payload["coordinate_convention"],
        license_sha256=payload["license_sha256"],
        readme_sha256=payload["readme_sha256"],
        files=payload["files"],
        source_config_sha256=payload["source_config_sha256"],
        source_identity_sha256=hashlib.sha256(_canonical_json(payload)).hexdigest(),
    )


def source_identity_from_dict(values: Any) -> SourceIdentity:
    required = {
        "schema_version",
        "provider",
        "source_revision",
        "match_id",
        "fps",
        "home_team_id",
        "away_team_id",
        "pitch_length_m",
        "pitch_width_m",
        "coordinate_convention",
        "license_sha256",
        "readme_sha256",
        "files",
        "source_config_sha256",
        "source_identity_sha256",
    }
    if not isinstance(values, dict) or set(values) != required:
        raise PolicyError("source identity has missing or unknown fields")
    if values["schema_version"] != SOURCE_IDENTITY_SCHEMA_VERSION:
        raise PolicyError("source identity schema version is unsupported")
    files = values["files"]
    if not isinstance(files, dict) or set(files) != set(SOURCE_FILE_ROLES):
        raise PolicyError("source identity file roles are invalid")
    normalized_files: dict[str, dict[str, str]] = {}
    for role in SOURCE_FILE_ROLES:
        entry = files[role]
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise PolicyError(f"source identity {role} file entry is invalid")
        normalized_files[role] = {
            "path": _logical_path(entry["path"]),
            "sha256": _required_sha256(entry["sha256"], f"{role} file SHA-256"),
        }
    payload = {
        **{
            key: values[key]
            for key in (
                "schema_version",
                "provider",
                "source_revision",
                "match_id",
                "fps",
                "home_team_id",
                "away_team_id",
                "pitch_length_m",
                "pitch_width_m",
                "coordinate_convention",
                "license_sha256",
                "readme_sha256",
            )
        },
        "files": normalized_files,
        "source_config_sha256": _required_sha256(
            values["source_config_sha256"],
            "source config SHA-256",
        ),
    }
    source_projection = {
        key: value for key, value in payload.items() if key != "source_config_sha256"
    }
    if (
        payload["source_config_sha256"]
        != hashlib.sha256(_canonical_json(source_projection)).hexdigest()
    ):
        raise PolicyError("source config SHA does not match source-only projection")
    digest = _required_sha256(
        values["source_identity_sha256"],
        "source identity SHA-256",
    )
    if digest != hashlib.sha256(_canonical_json(payload)).hexdigest():
        raise PolicyError("source identity digest does not match")
    return SourceIdentity(
        schema_version=payload["schema_version"],
        provider=_required_text(payload["provider"], "source provider"),
        source_revision=_required_commit(payload["source_revision"]),
        match_id=_required_text(payload["match_id"], "source match ID"),
        fps=_required_int(payload["fps"], "source fps", positive=True),
        home_team_id=_required_int(payload["home_team_id"], "home team ID"),
        away_team_id=_required_int(payload["away_team_id"], "away team ID"),
        pitch_length_m=_required_float(payload["pitch_length_m"], "pitch length"),
        pitch_width_m=_required_float(payload["pitch_width_m"], "pitch width"),
        coordinate_convention=_required_text(
            payload["coordinate_convention"],
            "coordinate convention",
        ),
        license_sha256=_required_sha256(payload["license_sha256"], "license SHA-256"),
        readme_sha256=_required_sha256(payload["readme_sha256"], "README SHA-256"),
        files=normalized_files,
        source_config_sha256=payload["source_config_sha256"],
        source_identity_sha256=digest,
    )


def build_source_identity_set(
    descriptor_path: str | os.PathLike[str],
    *,
    provider: str,
    holdout_matches: tuple[str, ...],
    source_root: str | os.PathLike[str] | None = None,
    identity_overrides: Mapping[str, SourceIdentity] | None = None,
) -> SourceIdentitySet:
    path = Path(descriptor_path)
    repository_root = Path(source_root) if source_root is not None else path.parent
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyError("could not read source-set descriptor") from error
    required = {"schema_version", "provider", "members", "source_set_sha256"}
    if not isinstance(values, dict) or set(values) != required:
        raise PolicyError("source-set descriptor has missing or unknown fields")
    if values["schema_version"] != "1.0":
        raise PolicyError("source-set descriptor schema version is unsupported")
    if values["provider"] != provider:
        raise PolicyError("source-set provider does not match source config")
    members = values["members"]
    if not isinstance(members, list) or not members:
        raise PolicyError("source-set members must be a non-empty list")
    parsed_members: list[dict[str, str]] = []
    seen: set[str] = set()
    identities: dict[str, SourceIdentity] = {}
    for member in members:
        if not isinstance(member, dict) or set(member) != {"match_id", "source_config"}:
            raise PolicyError("source-set member is invalid")
        match_id = _required_text(member["match_id"], "source-set match ID")
        if match_id in seen:
            raise PolicyError("source-set contains a duplicate match ID")
        seen.add(match_id)
        source_config = _logical_path(member["source_config"])
        config_path = repository_root / source_config
        identity = (
            identity_overrides[match_id]
            if identity_overrides is not None and match_id in identity_overrides
            else build_source_identity(config_path)
        )
        if identity.provider != provider or identity.match_id != match_id:
            raise PolicyError("source-set member identity does not match its match ID")
        parsed_members.append({"match_id": match_id, "source_config": source_config})
        identities[match_id] = identity
    parsed_members.sort(key=lambda member: member["match_id"])
    if set(identities) != set(holdout_matches):
        raise PolicyError("source-set members do not equal Holdout Manifest matches")
    expected_digest = _source_set_digest(provider, parsed_members)
    if values["source_set_sha256"] != expected_digest:
        raise PolicyError("source-set descriptor digest does not match")
    return SourceIdentitySet(
        schema_version="1.0",
        provider=provider,
        members=tuple(parsed_members),
        identities=identities,
        identity_digests={
            match_id: identity.source_identity_sha256 for match_id, identity in identities.items()
        },
        source_set_sha256=expected_digest,
    )


def build_single_source_identity_set(
    *,
    provider: str,
    match_id: str,
    source_config: str | os.PathLike[str],
    identity_override: SourceIdentity | None = None,
) -> SourceIdentitySet:
    identity = identity_override or build_source_identity(source_config)
    if identity.provider != provider or identity.match_id != match_id:
        raise PolicyError("single source identity does not match current match")
    source_config_name = Path(source_config).name
    members = ({"match_id": match_id, "source_config": source_config_name},)
    digest = _source_set_digest(provider, list(members))
    return SourceIdentitySet(
        schema_version="1.0",
        provider=provider,
        members=members,
        identities={match_id: identity},
        identity_digests={match_id: identity.source_identity_sha256},
        source_set_sha256=digest,
    )


def current_source_identity(
    source_set: SourceIdentitySet,
    *,
    match_id: str,
    source_config: str | os.PathLike[str],
    source_root: str | os.PathLike[str] | None,
    identity_override: SourceIdentity | None = None,
) -> SourceIdentity:
    identity = identity_override or build_source_identity(source_config)
    if match_id not in source_set.identity_digests:
        raise PolicyError("current match is not registered in SourceIdentitySet")
    if source_root is not None:
        member = next(member for member in source_set.members if member["match_id"] == match_id)
        expected_config = (Path(source_root) / member["source_config"]).resolve(strict=True)
        if Path(source_config).resolve(strict=True) != expected_config:
            raise PolicyError("current source config does not match SourceIdentitySet")
    if identity.source_identity_sha256 != source_set.identity_digests[match_id]:
        raise PolicyError("current source identity does not match sealed SourceIdentitySet")
    return identity


def source_identity_set_from_dict(values: Any) -> SourceIdentitySet:
    required = {
        "schema_version",
        "provider",
        "members",
        "source_identity_map",
        "source_set_sha256",
    }
    if not isinstance(values, dict) or set(values) != required:
        raise PolicyError("SourceIdentitySet has missing or unknown fields")
    if values["schema_version"] != "1.0":
        raise PolicyError("SourceIdentitySet schema version is unsupported")
    provider = _required_text(values["provider"], "source-set provider")
    raw_members = values["members"]
    if not isinstance(raw_members, list) or not raw_members:
        raise PolicyError("SourceIdentitySet members are empty")
    members: list[dict[str, str]] = []
    seen: set[str] = set()
    for member in raw_members:
        if not isinstance(member, dict) or set(member) != {"match_id", "source_config"}:
            raise PolicyError("SourceIdentitySet member is invalid")
        match_id = _required_text(member["match_id"], "source-set match ID")
        if match_id in seen:
            raise PolicyError("SourceIdentitySet contains a duplicate match ID")
        seen.add(match_id)
        members.append(
            {
                "match_id": match_id,
                "source_config": _logical_path(member["source_config"]),
            }
        )
    members.sort(key=lambda member: member["match_id"])
    if len(members) != len(raw_members) or any(
        left != right for left, right in zip(raw_members, members, strict=True)
    ):
        raise PolicyError("SourceIdentitySet members are not canonically sorted")
    identity_map = values["source_identity_map"]
    if not isinstance(identity_map, dict) or set(identity_map) != seen:
        raise PolicyError("SourceIdentitySet identity map does not match members")
    identity_digests = {
        match_id: _required_sha256(digest, f"source identity {match_id}")
        for match_id, digest in identity_map.items()
    }
    expected_digest = _source_set_digest(provider, members)
    if values["source_set_sha256"] != expected_digest:
        raise PolicyError("SourceIdentitySet descriptor digest does not match")
    return SourceIdentitySet(
        schema_version="1.0",
        provider=provider,
        members=tuple(members),
        identities={},
        identity_digests=identity_digests,
        source_set_sha256=expected_digest,
    )


def source_identity_payload(identity: SourceIdentity) -> dict[str, Any]:
    values = identity.to_dict()
    values.pop("source_identity_sha256")
    return values


def _canonical_json(values: dict[str, Any]) -> bytes:
    return json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _source_set_digest(provider: str, members: list[dict[str, str]]) -> str:
    payload = {
        "schema_version": "1.0",
        "provider": provider,
        "members": members,
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _logical_path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyError("source file path is missing")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise PolicyError("source file path must be logical and relative")
    return path.as_posix()


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f"{label} is missing")
    return value


def _required_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PolicyError(f"{label} is invalid")
    return value


def _required_commit(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PolicyError("source revision must be a full lowercase commit")
    return value


def _required_int(value: Any, label: str, *, positive: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or (positive and value <= 0):
        raise PolicyError(f"{label} is invalid")
    return value


def _required_float(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise PolicyError(f"{label} is invalid")
    return float(value)
