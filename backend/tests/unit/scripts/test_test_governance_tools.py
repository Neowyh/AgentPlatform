import subprocess
import sys
from pathlib import Path

import pnpm_command
from check_test_contracts import validate
from test_inventory import (
    _iter_test_files,
    _lanes,
    _matching_lanes,
    _node_lanes,
    _pytest_collected_nodes,
    build_inventory,
    compare_inventory,
)
from test_preflight import LANES, _minimum_python, _mkdir_probe


def test_inventory_assigns_exclusive_backend_lanes(tmp_path: Path) -> None:
    ordinary = tmp_path / "backend/tests/unit/test_serial_widget.py"
    ordinary.parent.mkdir(parents=True)
    ordinary.write_text("def test_sample(): pass\n", encoding="utf-8")
    assert _lanes(ordinary) == ["backend-standard"]

    serial = tmp_path / "backend/tests/unit/test_widget.py"
    serial.write_text("import pytest\npytestmark = pytest.mark.serial\n", encoding="utf-8")
    assert _lanes(serial) == ["backend-serial"]
    assert _lanes(Path("backend/tests/blocking_io/test_widget.py")) == ["backend-blocking-io"]
    live = tmp_path / "backend/tests/test_client_live.py"
    live.write_text("import pytest\npytestmark = pytest.mark.live\n", encoding="utf-8")
    assert _lanes(live) == ["backend-live"]


def test_inventory_keeps_special_frontend_lanes_visible() -> None:
    assert _lanes(Path("frontend/tests/e2e/auth/login.spec.ts")) == ["frontend-auth"]
    assert _lanes(Path("frontend/tests/e2e/visual/home.spec.ts")) == ["frontend-visual"]
    assert _lanes(Path("frontend/tests/e2e/smoke/home.spec.ts")) == ["frontend-mock-e2e"]


