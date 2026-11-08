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

from mtah_possession.governance.authorization import (
    GovernanceAuthorizationIdentity,
    governance_identity_from_dict,
)
from mtah_possession.governance.holdout import FreezeHashes
from mtah_possession.governance.migration import (
    MIGRATION_RECEIPT_FIELDS,
    load_verified_migration_receipt,
    validate_migration_receipt,
)
from mtah_possession.governance.policy import PolicyError


class LedgerEvent(StrEnum):
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    SEALED_VERIFIED = "SEALED_VERIFIED"
    UNSEALED = "UNSEALED"
    EVALUATION_STARTED = "EVALUATION_STARTED"
    EVALUATION_COMPLETED = "EVALUATION_COMPLETED"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    COMPROMISED = "COMPROMISED"
    FREEZE_PROTOCOL_MIGRATED = "FREEZE_PROTOCOL_MIGRATED"


class HoldoutLedgerState(StrEnum):
    SEALED = "SEALED"
    UNSEALED = "UNSEALED"
    EVALUATION_RUNNING = "EVALUATION_RUNNING"
    EVALUATION_COMPLETED = "EVALUATION_COMPLETED"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    COMPROMISED = "COMPROMISED"
    MIGRATED_AUDIT_ONLY = "MIGRATED_AUDIT_ONLY"


