from pathlib import Path

import pytest

from mtah_possession.config import (
    ConfigurationError,
    load_settings,
    require_layout,
    require_tactical_assets,
)


def test_environment_variable_resolves_data_root(tmp_path: Path) -> None:
    (tmp_path / "tactical").mkdir()
    (tmp_path / "broadcast").mkdir()
    settings = load_settings(environ={"MTAH_DATA_DIR": str(tmp_path)})
    report = require_layout(settings)
    assert report.valid
    assert settings.tactical_dir == tmp_path / "tactical"


def test_missing_environment_variable_is_clear() -> None:
    with pytest.raises(ConfigurationError, match="MTAH_DATA_DIR is not set"):
        load_settings(environ={})


def test_missing_layout_names_only_paths(tmp_path: Path) -> None:
    settings = load_settings(data_root=tmp_path)
    with pytest.raises(ConfigurationError) as caught:
        require_layout(settings)
    message = str(caught.value)
    assert str(tmp_path / "tactical") in message
    assert str(tmp_path / "broadcast") in message


def test_missing_tactical_asset_does_not_read_content(tmp_path: Path) -> None:
    (tmp_path / "tactical").mkdir()
    (tmp_path / "broadcast").mkdir()
    settings = load_settings(data_root=tmp_path)
    with pytest.raises(ConfigurationError, match="atd_meta"):
        require_tactical_assets(settings)
