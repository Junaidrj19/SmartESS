#!/usr/bin/env python3
"""Validate a SmartESS synthetic dataset (M5). Exit 0=PASS, 1=WARNING, 2=BLOCKED."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.validators.synthetic.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
