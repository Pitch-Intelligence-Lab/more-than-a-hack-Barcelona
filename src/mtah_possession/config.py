"""Environment-backed configuration and non-invasive data layout checks."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DATA_ROOT_ENV = "MTAH_DATA_DIR"
DEFAULT_MATCH_STEM = "BAR-ATH"
FPS = 25
EXPECTED_TACTICAL_FRAMES = 199_319
PITCH_LENGTH_M = 105.3
PITCH_WIDTH_M = 68.0

TACTICAL_ASSETS = {
    "atd_meta": "_tactical_atd.xml",
    "atd_raw": "_tactical_atd.txt",
    "homography": "_tactical_homography.csv",
    "smart_tagging": "_tactical_smart_tagging.xml",
    "video": "_tactical.mp4",
}
BROADCAST_ASSETS = {
    "atd_meta": "_broadcast_atd.xml",
    "atd_raw": "_broadcast_atd.txt",
    "homography": "_broadcast_homography.csv",
    "video": "_broadcast.mp4",
}


class ConfigurationError(ValueError):
    """Raised when required configuration or a data location is absent."""


@dataclass(frozen=True)
class DataSettings:
    """Resolved data paths. No asset is read while constructing this object."""

    root: Path
    tactical_dir: Path
    broadcast_dir: Path

    def tactical_asset(self, name: str) -> Path:
        try:
            suffix = TACTICAL_ASSETS[name]
        except KeyError as error:
            raise ConfigurationError(f"unknown tactical asset: {name!r}") from error
        return self.tactical_dir / f"{DEFAULT_MATCH_STEM}{suffix}"

    def broadcast_asset(self, name: str) -> Path:
        try:
            suffix = BROADCAST_ASSETS[name]
        except KeyError as error:
            raise ConfigurationError(f"unknown broadcast asset: {name!r}") from error
        return self.broadcast_dir / f"{DEFAULT_MATCH_STEM}{suffix}"


@dataclass(frozen=True)
class DataLayoutReport:
    """Existence-only report suitable for logs."""

    root_exists: bool
    tactical_exists: bool
    broadcast_exists: bool

    @property
    def valid(self) -> bool:
        return self.root_exists and self.tactical_exists and self.broadcast_exists


def load_settings(
    data_root: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> DataSettings:
    """Resolve ``MTAH_DATA_DIR`` without embedding a machine-specific path."""

    values = os.environ if environ is None else environ
    raw_root = os.fspath(data_root) if data_root is not None else values.get(DATA_ROOT_ENV)
    if not raw_root or not raw_root.strip():
        raise ConfigurationError(
            f"{DATA_ROOT_ENV} is not set. Set it to the root containing tactical/ and broadcast/."
        )

    root = Path(raw_root).expanduser().resolve(strict=False)
    return DataSettings(
        root=root,
        tactical_dir=root / "tactical",
        broadcast_dir=root / "broadcast",
    )


def inspect_layout(settings: DataSettings) -> DataLayoutReport:
    """Check directories only; never enumerate or open match content."""

    return DataLayoutReport(
        root_exists=settings.root.is_dir(),
        tactical_exists=settings.tactical_dir.is_dir(),
        broadcast_exists=settings.broadcast_dir.is_dir(),
    )


def require_layout(settings: DataSettings) -> DataLayoutReport:
    """Require the complete two-camera directory layout with a clear failure."""

    report = inspect_layout(settings)
    missing: list[str] = []
    if not report.root_exists:
        missing.append(str(settings.root))
    if not report.tactical_exists:
        missing.append(str(settings.tactical_dir))
    if not report.broadcast_exists:
        missing.append(str(settings.broadcast_dir))
    if missing:
        raise ConfigurationError(
            "match data layout is incomplete; missing directory path(s):\n  " + "\n  ".join(missing)
        )
    return report


def require_tactical_assets(
    settings: DataSettings,
    names: tuple[str, ...] = ("atd_meta", "atd_raw"),
) -> dict[str, Path]:
    """Return requested tactical paths after existence checks.

    Only paths are logged. File contents never appear in configuration errors.
    """

    paths = {name: settings.tactical_asset(name) for name in names}
    missing = [f"{name}: {path}" for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ConfigurationError(
            "required tactical asset path(s) are missing:\n  " + "\n  ".join(missing)
        )
    return paths
