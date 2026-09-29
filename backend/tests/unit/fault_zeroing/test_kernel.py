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
PKG_DIR = REPO_ROOT / "backend" / "app" / "agentplatform" / "fault_zeroing"


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
    model_name: str | None = None


class FakeStore:
    def __init__(self) -> None:
        self.runs: dict[str, FakeRun] = {}
        self.events: list[tuple[str, str, dict]] = []
        self.commands: list[tuple[str, str, str, dict]] = []
        self.canonical_calls: list[tuple] = []

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

    async def update_paused_run_snapshot(self, run_id, snapshot):
        self.runs[run_id].snapshot = dict(snapshot)
        return True

    async def submit_command(self, command_id, run_id, command_type, payload, created_by):
        self.commands.append((command_id, run_id, command_type, dict(payload)))
        return type("Cmd", (), {"command_id": command_id})()

    async def create_canonical_run(self, run_id, workflow_resource_id, inputs, actor, **kwargs):
        self.canonical_calls.append(("create_canonical_run", run_id, workflow_resource_id, actor))
        run = FakeRun(
            run_id,
            "fault-zeroing",
            1,
            dict(inputs),
            actor.user_id,
            snapshot={**dict(kwargs.get("intake_snapshot") or {}), "run_evidence": {}},
        )
        self.runs[run_id] = run
        return run

    async def create_canonical_paused_run(self, run_id, workflow_resource_id, inputs, actor, **kwargs):
        self.canonical_calls.append(("create_canonical_paused_run", run_id, workflow_resource_id, actor))
        run = FakeRun(
            run_id,
            "fault-zeroing",
            1,
            dict(inputs),
            actor.user_id,
            status="paused",
            snapshot=dict(kwargs.get("intake_snapshot") or {}),
            model_name=kwargs.get("model_name"),
        )
        self.runs[run_id] = run
        return run


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
    inputs = {"upload_dir": "/mnt/user-data/uploads"}

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
                inputs={},
                created_by="user-1",
            )
        )

    assert excinfo.value.reason_code == "intake_evidence_missing_both"
    assert store.runs == {}  # no usable run is created


def test_description_only_start_pauses_with_derived_hybrid_snapshot(kernel_env) -> None:
    """A non-empty description satisfies the document side (glossary)."""

    _, _, _, _, kernel, store, _ = kernel_env

    result = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs={"problem_description": "主轴电机过热报警，请分析根因"},
            created_by="user-1",
        )
    )

    assert result.status == "paused"
    record = store.runs[result.run_id].snapshot["evidence_intake"]
    assert record["missing"] == ["code_evidence_package"]
    # The mode in the Run snapshot is the derived system result.
    assert record["evidence_mode"] == "hybrid"


def test_user_supplied_evidence_mode_in_inputs_is_ignored(kernel_env) -> None:
    """evidence_mode is no longer a caller input; a stale value cannot
    resurrect a document-only run."""

    _, _, _, _, kernel, store, _ = kernel_env

    result = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs={"problem_description": "主轴电机过热报警", "evidence_mode": "document"},
            created_by="user-1",
        )
    )

    record = store.runs[result.run_id].snapshot["evidence_intake"]
    assert record["evidence_mode"] == "hybrid"
    assert record["missing"] == ["code_evidence_package"]


# ---------------------------------------------------------------------------
# Canonical resource runs (frozen UUID closure through the same intake gate).
# ---------------------------------------------------------------------------


def _actor():
    return type("Actor", (), {"user_id": "user-1", "department_id": None, "tool_groups": None})()


def test_start_canonical_run_queues_through_frozen_closure(kernel_env) -> None:
    _, _, _, _, kernel, store, _ = kernel_env
    actor = _actor()

    result = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs=dict(BASE_INPUTS),
            created_by="user-1",
            workflow_resource_id="wf-resource-uuid",
            actor=actor,
        )
    )

    assert result.status == "queued"
    # The canonical contract, not the legacy name+version rows.
    assert [call[0] for call in store.canonical_calls] == ["create_canonical_run"]
    assert store.canonical_calls[0][2] == "wf-resource-uuid"
    # The intake contract stays pinned on the canonical run snapshot.
    assert store.runs[result.run_id].snapshot["contract_version"] == kernel._contract_version
    assert any(event_type == "run_started" for _, event_type, _ in store.events)


