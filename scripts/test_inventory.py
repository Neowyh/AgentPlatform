#!/usr/bin/env python3
"""Inventory backend and frontend tests for reorganization work.

The report is intentionally static: it lists test files, discovered test names,
imported production modules, and whether a filename looks like a coverage-patch
file. It does not import project code.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


PATCH_MARKERS = ("coverage", "boost", "gaps", "full", "extra")
TEST_SUFFIXES = (".py", ".ts", ".tsx")


def _is_test_file(path: Path) -> bool:
    if path.suffix not in TEST_SUFFIXES:
        return False
    return (
        path.name.startswith("test_")
        or path.name.endswith(".spec.ts")
        or path.name.endswith(".test.ts")
        or path.name.endswith(".test.tsx")
    )


def _iter_test_files(root: Path) -> list[Path]:
    ignored = {"__pycache__", "node_modules", "test-results", "playwright-report", "playwright-artifacts"}
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in ignored for part in path.parts):
            continue
        if path.is_file() and _is_test_file(path):
            files.append(path)
    return sorted(files)


def _python_inventory(path: Path) -> tuple[list[str], list[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tests: list[str] = []
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            tests.append(node.name)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            tests.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    production_imports = sorted(
        item
        for item in imports
        if not item.startswith(("tests", "pytest", "unittest", "typing", "_"))
    )
    return sorted(tests), production_imports


def _typescript_inventory(path: Path) -> tuple[list[str], list[str]]:
    tests: list[str] = []
    imports: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("test(", "test.describe(", "describe(")):
            quote = '"' if '"' in stripped else "'"
            parts = stripped.split(quote)
            if len(parts) > 1:
                tests.append(parts[1])
        if stripped.startswith("import ") and " from " in stripped:
            module = stripped.rsplit(" from ", 1)[1].strip().strip(";").strip("'\"")
            if module.startswith(("@/", "./src", "../../src", "../src")):
                imports.add(module)
    return sorted(tests), sorted(imports)


def _target_bucket(path: Path) -> str:
    name = path.name.lower()
    parts = set(path.parts)
    if "e2e" in parts:
        if "auth" in parts:
            return "frontend/e2e/auth"
        if "visual" in parts:
            return "frontend/e2e/visual"
        if "a11y" in parts:
            return "frontend/e2e/a11y"
        if "smoke" in parts:
            return "frontend/e2e/smoke"
        return "frontend/e2e/workflows"
    if "unit" in parts:
        return "frontend/unit" if "frontend" in parts else "/".join(path.parts[path.parts.index("unit") : -1])
    if "script" in name or name in {"test_doctor.py", "test_setup_wizard.py"}:
        return "backend/unit/scripts"
    if "auth" in name or "rbac" in name or "permission" in name:
        return "backend/unit/gateway or backend/contracts"
    if "memory" in name:
        return "backend/unit/memory or backend/integration/api"
    if "sandbox" in name:
        return "backend/unit/sandbox or backend/integration/sandbox"
    if "workflow" in name:
        return "backend/unit/workflows or backend/integration/api"
    if "router" in name or "api" in name or "e2e" in name:
        return "backend/integration/api"
    return "backend/unit"


def build_inventory(root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in _iter_test_files(root):
        if path.suffix == ".py":
            tests, imports = _python_inventory(path)
        else:
            tests, imports = _typescript_inventory(path)
        rows.append(
            {
                "path": path.as_posix(),
                "tests": tests,
                "production_imports": imports,
                "is_patch_coverage_file": any(marker in path.stem.lower() for marker in PATCH_MARKERS),
                "suggested_bucket": _target_bucket(path),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", help="Repository root")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    args = parser.parse_args()

    rows = build_inventory(Path(args.root))
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return

    print("path\tpatch_file\tsuggested_bucket\ttest_count\tproduction_imports")
    for row in rows:
        print(
            f"{row['path']}\t{row['is_patch_coverage_file']}\t{row['suggested_bucket']}\t"
            f"{len(row['tests'])}\t{', '.join(row['production_imports'])}"
        )


if __name__ == "__main__":
    main()
