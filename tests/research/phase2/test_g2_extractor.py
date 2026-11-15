from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

import pytest

from mtah_possession.research.phase2.constants import FEATURE_COLUMNS
from mtah_possession.research.phase2.g2 import (
    DYNAMIC_FEATURES,
    G2_COLUMNS,
    G2Error,
    derive_g2,
)

MATCH_ID = "DFL-MAT-J03WMX"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_gzip_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("wb") as raw:
        compressed = gzip.GzipFile(fileobj=raw, mode="wb", mtime=0)
        text = io.TextIOWrapper(compressed, encoding="utf-8", newline="")
        writer = csv.DictWriter(text, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        text.close()
        if not compressed.closed:
            compressed.close()


def _feature_rows(*, negate_signed: bool = False) -> list[dict[str, str]]:
    frame_numbers = list(range(1000, 1030)) + list(range(1040, 1045)) + list(range(2000, 2010))
    rows = []
    for index, frame_number in enumerate(frame_numbers):
        section = "firstHalf" if index < 35 else "secondHalf"
        row = {column: "0" for column in FEATURE_COLUMNS}
        row.update(
            {
                "match_id": MATCH_ID,
                "frame_number": str(frame_number),
                "timestamp_utc": f"2023-05-27T13:{index:02d}:00.000Z",
                "game_section": section,
                "home_team_id": "HOME",
                "away_team_id": "AWAY",
                "home_tracked_n": "11",
                "away_tracked_n": "11",
                "ball_geometry_valid": "true",
            }
        )
        for feature in DYNAMIC_FEATURES:
            value = (
                -index
                if negate_signed
                and feature
                in {
                    "nearest_team_delta_m",
                    "ball_home_centroid_delta_m",
                }
                else index
            )
            row[feature] = str(value)
        if index == 10:
            row["nearest_home_m"] = ""
        rows.append(row)
    return rows


def _make_input(
    root: Path,
    *,
    negate_signed: bool = False,
    columns: tuple[str, ...] = FEATURE_COLUMNS,
    extra_provider: bool = False,
) -> tuple[Path, Path]:
    root.mkdir(parents=True)
    features_path = root / "features.csv.gz"
    rows = _feature_rows(negate_signed=negate_signed)
    if extra_provider:
        columns = (*FEATURE_COLUMNS, "provider_alive")
        for row in rows:
            row["provider_alive"] = "true"
    _write_gzip_csv(features_path, columns, rows)
    metadata_path = root / "metadata.json"
    metadata = {
        "match_id": MATCH_ID,
        "output_schema_version": "P2-FS-0.1",
        "outputs": {
            "features.csv.gz": {
                "bytes": features_path.stat().st_size,
                "sha256": _sha256(features_path),
            }
        },
    }
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return features_path, metadata_path


def _read_g2(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with gzip.open(path, mode="rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def _derive(features: Path, output: Path, *, overwrite: bool = False):
    return derive_g2(features_path=features, output_dir=output, overwrite=overwrite)


def test_delta5_and_delta25_exact_values(tmp_path: Path) -> None:
    features, _ = _make_input(tmp_path / "input")
    output = tmp_path / "output"
    _derive(features, output)
    _, rows = _read_g2(output / "g2_features.csv.gz")
    assert rows[5]["delta5__nearest_home_m"] == "5.000000"
    assert rows[25]["delta25__nearest_home_m"] == "25.000000"
    assert rows[25]["delta5__nearest_home_m"] == "5.000000"


def test_run_starts_and_boundaries_do_not_cross_frames(tmp_path: Path) -> None:
    features, _ = _make_input(tmp_path / "input")
    output = tmp_path / "output"
    result = _derive(features, output)
    _, rows = _read_g2(output / "g2_features.csv.gz")
    assert result["run_count"] == 3
    for index in (0, 5, 30, 35):
        if index < 5:
            assert rows[index]["delta5__nearest_home_m"] == ""
    assert rows[30]["delta5__nearest_home_m"] == ""
    assert rows[35]["delta5__nearest_home_m"] == ""
    metadata = json.loads((output / "g2_metadata.json").read_text(encoding="utf-8"))
    assert metadata["run_count"] == 3
    assert metadata["section_boundary_count"] == 1
    assert metadata["frame_gap_count"] == 1


def test_missing_current_or_historical_values_stay_missing(tmp_path: Path) -> None:
    features, _ = _make_input(tmp_path / "input")
    output = tmp_path / "output"
    _derive(features, output)
    _, rows = _read_g2(output / "g2_features.csv.gz")
    assert rows[10]["delta5__nearest_home_m"] == ""
    assert rows[15]["delta5__nearest_home_m"] == ""
    metadata = json.loads((output / "g2_metadata.json").read_text(encoding="utf-8"))
    assert metadata["missing_counts"]["delta25__nearest_home_m"] == 40


def test_output_schema_order_and_input_order_are_fixed(tmp_path: Path) -> None:
    features, _ = _make_input(tmp_path / "input")
    output = tmp_path / "output"
    result = _derive(features, output)
    columns, rows = _read_g2(output / "g2_features.csv.gz")
    assert columns == list(G2_COLUMNS)
    assert len(rows) == result["rows"] == 45
    assert columns[:3] == ["match_id", "frame_number", "game_section"]
    assert columns[3:18] == [f"delta5__{feature}" for feature in DYNAMIC_FEATURES]
    assert columns[18:] == [f"delta25__{feature}" for feature in DYNAMIC_FEATURES]
    expected_frames = list(range(1000, 1030)) + list(range(1040, 1045)) + list(range(2000, 2010))
    assert [int(row["frame_number"]) for row in rows] == expected_frames


def test_signed_swap_features_change_delta_sign(tmp_path: Path) -> None:
    positive_features, _ = _make_input(tmp_path / "positive")
    negative_features, _ = _make_input(tmp_path / "negative", negate_signed=True)
    positive = _derive(positive_features, tmp_path / "positive-output")
    negative = _derive(negative_features, tmp_path / "negative-output")
    _, positive_rows = _read_g2(Path(positive["output_dir"]) / "g2_features.csv.gz")
    _, negative_rows = _read_g2(Path(negative["output_dir"]) / "g2_features.csv.gz")
    for feature in ("nearest_team_delta_m", "ball_home_centroid_delta_m"):
        column = f"delta5__{feature}"
        assert positive_rows[5][column] == "5.000000"
        assert negative_rows[5][column] == "-5.000000"


def test_repeated_outputs_are_byte_identical(tmp_path: Path) -> None:
    features, _ = _make_input(tmp_path / "input")
    first = _derive(features, tmp_path / "first")
    second = _derive(features, tmp_path / "second")
    assert (tmp_path / "first" / "g2_features.csv.gz").read_bytes() == (
        tmp_path / "second" / "g2_features.csv.gz"
    ).read_bytes()
    assert first["output_sha256"] == second["output_sha256"]


def test_overwrite_defaults_to_reject(tmp_path: Path) -> None:
    features, _ = _make_input(tmp_path / "input")
    output = tmp_path / "output"
    _derive(features, output)
    before = (output / "g2_features.csv.gz").read_bytes()
    with pytest.raises(G2Error, match="already exists"):
        _derive(features, output)
    assert (output / "g2_features.csv.gz").read_bytes() == before


def test_provider_or_reference_columns_fail_schema_validation(tmp_path: Path) -> None:
    features, _ = _make_input(tmp_path / "input", extra_provider=True)
    with pytest.raises(G2Error, match="input feature schema mismatch"):
        _derive(features, tmp_path / "output")


def test_metadata_records_input_and_output_hashes(tmp_path: Path) -> None:
    features, _ = _make_input(tmp_path / "input")
    output = tmp_path / "output"
    result = _derive(features, output)
    metadata = json.loads((output / "g2_metadata.json").read_text(encoding="utf-8"))
    assert metadata["input"]["features_sha256"] == _sha256(features)
    assert metadata["input"]["schema_version"] == "P2-FS-0.1"
    assert metadata["lags"] == [5, 25]
    assert metadata["features"] == list(DYNAMIC_FEATURES)
    assert metadata["outputs"]["g2_features.csv.gz"]["sha256"] == result["output_sha256"]
    assert metadata["outputs"]["g2_features.csv.gz"]["sha256"] == _sha256(
        output / "g2_features.csv.gz"
    )
    assert metadata["repository_head"]
    assert metadata["implementation_commit"]
    assert metadata["source_tree_dirty"] in {True, False}


def test_input_metadata_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    features, metadata_path = _make_input(tmp_path / "input")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["outputs"]["features.csv.gz"]["sha256"] = "0" * 64
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(G2Error, match="does not match metadata"):
        _derive(features, tmp_path / "output")
