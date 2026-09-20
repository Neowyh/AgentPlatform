#!/usr/bin/env python3
"""Validate test ownership and the commands exposed by canonical lanes."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from test_inventory import build_inventory

ROOT = Path(__file__).resolve().parents[1]
BASE_LANES = {"backend-standard", "backend-serial", "frontend-standard"}


def validate(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    rows = build_inventory(root)
    for row in rows:
        lanes = row["lanes"]
        if not lanes:
            errors.append(f"{row['path']}: no lane ownership")
        if len(set(lanes) - BASE_LANES) == 0 and len(lanes) != 1:
            errors.append(f"{row['path']}: duplicate base ownership {lanes}")
        if "backend-standard" in lanes and "backend-serial" in lanes:
            errors.append(f"{row['path']}: backend standard/serial overlap")
    runner = ROOT / "scripts" / "run-test-lane.sh"
    help_result = subprocess.run(
        ["bash", str(runner), "--help"], capture_output=True, text=True, check=False
    )
    help_text = help_result.stdout
    if help_result.returncode != 0:
        errors.append("runner --help must exit successfully")
    unknown = subprocess.run(
        ["bash", str(runner), "__unknown__"],
        capture_output=True,
        text=True,
        check=False,
    )
    if unknown.returncode != 2:
        errors.append(f"runner unknown lane returned {unknown.returncode}, expected 2")
    for lane in (
        "local-runtime",
        "backend-standard",
        "backend-serial",
        "backend-full",
        "backend-external",
        "frontend-standard",
        "frontend-core",
        "frontend-smoke",
        "frontend-mock-e2e",
        "frontend-auth",
        "frontend-real",
        "frontend-stagehand",
        "pr-standard",
        "core-full",
    ):
        if lane not in help_text:
            errors.append(f"runner help omits lane {lane}")
    package = json.loads(
        (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    )
    for script in (
        "test",
        "test:coverage",
        "test:e2e:smoke",
        "test:e2e:visual",
        "test:e2e:a11y",
        "test:e2e:stagehand",
        "test:full",
    ):
        if script not in package.get("scripts", {}):
            errors.append(f"frontend package omits script {script}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    errors = validate()
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    else:
        if errors:
            for error in errors:
                print(f"[test-contracts] FAIL {error}")
        else:
            print("[test-contracts] OK ownership and lane entry contracts")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
