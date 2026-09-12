#!/usr/bin/env python3
"""Resolve and execute the pnpm command used by test lanes.

The resolver is intentionally shared by preflight and the lane runner: a
successful prerequisite check must describe the exact executable the lane
will subsequently invoke.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def resolve() -> list[str]:
    configured = os.environ.get("TEST_PNPM_BIN")
    if configured:
        path = Path(configured)
        if not path.is_file() or not os.access(path, os.X_OK):
            raise FileNotFoundError("TEST_PNPM_BIN is not executable")
        return [str(path)]

    pnpm = shutil.which("pnpm")
    if pnpm:
        return [pnpm]

    corepack = shutil.which("corepack")
    if corepack:
        return [corepack, "pnpm"]
    raise FileNotFoundError("install pnpm or enable Corepack")


def main() -> int:
    try:
        command = resolve()
    except FileNotFoundError as exc:
        print(f"pnpm command unavailable: {exc}", file=sys.stderr)
        return 127
    os.execvpe(command[0], [*command, *sys.argv[1:]], os.environ.copy())
    return 127  # pragma: no cover - execvpe never returns on success


if __name__ == "__main__":
    raise SystemExit(main())
