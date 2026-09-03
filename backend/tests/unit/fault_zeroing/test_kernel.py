"""Tests for the shared fault-zeroing execution kernel (tickets 02/03/05)."""

from __future__ import annotations

import asyncio
import importlib.util
import json
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


def load_kernel_pkg():
    # Load contract, intake, policy and kernel in dependency order.
    contract = load_module("fz_contract_kernel", PKG_DIR / "contract.py")
    intake = load_module("fz_intake_kernel", PKG_DIR / "intake.py")
    policy = load_module("fz_policy_kernel", PKG_DIR / "policy.py")
    kernel = load_module("fz_kernel", PKG_DIR / "kernel.py")
    return contract, intake, policy, kernel


# ---------------------------------------------------------------------------
# Fake store (mirrors the WorkflowV2Store surface the kernel uses).
# ---------------------------------------------------------------------------


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
        self.events: list[tuple[str, str, dict]] = []
        self.commands: list[tuple[str, str, str, dict]] = []

    async def create_run(self, run_id, workflow_name, definition_version, inputs, created_by, *, snapshot=None, department_id=None):
        run = FakeRun(run_id, workflow_name, definition_version, dict(inputs), created_by, snapshot=dict(snapshot or {}))
        self.runs[run_id] = run
        return run

    async def create_paused_run(self, run_id, workflow_name, definition_version, inputs, created_by, *, snapshot=None, department_id=None):
        run = FakeRun(
            run_id,
            workflow_name,
            definition_version,
            dict(inputs),
            created_by,
            status="paused",
            snapshot=dict(snapshot or {}),
        )
        self.runs[run_id] = run
        return run

    async def append_event(self, run_id, event_type, payload, *, worker_id=None, **kwargs):
        self.events.append((run_id, event_type, dict(payload)))

    async def get_run(self, run_id):
        return self.runs.get(run_id)

    async def update_snapshot(self, run_id, snapshot, *, worker_id):
        self.runs[run_id].snapshot = dict(snapshot)
        return True

    async def submit_command(self, command_id, run_id, command_type, payload, created_by):
        self.commands.append((command_id, run_id, command_type, dict(payload)))
        return type("Cmd", (), {"command_id": command_id})()


# ---------------------------------------------------------------------------
# Shared output fixture: valid five artifacts (imported from contract tests).
# ---------------------------------------------------------------------------


def make_valid_outputs(tmp_path: Path) -> Path:
    contract_tests = load_module(
        "fz_contract_fixtures",
        REPO_ROOT / "backend" / "tests" / "unit" / "fault_zeroing" / "test_contract.py",
    )
    return contract_tests.write_outputs(tmp_path)


@pytest.fixture()
def kernel_env(tmp_path):
    contract, intake, policy, kernel_mod = load_kernel_pkg()
    store = FakeStore()
    kernel = kernel_mod.FaultZeroingKernel(store)
    outputs_dir = make_valid_outputs(tmp_path)
    return contract, intake, policy, kernel_mod, kernel, store, outputs_dir


BASE_INPUTS = {
    "upload_dir": "/mnt/user-data/uploads",
    "code_package_source": "/mnt/user-data/code-evidence/pkg-1/source",
    "evidence_mode": "hybrid",
}


# ---------------------------------------------------------------------------
# Ticket 02: intake through the kernel.
# ---------------------------------------------------------------------------


def test_start_run_queues_when_both_sides_present(kernel_env) -> None:
    _, _, _, _, kernel, store, _ = kernel_env

    result = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs=dict(BASE_INPUTS),
            created_by="user-1",
        )
    )

    assert result.status == "queued"
    assert result.reason_code == "intake_evidence_complete"
    run = store.runs[result.run_id]
    assert run.status == "queued"
    # Contract version is pinned per run.
    assert run.snapshot["contract_version"] == kernel._contract_version


def test_start_run_pauses_on_missing_side_without_claimable_task(kernel_env) -> None:
    _, _, _, _, kernel, store, _ = kernel_env
    inputs = {"upload_dir": "/mnt/user-data/uploads", "evidence_mode": "hybrid"}

    result = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs=inputs,
            created_by="user-1",
        )
    )

    assert result.status == "paused"
    run = store.runs[result.run_id]
    assert run.status == "paused"
    interrupt = run.snapshot["interrupt"][0]
    assert interrupt["type"] == "evidence_confirmation"
    assert interrupt["missing"] == ["code_evidence_package"]
    assert any(event_type == "interrupted" and payload["code"] == "intake_confirmation_required" for _, event_type, payload in store.events)


