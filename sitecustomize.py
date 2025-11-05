"""Ensure src/ is available on sys.path for local development."""
from __future__ import annotations

import sys
from pathlib import Path

SRC_PATH = Path(__file__).parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
