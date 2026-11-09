"""Machine-validated external data policy."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class PolicyError(ValueError):
    """Raised when policy data is incomplete or a requested use is not allowed."""


class AuthorizationFailureReason(StrEnum):
    EXTERNAL_LICENSE_HOLD = "EXTERNAL_LICENSE_HOLD"
    INTERNAL_RESEARCH_HOLD = "INTERNAL_RESEARCH_HOLD"
    USE_PERMISSION_HOLD = "USE_PERMISSION_HOLD"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    UNREGISTERED_EVIDENCE = "UNREGISTERED_EVIDENCE"
    PERMISSION_FAIL = "PERMISSION_FAIL"
    POLICY_INTEGRITY_ERROR = "POLICY_INTEGRITY_ERROR"
    SOURCE_IDENTITY_ERROR = "SOURCE_IDENTITY_ERROR"


class AuthorizationFailure(PolicyError):
    """A classified production authorization failure."""

    def __init__(self, reason: AuthorizationFailureReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class PolicyStatus(StrEnum):
    PASS = "PASS"
    PROJECT_RISK_ACCEPTED_INTERNAL = "PROJECT_RISK_ACCEPTED_INTERNAL"
    HOLD = "HOLD"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AuthorizationBasis(StrEnum):
    EXTERNAL_RIGHT = "EXTERNAL_RIGHT"
    SCOPED_INTERNAL_RISK = "SCOPED_INTERNAL_RISK"


class DataUse(StrEnum):
    DOWNLOAD_STORE = "download_store"
    READ_PREPROCESS = "read_preprocess"
    TRACKING_MODEL_INPUT = "tracking_model_input"
    POSSESSION_GROUP_TARGET = "possession_group_target"
    POSSESSION_PLAYER_AUX_TARGET = "possession_player_aux_target"
    PHASE_AUXILIARY_TARGET = "phase_auxiliary_target"
    PHASE_MODEL_INPUT = "phase_model_input"
    EVALUATION_REFERENCE = "evaluation_reference"
    DERIVED_MODEL = "derived_model"
    PUBLICATION = "publication"
    SOURCE_REDISTRIBUTION = "source_redistribution"
    DERIVED_REDISTRIBUTION = "derived_redistribution"


STATUS_AXES = frozenset(
    {
        "PUBLIC_SOURCE_VERIFIED",
        "LICENSE_VERIFIED",
        "INTERNAL_RESEARCH_AUTHORIZED",
        "TRAINING_AUTHORIZED",
        "EVALUATION_AUTHORIZED",
        "PUBLICATION_AUTHORIZED",
        "REDISTRIBUTION_AUTHORIZED",
        "TEMPORAL_AVAILABILITY_VERIFIED",
        "PHASE_SEMANTICS_VERIFIED",
        "PLAYER_ID_LABEL_QUALITY_VERIFIED",
        "LABEL_SEMANTICS_ALIGNED",
        "HOLDOUT_SEAL_VERIFIED",
    }
)

USE_AXES = frozenset(use.value for use in DataUse)
SCOPED_INTERNAL_RISK_USES = frozenset(
    {
        DataUse.DOWNLOAD_STORE,
        DataUse.READ_PREPROCESS,
    }
)
NEVER_SCOPED_INTERNAL_RISK_USES = frozenset(
    {
        "final_candidate",
        DataUse.PUBLICATION.value,
        DataUse.SOURCE_REDISTRIBUTION.value,
        DataUse.DERIVED_REDISTRIBUTION.value,
    }
)
SCOPED_RISK_FALLBACK_REASONS = frozenset(
    {
        AuthorizationFailureReason.EXTERNAL_LICENSE_HOLD,
        AuthorizationFailureReason.INTERNAL_RESEARCH_HOLD,
        AuthorizationFailureReason.USE_PERMISSION_HOLD,
    }
)


@dataclass(frozen=True)
class UsePermission:
    status: PolicyStatus
    evidence_ids: tuple[str, ...]
    conditions: tuple[str, ...]


@dataclass(frozen=True)
class LabelProfile:
    provider: str
    provider_label_definition_id: str
    source_field: str
    label_kind: str
    roles: tuple[str, ...]
    time_basis: str
    null_semantics: str
    target_mapping_id: str
    mapping_version: str
    mapping_evidence: tuple[str, ...]
    status: PolicyStatus


@dataclass(frozen=True)
class ProjectRiskAcceptance:
    scope_id: str
    provider: str
    source_revision: str
    match_ids: tuple[str, ...]
    allowed_uses: tuple[str, ...]
    restrictions: tuple[str, ...]
    risk_owner: str
    accepted_at: str
    review_at: str
    status: PolicyStatus


@dataclass(frozen=True)
class AuthorizationDecision:
    basis: AuthorizationBasis
    scope_id: str | None = None


@dataclass(frozen=True)
class ProviderPolicy:
    name: str
    source_revision: str
    source_evidence: tuple[str, ...]
    statuses: dict[str, PolicyStatus]
    uses: dict[DataUse, UsePermission]
    label_profiles: tuple[LabelProfile, ...]
    project_risk_acceptances: tuple[ProjectRiskAcceptance, ...] = ()

    @property
    def overall_status(self) -> PolicyStatus:
        """Display-only aggregate; production authorization uses individual gates."""
        research_uses = (
            DataUse.DOWNLOAD_STORE,
            DataUse.READ_PREPROCESS,
            DataUse.TRACKING_MODEL_INPUT,
            DataUse.POSSESSION_GROUP_TARGET,
            DataUse.POSSESSION_PLAYER_AUX_TARGET,
            DataUse.PHASE_AUXILIARY_TARGET,
            DataUse.PHASE_MODEL_INPUT,
            DataUse.EVALUATION_REFERENCE,
            DataUse.DERIVED_MODEL,
        )
        statuses = {self.uses[use].status for use in research_uses}
        if PolicyStatus.FAIL in statuses:
            return PolicyStatus.FAIL
        if PolicyStatus.HOLD in statuses:
            return PolicyStatus.HOLD
        if statuses == {PolicyStatus.NOT_APPLICABLE}:
            return PolicyStatus.NOT_APPLICABLE
        return PolicyStatus.PASS


@dataclass(frozen=True)
class ExternalDataPolicy:
    schema_version: str
    policy_version: str
    official_rule_revision: str
    providers: dict[str, ProviderPolicy]

    def provider(self, name: str) -> ProviderPolicy:
        try:
            return self.providers[name]
        except KeyError as error:
            raise PolicyError(f"provider {name!r} is not registered") from error


def load_policy(path: str | os.PathLike[str]) -> ExternalDataPolicy:
    policy_path = Path(path)
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyError(f"could not read external data policy: {policy_path}") from error
    if not isinstance(raw, dict):
        raise PolicyError("policy root must be an object")
    required = {"schema_version", "policy_version", "official_rule_revision", "providers"}
    if set(raw) != required:
        raise PolicyError("policy root has missing or unknown fields")
    if raw["schema_version"] not in {"2.0", "2.1"}:
        raise PolicyError("policy schema_version must be 2.0 or 2.1")
    if raw["policy_version"] not in {"DP-006-POLICY-v2", "DP-006-POLICY-v2.1"}:
        raise PolicyError("unexpected policy_version")
    if (
        not isinstance(raw["official_rule_revision"], str)
        or len(raw["official_rule_revision"]) < 40
    ):
        raise PolicyError("official rule revision must be pinned")
    if not isinstance(raw["providers"], list):
        raise PolicyError("providers must be a list")
    providers: dict[str, ProviderPolicy] = {}
    for provider_raw in raw["providers"]:
        provider = _parse_provider(provider_raw)
        if provider.name in providers:
            raise PolicyError(f"duplicate provider: {provider.name}")
        providers[provider.name] = provider
    return ExternalDataPolicy(
        schema_version=raw["schema_version"],
        policy_version=raw["policy_version"],
        official_rule_revision=raw["official_rule_revision"],
        providers=providers,
    )


def require_source_identity(
    policy: ExternalDataPolicy,
    provider_name: str,
    source_revision: str,
) -> ProviderPolicy:
    provider = policy.provider(provider_name)
    if not source_revision.strip():
        raise PolicyError("provider source revision is not pinned")
    if provider.source_revision != source_revision:
        raise PolicyError(
            "provider revision mismatch: "
            f"policy={provider.source_revision}, source={source_revision}"
        )
    if not provider.source_evidence:
        raise PolicyError("provider source evidence IDs are missing")
    return provider


def require_scoped_internal_risk(
    policy: ExternalDataPolicy,
    *,
    provider_name: str,
    source_revision: str,
    match_id: str,
    use: str,
    now: datetime | None = None,
) -> ProjectRiskAcceptance:
    """Authorize one bounded internal use without changing external rights."""
    if use in NEVER_SCOPED_INTERNAL_RISK_USES:
        raise PolicyError(f"scoped internal risk cannot authorize {use}")
    provider = require_source_identity(policy, provider_name, source_revision)
    current = now or datetime.now(UTC)
    for scope in provider.project_risk_acceptances:
        if scope.status != PolicyStatus.PROJECT_RISK_ACCEPTED_INTERNAL:
            continue
        if scope.provider != provider_name or scope.source_revision != source_revision:
            continue
        if match_id not in scope.match_ids or use not in scope.allowed_uses:
            continue
        if not scope.restrictions or not scope.risk_owner:
            continue
        try:
            accepted = datetime.fromisoformat(scope.accepted_at)
            review = datetime.fromisoformat(scope.review_at)
        except (TypeError, ValueError) as error:
            raise PolicyError("project risk acceptance timestamps are invalid") from error
        if accepted.tzinfo is None or review.tzinfo is None or accepted >= review:
            raise PolicyError("project risk acceptance timestamps are invalid")
        if accepted > current or review <= current:
            continue
        return scope
    raise PolicyError(f"no active scoped internal risk acceptance for {provider_name}/{use}")


def require_allowed(
    policy: ExternalDataPolicy,
    provider_name: str,
    use: DataUse,
    *,
    source_revision: str,
    match_id: str | None = None,
    allow_scoped_internal: bool = False,
    now: datetime | None = None,
) -> AuthorizationDecision:
    provider = require_source_identity(policy, provider_name, source_revision)
    try:
        _require_external_right(provider, use)
    except AuthorizationFailure as external_error:
        if external_error.reason not in SCOPED_RISK_FALLBACK_REASONS:
            raise
        if not allow_scoped_internal:
            raise
        if use not in SCOPED_INTERNAL_RISK_USES:
            raise
        if not match_id:
            raise PolicyError("scoped internal risk requires a match ID") from None
        if provider.statuses["PUBLIC_SOURCE_VERIFIED"] != PolicyStatus.PASS:
            raise PolicyError(
                f"{provider_name} PUBLIC_SOURCE_VERIFIED="
                f"{provider.statuses['PUBLIC_SOURCE_VERIFIED'].value}"
            ) from None
        for axis in ("LICENSE_VERIFIED", "INTERNAL_RESEARCH_AUTHORIZED"):
            if provider.statuses[axis] == PolicyStatus.FAIL:
                raise PolicyError(f"{provider_name} {axis}=FAIL") from None
        if provider.uses[use].status == PolicyStatus.FAIL:
            raise PolicyError(f"{provider_name} use {use.value} status is FAIL") from None
        try:
            scope = require_scoped_internal_risk(
                policy,
                provider_name=provider_name,
                source_revision=source_revision,
                match_id=match_id,
                use=use.value,
                now=now,
            )
        except PolicyError as scope_error:
            raise PolicyError(f"{external_error}; {scope_error}") from scope_error
        return AuthorizationDecision(
            basis=AuthorizationBasis.SCOPED_INTERNAL_RISK,
            scope_id=scope.scope_id,
        )
    return AuthorizationDecision(basis=AuthorizationBasis.EXTERNAL_RIGHT)


def _require_external_right(provider: ProviderPolicy, use: DataUse) -> None:
    required_statuses = _required_statuses(use)
    failed: list[str] = []
    reasons: set[AuthorizationFailureReason] = set()
    for axis in required_statuses:
        status = provider.statuses[axis]
        if status == PolicyStatus.PASS:
            continue
        failed.append(f"{axis}={status.value}")
        if axis == "PUBLIC_SOURCE_VERIFIED":
            reasons.add(AuthorizationFailureReason.SOURCE_IDENTITY_ERROR)
        elif axis == "LICENSE_VERIFIED" and status == PolicyStatus.HOLD:
            reasons.add(AuthorizationFailureReason.EXTERNAL_LICENSE_HOLD)
        elif axis == "INTERNAL_RESEARCH_AUTHORIZED" and status == PolicyStatus.HOLD:
            reasons.add(AuthorizationFailureReason.INTERNAL_RESEARCH_HOLD)
        elif status == PolicyStatus.HOLD:
            reasons.add(AuthorizationFailureReason.USE_PERMISSION_HOLD)
        else:
            reasons.add(AuthorizationFailureReason.PERMISSION_FAIL)
    permission = provider.uses[use]
    if permission.status == PolicyStatus.FAIL:
        reasons.add(AuthorizationFailureReason.PERMISSION_FAIL)
        failed.append(f"{use.value}=FAIL")
    elif permission.status == PolicyStatus.HOLD:
        reasons.add(AuthorizationFailureReason.USE_PERMISSION_HOLD)
        failed.append(f"{use.value}=HOLD")
    elif permission.status != PolicyStatus.PASS:
        reasons.add(AuthorizationFailureReason.POLICY_INTEGRITY_ERROR)
        failed.append(f"{use.value}={permission.status.value}")
    elif not permission.evidence_ids:
        reasons.add(AuthorizationFailureReason.MISSING_EVIDENCE)
        failed.append(f"{use.value}=MISSING_EVIDENCE")
    else:
        unavailable = sorted(set(permission.evidence_ids).difference(provider.source_evidence))
        if unavailable:
            reasons.add(AuthorizationFailureReason.UNREGISTERED_EVIDENCE)
            failed.append(f"{use.value}=UNREGISTERED_EVIDENCE")
    if reasons:
        reason = next(
            (
                candidate
                for candidate in (
                    AuthorizationFailureReason.SOURCE_IDENTITY_ERROR,
                    AuthorizationFailureReason.PERMISSION_FAIL,
                    AuthorizationFailureReason.MISSING_EVIDENCE,
                    AuthorizationFailureReason.UNREGISTERED_EVIDENCE,
                    AuthorizationFailureReason.POLICY_INTEGRITY_ERROR,
                    AuthorizationFailureReason.EXTERNAL_LICENSE_HOLD,
                    AuthorizationFailureReason.INTERNAL_RESEARCH_HOLD,
                    AuthorizationFailureReason.USE_PERMISSION_HOLD,
                )
                if candidate in reasons
            ),
            AuthorizationFailureReason.POLICY_INTEGRITY_ERROR,
        )
        raise AuthorizationFailure(
            reason,
            f"{provider.name} use {use.value} is not allowed: " + ", ".join(failed),
        )


def _parse_provider(raw: Any) -> ProviderPolicy:
    if not isinstance(raw, dict):
        raise PolicyError("provider entry must be an object")
    required = {
        "provider",
        "source_revision",
        "source_evidence",
        "statuses",
        "uses",
        "label_profiles",
    }
    optional = {"project_risk_acceptances"}
    if set(raw) != required and set(raw) != required | optional:
        raise PolicyError("provider entry has missing or unknown fields")
    if not isinstance(raw["provider"], str) or not raw["provider"].strip():
        raise PolicyError("provider name is missing")
    if not isinstance(raw["source_revision"], str) or len(raw["source_revision"]) < 7:
        raise PolicyError(f"provider {raw['provider']} revision is not pinned")
    source_evidence = _string_tuple(raw["source_evidence"], "source_evidence")
    if not source_evidence:
        raise PolicyError(f"provider {raw['provider']} has no source evidence")
    statuses = _parse_statuses(raw["statuses"])
    uses = _parse_uses(raw["uses"])
    for use, permission in uses.items():
        if permission.status != PolicyStatus.PASS:
            continue
        if not permission.evidence_ids:
            raise PolicyError(f"PASS use {use.value} requires evidence IDs")
        unavailable = sorted(set(permission.evidence_ids).difference(source_evidence))
        if unavailable:
            raise PolicyError(
                f"PASS use {use.value} evidence IDs are not registered: {unavailable}"
            )
    profiles = tuple(_parse_label_profile(raw["provider"], item) for item in raw["label_profiles"])
    risks = tuple(
        _parse_project_risk_acceptance(raw["provider"], item)
        for item in raw.get("project_risk_acceptances", ())
    )
    if any(scope.source_revision != raw["source_revision"] for scope in risks):
        raise PolicyError("project risk acceptance revision does not match provider")
    return ProviderPolicy(
        name=raw["provider"],
        source_revision=raw["source_revision"],
        source_evidence=source_evidence,
        statuses=statuses,
        uses=uses,
        label_profiles=profiles,
        project_risk_acceptances=risks,
    )


def _parse_statuses(raw: Any) -> dict[str, PolicyStatus]:
    if not isinstance(raw, dict) or set(raw) != STATUS_AXES:
        raise PolicyError("policy status axes are missing or unknown")
    try:
        return {name: PolicyStatus(value) for name, value in raw.items()}
    except ValueError as error:
        raise PolicyError("policy status contains an invalid value") from error


def _parse_uses(raw: Any) -> dict[DataUse, UsePermission]:
    if not isinstance(raw, dict) or set(raw) != USE_AXES:
        raise PolicyError("policy use axes are missing or unknown")
    parsed: dict[DataUse, UsePermission] = {}
    for name, item in raw.items():
        if not isinstance(item, dict) or set(item) != {"status", "evidence_ids", "conditions"}:
            raise PolicyError(f"use {name} has invalid fields")
        try:
            status = PolicyStatus(item["status"])
        except ValueError as error:
            raise PolicyError(f"use {name} has invalid status") from error
        parsed[DataUse(name)] = UsePermission(
            status=status,
            evidence_ids=_string_tuple(item["evidence_ids"], "evidence_ids"),
            conditions=_string_tuple(item["conditions"], "conditions"),
        )
    return parsed


def _parse_label_profile(provider: str, raw: Any) -> LabelProfile:
    required = {
        "provider_label_definition_id",
        "source_field",
        "label_kind",
        "roles",
        "time_basis",
        "null_semantics",
        "target_mapping_id",
        "mapping_version",
        "mapping_evidence",
        "status",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise PolicyError("label profile has missing or unknown fields")
    if raw["label_kind"] not in {"truth", "proxy", "event-derived", "unknown"}:
        raise PolicyError("label profile has invalid label_kind")
    roles = _string_tuple(raw["roles"], "roles")
    if "MODEL_INPUT" in roles:
        raise PolicyError("label profile roles cannot include MODEL_INPUT by default")
    try:
        status = PolicyStatus(raw["status"])
    except ValueError as error:
        raise PolicyError("label profile has invalid status") from error
    for key in (
        "provider_label_definition_id",
        "source_field",
        "time_basis",
        "null_semantics",
        "target_mapping_id",
        "mapping_version",
    ):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise PolicyError(f"label profile {key} is missing")
    mapping_evidence = _string_tuple(raw["mapping_evidence"], "mapping_evidence")
    if not mapping_evidence:
        raise PolicyError("label profile mapping evidence is missing")
    return LabelProfile(
        provider=provider,
        provider_label_definition_id=raw["provider_label_definition_id"],
        source_field=raw["source_field"],
        label_kind=raw["label_kind"],
        roles=roles,
        time_basis=raw["time_basis"],
        null_semantics=raw["null_semantics"],
        target_mapping_id=raw["target_mapping_id"],
        mapping_version=raw["mapping_version"],
        mapping_evidence=mapping_evidence,
        status=status,
    )


def _parse_project_risk_acceptance(
    provider: str,
    raw: Any,
) -> ProjectRiskAcceptance:
    required = {
        "scope_id",
        "provider",
        "source_revision",
        "match_ids",
        "allowed_uses",
        "restrictions",
        "risk_owner",
        "accepted_at",
        "review_at",
        "status",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise PolicyError("project risk acceptance has missing or unknown fields")
    if raw["provider"] != provider:
        raise PolicyError("project risk acceptance provider mismatch")
    match_ids = _string_tuple(raw["match_ids"], "match_ids")
    allowed_uses = _string_tuple(raw["allowed_uses"], "allowed_uses")
    restrictions = _string_tuple(raw["restrictions"], "restrictions")
    if not match_ids or match_ids != tuple(sorted(set(match_ids))):
        raise PolicyError("project risk acceptance match IDs are invalid")
    if not allowed_uses or not restrictions:
        raise PolicyError("project risk acceptance scope is incomplete")
    try:
        status = PolicyStatus(raw["status"])
    except ValueError as error:
        raise PolicyError("project risk acceptance status is invalid") from error
    if status != PolicyStatus.PROJECT_RISK_ACCEPTED_INTERNAL:
        raise PolicyError("project risk acceptance must use scoped internal status")
    return ProjectRiskAcceptance(
        scope_id=str(raw["scope_id"]),
        provider=provider,
        source_revision=str(raw["source_revision"]),
        match_ids=match_ids,
        allowed_uses=allowed_uses,
        restrictions=restrictions,
        risk_owner=str(raw["risk_owner"]),
        accepted_at=str(raw["accepted_at"]),
        review_at=str(raw["review_at"]),
        status=status,
    )


def _required_statuses(use: DataUse) -> tuple[str, ...]:
    common = (
        "PUBLIC_SOURCE_VERIFIED",
        "LICENSE_VERIFIED",
        "INTERNAL_RESEARCH_AUTHORIZED",
    )
    specific = {
        DataUse.POSSESSION_GROUP_TARGET: ("TRAINING_AUTHORIZED",),
        DataUse.POSSESSION_PLAYER_AUX_TARGET: ("TRAINING_AUTHORIZED",),
        DataUse.PHASE_AUXILIARY_TARGET: ("TRAINING_AUTHORIZED", "PHASE_SEMANTICS_VERIFIED"),
        DataUse.PHASE_MODEL_INPUT: ("PHASE_SEMANTICS_VERIFIED",),
        DataUse.TRACKING_MODEL_INPUT: ("TEMPORAL_AVAILABILITY_VERIFIED",),
        DataUse.EVALUATION_REFERENCE: ("EVALUATION_AUTHORIZED",),
        DataUse.PUBLICATION: ("PUBLICATION_AUTHORIZED",),
        DataUse.SOURCE_REDISTRIBUTION: ("REDISTRIBUTION_AUTHORIZED",),
        DataUse.DERIVED_REDISTRIBUTION: ("REDISTRIBUTION_AUTHORIZED",),
    }
    return common + specific.get(use, ())


def _string_tuple(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PolicyError(f"{name} must be a string list")
    return tuple(value)