def test_start_run_rejects_when_both_sides_missing(kernel_env) -> None:
    _, _, _, kernel_mod, kernel, store, _ = kernel_env

    with pytest.raises(kernel_mod.EvidenceIntakeRejected) as excinfo:
        asyncio.run(
            kernel.start_run(
                workflow_name="fault-zeroing",
                definition_version=1,
                inputs={"evidence_mode": "hybrid"},
                created_by="user-1",
            )
        )

    assert excinfo.value.reason_code == "intake_evidence_missing_both"
    assert store.runs == {}  # no usable run is created


def test_confirm_evidence_resumes_paused_run(kernel_env) -> None:
    _, _, _, _, kernel, store, _ = kernel_env
    started = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs={"upload_dir": "/u", "evidence_mode": "hybrid"},
            created_by="user-1",
        )
    )
    interrupt = store.runs[started.run_id].snapshot["interrupt"][0]

    result = asyncio.run(
        kernel.confirm_evidence(
            started.run_id,
            payload={"input_snapshot_hash": interrupt["input_snapshot_hash"]},
            confirmed_by="user-1",
        )
    )

    record = store.runs[started.run_id].snapshot["evidence_intake"]
    assert record["confirmed"] is True
    assert record["confirmed_snapshot_hash"] == interrupt["input_snapshot_hash"]
    assert store.commands and store.commands[0][2] == "resume"
    assert result["missing_evidence_sides"] == ["code_evidence_package"]


def test_new_material_requires_reconfirmation(kernel_env) -> None:
    _, _, _, kernel_mod, kernel, store, _ = kernel_env
    started = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs={"upload_dir": "/u", "evidence_mode": "hybrid"},
            created_by="user-1",
        )
    )
    interrupt = store.runs[started.run_id].snapshot["interrupt"][0]

    # New material arrives after the pause: the presented hash is stale.
    store.runs[started.run_id].inputs = dict(store.runs[started.run_id].inputs, code_package_source="/c")

    with pytest.raises(kernel_mod.ConfirmationStaleError) as excinfo:
        asyncio.run(
            kernel.confirm_evidence(
                started.run_id,
                payload={"input_snapshot_hash": interrupt["input_snapshot_hash"]},
                confirmed_by="user-1",
            )
        )
    assert excinfo.value.reason_code == "intake_snapshot_changed"
    # The rejection is observable.
    assert any(event_type == "kernel_confirmation_rejected" for _, event_type, _ in store.events)
    assert not store.commands  # nothing was resumed


# ---------------------------------------------------------------------------
# Ticket 03: contract-gated completion.
# ---------------------------------------------------------------------------


def test_completion_passes_with_valid_outputs(kernel_env) -> None:
    _, _, _, _, kernel, store, outputs_dir = kernel_env
    started = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs=dict(BASE_INPUTS),
            created_by="user-1",
        )
    )

    completion = asyncio.run(kernel.evaluate_completion(started.run_id, str(outputs_dir)))

    assert completion.status == "completed"
    assert completion.pending_verification is True  # VP-01 pending, disclosed
    assert any(event_type == "kernel_contract_evaluated" for _, event_type, _ in store.events)


def test_completion_fails_when_report_section_missing(kernel_env) -> None:
    _, _, _, _, kernel, store, outputs_dir = kernel_env
    started = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs=dict(BASE_INPUTS),
            created_by="user-1",
        )
    )
    report = (outputs_dir / "zeroing_report.md").read_text(encoding="utf-8")
    # "问题概述" appears only as a section heading, so removing the whole
    # section reliably triggers the missing-section check.
    report = report.replace("## 1. 问题概述\n\n- 顶事件：热流传感器 HF-07 测值超过试验允许上限\n- 主根因：HF-07 测量链路零点漂移\n", "")
    (outputs_dir / "zeroing_report.md").write_text(report, encoding="utf-8")

    completion = asyncio.run(kernel.evaluate_completion(started.run_id, str(outputs_dir)))

    assert completion.status == "failed"
    assert "report_section_missing" in completion.reason_codes
    assert any(event_type == "kernel_contract_failed" and payload["code"] == "contract_failed" for _, event_type, payload in store.events)


