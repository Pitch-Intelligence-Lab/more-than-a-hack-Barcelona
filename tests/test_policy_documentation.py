import csv
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HISTORICAL_BLOBS = {
    "docs/external-data-audit.md": "1482f7a09cce1ac55aafa17a9d9c68532d89d048",
    "docs/external-evaluation.md": "6e36f81b4f29b6839cb3bf2a738aad5a37b658d1",
    "docs/experiment-log.md": "54f288528f771d64bd4810bf66d418646028f3e9",
    "docs/technical-report.md": "19ef8fcc4c5d28789c4c2e805d2681eef09295e2",
    "docs/engineering-sprint-dp006.md": "356746322f5bb9a20653c20d2ff604f830f80016",
}

OFFICIAL_HASHES = {
    "RULES.md": "3c6edea8f903180212c8dccf7c68ed81e500518d987a1151441ca74b62127db5",
    "FAQ.md": "0bb368bba8fb63f1ce4304b61b0a56268da4711109af8e328d75c55d355affce",
}


def test_official_rule_audit_has_machine_traceability() -> None:
    with (ROOT / "docs" / "policy" / "OFFICIAL_RULE_AUDIT.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "official_repository",
        "official_revision",
        "source_file",
        "line_start",
        "line_end",
        "file_sha256",
        "evidence_id",
        "exact_quote",
        "implication",
        "decision",
    }
    assert rows
    assert set(rows[0]) == required
    evidence_ids = set()
    for row in rows:
        assert row["official_revision"] == "f8f2629ff1e0985f81d7e59d8413678514ee1530"
        assert row["source_file"] in {"RULES.md", "FAQ.md"}
        assert int(row["line_end"]) >= int(row["line_start"]) >= 1
        assert re.fullmatch(r"[0-9a-f]{64}", row["file_sha256"])
        assert row["file_sha256"] == OFFICIAL_HASHES[row["source_file"]]
        assert row["evidence_id"] not in evidence_ids
        assert row["exact_quote"].strip()
        evidence_ids.add(row["evidence_id"])


def test_historical_dp006_blobs_match_frozen_baseline() -> None:
    for relative, expected_blob in HISTORICAL_BLOBS.items():
        actual = subprocess.check_output(
            ["git", "hash-object", relative],
            cwd=ROOT,
            text=True,
        ).strip()
        assert actual == expected_blob, relative
