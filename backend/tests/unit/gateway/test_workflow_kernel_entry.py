"""S3 seam: the workflow launch endpoints adopt the kernel canonical path.

Ticket 03: when the target workflow declares a ``result_contract``, starting
a run must go through ``FaultZeroingKernel.start_run`` — double-missing
evidence is a 4xx rejection without any Run row, a single missing side parks
a paused Run with the missing-side information, and complete evidence queues
through the canonical freeze with the kernel pins.  Everything else (RBAC,
the plain non-contract path, the run detail payload) must keep its existing
gateway behavior.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agentplatform import rbac_models as _rbac_models  # noqa: F401 - register auth tables
from app.agentplatform import resource_models as _resource_models  # noqa: F401 - register resource tables
from app.agentplatform.fault_zeroing.contract import CONTRACT_VERSION
from app.agentplatform.fault_zeroing.intake import INTERRUPT_TYPE
from app.agentplatform.rbac_models import UserModel, UserRole
from app.agentplatform.resource_models import Resource, ResourceVersion
from app.gateway.routers import resources
from app.gateway.routers.resources import WorkflowCommandRequest, WorkflowRunRequest
from deerflow.persistence.base import Base as DeerFlowBase
from deerflow.persistence.models.workflow_v2 import WorkflowTaskRow, WorkflowV2RunRow

FULL_EVIDENCE_INPUTS = {
    "upload_dir": "/mnt/user-data/uploads",
    "code_package_source": "/mnt/user-data/code-evidence/pkg-1/source",
    "problem_description": "主轴电机过热报警",
}
DOCUMENT_ONLY_INPUTS = {"problem_description": "主轴电机过热报警"}

CONTRACT_VALIDATOR = "app.agentplatform.fault_zeroing.entries:evaluate_workflow_contract"


def _definition(*, with_contract: bool) -> dict:
    definition = {
        "schema_version": 2,
        "name": "fault-zeroing",
        "inputs": {
            "evidence_mode": {"type": "string", "default": "hybrid"},
            "output_base_dir": {"type": "string", "default": "/mnt/user-data/outputs"},
        },
        "state": {},
        "entrypoint": "only",
        "nodes": [{"id": "only", "type": "action", "action": {"kind": "tool", "name": "finish"}}],
        "edges": [],
    }
    if with_contract:
        definition["result_contract"] = {"validator": CONTRACT_VALIDATOR}
    return definition


def _user(role: UserRole, user_id: str) -> UserModel:
    return UserModel(id=user_id, username=f"{user_id}@test.com", role=role, department_id=None, disabled=False)


@pytest_asyncio.fixture
async def env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'gateway.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(DeerFlowBase.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(resources, "_factory", lambda: factory)
    async with factory() as session:
        for user_id, role in (("owner-1", UserRole.USER), ("viewer-1", UserRole.VIEWER)):
            session.add(UserModel(id=user_id, username=f"{user_id}@test.com", role=role, disabled=False))
        for resource_id, slug, with_contract in (
            ("wf-contract", "fault-zeroing", True),
            ("wf-plain", "plain-workflow", False),
        ):
            definition = _definition(with_contract=with_contract)
            session.add(
                Resource(
                    id=resource_id,
                    type="workflow",
                    slug=slug,
                    display_name=slug,
                    owner_id="owner-1",
                    visibility="public",
                    scope_department_id=None,
                    lifecycle_status="active",
                    latest_version=1,
                    draft_revision=0,
                    storage_kind="database",
                    storage_key=f"workflows/{resource_id}",
                    system_owned=False,
                    authz_revision=1,
                )
            )
            session.add(
                ResourceVersion(
                    id=f"wv-{resource_id}",
                    resource_id=resource_id,
                    version=1,
                    content_hash="a" * 64,
                    storage_key=f"workflows/{resource_id}/versions/1",
                    scan_result={},
                    content=definition,
                    created_by="owner-1",
                )
            )
        await session.commit()
    yield SimpleNamespace(factory=factory, engine=engine)
    await engine.dispose()


async def _run_rows(factory, model=WorkflowV2RunRow):
    async with factory() as session:
        return list((await session.execute(select(model))).scalars())


async def _task_rows(factory):
    async with factory() as session:
        return list((await session.execute(select(WorkflowTaskRow))).scalars())


# ---------------------------------------------------------------------------
# Three intake paths end to end (acceptance: 双缺 4xx 不创建 Run；单缺 paused；
# 双侧齐 canonical 冻结 + 契约版本钉扎).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_double_missing_evidence_is_rejected_without_creating_a_run(env) -> None:
    with pytest.raises(HTTPException) as excinfo:
        await resources.create_workflow_run(
            "wf-contract",
            body=WorkflowRunRequest(inputs={}),
            current_user=_user(UserRole.USER, "owner-1"),
        )

    assert excinfo.value.status_code == 422
    detail = excinfo.value.detail
    assert detail["code"] == "intake_evidence_missing_both"
    assert await _run_rows(env.factory) == []
    assert await _task_rows(env.factory) == []


@pytest.mark.asyncio
async def test_single_missing_side_parks_a_paused_run_with_missing_side_info(env) -> None:
    response = await resources.create_workflow_run(
        "wf-contract",
        body=WorkflowRunRequest(inputs=dict(DOCUMENT_ONLY_INPUTS)),
        current_user=_user(UserRole.USER, "owner-1"),
    )

    assert response["status"] == "paused"
    assert response["missing_evidence_sides"] == ["code_evidence_package"]
    assert response["reason_code"] == "intake_confirmation_required"
    runs = await _run_rows(env.factory)
    assert len(runs) == 1 and runs[0].status == "paused"
    assert runs[0].snapshot["evidence_intake"]["missing"] == ["code_evidence_package"]
    assert runs[0].snapshot["contract_version"] == CONTRACT_VERSION
    assert runs[0].snapshot["entry"] == "workflow"
    assert runs[0].snapshot["interrupt"][0]["type"] == INTERRUPT_TYPE
    tasks = await _task_rows(env.factory)
    assert len(tasks) == 1 and tasks[0].status == "paused"
    store = resources.WorkflowV2Store(env.factory)
    events = await store.list_events(runs[0].run_id)
    assert any(event.event_type == "interrupted" and event.payload["code"] == "intake_confirmation_required" for event in events)


@pytest.mark.asyncio
async def test_paused_run_inputs_carry_the_declared_defaults(env) -> None:
    """单缺侧暂停的 Run 也要应用定义声明的输入默认值。

    前端留空不发送、聊天工具只传证据字段：paused 创建路径若原样落库
    inputs，确认恢复后 ``output_base_dir`` 等默认值缺失，五件套写根全部
    无法渲染，契约门必然判 failed。
    """

    response = await resources.create_workflow_run(
        "wf-contract",
        body=WorkflowRunRequest(inputs=dict(DOCUMENT_ONLY_INPUTS)),
        current_user=_user(UserRole.USER, "owner-1"),
    )

    assert response["status"] == "paused"
    runs = await _run_rows(env.factory)
    assert runs[0].inputs["output_base_dir"] == "/mnt/user-data/outputs"
    assert runs[0].inputs["evidence_mode"] == "hybrid"
    assert runs[0].inputs["problem_description"] == DOCUMENT_ONLY_INPUTS["problem_description"]


@pytest.mark.asyncio
async def test_paused_launch_enforces_concurrency_limits(env, monkeypatch) -> None:
    """达到并发上限时发起单缺侧：按既有并发语义 4xx，且不创建 paused Run。"""

    monkeypatch.setattr(
        resources,
        "get_app_config",
        lambda: SimpleNamespace(
            workflow_runtime=SimpleNamespace(user_concurrency=1, department_concurrency=None),
            get_model_config=lambda name: None,
        ),
    )

    started = await resources.create_workflow_run(
        "wf-contract",
        body=WorkflowRunRequest(inputs=dict(FULL_EVIDENCE_INPUTS)),
        current_user=_user(UserRole.USER, "owner-1"),
    )
    assert started["status"] == "queued"

    with pytest.raises(HTTPException) as excinfo:
        await resources.create_workflow_run(
            "wf-contract",
            body=WorkflowRunRequest(inputs=dict(DOCUMENT_ONLY_INPUTS)),
            current_user=_user(UserRole.USER, "owner-1"),
        )

    assert excinfo.value.status_code == 429
    runs = await _run_rows(env.factory)
    assert len(runs) == 1 and runs[0].status == "queued"


@pytest.mark.asyncio
async def test_full_evidence_queues_through_the_canonical_freeze(env) -> None:
    response = await resources.create_workflow_run(
        "wf-contract",
        body=WorkflowRunRequest(inputs=dict(FULL_EVIDENCE_INPUTS)),
        current_user=_user(UserRole.USER, "owner-1"),
    )

    assert response["status"] == "queued"
    runs = await _run_rows(env.factory)
    assert len(runs) == 1 and runs[0].status == "queued"
    # Canonical freeze + kernel pins landed with the run row itself.
    assert runs[0].snapshot["run_evidence"]["resource_snapshots"]
    assert runs[0].snapshot["evidence_intake"]["status"] == "execute"
    assert runs[0].snapshot["contract_version"] == CONTRACT_VERSION
    assert runs[0].snapshot["entry"] == "workflow"
    tasks = await _task_rows(env.factory)
    assert len(tasks) == 1 and tasks[0].status == "queued"
    store = resources.WorkflowV2Store(env.factory)
    events = await store.list_events(runs[0].run_id)
    started = [event for event in events if event.event_type == "run_started"]
    assert len(started) == 1
    assert started[0].payload["entry"] == "workflow"
    assert started[0].payload["contract_version"] == CONTRACT_VERSION


@pytest.mark.asyncio
async def test_workflow_without_contract_keeps_the_plain_launch_path(env) -> None:
    """No declared contract: the current direct canonical launch, unchanged."""

    response = await resources.create_workflow_run(
        "wf-plain",
        body=WorkflowRunRequest(inputs={"topic": "any"}),
        current_user=_user(UserRole.USER, "owner-1"),
    )

    assert response["status"] == "queued"
    runs = await _run_rows(env.factory)
    assert len(runs) == 1 and runs[0].status == "queued"
    assert "evidence_intake" not in runs[0].snapshot
    assert "entry" not in runs[0].snapshot


# ---------------------------------------------------------------------------
# RBAC regression: 无使用权限用户发起被拒.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_without_use_permission_is_rejected(env) -> None:
    with pytest.raises(HTTPException) as excinfo:
        await resources.create_workflow_run(
            "wf-contract",
            body=WorkflowRunRequest(inputs=dict(FULL_EVIDENCE_INPUTS)),
            current_user=_user(UserRole.VIEWER, "viewer-1"),
        )

    assert excinfo.value.status_code == 403
    assert await _run_rows(env.factory) == []


# ---------------------------------------------------------------------------
# Run detail exposure: 收件决定 + entry 标签 + 契约判定事件可读.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_detail_exposes_intake_decision_and_kernel_events(env) -> None:
    started = await resources.create_workflow_run(
        "wf-contract",
        body=WorkflowRunRequest(inputs=dict(DOCUMENT_ONLY_INPUTS)),
        current_user=_user(UserRole.USER, "owner-1"),
    )
    resource_id, run_id = "wf-contract", started["run_id"]

    detail = await resources.get_canonical_workflow_run(resource_id, run_id, _user(UserRole.USER, "owner-1"))

    assert detail["snapshot"]["entry"] == "workflow"
    assert detail["snapshot"]["evidence_intake"]["missing"] == ["code_evidence_package"]
    assert detail["snapshot"]["contract_version"] == CONTRACT_VERSION
    store = resources.WorkflowV2Store(env.factory)
    events = await store.list_events(run_id)
    assert any(event.event_type == "interrupted" for event in events)


# ---------------------------------------------------------------------------
# Evidence confirmation through the existing command API.
# ---------------------------------------------------------------------------


def _request() -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(checkpointer=None)))


@pytest.mark.asyncio
async def test_with_files_kernel_launch_returns_the_stored_code_package(env, monkeypatch) -> None:
    """with-files 内核路径的响应保留既有 code_package 字段（与普通路径同形）。"""

    manifest = SimpleNamespace(
        source_virtual_path="/mnt/user-data/code-evidence/run-pkg/source",
        as_dict=lambda: {"package_id": "run-pkg"},
    )

    async def _fake_store_files(*, run_id, user_id, files):
        return manifest, [f.filename or "" for f in files]

    async def _fake_cleanup(run_id, user_id):
        return None

    monkeypatch.setattr(resources, "_store_workflow_run_files", _fake_store_files)
    monkeypatch.setattr(resources, "_cleanup_run_user_data", _fake_cleanup)

    response = await resources.create_workflow_run_with_files(
        "wf-contract",
        inputs='{"problem_description": "主轴电机过热报警"}',
        model_name=None,
        files=[SimpleNamespace(filename="source.zip")],
        current_user=_user(UserRole.USER, "owner-1"),
    )

    assert response["status"] == "queued"
    assert response["code_package"] == {"package_id": "run-pkg"}
    assert response["missing_evidence_sides"] == []


@pytest.mark.asyncio
async def test_with_files_kernel_launch_binds_materialized_files_to_the_created_run(env, monkeypatch) -> None:
    """预物化的上传与代码包必须落在内核实际创建的 Run 工作区下。"""

    stored_under: dict[str, str] = {}

    async def _fake_store_files(*, run_id, user_id, files):
        stored_under["run_id"] = run_id
        return None, []

    async def _fake_cleanup(run_id, user_id):
        return None

    monkeypatch.setattr(resources, "_store_workflow_run_files", _fake_store_files)
    monkeypatch.setattr(resources, "_cleanup_run_user_data", _fake_cleanup)

    response = await resources.create_workflow_run_with_files(
        "wf-contract",
        inputs='{"problem_description": "主轴电机过热报警"}',
        model_name=None,
        files=[SimpleNamespace(filename="log.txt")],
        current_user=_user(UserRole.USER, "owner-1"),
    )

    # No source ZIP in this launch: single-missing-side intake parks the run —
    # the point is that the parked Run owns the pre-materialized workspace.
    assert response["status"] == "paused"
    assert response["run_id"] == stored_under["run_id"]


@pytest.mark.asyncio
async def test_with_files_kernel_launch_cleans_uploads_on_unexpected_error(env, tmp_path, monkeypatch) -> None:
    """内核分支抛出非 Runtime 异常（如存储层错误）时，上传目录必须被清理。"""

    import io

    from sqlalchemy.exc import SQLAlchemyError
    from starlette.datastructures import UploadFile

    from deerflow.config.paths import Paths

    base = tmp_path / "base"
    monkeypatch.setattr(resources, "get_paths", lambda: Paths(base))

    class _ExplodingKernel:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def start_run(self, **kwargs):
            raise SQLAlchemyError("store exploded")

    monkeypatch.setattr(resources, "FaultZeroingKernel", _ExplodingKernel)

    real_store_files = resources._store_workflow_run_files
    recorded: dict[str, str] = {}

    async def _recording_store_files(*, run_id, user_id, files):
        result = await real_store_files(run_id=run_id, user_id=user_id, files=files)
        recorded["run_id"] = run_id
        return result

    monkeypatch.setattr(resources, "_store_workflow_run_files", _recording_store_files)

    with pytest.raises(SQLAlchemyError):
        await resources.create_workflow_run_with_files(
            "wf-contract",
            inputs='{"problem_description": "主轴电机过热报警"}',
            model_name=None,
            files=[UploadFile(file=io.BytesIO(b"evidence"), filename="log.txt")],
            current_user=_user(UserRole.USER, "owner-1"),
        )

    uploads_dir = Paths(base).sandbox_uploads_dir(recorded["run_id"], user_id="owner-1")
    assert not uploads_dir.exists() or list(uploads_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_resume_on_an_evidence_pause_confirms_through_the_kernel(env) -> None:
    started = await resources.create_workflow_run(
        "wf-contract",
        body=WorkflowRunRequest(inputs=dict(DOCUMENT_ONLY_INPUTS)),
        current_user=_user(UserRole.USER, "owner-1"),
    )
    run_id = started["run_id"]
    store = resources.WorkflowV2Store(env.factory)
    run = await store.get_run(run_id)
    presented_hash = run.snapshot["interrupt"][0]["input_snapshot_hash"]

    response = await resources.submit_canonical_workflow_command(
        "wf-contract",
        run_id,
        body=WorkflowCommandRequest(command_id="cmd-confirm-1", type="resume", payload={"input_snapshot_hash": presented_hash}),
        request=_request(),
        current_user=_user(UserRole.USER, "owner-1"),
    )

    assert response["accepted"] is True
    assert response["command_id"]
    assert response["missing_evidence_sides"] == ["code_evidence_package"]
    resumed = await store.get_run(run_id)
    assert resumed is not None and resumed.status == "queued"
    assert resumed.snapshot["evidence_intake"]["confirmed"] is True
    assert resumed.snapshot["entry"] == "workflow"
    tasks = await _task_rows(env.factory)
    assert tasks[0].status == "queued"
    events = await store.list_events(run_id)
    resumed_events = [event for event in events if event.event_type == "resumed"]
    assert len(resumed_events) == 1
    assert resumed_events[0].payload["confirmed_by"] == "owner-1"
    assert resumed_events[0].payload["input_snapshot_hash"] == presented_hash


@pytest.mark.asyncio
async def test_stale_confirmation_hash_is_rejected_and_recorded(env) -> None:
    started = await resources.create_workflow_run(
        "wf-contract",
        body=WorkflowRunRequest(inputs=dict(DOCUMENT_ONLY_INPUTS)),
        current_user=_user(UserRole.USER, "owner-1"),
    )
    run_id = started["run_id"]
    store = resources.WorkflowV2Store(env.factory)

    with pytest.raises(HTTPException) as excinfo:
        await resources.submit_canonical_workflow_command(
            "wf-contract",
            run_id,
            body=WorkflowCommandRequest(command_id="cmd-confirm-2", type="resume", payload={"input_snapshot_hash": "stale"}),
            request=_request(),
            current_user=_user(UserRole.USER, "owner-1"),
        )

    assert excinfo.value.status_code == 409
    assert excinfo.value.detail["code"] == "intake_snapshot_changed"
    still_paused = await store.get_run(run_id)
    assert still_paused is not None and still_paused.status == "paused"
    events = await store.list_events(run_id)
    assert any(event.event_type == "kernel_confirmation_rejected" for event in events)