def test_completion_fails_on_file_existence_only(kernel_env) -> None:
    """File existence alone never implies completion (regression)."""

    _, _, _, _, kernel, store, outputs_dir = kernel_env
    started = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs=dict(BASE_INPUTS),
            created_by="user-1",
        )
    )
    # Truncate the tree to something non-empty but structurally broken.
    (outputs_dir / "fault_tree.json").write_text(json.dumps({"top_event": "占位"}), encoding="utf-8")

    completion = asyncio.run(kernel.evaluate_completion(started.run_id, str(outputs_dir)))

    assert completion.status == "failed"
    assert completion.reason_codes


def test_single_side_run_requires_hybrid_disclosure_at_completion(kernel_env) -> None:
    _, _, _, _, kernel, store, outputs_dir = kernel_env
    started = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs={"upload_dir": "/u", "evidence_mode": "hybrid"},
            created_by="user-1",
        )
    )

    completion = asyncio.run(kernel.evaluate_completion(started.run_id, str(outputs_dir)))

    assert completion.status == "failed"
    assert "hybrid_disclosure_missing" in completion.reason_codes


# ---------------------------------------------------------------------------
# Ticket 05: policy decision table.
# ---------------------------------------------------------------------------


def test_policy_transient_errors_use_bounded_provider_retry(kernel_env) -> None:
    _, _, policy, _, _, _, _ = kernel_env

    decision = policy.classify_failure(policy.TRANSIENT_PROVIDER_ERROR, provider_retries_used=0)
    assert decision.action == policy.ACTION_PROVIDER_RETRY
    assert decision.reason_code == policy.REASON_PROVIDER_RETRY

    exhausted = policy.classify_failure(policy.TRANSIENT_PROVIDER_ERROR, provider_retries_used=policy.PROVIDER_RETRY_BUDGET)
    assert exhausted.action == policy.ACTION_USER_PAUSE
    assert exhausted.reason_code == policy.REASON_PROVIDER_RETRY_EXHAUSTED


def test_policy_structural_error_repaired_at_most_once(kernel_env) -> None:
    _, _, policy, _, _, _, _ = kernel_env

    first = policy.classify_failure(policy.STRUCTURAL_ERROR, repairs_used=0, detail="fault_tree.json schema violation at ...")
    assert first.action == policy.ACTION_STAGE_REPAIR
    assert first.reason_code == policy.REASON_STAGE_REPAIR

    second = policy.classify_failure(policy.STRUCTURAL_ERROR, repairs_used=1)
    assert second.action == policy.ACTION_EXPLICIT_FAILURE
    assert second.reason_code == policy.REASON_REPAIR_BUDGET_EXHAUSTED


def test_policy_missing_evidence_never_retried_by_model(kernel_env) -> None:
    _, _, policy, _, _, _, _ = kernel_env

    decision = policy.classify_failure(policy.MISSING_EVIDENCE)
    assert decision.action == policy.ACTION_USER_PAUSE
    assert decision.reason_code == policy.REASON_USER_PAUSE


def test_policy_semantic_conflict_local_repair_only(kernel_env) -> None:
    _, _, policy, _, _, _, _ = kernel_env

    decision = policy.classify_failure(policy.SEMANTIC_CONFLICT)
    assert decision.action == policy.ACTION_LOCAL_REPAIR

    exhausted = policy.classify_failure(policy.SEMANTIC_CONFLICT, repairs_used=1)
    assert exhausted.action == policy.ACTION_EXPLICIT_FAILURE


def test_policy_contract_unavailable_fails_explicitly(kernel_env) -> None:
    _, _, policy, _, _, _, _ = kernel_env

    decision = policy.classify_failure(policy.CONTRACT_UNAVAILABLE)
    assert decision.action == policy.ACTION_EXPLICIT_FAILURE
    assert decision.reason_code == policy.REASON_CONTRACT_UNAVAILABLE