LEGACY_RECORD_FIELDS = frozenset(
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
V2_RECORD_FIELDS = LEGACY_RECORD_FIELDS | {"governance_identity"}
V3_RECORD_FIELDS = V2_RECORD_FIELDS | {
    "freeze_protocol_version",
    "holdout_manifest_path_sha256",
    "split_manifest_sha256",
}
MIGRATION_RECORD_FIELDS = V3_RECORD_FIELDS | {"migration_receipt"}
LEGACY_FREEZE_PROTOCOL_VERSION = "combined-policy-model-v1"
PRE_SPLIT_FREEZE_PROTOCOL_VERSION = "model-governance-separated-v2"
SEAL_BOUND_FREEZE_PROTOCOL_VERSION = "seal-bound-evaluation-v3"
MIGRATION_RULE_VERSION = "1.0"
_LIFECYCLE_FREEZE_EVENTS = {
    LedgerEvent.SEALED_VERIFIED.value,
    LedgerEvent.UNSEALED.value,
    LedgerEvent.EVALUATION_STARTED.value,
    LedgerEvent.EVALUATION_COMPLETED.value,
    LedgerEvent.EVALUATION_FAILED.value,
}


@dataclass(frozen=True)
class HoldoutLedger:
    path: Path
    provider: str
    holdout_id: str
    match_ids: tuple[str, ...]
    freeze_hashes: FreezeHashes
    holdout_manifest_sha256: str
    holdout_manifest_path_sha256: str | None
    split_manifest_sha256: str | None
    code_commit: str
    governance_identity: GovernanceAuthorizationIdentity | None = None

    def append(
        self,
        event_type: LedgerEvent,
        *,
        prediction_sha256: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        if self.governance_identity is None:
            raise PolicyError("holdout ledger append requires a governance identity")
        if self.split_manifest_sha256 is None:
            raise PolicyError("holdout ledger append requires a split manifest SHA-256")
        if self.holdout_manifest_path_sha256 is None:
            raise PolicyError("holdout ledger append requires a Manifest path SHA-256")
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
            "governance_identity": self.governance_identity.to_dict(),
            "freeze_protocol_version": SEAL_BOUND_FREEZE_PROTOCOL_VERSION,
            "holdout_manifest_path_sha256": self.holdout_manifest_path_sha256,
            "split_manifest_sha256": self.split_manifest_sha256,
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

    def append_freeze_migration(
        self,
        *,
        migration_receipt: Mapping[str, Any],
    ) -> dict[str, Any]:
        if self.governance_identity is None:
            raise PolicyError("freeze migration requires a governance identity")
        if set(migration_receipt) != MIGRATION_RECEIPT_FIELDS:
            raise PolicyError("migration receipt has missing or unknown fields")
        if (
            migration_receipt["status"] != "MIGRATED_AUDIT_ONLY"
            or migration_receipt["promotion_authorized"] is not False
        ):
            raise PolicyError("migration receipt must be audit-only")
        records = self.records()
        if not records:
            raise PolicyError("legacy holdout ledger is empty")
        if self.state == HoldoutLedgerState.COMPROMISED:
            raise PolicyError("COMPROMISED holdout ledger cannot be migrated")
        if any(_ledger_record_kind(record) != "legacy" for record in records):
            raise PolicyError("holdout ledger is already on a newer freeze protocol")
        previous = _record_sha256(records[-1])
        if migration_receipt["previous_record_sha256"] != previous:
            raise PolicyError("migration receipt does not bind the ledger head")
        if migration_receipt["source_provider"] != self.provider:
            raise PolicyError("migration receipt provider does not match ledger")
        if migration_receipt["source_holdout_id"] != self.holdout_id:
            raise PolicyError("migration receipt Holdout ID does not match ledger")
        if migration_receipt["source_match_ids"] != list(self.match_ids):
            raise PolicyError("migration receipt match set does not match ledger")
        record = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "event_type": LedgerEvent.FREEZE_PROTOCOL_MIGRATED.value,
            "provider": self.provider,
            "holdout_id": self.holdout_id,
            "match_ids": list(self.match_ids),
            "freeze_hashes": _freeze_dict(self.freeze_hashes),
            "holdout_manifest_sha256": migration_receipt["old_holdout_manifest_sha256"],
            "holdout_manifest_path_sha256": self.holdout_manifest_path_sha256,
            "split_manifest_sha256": migration_receipt["target_split_manifest_sha256"],
            "freeze_protocol_version": SEAL_BOUND_FREEZE_PROTOCOL_VERSION,
            "code_commit": migration_receipt["migration_commit"],
            "prediction_sha256": None,
            "previous_record_sha256": previous,
            "reason": migration_receipt["reason"],
            "governance_identity": self.governance_identity.to_dict(),
            "migration_receipt": dict(migration_receipt),
        }
        _validate_record(
            record,
            provider=self.provider,
            holdout_id=self.holdout_id,
            match_ids=self.match_ids,
            previous_hash=previous,
        )
        reduce_holdout_state((*records, record))
        _append_json_record(self.path, record)
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
        _validate_protocol_sequence(records)
        _validate_seal_immutability(records)
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

    def has_migration_event(self) -> bool:
        return self.has_event(LedgerEvent.FREEZE_PROTOCOL_MIGRATED)

    @property
    def requires_freeze_migration(self) -> bool:
        records = self.records()
        return (
            bool(records)
            and _ledger_record_kind(records[0]) == "legacy"
            and (not self.has_migration_event())
        )

    @property
    def requires_split_protocol_reseal(self) -> bool:
        records = self.records()
        return bool(records) and _ledger_record_kind(records[0]) == "v2"

    def sealed_manifest_sha256(self) -> str | None:
        for record in self.records():
            if record["event_type"] == LedgerEvent.SEALED_VERIFIED.value:
                return str(record["holdout_manifest_sha256"])
        return None

    def sealed_split_manifest_sha256(self) -> str | None:
        for record in self.records():
            if (
                record["event_type"] == LedgerEvent.SEALED_VERIFIED.value
                and _ledger_record_kind(record) == "v3"
            ):
                return str(record["split_manifest_sha256"])
        return None

    def sealed_manifest_path_sha256(self) -> str | None:
        for record in self.records():
            if (
                record["event_type"] == LedgerEvent.SEALED_VERIFIED.value
                and _ledger_record_kind(record) == "v3"
            ):
                return str(record["holdout_manifest_path_sha256"])
        return None

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

    def model_freeze_hashes(self) -> FreezeHashes | None:
        records = self.records()
        for record in reversed(records):
            if record["event_type"] == LedgerEvent.FREEZE_PROTOCOL_MIGRATED.value:
                return _freeze_from_record(record)
            if _ledger_record_kind(record) == "v3":
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
        if event == LedgerEvent.FREEZE_PROTOCOL_MIGRATED:
            if state == HoldoutLedgerState.COMPROMISED:
                raise PolicyError("holdout ledger has migration after COMPROMISED")
            state = HoldoutLedgerState.MIGRATED_AUDIT_ONLY
            continue
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
        if state == HoldoutLedgerState.MIGRATED_AUDIT_ONLY:
            raise PolicyError("migrated audit-only ledger cannot re-enter Promotion")
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
    holdout_manifest_path_sha256: str,
    split_manifest_sha256: str,
    code_commit: str,
    governance_identity: GovernanceAuthorizationIdentity | None = None,
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
        holdout_manifest_path_sha256=holdout_manifest_path_sha256,
        split_manifest_sha256=split_manifest_sha256,
        code_commit=code_commit,
        governance_identity=governance_identity,
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
        holdout_manifest_path_sha256=None,
        split_manifest_sha256=None,
        code_commit="",
    )
    records = ledger.records()
    if not records:
        raise PolicyError("holdout ledger is empty")
    last = records[-1]
    identity = (
        governance_identity_from_dict(last["governance_identity"])
        if _ledger_record_kind(last) != "legacy"
        else None
    )
    return HoldoutLedger(
        path=path,
        provider=normalized_provider,
        holdout_id=holdout_id,
        match_ids=normalized_matches,
        freeze_hashes=(
            _freeze_from_mapping(last["new_model_freeze"])
            if last["event_type"] == LedgerEvent.FREEZE_PROTOCOL_MIGRATED.value
            else _freeze_from_record(last)
        ),
        holdout_manifest_sha256=str(last["holdout_manifest_sha256"]),
        holdout_manifest_path_sha256=(
            str(last["holdout_manifest_path_sha256"])
            if _ledger_record_kind(last) in {"v3", "migration"}
            else None
        ),
        split_manifest_sha256=(
            str(last["split_manifest_sha256"])
            if _ledger_record_kind(last) in {"v3", "migration"}
            else None
        ),
        code_commit=str(last["code_commit"]),
        governance_identity=identity,
    )


