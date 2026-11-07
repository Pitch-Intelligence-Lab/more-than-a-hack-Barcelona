"""Single fail-closed authorization result for real external-data runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mtah_possession.evaluation.splits import (
    EvaluationMode,
    SplitManifest,
    require_split,
)
from mtah_possession.governance.holdout import (
    FreezeHashes,
    HoldoutManifest,
    SplitAssignment,
)
from mtah_possession.governance.policy import (
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


@dataclass(frozen=True)
class AuthorizedExternalRun:
    policy: ExternalDataPolicy
    provider: ProviderPolicy
    use_permissions: dict[DataUse, UsePermission]
    label_profiles: dict[str, LabelProfile]
    freeze_hashes: FreezeHashes | None


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
) -> AuthorizedExternalRun:
    policy = load_policy(policy_path)
    require_source_identity(policy, provider, source_revision)
    for use in requested_uses:
        require_allowed(
            policy,
            provider,
            use,
            source_revision=source_revision,
        )
    provider_policy = policy.provider(provider)
    for axis in ("LABEL_SEMANTICS_ALIGNED", *required_status_axes):
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
        holdout_manifest.require_frozen(freeze_hashes)

    return AuthorizedExternalRun(
        policy=policy,
        provider=provider_policy,
        use_permissions={use: provider_policy.uses[use] for use in requested_uses},
        label_profiles=profiles,
        freeze_hashes=freeze_hashes,
    )


def _find_profile(provider: ProviderPolicy, profile_id: str) -> LabelProfile:
    for profile in provider.label_profiles:
        if profile.provider_label_definition_id == profile_id:
            return profile
    raise PolicyError(f"label profile {profile_id!r} is not registered")
