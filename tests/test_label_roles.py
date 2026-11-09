import numpy as np
import pytest

from mtah_possession.data.model_input import AllowedEventEvidence, ModelInput
from mtah_possession.data.tracking import FrameAlignment, TrackingData
from mtah_possession.governance.policy import LabelProfile, PolicyError, PolicyStatus
from mtah_possession.governance.roles import (
    LabelRole,
    model_input_field_names,
    validate_label_role,
    validate_model_input_fields,
)


def model_input() -> ModelInput:
    tracking = TrackingData(
        frame_count=1,
        home_team="H",
        away_team="A",
        team_by_slot=np.asarray([0, 1], dtype=np.int8),
        ball_positions=np.zeros((1, 2), dtype=np.float32),
        slot_positions=np.zeros((1, 2, 2), dtype=np.float32),
        alignment=FrameAlignment(1, 1, 1, True),
    )
    return ModelInput(
        match_id="fixture",
        fps=10,
        pitch_length_m=105.0,
        pitch_width_m=68.0,
        tracking=tracking,
        event_evidence=AllowedEventEvidence.empty(1),
    )


def test_existing_model_input_fields_pass_allowlist() -> None:
    validate_model_input_fields(model_input_field_names(model_input()))


@pytest.mark.parametrize(
    "field",
    [
        "possession_group",
        "possession_player_id",
        "team_in_possession",
        "player_possession_count",
        "phase_team",
        "event_end_x",
        "event_result",
    ],
)
def test_possession_phase_and_future_variants_are_rejected(field: str) -> None:
    with pytest.raises(PolicyError):
        validate_model_input_fields([field])


def test_label_role_profile_requires_pass_and_allowed_role() -> None:
    profile = LabelProfile(
        provider="fixture",
        provider_label_definition_id="fixture_target",
        source_field="possession.group",
        label_kind="proxy",
        roles=("TRAINING_TARGET", "EVALUATION_REFERENCE"),
        time_basis="frame",
        null_semantics="unknown",
        target_mapping_id="mapping",
        mapping_version="1",
        mapping_evidence=("evidence",),
        status=PolicyStatus.PASS,
    )
    validate_label_role(profile, LabelRole.TRAINING_TARGET)
    with pytest.raises(PolicyError, match="cannot enter ModelInput"):
        validate_label_role(profile, LabelRole.MODEL_INPUT)


def test_hold_label_role_is_rejected() -> None:
    profile = LabelProfile(
        provider="fixture",
        provider_label_definition_id="fixture_target",
        source_field="possession.group",
        label_kind="proxy",
        roles=("TRAINING_TARGET",),
        time_basis="frame",
        null_semantics="unknown",
        target_mapping_id="mapping",
        mapping_version="1",
        mapping_evidence=("evidence",),
        status=PolicyStatus.HOLD,
    )
    with pytest.raises(PolicyError, match="HOLD"):
        validate_label_role(profile, LabelRole.TRAINING_TARGET)