def test_inventory_separates_discovery_roots_from_repository_scripts(
    tmp_path: Path,
) -> None:
    for relative in (
        "backend/tests/test_backend.py",
        "frontend/tests/test_frontend.py",
        "local-runtime/tests/test_runtime.py",
        "scripts/test_helper.py",
        "examples/test_example.py",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def test_sample(): pass\n", encoding="utf-8")

    assert {path.relative_to(tmp_path).as_posix() for path in _iter_test_files(tmp_path)} == {
        "backend/tests/test_backend.py",
        "frontend/tests/test_frontend.py",
        "local-runtime/tests/test_runtime.py",
    }


def test_inventory_reports_discovery_collection_and_execution_separately(
    tmp_path: Path,
) -> None:
    backend_test = tmp_path / "backend/tests/test_sample.py"
    backend_test.parent.mkdir(parents=True)
    backend_test.write_text("def test_sample(): pass\n", encoding="utf-8")
    smoke_test = tmp_path / "frontend/tests/e2e/smoke/home.spec.ts"
    smoke_test.parent.mkdir(parents=True)
    smoke_test.write_text("test('home', async () => {});\n", encoding="utf-8")
    rstest_test = tmp_path / "frontend/tests/unit/use-test.test.ts"
    rstest_test.parent.mkdir(parents=True)
    rstest_test.write_text("import { test } from '@rstest/core';\n", encoding="utf-8")
    record_test = tmp_path / "frontend/tests/e2e-record/sample.spec.ts"
    record_test.parent.mkdir(parents=True)
    record_test.write_text("test('sample', async () => {});\n", encoding="utf-8")

    rows = {row["path"]: row for row in build_inventory(tmp_path)}

    assert rows["backend/tests/test_sample.py"]["framework_collection_status"] == "not-checked"
    assert rows["backend/tests/test_sample.py"]["execution_status"] == "not-observed"
    assert rows["backend/tests/test_sample.py"]["node_ownership_status"] == "unverified-file-static"
    assert isinstance(rows["backend/tests/test_sample.py"]["suggested_bucket"], str)
    assert rows["frontend/tests/e2e/smoke/home.spec.ts"]["lanes"] == ["frontend-mock-e2e"]
    assert rows["frontend/tests/e2e/smoke/home.spec.ts"]["aggregate_lanes"] == ["frontend-smoke"]
    assert rows["frontend/tests/unit/use-test.test.ts"]["runner"] == "rstest"
    assert rows["frontend/tests/e2e-record/sample.spec.ts"]["lanes"] == ["frontend-record"]
    assert rows["frontend/tests/e2e-record/sample.spec.ts"]["suggested_bucket"] == "frontend/e2e/record"


def test_inventory_assigns_mixed_pytest_markers_per_node() -> None:
    path = Path("backend/tests/unit/test_mixed.py")

    assert _node_lanes(path, {"serial"}) == ["backend-serial"]
    assert _node_lanes(path, set()) == ["backend-standard"]
    assert _node_lanes(path, {"requires_llm", "serial"}) == ["backend-llm"]


def test_inventory_reports_actual_runner_lane_overlap() -> None:
    path = Path("backend/tests/test_overlap.py")
    assert _node_lanes(path, {"external", "requires_llm"}) == ["backend-external"]
    assert _matching_lanes(path, {"external", "requires_llm"}) == ["backend-external"]
    assert _node_lanes(path, {"live", "requires_llm"}) == ["backend-live"]
    assert _matching_lanes(path, {"live", "requires_llm"}) == ["backend-live"]
    assert _matching_lanes(path, {"external", "serial"}) == ["backend-external"]
    assert _matching_lanes(path, set()) == ["backend-standard"]
    assert _matching_lanes(path, {"serial"}) == ["backend-serial"]
    assert _matching_lanes(path, {"requires_llm"}) == ["backend-llm"]
    assert _matching_lanes(path, {"live"}) == ["backend-live"]


def test_inventory_collects_effective_markers_per_pytest_node(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backend_tests = tmp_path / "backend/tests"
    backend_tests.mkdir(parents=True)
    (backend_tests / "test_sample.py").write_text(
        "import pytest\ndef test_standard(): pass\n@pytest.mark.serial\ndef test_serial(): pass\n",
        encoding="utf-8",
    )
    (backend_tests / "test_optional.py").write_text(
        "import pytest\npytest.skip('optional provider is unavailable', allow_module_level=True)\n",
        encoding="utf-8",
    )
    real_run = subprocess.run

    def system_pytest(command, **kwargs):
        assert command[:4] == ["uv", "run", "--no-sync", "pytest"]
        return real_run([sys.executable, "-m", "pytest", *command[4:]], **kwargs)

    monkeypatch.setattr("test_inventory.subprocess.run", system_pytest)

    nodes, skipped, error = _pytest_collected_nodes(tmp_path)

    assert error is None
    assert nodes["tests/test_sample.py::test_standard"] == []
    assert nodes["tests/test_sample.py::test_serial"] == ["serial"]
    assert "tests/test_optional.py" in skipped
    assert "optional provider is unavailable" in skipped["tests/test_optional.py"]

    rows = {row["path"]: row for row in build_inventory(tmp_path, collect=True)}
    optional = rows["backend/tests/test_optional.py"]
    assert optional["framework_collection_status"] == "collection-skipped"
    assert optional["node_ownership_status"] == "collection-skipped"
    assert "optional provider is unavailable" in optional["collection_skip_reason"]
    assert _lanes(Path("frontend/tests/e2e-real-backend/real-backend-render.spec.ts")) == ["frontend-real"]
    assert _lanes(Path("frontend/tests/e2e/stagehand/chat-interactions.spec.ts")) == ["frontend-stagehand"]


def test_preflight_declares_every_runner_lane() -> None:
    expected = {
        "local-runtime",
        "backend-standard",
        "backend-serial",
        "backend-full",
        "backend-llm",
        "backend-blocking-io",
        "frontend-standard",
        "frontend-core",
        "frontend-smoke",
        "frontend-mock-e2e",
        "frontend-visual",
        "frontend-a11y",
        "frontend-auth",
        "frontend-real",
        "frontend-stagehand",
        "pr-standard",
        "core-full",
    }
    assert expected <= LANES.keys()


def test_local_runtime_preflight_accepts_supported_python_38() -> None:
    assert _minimum_python(LANES["local-runtime"]) == (3, 8)
    assert _minimum_python(LANES["backend-standard"]) == (3, 12)


def test_writable_probe_creates_missing_directory(tmp_path: Path) -> None:
    target = tmp_path / "scratch"
    assert _mkdir_probe(target)
    assert target.is_dir()


def test_repository_lane_contracts_are_consistent() -> None:
    assert validate() == []


def test_inventory_comparison_reports_add_remove_and_lane_changes() -> None:
    baseline = [
        {"path": "a.py", "lanes": ["backend-standard"]},
        {"path": "gone.py", "lanes": ["backend-standard"]},
    ]
    current = [
        {"path": "a.py", "lanes": ["backend-serial"]},
        {"path": "new.py", "lanes": ["backend-standard"]},
    ]
    assert compare_inventory(current, baseline) == {
        "added": ["new.py"],
        "removed": ["gone.py"],
        "lane_changed": ["a.py"],
    }


def test_pnpm_command_falls_back_to_corepack_pnpm(monkeypatch) -> None:
    """The public pnpm command must ask Corepack for pnpm, not its own version."""
    monkeypatch.delenv("TEST_PNPM_BIN", raising=False)
    monkeypatch.setattr(
        pnpm_command.shutil,
        "which",
        lambda name: "/tools/corepack" if name == "corepack" else None,
    )

    assert pnpm_command.resolve() == ["/tools/corepack", "pnpm"]


def test_inventory_comparison_reports_path_and_lane_changes() -> None:
    baseline = [
        {"path": "backend/tests/test_old.py", "lanes": ["backend-standard"]},
        {"path": "backend/tests/test_moved.py", "lanes": ["backend-standard"]},
    ]
    current = [
        {"path": "backend/tests/test_new.py", "lanes": ["backend-standard"]},
        {"path": "backend/tests/test_moved.py", "lanes": ["backend-serial"]},
    ]

    assert compare_inventory(current, baseline) == {
        "added": ["backend/tests/test_new.py"],
        "removed": ["backend/tests/test_old.py"],
        "lane_changed": ["backend/tests/test_moved.py"],
    }


def test_contract_allows_distinct_nodes_in_mixed_marker_file(monkeypatch):
    import check_test_contracts

    monkeypatch.setattr(
        check_test_contracts,
        "build_inventory",
        lambda *a, **kw: [
            {
                "path": "backend/tests/test_mixed.py",
                "lanes": ["backend-standard", "backend-serial"],
                "node_ownership_status": "collected",
                "nodes": [
                    {"node_id": "test_standard", "lanes": ["backend-standard"], "matching_lanes": ["backend-standard"]},
                    {"node_id": "test_serial", "lanes": ["backend-serial"], "matching_lanes": ["backend-serial"]},
                ],
            }
        ],
    )
    assert check_test_contracts.validate(collect=True) == []