def migrate_legacy_ledger(
    ledger_dir: str | os.PathLike[str],
    *,
    repo_root: str | os.PathLike[str],
    provider: str,
    match_ids: tuple[str, ...],
    model_freeze: FreezeHashes,
    governance_identity: GovernanceAuthorizationIdentity,
    holdout_manifest_sha256: str,
    holdout_manifest_path_sha256: str,
    target_holdout_manifest_sha256: str,
    split_manifest_sha256: str,
    freeze_spec_sha256: str,
    policy_sha256: str,
    approval_receipt_path: str | os.PathLike[str],
    approval_commit: str,
    migration_commit: str,
) -> HoldoutLedger:
    existing = load_existing_ledger(
        ledger_dir,
        provider=provider,
        match_ids=match_ids,
    )
    if existing.state == HoldoutLedgerState.COMPROMISED:
        raise PolicyError("COMPROMISED holdout ledger cannot be migrated")
    raw_ledger = existing.path.read_bytes()
    source_ledger_head_sha256 = hashlib.sha256(raw_ledger).hexdigest()
    records = existing.records()
    lifecycle_records = [
        record for record in records if record["event_type"] in _LIFECYCLE_FREEZE_EVENTS
    ]
    if not lifecycle_records:
        raise PolicyError("legacy ledger has no frozen lifecycle event")
    legacy_freezes = {_canonical_json(record["freeze_hashes"]) for record in lifecycle_records}
    if len(legacy_freezes) != 1:
        raise PolicyError("legacy combined freeze identity is inconsistent")
    legacy_freeze = lifecycle_records[-1]["freeze_hashes"]
    old_code_commit = str(records[-1]["code_commit"])
    previous_record_sha256 = _record_sha256(records[-1])
    target_model_identity = {
        "model": model_freeze.model,
        "feature_set": model_freeze.feature_set,
        "configuration": model_freeze.configuration,
        "hyperparameters": model_freeze.hyperparameters,
    }
    target_evaluation_identity = {
        "evaluation_script": model_freeze.evaluation_script,
        "metric_contract_version": model_freeze.metric_contract_version,
    }
    receipt = load_verified_migration_receipt(
        repo_root=repo_root,
        approval_commit=approval_commit,
        migration_commit=migration_commit,
        receipt_path=approval_receipt_path,
        expected={
            "status": "MIGRATED_AUDIT_ONLY",
            "promotion_authorized": False,
            "source_provider": existing.provider,
            "source_holdout_id": existing.holdout_id,
            "source_match_ids": list(existing.match_ids),
            "source_protocol_version": LEGACY_FREEZE_PROTOCOL_VERSION,
            "source_ledger_head_sha256": source_ledger_head_sha256,
            "legacy_combined_freeze": legacy_freeze,
            "old_code_commit": old_code_commit,
            "migration_commit": migration_commit,
            "model_freeze_spec_sha256": freeze_spec_sha256,
            "evaluation_freeze_spec_sha256": freeze_spec_sha256,
            "policy_sha256": policy_sha256,
            "old_holdout_manifest_sha256": holdout_manifest_sha256,
            "target_model_identity": target_model_identity,
            "target_evaluation_identity": target_evaluation_identity,
            "target_split_manifest_sha256": split_manifest_sha256,
            "target_holdout_manifest_sha256": target_holdout_manifest_sha256,
            "governance_identity_digest": (governance_identity.authorization_status_digest),
            "previous_record_sha256": previous_record_sha256,
        },
    )
    ledger = HoldoutLedger(
        path=existing.path,
        provider=existing.provider,
        holdout_id=existing.holdout_id,
        match_ids=existing.match_ids,
        freeze_hashes=model_freeze,
        holdout_manifest_sha256=target_holdout_manifest_sha256,
        holdout_manifest_path_sha256=holdout_manifest_path_sha256,
        split_manifest_sha256=split_manifest_sha256,
        code_commit=migration_commit,
        governance_identity=governance_identity,
    )
    ledger.append_freeze_migration(migration_receipt=receipt)
    return ledger


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


