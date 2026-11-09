"""Match-level split and holdout seal lifecycle."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from mtah_possession.governance.policy import PolicyError


class HoldoutCompromisedError(PolicyError):
    """Raised when a frozen holdout identity no longer matches."""


class HoldoutStatus(StrEnum):
    UNASSIGNED = "unassigned"
    SEALED = "sealed"
    UNSEALED = "unsealed"
    COMPROMISED = "compromised"


@dataclass(frozen=True)
class FreezeHashes:
    model: str
    feature_set: str
    configuration: str
    hyperparameters: str
    evaluation_script: str
    metric_contract_version: str

    def missing(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, value in (
                ("model", self.model),
                ("feature_set", self.feature_set),
                ("configuration", self.configuration),
                ("hyperparameters", self.hyperparameters),
                ("evaluation_script", self.evaluation_script),
                ("metric_contract_version", self.metric_contract_version),
            )
            if not value.strip()
        )


@dataclass(frozen=True)
class SplitAssignment:
    development: frozenset[str]
    validation: frozenset[str]
    holdout: frozenset[str]

    def validate(self) -> None:
        if "2017461" in self.holdout or "2017461" in self.validation:
            raise PolicyError("2017461 is development-only and cannot leave development")
        groups = (self.development, self.validation, self.holdout)
        if any(self.development & group for group in groups[1:]):
            raise PolicyError("development split overlaps another split")
        if self.validation & self.holdout:
            raise PolicyError("validation split overlaps holdout")

    def assign_vendor_test_as_project_holdout(self, _match_id: str) -> None:
        raise PolicyError("vendor test split cannot automatically become project holdout")


@dataclass(frozen=True)
class HoldoutManifest:
    schema_version: str
    status: HoldoutStatus
    matches: tuple[str, ...]
    model_freeze_sha256: str | None
    feature_set_sha256: str | None
    config_freeze_sha256: str | None
    hyperparameter_set_sha256: str | None
    evaluation_script_sha256: str | None
    metric_contract_version: str | None
    unseal_log: tuple[str, ...]

    @classmethod
    def sealed(
        cls,
        matches: tuple[str, ...],
        freeze: FreezeHashes | None = None,
    ) -> HoldoutManifest:
        return cls(
            schema_version="2.0",
            status=HoldoutStatus.SEALED,
            matches=matches,
            model_freeze_sha256=None if freeze is None else freeze.model,
            feature_set_sha256=None if freeze is None else freeze.feature_set,
            config_freeze_sha256=None if freeze is None else freeze.configuration,
            hyperparameter_set_sha256=None if freeze is None else freeze.hyperparameters,
            evaluation_script_sha256=None if freeze is None else freeze.evaluation_script,
            metric_contract_version=None if freeze is None else freeze.metric_contract_version,
            unseal_log=(),
        )

    def require_frozen(self, freeze: FreezeHashes) -> None:
        if self.status != HoldoutStatus.SEALED:
            raise PolicyError("holdout manifest is not sealed")
        missing = freeze.missing()
        if missing:
            raise PolicyError(f"holdout freeze identity is missing: {missing}")
        stored = (
            self.model_freeze_sha256,
            self.feature_set_sha256,
            self.config_freeze_sha256,
            self.hyperparameter_set_sha256,
            self.evaluation_script_sha256,
            self.metric_contract_version,
        )
        expected = (
            freeze.model,
            freeze.feature_set,
            freeze.configuration,
            freeze.hyperparameters,
            freeze.evaluation_script,
            freeze.metric_contract_version,
        )
        if stored != expected:
            raise HoldoutCompromisedError("holdout freeze hash or metric contract does not match")

    def unseal(
        self,
        *,
        evaluation_licensed: bool,
        exposure_verified: bool,
        freeze: FreezeHashes,
        evaluation_independent: bool,
    ) -> HoldoutManifest:
        if self.status != HoldoutStatus.SEALED:
            raise PolicyError("only a sealed holdout can be unsealed")
        self.require_frozen(freeze)
        if not evaluation_licensed or not exposure_verified or not evaluation_independent:
            raise PolicyError("holdout unseal rights/exposure/independence gate failed")
        return replace(
            self,
            status=HoldoutStatus.UNSEALED,
            model_freeze_sha256=freeze.model,
            feature_set_sha256=freeze.feature_set,
            config_freeze_sha256=freeze.configuration,
            hyperparameter_set_sha256=freeze.hyperparameters,
            evaluation_script_sha256=freeze.evaluation_script,
            metric_contract_version=freeze.metric_contract_version,
            unseal_log=self.unseal_log
            + (
                hashlib.sha256(
                    f"{freeze.model}:{freeze.feature_set}:{freeze.configuration}:"
                    f"{freeze.hyperparameters}:{freeze.evaluation_script}".encode()
                ).hexdigest(),
            ),
        )

    def record_result(
        self,
        *,
        freeze: FreezeHashes,
        used_for_tuning: bool,
    ) -> HoldoutManifest:
        if self.status != HoldoutStatus.UNSEALED:
            raise PolicyError("holdout must be unsealed before recording results")
        changed = (
            freeze.model != self.model_freeze_sha256
            or freeze.feature_set != self.feature_set_sha256
            or freeze.configuration != self.config_freeze_sha256
            or freeze.hyperparameters != self.hyperparameter_set_sha256
        )
        if used_for_tuning or changed:
            return replace(self, status=HoldoutStatus.COMPROMISED)
        return self


def load_holdout_manifest(path: str | os.PathLike[str]) -> HoldoutManifest:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyError("could not read holdout manifest") from error
    required = {
        "schema_version",
        "status",
        "matches",
        "model_freeze_sha256",
        "feature_set_sha256",
        "config_freeze_sha256",
        "hyperparameter_set_sha256",
        "evaluation_script_sha256",
        "metric_contract_version",
        "unseal_log",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise PolicyError("holdout manifest has missing or unknown fields")
    if raw["schema_version"] != "2.0":
        raise PolicyError("holdout schema_version must be 2.0")
    try:
        status = HoldoutStatus(raw["status"])
    except ValueError as error:
        raise PolicyError("invalid holdout status") from error
    return HoldoutManifest(
        schema_version="2.0",
        status=status,
        matches=_string_tuple(raw["matches"]),
        model_freeze_sha256=_optional_string(raw["model_freeze_sha256"]),
        feature_set_sha256=_optional_string(raw["feature_set_sha256"]),
        config_freeze_sha256=_optional_string(raw["config_freeze_sha256"]),
        hyperparameter_set_sha256=_optional_string(raw["hyperparameter_set_sha256"]),
        evaluation_script_sha256=_optional_string(raw["evaluation_script_sha256"]),
        metric_contract_version=_optional_string(raw["metric_contract_version"]),
        unseal_log=_string_tuple(raw["unseal_log"]),
    )


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PolicyError("holdout manifest list fields must contain strings")
    return tuple(value)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PolicyError("holdout freeze values must be strings or null")
    return value
