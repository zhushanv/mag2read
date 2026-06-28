#!/usr/bin/env python3
"""CLI wrapper for backend.app.modules.layout_refine."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.modules.layout_refine import main


if __name__ == "__main__":
    raise SystemExit(main())
