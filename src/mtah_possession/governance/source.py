"""Canonical identity for the actual audited external source."""

from __future__ import annotations

import hashlib
import json
import os
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


def build_source_identity(config_path: str | os.PathLike[str]) -> SourceIdentity:
    manifest = load_skillcorner_manifest(config_path)
    source_config_sha256 = _sha256_file(config_path)
    files = {
        role: {
            "path": _logical_path(manifest["files"][role]["path"]),
            "sha256": _required_sha256(
                manifest["files"][role]["sha256"],
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
    payload = {
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
            manifest["license_sha256"],
            "license SHA-256",
        ),
        "readme_sha256": _required_sha256(
            manifest["readme_sha256"],
            "README SHA-256",
        ),
        "files": files,
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


def source_identity_payload(identity: SourceIdentity) -> dict[str, Any]:
    values = identity.to_dict()
    values.pop("source_identity_sha256")
    return values


def _canonical_json(values: dict[str, Any]) -> bytes:
    return json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise PolicyError(f"could not hash source config: {path}") from error
    return digest.hexdigest()


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
