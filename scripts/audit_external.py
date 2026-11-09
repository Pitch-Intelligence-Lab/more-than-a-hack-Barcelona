#!/usr/bin/env python3
"""Create an aggregate-only audit report for the audited external match."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mtah_possession.data.neutral import (  # noqa: E402
    map_reference_proxy_target,
    prediction_source_from_match,
)
from mtah_possession.data.skillcorner import (  # noqa: E402
    LoadedSkillCornerSource,
    create_skillcorner_manifest_snapshot,
    load_skillcorner_evaluation_reference,
    load_skillcorner_match_from_snapshot,
)
from mtah_possession.evaluation.splits import (  # noqa: E402
    EvaluationMode,  # noqa: E402
    load_split_manifest,
    split_manifest_dict,
)
from mtah_possession.governance.authorization import (  # noqa: E402
    EVALUATION_PHASE_PROFILE,
    EVALUATION_POSSESSION_PROFILE,
    authorize_external_run,
)
from mtah_possession.governance.policy import (  # noqa: E402
    DataUse,
)
from mtah_possession.governance.source import (  # noqa: E402
    build_source_identity_from_manifest,
)
from mtah_possession.states.phase_layer import (  # noqa: E402
    compile_phase_evidence,
    derive_gap_dead_directives,
)


def _atomic_json(path: Path, values: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(values, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _validate_loaded_source(
    loaded: LoadedSkillCornerSource,
    snapshot,
    expected_source_identity,
):
    if not isinstance(loaded, LoadedSkillCornerSource):
        raise ValueError("audit loader must return an immutable source result")
    if loaded.manifest_snapshot.snapshot_digest != snapshot.snapshot_digest:
        raise ValueError("audit loader manifest snapshot digest does not match")
    if loaded.actual_source_identity != expected_source_identity:
        raise ValueError("audit loader actual Source Identity does not match")
    expected_checksums = {
        "license": expected_source_identity.license_sha256,
        "readme": expected_source_identity.readme_sha256,
        **{
            role: expected_source_identity.files[role]["sha256"]
            for role in ("tracking", "phases", "match")
        },
    }
    if dict(loaded.actual_checksums) != expected_checksums:
        raise ValueError("audit loader actual checksums do not match")
    if loaded.match.match_id != expected_source_identity.match_id:
        raise ValueError("audit loader match ID does not match")
    return loaded.match


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(ROOT / "configs" / "external-skillcorner.json"))
    parser.add_argument("--splits", default=str(ROOT / "configs" / "external-splits.json"))
    parser.add_argument(
        "--policy",
        default=str(ROOT / "configs" / "policy" / "external-data-policy-v2.1.json"),
    )
    parser.add_argument("--external-root", default=None)
    parser.add_argument(
        "--mode",
        choices=("structural", "proxy"),
        default="proxy",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    root = args.external_root or os.environ.get("MTAH_EXTERNAL_DATA_DIR")
    if not root:
        print("FAIL  MTAH_EXTERNAL_DATA_DIR is not set", file=sys.stderr)
        return 1
    try:
        snapshot = create_skillcorner_manifest_snapshot(args.config)
        manifest = snapshot.manifest
        source_identity = build_source_identity_from_manifest(manifest)
        splits = load_split_manifest(args.splits)
        proxy_mode = args.mode == "proxy"
        authorized = authorize_external_run(
            policy_path=args.policy,
            provider=str(manifest["provider"]),
            source_revision=str(manifest["commit"]),
            requested_uses=(
                (
                    DataUse.READ_PREPROCESS,
                    DataUse.EVALUATION_REFERENCE,
                )
                if proxy_mode
                else (DataUse.READ_PREPROCESS,)
            ),
            label_profile_ids=(
                (
                    EVALUATION_POSSESSION_PROFILE,
                    EVALUATION_PHASE_PROFILE,
                )
                if proxy_mode
                else ()
            ),
            required_status_axes=(
                ("LABEL_SEMANTICS_ALIGNED", "PHASE_SEMANTICS_VERIFIED") if proxy_mode else ()
            ),
            split_manifest=splits,
            match_id=str(manifest["match_id"]),
            split="development",
            mode=EvaluationMode.DIAGNOSTIC,
        )
        loaded_source = load_skillcorner_match_from_snapshot(
            snapshot,
            root,
            source_identity,
            read_roles=("license", "readme", "tracking", "phases", "match"),
            parse_reference=False,
        )
        match = _validate_loaded_source(
            loaded_source,
            snapshot,
            source_identity,
        )
        proxy = None
        if proxy_mode:
            reference = load_skillcorner_evaluation_reference(
                loaded_source,
                include_phases=True,
            )
            proxy = map_reference_proxy_target(
                prediction_source_from_match(match),
                reference,
                possession_profile=authorized.label_profiles[EVALUATION_POSSESSION_PROFILE],
                phase_profile=authorized.label_profiles[EVALUATION_PHASE_PROFILE],
            )
        periods = [
            {
                "period": period.period,
                "start_frame": period.start_frame,
                "end_frame": period.end_frame,
                "declared_frames": period.end_frame - period.start_frame,
                "tracking_frames_present": int(
                    match.frame_present[period.start_frame : period.end_frame].sum()
                ),
            }
            for period in match.periods
        ]
        in_play = [False] * match.frame_count
        for phase in match.phases:
            for frame in range(phase.start_frame, phase.end_frame):
                in_play[frame] = True
        directives = derive_gap_dead_directives(
            tuple((period.start_frame, period.end_frame) for period in match.periods),
            tuple((phase.start_frame, phase.end_frame) for phase in match.phases),
            source="skillcorner_phases_of_play_gap",
        )
        phase_evidence = compile_phase_evidence(match.frame_count, match.fps, directives)
        report = {
            "match_id": match.match_id,
            "fps": match.fps,
            "frame_count": match.frame_count,
            "pitch_length_m": match.pitch_length_m,
            "pitch_width_m": match.pitch_width_m,
            "coordinate_convention": match.coordinate_convention,
            "home_team": {"id": match.home_team_id, "name": match.home_team_name},
            "away_team": {"id": match.away_team_id, "name": match.away_team_name},
            "periods": periods,
            "phase_rows": len(match.phases),
            "in_play_frames": sum(in_play),
            "phase_gap_dead_frames": phase_evidence.forced_dead_frames,
            "tracking_frames_present": int(match.frame_present.sum()),
            "tracking_aggregate": dict(match.source_metadata.get("tracking_aggregate", {})),
            "source_checksums": dict(match.source_checksums),
            "source_integrity": {
                "source_identity_sha256": source_identity.source_identity_sha256,
                "source_snapshot_digest": loaded_source.snapshot_digest,
                "actual_checksums": dict(loaded_source.actual_checksums),
            },
            "split": split_manifest_dict(splits, match.match_id),
            "policy_identity": {
                "policy_version": authorized.policy.policy_version,
                "label_profiles": {
                    profile_id: {
                        "target_mapping_id": profile.target_mapping_id,
                        "mapping_version": profile.mapping_version,
                    }
                    for profile_id, profile in authorized.label_profiles.items()
                },
            },
        }
        if proxy is not None:
            report["proxy_counts"] = dict(proxy.counts)
            report["proxy_sources"] = dict(proxy.source_counts)
        report["audit_mode"] = args.mode
        report["observed_uses"] = {
            "declared_uses": [
                DataUse.READ_PREPROCESS.value,
                *([DataUse.EVALUATION_REFERENCE.value] if proxy_mode else []),
            ],
            "runtime_read_roles": list(loaded_source.read_roles),
            "evaluation_reference_read": proxy_mode,
        }
        _atomic_json(Path(args.output), report)
    except ValueError as error:
        print(f"FAIL  {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
