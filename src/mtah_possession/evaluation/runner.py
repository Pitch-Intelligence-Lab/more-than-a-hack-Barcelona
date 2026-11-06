"""Fail-closed orchestration for external evaluation."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from mtah_possession.algorithm_config import StateEngineConfig, load_algorithm_config
from mtah_possession.data.neutral import NeutralMatch
from mtah_possession.data.skillcorner import (
    load_skillcorner_manifest,
    load_skillcorner_match,
)
from mtah_possession.evaluation.external import (
    ExternalMatchEvaluation,
    evaluate_external_match,
)
from mtah_possession.evaluation.provenance import report_with_identity
from mtah_possession.evaluation.splits import (
    EvaluationMode,
    load_split_manifest,
    require_split,
    split_manifest_dict,
)


@dataclass(frozen=True)
class ExternalRunResult:
    evaluation: ExternalMatchEvaluation
    report: dict[str, Any]


def run_external_evaluation(
    *,
    config_path: str | os.PathLike[str],
    state_config_path: str | os.PathLike[str],
    splits_path: str | os.PathLike[str],
    external_root: str | os.PathLike[str] | None,
    split: str,
    mode: EvaluationMode,
    code_commit: str,
    match_loader: Callable[[str | os.PathLike[str], str | os.PathLike[str]], NeutralMatch] = (
        load_skillcorner_match
    ),
    state_config_loader: Callable[[str | os.PathLike[str]], StateEngineConfig] = (
        load_algorithm_config
    ),
) -> ExternalRunResult:
    splits = load_split_manifest(splits_path)
    manifest = load_skillcorner_manifest(config_path)
    require_split(
        splits,
        str(manifest["match_id"]),
        split,
        mode=mode,
    )
    if not external_root:
        raise ValueError("MTAH_EXTERNAL_DATA_DIR is not set")
    if not code_commit.strip():
        raise ValueError("code commit is required")

    match = match_loader(config_path, external_root)
    state_config = state_config_loader(state_config_path)
    if not isinstance(state_config, StateEngineConfig):
        raise ValueError("external evaluation requires a state-engine configuration")
    evaluation = evaluate_external_match(match, state_config, split=split)
    report = evaluation.to_dict()
    report["split_manifest"] = split_manifest_dict(splits, match.match_id)
    report = report_with_identity(
        report,
        code_commit=code_commit,
        config_version=str(manifest["schema_version"]),
    )
    return ExternalRunResult(evaluation=evaluation, report=report)
