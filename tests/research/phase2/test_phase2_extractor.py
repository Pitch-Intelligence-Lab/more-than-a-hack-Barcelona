from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from mtah_possession.research.phase2.constants import (
    ALL_MATCH_IDS,
    FEATURE_COLUMNS,
    REFERENCE_COLUMNS,
)
from mtah_possession.research.phase2.extractor import (
    ExtractionError,
    extract_idss,
    load_split_config,
    read_ball_timeline,
)
from mtah_possession.research.phase2.geometry import (
    event_xy_to_centered,
    swap_feature_sides,
)

MATCH_ID = "DFL-MAT-J03WMX"
HOME_ID = "DFL-CLU-HOME"
AWAY_ID = "DFL-CLU-AWAY"
SPLIT_CONFIG = (
    Path(__file__).resolve().parents[3] / "configs" / "research" / "phase2" / "idss_split.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metadata_xml(match_id: str = MATCH_ID) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<PutDataRequest>
  <MatchInformation>
    <General CompetitionName="Bundesliga" Season="2022/2023" MatchId="{match_id}" />
    <Environment PitchX="105.00" PitchY="68.00" />
    <Teams>
      <Team TeamId="{AWAY_ID}" Role="guest" />
      <Team TeamId="{HOME_ID}" Role="home" />
    </Teams>
  </MatchInformation>
</PutDataRequest>
"""


def _frame(
    frame_number: int,
    x: float,
    y: float,
    *,
    ball: bool,
    status: int,
    possession: int,
    marker: int = 1,
) -> str:
    suffix = f' BallPossession="{possession}" BallStatus="{status}"' if ball else f' M="{marker}"'
    return (
        f'<Frame N="{frame_number}" T="2023-05-27T13:30:{frame_number % 60:02d}.000+00:00" '
        f'X="{x}" Y="{y}" D="0.00" S="0.00" A="0.00"{suffix}/>'
    )


def _tracking_xml(
    *,
    match_id: str = MATCH_ID,
    ball_frames: tuple[tuple[float, float], tuple[float, float]] = (
        (0.0, 0.0),
        (1.0, 1.0),
    ),
    statuses: tuple[int, int] = (1, 0),
    possessions: tuple[int, int] = (1, 2),
    home_players: dict[str, tuple[tuple[float, float], tuple[float, float]]] | None = None,
    away_players: dict[str, tuple[tuple[float, float], tuple[float, float]]] | None = None,
    marker: int = 1,
) -> str:
    home_players = home_players or {
        "HOME-1": ((-1.0, 0.0), (-2.0, 0.0)),
        "HOME-2": ((-3.0, 0.0), (-4.0, 0.0)),
    }
    away_players = away_players or {
        "AWAY-1": ((2.0, 0.0), (3.0, 0.0)),
        "AWAY-2": ((4.0, 0.0), (5.0, 0.0)),
    }
    frame_numbers = (100, 200)
    sections = ("firstHalf", "secondHalf")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<PutDataRequest>", "<Positions>"]
    for half_index, section in enumerate(sections):
        for team_id, players in ((HOME_ID, home_players), (AWAY_ID, away_players)):
            for person_id, coordinates in players.items():
                x, y = coordinates[half_index]
                lines.append(
                    f'<FrameSet GameSection="{section}" MatchId="{match_id}" '
                    f'TeamId="{team_id}" PersonId="{person_id}">'
                )
                lines.append(
                    _frame(
                        frame_numbers[half_index],
                        x,
                        y,
                        ball=False,
                        status=1,
                        possession=1,
                        marker=marker,
                    )
                )
                lines.append("</FrameSet>")
        x, y = ball_frames[half_index]
        lines.append(
            f'<FrameSet GameSection="{section}" MatchId="{match_id}" '
            'TeamId="BALL" PersonId="BALL-ID">'
        )
        lines.append(
            _frame(
                frame_numbers[half_index],
                x,
                y,
                ball=True,
                status=statuses[half_index],
                possession=possessions[half_index],
            )
        )
        lines.append("</FrameSet>")
    lines.extend(("</Positions>", "</PutDataRequest>"))
    return "\n".join(lines) + "\n"


def _make_package(
    root: Path,
    *,
    statuses: tuple[int, int] = (1, 0),
    possessions: tuple[int, int] = (1, 2),
    ball_frames: tuple[tuple[float, float], tuple[float, float]] = (
        (0.0, 0.0),
        (1.0, 1.0),
    ),
    home_players: dict[str, tuple[tuple[float, float], tuple[float, float]]] | None = None,
    away_players: dict[str, tuple[tuple[float, float], tuple[float, float]]] | None = None,
    marker: int = 1,
) -> Path:
    package = root / "package"
    repository = package / "01_RAW_DATA" / "idsse" / "repository"
    quality = package / "04_QUALITY_ASSESSMENT"
    repository.mkdir(parents=True)
    quality.mkdir(parents=True)
    for match_id in ALL_MATCH_IDS:
        if match_id == MATCH_ID:
            continue
        for role in ("matchinformation", "positions_raw_observed", "events_raw"):
            path = repository / f"DFL_00_00_{role}_DFL-COM-000001_{match_id}.xml"
            path.write_text(f"{match_id} {role}\n", encoding="utf-8", newline="\n")
    (repository / f"DFL_02_01_matchinformation_DFL-COM-000001_{MATCH_ID}.xml").write_text(
        _metadata_xml(), encoding="utf-8", newline="\n"
    )
    (repository / f"DFL_04_03_positions_raw_observed_DFL-COM-000001_{MATCH_ID}.xml").write_text(
        _tracking_xml(
            statuses=statuses,
            possessions=possessions,
            ball_frames=ball_frames,
            home_players=home_players,
            away_players=away_players,
            marker=marker,
        ),
        encoding="utf-8",
        newline="\n",
    )
    (repository / f"DFL_03_02_events_raw_DFL-COM-000001_{MATCH_ID}.xml").write_text(
        "<PutDataRequest><Events/></PutDataRequest>\n",
        encoding="utf-8",
        newline="\n",
    )
    inventory = quality / "FILE_INVENTORY.csv"
    with inventory.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("source", "relative_path", "bytes", "sha256"),
            lineterminator="\n",
        )
        writer.writeheader()
        for path in sorted(repository.glob("*.xml")):
            writer.writerow(
                {
                    "source": "IDSSE",
                    "relative_path": path.relative_to(package).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    return package


def _extract(package: Path, output: Path, *, overwrite: bool = False):
    return extract_idss(
        package_root=package,
        match_id=MATCH_ID,
        output_dir=output,
        split_config_path=SPLIT_CONFIG,
        overwrite=overwrite,
    )


def _read_gzip_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with gzip.open(path, mode="rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def test_synthetic_join_schema_reference_and_two_half_identity(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    output = tmp_path / "output"
    result = _extract(package, output)

    assert result["status"] == "PASS"
    feature_columns, features = _read_gzip_rows(output / "features.csv.gz")
    reference_columns, references = _read_gzip_rows(output / "reference.csv.gz")
    assert feature_columns == list(FEATURE_COLUMNS)
    assert reference_columns == list(REFERENCE_COLUMNS)
    assert len(features) == len(references) == 2
    assert [row["frame_number"] for row in features] == ["100", "200"]
    assert [row["game_section"] for row in features] == ["firstHalf", "secondHalf"]
    assert all(
        "BallStatus" not in column and "possession" not in column for column in feature_columns
    )
    assert references[0]["provider_alive"] == "true"
    assert references[0]["provider_home_possession"] == "true"
    assert references[1]["provider_alive"] == "false"
    assert references[1]["provider_home_possession"] == "false"

    first = features[0]
    assert first["nearest_home_m"] == "1.000000"
    assert first["nearest_away_m"] == "2.000000"
    assert first["nearest_team_delta_m"] == "1.000000"
    assert first["second_home_m"] == "3.000000"
    assert first["players_within_2m_home"] == "1"
    assert first["players_within_2m_away"] == "1"
    assert first["players_within_5m_home"] == "2"
    assert first["players_within_5m_away"] == "2"
    assert first["home_centroid_x"] == "-2.000000"
    assert first["away_centroid_x"] == "3.000000"
    assert first["centroid_distance_m"] == "5.000000"
    assert first["ball_home_centroid_delta_m"] == "-1.000000"


def test_negative_tracking_x_is_accepted_and_not_clipped(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    output = tmp_path / "output"
    _extract(package, output)
    _, rows = _read_gzip_rows(output / "features.csv.gz")
    assert rows[0]["home_centroid_x"] == "-2.000000"
    assert rows[0]["home_depth_m"] == "2.000000"
    assert rows[0]["home_width_m"] == "0.000000"


def test_invalid_ball_geometry_blanks_only_ball_dependent_fields(tmp_path: Path) -> None:
    package = _make_package(tmp_path, ball_frames=((0.0, 0.0), (60.0, 0.0)))
    output = tmp_path / "output"
    _extract(package, output)
    _, rows = _read_gzip_rows(output / "features.csv.gz")
    invalid = rows[1]
    assert invalid["ball_geometry_valid"] == "false"
    for column in (
        "nearest_home_m",
        "nearest_away_m",
        "nearest_team_delta_m",
        "second_home_m",
        "second_away_m",
        "players_within_2m_home",
        "players_within_2m_away",
        "players_within_5m_home",
        "players_within_5m_away",
        "ball_home_centroid_delta_m",
    ):
        assert invalid[column] == ""
    assert invalid["home_centroid_x"] != ""
    assert invalid["away_centroid_x"] != ""
    assert invalid["centroid_distance_m"] != ""


def test_second_nearest_is_blank_with_fewer_than_two_players(tmp_path: Path) -> None:
    package = _make_package(
        tmp_path,
        home_players={"HOME-1": ((-1.0, 0.0), (-2.0, 0.0))},
    )
    output = tmp_path / "output"
    _extract(package, output)
    _, rows = _read_gzip_rows(output / "features.csv.gz")
    assert rows[0]["home_tracked_n"] == "1"
    assert rows[0]["second_home_m"] == ""


def test_marker_attribute_does_not_filter_players(tmp_path: Path) -> None:
    package = _make_package(tmp_path, marker=25)
    output = tmp_path / "output"
    _extract(package, output)
    _, rows = _read_gzip_rows(output / "features.csv.gz")
    assert rows[0]["home_tracked_n"] == "2"
    assert rows[0]["away_tracked_n"] == "2"


def test_illegal_reference_fails_closed_without_output(tmp_path: Path) -> None:
    package = _make_package(tmp_path, statuses=(1, 7))
    output = tmp_path / "must-not-exist"
    with pytest.raises(ExtractionError, match=r"frame 200 invalid BallStatus=7"):
        _extract(package, output)
    assert not output.exists()


def test_ball_frames_must_be_strictly_contiguous_within_half(tmp_path: Path) -> None:
    tracking = tmp_path / "duplicate.xml"
    tracking.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<PutDataRequest><Positions>
  <FrameSet GameSection="firstHalf" MatchId="DFL-MAT-J03WMX" TeamId="BALL" PersonId="B">
    <Frame N="100" T="2023-05-27T13:30:00.000+00:00" X="0" Y="0" BallStatus="1" BallPossession="1"/>
    <Frame N="102" T="2023-05-27T13:30:00.080+00:00" X="1" Y="0" BallStatus="1" BallPossession="1"/>
  </FrameSet>
  <FrameSet GameSection="secondHalf" MatchId="DFL-MAT-J03WMX" TeamId="BALL" PersonId="B">
    <Frame N="200" T="2023-05-27T14:30:00.000+00:00" X="0" Y="0" BallStatus="1" BallPossession="1"/>
  </FrameSet>
</Positions></PutDataRequest>
""",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(ExtractionError, match="non-contiguous"):
        read_ball_timeline(tracking, MATCH_ID)


def test_split_config_is_exact_and_match_level() -> None:
    config = load_split_config(SPLIT_CONFIG)
    assert config["split_unit"] == "match"
    assert config["random_frame_split"] is False
    assert config["historical_exposure"] == "metadata+tracking_aggregate+event_aggregate"
    roles = {entry["match_id"]: entry["split_role"] for entry in config["matches"]}
    assert roles["DFL-MAT-J03WN1"] == "operational_lockbox"
    assert roles["DFL-MAT-J03WR9"] == "operational_lockbox"
    assert sum(role == "development" for role in roles.values()) == 5


def test_event_coordinates_use_an_explicit_centered_conversion() -> None:
    assert event_xy_to_centered(0.0, 0.0) == (-52.5, -34.0)
    assert event_xy_to_centered(105.0, 68.0) == (52.5, 34.0)


def test_home_away_swap_twice_restores_original_and_delta_changes_sign() -> None:
    features = {
        "match_id": MATCH_ID,
        "home_team_id": HOME_ID,
        "away_team_id": AWAY_ID,
        "home_tracked_n": 2,
        "away_tracked_n": 3,
        "nearest_home_m": 1.5,
        "nearest_away_m": 2.5,
        "nearest_team_delta_m": 1.0,
        "ball_home_centroid_delta_m": -2.0,
    }
    swapped = swap_feature_sides(features)
    restored = swap_feature_sides(swapped)
    assert swapped["home_team_id"] == AWAY_ID
    assert swapped["nearest_home_m"] == 2.5
    assert swapped["nearest_team_delta_m"] == -1.0
    assert swapped["ball_home_centroid_delta_m"] == 2.0
    assert restored == features


def test_repeated_gzip_outputs_are_byte_identical(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_result = _extract(package, first)
    second_result = _extract(package, second)
    for name in ("features.csv.gz", "reference.csv.gz"):
        assert first_result["outputs"][name]["sha256"] == second_result["outputs"][name]["sha256"]
        assert (first / name).read_bytes() == (second / name).read_bytes()
        header = (first / name).read_bytes()[:10]
        assert int.from_bytes(header[4:8], "little") == 0
    assert (
        first_result["outputs"]["split_manifest.json"]["sha256"]
        == second_result["outputs"]["split_manifest.json"]["sha256"]
    )


def test_existing_output_is_rejected_without_overwrite(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    output = tmp_path / "output"
    _extract(package, output)
    before = (output / "features.csv.gz").read_bytes()
    with pytest.raises(ExtractionError, match="already exists"):
        _extract(package, output)
    assert (output / "features.csv.gz").read_bytes() == before


def test_metadata_and_split_manifest_record_required_contracts(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    output = tmp_path / "output"
    _extract(package, output)
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    split = json.loads((output / "split_manifest.json").read_text(encoding="utf-8"))
    assert metadata["coordinate_system"] == "centered_pitch_metres"
    assert metadata["coordinate_contract"]["event"]["bounds"] == [0.0, 105.0, 0.0, 68.0]
    assert metadata["coordinate_contract"]["tracking"]["bounds"] == [-54.5, 54.5, -36.0, 36.0]
    assert metadata["frame_counts"]["total"] == 2
    assert metadata["frame_counts"]["half_boundary_frame_jump"] == 99
    assert metadata["source"]["files"]["tracking"]["matches_inventory"] is True
    assert split["split_unit"] == "match"
    assert split["random_frame_split"] is False
    assert len(split["matches"]) == 7
    assert all(len(entry["sources"]) == 3 for entry in split["matches"])


def test_centroid_distance_remains_when_ball_is_outside_envelope(tmp_path: Path) -> None:
    package = _make_package(tmp_path, ball_frames=((100.0, 0.0), (1.0, 1.0)))
    output = tmp_path / "output"
    _extract(package, output)
    _, rows = _read_gzip_rows(output / "features.csv.gz")
    assert rows[0]["ball_geometry_valid"] == "false"
    assert rows[0]["centroid_distance_m"] == "5.000000"
    assert float(rows[1]["centroid_distance_m"]) == 7.0
