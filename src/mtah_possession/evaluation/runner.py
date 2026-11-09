"""Fail-closed orchestration for external evaluation."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from mtah_possession.algorithm_config import StateEngineConfig, load_algorithm_config
from mtah_possession.data.skillcorner import (
    LoadedSkillCornerSource,
    SkillCornerDataError,
    SkillCornerManifestSnapshot,
    create_skillcorner_manifest_snapshot,
    load_skillcorner_match_from_snapshot,
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
    MatchLedgerState,
    create_ledger,
    manifest_path_has_conflicting_identity,
    sha256_path_identity,
)
from mtah_possession.governance.policy import (
    DataUse,
    PolicyError,
)
from mtah_possession.governance.source import (
    SourceIdentity,
    build_single_source_identity_set,
    build_source_identity_from_manifest,
    build_source_identity_set,
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
    match_loader: Callable[
        [
            SkillCornerManifestSnapshot,
            str | os.PathLike[str],
            SourceIdentity,
        ],
        LoadedSkillCornerSource,
    ] = load_skillcorner_match_from_snapshot,
    holdout_manifest_path: str | os.PathLike[str] = DEFAULT_HOLDOUT_MANIFEST_PATH,
    freeze_spec_path: str | os.PathLike[str] = DEFAULT_FREEZE_SPEC_PATH,
    ledger_dir: str | os.PathLike[str] = DEFAULT_LEDGER_DIR,
    source_set_path: str | os.PathLike[str] | None = None,
    state_config_loader: Callable[[str | os.PathLike[str]], StateEngineConfig] = (
        load_algorithm_config
    ),
) -> ExternalRunResult:
    splits = load_split_manifest(splits_path)
    split_manifest_sha256 = sha256_file(splits_path)
    manifest_snapshot = create_skillcorner_manifest_snapshot(config_path)
    manifest = manifest_snapshot.manifest
    snapshot_source_identity = build_source_identity_from_manifest(manifest)
    provider_name = str(manifest["provider"])
    source_revision = str(manifest["commit"])
    holdout_manifest: HoldoutManifest | None = None
    freeze_hashes: FreezeHashes | None = None
    ledger: HoldoutLedger | None = None
    if mode == EvaluationMode.PROMOTION:
        holdout_manifest = load_holdout_manifest(holdout_manifest_path)
        current_match_id = str(manifest["match_id"])
        freeze_hashes = compute_freeze_hashes(freeze_spec_path)
        holdout_manifest_sha256 = sha256_file(holdout_manifest_path)
        holdout_manifest_path_sha256 = sha256_path_identity(holdout_manifest_path)
        holdout_matches_are_valid = (
            bool(holdout_manifest.matches)
            and set(holdout_manifest.matches) == set(splits.holdout)
            and str(manifest["match_id"]) in holdout_manifest.matches
        )
        source_set = None
        source_identity = None
        source_error: PolicyError | None = None
        if holdout_matches_are_valid:
            try:
                if source_set_path is not None:
                    source_root = _source_set_root(source_set_path)
                    source_set = build_source_identity_set(
                        source_set_path,
                        provider=provider_name,
                        holdout_matches=holdout_manifest.matches,
                        source_root=source_root,
                        identity_overrides={
                            str(manifest["match_id"]): snapshot_source_identity,
                        },
                    )
                    source_identity = source_set.identities[str(manifest["match_id"])]
                    member = next(
                        member
                        for member in source_set.members
                        if member["match_id"] == str(manifest["match_id"])
                    )
                    expected_config = (source_root / member["source_config"]).resolve(strict=False)
                    if expected_config.as_posix() != manifest_snapshot.source_path:
                        raise PolicyError("current source config does not match SourceIdentitySet")
                else:
                    if len(holdout_manifest.matches) != 1:
                        raise PolicyError("multi-match Holdout requires a source-set descriptor")
                    source_set = build_single_source_identity_set(
                        provider=provider_name,
                        match_id=str(manifest["match_id"]),
                        source_config=config_path,
                        identity_override=snapshot_source_identity,
                    )
                    source_identity = source_set.identities[str(manifest["match_id"])]
            except PolicyError as error:
                source_error = error
            if manifest_path_has_conflicting_identity(
                ledger_dir,
                provider=provider_name,
                match_ids=holdout_manifest.matches,
                manifest_path_sha256=holdout_manifest_path_sha256,
            ):
                raise PolicyError(
                    "sealed Holdout Manifest path is bound to a different match identity"
                )
        ledger = create_ledger(
            ledger_dir,
            provider=provider_name,
            match_ids=holdout_manifest.matches,
            freeze_hashes=freeze_hashes,
            holdout_manifest_sha256=holdout_manifest_sha256,
            holdout_manifest_path_sha256=holdout_manifest_path_sha256,
            split_manifest_sha256=split_manifest_sha256,
            code_commit=code_commit,
            source_identity=source_identity,
            source_identity_set=source_set,
        )
        ledger_state = ledger.state
        if ledger_state == HoldoutLedgerState.COMPROMISED:
            raise PolicyError("holdout ledger is permanently COMPROMISED")
        if ledger_state == HoldoutLedgerState.MIGRATED_AUDIT_ONLY:
            raise PolicyError("migrated holdout ledger is audit-only and cannot promote")
        if ledger.requires_freeze_migration:
            raise PolicyError("legacy holdout ledger requires explicit freeze migration")
        if ledger.requires_split_protocol_reseal:
            raise PolicyError("pre-split holdout ledger requires a new approved seal")
        if ledger.requires_source_protocol_reseal:
            raise PolicyError("pre-source holdout ledger requires a new approved seal")
        if ledger_state == HoldoutLedgerState.COMPLETED:
            raise PolicyError("holdout evaluation is already completed and cannot be reused")
        sealed_manifest_sha256 = ledger.sealed_manifest_sha256()
        if sealed_manifest_sha256 is not None and sealed_manifest_sha256 != holdout_manifest_sha256:
            raise PolicyError("sealed Holdout Manifest SHA-256 has changed")
        sealed_split_sha256 = ledger.sealed_split_manifest_sha256()
        if sealed_split_sha256 is not None and sealed_split_sha256 != split_manifest_sha256:
            raise PolicyError("changed sealed split manifest SHA-256")
        sealed_manifest_path_sha256 = ledger.sealed_manifest_path_sha256()
        if (
            sealed_manifest_path_sha256 is not None
            and sealed_manifest_path_sha256 != holdout_manifest_path_sha256
        ):
            raise PolicyError("sealed Holdout Manifest path has changed")
        sealed_source_set = ledger.sealed_source_identity_set()
        if (
            source_set is not None
            and sealed_source_set is not None
            and (
                sealed_source_set.provider != source_set.provider
                or sealed_source_set.members != source_set.members
                or sealed_source_set.source_set_sha256 != source_set.source_set_sha256
                or sealed_source_set.identity_digests != source_set.identity_digests
            )
        ):
            raise PolicyError("sealed Source Identity set has changed")
        prior_freeze = ledger.model_freeze_hashes()
        if prior_freeze is not None and prior_freeze != freeze_hashes:
            if source_identity is None or source_set is None:
                raise source_error or PolicyError("holdout Source Identity is unavailable")
            identity = build_governance_identity(
                policy_path=policy_path,
                provider=provider_name,
                source_revision=source_revision,
            )
            ledger = replace(
                ledger,
                governance_identity=identity,
                source_identity=source_identity,
                source_identity_set=source_set,
            )
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
    if mode != EvaluationMode.PROMOTION:
        source_set = build_single_source_identity_set(
            provider=provider_name,
            match_id=str(manifest["match_id"]),
            source_config=config_path,
            identity_override=snapshot_source_identity,
        )
        source_identity = source_set.identities[str(manifest["match_id"])]
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
        if (
            ledger is not None
            and code_commit.strip()
            and source_identity is not None
            and source_set is not None
        ):
            ledger = replace(
                ledger,
                governance_identity=governance_identity,
                source_identity=source_identity,
                source_identity_set=source_set,
            )
            ledger.append(
                LedgerEvent.AUTHORIZATION_DENIED,
                match_id=str(manifest["match_id"]),
                reason=str(error),
            )
        raise
    if not code_commit.strip():
        raise ValueError("code commit is required")
    if not external_root:
        raise ValueError("MTAH_EXTERNAL_DATA_DIR is not set")
    if source_identity is None or source_set is None:
        raise source_error or PolicyError("holdout Source Identity is unavailable")
    if ledger is not None:
        member_state = ledger.match_state(current_match_id)
        if member_state == MatchLedgerState.RUNNING:
            raise PolicyError(f"match {current_match_id} evaluation is already running")
        if member_state == MatchLedgerState.COMPLETED:
            raise PolicyError(f"match {current_match_id} evaluation is already completed")
    if ledger is not None:
        if not ledger.has_event(LedgerEvent.SEALED_VERIFIED):
            ledger.append(LedgerEvent.SEALED_VERIFIED)
        if not ledger.has_event(LedgerEvent.UNSEALED):
            ledger.append(LedgerEvent.UNSEALED)
        ledger.append(
            LedgerEvent.EVALUATION_STARTED,
            match_id=str(manifest["match_id"]),
        )
    try:
        loaded_source = match_loader(
            manifest_snapshot,
            external_root,
            source_identity,
        )
        if not isinstance(loaded_source, LoadedSkillCornerSource):
            raise SkillCornerDataError(
                "external loader must return an immutable SkillCorner source result"
            )
        if loaded_source.manifest_snapshot.snapshot_digest != manifest_snapshot.snapshot_digest:
            raise SkillCornerDataError("loader manifest snapshot digest does not match")
        if loaded_source.actual_source_identity != source_identity:
            raise SkillCornerDataError("loader actual Source Identity does not match the seal")
        expected_checksums = {
            "license": source_identity.license_sha256,
            "readme": source_identity.readme_sha256,
            **{
                role: source_identity.files[role]["sha256"]
                for role in ("tracking", "phases", "match")
            },
        }
        if dict(loaded_source.actual_checksums) != expected_checksums:
            raise SkillCornerDataError("loader actual checksums do not match the seal")
        if loaded_source.match.match_id != source_identity.match_id:
            raise SkillCornerDataError("loader match ID does not match the sealed source")
        match = loaded_source.match
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
            ledger.append(
                LedgerEvent.EVALUATION_FAILED,
                match_id=str(manifest["match_id"]),
                reason=type(error).__name__,
            )
        raise
    if ledger is not None:
        prediction_hashes = ":".join(
            candidate.metrics.prediction_sha256 for candidate in evaluation.candidates.values()
        )
        ledger.append(
            LedgerEvent.EVALUATION_COMPLETED,
            match_id=str(manifest["match_id"]),
            prediction_sha256=hashlib.sha256(prediction_hashes.encode()).hexdigest(),
        )
    report = evaluation.to_dict()
    report["source_integrity"] = {
        "source_identity_sha256": source_identity.source_identity_sha256,
        "source_snapshot_digest": loaded_source.snapshot_digest,
        "actual_checksums": dict(loaded_source.actual_checksums),
    }
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


def _source_set_root(descriptor_path: str | os.PathLike[str]) -> Path:
    path = Path(descriptor_path).resolve(strict=True)
    for parent in path.parents:
        if (parent / ".git").exists():
            return parent
    return path.parent
