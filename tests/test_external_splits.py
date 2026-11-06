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
    require_validation_ready,
)

ROOT = Path(__file__).resolve().parents[1]


def test_external_split_is_match_level_and_disjoint() -> None:
    manifest = load_split_manifest(ROOT / "configs" / "external-splits.json")
    assert manifest.development == frozenset({"2017461"})
    assert manifest.validation == frozenset()
    assert manifest.holdout == frozenset()
    assert manifest.status == "diagnostic_only"
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
        status="ready_for_promotion_review",
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
            "--split",
            "holdout",
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


def test_ready_for_validation_does_not_authorize_promotion() -> None:
    manifest = SplitManifest(
        development=frozenset({"dev-1"}),
        validation=frozenset({"val-1"}),
        holdout=frozenset({"holdout-1"}),
        status="ready_for_validation",
    )
    require_validation_ready(manifest)
    with pytest.raises(SplitManifestError, match="not ready_for_promotion_review"):
        require_promotion_ready(manifest)


def test_validation_and_holdout_selection_are_explicit() -> None:
    validation_ready = SplitManifest(
        development=frozenset({"dev-1"}),
        validation=frozenset({"val-1"}),
        holdout=frozenset({"holdout-1"}),
        status="ready_for_validation",
    )
    require_split(
        validation_ready,
        "val-1",
        "validation",
        mode=EvaluationMode.VALIDATION,
    )
    promotion_ready = SplitManifest(
        development=frozenset({"dev-1"}),
        validation=frozenset({"val-1"}),
        holdout=frozenset({"holdout-1"}),
        status="ready_for_promotion_review",
    )
    require_split(
        promotion_ready,
        "holdout-1",
        "holdout",
        mode=EvaluationMode.PROMOTION,
    )
    with pytest.raises(SplitManifestError, match="requires split"):
        require_split(
            promotion_ready,
            "holdout-1",
            "validation",
            mode=EvaluationMode.PROMOTION,
        )
    with pytest.raises(SplitManifestError, match="belongs to development"):
        require_split(
            promotion_ready,
            "dev-1",
            "holdout",
            mode=EvaluationMode.PROMOTION,
        )


def test_empty_validation_or_holdout_fails_promotion() -> None:
    base = {
        "development": frozenset({"dev-1"}),
        "validation": frozenset({"val-1"}),
        "holdout": frozenset({"holdout-1"}),
        "status": "ready_for_promotion_review",
    }
    assert assess_promotion_gate(SplitManifest(**base)).allowed
    assert not assess_promotion_gate(SplitManifest(**{**base, "validation": frozenset()})).allowed
    assert not assess_promotion_gate(SplitManifest(**{**base, "holdout": frozenset()})).allowed


def test_duplicate_match_ids_and_invalid_status_are_rejected(tmp_path: Path) -> None:
    values = json.loads((ROOT / "configs" / "external-splits.json").read_text(encoding="utf-8"))
    values["development"] = ["same", "same"]
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(SplitManifestError, match="duplicate"):
        load_split_manifest(path)

    values = json.loads((ROOT / "configs" / "external-splits.json").read_text(encoding="utf-8"))
    values["status"] = "ready_for_badness"
    path = tmp_path / "invalid-status.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(SplitManifestError, match="unknown lifecycle status"):
        load_split_manifest(path)


def test_cli_requires_split_and_rejects_invalid_split(tmp_path: Path) -> None:
    missing = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "evaluate_external.py"),
            "--output",
            str(tmp_path / "missing.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing.returncode == 2
    invalid = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "evaluate_external.py"),
            "--split",
            "test",
            "--output",
            str(tmp_path / "invalid.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert invalid.returncode == 2
