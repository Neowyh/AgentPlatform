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
import tempfile
from pathlib import Path

PATCH_MARKERS = ("coverage", "boost", "gaps", "full", "extra")
TEST_SUFFIXES = (".py", ".ts", ".tsx")


def _is_test_file(path: Path) -> bool:
    if path.suffix not in TEST_SUFFIXES:
        return False
    return path.name.startswith("test_") or path.name.endswith(".spec.ts") or path.name.endswith(".test.ts") or path.name.endswith(".test.tsx")


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
    files: set[Path] = set()
    # Match the test roots consumed by the lane runner. Repository tooling,
    # examples, vendored skills, and docs may contain test-shaped filenames;
    # those files are not tests owned by this repository's test runners.
    for relative_root in (
        "backend/tests",
        "frontend/tests",
        "local-runtime/tests",
    ):
        test_root = root / relative_root
        if not test_root.is_dir():
            continue
        for path in test_root.rglob("*"):
            if any(part in ignored for part in path.parts):
                continue
            if path.is_file() and _is_test_file(path):
                files.add(path)
    return sorted(files)


def _python_inventory(path: Path) -> tuple[list[str], list[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tests: list[str] = []
    imports: set[str] = set()
    for node in ast.walk(tree):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")) or (isinstance(node, ast.ClassDef) and node.name.startswith("Test")):
            tests.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    production_imports = sorted(item for item in imports if not item.startswith(("tests", "pytest", "unittest", "typing", "_")))
    return sorted(tests), production_imports


def _markers(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    found = set(re.findall(r"(?:pytest\.mark\.|@pytest\.mark\.)([A-Za-z_]+)", text))
    found.update(re.findall(r"@([A-Za-z_]+)", text))
    return sorted(item for item in found if item in {"serial", "live", "requires_llm", "external", "smoke", "skip", "skipif"})


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
        if "e2e-record" in parts:
            return "frontend/e2e/record"
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
        if "e2e-record" in parts:
            return ["frontend-record"]
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
            return ["frontend-mock-e2e"]
        return ["frontend-mock-e2e"]
    if path.suffix == ".py":
        if "blocking_io" in parts:
            return ["backend-blocking-io"]
        if path.is_file():
            markers = set(_markers(path))
            if markers.intersection({"external", "live", "requires_llm", "serial"}):
                return _node_lanes(path, markers)
        return ["backend-standard"]
    return ["frontend-standard"]


def _matching_lanes(path: Path, markers: set[str]) -> list[str]:
    """Return every backend command whose current marker selector matches."""
    if "blocking_io" in {part.lower() for part in path.parts}:
        return ["backend-blocking-io"]
    lanes: list[str] = []
    if "external" in markers:
        lanes.append("backend-external")
    if "requires_llm" in markers and not markers.intersection({"external", "live"}):
        lanes.append("backend-llm")
    if "live" in markers and "external" not in markers:
        lanes.append("backend-live")
    if "serial" in markers and not markers.intersection({"requires_llm", "live", "external"}):
        lanes.append("backend-serial")
    if not markers.intersection({"serial", "requires_llm", "live", "external"}):
        lanes.append("backend-standard")
    return lanes


def _node_lanes(path: Path, markers: set[str]) -> list[str]:
    """Assign one primary owner while retaining overlaps in matching_lanes."""
    if "blocking_io" in {part.lower() for part in path.parts}:
        return ["backend-blocking-io"]
    if "external" in markers:
        return ["backend-external"]
    if "live" in markers:
        return ["backend-live"]
    if "requires_llm" in markers:
        return ["backend-llm"]
    if "serial" in markers:
        return ["backend-serial"]
    return ["backend-standard"]


def _pytest_collected_nodes(
    root: Path,
) -> tuple[dict[str, list[str]], dict[str, str], str | None]:
    """Collect backend node IDs and effective marker sets once."""
    backend = root / "backend"
    if not backend.is_dir():
        return {}, {}, "backend directory is missing"
    plugin_source = """\
import json, os
skipped = {}
def pytest_collectreport(report):
    if report.outcome == "skipped":
        skipped[report.nodeid] = str(report.longrepr)
def pytest_collection_finish(session):
    nodes = {}
    for item in session.items:
        nodes[item.nodeid] = sorted({marker.name for marker in item.iter_markers()})
    with open(os.environ["TEST_INVENTORY_COLLECTION_OUTPUT"], "w", encoding="utf-8") as stream:
        json.dump({"nodes": nodes, "skipped": skipped}, stream)
"""
    with tempfile.TemporaryDirectory(prefix="test-inventory-") as temp_dir:
        plugin_path = Path(temp_dir) / "test_inventory_collection_plugin.py"
        output_path = Path(temp_dir) / "nodes.json"
        plugin_path.write_text(plugin_source, encoding="utf-8")
        command = [
            "uv",
            "run",
            "--no-sync",
            "pytest",
            "tests",
            "--collect-only",
            "-q",
            "-p",
            "test_inventory_collection_plugin",
        ]
        try:
            env = os.environ.copy()
            env.setdefault("UV_CACHE_DIR", "/tmp/deer-flow-uv-cache")
            env["TEST_INVENTORY_COLLECTION_OUTPUT"] = str(output_path)
            env["PYTHONPATH"] = os.pathsep.join([temp_dir, ".", "tests", env.get("PYTHONPATH", "")])
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
            return {}, {}, f"pytest collection unavailable: {exc}"
        payload = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else {"nodes": {}, "skipped": {}}
        nodes = payload.get("nodes", {})
        skipped = payload.get("skipped", {})
        if result.returncode:
            detail = result.stderr.strip().splitlines()[-1:] or ["pytest collect-only failed"]
            return nodes, skipped, detail[0]
        return nodes, skipped, None


def build_inventory(root: Path, *, collect: bool = False) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    root = root.resolve()
    collected_nodes, skipped_nodes, collection_error = _pytest_collected_nodes(root) if collect else ({}, {}, None)
    for path in _iter_test_files(root):
        if path.suffix == ".py":
            tests, imports = _python_inventory(path)
        else:
            tests, imports = _typescript_inventory(path)
        lanes = _lanes(path)
        markers = _markers(path)
        if path.suffix == ".py":
            runner = "pytest"
        elif "e2e" in path.parts or any(part.startswith("e2e-") for part in path.parts):
            runner = "playwright"
        elif "frontend" in path.parts and "tests" in path.parts:
            runner = "rstest" if "@rstest/core" in path.read_text(encoding="utf-8") else "vitest"
        else:
            runner = "pytest" if path.suffix == ".ts" else "unknown"
        relative_path = path.relative_to(root).as_posix()
        static_nodes = [f"{relative_path}::{name}" for name in tests]
        node_details: list[dict[str, object]] = []
        if collect and relative_path.startswith("backend/") and path.suffix == ".py":
            backend_relative_path = relative_path.removeprefix("backend/")
            collected_for_file = {node: node_markers for node, node_markers in collected_nodes.items() if node.startswith(f"{backend_relative_path}::")}
            collection_skip_reason = skipped_nodes.get(backend_relative_path)
            actual_nodes = [f"backend/{node}" for node in sorted(collected_for_file)]
            for node, node_markers in sorted(collected_for_file.items()):
                marker_set = set(node_markers)
                node_details.append(
                    {
                        "node_id": f"backend/{node}",
                        "markers": sorted(marker_set),
                        "lanes": _node_lanes(path, marker_set),
                        "matching_lanes": _matching_lanes(path, marker_set),
                        "execution_status": "not-observed",
                    }
                )
            collection_status = "collection-error" if collection_error else ("collected" if node_details else ("collection-skipped" if collection_skip_reason else "not-collected"))
        else:
            actual_nodes = static_nodes
            collection_status = "static-only"
            collection_skip_reason = None
        if collect and node_details:
            lanes = sorted({lane for node in node_details for lane in node["lanes"]})
        node_ownership_status = (
            "collection-error"
            if collect and relative_path.startswith("backend/") and collection_error
            else (
                "collected"
                if collect and relative_path.startswith("backend/") and node_details
                else (
                    "collection-skipped"
                    if collect and relative_path.startswith("backend/") and collection_status == "collection-skipped"
                    else ("not-collected" if collect and relative_path.startswith("backend/") else "unverified-file-static")
                )
            )
        )
        aggregate_lanes = ["frontend-smoke"] if lanes == ["frontend-mock-e2e"] and "smoke" in path.parts else []
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "tests": tests,
                "production_imports": imports,
                "is_patch_coverage_file": any(marker in path.stem.lower() for marker in PATCH_MARKERS),
                "suggested_bucket": _target_bucket(path),
                "lanes": lanes,
                "base_lane": (lanes[0] if node_ownership_status == "collected" and len(lanes) == 1 else None),
                "aggregate_lanes": aggregate_lanes,
                "runner": runner,
                "node_ids": actual_nodes,
                "nodes": node_details,
                "node_ownership_status": node_ownership_status,
                "entry": lanes[0] if node_ownership_status == "collected" and len(lanes) == 1 else None,
                "markers": markers,
                "skip": any(marker in markers for marker in ("skip", "skipif")),
                "discovery_status": "discovered",
                "framework_collection_status": (collection_status if collect and relative_path.startswith("backend/") else "not-checked"),
                "execution_status": "not-observed",
                "collection_status": collection_status,
                "collection_skip_reason": collection_skip_reason,
            }
        )
    return rows


def compare_inventory(current: list[dict[str, object]], baseline: list[dict[str, object]]) -> dict[str, object]:
    """Return stable path and ownership changes between two snapshots."""
    old = {str(row["path"]): row for row in baseline}
    new = {str(row["path"]): row for row in current}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(path for path in set(old) & set(new) if old[path].get("lanes") != new[path].get("lanes"))
    return {"added": added, "removed": removed, "lane_changed": changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", help="Repository root")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    parser.add_argument("--baseline", type=Path, help="Compare against a prior JSON inventory")
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
        payload: object = {"tests": rows, "comparison": comparison} if comparison is not None else rows
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print("path\tlanes\tpatch_file\tsuggested_bucket\ttest_count\tproduction_imports")
    for row in rows:
        print(f"{row['path']}\t{','.join(row['lanes'])}\t{row['is_patch_coverage_file']}\t{row['suggested_bucket']}\t{len(row['tests'])}\t{', '.join(row['production_imports'])}")
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
