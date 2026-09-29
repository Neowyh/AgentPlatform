"""S1 seam: the fault-zeroing kernel against the real WorkflowV2Store.

Ticket 03 routes the workflow entry through the kernel's canonical creation
path, so the pins, the pause and the kernel events must all survive real
SQLite persistence — a lease-guarded snapshot write or a lease-checked event
append would silently lose the intake record, the contract pin or the audit
trail while every fake-store test kept passing.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agentplatform.fault_zeroing.contract import CONTRACT_VERSION
from app.agentplatform.fault_zeroing.kernel import (
    SNAPSHOT_CONTRACT_VERSION_KEY,
    SNAPSHOT_ENTRY_KEY,
    SNAPSHOT_INTAKE_KEY,
    ConfirmationStaleError,
    EvidenceIntakeRejected,
    FaultZeroingKernel,
)
from app.agentplatform.resources.runtime import _json_hash
from app.agentplatform.resources.service import ResourceAction, ResourceActor
from app.agentplatform.workflows.v2.store import WorkflowV2Store
from deerflow.persistence.base import Base
from deerflow.persistence.models.workflow_v2 import WorkflowTaskRow, WorkflowV2RunRow

REPO_ROOT = Path(__file__).resolve().parents[4]

FULL_EVIDENCE_INPUTS = {
    "upload_dir": "/mnt/user-data/uploads",
    "code_package_source": "/mnt/user-data/code-evidence/pkg-1/source",
    "problem_description": "主轴电机过热报警",
}
DOCUMENT_ONLY_INPUTS = {"problem_description": "主轴电机过热报警"}


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'workflow.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield WorkflowV2Store(async_sessionmaker(engine, expire_on_commit=False))
    finally:
        await engine.dispose()


def _actor() -> ResourceActor:
    return ResourceActor(
        user_id="user-1",
        department_id=None,
        role="user",
        permissions=frozenset({ResourceAction.READ, ResourceAction.USE}),
        tool_groups=None,
    )


async def _seed_workflow(store: WorkflowV2Store) -> str:
    """Freeze-ready canonical workflow resource with a single published version."""

    from app.agentplatform.resource_models import Resource, ResourceVersion

    workflow_id = str(uuid4())
    definition = {
        "schema_version": 2,
        "name": "fault-zeroing",
        "inputs": {},
        "state": {},
        "entrypoint": "only",
        "nodes": [{"id": "only", "type": "action", "action": {"kind": "tool", "name": "finish"}}],
        "edges": [],
    }
    async with store.session_factory() as session:
        session.add(
            Resource(
                id=workflow_id,
                type="workflow",
                slug="fault-zeroing",
                display_name="fault-zeroing",
                owner_id="user-1",
                visibility="public",
                scope_department_id=None,
                lifecycle_status="active",
                latest_version=1,
                draft_revision=0,
                storage_kind="database",
                storage_key=f"workflows/{workflow_id}",
                system_owned=False,
                authz_revision=1,
            )
        )
        session.add(
            ResourceVersion(
                id=f"wv-{workflow_id}",
                resource_id=workflow_id,
                version=1,
                content_hash=_json_hash(definition),
                storage_key=f"workflows/{workflow_id}/versions/1",
                scan_result={},
                content=definition,
                created_by="user-1",
            )
        )
        await session.commit()
    return workflow_id


def _contract_fixtures():
    spec = importlib.util.spec_from_file_location(
        "fz_contract_fixtures_kernel_store",
        REPO_ROOT / "backend" / "tests" / "unit" / "fault_zeroing" / "test_contract.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("fz_contract_fixtures_kernel_store", module)
    spec.loader.exec_module(module)
    return module


async def _run_task_status(store: WorkflowV2Store, run_id: str) -> str | None:
    async with store.session_factory() as session:
        task = (await session.execute(select(WorkflowTaskRow).where(WorkflowTaskRow.run_id == run_id))).scalar_one_or_none()
        return task.status if task is not None else None


async def _start(kernel: FaultZeroingKernel, store: WorkflowV2Store, inputs: dict, **kwargs):
    workflow_id = await _seed_workflow(store)
    return await kernel.start_run(
        workflow_name="fault-zeroing",
        definition_version=1,
        inputs=dict(inputs),
        created_by="user-1",
        workflow_resource_id=workflow_id,
        actor=_actor(),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_canonical_queued_run_pins_kernel_snapshot_keys_and_logs_start(store: WorkflowV2Store) -> None:
    """双侧齐：canonical 冻结 + intake/contract/entry 钉扎 + run_started 事件留痕."""

    kernel = FaultZeroingKernel(store)
    result = await _start(kernel, store, FULL_EVIDENCE_INPUTS, entry="workflow")

    assert result.status == "queued"
    run = await store.get_run(result.run_id)
    assert run is not None and run.status == "queued"
    assert run.snapshot[SNAPSHOT_INTAKE_KEY]["status"] == "execute"
    assert run.snapshot[SNAPSHOT_CONTRACT_VERSION_KEY] == CONTRACT_VERSION
    assert run.snapshot[SNAPSHOT_ENTRY_KEY] == "workflow"

    events = await store.list_events(result.run_id)
    started = [event for event in events if event.event_type == "run_started"]
    assert len(started) == 1
    assert started[0].payload["code"] == "intake_evidence_complete"
    assert started[0].payload["entry"] == "workflow"
    assert started[0].payload["contract_version"] == CONTRACT_VERSION


@pytest.mark.asyncio
async def test_canonical_paused_run_stays_parked_with_intake_event(store: WorkflowV2Store) -> None:
    """单缺：canonical paused Run，缺侧信息入快照，interrupted 事件留痕."""

    kernel = FaultZeroingKernel(store)
    result = await _start(kernel, store, DOCUMENT_ONLY_INPUTS, entry="workflow")

    assert result.status == "paused"
    assert result.intake.missing == ("code_evidence_package",)
    run = await store.get_run(result.run_id)
    assert run is not None and run.status == "paused"
    assert run.snapshot[SNAPSHOT_INTAKE_KEY]["missing"] == ["code_evidence_package"]
    assert run.snapshot[SNAPSHOT_CONTRACT_VERSION_KEY] == CONTRACT_VERSION
    assert run.snapshot[SNAPSHOT_ENTRY_KEY] == "workflow"
    interrupt = run.snapshot["interrupt"][0]
    assert interrupt["type"] == "evidence_confirmation"
    assert interrupt["missing"] == ["code_evidence_package"]

    assert await _run_task_status(store, result.run_id) == "paused"

    events = await store.list_events(result.run_id)
    interrupted = [event for event in events if event.event_type == "interrupted"]
    assert len(interrupted) == 1
    assert interrupted[0].payload["code"] == "intake_confirmation_required"
    assert interrupted[0].payload["entry"] == "workflow"


@pytest.mark.asyncio
async def test_double_missing_rejection_creates_no_run_row(store: WorkflowV2Store) -> None:
    """双缺：4xx 语义的拒绝（不创建任何 Run 行）。"""

    kernel = FaultZeroingKernel(store)

    with pytest.raises(EvidenceIntakeRejected) as excinfo:
        await _start(kernel, store, {})

    assert excinfo.value.reason_code == "intake_evidence_missing_both"
    async with store.session_factory() as session:
        runs = list((await session.execute(select(WorkflowV2RunRow))).scalars())
        tasks = list((await session.execute(select(WorkflowTaskRow))).scalars())
    assert runs == [] and tasks == []


@pytest.mark.asyncio
async def test_canonical_paused_run_keeps_the_requested_model(store: WorkflowV2Store) -> None:
    """单缺 paused Run 仍保留发起时的模型选择：恢复后 worker 用同一模型执行."""

    kernel = FaultZeroingKernel(store)
    result = await _start(kernel, store, DOCUMENT_ONLY_INPUTS, entry="workflow", model_name="model-b")

    run = await store.get_run(result.run_id)
    assert run is not None and run.model_name == "model-b"


@pytest.mark.asyncio
async def test_confirm_evidence_resumes_paused_run_and_leaves_audit_trail(store: WorkflowV2Store) -> None:
    """确认恢复：哈希绑定校验通过 → intake 记录确认留痕 + resume 命令 + resumed 事件."""

    kernel = FaultZeroingKernel(store)
    started = await _start(kernel, store, DOCUMENT_ONLY_INPUTS, entry="workflow")
    paused = await store.get_run(started.run_id)
    interrupt = paused.snapshot["interrupt"][0]

    confirmation = await kernel.confirm_evidence(
        started.run_id,
        payload={"input_snapshot_hash": interrupt["input_snapshot_hash"]},
        confirmed_by="user-1",
    )

    assert confirmation["missing_evidence_sides"] == ["code_evidence_package"]
    resumed_run = await store.get_run(started.run_id)
    assert resumed_run is not None and resumed_run.status == "queued"
    record = resumed_run.snapshot[SNAPSHOT_INTAKE_KEY]
    assert record["confirmed"] is True
    assert record["confirmed_by"] == "user-1"
    assert record["confirmed_snapshot_hash"] == interrupt["input_snapshot_hash"]
    # The pins survive the confirmation snapshot update.
    assert resumed_run.snapshot[SNAPSHOT_CONTRACT_VERSION_KEY] == CONTRACT_VERSION
    assert resumed_run.snapshot[SNAPSHOT_ENTRY_KEY] == "workflow"

    assert await _run_task_status(store, started.run_id) == "queued"
    command = await store.latest_command(started.run_id, "resume")
    assert command is not None
    assert command.payload["input_snapshot_hash"] == interrupt["input_snapshot_hash"]

    events = await store.list_events(started.run_id)
    resumed = [event for event in events if event.event_type == "resumed"]
    assert len(resumed) == 1
    assert resumed[0].payload["confirmed_by"] == "user-1"
    assert resumed[0].payload["input_snapshot_hash"] == interrupt["input_snapshot_hash"]


@pytest.mark.asyncio
async def test_confirm_with_stale_hash_is_rejected_and_recorded(store: WorkflowV2Store) -> None:
    """快照哈希不匹配：确认被拒并留 kernel_confirmation_rejected 事件."""

    kernel = FaultZeroingKernel(store)
    started = await _start(kernel, store, DOCUMENT_ONLY_INPUTS)

    with pytest.raises(ConfirmationStaleError) as excinfo:
        await kernel.confirm_evidence(
            started.run_id,
            payload={"input_snapshot_hash": "stale-hash"},
            confirmed_by="user-1",
        )

    assert excinfo.value.reason_code == "intake_snapshot_changed"
    still_paused = await store.get_run(started.run_id)
    assert still_paused is not None and still_paused.status == "paused"
    assert await store.latest_command(started.run_id, "resume") is None

    events = await store.list_events(started.run_id)
    rejections = [event for event in events if event.event_type == "kernel_confirmation_rejected"]
    assert len(rejections) == 1
    assert rejections[0].payload["code"] == "intake_snapshot_changed"


@pytest.mark.asyncio
async def test_confirm_requires_a_run_paused_by_intake(store: WorkflowV2Store) -> None:
    """非 paused Run 的确认被拒并留事件（不静默恢复）。"""

    kernel = FaultZeroingKernel(store)
    started = await _start(kernel, store, FULL_EVIDENCE_INPUTS)

    with pytest.raises(ConfirmationStaleError) as excinfo:
        await kernel.confirm_evidence(
            started.run_id,
            payload={"input_snapshot_hash": "whatever"},
            confirmed_by="user-1",
        )

    assert excinfo.value.reason_code == "run_not_paused_for_confirmation"
    events = await store.list_events(started.run_id)
    assert any(event.event_type == "kernel_confirmation_rejected" for event in events)
    assert await store.latest_command(started.run_id, "resume") is None


@pytest.mark.asyncio
async def test_completion_evaluation_persists_kernel_contract_event(store: WorkflowV2Store, tmp_path: Path) -> None:
    """完成判定经内核评估后，kernel_contract_evaluated 事件在真存储留痕."""

    fixtures = _contract_fixtures()
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    outputs = fixtures.write_outputs(output_dir)

    kernel = FaultZeroingKernel(store)
    started = await _start(kernel, store, FULL_EVIDENCE_INPUTS)

    completion = await kernel.evaluate_completion(started.run_id, str(outputs))

    assert completion.status == "completed"
    assert completion.pending_verification is True
    events = await store.list_events(started.run_id)
    evaluated = [event for event in events if event.event_type == "kernel_contract_evaluated"]
    assert len(evaluated) == 1
    assert evaluated[0].payload["code"] == "contract_passed"
    assert evaluated[0].payload["contract_version"] == CONTRACT_VERSION
    assert evaluated[0].payload["pending_verification_disclosed"] is True