def sha256_path_identity(path: str | os.PathLike[str]) -> str:
    resolved = Path(path).resolve(strict=True)
    return hashlib.sha256(resolved.as_posix().encode("utf-8")).hexdigest()


def manifest_path_has_conflicting_identity(
    ledger_dir: str | os.PathLike[str],
    *,
    provider: str,
    match_ids: tuple[str, ...],
    manifest_path_sha256: str,
) -> bool:
    normalized_provider, normalized_matches, holdout_id = stable_holdout_identity(
        provider,
        match_ids,
    )
    directory = Path(ledger_dir)
    if not directory.exists():
        return False
    for path in sorted(directory.glob("*.jsonl")):
        try:
            raw_records = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, json.JSONDecodeError):
            continue
        matching = [
            record
            for record in raw_records
            if isinstance(record, dict)
            and record.get("holdout_manifest_path_sha256") == manifest_path_sha256
        ]
        if not matching:
            continue
        first = matching[0]
        if (
            first.get("provider") != normalized_provider
            or first.get("holdout_id") != holdout_id
            or first.get("match_ids") != list(normalized_matches)
        ):
            return True
    return False


def _validate_record(
    record: Mapping[str, Any],
    *,
    provider: str,
    holdout_id: str,
    match_ids: tuple[str, ...],
    previous_hash: str | None,
) -> None:
    kind = _ledger_record_kind(record)
    if kind == "legacy" and set(record) != LEGACY_RECORD_FIELDS:
        raise PolicyError("legacy holdout ledger record has invalid fields")
    if kind == "v2" and set(record) != V2_RECORD_FIELDS:
        raise PolicyError("holdout ledger record has missing or unknown fields")
    if kind == "v3" and set(record) != V3_RECORD_FIELDS:
        raise PolicyError("seal-bound ledger record has missing or unknown fields")
    if kind == "migration" and set(record) != MIGRATION_RECORD_FIELDS:
        raise PolicyError("holdout migration record has missing or unknown fields")
    if kind not in {"legacy", "v2", "v3", "migration"}:
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
    _freeze_from_mapping(record["freeze_hashes"])
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
    if event == LedgerEvent.FREEZE_PROTOCOL_MIGRATED and kind != "migration":
        raise PolicyError("FREEZE_PROTOCOL_MIGRATED record is incomplete")
    if kind in {"v3", "migration"}:
        if record["freeze_protocol_version"] != SEAL_BOUND_FREEZE_PROTOCOL_VERSION:
            raise PolicyError("seal-bound freeze protocol version is unsupported")
        _validate_sha256(
            record["holdout_manifest_path_sha256"],
            "Manifest path SHA-256",
        )
        _validate_sha256(record["split_manifest_sha256"], "split manifest SHA-256")
    if kind == "migration":
        if event != LedgerEvent.FREEZE_PROTOCOL_MIGRATED:
            raise PolicyError("migration fields require FREEZE_PROTOCOL_MIGRATED event")
        _validate_migration_record(record)
    if kind != "legacy":
        identity = governance_identity_from_dict(record["governance_identity"])
        if identity.provider != provider:
            raise PolicyError("holdout ledger governance provider mismatch")
        if kind == "migration" and (
            record["migration_receipt"]["governance_identity_digest"]
            != identity.authorization_status_digest
        ):
            raise PolicyError("migration governance identity digest does not match")


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
    return _freeze_from_mapping(record.get("freeze_hashes"))


