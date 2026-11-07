"""Fail-closed orchestration for external evaluation."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
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
    split_manifest_dict,
)
from mtah_possession.governance.artifacts import compute_freeze_hashes
from mtah_possession.governance.authorization import (
    EVALUATION_PHASE_PROFILE,
    EVALUATION_POSSESSION_PROFILE,
    authorize_external_run,
)
from mtah_possession.governance.holdout import (
    FreezeHashes,
    HoldoutManifest,
    load_holdout_manifest,
)
from mtah_possession.governance.ledger import (
    HoldoutLedger,
    LedgerEvent,
    create_ledger,
)
from mtah_possession.governance.policy import (
    DataUse,
    PolicyError,
)
from mtah_possession.validation.submission import sha256_file

DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "policy" / "external-data-policy-v2.json"
)
DEFAULT_HOLDOUT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "policy" / "holdout-manifest-v2.json"
)
DEFAULT_FREEZE_SPEC_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "policy" / "artifact-freeze-v2.json"
)
DEFAULT_LEDGER_DIR = Path(__file__).resolve().parents[3] / "outputs" / "holdout"


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
    policy_path: str | os.PathLike[str] = DEFAULT_POLICY_PATH,
    match_loader: Callable[[str | os.PathLike[str], str | os.PathLike[str]], NeutralMatch] = (
        load_skillcorner_match
    ),
    holdout_manifest_path: str | os.PathLike[str] = DEFAULT_HOLDOUT_MANIFEST_PATH,
    freeze_spec_path: str | os.PathLike[str] = DEFAULT_FREEZE_SPEC_PATH,
    ledger_dir: str | os.PathLike[str] = DEFAULT_LEDGER_DIR,
    state_config_loader: Callable[[str | os.PathLike[str]], StateEngineConfig] = (
        load_algorithm_config
    ),
) -> ExternalRunResult:
    splits = load_split_manifest(splits_path)
    manifest = load_skillcorner_manifest(config_path)
    provider_name = str(manifest["provider"])
    source_revision = str(manifest["commit"])
    holdout_manifest: HoldoutManifest | None = None
    freeze_hashes: FreezeHashes | None = None
    if mode == EvaluationMode.PROMOTION:
        holdout_manifest = load_holdout_manifest(holdout_manifest_path)
        freeze_hashes = compute_freeze_hashes(freeze_spec_path)
    try:
        authorized = authorize_external_run(
            policy_path=policy_path,
            provider=provider_name,
            source_revision=source_revision,
            requested_uses=(
                DataUse.READ_PREPROCESS,
                DataUse.TRACKING_MODEL_INPUT,
                DataUse.PHASE_MODEL_INPUT,
                DataUse.EVALUATION_REFERENCE,
            ),
            label_profile_ids=(
                EVALUATION_POSSESSION_PROFILE,
                EVALUATION_PHASE_PROFILE,
            ),
            split_manifest=splits,
            match_id=str(manifest["match_id"]),
            split=split,
            mode=mode,
            holdout_manifest=holdout_manifest,
            freeze_hashes=freeze_hashes,
        )
    except PolicyError as error:
        if mode == EvaluationMode.PROMOTION and code_commit.strip():
            _append_compromised(
                ledger_dir,
                holdout_manifest=holdout_manifest,
                freeze_hashes=freeze_hashes,
                holdout_manifest_path=holdout_manifest_path,
                code_commit=code_commit,
                reason=str(error),
            )
        raise
    if not code_commit.strip():
        raise ValueError("code commit is required")
    ledger: HoldoutLedger | None = None
    if mode == EvaluationMode.PROMOTION:
        ledger = create_ledger(
            ledger_dir,
            match_ids=holdout_manifest.matches if holdout_manifest is not None else (),
            freeze_hashes=freeze_hashes,
            holdout_manifest_sha256=sha256_file(holdout_manifest_path),
            code_commit=code_commit,
        )
        ledger.append(LedgerEvent.SEALED_VERIFIED)
    if not external_root:
        raise ValueError("MTAH_EXTERNAL_DATA_DIR is not set")
    if ledger is not None:
        ledger.append(LedgerEvent.UNSEALED)
        ledger.append(LedgerEvent.EVALUATION_STARTED)
    try:
        match = match_loader(config_path, external_root)
        state_config = state_config_loader(state_config_path)
        if not isinstance(state_config, StateEngineConfig):
            raise ValueError("external evaluation requires a state-engine configuration")
        evaluation = evaluate_external_match(
            match,
            state_config,
            authorization=authorized,
            split=split,
        )
    except Exception as error:
        if ledger is not None:
            ledger.append(LedgerEvent.EVALUATION_FAILED, reason=type(error).__name__)
        raise
    if ledger is not None:
        prediction_hashes = ":".join(
            candidate.metrics.prediction_sha256 for candidate in evaluation.candidates.values()
        )
        ledger.append(
            LedgerEvent.EVALUATION_COMPLETED,
            prediction_sha256=hashlib.sha256(prediction_hashes.encode()).hexdigest(),
        )
    report = evaluation.to_dict()
    report["split_manifest"] = split_manifest_dict(splits, match.match_id)
    report["policy_identity"] = {
        "policy_version": authorized.policy.policy_version,
        "official_rule_revision": authorized.policy.official_rule_revision,
        "provider": provider_name,
        "source_revision": source_revision,
        "evaluation_reference_status": authorized.use_permissions[
            DataUse.EVALUATION_REFERENCE
        ].status.value,
        "label_profiles": {
            profile_id: {
                "target_mapping_id": profile.target_mapping_id,
                "mapping_version": profile.mapping_version,
                "label_kind": profile.label_kind,
            }
            for profile_id, profile in authorized.label_profiles.items()
        },
    }
    report = report_with_identity(
        report,
        code_commit=code_commit,
        config_version=str(manifest["schema_version"]),
    )
    return ExternalRunResult(evaluation=evaluation, report=report)


def _append_compromised(
    ledger_dir: str | os.PathLike[str],
    *,
    holdout_manifest: HoldoutManifest | None,
    freeze_hashes: FreezeHashes | None,
    holdout_manifest_path: str | os.PathLike[str],
    code_commit: str,
    reason: str,
) -> None:
    if holdout_manifest is None or freeze_hashes is None:
        return
    ledger = create_ledger(
        ledger_dir,
        match_ids=holdout_manifest.matches,
        freeze_hashes=freeze_hashes,
        holdout_manifest_sha256=sha256_file(holdout_manifest_path),
        code_commit=code_commit,
    )
    ledger.append(LedgerEvent.COMPROMISED, reason=reason)
