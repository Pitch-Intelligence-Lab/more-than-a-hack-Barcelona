"""Append-only holdout lifecycle ledger."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from mtah_possession.governance.holdout import FreezeHashes
from mtah_possession.governance.policy import PolicyError


class LedgerEvent(StrEnum):
    SEALED_VERIFIED = "SEALED_VERIFIED"
    UNSEALED = "UNSEALED"
    EVALUATION_STARTED = "EVALUATION_STARTED"
    EVALUATION_COMPLETED = "EVALUATION_COMPLETED"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    COMPROMISED = "COMPROMISED"


@dataclass(frozen=True)
class HoldoutLedger:
    path: Path
    holdout_id: str
    match_ids: tuple[str, ...]
    freeze_hashes: FreezeHashes
    holdout_manifest_sha256: str
    code_commit: str

    def append(
        self,
        event_type: LedgerEvent,
        *,
        prediction_sha256: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        existing = self.records()
        previous = _record_sha256(existing[-1]) if existing else None
        record = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "event_type": event_type.value,
            "holdout_id": self.holdout_id,
            "match_ids": list(self.match_ids),
            "freeze_hashes": {
                "model": self.freeze_hashes.model,
                "feature_set": self.freeze_hashes.feature_set,
                "configuration": self.freeze_hashes.configuration,
                "hyperparameters": self.freeze_hashes.hyperparameters,
                "evaluation_script": self.freeze_hashes.evaluation_script,
                "metric_contract_version": self.freeze_hashes.metric_contract_version,
            },
            "holdout_manifest_sha256": self.holdout_manifest_sha256,
            "code_commit": self.code_commit,
            "prediction_sha256": prediction_sha256,
            "previous_record_sha256": previous,
            "reason": reason,
        }
        line = json.dumps(record, sort_keys=True, separators=(",", ":"))
        try:
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as error:
            raise PolicyError(f"could not append holdout ledger at {self.path}") from error
        return record

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        previous_hash: str | None = None
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    if record.get("previous_record_sha256") != previous_hash:
                        raise PolicyError("holdout ledger hash chain is broken")
                    records.append(record)
                    previous_hash = _record_sha256(record)
        except (OSError, json.JSONDecodeError) as error:
            raise PolicyError(f"could not read holdout ledger at {self.path}") from error
        return records

    @property
    def status(self) -> str:
        records = self.records()
        return str(records[-1]["event_type"]) if records else "unassigned"


def create_ledger(
    ledger_dir: str | os.PathLike[str],
    *,
    match_ids: tuple[str, ...],
    freeze_hashes: FreezeHashes,
    holdout_manifest_sha256: str,
    code_commit: str,
) -> HoldoutLedger:
    directory = Path(ledger_dir)
    directory.mkdir(parents=True, exist_ok=True)
    holdout_key = hashlib.sha256(
        f"{holdout_manifest_sha256}:{','.join(sorted(match_ids))}".encode()
    ).hexdigest()[:16]
    path = directory / f"{holdout_key}.jsonl"
    ledger = HoldoutLedger(
        path=path,
        holdout_id=f"holdout-{holdout_key}",
        match_ids=tuple(sorted(match_ids)),
        freeze_hashes=freeze_hashes,
        holdout_manifest_sha256=holdout_manifest_sha256,
        code_commit=code_commit,
    )
    # Prove the directory is writable before an external loader is invoked.
    try:
        with path.open("a", encoding="utf-8"):
            pass
    except OSError as error:
        raise PolicyError(f"holdout ledger is not writable: {path}") from error
    return ledger


def _record_sha256(record: dict[str, Any]) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
