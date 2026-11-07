"""Match-level split and holdout seal lifecycle."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from enum import StrEnum

from mtah_possession.governance.policy import PolicyError


class HoldoutStatus(StrEnum):
    UNASSIGNED = "unassigned"
    SEALED = "sealed"
    UNSEALED = "unsealed"
    COMPROMISED = "compromised"


@dataclass(frozen=True)
class SplitAssignment:
    development: frozenset[str]
    validation: frozenset[str]
    holdout: frozenset[str]

    def validate(self) -> None:
        if "2017461" in self.holdout:
            raise PolicyError("2017461 is development-only and cannot enter holdout")
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
    def sealed(cls, matches: tuple[str, ...]) -> HoldoutManifest:
        return cls(
            schema_version="2.0",
            status=HoldoutStatus.SEALED,
            matches=matches,
            model_freeze_sha256=None,
            feature_set_sha256=None,
            config_freeze_sha256=None,
            hyperparameter_set_sha256=None,
            evaluation_script_sha256=None,
            metric_contract_version=None,
            unseal_log=(),
        )

    def unseal(
        self,
        *,
        evaluation_licensed: bool,
        exposure_verified: bool,
        model_freeze: str,
        feature_set: str,
        config_freeze: str,
        hyperparameters: str,
        evaluation_script: str,
        metric_contract_version: str,
        evaluation_independent: bool,
    ) -> HoldoutManifest:
        if self.status != HoldoutStatus.SEALED:
            raise PolicyError("only a sealed holdout can be unsealed")
        missing = [
            name
            for name, value in (
                ("model_freeze", model_freeze),
                ("feature_set", feature_set),
                ("config_freeze", config_freeze),
                ("hyperparameters", hyperparameters),
                ("evaluation_script", evaluation_script),
                ("metric_contract_version", metric_contract_version),
            )
            if not value.strip()
        ]
        if missing:
            raise PolicyError(f"holdout unseal requires frozen identities: {missing}")
        if not evaluation_licensed or not exposure_verified or not evaluation_independent:
            raise PolicyError("holdout unseal rights/exposure/independence gate failed")
        return replace(
            self,
            status=HoldoutStatus.UNSEALED,
            model_freeze_sha256=model_freeze,
            feature_set_sha256=feature_set,
            config_freeze_sha256=config_freeze,
            hyperparameter_set_sha256=hyperparameters,
            evaluation_script_sha256=evaluation_script,
            metric_contract_version=metric_contract_version,
            unseal_log=self.unseal_log
            + (
                hashlib.sha256(
                    f"{model_freeze}:{feature_set}:{config_freeze}:"
                    f"{hyperparameters}:{evaluation_script}".encode()
                ).hexdigest(),
            ),
        )

    def record_result(
        self,
        *,
        model_freeze: str,
        feature_set: str,
        config_freeze: str,
        hyperparameters: str,
        used_for_tuning: bool,
    ) -> HoldoutManifest:
        if self.status != HoldoutStatus.UNSEALED:
            raise PolicyError("holdout must be unsealed before recording results")
        changed = (
            model_freeze != self.model_freeze_sha256
            or feature_set != self.feature_set_sha256
            or config_freeze != self.config_freeze_sha256
            or hyperparameters != self.hyperparameter_set_sha256
        )
        if used_for_tuning or changed:
            return replace(self, status=HoldoutStatus.COMPROMISED)
        return self
