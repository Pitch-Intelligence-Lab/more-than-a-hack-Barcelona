import json
from pathlib import Path

import pytest

from mtah_possession.evaluation.splits import (
    SplitManifestError,
    load_split_manifest,
    require_split,
)

ROOT = Path(__file__).resolve().parents[1]


def test_external_split_is_match_level_and_disjoint() -> None:
    manifest = load_split_manifest(ROOT / "configs" / "external-splits.json")
    assert manifest.development == frozenset({"2017461"})
    assert manifest.validation == frozenset()
    assert manifest.holdout == frozenset()
    require_split(manifest, "2017461", "development")


def test_overlapping_splits_are_rejected(tmp_path: Path) -> None:
    values = json.loads((ROOT / "configs" / "external-splits.json").read_text(encoding="utf-8"))
    values["holdout"] = ["2017461"]
    path = tmp_path / "splits.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(SplitManifestError, match="disjoint"):
        load_split_manifest(path)
