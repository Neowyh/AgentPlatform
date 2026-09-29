"""S4 seam: the chat-loop bridge tools over the Fault-zeroing Execution Kernel.

Ticket 04: real analysis requests raised inside the fault-zeroing Expert
closure are promoted into canonical kernel Runs by the ``start_zeroing_run``
tool; evidence declared in the chat is materialized into the Run workspace
and bound by the input snapshot hash; a single missing side parks the Run for
an ask_clarification three-choice confirmation; completion (or contract
violation) bridges the artifacts back into the chat thread.

Everything here drives the tool coroutines directly (the builtin-tool test
convention) against the real intake, the real kernel and a real SQLite
WorkflowV2Store — only the session-factory and filesystem seams are test
doubles.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agentplatform import rbac_models as _rbac_models  # noqa: F401 - register auth tables
from app.agentplatform import resource_models as _resource_models  # noqa: F401 - register resource tables
from app.agentplatform.fault_zeroing.contract import CONTRACT_VERSION, REQUIRED_OUTPUTS
from app.agentplatform.fault_zeroing.intake import INTERRUPT_TYPE
from app.agentplatform.resource_models import Resource, ResourceVersion
from app.agentplatform.resources.runtime import _json_hash
from app.agentplatform.tools import zeroing_run_tool
from deerflow.config.paths import Paths
from deerflow.persistence.base import Base as DeerFlowBase
from deerflow.persistence.models.workflow_v2 import WorkflowTaskRow, WorkflowV2RunRow

PROBLEM = "主轴电机过热报警"


def _definition() -> dict:
    return {
        "schema_version": 2,
        "name": "fault-zeroing",
        "inputs": {},
        "state": {},
        "entrypoint": "only",
        "nodes": [{"id": "only", "type": "action", "action": {"kind": "tool", "name": "finish"}}],
        "edges": [],
        "result_contract": {"validator": "app.agentplatform.fault_zeroing.entries:evaluate_workflow_contract"},
    }


def _runtime(
    thread_id: str = "thread-1",
    user_id: str = "owner-1",
    role: str = "user",
    agent_name: str = "fault-zeroing",
    department_id: str | None = None,
) -> SimpleNamespace:
    context: dict = {"thread_id": thread_id, "user_id": user_id, "user_role": role}
    if department_id is not None:
        context["authz_attributes"] = {"department_id": department_id}
    if agent_name is not None:
        context["agent_name"] = agent_name
    return SimpleNamespace(state=None, context=context, config={"configurable": {"thread_id": thread_id}})


@pytest_asyncio.fixture
async def env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tools.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(DeerFlowBase.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(zeroing_run_tool, "_session_factory", lambda: factory)
    monkeypatch.setattr(zeroing_run_tool, "get_paths", lambda: Paths(tmp_path))
    # The code-evidence helpers resolve their own paths singleton; keep the
    # seeded thread buckets inside the same tmp home.
    monkeypatch.setattr("app.agentplatform.code_evidence.get_paths", lambda: Paths(tmp_path))
    monkeypatch.setattr(
        zeroing_run_tool,
        "_workflow_runtime",
        lambda: SimpleNamespace(user_concurrency=None, department_concurrency=None),
    )
    async with factory() as session:
        session.add(
            Resource(
                id="wf-contract",
                type="workflow",
                slug="fault-zeroing",
                display_name="fault-zeroing",
                owner_id="someone-else",
                visibility="public",
                scope_department_id=None,
                lifecycle_status="active",
                latest_version=1,
                draft_revision=0,
                storage_kind="database",
                storage_key="workflows/wf-contract",
                system_owned=False,
                authz_revision=1,
            )
        )
        session.add(
            ResourceVersion(
                id="wv-wf-contract",
                resource_id="wf-contract",
                version=1,
                content_hash=_json_hash(_definition()),
                storage_key="workflows/wf-contract/versions/1",
                scan_result={},
                content=_definition(),
                created_by="someone-else",
            )
        )
        await session.commit()
    yield SimpleNamespace(factory=factory, paths=Paths(tmp_path), engine=engine)
    await engine.dispose()


async def _run_rows(factory) -> list[WorkflowV2RunRow]:
    async with factory() as session:
        return list((await session.execute(select(WorkflowV2RunRow))).scalars())


async def _task_rows(factory) -> list[WorkflowTaskRow]:
    async with factory() as session:
        return list((await session.execute(select(WorkflowTaskRow))).scalars())


def _payload(result) -> dict:
    """Parse the structured JSON payload from a tool result Command."""

    message = result.update["messages"][0]
    return json.loads(message.content)


def _seed_upload(env, filename: str, content: str = "evidence") -> str:
    uploads = env.paths.sandbox_uploads_dir("thread-1", user_id="owner-1")
    uploads.mkdir(parents=True, exist_ok=True)
    (uploads / filename).write_text(content, encoding="utf-8")
    return f"/mnt/user-data/uploads/{filename}"


def _thread_package_dir(env, thread_id: str, package_id: str):
    return env.paths.thread_dir(thread_id, user_id="owner-1") / "user-data" / "code-evidence" / package_id


def _seed_package(env, package_id: str = "pkg-1") -> str:
    """Seed one accepted Code Evidence Package on the chat thread."""

    package_dir = _thread_package_dir(env, "thread-1", package_id)
    source = package_dir / "source"
    source.mkdir(parents=True, exist_ok=True)
    (source / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    manifest = {
        "package_id": package_id,
        "original_filename": "source.zip",
        "accepted": ["main.c"],
        "excluded": [],
        "rejected": [],
        "compressed_size": 100,
        "expanded_size": 27,
        "source_virtual_path": f"/mnt/user-data/code-evidence/{package_id}/source",
    }
    (package_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return package_id


async def _finish_run(env, run_id: str, *, status: str, error: str | None = None, outputs: list[str] | None = None) -> None:
    """Drive the durable run to a terminal state and optionally drop outputs."""

    async with env.factory() as session:
        run = await session.get(WorkflowV2RunRow, run_id)
        assert run is not None
        run.status = status
        run.error = error
        await session.commit()
    if outputs:
        outputs_dir = env.paths.sandbox_outputs_dir(run_id, user_id="owner-1")
        outputs_dir.mkdir(parents=True, exist_ok=True)
        for name in outputs:
            (outputs_dir / name).write_text(f"# {name}\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Acceptance 1 — 发起创建 Run（双侧证据 → queued，物化 + 钉扎 + entry）。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_with_full_evidence_creates_a_queued_run_bound_to_materialized_files(env) -> None:
    upload = _seed_upload(env, "log.txt")
    _seed_package(env)

    result = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        problem_description=PROBLEM,
        upload_paths=[upload],
        code_package_id="pkg-1",
        tool_call_id="tc-1",
    )
    payload = _payload(result)
    assert payload.get("status") == "queued", payload

    assert payload["detail_url"] == f"/workspace/workflows/wf-contract/runs/{payload['run_id']}"
    runs = await _run_rows(env.factory)
    assert len(runs) == 1 and runs[0].run_id == payload["run_id"]
    run = runs[0]
    assert run.status == "queued"
    assert run.snapshot["entry"] == "expert"
    assert run.snapshot["contract_version"] == CONTRACT_VERSION
    assert run.snapshot["evidence_intake"]["status"] == "execute"
    # Materialized Run workspace: uploads and the code package live under the
    # run's own thread bucket, and the inputs bind the materialized paths.
    uploads_dir = env.paths.sandbox_uploads_dir(run.run_id, user_id="owner-1")
    assert (uploads_dir / "log.txt").read_text(encoding="utf-8") == "evidence"
    assert run.inputs["upload_dir"] == "/mnt/user-data/uploads"
    package_source = run.inputs["code_package_source"]
    assert package_source.startswith("/mnt/user-data/code-evidence/")
    package_id = package_source.split("/")[4]
    assert (_thread_package_dir(env, run.run_id, package_id) / "source" / "main.c").is_file()
    tasks = await _task_rows(env.factory)
    assert len(tasks) == 1 and tasks[0].status == "queued"


# ---------------------------------------------------------------------------
# Acceptance 2 — 双缺转引导卡片（描述缺失被参数校验拦截，不创建 Run）。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_without_description_answers_with_a_guidance_card_and_creates_no_run(env) -> None:
    result = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        problem_description="   ",
        tool_call_id="tc-2",
    )

    payload = _payload(result)
    assert payload["created"] is False
    assert "ask_clarification" in payload["next_action"]
    assert await _run_rows(env.factory) == []
    assert await _task_rows(env.factory) == []


# ---------------------------------------------------------------------------
# Acceptance 3 — 单缺 → 确认后恢复。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_missing_side_pauses_then_confirm_resumes_the_run(env) -> None:
    started = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        problem_description=PROBLEM,
        tool_call_id="tc-3",
    )
    payload = _payload(started)
    assert payload["status"] == "paused"
    assert payload["missing_evidence_sides"] == ["code_evidence_package"]
    assert payload["input_snapshot_hash"]
    run = (await _run_rows(env.factory))[0]
    assert run.status == "paused"
    assert run.snapshot["interrupt"][0]["type"] == INTERRUPT_TYPE
    assert (await _task_rows(env.factory))[0].status == "paused"

    confirmed = await zeroing_run_tool.confirm_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        run_id=payload["run_id"],
        input_snapshot_hash=payload["input_snapshot_hash"],
        tool_call_id="tc-3b",
    )
    confirmation = _payload(confirmed)
    assert confirmation["status"] == "queued"
    async with env.factory() as session:
        resumed = await session.get(WorkflowV2RunRow, payload["run_id"])
    assert resumed is not None and resumed.status == "queued"
    assert resumed.snapshot["evidence_intake"]["confirmed"] is True
    assert (await _task_rows(env.factory))[0].status == "queued"
    events = await zeroing_run_tool.WorkflowV2Store(env.factory).list_events(payload["run_id"])
    resumed_events = [event for event in events if event.event_type == "resumed"]
    assert len(resumed_events) == 1 and resumed_events[0].payload["confirmed_by"] == "owner-1"


# ---------------------------------------------------------------------------
# Acceptance: 物化后新增材料改变快照哈希 → 要求重新确认，不静默继续。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirmation_after_material_change_is_rejected_as_stale(env) -> None:
    started = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        problem_description=PROBLEM,
        tool_call_id="tc-4",
    )
    payload = _payload(started)
    run_id = payload["run_id"]

    # New material is declared into the parked run after the pause (a new
    # declared input changes the snapshot hash — build_input_snapshot contract).
    async with env.factory() as session:
        run = await session.get(WorkflowV2RunRow, run_id)
        assert run is not None
        run.inputs = {**run.inputs, "code_package_source": "/mnt/user-data/code-evidence/pkg-new/source"}
        await session.commit()

    rejected = await zeroing_run_tool.confirm_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        run_id=run_id,
        input_snapshot_hash=payload["input_snapshot_hash"],
        tool_call_id="tc-4b",
    )
    body = _payload(rejected)
    assert body["reconfirm_required"] is True
    assert body["reason_code"] == "intake_snapshot_changed"
    async with env.factory() as session:
        still = await session.get(WorkflowV2RunRow, run_id)
    assert still is not None and still.status == "paused"
    events = await zeroing_run_tool.WorkflowV2Store(env.factory).list_events(run_id)
    assert any(event.event_type == "kernel_confirmation_rejected" for event in events)


# ---------------------------------------------------------------------------
# Acceptance 4 — 完成产物回桥；Acceptance 5 — 违规回桥违规摘要 + 产物链接。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_completed_run_bridges_five_artifacts_into_the_thread(env) -> None:
    started = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        problem_description=PROBLEM,
        tool_call_id="tc-5",
    )
    run_id = _payload(started)["run_id"]
    await _finish_run(env, run_id, status="completed", outputs=list(REQUIRED_OUTPUTS))

    result = await zeroing_run_tool.check_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        run_id=run_id,
        tool_call_id="tc-5b",
    )

    assert result.update["artifacts"] == [f"/mnt/user-data/outputs/{name}" for name in REQUIRED_OUTPUTS]
    payload = _payload(result)
    assert payload["status"] == "completed"
    assert payload["presented"] == [f"/mnt/user-data/outputs/{name}" for name in REQUIRED_OUTPUTS]
    thread_outputs = env.paths.sandbox_outputs_dir("thread-1", user_id="owner-1")
    for name in REQUIRED_OUTPUTS:
        assert (thread_outputs / name).is_file()


@pytest.mark.asyncio
async def test_failed_run_bridges_violation_summary_and_artifact_links(env) -> None:
    started = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        problem_description=PROBLEM,
        tool_call_id="tc-6",
    )
    run_id = _payload(started)["run_id"]
    await _finish_run(
        env,
        run_id,
        status="failed",
        error="contract_failed: missing artifact fault_tree.svg; report missing residual risks",
        outputs=["zeroing_report.md"],
    )

    result = await zeroing_run_tool.check_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        run_id=run_id,
        tool_call_id="tc-6b",
    )

    payload = _payload(result)
    assert payload["status"] == "failed"
    assert "contract_failed" in payload["error_summary"]
    # 产物保留可查：已有产物照常回桥。
    assert payload["presented"] == ["/mnt/user-data/outputs/zeroing_report.md"]
    assert result.update["artifacts"] == ["/mnt/user-data/outputs/zeroing_report.md"]


# ---------------------------------------------------------------------------
# Acceptance — 发起工具仅对归零 Expert 闭包可用；无权限用户被拒。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_outside_the_zeroing_closure_is_rejected(env) -> None:
    result = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=_runtime(agent_name="data-analyst"),
        problem_description=PROBLEM,
        tool_call_id="tc-7",
    )

    payload = _payload(result)
    assert payload["created"] is False
    assert payload["reason_code"] == "zeroing_closure_required"
    assert await _run_rows(env.factory) == []


@pytest.mark.asyncio
async def test_skill_context_activation_also_belongs_to_the_closure(env) -> None:
    runtime = _runtime(agent_name="lead_agent")
    runtime.context["skill_names"] = ["fault-zeroing"]
    started = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=runtime,
        problem_description=PROBLEM,
        tool_call_id="tc-8",
    )

    payload = _payload(started)
    assert payload["status"] == "paused"
    runs = await _run_rows(env.factory)
    assert runs[0].snapshot["entry"] == "skill"


@pytest.mark.asyncio
async def test_user_without_workflow_visibility_is_rejected_without_a_run(env, monkeypatch) -> None:
    async with env.factory() as session:
        resource = await session.get(Resource, "wf-contract")
        assert resource is not None
        resource.visibility = "private"
        resource.owner_id = "someone-else"
        await session.commit()

    result = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        problem_description=PROBLEM,
        tool_call_id="tc-9",
    )

    payload = _payload(result)
    assert payload["created"] is False
    assert payload["reason_code"] == "workflow_not_usable"
    assert await _run_rows(env.factory) == []


@pytest.mark.asyncio
async def test_viewer_role_cannot_start_a_run(env) -> None:
    result = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=_runtime(role="viewer"),
        problem_description=PROBLEM,
        tool_call_id="tc-10",
    )

    payload = _payload(result)
    assert payload["created"] is False
    assert payload["reason_code"] == "workflow_not_usable"
    assert await _run_rows(env.factory) == []


# ---------------------------------------------------------------------------
# Tool-boundary guards: 未知 Run / 越权访问 / 未知包 / 上传路径越界。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_and_check_reject_unknown_or_foreign_runs(env) -> None:
    foreign = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        problem_description=PROBLEM,
        tool_call_id="tc-11",
    )
    run_id = _payload(foreign)["run_id"]

    unknown = await zeroing_run_tool.check_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        run_id="missing-run",
        tool_call_id="tc-11b",
    )
    assert _payload(unknown)["reason_code"] == "run_not_found"

    squatter = await zeroing_run_tool.confirm_zeroing_run_tool.coroutine(
        runtime=_runtime(user_id="other-user"),
        run_id=run_id,
        input_snapshot_hash="any",
        tool_call_id="tc-11c",
    )
    assert _payload(squatter)["reason_code"] == "run_not_accessible"


@pytest.mark.asyncio
async def test_unknown_code_package_is_reported_and_no_run_is_created(env) -> None:
    result = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        problem_description=PROBLEM,
        code_package_id="ghost",
        tool_call_id="tc-12",
    )

    payload = _payload(result)
    assert payload["created"] is False
    assert payload["reason_code"] == "code_package_not_found"
    # 物化失败 = 到达 intake 前的双缺：转引导卡片，不创建 Run。
    assert "ask_clarification" in payload["next_action"]
    assert await _run_rows(env.factory) == []


@pytest.mark.asyncio
async def test_upload_path_outside_the_thread_uploads_is_rejected(env) -> None:
    result = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=_runtime(),
        problem_description=PROBLEM,
        upload_paths=["/mnt/user-data/outputs/zeroing_report.md"],
        tool_call_id="tc-13",
    )

    payload = _payload(result)
    assert payload["created"] is False
    assert payload["reason_code"] == "upload_path_rejected"
    # 同为物化失败双缺分支：引导卡片而非失败 Run。
    assert "ask_clarification" in payload["next_action"]
    assert await _run_rows(env.factory) == []


# ---------------------------------------------------------------------------
# 线程级集成：发起 → 暂停 → 确认 → 完成 → 产物回桥全链路。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thread_level_full_loop_from_start_to_artifact_bridge(env) -> None:
    runtime = _runtime()
    started = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=runtime,
        problem_description=PROBLEM,
        tool_call_id="tc-14",
    )
    paused = _payload(started)
    assert paused["status"] == "paused"

    confirmed = await zeroing_run_tool.confirm_zeroing_run_tool.coroutine(
        runtime=runtime,
        run_id=paused["run_id"],
        input_snapshot_hash=paused["input_snapshot_hash"],
        tool_call_id="tc-14b",
    )
    assert _payload(confirmed)["status"] == "queued"

    # Still running: the model reports the detail link, no artifacts yet.
    running = await zeroing_run_tool.check_zeroing_run_tool.coroutine(
        runtime=runtime,
        run_id=paused["run_id"],
        tool_call_id="tc-14c",
    )
    body = _payload(running)
    assert body["status"] == "queued"
    assert "artifacts" not in body
    assert body["detail_url"] == f"/workspace/workflows/wf-contract/runs/{paused['run_id']}"

    await _finish_run(env, paused["run_id"], status="completed", outputs=list(REQUIRED_OUTPUTS))
    finished = await zeroing_run_tool.check_zeroing_run_tool.coroutine(
        runtime=runtime,
        run_id=paused["run_id"],
        tool_call_id="tc-14d",
    )
    assert finished.update["artifacts"] == [f"/mnt/user-data/outputs/{name}" for name in REQUIRED_OUTPUTS]
    assert _payload(finished)["status"] == "completed"


# ---------------------------------------------------------------------------
# 注册接线：fault-zeroing 工具组 + 归零 Expert / Skill 声明联动。
# ---------------------------------------------------------------------------


def test_zeroing_tools_resolve_and_filter_through_their_group() -> None:
    from langchain.tools import BaseTool

    from deerflow.config.app_config import AppConfig
    from deerflow.config.sandbox_config import SandboxConfig
    from deerflow.config.tool_config import ToolConfig, ToolGroupConfig
    from deerflow.reflection import resolve_variable
    from deerflow.tools import get_available_tools

    module = "app.agentplatform.tools.zeroing_run_tool"
    entries = [
        ToolConfig(name="start_zeroing_run", group="fault-zeroing", use=f"{module}:start_zeroing_run_tool"),
        ToolConfig(name="confirm_zeroing_run", group="fault-zeroing", use=f"{module}:confirm_zeroing_run_tool"),
        ToolConfig(name="check_zeroing_run", group="fault-zeroing", use=f"{module}:check_zeroing_run_tool"),
        ToolConfig(name="read_file", group="file:read", use="deerflow.sandbox.tools:read_file_tool"),
    ]
    for entry in entries:
        resolved = resolve_variable(entry.use, BaseTool)
        assert getattr(resolved, "name") == entry.name

    app_config = AppConfig(
        sandbox=SandboxConfig(use="deerflow.sandbox.providers.local_sandbox:LocalSandboxProvider"),
        tools=entries,
        tool_groups=[ToolGroupConfig(name="fault-zeroing"), ToolGroupConfig(name="file:read")],
    )
    zeroing = get_available_tools(groups=["fault-zeroing"], include_mcp=False, app_config=app_config)
    assert {"start_zeroing_run", "confirm_zeroing_run", "check_zeroing_run"} <= {tool.name for tool in zeroing}
    assert "read_file" not in {tool.name for tool in zeroing}

    other = get_available_tools(groups=["file:read"], include_mcp=False, app_config=app_config)
    assert "start_zeroing_run" not in {tool.name for tool in other}


def test_bundled_agent_and_example_config_declare_the_fault_zeroing_group() -> None:
    import yaml

    repo_root = Path(__file__).resolve().parents[4]
    agent_config = yaml.safe_load((repo_root / "resources" / "agents" / "fault-zeroing" / "config.yaml").read_text(encoding="utf-8"))
    assert "fault-zeroing" in (agent_config.get("tool_groups") or [])

    example = yaml.safe_load((repo_root / "config.example.yaml").read_text(encoding="utf-8"))
    group_names = {group["name"] for group in example.get("tool_groups") or []}
    assert "fault-zeroing" in group_names
    wired = {tool["name"]: tool for tool in example.get("tools") or []}
    for name in ("start_zeroing_run", "confirm_zeroing_run", "check_zeroing_run"):
        assert wired[name]["group"] == "fault-zeroing"
        assert wired[name]["use"].startswith("app.agentplatform.tools.zeroing_run_tool:")

    skill_text = (repo_root / "resources" / "skills" / "fault-zeroing" / "SKILL.md").read_text(encoding="utf-8")
    for name in ("start_zeroing_run", "confirm_zeroing_run", "check_zeroing_run"):
        assert f"  - {name}" in skill_text