def _freeze_from_mapping(freeze: Any) -> FreezeHashes:
    required = {
        "model",
        "feature_set",
        "configuration",
        "hyperparameters",
        "evaluation_script",
        "metric_contract_version",
    }
    if not isinstance(freeze, dict) or set(freeze) != required:
        raise PolicyError("holdout ledger freeze identity is invalid")
    if not all(isinstance(value, str) and value.strip() for value in freeze.values()):
        raise PolicyError("holdout ledger freeze identity is incomplete")
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


def _validate_migration_record(record: Mapping[str, Any]) -> None:
    receipt = validate_migration_receipt(record["migration_receipt"])
    if receipt["source_provider"] != record["provider"]:
        raise PolicyError("migration receipt provider does not match record")
    if receipt["source_holdout_id"] != record["holdout_id"]:
        raise PolicyError("migration receipt Holdout ID does not match record")
    if receipt["source_match_ids"] != record["match_ids"]:
        raise PolicyError("migration receipt match set does not match record")
    if receipt["previous_record_sha256"] != record["previous_record_sha256"]:
        raise PolicyError("migration receipt previous hash does not match record")
    if receipt["migration_commit"] != record["code_commit"]:
        raise PolicyError("migration commit does not match event code commit")
    if receipt["old_holdout_manifest_sha256"] != record["holdout_manifest_sha256"]:
        raise PolicyError("migration old Holdout Manifest SHA does not match record")
    if receipt["target_split_manifest_sha256"] != record["split_manifest_sha256"]:
        raise PolicyError("migration split identity does not match record")
    target_model = {
        "model": record["freeze_hashes"]["model"],
        "feature_set": record["freeze_hashes"]["feature_set"],
        "configuration": record["freeze_hashes"]["configuration"],
        "hyperparameters": record["freeze_hashes"]["hyperparameters"],
    }
    if receipt["target_model_identity"] != target_model:
        raise PolicyError("migration target model identity does not match record")
    target_evaluation = {
        "evaluation_script": record["freeze_hashes"]["evaluation_script"],
        "metric_contract_version": record["freeze_hashes"]["metric_contract_version"],
    }
    if receipt["target_evaluation_identity"] != target_evaluation:
        raise PolicyError("migration target evaluation identity does not match record")


