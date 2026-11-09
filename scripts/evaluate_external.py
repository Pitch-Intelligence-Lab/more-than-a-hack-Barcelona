#!/usr/bin/env python3
"""Run an aggregate external proxy comparison for one audited match."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mtah_possession.evaluation.external import (  # noqa: E402
    EvaluationPlan,
    ExternalPredictionBatch,
)
from mtah_possession.evaluation.runner import run_external_evaluation  # noqa: E402
from mtah_possession.evaluation.splits import EvaluationMode  # noqa: E402


def _write_json_atomic(path: Path, values: dict) -> None:
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
    parser.add_argument("--state-config", default=str(ROOT / "configs" / "state-engine.json"))
    parser.add_argument("--splits", default=str(ROOT / "configs" / "external-splits.json"))
    parser.add_argument(
        "--policy",
        default=str(ROOT / "configs" / "policy" / "external-data-policy-v2.1.json"),
    )
    parser.add_argument(
        "--holdout-manifest",
        default=str(ROOT / "configs" / "policy" / "holdout-manifest-v2.json"),
    )
    parser.add_argument(
        "--freeze-spec",
        default=str(ROOT / "configs" / "policy" / "artifact-freeze-v2.json"),
    )
    parser.add_argument(
        "--holdout-ledger-dir",
        default=str(ROOT / "outputs" / "holdout"),
    )
    parser.add_argument(
        "--exposure-register",
        default=str(ROOT / "configs" / "policy" / "exposure-register-v1.json"),
    )
    parser.add_argument("--external-root", default=None)
    parser.add_argument("--source-set", default=None)
    parser.add_argument(
        "--split",
        required=True,
        choices=["development", "validation", "holdout"],
    )
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in EvaluationMode],
        default=EvaluationMode.DIAGNOSTIC.value,
    )
    parser.add_argument("--code-commit", default=os.environ.get("MTAH_CODE_COMMIT"))
    parser.add_argument(
        "--evaluation-plan",
        choices=("full-scored", "tracking-only", "prediction-phase-only"),
        default="full-scored",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    try:
        mode = EvaluationMode(args.mode)
        plan = {
            "full-scored": EvaluationPlan.full_scored,
            "tracking-only": EvaluationPlan.tracking_only,
            "prediction-phase-only": EvaluationPlan.prediction_phase_only,
        }[args.evaluation_plan]()
        plan.validate_for_mode(mode.value)
        external_root = args.external_root or os.environ.get("MTAH_EXTERNAL_DATA_DIR")
        result = run_external_evaluation(
            config_path=args.config,
            state_config_path=args.state_config,
            splits_path=args.splits,
            external_root=external_root,
            split=args.split,
            mode=mode,
            code_commit=args.code_commit or "",
            policy_path=args.policy,
            holdout_manifest_path=args.holdout_manifest,
            freeze_spec_path=args.freeze_spec,
            ledger_dir=args.holdout_ledger_dir,
            source_set_path=args.source_set,
            evaluation_plan=plan,
            exposure_register_path=args.exposure_register,
        )
        _write_json_atomic(Path(args.output), result.report)
    except (OSError, ValueError) as error:
        print(f"FAIL  {error}", file=sys.stderr)
        return 1

    evaluation = result.evaluation
    print(f"match={evaluation.match_id} split={evaluation.split} mode={args.mode}")
    if isinstance(evaluation, ExternalPredictionBatch):
        print(f"prediction_only={len(evaluation.predictions)}")
        for name, prediction in evaluation.predictions.items():
            print(f"{name}: hash={prediction.prediction_sha256}")
    else:
        print(f"proxy={dict(evaluation.proxy.counts)}")
        for name, candidate in evaluation.candidates.items():
            metrics = candidate.metrics
            print(
                f"{name}: macroF1={metrics.macro_f1:.4f} "
                f"segmentF1={metrics.segment_f1_mean:.4f} "
                f"transitionF1={metrics.transition_f1:.4f} "
                f"falseD={metrics.false_dead_frames} "
                f"missedD={metrics.missed_dead_frames} "
                f"switches={metrics.team_switches} "
                f"hash={metrics.prediction_sha256}"
            )
    print(f"report={Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
