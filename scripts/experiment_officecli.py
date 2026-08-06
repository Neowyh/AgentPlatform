#!/usr/bin/env python3
"""Local experiment harness: OfficeCLI inside the AIO sandbox container.

Validates the offline-intranet integration approach end to end:
  - sandbox.mounts injects the officecli binary into the sandbox container
  - sandbox.environment (OFFICECLI_SKIP_UPDATE=1) disables its online
    auto-update check, which would stall on an air-gapped network
  - the skills directory is mounted read-only at /mnt/skills
  - officecli can create / edit / render Office documents inside the sandbox

Run from the repo root (venv has ideer installed):
  IDEER_CONFIG_PATH=.experiment-officecli/config.yaml \
    PYTHONPATH=backend backend/.venv/bin/python scripts/experiment_officecli.py

Exit code 0 only when every gate (G2-G4) passes.
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend"))

from ideer.community.aio_sandbox import AioSandboxProvider  # noqa: E402

THREAD_ID = "officecli-experiment"
WORKSPACE = "/mnt/user-data/workspace"


def main() -> int:
    checks = [
        (
            "G2: binary present and runs inside sandbox",
            "which officecli && officecli --version",
            ["1.0.143"],
        ),
        (
            "G2b: auto-update disabled via env injection",
            "echo OFFICECLI_SKIP_UPDATE=$OFFICECLI_SKIP_UPDATE",
            ["OFFICECLI_SKIP_UPDATE=1"],
        ),
        (
            "G3a: create pptx in thread workspace",
            f"cd {WORKSPACE} && officecli create demo.pptx && ls -la demo.pptx",
            ["Created: demo.pptx", "demo.pptx"],
        ),
        (
            "G3b: add a slide with a title",
            f"cd {WORKSPACE} && officecli add demo.pptx / --type slide "
            "--prop title='OfficeCLI Experiment'",
            ["Added slide"],
        ),
        (
            "G3c: render pptx to standalone html",
            f"cd {WORKSPACE} && officecli view demo.pptx html -o demo.html "
            "&& ls -la demo.html",
            ["demo.html"],
        ),
        (
            "G4: officecli skill visible at /mnt/skills",
            "ls -la /mnt/skills/custom/officecli/SKILL.md",
            ["SKILL.md"],
        ),
    ]

    failed = False
    provider = AioSandboxProvider()
    try:
        sandbox_id = provider.acquire(THREAD_ID)
        sandbox = provider.get(sandbox_id)
        if sandbox is None:
            print("FATAL: acquired sandbox_id but provider returned None")
            return 2

        for name, command, markers in checks:
            print(f"\n=== {name} ===")
            output = sandbox.execute_command(command)
            print(output)
            missing = [m for m in markers if m not in output]
            if missing:
                print(f">>> {name}: FAILED (missing markers: {missing})")
                failed = True
            else:
                print(f">>> {name}: OK")
    finally:
        provider.shutdown()

    print(f"\n{'FAILED' if failed else 'ALL GATES PASSED'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
