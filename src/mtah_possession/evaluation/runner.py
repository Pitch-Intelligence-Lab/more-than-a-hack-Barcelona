"""Fail-closed orchestration for external evaluation."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass, replace
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
    SplitManifestError,
    load_split_manifest,
    split_manifest_dict,
)
from mtah_possession.governance.artifacts import compute_freeze_hashes
from mtah_possession.governance.authorization import (
    EVALUATION_PHASE_PROFILE,
    EVALUATION_POSSESSION_PROFILE,
    authorize_external_run,
    build_governance_identity,
)
from mtah_possession.governance.holdout import (
    FreezeHashes,
    HoldoutCompromisedError,
    HoldoutManifest,
    load_holdout_manifest,
)
from mtah_possession.governance.ledger import (
    HoldoutLedger,
    HoldoutLedgerState,
    LedgerEvent,
    create_ledger,
    manifest_path_has_conflicting_identity,
    sha256_path_identity,
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
    split_manifest_sha256 = sha256_file(splits_path)
    manifest = load_skillcorner_manifest(config_path)
    provider_name = str(manifest["provider"])
    source_revision = str(manifest["commit"])
    holdout_manifest: HoldoutManifest | None = None
    freeze_hashes: FreezeHashes | None = None
    ledger: HoldoutLedger | None = None
    if mode == EvaluationMode.PROMOTION:
        holdout_manifest = load_holdout_manifest(holdout_manifest_path)
        freeze_hashes = compute_freeze_hashes(freeze_spec_path)
        holdout_manifest_sha256 = sha256_file(holdout_manifest_path)
        holdout_manifest_path_sha256 = sha256_path_identity(holdout_manifest_path)
        if manifest_path_has_conflicting_identity(
            ledger_dir,
            provider=provider_name,
            match_ids=holdout_manifest.matches,
            manifest_path_sha256=holdout_manifest_path_sha256,
        ):
            raise PolicyError("sealed Holdout Manifest path is bound to a different match identity")
        ledger = create_ledger(
            ledger_dir,
            provider=provider_name,
            match_ids=holdout_manifest.matches,
            freeze_hashes=freeze_hashes,
            holdout_manifest_sha256=holdout_manifest_sha256,
            holdout_manifest_path_sha256=holdout_manifest_path_sha256,
            split_manifest_sha256=split_manifest_sha256,
            code_commit=code_commit,
        )
        ledger_state = ledger.state
        if ledger_state == HoldoutLedgerState.COMPROMISED:
            raise PolicyError("holdout ledger is permanently COMPROMISED")
        if ledger_state == HoldoutLedgerState.MIGRATED_AUDIT_ONLY:
            raise PolicyError("migrated holdout ledger is audit-only and cannot promote")
        if ledger_state == HoldoutLedgerState.EVALUATION_COMPLETED:
            raise PolicyError("holdout evaluation is already completed and cannot be reused")
        if ledger_state == HoldoutLedgerState.EVALUATION_RUNNING:
            raise PolicyError("holdout evaluation is already running or indeterminate")
        if ledger.requires_freeze_migration:
            raise PolicyError("legacy holdout ledger requires explicit freeze migration")
        if ledger.requires_split_protocol_reseal:
            raise PolicyError("pre-split holdout ledger requires a new approved seal")
        sealed_manifest_sha256 = ledger.sealed_manifest_sha256()
        if sealed_manifest_sha256 is not None and sealed_manifest_sha256 != holdout_manifest_sha256:
            raise PolicyError("sealed Holdout Manifest SHA-256 has changed")
        sealed_split_sha256 = ledger.sealed_split_manifest_sha256()
        if sealed_split_sha256 is not None and sealed_split_sha256 != split_manifest_sha256:
            raise PolicyError("sealed split manifest SHA-256 has changed")
        sealed_manifest_path_sha256 = ledger.sealed_manifest_path_sha256()
        if (
            sealed_manifest_path_sha256 is not None
            and sealed_manifest_path_sha256 != holdout_manifest_path_sha256
        ):
            raise PolicyError("sealed Holdout Manifest path has changed")
        prior_freeze = ledger.model_freeze_hashes()
        if prior_freeze is not None and prior_freeze != freeze_hashes:
            identity = build_governance_identity(
                policy_path=policy_path,
                provider=provider_name,
                source_revision=source_revision,
            )
            ledger = replace(ledger, governance_identity=identity)
            _append_compromised(
                ledger,
                reason="freeze identity changed after holdout verification",
            )
            raise PolicyError("holdout freeze identity changed after verification")
    governance_identity = build_governance_identity(
        policy_path=policy_path,
        provider=provider_name,
        source_revision=source_revision,
    )
    if ledger is not None:
        ledger = replace(ledger, governance_identity=governance_identity)
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
            governance_identity=governance_identity,
            verify_holdout_freeze=True,
        )
    except HoldoutCompromisedError as error:
        if ledger is not None:
            _append_compromised(ledger, reason=str(error))
        raise
    except (PolicyError, SplitManifestError) as error:
        if ledger is not None and code_commit.strip():
            ledger.append(LedgerEvent.AUTHORIZATION_DENIED, reason=str(error))
        raise
    if not code_commit.strip():
        raise ValueError("code commit is required")
    if not external_root:
        raise ValueError("MTAH_EXTERNAL_DATA_DIR is not set")
    if ledger is not None:
        if not ledger.has_event(LedgerEvent.SEALED_VERIFIED):
            ledger.append(LedgerEvent.SEALED_VERIFIED)
        if not ledger.has_event(LedgerEvent.UNSEALED):
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
        "governance_identity_digest": (authorized.governance_identity.authorization_status_digest),
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
    ledger: HoldoutLedger,
    *,
    reason: str,
) -> None:
    ledger.append(LedgerEvent.COMPROMISED, reason=reason)
