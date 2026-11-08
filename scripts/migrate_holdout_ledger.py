#!/usr/bin/env python3
"""Append an explicit model/governance freeze-protocol migration."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mtah_possession.governance.artifacts import compute_freeze_hashes  # noqa: E402
from mtah_possession.governance.authorization import (  # noqa: E402
    build_governance_identity,
)
from mtah_possession.governance.ledger import (  # noqa: E402
    migrate_legacy_ledger,
    sha256_path_identity,
)
from mtah_possession.validation.submission import sha256_file  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger-dir",
        default=str(ROOT / "outputs" / "holdout"),
    )
    parser.add_argument("--provider", required=True)
    parser.add_argument(
        "--match-id",
        dest="match_ids",
        action="append",
        required=True,
        help="Holdout match ID; repeat for a multi-match holdout.",
    )
    parser.add_argument(
        "--freeze-spec",
        default=str(ROOT / "configs" / "policy" / "artifact-freeze-v2.json"),
    )
    parser.add_argument(
        "--policy",
        default=str(ROOT / "configs" / "policy" / "external-data-policy-v2.json"),
    )
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--holdout-manifest", required=True)
    parser.add_argument("--target-holdout-manifest", required=True)
    parser.add_argument(
        "--split-manifest",
        default=str(ROOT / "configs" / "external-splits.json"),
    )
    parser.add_argument("--approval-receipt", required=True)
    parser.add_argument("--approval-commit", required=True)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--migration-commit", required=True)
    args = parser.parse_args(argv)

    try:
        model_freeze = compute_freeze_hashes(args.freeze_spec)
        governance_identity = build_governance_identity(
            policy_path=args.policy,
            provider=args.provider,
            source_revision=args.source_revision,
        )
        ledger = migrate_legacy_ledger(
            args.ledger_dir,
            repo_root=args.repo_root,
            provider=args.provider,
            match_ids=tuple(args.match_ids),
            model_freeze=model_freeze,
            governance_identity=governance_identity,
            holdout_manifest_sha256=sha256_file(args.holdout_manifest),
            holdout_manifest_path_sha256=sha256_path_identity(args.target_holdout_manifest),
            target_holdout_manifest_sha256=sha256_file(args.target_holdout_manifest),
            split_manifest_sha256=sha256_file(args.split_manifest),
            freeze_spec_sha256=sha256_file(args.freeze_spec),
            policy_sha256=sha256_file(args.policy),
            approval_receipt_path=args.approval_receipt,
            approval_commit=args.approval_commit,
            migration_commit=args.migration_commit,
        )
    except (OSError, ValueError) as error:
        print(f"FAIL  {error}", file=sys.stderr)
        return 1

    print(f"holdout_id={ledger.holdout_id}")
    print(f"state={ledger.state.value}")
    print(f"model_freeze={ledger.model_freeze_hashes()}")
    print(f"ledger={ledger.path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
