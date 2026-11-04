from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = [ROOT / "src", ROOT / "scripts", ROOT / "configs"]
FORBIDDEN = (
    "C:\\Users\\",
    "E:\\barca",
    "ghp_",
    "github_pat_",
    "BEGIN PRIVATE KEY",
)


def test_code_and_config_have_no_machine_paths_or_credentials() -> None:
    violations: list[str] = []
    for folder in SCANNED:
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".json", ".toml"}:
                continue
            text = path.read_text(encoding="utf-8")
            violations.extend(
                f"{path.relative_to(ROOT)} contains forbidden marker {marker!r}"
                for marker in FORBIDDEN
                if marker in text
            )
    assert violations == []


def test_repository_contains_no_match_assets() -> None:
    forbidden_suffixes = {".mp4", ".rar", ".zip"}
    found = [
        str(path.relative_to(ROOT))
        for path in ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in forbidden_suffixes
    ]
    assert found == []
