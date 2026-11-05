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

from mtah_possession.algorithm_config import load_algorithm_config  # noqa: E402
from mtah_possession.data.skillcorner import load_skillcorner_match  # noqa: E402
from mtah_possession.evaluation.external import evaluate_external_match  # noqa: E402
from mtah_possession.evaluation.splits import (  # noqa: E402
    load_split_manifest,
    require_split,
    split_manifest_dict,
)


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
    parser.add_argument("--external-root", default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    external_root = args.external_root or os.environ.get("MTAH_EXTERNAL_DATA_DIR")
    if not external_root:
        print("FAIL  MTAH_EXTERNAL_DATA_DIR is not set", file=sys.stderr)
        return 1
    try:
        match = load_skillcorner_match(args.config, external_root)
        splits = load_split_manifest(args.splits)
        require_split(splits, match.match_id, "development")
        state_config = load_algorithm_config(args.state_config)
        evaluation = evaluate_external_match(match, state_config, split="development")
        report = evaluation.to_dict()
        report["split_manifest"] = split_manifest_dict(splits, match.match_id)
        _write_json_atomic(Path(args.output), report)
    except (OSError, ValueError) as error:
        print(f"FAIL  {error}", file=sys.stderr)
        return 1

    print(f"match={evaluation.match_id} split={evaluation.split}")
    print(f"proxy={dict(evaluation.proxy.counts)}")
    for name, candidate in evaluation.candidates.items():
        metrics = candidate.metrics
        print(
            f"{name}: macroF1={metrics.macro_f1:.4f} "
            f"segmentF1={metrics.segment_f1_mean:.4f} "
            f"falseD={metrics.false_dead_frames} "
            f"missedD={metrics.missed_dead_frames} "
            f"switches={metrics.team_switches} "
            f"hash={metrics.prediction_sha256}"
        )
    print(f"report={Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
