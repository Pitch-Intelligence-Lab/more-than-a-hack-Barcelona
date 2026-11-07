import pytest

from mtah_possession.governance.policy import LabelProfile, PolicyError, PolicyStatus
from mtah_possession.governance.providers import (
    group_profiles_by_provider,
    validate_provider_alignment,
)


def profile(
    provider: str,
    definition: str,
    *,
    label_kind: str = "proxy",
    mapping: str = "shared_map",
    version: str = "1",
) -> LabelProfile:
    return LabelProfile(
        provider=provider,
        provider_label_definition_id=definition,
        source_field="possession.group",
        label_kind=label_kind,
        roles=("TRAINING_TARGET",),
        time_basis="frame",
        null_semantics="unknown",
        target_mapping_id=mapping,
        mapping_version=version,
        mapping_evidence=("evidence",),
        status=PolicyStatus.PASS,
    )


def test_profiles_need_complete_shared_mapping() -> None:
    profiles = (profile("a", "a-label"), profile("b", "b-label"))
    validate_provider_alignment(profiles)
    assert set(group_profiles_by_provider(profiles)) == {"a", "b"}


def test_missing_definition_or_mapping_fails() -> None:
    with pytest.raises(PolicyError, match="mapping/version"):
        validate_provider_alignment(
            (
                profile("a", "a-label", mapping="one"),
                profile("b", "b-label", mapping="two"),
            )
        )
    with pytest.raises(PolicyError, match="cannot be merged"):
        validate_provider_alignment(
            (
                profile("a", "a-label", label_kind="truth"),
                profile("b", "b-label", label_kind="proxy"),
            )
        )
