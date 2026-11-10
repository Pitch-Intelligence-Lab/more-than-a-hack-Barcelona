import csv
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from tools.cda_v2.package_archives import (
    create_metadata_zip,
    is_cache_path,
    remove_cache_artifacts,
    write_manifest,
)
from tools.cda_v2.readers import StatsBombReader
from tools.cda_v2.reassemble_package import (
    ReassemblyError,
    reassemble,
    safe_member_path,
)
from tools.cda_v2.verify_source_integrity import git_blob_sha1, verify


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _statsbomb_fixture(root: Path) -> StatsBombReader:
    data = root / "data"
    _write_json(
        data / "competitions.json",
        [
            {
                "competition_id": 1,
                "season_id": 2,
                "competition_name": "Fixture League",
                "season_name": "2026",
            }
        ],
    )
    indexed = [{"match_id": match_id} for match_id in range(1, 3962)]
    _write_json(data / "matches" / "1" / "2.json", indexed)
    for match_id in range(5000, 5274):
        _write_json(data / "events" / f"{match_id}.json", [])
    return StatsBombReader(root)


def _tiny_source_zip(path: Path, prefix: str, member: str, payload: bytes) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{prefix}/{member}", payload)


def _tiny_index(archive_root: Path) -> list[dict[str, str | int]]:
    rows = []
    for scope in ("SkillCorner", "IDSSE", "StatsBomb", "Wyscout"):
        name = f"{scope}.zip"
        archive = archive_root / name
        _tiny_source_zip(archive, scope, "fixture.txt", b"raw\n")
        rows.append(
            {
                "archive": name,
                "scope": scope,
                "contents": 1,
                "bytes": archive.stat().st_size,
                "sha256": _sha256(archive),
            }
        )
    metadata = archive_root / "Metadata.zip"
    with zipfile.ZipFile(metadata, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.md", "metadata\n")
    rows.append(
        {
            "archive": "Metadata.zip",
            "scope": "metadata_and_tools",
            "contents": 1,
            "bytes": metadata.stat().st_size,
            "sha256": _sha256(metadata),
        }
    )
    with (archive_root / "ZIP_INDEX.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (archive_root / "MANIFEST.sha256").write_text(
        f"{'0' * 64}  README.md\n",
        encoding="utf-8",
    )
    return rows


def test_hc2_01_02_statsbomb_reader_merges_unknown_event_matches(tmp_path: Path) -> None:
    matches = list(_statsbomb_fixture(tmp_path).matches())
    by_id = {match.match_id: match for match in matches}
    indexed = [match for match in matches if match.competition != "unknown"]
    unindexed = [match for match in matches if match.competition == "unknown"]
    assert len(indexed) == 3961
    assert len(unindexed) == 274
    assert len(matches) == 4235
    assert len(by_id) == len(matches)
    assert unindexed[0].competition_id is None
    assert unindexed[0].season_id is None
    assert unindexed[0].competition == "unknown"
    assert unindexed[0].season == "unknown"
    assert [match.match_id for match in matches] == sorted(by_id)


def test_hc2_03_new_unindexed_event_is_discovered_without_hardcoding(
    tmp_path: Path,
) -> None:
    reader = _statsbomb_fixture(tmp_path)
    before = {match.match_id for match in reader.matches()}
    _write_json(tmp_path / "data" / "events" / "9001.json", [])
    after = {match.match_id for match in reader.matches()}
    assert after.difference(before) == {9001}


def test_hc2_04_05_cache_paths_are_excluded_from_manifest_and_metadata_zip(
    tmp_path: Path,
) -> None:
    delivery = tmp_path / "package"
    readers = delivery / "05_ACCESS_TOOLS" / "SOURCE_READERS" / "cda_v2"
    readers.mkdir(parents=True)
    (readers / "readers.py").write_text("VALUE = 1\n", encoding="utf-8")
    cache = readers / "__pycache__"
    cache.mkdir()
    (cache / "readers.cpython-312.pyc").write_bytes(b"cache")
    (delivery / "README.md").write_text("fixture\n", encoding="utf-8")
    assert is_cache_path(cache / "readers.cpython-312.pyc")
    assert remove_cache_artifacts(delivery) == 2
    write_manifest(delivery)
    assert "__pycache__" not in (delivery / "MANIFEST.sha256").read_text(encoding="utf-8")
    metadata, _count = create_metadata_zip(delivery, tmp_path / "archives")
    with zipfile.ZipFile(metadata) as archive:
        assert not any(
            "__pycache__" in name or name.endswith((".pyc", ".pyo")) for name in archive.namelist()
        )


def test_hc2_06_reader_import_does_not_change_manifest(tmp_path: Path) -> None:
    delivery = tmp_path / "package"
    tools = delivery / "05_ACCESS_TOOLS" / "SOURCE_READERS" / "cda_v2"
    tools.mkdir(parents=True)
    (tools / "readers.py").write_text("VALUE = 1\n", encoding="utf-8")
    (delivery / "README.md").write_text("fixture\n", encoding="utf-8")
    write_manifest(delivery)
    before = (delivery / "MANIFEST.sha256").read_bytes()
    cache = tools / "__pycache__"
    cache.mkdir()
    (cache / "readers.cpython-312.pyc").write_bytes(b"generated")
    write_manifest(delivery)
    assert (delivery / "MANIFEST.sha256").read_bytes() == before


def test_hc2_07_09_10_14_reassembly_maps_sources_and_honors_archive_root(
    tmp_path: Path,
) -> None:
    archive_root = tmp_path / "portable-archives"
    archive_root.mkdir()
    _tiny_index(archive_root)
    output = tmp_path / "empty-output"
    result = reassemble(archive_root=archive_root, output=output)
    assert result["status"] == "PASS"
    for source in ("skillcorner", "idsse", "statsbomb", "wyscout"):
        assert (output / "01_RAW_DATA" / source / "repository" / "fixture.txt").exists()
    assert (output / "README.md").read_text(encoding="utf-8") == "metadata\n"


def test_hc2_08_wrong_archive_sha_is_rejected(tmp_path: Path) -> None:
    archive_root = tmp_path / "archives"
    archive_root.mkdir()
    rows = _tiny_index(archive_root)
    rows[0]["sha256"] = "0" * 64
    with (archive_root / "ZIP_INDEX.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ReassemblyError, match="SHA-256"):
        reassemble(archive_root=archive_root, output=tmp_path / "output")


@pytest.mark.parametrize(
    "member",
    ["../evil", "C:/evil", "C:\\evil", "/absolute", r"SkillCorner\..\evil"],
)
def test_hc2_09_zip_path_traversal_is_rejected(member: str) -> None:
    with pytest.raises(ReassemblyError, match="unsafe"):
        safe_member_path(member)


def test_hc2_11_portable_source_identity_verifies_without_git(tmp_path: Path) -> None:
    package = tmp_path / "package"
    registry = package / "00_SOURCE_REGISTRY"
    trees = registry / "PORTABLE_TREES"
    identities = {}
    for source, key in (
        ("SkillCorner", "skillcorner"),
        ("IDSSE", "idsse"),
        ("StatsBomb", "statsbomb"),
        ("Wyscout", "wyscout"),
    ):
        file = package / "01_RAW_DATA" / key / "repository" / "fixture.txt"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"payload\n")
        tree = {
            "source_url": f"https://example.invalid/{key}",
            "ref": "main",
            "commit": "a" * 40,
            "tree": [
                {
                    "path": "fixture.txt",
                    "size": file.stat().st_size,
                    "git_blob_sha1": git_blob_sha1(file),
                }
            ],
        }
        _write_json(trees / f"{key}.json", tree)
        identities[source] = {
            "commit": tree["commit"],
            "portable_tree": f"00_SOURCE_REGISTRY/PORTABLE_TREES/{key}.json",
        }
    _write_json(registry / "PORTABLE_SOURCE_IDENTITIES.json", identities)
    result = verify(package)
    assert result["status"] == "PASS"
    assert all(result[source]["status"] == "PASS" for source in identities)
    assert not (package / ".git").exists()


def test_hc2_12_zip_index_contains_only_relative_archive_names(tmp_path: Path) -> None:
    archive_root = tmp_path / "archives"
    archive_root.mkdir()
    rows = _tiny_index(archive_root)
    for row in rows:
        assert not Path(row["archive"]).is_absolute()
        assert ":" not in row["archive"]


def test_hc2_13_verify_package_uses_archive_root(tmp_path: Path) -> None:
    archive_root = tmp_path / "relocated-archives"
    archive_root.mkdir()
    _tiny_index(archive_root)
    package = tmp_path / "package"
    required = (
        "README.md",
        "00_SOURCE_REGISTRY/DATA_SOURCE_MASTER.csv",
        "00_SOURCE_REGISTRY/ACCESS_AND_LICENSE.csv",
        "00_SOURCE_REGISTRY/EXCLUDED_AND_DEFERRED.csv",
        "02_MATCH_INVENTORY/MATCH_INVENTORY.csv",
        "03_SCHEMA_DOCUMENTATION/DATA_SCHEMA.md",
        "04_QUALITY_ASSESSMENT/QUALITY_ASSESSMENT.csv",
        "04_QUALITY_ASSESSMENT/QUALITY_REPORT.md",
        "04_QUALITY_ASSESSMENT/FILE_INVENTORY.csv",
        "05_ACCESS_TOOLS/SOURCE_READERS/cda_v2/readers.py",
        "05_ACCESS_TOOLS/BASIC_EXAMPLES/inspect_sources.py",
        "06_HANDOFF/RESEARCHER_QUICKSTART.md",
        "06_HANDOFF/ACQUISITION_LOG.md",
    )
    for relative in required:
        path = package / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
    archive_index = package / "archives" / "ZIP_INDEX.csv"
    archive_index.parent.mkdir(parents=True)
    archive_index.write_bytes((archive_root / "ZIP_INDEX.csv").read_bytes())
    write_manifest(package)
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "tools" / "cda_v2" / "verify_package.py"),
            str(package),
            "--archive-root",
            str(archive_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "PASS"
