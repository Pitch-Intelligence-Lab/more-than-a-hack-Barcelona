"""Machine-readable historical exposure register for Holdout eligibility."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
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

    def for_holdout(
        self,
        *,
        provider: str,
        source_revision: str,
        match_ids: tuple[str, ...],
    ) -> tuple[ExposureRecord, ...]:
        if not match_ids:
            return ()
        by_match = {record.match_id: record for record in self.records}
        missing = sorted(set(match_ids).difference(by_match))
        if missing:
            raise PolicyError(f"Holdout exposure history is missing for matches: {missing}")
        selected = tuple(by_match[match_id] for match_id in sorted(set(match_ids)))
        for record in selected:
            if record.provider != provider or record.source_revision != source_revision:
                raise PolicyError(f"Holdout exposure identity mismatch for match {record.match_id}")
            if record.exposure_level not in HOLDOUT_ELIGIBLE_LEVELS:
                raise PolicyError(
                    f"historically exposed match {record.match_id} cannot become Holdout: "
                    f"{record.exposure_level.value}"
                )
        return selected


def load_exposure_register(path: str | os.PathLike[str]) -> ExposureRegister:
    register_path = Path(path)
    try:
        raw = json.loads(register_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyError(f"could not read exposure register: {register_path}") from error
    required = {"schema_version", "status", "missing_record_policy", "records"}
    if not isinstance(raw, dict) or set(raw) != required:
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
    evidence = raw["evidence"]
    if (
        not isinstance(evidence, list)
        or not evidence
        or not all(isinstance(item, str) and item.strip() for item in evidence)
    ):
        raise PolicyError("exposure record evidence must be a non-empty string list")
    for field in ("match_id", "provider", "source_revision", "recorded_at", "recorded_by"):
        if not isinstance(raw[field], str) or not raw[field].strip():
            raise PolicyError(f"exposure record field {field} is invalid")
    if not isinstance(raw["notes"], str):
        raise PolicyError("exposure record notes must be a string")
    try:
        recorded_at = datetime.fromisoformat(raw["recorded_at"])
    except (TypeError, ValueError) as error:
        raise PolicyError("exposure record timestamp is invalid") from error
    if recorded_at.tzinfo is None:
        raise PolicyError("exposure record timestamp must include a timezone")
    return ExposureRecord(
        match_id=raw["match_id"],
        provider=raw["provider"],
        source_revision=raw["source_revision"],
        exposure_level=level,
        evidence=tuple(evidence),
        recorded_at=raw["recorded_at"],
        recorded_by=raw["recorded_by"],
        notes=raw["notes"],
    )
