"""Cross-provider label definition validation."""

from __future__ import annotations

from collections import defaultdict

from mtah_possession.governance.policy import LabelProfile, PolicyError, PolicyStatus


def validate_provider_alignment(profiles: tuple[LabelProfile, ...]) -> None:
    if not profiles:
        raise PolicyError("at least one label profile is required")
    for profile in profiles:
        if profile.status != PolicyStatus.PASS:
            raise PolicyError(
                f"label profile {profile.provider_label_definition_id} is {profile.status.value}"
            )
    if len(profiles) == 1:
        return
    mapping_ids = {profile.target_mapping_id for profile in profiles}
    mapping_versions = {profile.mapping_version for profile in profiles}
    label_kinds = {profile.label_kind for profile in profiles}
    if len(mapping_ids) != 1 or len(mapping_versions) != 1:
        raise PolicyError("cross-provider profiles do not share a target mapping/version")
    if len(label_kinds) != 1:
        raise PolicyError("truth, proxy and event-derived labels cannot be merged")
    if any(not profile.mapping_evidence for profile in profiles):
        raise PolicyError("cross-provider mapping evidence is missing")


def group_profiles_by_provider(
    profiles: tuple[LabelProfile, ...],
) -> dict[str, tuple[LabelProfile, ...]]:
    grouped: dict[str, list[LabelProfile]] = defaultdict(list)
    for profile in profiles:
        grouped[profile.provider].append(profile)
    return {provider: tuple(items) for provider, items in grouped.items()}
