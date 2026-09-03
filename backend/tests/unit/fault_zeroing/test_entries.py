"""Tests for Skill / Expert / Workflow entry adapters (ticket 04)."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
PKG_DIR = REPO_ROOT / "backend" / "packages" / "harness" / "ideer" / "fault_zeroing"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


def load_all():
    contract = load_module("fz_contract_entries", PKG_DIR / "contract.py")
    intake = load_module("fz_intake_entries", PKG_DIR / "intake.py")
    policy = load_module("fz_policy_entries", PKG_DIR / "policy.py")
    kernel_mod = load_module("fz_kernel_entries", PKG_DIR / "kernel.py")
    entries = load_module("fz_entries", PKG_DIR / "entries.py")
    return contract, intake, policy, kernel_mod, entries


@dataclass
class FakeRun:
    run_id: str
    workflow_name: str
    definition_version: int
    inputs: dict
    created_by: str
    status: str = "queued"
    snapshot: dict = field(default_factory=dict)


class FakeStore:
    def __init__(self) -> None:
        self.runs: dict[str, FakeRun] = {}
        self.calls: list[str] = []

    async def create_run(self, run_id, workflow_name, definition_version, inputs, created_by, **kwargs):
        self.calls.append(f"create_run:{run_id}")
        self.runs[run_id] = FakeRun(
            run_id,
            workflow_name,
            definition_version,
            dict(inputs),
            created_by,
            snapshot=dict(kwargs.get("snapshot") or {}),
        )
        return self.runs[run_id]

    async def create_paused_run(self, run_id, workflow_name, definition_version, inputs, created_by, **kwargs):
        self.calls.append(f"create_paused_run:{run_id}")
        self.runs[run_id] = FakeRun(
            run_id,
            workflow_name,
            definition_version,
            dict(inputs),
            created_by,
            status="paused",
            snapshot=dict(kwargs.get("snapshot") or {}),
        )
        return self.runs[run_id]

    async def append_event(self, *args, **kwargs):
        self.calls.append(f"event:{args[1]}")

    async def get_run(self, run_id):
        return self.runs.get(run_id)

    async def update_snapshot(self, run_id, snapshot, *, worker_id):
        self.runs[run_id].snapshot = dict(snapshot)
        return True

    async def submit_command(self, *args, **kwargs):
        self.calls.append(f"command:{args[2]}")
        return type("Cmd", (), {"command_id": args[0]})()


BASE_INPUTS = {
    "upload_dir": "/mnt/user-data/uploads",
    "code_package_source": "/mnt/user-data/code-evidence/pkg-1/source",
    "evidence_mode": "hybrid",
}


@pytest.mark.parametrize("entry", ["skill", "expert", "workflow"])
def test_all_three_entries_route_to_the_same_kernel(entry: str, tmp_path: Path) -> None:
    """Every entry starts its run through the identical kernel seam."""

    _, _, _, kernel_mod, entries_mod = load_all()
    store = FakeStore()
    kernel = kernel_mod.FaultZeroingKernel(store)
    adapter = entries_mod.adapter_for(entry)

    result = asyncio.run(
        adapter.start_run(
            kernel,
            run_inputs=dict(BASE_INPUTS),
            created_by="user-1",
            workflow_name="fault-zeroing",
            definition_version=1,
        )
    )

    assert result.status == "queued"
    assert store.calls[0].startswith("create_run:")
    # Same contract pinning regardless of entry.
    assert store.runs[result.run_id].snapshot["contract_version"] == kernel._contract_version


def test_entry_adapter_rejects_unknown_entry() -> None:
    _, _, _, _, entries_mod = load_all()

    with pytest.raises(entries_mod.EntryConfigError):
        entries_mod.adapter_for("cli")


def test_entries_do_not_reimplement_stages_or_validation() -> None:
    """The adapter module must stay a thin shim: no stage or gate logic."""

    source = (PKG_DIR / "entries.py").read_text(encoding="utf-8")
    forbidden_fragments = (
        "def validate_",  # no result validation in the adapter
        "def evaluate_",  # no contract evaluation in the adapter
        "jsonschema",  # no gate implementation
        "precondition",  # no stage logic
        "schema_file",  # no gate wiring
        "retry",  # no per-entry retry policy
    )
    for fragment in forbidden_fragments:
        assert fragment not in source


def test_semantic_fields_are_entry_independent(tmp_path: Path) -> None:
    """semantic_fields() extracts identical fields from identical outputs."""

    _, _, _, _, entries_mod = load_all()
    contract_tests = load_module(
        "fz_contract_fixtures_entries",
        REPO_ROOT / "backend" / "tests" / "unit" / "fault_zeroing" / "test_contract.py",
    )
    (tmp_path / "one").mkdir(parents=True)
    (tmp_path / "two").mkdir(parents=True)
    dir_one = contract_tests.write_outputs(tmp_path / "one")
    dir_two = contract_tests.write_outputs(tmp_path / "two")

    fields_one = entries_mod.semantic_fields(dir_one)
    fields_two = entries_mod.semantic_fields(dir_two)

    assert entries_mod.semantic_equivalent(fields_one, fields_two)
    assert fields_one["top_event"]
    assert fields_one["root_causes"][0]["id"] == "RC-01"

    # A changed root cause status breaks semantic equivalence.
    import json

    tree = json.loads((dir_two / "fault_tree.json").read_text(encoding="utf-8"))
    tree["root_causes"][0]["status"] = "to_verify"
    (dir_two / "fault_tree.json").write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    fields_two = entries_mod.semantic_fields(dir_two)
    assert not entries_mod.semantic_equivalent(fields_one, fields_two)
