#!/usr/bin/env python3
"""Inventory backend and frontend tests and their canonical lane ownership.

The report is intentionally static: it lists test files, discovered test names,
imported production modules, and whether a filename looks like a coverage-patch
file. It does not import project code.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
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
    ignored = {
        ".git",
        ".next",
        ".venv",
        "venv",
        "dist",
        "build",
        "__pycache__",
        "node_modules",
        "test-results",
        "playwright-report",
        "playwright-artifacts",
        "coverage",
    }
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
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ) or (isinstance(node, ast.ClassDef) and node.name.startswith("Test")):
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


def _markers(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    found = set(re.findall(r"(?:pytest\.mark\.|@pytest\.mark\.)([A-Za-z_]+)", text))
    found.update(re.findall(r"@([A-Za-z_]+)", text))
    return sorted(
        item
        for item in found
        if item
        in {"serial", "live", "requires_llm", "external", "smoke", "skip", "skipif"}
    )


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
    if "e2e" in parts or any(part.startswith("e2e-") for part in parts):
        if "auth" in parts or any(part.startswith("e2e-auth") for part in parts):
            return "frontend/e2e/auth"
        if "visual" in parts:
            return "frontend/e2e/visual"
        if "a11y" in parts:
            return "frontend/e2e/a11y"
        if "real" in parts or any(part.startswith("e2e-real") for part in parts):
            return "frontend/e2e/real"
        if "stagehand" in parts or "stagehand" in name:
            return "frontend/e2e/stagehand"
        if "smoke" in parts or "smoke" in name:
            return "frontend/e2e/smoke"
        return "frontend/e2e/workflows"
    if "unit" in parts:
        return (
            "frontend/unit"
            if "frontend" in parts
            else "/".join(path.parts[path.parts.index("unit") : -1])
        )
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


def _lanes(path: Path) -> list[str]:
    """Return mutually exclusive ownership plus the aggregate lanes.

    Classification is path/marker based so files requiring unavailable
    credentials remain visible in the inventory even when collection cannot
    import them.
    """
    parts = {p.lower() for p in path.parts}
    name = path.name.lower()
    if "local-runtime" in parts:
        return ["local-runtime"]
    if "e2e" in parts or any(part.startswith("e2e-") for part in parts):
        if "auth" in parts or any(part.startswith("e2e-auth") for part in parts):
            return ["frontend-auth"]
        if "visual" in parts:
            return ["frontend-visual"]
        if "a11y" in parts:
            return ["frontend-a11y"]
        if "real" in parts or any(part.startswith("e2e-real") for part in parts):
            return ["frontend-real"]
        if "stagehand" in parts or "stagehand" in name:
            return ["frontend-stagehand"]
        if "smoke" in parts or "smoke" in name:
            return ["frontend-smoke", "frontend-mock-e2e"]
        return ["frontend-mock-e2e"]
    if path.suffix == ".py":
        if "blocking_io" in parts:
            return ["backend-blocking-io"]
        if "test_extension_manager.py" == name:
            return ["backend-external"]
        if "live" in name or "requires_llm" in name:
            return ["backend-llm"]
        if "serial" in name or "serial" in parts:
            return ["backend-serial"]
        return ["backend-standard"]
    return ["frontend-standard"]


def _pytest_collected_nodes(root: Path) -> tuple[set[str], str | None]:
    """Collect backend nodes once, keeping failures visible to the report."""
    backend = root / "backend"
    if not backend.is_dir():
        return set(), "backend directory is missing"
    command = ["uv", "run", "pytest", "tests", "--collect-only", "-q"]
    try:
        env = os.environ.copy()
        env.setdefault("UV_CACHE_DIR", "/tmp/deer-flow-uv-cache")
        env["PYTHONPATH"] = (
            ".:tests" if not env.get("PYTHONPATH") else f".:tests:{env['PYTHONPATH']}"
        )
        result = subprocess.run(
            command,
            cwd=backend,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return set(), f"pytest collection unavailable: {exc}"
    nodes = {
        line.strip()
        for line in result.stdout.splitlines()
        if line.startswith("tests/") and "::" in line
    }
    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1:] or [
            "pytest collect-only failed"
        ]
        return nodes, detail[0]
    return nodes, None


def build_inventory(root: Path, *, collect: bool = False) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    root = root.resolve()
    collected_nodes, collection_error = (
        _pytest_collected_nodes(root) if collect else (set(), None)
    )
    for path in _iter_test_files(root):
        if path.suffix == ".py":
            tests, imports = _python_inventory(path)
        else:
            tests, imports = _typescript_inventory(path)
        lanes = _lanes(path)
        markers = _markers(path)
        runner = (
            "pytest"
            if path.suffix == ".py"
            else ("playwright" if "e2e" in path.parts else "vitest/rstest")
        )
        relative_path = path.relative_to(root).as_posix()
        static_nodes = [f"{relative_path}::{name}" for name in tests]
        if collect and path.suffix == ".py":
            backend_nodes = {
                node for node in collected_nodes if node.startswith("tests/")
            }
            actual_nodes = [
                f"backend/{node}"
                for node in sorted(backend_nodes)
                if node.startswith(relative_path.removeprefix("backend/"))
            ]
            collection_status = (
                "collected"
                if actual_nodes
                else ("collection-error" if collection_error else "not-collected")
            )
        else:
            actual_nodes = static_nodes
            collection_status = "static-only"
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "tests": tests,
                "production_imports": imports,
                "is_patch_coverage_file": any(
                    marker in path.stem.lower() for marker in PATCH_MARKERS
                ),
                "suggested_bucket": _target_bucket(path),
                "lanes": lanes,
                "base_lane": lanes[0] if lanes else None,
                "runner": runner,
                "node_ids": actual_nodes,
                "entry": lanes[0] if lanes else None,
                "markers": markers,
                "skip": any(marker in markers for marker in ("skip", "skipif")),
                "collection_status": collection_status,
            }
        )
    return rows


def compare_inventory(
    current: list[dict[str, object]], baseline: list[dict[str, object]]
) -> dict[str, object]:
    """Return stable path and ownership changes between two snapshots."""
    old = {str(row["path"]): row for row in baseline}
    new = {str(row["path"]): row for row in current}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(
        path
        for path in set(old) & set(new)
        if old[path].get("lanes") != new[path].get("lanes")
    )
    return {"added": added, "removed": removed, "lane_changed": changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", help="Repository root")
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON instead of a table"
    )
    parser.add_argument(
        "--baseline", type=Path, help="Compare against a prior JSON inventory"
    )
    parser.add_argument(
        "--collect",
        action="store_true",
        help="Run pytest collection and mark backend nodes collected",
    )
    args = parser.parse_args()

    rows = build_inventory(Path(args.root), collect=args.collect)
    comparison = None
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        if not isinstance(baseline, list):
            raise SystemExit("baseline inventory must be a JSON list")
        comparison = compare_inventory(rows, baseline)
    if args.json:
        payload: object = (
            {"tests": rows, "comparison": comparison}
            if comparison is not None
            else rows
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print("path\tlanes\tpatch_file\tsuggested_bucket\ttest_count\tproduction_imports")
    for row in rows:
        print(
            f"{row['path']}\t{','.join(row['lanes'])}\t{row['is_patch_coverage_file']}\t{row['suggested_bucket']}\t"
            f"{len(row['tests'])}\t{', '.join(row['production_imports'])}"
        )
    if comparison is not None:
        print("\nchanges:")
        for kind in ("added", "removed", "lane_changed"):
            for path in comparison[kind]:
                print(f"{kind}\t{path}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # Piped table/JSON output is commonly truncated with ``head`` during
        # diagnostics; do not turn an intentional closed stdout into a failed
        # inventory run or traceback.
        pass
