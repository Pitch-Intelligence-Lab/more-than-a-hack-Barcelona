import json
import subprocess
import sys
from pathlib import Path

import pytest

from mtah_possession.evaluation.splits import (
    EvaluationMode,
    SplitManifest,
    SplitManifestError,
    assess_promotion_gate,
    load_split_manifest,
    require_promotion_ready,
    require_split,
)

ROOT = Path(__file__).resolve().parents[1]


def test_external_split_is_match_level_and_disjoint() -> None:
    manifest = load_split_manifest(ROOT / "configs" / "external-splits.json")
    assert manifest.development == frozenset({"2017461"})
    assert manifest.validation == frozenset()
    assert manifest.holdout == frozenset()
    require_split(manifest, "2017461", "development")
    require_split(
        manifest,
        "2017461",
        "development",
        mode=EvaluationMode.DIAGNOSTIC,
    )


def test_overlapping_splits_are_rejected(tmp_path: Path) -> None:
    values = json.loads((ROOT / "configs" / "external-splits.json").read_text(encoding="utf-8"))
    values["holdout"] = ["2017461"]
    path = tmp_path / "splits.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(SplitManifestError, match="disjoint"):
        load_split_manifest(path)


def test_one_match_manifest_cannot_pass_promotion_gate() -> None:
    manifest = load_split_manifest(ROOT / "configs" / "external-splits.json")
    gate = assess_promotion_gate(manifest)
    assert gate.allowed is False
    assert "validation split is empty" in gate.reasons
    assert "holdout split is empty" in gate.reasons
    with pytest.raises(SplitManifestError, match="promotion gate failed"):
        require_promotion_ready(manifest)
    with pytest.raises(SplitManifestError, match="promotion gate failed"):
        require_split(
            manifest,
            "2017461",
            "holdout",
            mode=EvaluationMode.PROMOTION,
        )


def test_complete_ready_manifest_passes_promotion_gate() -> None:
    manifest = SplitManifest(
        development=frozenset({"dev-1"}),
        validation=frozenset({"val-1"}),
        holdout=frozenset({"holdout-1"}),
        status="ready_for_validation",
    )
    gate = assess_promotion_gate(manifest)
    assert gate.allowed is True
    assert gate.reasons == ()
    require_promotion_ready(manifest)


def test_promotion_cli_rejects_single_match_before_external_access(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "evaluate_external.py"),
            "--mode",
            "promotion",
            "--output",
            str(tmp_path / "should-not-exist.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "promotion gate failed" in result.stderr
    assert "MTAH_EXTERNAL_DATA_DIR" not in result.stderr
    assert not (tmp_path / "should-not-exist.json").exists()