def _ledger_record_kind(record: Mapping[str, Any]) -> str:
    fields = set(record)
    if fields == LEGACY_RECORD_FIELDS:
        return "legacy"
    if fields == V2_RECORD_FIELDS:
        return "v2"
    if fields == V3_RECORD_FIELDS:
        return "v3"
    if fields == MIGRATION_RECORD_FIELDS:
        return "migration"
    return "invalid"


def _validate_protocol_sequence(records: Sequence[Mapping[str, Any]]) -> None:
    if not records:
        return
    kinds = [_ledger_record_kind(record) for record in records]
    if any(kind == "invalid" for kind in kinds):
        raise PolicyError("holdout ledger protocol record is invalid")
    if kinds[0] == "v2":
        if any(kind != "v2" for kind in kinds):
            raise PolicyError("native v2 holdout ledger has mixed protocol records")
        return
    if kinds[0] == "v3":
        if any(kind != "v3" for kind in kinds):
            raise PolicyError("seal-bound holdout ledger has mixed protocol records")
        return
    if kinds[0] != "legacy":
        raise PolicyError("holdout ledger must begin with a legacy, v2 or v3 record")
    migration_indexes = [index for index, kind in enumerate(kinds) if kind == "migration"]
    if len(migration_indexes) > 1:
        raise PolicyError("holdout ledger has multiple freeze migrations")
    if not migration_indexes:
        if any(kind != "legacy" for kind in kinds):
            raise PolicyError("legacy holdout ledger requires freeze migration")
        return
    migration_index = migration_indexes[0]
    if any(kind != "legacy" for kind in kinds[:migration_index]):
        raise PolicyError("holdout migration is out of protocol order")
    if migration_index != len(kinds) - 1:
        raise PolicyError("migrated audit-only ledger cannot accept later events")


def _validate_seal_immutability(records: Sequence[Mapping[str, Any]]) -> None:
    sealed_manifest_sha256: str | None = None
    sealed_manifest_path_sha256: str | None = None
    sealed_split_sha256: str | None = None
    for record in records:
        if record["event_type"] == LedgerEvent.SEALED_VERIFIED.value:
            if sealed_manifest_sha256 is None:
                sealed_manifest_sha256 = str(record["holdout_manifest_sha256"])
                if _ledger_record_kind(record) == "v3":
                    sealed_manifest_path_sha256 = str(record["holdout_manifest_path_sha256"])
                    sealed_split_sha256 = str(record["split_manifest_sha256"])
            continue
        if sealed_manifest_sha256 is None:
            continue
        if record["holdout_manifest_sha256"] != sealed_manifest_sha256:
            raise PolicyError("holdout ledger contains a changed sealed Manifest SHA")
        if (
            sealed_manifest_path_sha256 is not None
            and _ledger_record_kind(record) == "v3"
            and record["holdout_manifest_path_sha256"] != sealed_manifest_path_sha256
        ):
            raise PolicyError("holdout ledger contains a changed sealed Manifest path")
        if (
            sealed_split_sha256 is not None
            and _ledger_record_kind(record) == "v3"
            and record["split_manifest_sha256"] != sealed_split_sha256
        ):
            raise PolicyError("holdout ledger contains a changed sealed split SHA")


def _canonical_json(values: Mapping[str, Any]) -> bytes:
    return json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _append_json_record(path: Path, record: Mapping[str, Any]) -> None:
    line = json.dumps(record, sort_keys=True, separators=(",", ":"))
    try:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as error:
        raise PolicyError(f"could not append holdout ledger at {path}") from error


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
