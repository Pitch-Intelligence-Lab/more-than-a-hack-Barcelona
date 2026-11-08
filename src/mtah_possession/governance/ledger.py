"""Append-only, stateful holdout lifecycle ledger."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from mtah_possession.governance.holdout import FreezeHashes
from mtah_possession.governance.policy import PolicyError


class LedgerEvent(StrEnum):
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    SEALED_VERIFIED = "SEALED_VERIFIED"
    UNSEALED = "UNSEALED"
    EVALUATION_STARTED = "EVALUATION_STARTED"
    EVALUATION_COMPLETED = "EVALUATION_COMPLETED"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    COMPROMISED = "COMPROMISED"


class HoldoutLedgerState(StrEnum):
    SEALED = "SEALED"
    UNSEALED = "UNSEALED"
    EVALUATION_RUNNING = "EVALUATION_RUNNING"
    EVALUATION_COMPLETED = "EVALUATION_COMPLETED"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    COMPROMISED = "COMPROMISED"


RECORD_FIELDS = frozenset(
    {
        "recorded_at",
        "event_type",
        "provider",
        "holdout_id",
        "match_ids",
        "freeze_hashes",
        "holdout_manifest_sha256",
        "code_commit",
        "prediction_sha256",
        "previous_record_sha256",
        "reason",
    }
)


@dataclass(frozen=True)
class HoldoutLedger:
    path: Path
    provider: str
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
            "provider": self.provider,
            "holdout_id": self.holdout_id,
            "match_ids": list(self.match_ids),
            "freeze_hashes": _freeze_dict(self.freeze_hashes),
            "holdout_manifest_sha256": self.holdout_manifest_sha256,
            "code_commit": self.code_commit,
            "prediction_sha256": prediction_sha256,
            "previous_record_sha256": previous,
            "reason": reason,
        }
        _validate_record(
            record,
            provider=self.provider,
            holdout_id=self.holdout_id,
            match_ids=self.match_ids,
            previous_hash=previous,
        )
        reduce_holdout_state((*existing, record))
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
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise PolicyError(f"holdout ledger record {line_number} must be an object")
                    _validate_record(
                        record,
                        provider=self.provider,
                        holdout_id=self.holdout_id,
                        match_ids=self.match_ids,
                        previous_hash=previous_hash,
                    )
                    records.append(record)
                    previous_hash = _record_sha256(record)
        except (OSError, json.JSONDecodeError) as error:
            raise PolicyError(f"could not read holdout ledger at {self.path}") from error
        reduce_holdout_state(records)
        return records

    @property
    def state(self) -> HoldoutLedgerState:
        return reduce_holdout_state(self.records())

    @property
    def status(self) -> str:
        return self.state.value

    def has_event(self, event_type: LedgerEvent) -> bool:
        return any(record["event_type"] == event_type.value for record in self.records())

    def lifecycle_freeze_hashes(self) -> FreezeHashes | None:
        for record in self.records():
            if record["event_type"] in {
                LedgerEvent.SEALED_VERIFIED.value,
                LedgerEvent.UNSEALED.value,
                LedgerEvent.EVALUATION_STARTED.value,
                LedgerEvent.EVALUATION_COMPLETED.value,
                LedgerEvent.EVALUATION_FAILED.value,
            }:
                return _freeze_from_record(record)
        return None


def reduce_holdout_state(
    records: Sequence[Mapping[str, Any]],
) -> HoldoutLedgerState:
    """Derive lifecycle state from validated event order."""
    state = HoldoutLedgerState.SEALED
    sealed_verified = False
    for record in records:
        try:
            event = LedgerEvent(record["event_type"])
        except (KeyError, TypeError, ValueError) as error:
            raise PolicyError("holdout ledger event type is invalid") from error
        if event == LedgerEvent.AUTHORIZATION_DENIED:
            if state == HoldoutLedgerState.COMPROMISED:
                raise PolicyError("holdout ledger has events after COMPROMISED")
            continue
        if event == LedgerEvent.COMPROMISED:
            if state == HoldoutLedgerState.COMPROMISED:
                raise PolicyError("holdout ledger has duplicate terminal state")
            state = HoldoutLedgerState.COMPROMISED
            continue
        if state == HoldoutLedgerState.COMPROMISED:
            raise PolicyError("holdout ledger has events after COMPROMISED")
        if event == LedgerEvent.SEALED_VERIFIED:
            if state != HoldoutLedgerState.SEALED or sealed_verified:
                raise PolicyError("holdout ledger has an invalid SEALED_VERIFIED transition")
            sealed_verified = True
        elif event == LedgerEvent.UNSEALED:
            if state != HoldoutLedgerState.SEALED or not sealed_verified:
                raise PolicyError("holdout ledger has an invalid UNSEALED transition")
            state = HoldoutLedgerState.UNSEALED
        elif event == LedgerEvent.EVALUATION_STARTED:
            if state not in {
                HoldoutLedgerState.UNSEALED,
                HoldoutLedgerState.EVALUATION_FAILED,
            }:
                raise PolicyError("holdout ledger has an invalid EVALUATION_STARTED transition")
            state = HoldoutLedgerState.EVALUATION_RUNNING
        elif event == LedgerEvent.EVALUATION_COMPLETED:
            if state != HoldoutLedgerState.EVALUATION_RUNNING:
                raise PolicyError("holdout ledger has an invalid EVALUATION_COMPLETED transition")
            state = HoldoutLedgerState.EVALUATION_COMPLETED
        elif event == LedgerEvent.EVALUATION_FAILED:
            if state != HoldoutLedgerState.EVALUATION_RUNNING:
                raise PolicyError("holdout ledger has an invalid EVALUATION_FAILED transition")
            state = HoldoutLedgerState.EVALUATION_FAILED
    return state


def create_ledger(
    ledger_dir: str | os.PathLike[str],
    *,
    provider: str,
    match_ids: tuple[str, ...],
    freeze_hashes: FreezeHashes,
    holdout_manifest_sha256: str,
    code_commit: str,
) -> HoldoutLedger:
    normalized_provider, normalized_matches, holdout_id = stable_holdout_identity(
        provider,
        match_ids,
    )
    directory = Path(ledger_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{holdout_id}.jsonl"
    ledger = HoldoutLedger(
        path=path,
        provider=normalized_provider,
        holdout_id=holdout_id,
        match_ids=normalized_matches,
        freeze_hashes=freeze_hashes,
        holdout_manifest_sha256=holdout_manifest_sha256,
        code_commit=code_commit,
    )
    try:
        with path.open("a", encoding="utf-8"):
            pass
    except OSError as error:
        raise PolicyError(f"holdout ledger is not writable: {path}") from error
    return ledger


def load_existing_ledger(
    ledger_dir: str | os.PathLike[str],
    *,
    provider: str,
    match_ids: tuple[str, ...],
) -> HoldoutLedger:
    normalized_provider, normalized_matches, holdout_id = stable_holdout_identity(
        provider,
        match_ids,
    )
    path = Path(ledger_dir) / f"{holdout_id}.jsonl"
    if not path.exists():
        raise PolicyError("holdout ledger does not exist")
    placeholder = FreezeHashes("", "", "", "", "", "")
    ledger = HoldoutLedger(
        path=path,
        provider=normalized_provider,
        holdout_id=holdout_id,
        match_ids=normalized_matches,
        freeze_hashes=placeholder,
        holdout_manifest_sha256="",
        code_commit="",
    )
    records = ledger.records()
    if not records:
        raise PolicyError("holdout ledger is empty")
    last = records[-1]
    return HoldoutLedger(
        path=path,
        provider=normalized_provider,
        holdout_id=holdout_id,
        match_ids=normalized_matches,
        freeze_hashes=_freeze_from_record(last),
        holdout_manifest_sha256=str(last["holdout_manifest_sha256"]),
        code_commit=str(last["code_commit"]),
    )


def mark_holdout_used_for_tuning(
    ledger_dir: str | os.PathLike[str],
    *,
    provider: str,
    match_ids: tuple[str, ...],
    prediction_sha256: str,
    reason: str,
) -> HoldoutLedger:
    if not prediction_sha256.strip():
        raise PolicyError("prediction SHA-256 is required")
    if not reason.strip():
        raise PolicyError("tuning contamination reason is required")
    ledger = load_existing_ledger(
        ledger_dir,
        provider=provider,
        match_ids=match_ids,
    )
    if ledger.state != HoldoutLedgerState.EVALUATION_COMPLETED:
        raise PolicyError("only a completed holdout evaluation can be marked for tuning")
    completed = [
        record
        for record in ledger.records()
        if record["event_type"] == LedgerEvent.EVALUATION_COMPLETED.value
    ]
    if not completed or completed[-1]["prediction_sha256"] != prediction_sha256:
        raise PolicyError("prediction SHA-256 does not match the completed evaluation")
    ledger.append(
        LedgerEvent.COMPROMISED,
        prediction_sha256=prediction_sha256,
        reason=reason,
    )
    return ledger


def stable_holdout_identity(
    provider: str,
    match_ids: tuple[str, ...],
) -> tuple[str, tuple[str, ...], str]:
    normalized_provider = provider.strip().lower()
    if not normalized_provider:
        raise PolicyError("holdout provider is required")
    if not all(isinstance(match_id, str) and match_id for match_id in match_ids):
        raise PolicyError("holdout match IDs must be non-empty strings")
    normalized_matches = tuple(sorted(set(match_ids)))
    payload = json.dumps(
        {
            "provider": normalized_provider,
            "match_ids": list(normalized_matches),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    digest = hashlib.sha256(payload).hexdigest()
    return normalized_provider, normalized_matches, f"holdout-{digest[:24]}"


def _validate_record(
    record: Mapping[str, Any],
    *,
    provider: str,
    holdout_id: str,
    match_ids: tuple[str, ...],
    previous_hash: str | None,
) -> None:
    if set(record) != RECORD_FIELDS:
        raise PolicyError("holdout ledger record has missing or unknown fields")
    try:
        event = LedgerEvent(record["event_type"])
    except (TypeError, ValueError) as error:
        raise PolicyError("holdout ledger event type is invalid") from error
    if record["provider"] != provider:
        raise PolicyError("holdout ledger provider does not match stable identity")
    if record["holdout_id"] != holdout_id:
        raise PolicyError("holdout ledger ID does not match stable identity")
    if record["match_ids"] != list(match_ids):
        raise PolicyError("holdout ledger match set does not match stable identity")
    if record["previous_record_sha256"] != previous_hash:
        raise PolicyError("holdout ledger hash chain is broken")
    if not isinstance(record["recorded_at"], str) or not record["recorded_at"]:
        raise PolicyError("holdout ledger timestamp is missing")
    _validate_sha256(record["holdout_manifest_sha256"], "holdout manifest SHA-256")
    if not isinstance(record["code_commit"], str) or len(record["code_commit"].strip()) < 7:
        raise PolicyError("holdout ledger code commit is invalid")
    freeze = record["freeze_hashes"]
    if not isinstance(freeze, dict) or set(freeze) != {
        "model",
        "feature_set",
        "configuration",
        "hyperparameters",
        "evaluation_script",
        "metric_contract_version",
    }:
        raise PolicyError("holdout ledger freeze identity is invalid")
    if not all(isinstance(value, str) and value.strip() for value in freeze.values()):
        raise PolicyError("holdout ledger freeze identity is incomplete")
    prediction = record["prediction_sha256"]
    if prediction is not None:
        _validate_sha256(prediction, "prediction SHA-256")
    reason = record["reason"]
    if reason is not None and not isinstance(reason, str):
        raise PolicyError("holdout ledger reason is invalid")
    if event in {LedgerEvent.AUTHORIZATION_DENIED, LedgerEvent.COMPROMISED} and not (
        isinstance(reason, str) and reason.strip()
    ):
        raise PolicyError(f"holdout ledger {event.value} event requires a reason")
    if event == LedgerEvent.EVALUATION_COMPLETED and prediction is None:
        raise PolicyError("holdout ledger completed event requires a prediction SHA-256")


def _freeze_dict(freeze: FreezeHashes) -> dict[str, str]:
    return {
        "model": freeze.model,
        "feature_set": freeze.feature_set,
        "configuration": freeze.configuration,
        "hyperparameters": freeze.hyperparameters,
        "evaluation_script": freeze.evaluation_script,
        "metric_contract_version": freeze.metric_contract_version,
    }


def _freeze_from_record(record: Mapping[str, Any]) -> FreezeHashes:
    freeze = record.get("freeze_hashes")
    if not isinstance(freeze, dict):
        raise PolicyError("holdout ledger freeze identity is invalid")
    try:
        return FreezeHashes(
            model=str(freeze["model"]),
            feature_set=str(freeze["feature_set"]),
            configuration=str(freeze["configuration"]),
            hyperparameters=str(freeze["hyperparameters"]),
            evaluation_script=str(freeze["evaluation_script"]),
            metric_contract_version=str(freeze["metric_contract_version"]),
        )
    except KeyError as error:
        raise PolicyError("holdout ledger freeze identity is incomplete") from error


def _validate_sha256(value: Any, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PolicyError(f"{label} is invalid")


def _record_sha256(record: Mapping[str, Any]) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
