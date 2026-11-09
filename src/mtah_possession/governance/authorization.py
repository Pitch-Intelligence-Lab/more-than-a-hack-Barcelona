"""Single fail-closed authorization result for real external-data runs."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import datetime
from pathlib import Path
from typing import Any

from mtah_possession.evaluation.splits import (
    EvaluationMode,
    SplitManifest,
    require_split,
)
from mtah_possession.governance.exposure import (
    ExposureRecord,
    load_exposure_register,
)
from mtah_possession.governance.holdout import (
    FreezeHashes,
    HoldoutManifest,
    SplitAssignment,
)
from mtah_possession.governance.policy import (
    AuthorizationBasis,
    AuthorizationDecision,
    DataUse,
    ExternalDataPolicy,
    LabelProfile,
    PolicyError,
    PolicyStatus,
    ProviderPolicy,
    UsePermission,
    load_policy,
    require_allowed,
    require_source_identity,
)
from mtah_possession.governance.roles import LabelRole

EVALUATION_POSSESSION_PROFILE = "skillcorner_possession_group_v1"
EVALUATION_PHASE_PROFILE = "skillcorner_phases_v1"
GOVERNANCE_IDENTITY_SCHEMA_VERSION = "1.0"
DEFAULT_EXPOSURE_REGISTER_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "policy" / "exposure-register-v1.json"
)


@dataclass(frozen=True)
class GovernanceAuthorizationIdentity:
    schema_version: str
    provider: str
    source_revision: str
    policy_version: str
    policy_sha256: str
    license_status: str
    internal_research_authorization: str
    evaluation_authorization: str
    temporal_authorization: str
    phase_authorization: str
    holdout_seal_authorization: str
    authorization_status_digest: str
    evidence_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider,
            "source_revision": self.source_revision,
            "policy_version": self.policy_version,
            "policy_sha256": self.policy_sha256,
            "license_status": self.license_status,
            "internal_research_authorization": self.internal_research_authorization,
            "evaluation_authorization": self.evaluation_authorization,
            "temporal_authorization": self.temporal_authorization,
            "phase_authorization": self.phase_authorization,
            "holdout_seal_authorization": self.holdout_seal_authorization,
            "authorization_status_digest": self.authorization_status_digest,
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True)
class AuthorizedExternalRun:
    policy: ExternalDataPolicy
    provider: ProviderPolicy
    use_permissions: dict[DataUse, UsePermission]
    label_profiles: dict[str, LabelProfile]
    freeze_hashes: FreezeHashes | None
    governance_identity: GovernanceAuthorizationIdentity
    use_bases: dict[DataUse, AuthorizationBasis] = dataclass_field(default_factory=dict)
    scope_ids: dict[DataUse, str | None] = dataclass_field(default_factory=dict)
    exposure_records: tuple[ExposureRecord, ...] = ()

    def to_authorization_record(self) -> dict[str, Any]:
        return {
            "uses": {
                use.value: {
                    "authorization_basis": (
                        self.use_bases[use].value
                        if use in self.use_bases
                        else AuthorizationBasis.EXTERNAL_RIGHT.value
                    ),
                    "scope_id": self.scope_ids.get(use),
                }
                for use in sorted(self.use_permissions, key=lambda item: item.value)
            },
            "exposure_disclosure": [record.to_dict() for record in self.exposure_records],
        }


def build_governance_identity(
    *,
    policy_path: str | os.PathLike[str],
    provider: str,
    source_revision: str,
) -> GovernanceAuthorizationIdentity:
    policy = load_policy(policy_path)
    provider_policy = policy.provider(provider)
    evidence_ids = sorted(
        {
            *provider_policy.source_evidence,
            *(
                evidence_id
                for permission in provider_policy.uses.values()
                for evidence_id in permission.evidence_ids
            ),
            *(
                evidence_id
                for profile in provider_policy.label_profiles
                for evidence_id in profile.mapping_evidence
            ),
        }
    )
    statuses = {
        "license_status": provider_policy.statuses["LICENSE_VERIFIED"].value,
        "internal_research_authorization": provider_policy.statuses[
            "INTERNAL_RESEARCH_AUTHORIZED"
        ].value,
        "evaluation_authorization": provider_policy.statuses["EVALUATION_AUTHORIZED"].value,
        "temporal_authorization": provider_policy.statuses["TEMPORAL_AVAILABILITY_VERIFIED"].value,
        "phase_authorization": provider_policy.statuses["PHASE_SEMANTICS_VERIFIED"].value,
        "holdout_seal_authorization": provider_policy.statuses["HOLDOUT_SEAL_VERIFIED"].value,
    }
    payload: dict[str, Any] = {
        "schema_version": GOVERNANCE_IDENTITY_SCHEMA_VERSION,
        "provider": provider,
        "source_revision": source_revision,
        "policy_version": policy.policy_version,
        "policy_sha256": _sha256_file(policy_path),
        **statuses,
        "evidence_ids": evidence_ids,
    }
    digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
    return GovernanceAuthorizationIdentity(
        schema_version=GOVERNANCE_IDENTITY_SCHEMA_VERSION,
        provider=provider,
        source_revision=source_revision,
        policy_version=policy.policy_version,
        policy_sha256=payload["policy_sha256"],
        license_status=statuses["license_status"],
        internal_research_authorization=statuses["internal_research_authorization"],
        evaluation_authorization=statuses["evaluation_authorization"],
        temporal_authorization=statuses["temporal_authorization"],
        phase_authorization=statuses["phase_authorization"],
        holdout_seal_authorization=statuses["holdout_seal_authorization"],
        authorization_status_digest=digest,
        evidence_ids=tuple(evidence_ids),
    )


def governance_identity_from_dict(
    values: Any,
) -> GovernanceAuthorizationIdentity:
    required = {
        "schema_version",
        "provider",
        "source_revision",
        "policy_version",
        "policy_sha256",
        "license_status",
        "internal_research_authorization",
        "evaluation_authorization",
        "temporal_authorization",
        "phase_authorization",
        "holdout_seal_authorization",
        "authorization_status_digest",
        "evidence_ids",
    }
    if not isinstance(values, dict) or set(values) != required:
        raise PolicyError("governance identity has missing or unknown fields")
    evidence_ids = values["evidence_ids"]
    if (
        not isinstance(evidence_ids, list)
        or not all(isinstance(item, str) and item for item in evidence_ids)
        or evidence_ids != sorted(set(evidence_ids))
    ):
        raise PolicyError("governance identity evidence IDs are invalid")
    for field in (
        "schema_version",
        "provider",
        "source_revision",
        "policy_version",
        "policy_sha256",
        "license_status",
        "internal_research_authorization",
        "evaluation_authorization",
        "temporal_authorization",
        "phase_authorization",
        "holdout_seal_authorization",
        "authorization_status_digest",
    ):
        if not isinstance(values[field], str) or not values[field]:
            raise PolicyError(f"governance identity field {field} is invalid")
    for field in (
        "license_status",
        "internal_research_authorization",
        "evaluation_authorization",
        "temporal_authorization",
        "phase_authorization",
        "holdout_seal_authorization",
    ):
        if values[field] not in {status.value for status in PolicyStatus}:
            raise PolicyError(f"governance identity field {field} has invalid status")
    if values["schema_version"] != GOVERNANCE_IDENTITY_SCHEMA_VERSION:
        raise PolicyError("governance identity schema version is unsupported")
    _validate_sha256(values["policy_sha256"], "governance policy SHA-256")
    _validate_sha256(
        values["authorization_status_digest"],
        "governance authorization digest",
    )
    payload = {key: value for key, value in values.items() if key != "authorization_status_digest"}
    expected = hashlib.sha256(_canonical_json(payload)).hexdigest()
    if values["authorization_status_digest"] != expected:
        raise PolicyError("governance authorization digest does not match")
    return GovernanceAuthorizationIdentity(
        schema_version=values["schema_version"],
        provider=values["provider"],
        source_revision=values["source_revision"],
        policy_version=values["policy_version"],
        policy_sha256=values["policy_sha256"],
        license_status=values["license_status"],
        internal_research_authorization=values["internal_research_authorization"],
        evaluation_authorization=values["evaluation_authorization"],
        temporal_authorization=values["temporal_authorization"],
        phase_authorization=values["phase_authorization"],
        holdout_seal_authorization=values["holdout_seal_authorization"],
        authorization_status_digest=values["authorization_status_digest"],
        evidence_ids=tuple(evidence_ids),
    )


def authorize_external_run(
    *,
    policy_path: str | Path,
    provider: str,
    source_revision: str,
    requested_uses: tuple[DataUse, ...],
    label_profile_ids: tuple[str, ...],
    required_status_axes: tuple[str, ...] = (),
    split_manifest: SplitManifest,
    match_id: str,
    split: str,
    mode: EvaluationMode,
    holdout_manifest: HoldoutManifest | None = None,
    freeze_hashes: FreezeHashes | None = None,
    governance_identity: GovernanceAuthorizationIdentity | None = None,
    verify_holdout_freeze: bool = True,
    exposure_register_path: str | os.PathLike[str] | None = DEFAULT_EXPOSURE_REGISTER_PATH,
    now: datetime | None = None,
) -> AuthorizedExternalRun:
    policy = load_policy(policy_path)
    identity = governance_identity or build_governance_identity(
        policy_path=policy_path,
        provider=provider,
        source_revision=source_revision,
    )
    if identity.provider != provider or identity.source_revision != source_revision:
        raise PolicyError("governance identity does not match provider/source revision")
    if identity.policy_sha256 != _sha256_file(policy_path):
        raise PolicyError("governance identity policy SHA-256 is stale")
    require_source_identity(policy, provider, source_revision)
    decisions: dict[DataUse, AuthorizationDecision] = {}
    for use in requested_uses:
        decisions[use] = require_allowed(
            policy,
            provider,
            use,
            source_revision=source_revision,
            match_id=match_id,
            allow_scoped_internal=True,
            now=now,
        )
    provider_policy = policy.provider(provider)
    status_axes = list(required_status_axes)
    if label_profile_ids:
        status_axes.append("LABEL_SEMANTICS_ALIGNED")
    for axis in sorted(set(status_axes)):
        if provider_policy.statuses[axis] != PolicyStatus.PASS:
            raise PolicyError(f"{provider} {axis}={provider_policy.statuses[axis].value}")

    profiles: dict[str, LabelProfile] = {}
    for profile_id in label_profile_ids:
        profile = _find_profile(provider_policy, profile_id)
        if profile.status != PolicyStatus.PASS:
            raise PolicyError(f"label profile {profile_id} status is {profile.status.value}")
        if LabelRole.EVALUATION_REFERENCE.value not in profile.roles:
            raise PolicyError(f"label profile {profile_id} lacks EVALUATION_REFERENCE role")
        if not profile.target_mapping_id or not profile.mapping_version:
            raise PolicyError(f"label profile {profile_id} mapping is incomplete")
        profiles[profile_id] = profile

    SplitAssignment(
        development=split_manifest.development,
        validation=split_manifest.validation,
        holdout=split_manifest.holdout,
    ).validate()
    require_split(split_manifest, match_id, split, mode=mode)

    if mode == EvaluationMode.PROMOTION:
        if provider_policy.statuses["HOLDOUT_SEAL_VERIFIED"] != PolicyStatus.PASS:
            raise PolicyError(
                f"HOLDOUT_SEAL_VERIFIED={provider_policy.statuses['HOLDOUT_SEAL_VERIFIED'].value}"
            )
        if holdout_manifest is None or freeze_hashes is None:
            raise PolicyError("promotion requires sealed holdout and frozen artifacts")
        if not holdout_manifest.matches:
            raise PolicyError("holdout manifest match set is empty")
        if set(holdout_manifest.matches) != set(split_manifest.holdout):
            raise PolicyError("holdout manifest matches do not equal split holdout matches")
        if match_id not in holdout_manifest.matches:
            raise PolicyError("current match is not in the holdout manifest")
        if verify_holdout_freeze:
            holdout_manifest.require_frozen(freeze_hashes)

    exposure_records: tuple[ExposureRecord, ...] = ()
    if split == "holdout":
        if exposure_register_path is None:
            raise PolicyError("Holdout authorization requires an exposure register")
        exposure_records = load_exposure_register(exposure_register_path).for_holdout(
            provider=provider,
            source_revision=source_revision,
            match_ids=tuple(sorted(split_manifest.holdout)),
        )

    return AuthorizedExternalRun(
        policy=policy,
        provider=provider_policy,
        use_permissions={use: provider_policy.uses[use] for use in requested_uses},
        label_profiles=profiles,
        freeze_hashes=freeze_hashes,
        governance_identity=identity,
        use_bases={use: decision.basis for use, decision in decisions.items()},
        scope_ids={use: decision.scope_id for use, decision in decisions.items()},
        exposure_records=exposure_records,
    )


def _find_profile(provider: ProviderPolicy, profile_id: str) -> LabelProfile:
    for profile in provider.label_profiles:
        if profile.provider_label_definition_id == profile_id:
            return profile
    raise PolicyError(f"label profile {profile_id!r} is not registered")


def _sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise PolicyError(f"could not hash governance policy: {path}") from error
    return digest.hexdigest()


def _canonical_json(values: dict[str, Any]) -> bytes:
    return json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _validate_sha256(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise PolicyError(f"{label} is invalid")