def test_start_canonical_run_pauses_with_intake_snapshot(kernel_env) -> None:
    _, _, _, _, kernel, store, _ = kernel_env
    actor = _actor()
    inputs = {"upload_dir": "/mnt/user-data/uploads"}

    result = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs=inputs,
            created_by="user-1",
            workflow_resource_id="wf-resource-uuid",
            actor=actor,
        )
    )

    assert result.status == "paused"
    assert [call[0] for call in store.canonical_calls] == ["create_canonical_paused_run"]
    run = store.runs[result.run_id]
    assert run.status == "paused"
    # The paused canonical run keeps the intake record the confirm path reads.
    assert run.snapshot["interrupt"][0]["type"] == "evidence_confirmation"
    assert run.snapshot["contract_version"] == kernel._contract_version
    assert any(event_type == "interrupted" for _, event_type, _ in store.events)


def test_start_canonical_run_rejects_before_creating_anything(kernel_env) -> None:
    _, _, _, kernel_mod, kernel, store, _ = kernel_env
    actor = _actor()

    with pytest.raises(kernel_mod.EvidenceIntakeRejected):
        asyncio.run(
            kernel.start_run(
                workflow_name="fault-zeroing",
                definition_version=1,
                inputs={},
                created_by="user-1",
                workflow_resource_id="wf-resource-uuid",
                actor=actor,
            )
        )

    assert store.canonical_calls == []
    assert store.runs == {}


def test_start_run_records_the_invocation_entry(kernel_env) -> None:
    """The entry label rides the kernel snapshot keys and lifecycle events."""

    _, _, _, kernel_mod, kernel, store, _ = kernel_env

    queued = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs=dict(BASE_INPUTS),
            created_by="user-1",
            entry="workflow",
        )
    )
    paused = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs={"upload_dir": "/u"},
            created_by="user-1",
            entry="workflow",
        )
    )

    assert store.runs[queued.run_id].snapshot[kernel_mod.SNAPSHOT_ENTRY_KEY] == "workflow"
    assert store.runs[paused.run_id].snapshot[kernel_mod.SNAPSHOT_ENTRY_KEY] == "workflow"
    assert any(event_type == "run_started" and payload.get("entry") == "workflow" for _, event_type, payload in store.events)
    assert any(event_type == kernel_mod.EVENT_INTERRUPTED and payload.get("entry") == "workflow" for _, event_type, payload in store.events)


def test_confirm_evidence_resumes_paused_run(kernel_env) -> None:
    _, _, _, _, kernel, store, _ = kernel_env
    started = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs={"upload_dir": "/u"},
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


def test_confirm_evidence_requires_paused_run(kernel_env) -> None:
    _, _, _, kernel_mod, kernel, store, _ = kernel_env
    started = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs=dict(BASE_INPUTS),
            created_by="user-1",
        )
    )

    with pytest.raises(kernel_mod.ConfirmationStaleError) as excinfo:
        asyncio.run(
            kernel.confirm_evidence(
                started.run_id,
                payload={"input_snapshot_hash": "whatever"},
                confirmed_by="user-1",
            )
        )
    assert excinfo.value.reason_code == kernel_mod.REASON_RUN_NOT_PAUSED
    assert not store.commands


def test_new_material_requires_reconfirmation(kernel_env) -> None:
    _, _, _, kernel_mod, kernel, store, _ = kernel_env
    started = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs={"upload_dir": "/u"},
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


def test_description_change_after_pause_requires_reconfirmation(kernel_env) -> None:
    """The problem description is part of the confirmation-bound hash."""

    _, _, _, kernel_mod, kernel, store, _ = kernel_env
    started = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs={"problem_description": "主轴电机过热报警"},
            created_by="user-1",
        )
    )
    interrupt = store.runs[started.run_id].snapshot["interrupt"][0]

    # The description changed after the pause: the presented hash is stale.
    store.runs[started.run_id].inputs = dict(store.runs[started.run_id].inputs, problem_description="主轴电机过热停机")

    with pytest.raises(kernel_mod.ConfirmationStaleError) as excinfo:
        asyncio.run(
            kernel.confirm_evidence(
                started.run_id,
                payload={"input_snapshot_hash": interrupt["input_snapshot_hash"]},
                confirmed_by="user-1",
            )
        )
    assert excinfo.value.reason_code == "intake_snapshot_changed"
    assert not store.commands


