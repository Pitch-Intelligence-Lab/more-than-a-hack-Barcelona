"""Label-role and ModelInput allowlist enforcement."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import StrEnum
from typing import Any

from mtah_possession.governance.policy import LabelProfile, PolicyError, PolicyStatus


class LabelRole(StrEnum):
    MODEL_INPUT = "MODEL_INPUT"
    TRAINING_TARGET = "TRAINING_TARGET"
    AUXILIARY_TRAINING_TARGET = "AUXILIARY_TRAINING_TARGET"
    EVALUATION_REFERENCE = "EVALUATION_REFERENCE"
    POST_INFERENCE_DIAGNOSTIC = "POST_INFERENCE_DIAGNOSTIC"


MODEL_INPUT_ALLOWLIST = frozenset(
    {
        "match_id",
        "fps",
        "pitch_length_m",
        "pitch_width_m",
        "tracking",
        "event_evidence",
        "frame_count",
        "home_team",
        "away_team",
        "team_by_slot",
        "ball_positions",
        "slot_positions",
        "alignment",
        "slot_speeds",
        "forced_dead_mask",
        "restart_evidence",
        "source_codes",
        "ungraded_mask",
        "expected_frames",
        "first_frame_id",
        "last_frame_id",
        "contiguous",
    }
)

SUSPICIOUS_INPUT_FRAGMENTS = (
    "possession",
    "phase_team",
    "team_in_possession",
    "player_possession",
    "end_x",
    "end_y",
    "event_result",
    "reception_result",
)


def validate_model_input_fields(field_names: list[str] | tuple[str, ...] | set[str]) -> None:
    """Validate exact model-input names using an allowlist and leakage tripwires."""
    normalized = {name.lower() for name in field_names}
    suspicious = sorted(
        name
        for name in normalized
        if any(fragment in name for fragment in SUSPICIOUS_INPUT_FRAGMENTS)
    )
    if suspicious:
        raise PolicyError(f"evaluation-only fields cannot enter ModelInput: {suspicious}")
    leaf_names = {name.split(".")[-1] for name in normalized}
    unknown = sorted(leaf_names.difference({name.lower() for name in MODEL_INPUT_ALLOWLIST}))
    if unknown:
        raise PolicyError(f"fields are not on the ModelInput allowlist: {unknown}")


def model_input_field_names(value: Any, prefix: str = "") -> list[str]:
    names: list[str] = []
    if not is_dataclass(value):
        raise PolicyError("ModelInput validation requires dataclass objects")
    for item in fields(value):
        path = f"{prefix}.{item.name}" if prefix else item.name
        names.append(path)
        child = getattr(value, item.name)
        if is_dataclass(child):
            names.extend(model_input_field_names(child, path))
    return names


def validate_label_role(profile: LabelProfile, role: LabelRole) -> None:
    if profile.status != PolicyStatus.PASS:
        raise PolicyError(
            f"label {profile.provider_label_definition_id} is {profile.status.value}, not PASS"
        )
    if role == LabelRole.MODEL_INPUT:
        raise PolicyError("external possession/phase labels cannot enter ModelInput")
    if role.value not in profile.roles:
        raise PolicyError(
            f"label {profile.provider_label_definition_id} is not approved for {role.value}"
        )
