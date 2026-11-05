"""Match-level external evaluation split validation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class SplitManifestError(ValueError):
    """Raised when external match splits overlap or are malformed."""


class EvaluationMode(StrEnum):
    DIAGNOSTIC = "diagnostic"
    PROMOTION = "promotion"


@dataclass(frozen=True)
class SplitManifest:
    development: frozenset[str]
    validation: frozenset[str]
    holdout: frozenset[str]
    status: str

    def split_for(self, match_id: str) -> str | None:
        normalized = str(match_id)
        for name in ("development", "validation", "holdout"):
            if normalized in getattr(self, name):
                return name
        return None


@dataclass(frozen=True)
class PromotionGateResult:
    allowed: bool
    reasons: tuple[str, ...]


def load_split_manifest(path: str | os.PathLike[str]) -> SplitManifest:
    try:
        values = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SplitManifestError("could not read external split manifest") from error
    required = {
        "schema_version",
        "split_unit",
        "development",
        "validation",
        "holdout",
        "status",
        "reason",
    }
    if not isinstance(values, dict) or set(values) != required:
        raise SplitManifestError("split manifest has missing or unknown keys")
    if values["schema_version"] != "1.0" or values["split_unit"] != "match":
        raise SplitManifestError("split manifest must be schema 1.0 and match-level")
    sets = {}
    for name in ("development", "validation", "holdout"):
        raw = values[name]
        if not isinstance(raw, list) or not all(isinstance(value, str) for value in raw):
            raise SplitManifestError(f"{name} must be a string list")
        if len(set(raw)) != len(raw):
            raise SplitManifestError(f"{name} contains duplicate matches")
        sets[name] = frozenset(raw)
    if (
        sets["development"] & sets["validation"]
        or sets["development"] & sets["holdout"]
        or sets["validation"] & sets["holdout"]
    ):
        raise SplitManifestError("external match splits must be disjoint")
    return SplitManifest(
        development=sets["development"],
        validation=sets["validation"],
        holdout=sets["holdout"],
        status=str(values["status"]),
    )


def assess_promotion_gate(manifest: SplitManifest) -> PromotionGateResult:
    reasons: list[str] = []
    if not manifest.development:
        reasons.append("development split is empty")
    if not manifest.validation:
        reasons.append("validation split is empty")
    if not manifest.holdout:
        reasons.append("holdout split is empty")
    if manifest.status != "ready_for_validation":
        reasons.append("status is not ready_for_validation")
    return PromotionGateResult(allowed=not reasons, reasons=tuple(reasons))


def require_promotion_ready(manifest: SplitManifest) -> None:
    gate = assess_promotion_gate(manifest)
    if not gate.allowed:
        raise SplitManifestError("promotion gate failed: " + "; ".join(gate.reasons))


def require_split(
    manifest: SplitManifest,
    match_id: str,
    expected: str,
    *,
    mode: EvaluationMode = EvaluationMode.DIAGNOSTIC,
) -> None:
    if mode == EvaluationMode.PROMOTION:
        require_promotion_ready(manifest)
    elif mode != EvaluationMode.DIAGNOSTIC:
        raise SplitManifestError(f"unknown evaluation mode: {mode!r}")
    actual = manifest.split_for(match_id)
    if actual != expected:
        raise SplitManifestError(
            f"match {match_id} belongs to {actual or 'no split'}, not {expected}"
        )


def split_manifest_dict(manifest: SplitManifest, match_id: str) -> dict[str, Any]:
    return {
        "match_id": match_id,
        "split": manifest.split_for(match_id),
        "development": sorted(manifest.development),
        "validation": sorted(manifest.validation),
        "holdout": sorted(manifest.holdout),
        "status": manifest.status,
    }
