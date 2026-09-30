"""三入口一内核等价性验收（unified-kernel ticket 05）。

同一份证据（同一段问题描述文本 + 同一份物化的文档附件与 Code Evidence
Package）从三个入口分别发起真实归零 Run：

- ``workflow`` — 网关工作流启动路由的内核分支（ticket 03）；
- ``expert`` / ``skill`` — 聊天闭环 ``start_zeroing_run`` 工具协程直调
  （ticket 04），闭包上下文决定 entry 标签。

每个 Run 都由真实 worker ``run_once`` 执行图驱动到终态（agent 节点按 S2
先例打桩产出契约合法产物）。四项断言把「三入口一内核」承诺固化为测试：
收件决定（evidence_mode / missing / reason_code）、快照钉扎的契约版本、
内核契约判定事件、五件套产物集合。

复用 S1（内核 × 真实存储）+ S2（worker run_once 驱动真实图）接缝，不新增
接缝；只有 session-factory 与文件系统缝隙使用测试替身。
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
import yaml
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agentplatform import rbac_models as _rbac_models  # noqa: F401 - register auth tables
from app.agentplatform import resource_models as _resource_models  # noqa: F401 - register resource tables
from app.agentplatform.fault_zeroing.contract import CONTRACT_VERSION, REQUIRED_OUTPUTS
from app.agentplatform.resources.canonical_sandbox import canonical_run_key, canonical_sandbox_scope
from app.agentplatform.resources.runtime import _json_hash
from app.agentplatform.tools import zeroing_run_tool
from app.agentplatform.workflows.v2.adapters import ActionAdapterRegistry
from app.agentplatform.workflows.v2.file_roots import make_host_resolver
from app.agentplatform.workflows.v2.store import WorkflowV2Store
from app.agentplatform.workflows.v2.worker import WorkflowWorker
from app.gateway.routers import resources
from app.gateway.routers.resources import WorkflowRunRequest
from app.workflow_worker import execute_workflow_task
from deerflow.config.database_config import DatabaseConfig
from deerflow.config.paths import Paths
from deerflow.persistence.base import Base as DeerFlowBase
from deerflow.persistence.models.workflow_v2 import WorkflowV2RunRow

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_PATH = REPO_ROOT / "resources" / "workflows" / "fault-zeroing.yaml"

# 同一证据：三个入口使用完全相同的问题描述文本与同一线程物化证据。
PROBLEM = "主轴电机过热报警"
THREAD_ID = "thread-equivalence"
OWNER = "owner-1"
UPLOAD_NAME = "acceptance-evidence.log"
PACKAGE_ID = "pkg-1"

EXPECTED_INTAKE = {
    "status": "execute",
    "evidence_mode": "hybrid",
    "missing": [],
    "reason_code": "intake_evidence_complete",
}


def _user(user_id: str):
    from app.agentplatform.rbac_models import UserModel, UserRole

    return UserModel(id=user_id, username=f"{user_id}@test.com", role=UserRole.USER, department_id=None, disabled=False)


def _runtime(context_extra: dict) -> SimpleNamespace:
    context = {"thread_id": THREAD_ID, "user_id": OWNER, "user_role": "user", **context_extra}
    return SimpleNamespace(state=None, context=context, config={"configurable": {"thread_id": THREAD_ID}})


@pytest_asyncio.fixture
async def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    base = tmp_path / "base"
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'equivalence.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(DeerFlowBase.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    # Chat-loop tool seams (S4 convention): the store session factory and the
    # filesystem base, so the tool materializes into the same tree the worker
    # resolves.  The gateway workflow entry shares the same store via its
    # ``_factory`` seam (S3 convention).
    monkeypatch.setattr(resources, "_factory", lambda: factory)
    monkeypatch.setattr(zeroing_run_tool, "_session_factory", lambda: factory)
    monkeypatch.setattr(zeroing_run_tool, "get_paths", lambda: Paths(base))
    monkeypatch.setattr("app.agentplatform.code_evidence.get_paths", lambda: Paths(base))
    monkeypatch.setenv("IDEER_HOST_BASE_DIR", str(base))
    # The tool's concurrency seam: unlimited, matching the S4 convention (the
    # equivalence test drives each run to its terminal state before the next
    # start anyway).
    monkeypatch.setattr(
        zeroing_run_tool,
        "_workflow_runtime",
        lambda: SimpleNamespace(user_concurrency=None, department_concurrency=None),
    )

    # One seeded workflow resource carrying the real bundled definition
    # (contract-declared): the workflow entry starts it by resource id, the
    # chat entries resolve it by slug.
    definition = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    async with factory() as session:
        from app.agentplatform.resource_models import Resource, ResourceVersion

        session.add(
            Resource(
                id="wf-equivalence",
                type="workflow",
                slug="fault-zeroing",
                display_name="fault-zeroing",
                owner_id=OWNER,
                visibility="public",
                scope_department_id=None,
                lifecycle_status="active",
                latest_version=1,
                draft_revision=0,
                storage_kind="database",
                storage_key="workflows/wf-equivalence",
                system_owned=False,
                authz_revision=1,
            )
        )
        session.add(
            ResourceVersion(
                id="wv-wf-equivalence",
                resource_id="wf-equivalence",
                version=1,
                content_hash=_json_hash(definition),
                storage_key="workflows/wf-equivalence/versions/1",
                scan_result={},
                content=definition,
                created_by=OWNER,
            )
        )
        await session.commit()

    # 同一份物化证据（seed 一次，三个入口共享其声明）：
    # 文档侧 = 上传目录中的证据文件；代码侧 = 线程 Code Evidence Package。
    uploads = Paths(base).sandbox_uploads_dir(THREAD_ID, user_id=OWNER)
    uploads.mkdir(parents=True, exist_ok=True)
    (uploads / UPLOAD_NAME).write_text("HF-07 超限；邻近测点稳定\n", encoding="utf-8")
    package_source = Paths(base).thread_dir(THREAD_ID, user_id=OWNER) / "user-data" / "code-evidence" / PACKAGE_ID / "source"
    package_source.mkdir(parents=True, exist_ok=True)
    (package_source / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    (package_source.parent / "manifest.json").write_text(
        json.dumps(
            {
                "package_id": PACKAGE_ID,
                "original_filename": "source.zip",
                "accepted": ["main.c"],
                "excluded": [],
                "rejected": [],
                "compressed_size": 100,
                "expanded_size": 27,
                "source_virtual_path": f"/mnt/user-data/code-evidence/{PACKAGE_ID}/source",
            }
        ),
        encoding="utf-8",
    )

    yield SimpleNamespace(factory=factory, base=base, tmp=tmp_path, engine=engine, store=WorkflowV2Store(factory))
    await engine.dispose()


# ---------------------------------------------------------------------------
# Entry drivers: 每个入口一次真实发起。
# ---------------------------------------------------------------------------


async def _start_through_workflow_entry(env) -> dict:
    """网关启动路由的内核分支（ticket 03）：声明路径绑定同一份证据。"""

    response = await resources.create_workflow_run(
        "wf-equivalence",
        body=WorkflowRunRequest(
            inputs={
                "problem_description": PROBLEM,
                "upload_dir": "/mnt/user-data/uploads",
                "code_package_source": f"/mnt/user-data/code-evidence/{PACKAGE_ID}/source",
            }
        ),
        current_user=_user(OWNER),
    )
    assert response["status"] == "queued", response
    return response


async def _start_through_chat_entry(env, *, context_extra: dict, tool_call_id: str, code_package_id: str | None = PACKAGE_ID) -> dict:
    """聊天闭环发起工具协程直调（ticket 04）：物化同一线程证据后经内核发起。"""

    result = await zeroing_run_tool.start_zeroing_run_tool.coroutine(
        runtime=_runtime(context_extra),
        problem_description=PROBLEM,
        upload_paths=[f"/mnt/user-data/uploads/{UPLOAD_NAME}"],
        code_package_id=code_package_id,
        tool_call_id=tool_call_id,
    )
    payload = json.loads(result.update["messages"][0].content)
    assert payload.get("created") is True, payload
    assert payload.get("status") == ("paused" if code_package_id is None else "queued"), payload
    return payload


# ---------------------------------------------------------------------------
# Completion driver: worker run_once 执行真实图（agent 节点打桩，S2 先例）。
# ---------------------------------------------------------------------------


def _contract_fixtures():
    spec = importlib.util.spec_from_file_location(
        "fz_contract_fixtures_equivalence",
        REPO_ROOT / "backend" / "tests" / "unit" / "fault_zeroing" / "test_contract.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("fz_contract_fixtures_equivalence", module)
    spec.loader.exec_module(module)
    return module


class _StubAgent:
    """写齐契约合法产物的 agent 节点桩（test_fault_zeroing_worker_runtime 先例）。"""

    def __init__(self, calls: list[str], *, inputs_seen: list[dict] | None = None, disclose_missing_side: bool = False) -> None:
        self.calls = calls
        self.inputs_seen = inputs_seen
        self.disclose_missing_side = disclose_missing_side

    async def run(self, context, params):
        self.calls.append(context.node_id)
        if self.inputs_seen is not None:
            self.inputs_seen.append(dict(context.inputs))
        if context.file_access:
            fixtures = _contract_fixtures()
            resolver = make_host_resolver(
                context.run_id,
                OWNER,
                sandbox_scope=canonical_sandbox_scope(context.run_id, context.run_id),
            )
            for root in context.file_access.get("write", []):
                host = resolver(root)
                assert host is not None, f"unresolvable write root {root}"
                path = Path(host)
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.name == "fault_tree.json":
                    path.write_text(json.dumps(fixtures.valid_fault_tree(), ensure_ascii=False), encoding="utf-8")
                elif path.name == "fault_tree_structure.json":
                    path.write_text(
                        '{"top_event": "top", "intermediate_events": [], "bottom_events": [], "logic": [], "evidence": [], "root_causes": [], "verification_plan": []}',
                        encoding="utf-8",
                    )
                elif path.name == "corrective_actions.json":
                    path.write_text(
                        '{"corrective_actions": [{"id": "CA-01", "name": "fix", "description": "desc", "target_root_cause_id": "RC-01", "completion_criteria": "done"}]}',
                        encoding="utf-8",
                    )
                elif path.name == "scan_summary.json":
                    # Scanner Status disclosure gate (ticket 04): the
                    # evidence_collection node's outputs-side scan record.
                    summary = '{"package_id": "pkg-equivalence", "overall": "completed", "scanners": [{"name": "cppcheck", "available": true, "version": "2.17.1", "exit_code": 0, "timed_out": false, "skipped_reason": null}]}'
                    path.write_text(summary, encoding="utf-8")
                elif path.name == "zeroing_report.md":
                    report = fixtures.valid_report()
                    if self.disclose_missing_side:
                        # 单缺侧 Run 的完成契约：覆盖矩阵与遗留风险都要披露缺侧。
                        report = report.replace(
                            "| 历史或复核记录 | 已覆盖 | 05_review_record.md | 无 |",
                            "| 历史或复核记录 | 已覆盖 | 05_review_record.md | 无 |\n| 代码证据包未提供 | — | — | — |",
                        )
                        report = report.replace("暂无缺失资料风险；BE-02 仍待验证。", "代码证据包未提供；BE-02 仍待验证。")
                    path.write_text(report, encoding="utf-8")
                elif path.name == "fault_tree.svg":
                    path.write_text("<svg><rect/><text>fault tree</text></svg>", encoding="utf-8")
                elif path.name == "analysis_process.svg":
                    path.write_text(
                        "<svg><text>证据提取 故障树构建 底事件评估 根因归因 纠正措施 文档生产</text></svg>",
                        encoding="utf-8",
                    )
                elif path.name == "bottom_event_assessment.md":
                    path.write_text(
                        "| 底事件 | 证据 | 概率判断 | 置信度 | 验证状态 |\n| --- | --- | --- | --- | --- |\n| BE-01 | EV-01 | high | high | confirmed |\n",
                        encoding="utf-8",
                    )
                else:
                    path.write_text("{}", encoding="utf-8")
        return {"node_id": context.node_id}


def _freeze_skill_view(env, run_id: str) -> None:
    """The run-scoped frozen skill view the canonical file roots resolve."""

    frozen_skill = env.base / "resources" / "run-skill-views" / canonical_run_key(run_id) / "fault-zeroing"
    shutil.copytree(REPO_ROOT / "resources" / "skills" / "fault-zeroing", frozen_skill)


def _make_config(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        checkpointer=SimpleNamespace(type="sqlite", connection_string=str(tmp_path / "checkpoints.db")),
        database=DatabaseConfig(backend="memory"),
        workflow_runtime=SimpleNamespace(
            max_events_per_run=1000,
            node_timeout_seconds=30,
            max_parallel_actions=3,
        ),
    )


async def _drive_queue_to_emptiness(env, monkeypatch: pytest.MonkeyPatch, agent: _StubAgent) -> None:
    """Drive the real worker until no claimable task is left.

    All three runs are already started (and their frozen skill views in
    place), so one drain executes every queued graph exactly once.
    """

    monkeypatch.setattr("app.agentplatform.workflows.v2.file_roots.get_paths", lambda: Paths(str(env.base)))
    monkeypatch.setattr(
        "app.agentplatform.workflows.v2.file_roots._get_skills_host_path",
        lambda: str(REPO_ROOT / "resources" / "skills"),
    )
    registry = ActionAdapterRegistry({("agent", "fault-zeroing"): agent})
    config = _make_config(env.tmp)
    monkeypatch.setattr("app.workflow_worker.build_canonical_registry", AsyncMock(return_value=registry))

    async def execute(task) -> None:
        await execute_workflow_task(task, store=env.store, config=config)

    worker = WorkflowWorker(env.store, execute, worker_id="worker-equivalence")
    while await worker.run_once():
        pass


# ---------------------------------------------------------------------------
# The equivalence acceptance: 四项断言 × 三入口。
# ---------------------------------------------------------------------------


def _intake_fields(run: WorkflowV2RunRow) -> dict:
    record = run.snapshot["evidence_intake"]
    return {
        "status": record["status"],
        "evidence_mode": record["evidence_mode"],
        "missing": list(record["missing"]),
        "reason_code": record["reason_code"],
    }


def _outputs_host(run: WorkflowV2RunRow) -> Path:
    resolver = make_host_resolver(
        run.run_id,
        str(run.created_by),
        sandbox_scope=canonical_sandbox_scope(run.run_id, run.run_id),
    )
    host = resolver("/mnt/user-data/outputs")
    assert host is not None
    return Path(host)


@pytest.mark.asyncio
async def test_three_entries_produce_identical_kernel_semantics_for_the_same_evidence(env, monkeypatch) -> None:
    calls: list[str] = []
    agent = _StubAgent(calls)

    started = {
        "workflow": (await _start_through_workflow_entry(env))["run_id"],
        "expert": (await _start_through_chat_entry(env, context_extra={"agent_name": "fault-zeroing"}, tool_call_id="tc-expert"))["run_id"],
        "skill": (await _start_through_chat_entry(env, context_extra={"skill_names": ["fault-zeroing"]}, tool_call_id="tc-skill"))["run_id"],
    }
    for run_id in started.values():
        _freeze_skill_view(env, run_id)
    await _drive_queue_to_emptiness(env, monkeypatch, agent)

    runs = {entry: await env.store.get_run(run_id) for entry, run_id in started.items()}
    assert all(run is not None for run in runs.values())

    # 发起入口如实标注：审计可按入口统计（workflow / expert / skill）。
    assert runs["workflow"].snapshot["entry"] == "workflow"
    assert runs["expert"].snapshot["entry"] == "expert"
    assert runs["skill"].snapshot["entry"] == "skill"
    # 三条 Run 都真实执行了整张图。
    assert len(calls) == 27

    intake_by_entry: dict[str, dict] = {}
    version_by_entry: dict[str, str] = {}
    judgment_by_entry: dict[str, dict] = {}
    artifacts_by_entry: dict[str, set[str]] = {}
    document_side_by_entry: dict[str, str] = {}

    for entry, run in runs.items():
        assert run.status == "completed", f"entry {entry} must complete"

        # 断言 1 — 收件决定（evidence_mode / missing / reason_code / status）。
        intake_by_entry[entry] = _intake_fields(run)
        # 断言 2 — 快照钉扎的契约版本。
        version_by_entry[entry] = run.snapshot["contract_version"]
        # 断言 3 — 契约判定终态与内核契约事件。
        events = await env.store.list_events(run.run_id)
        evaluated = [event for event in events if event.event_type == "kernel_contract_evaluated"]
        assert len(evaluated) == 1, f"entry {entry} must leave one kernel contract event"
        judgment_by_entry[entry] = {
            "code": evaluated[0].payload["code"],
            "contract_version": evaluated[0].payload["contract_version"],
            "terminal": events[-1].event_type,
        }
        # 断言 4 — 产物集合（五件套文件名集合）。
        artifacts_by_entry[entry] = {path.name for path in _outputs_host(run).iterdir() if path.is_file()}
        # 「同一份证据」的文档侧快照逐字一致（同一描述文本 + 同一上传目录）。
        document_side_by_entry[entry] = run.snapshot["evidence_intake"]["input_snapshot"]["document_evidence"]

    expected_judgment = {"code": "contract_passed", "contract_version": CONTRACT_VERSION, "terminal": "run_completed"}
    for entry in runs:
        assert intake_by_entry[entry] == EXPECTED_INTAKE, f"entry {entry} intake decision"
        assert version_by_entry[entry] == CONTRACT_VERSION, f"entry {entry} pinned contract version"
        assert judgment_by_entry[entry] == expected_judgment, f"entry {entry} contract judgment"
        assert artifacts_by_entry[entry] == set(REQUIRED_OUTPUTS), f"entry {entry} artifact set"
        failed_events = await env.store.list_events(started[entry])
        assert not any(event.event_type == "kernel_contract_failed" for event in failed_events)

    # 跨入口收口：四项语义在三个入口之间完全一致——「三入口一内核」。
    assert len({json.dumps(value, sort_keys=True) for value in intake_by_entry.values()}) == 1
    assert len(set(version_by_entry.values())) == 1
    assert len({json.dumps(value, sort_keys=True) for value in judgment_by_entry.values()}) == 1
    assert len({json.dumps(sorted(value)) for value in artifacts_by_entry.values()}) == 1
    # 同一份证据的文档侧快照逐字一致；代码侧按 Run 自包含物化（包 id 逐 Run 派生）。
    assert len(set(document_side_by_entry.values())) == 1


@pytest.mark.asyncio
async def test_chat_entry_single_missing_side_parks_the_same_kernel_pause(env) -> None:
    """等价性的收件面反向钉扎：单缺侧时聊天入口得到与工作流入口（S1/S3 已
    钉扎）相同的内核暂停语义——missing / reason_code / evidence_mode 一致，
    且 entry 标签如实区分入口。"""

    payload = await _start_through_chat_entry(
        env,
        context_extra={"agent_name": "fault-zeroing"},
        tool_call_id="tc-pause",
        code_package_id=None,
    )
    run = await env.store.get_run(payload["run_id"])
    assert run is not None and run.status == "paused"
    assert _intake_fields(run) == {
        "status": "pause",
        "evidence_mode": "hybrid",
        "missing": ["code_evidence_package"],
        "reason_code": "intake_confirmation_required",
    }
    assert run.snapshot["entry"] == "expert"
    assert run.snapshot["contract_version"] == CONTRACT_VERSION


# ---------------------------------------------------------------------------
# Paused 全链路：paused → confirm → worker resume → agent 节点拿到含默认值的
# inputs 且五件套写根可渲染（OCR 审查 F1 验收）。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_paused_then_confirmed_run_executes_with_declared_input_defaults(env, monkeypatch) -> None:
    """单缺侧 paused Run 确认恢复后，agent 节点看到的 inputs 必须带定义默认值。

    前端留空不发送、聊天工具只传证据字段：paused 落库若不填充默认值，
    恢复后 ``output_base_dir`` 缺失 → 五件套写根渲染不出 → 契约门判 failed。
    """

    from app.agentplatform.fault_zeroing.kernel import FaultZeroingKernel

    calls: list[str] = []
    inputs_seen: list[dict] = []
    agent = _StubAgent(calls, inputs_seen=inputs_seen, disclose_missing_side=True)

    started = await _start_through_chat_entry(
        env,
        context_extra={"agent_name": "fault-zeroing"},
        tool_call_id="tc-paused-chain",
        code_package_id=None,
    )
    run_id = started["run_id"]
    paused = await env.store.get_run(run_id)
    assert paused is not None and paused.status == "paused"
    # RED 断言 1：paused inputs 含定义声明的默认值。
    assert paused.inputs["output_base_dir"] == "/mnt/user-data/outputs"
    assert paused.inputs["evidence_mode"] == "hybrid"

    confirmed = await FaultZeroingKernel(env.store).confirm_evidence(
        run_id,
        payload={"input_snapshot_hash": started["input_snapshot_hash"]},
        confirmed_by=OWNER,
    )
    assert confirmed["missing_evidence_sides"] == ["code_evidence_package"]

    _freeze_skill_view(env, run_id)
    await _drive_queue_to_emptiness(env, monkeypatch, agent)

    resumed = await env.store.get_run(run_id)
    assert resumed is not None
    # RED 断言 2：真实 worker 执行整张图，agent 节点拿到的 inputs 带默认值，
    # 且五件套写根全部可渲染为宿主路径（桩内 assert host is not None）。
    assert resumed.inputs["output_base_dir"] == "/mnt/user-data/outputs"
    assert len(calls) == 9
    assert inputs_seen and all(item.get("output_base_dir") == "/mnt/user-data/outputs" for item in inputs_seen)
    outputs_host = _outputs_host(resumed)
    assert {path.name for path in outputs_host.iterdir() if path.is_file()} == set(REQUIRED_OUTPUTS)
