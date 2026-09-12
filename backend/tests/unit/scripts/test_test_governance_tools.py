from pathlib import Path

import pnpm_command
from check_test_contracts import validate
from test_inventory import _lanes, compare_inventory
from test_preflight import LANES, _mkdir_probe


def test_inventory_assigns_exclusive_backend_lanes() -> None:
    assert _lanes(Path("backend/tests/unit/test_widget.py")) == ["backend-standard"]
    assert _lanes(Path("backend/tests/unit/test_serial_widget.py")) == ["backend-serial"]
    assert _lanes(Path("backend/tests/blocking_io/test_widget.py")) == ["backend-blocking-io"]


def test_inventory_keeps_special_frontend_lanes_visible() -> None:
    assert _lanes(Path("frontend/tests/e2e/auth/login.spec.ts")) == ["frontend-auth"]
    assert _lanes(Path("frontend/tests/e2e/visual/home.spec.ts")) == ["frontend-visual"]
    assert _lanes(Path("frontend/tests/e2e/smoke/home.spec.ts")) == ["frontend-smoke", "frontend-mock-e2e"]
    assert _lanes(Path("frontend/tests/e2e-real-backend/real-backend-render.spec.ts")) == ["frontend-real"]
    assert _lanes(Path("frontend/tests/e2e/stagehand/chat-interactions.spec.ts")) == ["frontend-stagehand"]


def test_preflight_declares_every_runner_lane() -> None:
    expected = {
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


def test_writable_probe_creates_missing_directory(tmp_path: Path) -> None:
    target = tmp_path / "scratch"
    assert _mkdir_probe(target)
    assert target.is_dir()


def test_repository_lane_contracts_are_consistent() -> None:
    assert validate() == []


def test_inventory_comparison_reports_add_remove_and_lane_changes() -> None:
    baseline = [{"path": "a.py", "lanes": ["backend-standard"]}, {"path": "gone.py", "lanes": ["backend-standard"]}]
    current = [{"path": "a.py", "lanes": ["backend-serial"]}, {"path": "new.py", "lanes": ["backend-standard"]}]
    assert compare_inventory(current, baseline) == {"added": ["new.py"], "removed": ["gone.py"], "lane_changed": ["a.py"]}


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
