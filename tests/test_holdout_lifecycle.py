import pytest

from mtah_possession.governance.holdout import (
    FreezeHashes,
    HoldoutManifest,
    HoldoutStatus,
    SplitAssignment,
)
from mtah_possession.governance.policy import PolicyError


def test_splits_must_not_overlap_or_put_development_match_in_holdout() -> None:
    with pytest.raises(PolicyError, match="overlaps"):
        SplitAssignment(
            development=frozenset({"m1"}),
            validation=frozenset({"m1"}),
            holdout=frozenset({"m2"}),
        ).validate()
    with pytest.raises(PolicyError, match="development-only"):
        SplitAssignment(
            development=frozenset({"2017461"}),
            validation=frozenset({"m2"}),
            holdout=frozenset({"2017461"}),
        ).validate()


def test_vendor_test_split_is_not_project_holdout() -> None:
    splits = SplitAssignment(frozenset(), frozenset(), frozenset())
    with pytest.raises(PolicyError, match="vendor test"):
        splits.assign_vendor_test_as_project_holdout("vendor-test")


def test_sealed_holdout_requires_frozen_identities() -> None:
    sealed = HoldoutManifest.sealed(("holdout-1",))
    with pytest.raises(PolicyError, match="freeze identity"):
        sealed.unseal(
            evaluation_licensed=True,
            exposure_verified=True,
            freeze=FreezeHashes(
                model="",
                feature_set="features",
                configuration="config",
                hyperparameters="params",
                evaluation_script="script",
                metric_contract_version="1",
            ),
            evaluation_independent=True,
        )


def test_holdout_result_used_for_tuning_becomes_compromised() -> None:
    freeze = FreezeHashes(
        model="model",
        feature_set="features",
        configuration="config",
        hyperparameters="params",
        evaluation_script="script",
        metric_contract_version="1",
    )
    sealed = HoldoutManifest.sealed(("holdout-1",), freeze)
    unsealed = sealed.unseal(
        evaluation_licensed=True,
        exposure_verified=True,
        freeze=freeze,
        evaluation_independent=True,
    )
    assert unsealed.status == HoldoutStatus.UNSEALED
    compromised = unsealed.record_result(
        freeze=FreezeHashes(
            model="changed",
            feature_set="features",
            configuration="config",
            hyperparameters="params",
            evaluation_script="script",
            metric_contract_version="1",
        ),
        used_for_tuning=True,
    )
    assert compromised.status == HoldoutStatus.COMPROMISED
