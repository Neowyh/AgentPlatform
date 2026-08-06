#!/usr/bin/env python3
"""Compatibility shim for the bundled fault-zeroing agent installer.

Delegates to the generic :mod:`install_agent` so the legacy script path,
CLI behaviour, and test imports keep working unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from install_agent import *  # noqa: F401,F403
from install_agent import main  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main(["--agent", "fault-zeroing", *sys.argv[1:]]))
