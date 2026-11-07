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

from mtah_possession.data.neutral import map_proxy_target  # noqa: E402
from mtah_possession.data.skillcorner import (  # noqa: E402
    load_skillcorner_manifest,
    load_skillcorner_match,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(ROOT / "configs" / "external-skillcorner.json"))
    parser.add_argument("--splits", default=str(ROOT / "configs" / "external-splits.json"))
    parser.add_argument(
        "--policy",
        default=str(ROOT / "configs" / "policy" / "external-data-policy-v2.json"),
    )
    parser.add_argument("--external-root", default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    root = args.external_root or os.environ.get("MTAH_EXTERNAL_DATA_DIR")
    if not root:
        print("FAIL  MTAH_EXTERNAL_DATA_DIR is not set", file=sys.stderr)
        return 1
    try:
        manifest = load_skillcorner_manifest(args.config)
        splits = load_split_manifest(args.splits)
        authorized = authorize_external_run(
            policy_path=args.policy,
            provider=str(manifest["provider"]),
            source_revision=str(manifest["commit"]),
            requested_uses=(
                DataUse.READ_PREPROCESS,
                DataUse.EVALUATION_REFERENCE,
            ),
            label_profile_ids=(
                EVALUATION_POSSESSION_PROFILE,
                EVALUATION_PHASE_PROFILE,
            ),
            required_status_axes=(
                "LABEL_SEMANTICS_ALIGNED",
                "PHASE_SEMANTICS_VERIFIED",
            ),
            split_manifest=splits,
            match_id=str(manifest["match_id"]),
            split="development",
            mode=EvaluationMode.DIAGNOSTIC,
        )
        match = load_skillcorner_match(args.config, root)
        proxy = map_proxy_target(
            match,
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
            "proxy_counts": dict(proxy.counts),
            "proxy_sources": dict(proxy.source_counts),
            "source_checksums": dict(match.source_checksums),
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
        _atomic_json(Path(args.output), report)
    except ValueError as error:
        print(f"FAIL  {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
