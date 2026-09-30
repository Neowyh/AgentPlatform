"""Tests for Skill / Expert / Workflow entry adapters (ticket 04)."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
PKG_DIR = REPO_ROOT / "backend" / "app" / "agentplatform" / "fault_zeroing"


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
    """The adapter module must stay a thin shim: no stage or gate logic.

    The workflow contract-gate adapter (unified-kernel ticket 01) delegates
    to ``contract.evaluate_result_contract``; the guard forbids carrying any
    contract rules or finding construction locally, so the shared contract
    stays the single validation standard.
    """

    source = (PKG_DIR / "entries.py").read_text(encoding="utf-8")
    forbidden_fragments = (
        "def validate_",  # no result validation in the adapter
        "ContractFinding(",  # no finding construction in the adapter
        "REQUIRED_OUTPUTS",  # no contract rule constants in the adapter
        "output_missing",  # no contract reason codes in the adapter
        "report_section_missing",
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


# ---------------------------------------------------------------------------
# Workflow contract-gate adapter (unified-kernel ticket 01).
# ---------------------------------------------------------------------------


def _gate_fixtures():
    contract_tests = load_module(
        "fz_contract_fixtures_gate",
        REPO_ROOT / "backend" / "tests" / "unit" / "fault_zeroing" / "test_contract.py",
    )
    return contract_tests, load_all()[4]


def _intake_snapshot(missing: list[str]) -> dict:
    return {
        "evidence_intake": {
            "status": "paused",
            "evidence_mode": "hybrid",
            "missing": missing,
            "reason_code": "intake_confirmation_required",
            "input_snapshot": {},
            "input_snapshot_hash": "hash-1",
        }
    }


def test_workflow_contract_adapter_delegates_to_shared_contract(tmp_path: Path) -> None:
    """Contract-valid five artifacts produce no violations via the gate adapter."""
    contract_tests, entries_mod = _gate_fixtures()
    outputs = contract_tests.write_outputs(tmp_path)

    assert entries_mod.evaluate_workflow_contract(outputs, {}) == []


def test_workflow_contract_adapter_reports_violation_messages(tmp_path: Path) -> None:
    """Violations come back as human-readable messages, not a verdict object."""
    contract_tests, entries_mod = _gate_fixtures()
    outputs = contract_tests.write_outputs(tmp_path)
    (outputs / "zeroing_report.md").write_text("# 归零报告\n", encoding="utf-8")

    violations = entries_mod.evaluate_workflow_contract(outputs, {})

    assert violations and all(isinstance(item, str) for item in violations)
    assert any("zeroing_report.md" in item for item in violations)


def test_workflow_contract_adapter_judges_intake_missing_sides(tmp_path: Path) -> None:
    """A snapshot carrying an intake record pins the missing evidence sides."""
    contract_tests, entries_mod = _gate_fixtures()
    outputs = contract_tests.write_outputs(tmp_path)

    # Undisclosed missing code side must fail the run.
    violations = entries_mod.evaluate_workflow_contract(outputs, _intake_snapshot(["code_evidence_package"]))
    assert any("代码证据包未提供" in item for item in violations)

    # The same artifacts with the disclosure present complete legitimately.
    report = contract_tests.valid_report()
    report = report.replace(
        "| 历史或复核记录 | 已覆盖 | 05_review_record.md | 无 |",
        "| 历史或复核记录 | 已覆盖 | 05_review_record.md | 无 |\n| 代码证据包 | 未提供 | — | 代码证据包未提供，代码侧结论保持 pending_verification |",
    )
    report = report.replace(
        "暂无缺失资料风险；BE-02 仍待验证。",
        "暂无其他缺失资料风险；代码证据包未提供，代码侧结论保持 pending_verification；BE-02 仍待验证。",
    )
    (outputs / "zeroing_report.md").write_text(report, encoding="utf-8")
    assert entries_mod.evaluate_workflow_contract(outputs, _intake_snapshot(["code_evidence_package"])) == []


def test_workflow_contract_adapter_treats_missing_intake_as_no_missing_sides(tmp_path: Path) -> None:
    """Snapshots without an intake record (workflow-entry runs) judge empty."""
    contract_tests, entries_mod = _gate_fixtures()
    outputs = contract_tests.write_outputs(tmp_path)

    assert entries_mod.evaluate_workflow_contract(outputs, {}) == []
    assert entries_mod.evaluate_workflow_contract(outputs, {"inputs": {}, "state": {}, "outputs": {}}) == []


def test_workflow_contract_adapter_fails_closed_on_malformed_intake(tmp_path: Path) -> None:
    """A malformed intake record is an execution error, not a silent pass."""
    contract_tests, entries_mod = _gate_fixtures()
    outputs = contract_tests.write_outputs(tmp_path)

    with pytest.raises(Exception, match="intake"):
        entries_mod.evaluate_workflow_contract(outputs, {"evidence_intake": {"status": "paused"}})


# ---------------------------------------------------------------------------
# Unified completion judgment (unified-kernel ticket 03): with an intake
# record the adapter delegates to the kernel judgment and shuttles its event
# trail; the snapshot-pinned contract version governs the evaluation.
# ---------------------------------------------------------------------------


def test_workflow_contract_adapter_emits_kernel_contract_events(tmp_path: Path) -> None:
    """The kernel contract event trail rides the emitted (type, payload) pairs."""
    contract_tests, entries_mod = _gate_fixtures()
    outputs = contract_tests.write_outputs(tmp_path)

    # Undisclosed missing side: the kernel failure event precedes the violations.
    events: list[tuple[str, dict]] = []
    violations = entries_mod.evaluate_workflow_contract(
        outputs,
        _intake_snapshot(["code_evidence_package"]),
        emit_event=lambda event_type, payload: events.append((event_type, payload)),
    )
    assert violations
    assert [event_type for event_type, _ in events] == ["kernel_contract_failed"]
    assert events[0][1]["code"] == "contract_failed"
    assert "hybrid_disclosure_missing" in events[0][1]["reason_codes"]

    # Disclosed missing side: a legitimate completion through the kernel gate.
    report = contract_tests.valid_report()
    report = report.replace(
        "| 历史或复核记录 | 已覆盖 | 05_review_record.md | 无 |",
        "| 历史或复核记录 | 已覆盖 | 05_review_record.md | 无 |\n| 代码证据包 | 未提供 | — | 代码证据包未提供，代码侧结论保持 pending_verification |",
    )
    report = report.replace(
        "暂无缺失资料风险；BE-02 仍待验证。",
        "暂无其他缺失资料风险；代码证据包未提供，代码侧结论保持 pending_verification；BE-02 仍待验证。",
    )
    (outputs / "zeroing_report.md").write_text(report, encoding="utf-8")
    events.clear()
    violations = entries_mod.evaluate_workflow_contract(
        outputs,
        _intake_snapshot(["code_evidence_package"]),
        emit_event=lambda event_type, payload: events.append((event_type, payload)),
    )
    assert violations == []
    assert [event_type for event_type, _ in events] == ["kernel_contract_evaluated"]
    assert events[0][1]["code"] == "contract_passed"
    assert events[0][1]["pending_verification_disclosed"] is True


def test_workflow_contract_adapter_judges_by_the_pinned_contract_version(tmp_path: Path) -> None:
    """跨票遗留 P2: the snapshot's pinned contract_version governs the judgment."""

    contract_tests, entries_mod = _gate_fixtures()
    outputs = contract_tests.write_outputs(tmp_path)
    snapshot = {**_intake_snapshot([]), "contract_version": "9.9.9"}

    events: list[tuple[str, dict]] = []
    violations = entries_mod.evaluate_workflow_contract(
        outputs,
        snapshot,
        emit_event=lambda event_type, payload: events.append((event_type, payload)),
    )

    assert any("9.9.9" in item for item in violations)
    assert events[0][1]["contract_version"] == "9.9.9"
    assert "contract_version_unsupported" in events[0][1]["reason_codes"]


def test_workflow_contract_adapter_without_intake_never_emits(tmp_path: Path) -> None:
    """Runs without an intake record keep the plain engine gate: no events."""

    contract_tests, entries_mod = _gate_fixtures()
    outputs = contract_tests.write_outputs(tmp_path)
    events: list[tuple[str, dict]] = []

    violations = entries_mod.evaluate_workflow_contract(
        outputs,
        {"inputs": {}, "state": {}, "outputs": {}},
        emit_event=lambda event_type, payload: events.append((event_type, payload)),
    )

    assert violations == []
    assert events == []