def test_confirm_succeeds_while_description_unchanged(kernel_env) -> None:
    _, _, _, _, kernel, store, _ = kernel_env
    started = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs={"problem_description": "主轴电机过热报警"},
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

    assert result["missing_evidence_sides"] == ["code_evidence_package"]
    assert store.commands and store.commands[0][2] == "resume"


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
            inputs={"upload_dir": "/u"},
            created_by="user-1",
        )
    )

    completion = asyncio.run(kernel.evaluate_completion(started.run_id, str(outputs_dir)))

    assert completion.status == "failed"
    assert "hybrid_disclosure_missing" in completion.reason_codes


def test_completion_uses_the_contract_version_pinned_on_the_snapshot(kernel_env) -> None:
    """A run is judged by the contract version it started with (ticket 03 P2)."""

    _, _, _, kernel_mod, kernel, store, outputs_dir = kernel_env
    started = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs=dict(BASE_INPUTS),
            created_by="user-1",
        )
    )
    store.runs[started.run_id].snapshot["contract_version"] = "9.9.9"

    completion = asyncio.run(kernel.evaluate_completion(started.run_id, str(outputs_dir)))

    assert completion.verdict.contract_version == "9.9.9"
    assert completion.status == "failed"
    assert "contract_version_unsupported" in completion.reason_codes
    assert any(event_type == kernel_mod.EVENT_CONTRACT_FAILED and payload["contract_version"] == "9.9.9" for _, event_type, payload in store.events)


def test_explicit_contract_version_argument_overrides_the_pin(kernel_env) -> None:
    _, _, _, _, kernel, store, outputs_dir = kernel_env
    started = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs=dict(BASE_INPUTS),
            created_by="user-1",
        )
    )
    store.runs[started.run_id].snapshot["contract_version"] = "9.9.9"

    completion = asyncio.run(kernel.evaluate_completion(started.run_id, str(outputs_dir), contract_version=kernel._contract_version))

    assert completion.status == "completed"


def test_judge_completion_is_a_pure_kernel_entry_with_events(kernel_env, tmp_path: Path) -> None:
    """The sync judgment entry (no store, no run id) returns the same verdict,
    completion status and kernel events the store-backed evaluation logs."""

    _, _, _, kernel_mod, kernel, store, outputs_dir = kernel_env
    started = asyncio.run(
        kernel.start_run(
            workflow_name="fault-zeroing",
            definition_version=1,
            inputs={"upload_dir": "/u"},
            created_by="user-1",
        )
    )
    snapshot = dict(store.runs[started.run_id].snapshot)

    judgment = kernel_mod.judge_completion(snapshot, str(outputs_dir))

    assert judgment.status == kernel_mod.COMPLETION_STATUS_FAILED
    assert "hybrid_disclosure_missing" in judgment.reason_codes
    assert [(event_type, dict(payload)) for event_type, payload in judgment.events] == [(kernel_mod.EVENT_CONTRACT_FAILED, {"code": "contract_failed", "contract_version": kernel_mod.CONTRACT_VERSION, "reason_codes": judgment.reason_codes})]

    passing_dir = tmp_path / "passing"
    passing_dir.mkdir()
    # The passing case needs an intake record with no missing sides; the
    # paused run's record pins a disclosure the valid fixture does not carry.
    fully_evidenced = {
        **snapshot,
        "evidence_intake": {**snapshot["evidence_intake"], "missing": []},
    }
    passing = kernel_mod.judge_completion(fully_evidenced, str(make_valid_outputs(passing_dir)))
    assert passing.status == kernel_mod.COMPLETION_STATUS_COMPLETED
    event_type, payload = passing.events[0]
    assert event_type == kernel_mod.EVENT_CONTRACT_EVALUATED
    assert payload["code"] == "contract_passed"
    assert "pending_verification_disclosed" in payload


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
