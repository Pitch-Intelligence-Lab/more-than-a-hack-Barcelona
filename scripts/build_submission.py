#!/usr/bin/env python3
"""Repository-friendly entry point for the submission builder."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mtah_possession.pipeline.build_submission import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
