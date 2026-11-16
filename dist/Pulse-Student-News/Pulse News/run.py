#!/usr/bin/env python3
"""Compatibility launcher for Render services whose Root Directory is still
the old `Pulse News` upload folder. It runs the current app from the repo root."""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / "run.py"), run_name="__main__")
