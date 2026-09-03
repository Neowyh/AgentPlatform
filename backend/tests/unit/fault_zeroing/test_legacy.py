"""Tests for legacy run lifecycle handling and old-path hygiene (ticket 06)."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
LEGACY_PATH = REPO_ROOT / "backend" / "packages" / "harness" / "ideer" / "fault_zeroing" / "legacy.py"


def load_legacy():
    spec = importlib.util.spec_from_file_location("fz_legacy", LEGACY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("fz_legacy", module)
    spec.loader.exec_module(module)
    return module


@dataclass
class FakeRun:
    run_id: str
    status: str
    workflow_resource_id: str | None = None


class FakeLegacyStore:
    def __init__(self, runs: list[FakeRun]) -> None:
        self.runs = runs
        self.events: list[tuple[str, str, dict]] = []
        self.cancelled: dict[str, str] = {}

    async def list_runs(self, *, workflow_name: str, limit: int):
        return list(self.runs), len(self.runs)

    async def cancel_legacy_run(self, run_id: str, *, status: str, reason_code: str):
        for run in self.runs:
            if run.run_id == run_id:
                run.status = status
                self.cancelled[run_id] = reason_code
                return True
        return False

    async def append_event(self, run_id, event_type, payload, *, worker_id=None):
        self.events.append((run_id, event_type, dict(payload)))


# ---------------------------------------------------------------------------
# Legacy run migration.
# ---------------------------------------------------------------------------


def test_queued_and_paused_legacy_runs_are_terminated() -> None:
    legacy = load_legacy()
    store = FakeLegacyStore(
        [
            FakeRun("run-q", "queued"),
            FakeRun("run-p", "paused"),
        ]
    )

    report = asyncio.run(legacy.terminate_legacy_runs(store))

    assert report.terminated_run_ids == ("run-q", "run-p")
    assert store.runs[0].status == "cancelled"
    assert store.runs[1].status == "cancelled"
    assert all(payload["code"] == "legacy_run_terminated" for _, _, payload in store.events)


def test_completed_legacy_runs_stay_readable() -> None:
    legacy = load_legacy()
    store = FakeLegacyStore(
        [
            FakeRun("run-done", "completed"),
            FakeRun("run-failed", "failed"),
            FakeRun("run-cancelled", "cancelled"),
        ]
    )

    report = asyncio.run(legacy.terminate_legacy_runs(store))

    assert report.terminated_run_ids == ()
    assert report.untouched_run_ids == ("run-done", "run-failed", "run-cancelled")
    assert store.events == []


def test_canonical_runs_are_never_touched() -> None:
    legacy = load_legacy()
    store = FakeLegacyStore(
        [
            FakeRun("canon-queued", "queued", workflow_resource_id="res-123"),
            FakeRun("legacy-queued", "queued"),
        ]
    )

    report = asyncio.run(legacy.terminate_legacy_runs(store))

    assert report.terminated_run_ids == ("legacy-queued",)
    assert store.runs[0].status == "queued"  # canonical run untouched


# ---------------------------------------------------------------------------
# Old-path hygiene (automated no-reference verification).
# ---------------------------------------------------------------------------


def test_legacy_fault_zeroing_paths_have_no_remaining_references() -> None:
    """Old install/seed paths must not be referenced by any live code."""

    forbidden = (
        "seed_fault_zeroing_workflow",
        "install_fault_zeroing_agent",
        "merge_fault_zeroing_subagents",
    )
    scanned_roots = [
        REPO_ROOT / "scripts",
        REPO_ROOT / "backend" / "app",
        REPO_ROOT / "backend" / "packages",
        REPO_ROOT / "backend" / "tests",
        REPO_ROOT / "resources",
        REPO_ROOT / "workflows",
    ]
    offenders: list[str] = []
    for root in scanned_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".sh", ".yaml", ".yml", ".md", ".toml"}:
                continue
            # Guard tests mention the forbidden names by design.
            if path.name.startswith("test_") and path.suffix == ".py":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for needle in forbidden:
                if needle in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{needle}")
    assert offenders == [], f"legacy fault-zeroing references remain: {offenders}"


def test_bundled_manifest_contains_full_fault_zeroing_closure() -> None:
    """The canonical bundle is the single lifecycle source for the closure."""

    manifest = json.loads((REPO_ROOT / "bundled-resources.json").read_text(encoding="utf-8"))
    slugs = {(item["type"], item["slug"]) for item in manifest["resources"]}
    assert ("skill", "fault-zeroing") in slugs
    assert ("agent", "fault-zeroing") in slugs
    assert ("workflow", "fault-zeroing") in slugs
