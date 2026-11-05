import json
from pathlib import Path

import pytest

from mtah_possession.algorithm_config import (
    AlgorithmConfigError,
    StateEngineConfig,
    load_algorithm_config,
)

ROOT = Path(__file__).resolve().parents[1]
STATE_CONFIG = ROOT / "configs" / "state-engine.json"


def test_state_engine_config_has_sources_and_generic_machine_settings() -> None:
    config = load_algorithm_config(STATE_CONFIG)
    assert isinstance(config, StateEngineConfig)
    assert config.fps == 25
    assert config.expected_frames == 199_319
    assert config.coordinate_representation == "normalized-origin-corner"
    assert config.team_mapping_source == "atd-metadata-order"
    assert config.forced_dead_blocks == ((110_808, 113_741),)
    assert all(parameter.source for parameter in config.parameters.values())
    assert all(parameter.rationale for parameter in config.parameters.values())


def test_unknown_parameter_source_is_rejected(tmp_path: Path) -> None:
    values = json.loads(STATE_CONFIG.read_text(encoding="utf-8"))
    values["parameters"]["candidate_confirmation_s"]["source"] = "target-ground-truth"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(AlgorithmConfigError, match="unknown source"):
        load_algorithm_config(path)


def test_ungraded_blocks_must_be_sorted_and_inside_contract(tmp_path: Path) -> None:
    values = json.loads(STATE_CONFIG.read_text(encoding="utf-8"))
    values["expected_frames"] = 20
    values["ungraded_blocks"] = [[10, 12], [11, 13]]
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(AlgorithmConfigError, match="sorted and non-overlapping"):
        load_algorithm_config(path)


def test_video_and_broadcast_cannot_be_enabled(tmp_path: Path) -> None:
    values = json.loads(STATE_CONFIG.read_text(encoding="utf-8"))
    values["optional_assets"]["broadcast"] = True
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(AlgorithmConfigError, match="not wired"):
        load_algorithm_config(path)


def test_forced_dead_blocks_cannot_overlap_ungraded_blocks(tmp_path: Path) -> None:
    values = json.loads(STATE_CONFIG.read_text(encoding="utf-8"))
    values["forced_dead_blocks"] = [[90_652, 90_700]]
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(AlgorithmConfigError, match="cannot overlap"):
        load_algorithm_config(path)
