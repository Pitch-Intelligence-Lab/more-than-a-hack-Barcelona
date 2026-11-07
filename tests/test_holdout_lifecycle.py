import pytest

from mtah_possession.governance.holdout import (
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
    with pytest.raises(PolicyError, match="frozen identities"):
        sealed.unseal(
            evaluation_licensed=True,
            exposure_verified=True,
            model_freeze="",
            feature_set="features",
            config_freeze="config",
            hyperparameters="params",
            evaluation_script="script",
            metric_contract_version="1",
            evaluation_independent=True,
        )


def test_holdout_result_used_for_tuning_becomes_compromised() -> None:
    sealed = HoldoutManifest.sealed(("holdout-1",))
    unsealed = sealed.unseal(
        evaluation_licensed=True,
        exposure_verified=True,
        model_freeze="model",
        feature_set="features",
        config_freeze="config",
        hyperparameters="params",
        evaluation_script="script",
        metric_contract_version="1",
        evaluation_independent=True,
    )
    assert unsealed.status == HoldoutStatus.UNSEALED
    compromised = unsealed.record_result(
        model_freeze="changed",
        feature_set="features",
        config_freeze="config",
        hyperparameters="params",
        used_for_tuning=True,
    )
    assert compromised.status == HoldoutStatus.COMPROMISED
