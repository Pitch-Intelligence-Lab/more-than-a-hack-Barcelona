"""Machine-readable historical exposure register with a trusted reseal chain."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from mtah_possession.governance.policy import PolicyError


class ExposureLevel(StrEnum):
    ID_ONLY = "ID_ONLY"
    METADATA_SEEN = "METADATA_SEEN"
    TRACKING_SEEN = "TRACKING_SEEN"
    EVENTS_SEEN = "EVENTS_SEEN"
    PHASES_SEEN = "PHASES_SEEN"
    MODEL_EXPERIMENT_USED = "MODEL_EXPERIMENT_USED"
    EVALUATION_REFERENCE_SEEN = "EVALUATION_REFERENCE_SEEN"
    HOLDOUT_RESULT_SEEN = "HOLDOUT_RESULT_SEEN"


EXPOSURE_RANK = {
    level: rank
    for rank, level in enumerate(
        (
            ExposureLevel.ID_ONLY,
            ExposureLevel.METADATA_SEEN,
            ExposureLevel.TRACKING_SEEN,
            ExposureLevel.EVENTS_SEEN,
            ExposureLevel.PHASES_SEEN,
            ExposureLevel.MODEL_EXPERIMENT_USED,
            ExposureLevel.EVALUATION_REFERENCE_SEEN,
            ExposureLevel.HOLDOUT_RESULT_SEEN,
        ),
        start=1,
    )
}
HOLDOUT_ELIGIBLE_LEVELS = frozenset(
    {
        ExposureLevel.ID_ONLY,
        ExposureLevel.METADATA_SEEN,
    }
)


@dataclass(frozen=True)
class ExposureRecord:
    match_id: str
    provider: str
    source_revision: str
    exposure_level: ExposureLevel
    evidence: tuple[str, ...]
    recorded_at: str
    recorded_by: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "provider": self.provider,
            "source_revision": self.source_revision,
            "exposure_level": self.exposure_level.value,
            "evidence": list(self.evidence),
            "recorded_at": self.recorded_at,
            "recorded_by": self.recorded_by,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ExposureRegister:
    schema_version: str
    status: str
    missing_record_policy: str
    records: tuple[ExposureRecord, ...]

    def record_for(self, match_id: str) -> ExposureRecord:
        for record in self.records:
            if record.match_id == match_id:
                return record
        raise PolicyError(f"Holdout exposure history is missing for match {match_id}")

    def for_holdout(
        self,
        *,
        provider: str,
        source_revision: str,
        match_ids: tuple[str, ...],
    ) -> tuple[ExposureRecord, ...]:
        if not match_ids:
            return ()
        selected = tuple(self.record_for(match_id) for match_id in sorted(set(match_ids)))
        for record in selected:
            if record.provider != provider or record.source_revision != source_revision:
                raise PolicyError(f"Holdout exposure identity mismatch for match {record.match_id}")
            if record.exposure_level not in HOLDOUT_ELIGIBLE_LEVELS:
                raise PolicyError(
                    f"historically exposed match {record.match_id} cannot become Holdout: "
                    f"{record.exposure_level.value}"
                )
        return selected


@dataclass(frozen=True)
class ExposureAnchor:
    schema_version: str
    register_path: str
    register_path_identity: str
    register_sha256: str
    previous_register_sha256: str | None
    reseal_id: str
    approved_by: str
    approved_at: str
    approval_evidence: tuple[str, ...]
    highest_exposure_by_match: dict[str, ExposureLevel]
    source_identity_by_match: dict[str, dict[str, str]]
    holdout_provider: str
    holdout_match_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "register_path": self.register_path,
            "register_path_identity": self.register_path_identity,
            "register_sha256": self.register_sha256,
            "previous_register_sha256": self.previous_register_sha256,
            "reseal_id": self.reseal_id,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "approval_evidence": list(self.approval_evidence),
            "highest_exposure_by_match": {
                match_id: level.value
                for match_id, level in sorted(self.highest_exposure_by_match.items())
            },
            "source_identity_by_match": {
                match_id: dict(identity)
                for match_id, identity in sorted(self.source_identity_by_match.items())
            },
            "holdout_provider": self.holdout_provider,
            "holdout_match_ids": list(self.holdout_match_ids),
        }


@dataclass(frozen=True)
class ResealRecord:
    reseal_id: str
    old_register_sha256: str
    new_register_sha256: str
    old_anchor_sha256: str
    new_anchor_sha256: str
    approved_by: str
    approved_at: str
    reason: str
    approval_evidence: tuple[str, ...]
    highest_exposure_by_match_before: dict[str, ExposureLevel]
    highest_exposure_by_match_after: dict[str, ExposureLevel]

    def to_dict(self) -> dict[str, Any]:
        return {
            "reseal_id": self.reseal_id,
            "old_register_sha256": self.old_register_sha256,
            "new_register_sha256": self.new_register_sha256,
            "old_anchor_sha256": self.old_anchor_sha256,
            "new_anchor_sha256": self.new_anchor_sha256,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "reason": self.reason,
            "approval_evidence": list(self.approval_evidence),
            "highest_exposure_by_match_before": {
                match_id: level.value
                for match_id, level in sorted(self.highest_exposure_by_match_before.items())
            },
            "highest_exposure_by_match_after": {
                match_id: level.value
                for match_id, level in sorted(self.highest_exposure_by_match_after.items())
            },
        }


@dataclass(frozen=True)
class ExposureTrustRoot:
    schema_version: str
    status: str
    anchor_path: str
    anchor_path_identity: str
    anchor_sha256: str
    reseals: tuple[ResealRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "anchor_path": self.anchor_path,
            "anchor_path_identity": self.anchor_path_identity,
            "anchor_sha256": self.anchor_sha256,
            "reseals": [record.to_dict() for record in self.reseals],
        }


@dataclass(frozen=True)
class VerifiedExposureSnapshot:
    register: ExposureRegister
    anchor: ExposureAnchor
    trust_root: ExposureTrustRoot
    records: tuple[ExposureRecord, ...]
    register_path: str
    register_path_identity: str
    register_sha256: str
    anchor_path: str
    anchor_path_identity: str
    anchor_sha256: str
    trust_root_sha256: str


@dataclass(frozen=True)
class ExposureSealResult:
    anchor_path: Path
    anchor_sha256: str
    trust_root_path: Path
    trust_root_sha256: str


def load_exposure_register(path: str | os.PathLike[str]) -> ExposureRegister:
    raw = _load_json_object(path, "exposure register")
    required = {"schema_version", "status", "missing_record_policy", "records"}
    if set(raw) != required:
        raise PolicyError("exposure register has missing or unknown fields")
    if raw["schema_version"] != "1.0":
        raise PolicyError("exposure register schema_version must be 1.0")
    if raw["status"] != "ACTIVE":
        raise PolicyError("exposure register must be ACTIVE")
    if raw["missing_record_policy"] != "DENY":
        raise PolicyError("exposure register must fail closed for missing records")
    if not isinstance(raw["records"], list):
        raise PolicyError("exposure register records must be a list")
    records = tuple(_parse_record(item) for item in raw["records"])
    match_ids = [record.match_id for record in records]
    if len(set(match_ids)) != len(match_ids):
        raise PolicyError("exposure register contains duplicate match IDs")
    return ExposureRegister(
        schema_version="1.0",
        status="ACTIVE",
        missing_record_policy="DENY",
        records=records,
    )


def load_exposure_anchor(path: str | os.PathLike[str]) -> ExposureAnchor:
    raw = _load_json_object(path, "exposure anchor")
    required = {
        "schema_version",
        "register_path",
        "register_path_identity",
        "register_sha256",
        "previous_register_sha256",
        "reseal_id",
        "approved_by",
        "approved_at",
        "approval_evidence",
        "highest_exposure_by_match",
        "source_identity_by_match",
        "holdout_provider",
        "holdout_match_ids",
    }
    if set(raw) != required:
        raise PolicyError("exposure anchor has missing or unknown fields")
    if raw["schema_version"] != "1.0":
        raise PolicyError("exposure anchor schema_version must be 1.0")
    for field in (
        "register_path",
        "register_path_identity",
        "register_sha256",
        "reseal_id",
        "approved_by",
        "approved_at",
        "holdout_provider",
    ):
        _require_nonempty_string(raw[field], f"exposure anchor {field}")
    _require_sha256(raw["register_path_identity"], "exposure register path identity")
    _require_sha256(raw["register_sha256"], "exposure register SHA-256")
    previous = raw["previous_register_sha256"]
    if previous is not None:
        _require_sha256(previous, "previous exposure register SHA-256")
    _require_timezone_timestamp(raw["approved_at"], "exposure anchor approved_at")
    evidence = _string_tuple(raw["approval_evidence"], "approval_evidence", nonempty=True)
    highest = _parse_level_map(raw["highest_exposure_by_match"], "highest exposure")
    identities = _parse_identity_map(raw["source_identity_by_match"])
    if set(highest) != set(identities):
        raise PolicyError("exposure anchor match histories are inconsistent")
    match_ids = _string_tuple(raw["holdout_match_ids"], "holdout_match_ids")
    if match_ids != tuple(sorted(set(match_ids))):
        raise PolicyError("exposure anchor Holdout match IDs must be sorted and unique")
    return ExposureAnchor(
        schema_version="1.0",
        register_path=raw["register_path"],
        register_path_identity=raw["register_path_identity"],
        register_sha256=raw["register_sha256"],
        previous_register_sha256=previous,
        reseal_id=raw["reseal_id"],
        approved_by=raw["approved_by"],
        approved_at=raw["approved_at"],
        approval_evidence=evidence,
        highest_exposure_by_match=highest,
        source_identity_by_match=identities,
        holdout_provider=raw["holdout_provider"],
        holdout_match_ids=match_ids,
    )


def load_exposure_trust_root(path: str | os.PathLike[str]) -> ExposureTrustRoot:
    raw = _load_json_object(path, "exposure trust root")
    required = {
        "schema_version",
        "status",
        "anchor_path",
        "anchor_path_identity",
        "anchor_sha256",
        "reseals",
    }
    if set(raw) != required:
        raise PolicyError("exposure trust root has missing or unknown fields")
    if raw["schema_version"] != "1.0" or raw["status"] != "ACTIVE":
        raise PolicyError("exposure trust root must be schema 1.0 and ACTIVE")
    _require_nonempty_string(raw["anchor_path"], "exposure trust root anchor_path")
    _require_sha256(raw["anchor_path_identity"], "exposure anchor path identity")
    _require_sha256(raw["anchor_sha256"], "exposure anchor SHA-256")
    if not isinstance(raw["reseals"], list):
        raise PolicyError("exposure reseal history must be a list")
    reseals = tuple(_parse_reseal(item) for item in raw["reseals"])
    reseal_ids = [record.reseal_id for record in reseals]
    if len(set(reseal_ids)) != len(reseal_ids):
        raise PolicyError("exposure reseal history contains duplicate IDs")
    return ExposureTrustRoot(
        schema_version="1.0",
        status="ACTIVE",
        anchor_path=raw["anchor_path"],
        anchor_path_identity=raw["anchor_path_identity"],
        anchor_sha256=raw["anchor_sha256"],
        reseals=reseals,
    )


def load_verified_exposure_snapshot(
    *,
    register_path: str | os.PathLike[str] | None,
    anchor_path: str | os.PathLike[str] | None,
    trust_root_path: str | os.PathLike[str] | None,
    expected_trust_root_sha256: str | None,
    provider: str,
    source_revision: str,
    match_ids: tuple[str, ...],
) -> VerifiedExposureSnapshot:
    if register_path is None or anchor_path is None or trust_root_path is None:
        raise PolicyError("Holdout authorization requires register, anchor and trust root")
    if expected_trust_root_sha256 is None:
        raise PolicyError("Holdout authorization requires a trusted exposure root")
    _require_sha256(expected_trust_root_sha256, "trusted exposure root SHA-256")

    register_path_text, register_path_identity = canonical_path_identity(register_path)
    anchor_path_text, anchor_path_identity = canonical_path_identity(anchor_path)
    register_sha256 = sha256_file(register_path)
    anchor_sha256 = sha256_file(anchor_path)
    trust_root_sha256 = sha256_file(trust_root_path)
    if trust_root_sha256 != expected_trust_root_sha256:
        raise PolicyError("exposure trust root does not match the approved trust root")

    register = load_exposure_register(register_path)
    anchor = load_exposure_anchor(anchor_path)
    trust_root = load_exposure_trust_root(trust_root_path)
    if trust_root.anchor_sha256 != anchor_sha256:
        raise PolicyError("exposure anchor SHA-256 does not match the trust root")
    if (
        trust_root.anchor_path != anchor_path_text
        or trust_root.anchor_path_identity != anchor_path_identity
    ):
        raise PolicyError("exposure anchor path identity does not match the trust root")
    if (
        anchor.register_path != register_path_text
        or anchor.register_path_identity != register_path_identity
    ):
        raise PolicyError("exposure register path identity does not match the anchor")
    if anchor.register_sha256 != register_sha256:
        raise PolicyError("exposure register SHA-256 does not match the sealed anchor")
    if anchor.holdout_provider != provider:
        raise PolicyError("sealed exposure Holdout provider does not match")
    expected_matches = tuple(sorted(set(match_ids)))
    if anchor.holdout_match_ids != expected_matches:
        raise PolicyError("sealed exposure Holdout match set does not match")
    register_match_ids = {record.match_id for record in register.records}
    if set(anchor.highest_exposure_by_match) != register_match_ids:
        raise PolicyError("exposure register and anchor match histories differ")
    for record in register.records:
        high_water = anchor.highest_exposure_by_match[record.match_id]
        if EXPOSURE_RANK[record.exposure_level] < EXPOSURE_RANK[high_water]:
            raise PolicyError(
                f"exposure level for match {record.match_id} is below the sealed high-water mark"
            )
        identity = anchor.source_identity_by_match[record.match_id]
        if (
            identity["provider"] != record.provider
            or identity["source_revision"] != record.source_revision
        ):
            raise PolicyError(f"exposure source identity changed for match {record.match_id}")
    records = register.for_holdout(
        provider=provider,
        source_revision=source_revision,
        match_ids=match_ids,
    )
    return VerifiedExposureSnapshot(
        register=register,
        anchor=anchor,
        trust_root=trust_root,
        records=records,
        register_path=register_path_text,
        register_path_identity=register_path_identity,
        register_sha256=register_sha256,
        anchor_path=anchor_path_text,
        anchor_path_identity=anchor_path_identity,
        anchor_sha256=anchor_sha256,
        trust_root_sha256=trust_root_sha256,
    )


def create_exposure_seal(
    *,
    register_path: str | os.PathLike[str],
    anchor_path: str | os.PathLike[str],
    trust_root_path: str | os.PathLike[str],
    holdout_provider: str,
    holdout_match_ids: tuple[str, ...],
    approved_by: str,
    approved_at: str,
    approval_evidence: tuple[str, ...],
    reseal_id: str,
) -> ExposureSealResult:
    """Create the first trusted exposure seal from an explicitly approved register."""
    _require_nonempty_string(approved_by, "exposure approval owner")
    _require_nonempty_string(reseal_id, "exposure reseal ID")
    _require_timezone_timestamp(approved_at, "exposure approved_at")
    if not approval_evidence:
        raise PolicyError("exposure seal requires approval evidence")
    register = load_exposure_register(register_path)
    register_path_text, register_path_identity = canonical_path_identity(register_path)
    anchor_path_text, anchor_path_identity = canonical_path_identity(anchor_path)
    matches = tuple(sorted(set(holdout_match_ids)))
    highest = {record.match_id: record.exposure_level for record in register.records}
    identities = {
        record.match_id: {
            "provider": record.provider,
            "source_revision": record.source_revision,
        }
        for record in register.records
    }
    anchor = ExposureAnchor(
        schema_version="1.0",
        register_path=register_path_text,
        register_path_identity=register_path_identity,
        register_sha256=sha256_file(register_path),
        previous_register_sha256=None,
        reseal_id=reseal_id,
        approved_by=approved_by,
        approved_at=approved_at,
        approval_evidence=approval_evidence,
        highest_exposure_by_match=highest,
        source_identity_by_match=identities,
        holdout_provider=holdout_provider,
        holdout_match_ids=matches,
    )
    _write_json_atomic(Path(anchor_path), anchor.to_dict())
    anchor_sha256 = sha256_file(anchor_path)
    trust_root = ExposureTrustRoot(
        schema_version="1.0",
        status="ACTIVE",
        anchor_path=anchor_path_text,
        anchor_path_identity=anchor_path_identity,
        anchor_sha256=anchor_sha256,
        reseals=(),
    )
    _write_json_atomic(Path(trust_root_path), trust_root.to_dict())
    return ExposureSealResult(
        anchor_path=Path(anchor_path),
        anchor_sha256=anchor_sha256,
        trust_root_path=Path(trust_root_path),
        trust_root_sha256=sha256_file(trust_root_path),
    )


def reseal_exposure_register(
    *,
    register_path: str | os.PathLike[str],
    anchor_path: str | os.PathLike[str],
    trust_root_path: str | os.PathLike[str],
    expected_trust_root_sha256: str,
    reseal_id: str,
    approved_by: str,
    approved_at: str,
    reason: str,
    approval_evidence: tuple[str, ...],
) -> ExposureSealResult:
    """Approve a monotonic register update and preserve its complete audit history."""
    _require_nonempty_string(reseal_id, "exposure reseal ID")
    _require_nonempty_string(approved_by, "exposure approval owner")
    _require_nonempty_string(reason, "exposure reseal reason")
    _require_timezone_timestamp(approved_at, "exposure reseal approved_at")
    if not approval_evidence:
        raise PolicyError("exposure reseal requires approval evidence")
    current_root_sha256 = sha256_file(trust_root_path)
    if current_root_sha256 != expected_trust_root_sha256:
        raise PolicyError("current exposure trust root does not match the approved root")

    register_path_text, register_path_identity = canonical_path_identity(register_path)
    anchor_path_text, anchor_path_identity = canonical_path_identity(anchor_path)
    anchor_sha256 = sha256_file(anchor_path)
    trust_root = load_exposure_trust_root(trust_root_path)
    anchor = load_exposure_anchor(anchor_path)
    if (
        trust_root.anchor_path != anchor_path_text
        or trust_root.anchor_path_identity != anchor_path_identity
        or trust_root.anchor_sha256 != anchor_sha256
    ):
        raise PolicyError("current exposure anchor does not match the trust root")
    if (
        anchor.register_path != register_path_text
        or anchor.register_path_identity != register_path_identity
    ):
        raise PolicyError("alternative exposure register path requires a new approved seal")
    if any(record.reseal_id == reseal_id for record in trust_root.reseals):
        raise PolicyError("exposure reseal ID has already been used")

    register = load_exposure_register(register_path)
    current_sha256 = sha256_file(register_path)
    if current_sha256 == anchor.register_sha256:
        raise PolicyError("exposure register has not changed since its approved seal")
    current_by_match = {record.match_id: record for record in register.records}
    missing = sorted(set(anchor.highest_exposure_by_match).difference(current_by_match))
    if missing:
        raise PolicyError(f"exposure reseal cannot remove historical matches: {missing}")
    highest_after = {
        match_id: max(
            current_by_match[match_id].exposure_level,
            previous_level,
            key=EXPOSURE_RANK.__getitem__,
        )
        for match_id, previous_level in anchor.highest_exposure_by_match.items()
    }
    for match_id, previous_level in anchor.highest_exposure_by_match.items():
        current = current_by_match[match_id]
        previous_identity = anchor.source_identity_by_match[match_id]
        if (
            current.provider != previous_identity["provider"]
            or current.source_revision != previous_identity["source_revision"]
        ):
            raise PolicyError(f"exposure reseal cannot change source identity for {match_id}")
        if EXPOSURE_RANK[current.exposure_level] < EXPOSURE_RANK[previous_level]:
            raise PolicyError(
                f"exposure reseal cannot lower match {match_id} below {previous_level.value}"
            )
    for record in register.records:
        highest_after.setdefault(record.match_id, record.exposure_level)
    identities_after = {
        record.match_id: {
            "provider": record.provider,
            "source_revision": record.source_revision,
        }
        for record in register.records
    }
    new_anchor = ExposureAnchor(
        schema_version="1.0",
        register_path=register_path_text,
        register_path_identity=register_path_identity,
        register_sha256=current_sha256,
        previous_register_sha256=anchor.register_sha256,
        reseal_id=reseal_id,
        approved_by=approved_by,
        approved_at=approved_at,
        approval_evidence=approval_evidence,
        highest_exposure_by_match=highest_after,
        source_identity_by_match=identities_after,
        holdout_provider=anchor.holdout_provider,
        holdout_match_ids=anchor.holdout_match_ids,
    )
    _write_json_atomic(Path(anchor_path), new_anchor.to_dict())
    new_anchor_sha256 = sha256_file(anchor_path)
    record = ResealRecord(
        reseal_id=reseal_id,
        old_register_sha256=anchor.register_sha256,
        new_register_sha256=current_sha256,
        old_anchor_sha256=anchor_sha256,
        new_anchor_sha256=new_anchor_sha256,
        approved_by=approved_by,
        approved_at=approved_at,
        reason=reason,
        approval_evidence=approval_evidence,
        highest_exposure_by_match_before=dict(anchor.highest_exposure_by_match),
        highest_exposure_by_match_after=dict(highest_after),
    )
    new_root = replace(
        trust_root,
        anchor_sha256=new_anchor_sha256,
        reseals=(*trust_root.reseals, record),
    )
    _write_json_atomic(Path(trust_root_path), new_root.to_dict())
    return ExposureSealResult(
        anchor_path=Path(anchor_path),
        anchor_sha256=new_anchor_sha256,
        trust_root_path=Path(trust_root_path),
        trust_root_sha256=sha256_file(trust_root_path),
    )


def canonical_path_identity(path: str | os.PathLike[str]) -> tuple[str, str]:
    resolved = Path(path).resolve()
    logical = resolved
    for parent in (resolved.parent, *resolved.parents):
        if (parent / ".git").exists():
            logical = resolved.relative_to(parent)
            break
    text = logical.as_posix()
    return text, hashlib.sha256(text.encode()).hexdigest()


def sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise PolicyError(f"could not hash exposure object: {path}") from error
    return digest.hexdigest()


def _parse_record(raw: Any) -> ExposureRecord:
    required = {
        "match_id",
        "provider",
        "source_revision",
        "exposure_level",
        "evidence",
        "recorded_at",
        "recorded_by",
        "notes",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise PolicyError("exposure record has missing or unknown fields")
    try:
        level = ExposureLevel(raw["exposure_level"])
    except (TypeError, ValueError) as error:
        raise PolicyError("exposure record has an invalid level") from error
    evidence = _string_tuple(raw["evidence"], "exposure evidence", nonempty=True)
    for field in ("match_id", "provider", "source_revision", "recorded_at", "recorded_by"):
        _require_nonempty_string(raw[field], f"exposure record {field}")
    if not isinstance(raw["notes"], str):
        raise PolicyError("exposure record notes must be a string")
    _require_timezone_timestamp(raw["recorded_at"], "exposure recorded_at")
    return ExposureRecord(
        match_id=raw["match_id"],
        provider=raw["provider"],
        source_revision=raw["source_revision"],
        exposure_level=level,
        evidence=evidence,
        recorded_at=raw["recorded_at"],
        recorded_by=raw["recorded_by"],
        notes=raw["notes"],
    )


def _parse_reseal(raw: Any) -> ResealRecord:
    required = {
        "reseal_id",
        "old_register_sha256",
        "new_register_sha256",
        "old_anchor_sha256",
        "new_anchor_sha256",
        "approved_by",
        "approved_at",
        "reason",
        "approval_evidence",
        "highest_exposure_by_match_before",
        "highest_exposure_by_match_after",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise PolicyError("exposure reseal record has missing or unknown fields")
    for field in ("reseal_id", "approved_by", "approved_at", "reason"):
        _require_nonempty_string(raw[field], f"exposure reseal {field}")
    _require_timezone_timestamp(raw["approved_at"], "exposure reseal approved_at")
    for field in (
        "old_register_sha256",
        "new_register_sha256",
        "old_anchor_sha256",
        "new_anchor_sha256",
    ):
        _require_sha256(raw[field], f"exposure reseal {field}")
    evidence = _string_tuple(raw["approval_evidence"], "reseal approval_evidence", nonempty=True)
    before = _parse_level_map(
        raw["highest_exposure_by_match_before"],
        "reseal highest before",
    )
    after = _parse_level_map(
        raw["highest_exposure_by_match_after"],
        "reseal highest after",
    )
    if not set(before) <= set(after):
        raise PolicyError("exposure reseal cannot remove history through high-water maps")
    for match_id, previous in before.items():
        if EXPOSURE_RANK[after[match_id]] < EXPOSURE_RANK[previous]:
            raise PolicyError(f"exposure reseal history lowers match {match_id}")
    return ResealRecord(
        reseal_id=raw["reseal_id"],
        old_register_sha256=raw["old_register_sha256"],
        new_register_sha256=raw["new_register_sha256"],
        old_anchor_sha256=raw["old_anchor_sha256"],
        new_anchor_sha256=raw["new_anchor_sha256"],
        approved_by=raw["approved_by"],
        approved_at=raw["approved_at"],
        reason=raw["reason"],
        approval_evidence=evidence,
        highest_exposure_by_match_before=before,
        highest_exposure_by_match_after=after,
    )


def _parse_level_map(raw: Any, label: str) -> dict[str, ExposureLevel]:
    if not isinstance(raw, dict):
        raise PolicyError(f"{label} must be an object")
    output: dict[str, ExposureLevel] = {}
    for match_id, level in raw.items():
        _require_nonempty_string(match_id, f"{label} match ID")
        try:
            output[match_id] = ExposureLevel(level)
        except (TypeError, ValueError) as error:
            raise PolicyError(f"{label} contains an invalid exposure level") from error
    return output


def _parse_identity_map(raw: Any) -> dict[str, dict[str, str]]:
    if not isinstance(raw, dict):
        raise PolicyError("exposure source identity map must be an object")
    output: dict[str, dict[str, str]] = {}
    for match_id, identity in raw.items():
        if not isinstance(identity, dict) or set(identity) != {
            "provider",
            "source_revision",
        }:
            raise PolicyError("exposure source identity record is invalid")
        _require_nonempty_string(identity["provider"], "exposure history provider")
        _require_nonempty_string(
            identity["source_revision"],
            "exposure history source revision",
        )
        output[match_id] = {
            "provider": identity["provider"],
            "source_revision": identity["source_revision"],
        }
    return output


def _load_json_object(path: str | os.PathLike[str], label: str) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyError(f"could not read {label}: {path}") from error
    if not isinstance(raw, dict):
        raise PolicyError(f"{label} root must be an object")
    return raw


def _write_json_atomic(path: Path, values: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(values, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _string_tuple(value: Any, label: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not all(isinstance(item, str) and item for item in value)
        or (nonempty and not value)
    ):
        raise PolicyError(f"{label} must be a {'non-empty ' if nonempty else ''}string list")
    return tuple(value)


def _require_nonempty_string(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f"{label} is required")


def _require_timezone_timestamp(value: Any, label: str) -> None:
    _require_nonempty_string(value, label)
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise PolicyError(f"{label} is invalid") from error
    if parsed.tzinfo is None:
        raise PolicyError(f"{label} must include a timezone")


def _require_sha256(value: Any, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PolicyError(f"{label} is invalid")
