"""Lock the canonical workflow agent adapter behavior.

Since the unified-kernel cleanup (ADR-0004) there is exactly one workflow
agent adapter: ``_CanonicalAgentAdapter`` over the agent definition frozen
into the run's canonical closure.  These tests pin its shared machinery —
system-prompt composition, file-access propagation, tool-group intersection,
LLM-unavailable surfacing, model failover, delegation evidence and progress
streaming.  The former name-based catalog-loading adapter (its alias
resolution, config.yaml/SOUL loading and missing-agent paths) was removed
together with these cleanup tests.
"""

from __future__ import annotations

import asyncio
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import pytest
from agentplatform_extension.evidence import AuthorizationContext, RunEvidenceBinding, bind_run_evidence, current_run_evidence
from agentplatform_extension.knowledge.scope import KnowledgeScope

import deerflow.config
import deerflow.tools.tools
from app.agentplatform.resources.runtime import CanonicalAgentDefinition
from app.agentplatform.workflows.v2 import executor_bridge as executor_module
from app.agentplatform.workflows.v2.adapters import ActionContext, _CanonicalAgentAdapter, _compose_system_prompt
from app.agentplatform.workflows.v2.compiler import WorkflowTransientError
from deerflow.config.agents_config import AgentConfig
from deerflow.runtime.user_context import get_effective_user_id

SOUL = "# Fault Zeroing Agent SOUL\n\n通用证据规则……"
OVERRIDE = "你是证据分析师。只负责读取资料、抽取证据、标注来源，不做根因结论。"


class _Status(Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class FakeExecutor:
    captured: list = []
    thread_ids: list[str | None] = []
    effective_user_ids: list[str] = []
    canonical_run_ids: list[str | None] = []

    def __init__(self, subagent, tools, app_config=None, thread_id=None) -> None:
        FakeExecutor.captured.append(subagent)
        self.config = subagent
        FakeExecutor.thread_ids.append(thread_id)

    async def _aexecute(self, prompt: str) -> SimpleNamespace:
        FakeExecutor.effective_user_ids.append(get_effective_user_id())
        FakeExecutor.canonical_run_ids.append(getattr(self, "canonical_run_id", None))
        return SimpleNamespace(status=_Status.COMPLETED, result={"ok": True}, error=None)


def _definition(*, soul: str | None = SOUL, resource_id: str = "agent-uuid", model: str | None = None, tool_groups: list[str] | None = None) -> CanonicalAgentDefinition:
    return CanonicalAgentDefinition(
        resource_id=resource_id,
        version=1,
        content_hash="a" * 64,
        path=Path("/unused"),
        config=AgentConfig(name="writer", tool_groups=tool_groups or [], skills=[], model=model),
        soul=soul or "",
    )


def _adapter(*, soul: str | None = SOUL, resource_id: str = "agent-uuid", user_id: str = "user-1", tool_groups: list[str] | None = None) -> _CanonicalAgentAdapter:
    return _CanonicalAgentAdapter(_definition(soul=soul, resource_id=resource_id, tool_groups=tool_groups), [], user_id, allowed_tool_groups=None)


def _context(run_id: str, node_id: str = "evidence_collection", **extra) -> ActionContext:
    return ActionContext(
        workflow_name="fault-zeroing",
        run_id=run_id,
        node_id=node_id,
        inputs={},
        state={},
        outputs={},
        **extra,
    )


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    FakeExecutor.captured = []
    FakeExecutor.thread_ids = []
    FakeExecutor.effective_user_ids = []
    FakeExecutor.canonical_run_ids = []
    monkeypatch.setattr(deerflow.config, "get_app_config", lambda: SimpleNamespace())
    monkeypatch.setattr(deerflow.tools.tools, "get_available_tools", lambda groups=None, app_config=None: [])
    monkeypatch.setattr(executor_module, "WorkflowSubagentExecutor", FakeExecutor)
    monkeypatch.setattr(executor_module, "SubagentStatus", _Status)
    return monkeypatch


def _expected_prompt(soul: str | None, override: str, context: ActionContext) -> str:
    return _compose_system_prompt(soul or "", override, context)


@pytest.mark.parametrize(
    ("soul", "override"),
    [
        (SOUL, OVERRIDE),
        (SOUL, ""),
        ("", OVERRIDE),
    ],
    ids=["soul-plus-override", "soul-only", "override-only"],
)
@pytest.mark.asyncio
async def test_agent_adapter_system_prompt_composition(env: pytest.MonkeyPatch, soul: str | None, override: str) -> None:
    adapter = _adapter(soul=soul)
    context = _context("run-1")
    params = {"prompt": "执行任务"}
    if override:
        params["system_prompt"] = override

    result = await adapter.run(context, params)

    assert result == {"ok": True}
    assert len(FakeExecutor.captured) == 1
    assert FakeExecutor.captured[0].system_prompt == _expected_prompt(soul, override, context)
    assert FakeExecutor.captured[0].description == "Workflow node: evidence_collection"


@pytest.mark.asyncio
async def test_agent_adapter_system_prompt_carries_explicit_workflow_node_marker(env: pytest.MonkeyPatch) -> None:
    """The composed prompt names the workflow/node and defers persona-level
    deliverables to the node instructions, so the model can tell node runs
    apart from standalone chats without relying on YAML authors."""
    adapter = _adapter()
    context = _context("run-1")

    await adapter.run(context, {"prompt": "执行任务", "system_prompt": OVERRIDE})

    prompt = FakeExecutor.captured[0].system_prompt
    assert prompt.index(SOUL.strip()) < prompt.index("## 运行模式：工作流节点") < prompt.index("## 当前阶段指令")
    assert "工作流「fault-zeroing」的节点「evidence_collection」" in prompt
    assert "不要更换路径重试" in prompt
    assert prompt.endswith(f"## 当前阶段指令\n\n{OVERRIDE}")


@pytest.mark.asyncio
async def test_agent_adapter_propagates_file_access_without_debug_stdout(
    env: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    previous_user_id = get_effective_user_id()
    adapter = _adapter()
    context = _context(
        "run-scoped",
        file_access={"read": ["/inputs/case"], "write": ["/outputs/evidence"]},
    )

    await adapter.run(context, {"prompt": "执行任务"})

    assert FakeExecutor.captured[0].file_access == context.file_access
    assert FakeExecutor.thread_ids == ["run-scoped"]
    assert FakeExecutor.effective_user_ids == ["user-1"]
    assert get_effective_user_id() == previous_user_id
    assert capsys.readouterr().out == ""


@pytest.mark.asyncio
async def test_canonical_agent_adapter_intersects_runner_groups_and_never_loads_owner_paths(
    env: pytest.MonkeyPatch,
) -> None:
    class FakeTool:
        def __init__(self, name: str, group: str) -> None:
            self.name = name
            self.group = group

    tools = [FakeTool("read_file", "file:read"), FakeTool("write_file", "file:write")]
    captured_tools: list = []

    class CapturingExecutor(FakeExecutor):
        def __init__(self, subagent, tools, app_config=None, thread_id=None) -> None:
            super().__init__(subagent, tools, app_config, thread_id)
            captured_tools.extend(tools)

    env.setattr(executor_module, "WorkflowSubagentExecutor", CapturingExecutor)
    env.setattr(
        deerflow.tools.tools,
        "get_available_tools",
        lambda groups=None, app_config=None: [tool for tool in tools if tool.group in (groups or [])],
    )
    definition = CanonicalAgentDefinition(
        resource_id="agent-uuid",
        version=1,
        content_hash="a" * 64,
        path=Path("/unused"),
        config=AgentConfig(name="writer", tool_groups=["file:read", "file:write"], skills=[]),
        soul="Frozen soul",
    )
    adapter = _CanonicalAgentAdapter(
        definition,
        [],
        "runner",
        allowed_tool_groups=frozenset({"file:read"}),
    )
    context = _context("run-canonical", node_id="node")

    result = await adapter.run(context, {"prompt": "work"})

    assert result == {"ok": True}
    assert [tool.name for tool in captured_tools] == ["read_file"]
    assert FakeExecutor.captured[0].name == "agent-uuid"
    assert FakeExecutor.effective_user_ids == ["runner"]
    assert FakeExecutor.canonical_run_ids == ["run-canonical"]


@pytest.mark.asyncio
async def test_canonical_agent_adapter_narrows_workflow_scope_to_agent_dependencies(
    env: pytest.MonkeyPatch,
) -> None:
    definition = CanonicalAgentDefinition(
        resource_id="agent-uuid",
        version=1,
        content_hash="a" * 64,
        path=Path("/unused"),
        config=AgentConfig(name="writer", tool_groups=[], skills=[]),
        soul="Frozen soul",
        knowledge_resource_ids=frozenset({"kb-allowed"}),
    )
    adapter = _CanonicalAgentAdapter(definition, [], "runner", allowed_tool_groups=None)
    context = _context(
        "run-canonical-scope",
        node_id="node",
        knowledge_scope=KnowledgeScope.from_bindings({"kb-allowed": "dataset-a", "kb-hidden": "dataset-b"}),
    )

    await adapter.run(context, {"prompt": "work"})

    assert FakeExecutor.captured[0].knowledge_scope.as_mapping()["bindings"] == {"kb-allowed": "dataset-a"}


@pytest.mark.asyncio
async def test_agent_adapter_respects_max_turns_param(env: pytest.MonkeyPatch) -> None:
    """Long-running nodes (e.g. report generation) can raise max_turns to
    avoid hitting the langgraph recursion limit mid-flight."""
    adapter = _adapter()
    context = _context("run-5", node_id="generate_outputs")

    result = await adapter.run(context, {"prompt": "生成报告", "max_turns": 200})
    assert result == {"ok": True}
    assert FakeExecutor.captured[0].max_turns == 200

    FakeExecutor.captured = []
    await adapter.run(context, {"prompt": "生成报告"})
    assert FakeExecutor.captured[0].max_turns == 50


@pytest.mark.asyncio
async def test_agent_adapter_fails_when_llm_unavailable(env: pytest.MonkeyPatch) -> None:
    """The LLM error middleware returns a graceful user-facing message when
    the provider is down. A workflow node must surface that as a transient
    error (retried with backoff, then the run pauses for resume) instead of
    silently producing empty output."""

    class UnavailableExecutor(FakeExecutor):
        async def _aexecute(self, prompt: str) -> SimpleNamespace:
            return SimpleNamespace(
                status=_Status.COMPLETED,
                result="The configured LLM provider is temporarily unavailable after multiple retries. Please wait a moment and continue the conversation.",
                error=None,
            )

    env.setattr(executor_module, "WorkflowSubagentExecutor", UnavailableExecutor)

    adapter = _adapter()
    with pytest.raises(WorkflowTransientError, match="LLM provider unavailable"):
        await adapter.run(_context("run-6"), {"prompt": "执行任务"})


@pytest.mark.asyncio
async def test_agent_adapter_fails_over_to_next_configured_model(env: pytest.MonkeyPatch) -> None:
    class FailoverExecutor(FakeExecutor):
        async def _aexecute(self, prompt: str) -> SimpleNamespace:
            if self.config.model == "model-a":
                return SimpleNamespace(
                    status=_Status.COMPLETED,
                    result="The configured LLM provider is temporarily unavailable after multiple retries. Please wait a moment and continue the conversation.",
                    error=None,
                )
            return SimpleNamespace(status=_Status.COMPLETED, result={"model": self.config.model}, error=None)

    env.setattr(executor_module, "WorkflowSubagentExecutor", FailoverExecutor)
    env.setattr(
        deerflow.config,
        "get_app_config",
        lambda: SimpleNamespace(
            models=[SimpleNamespace(name="model-a"), SimpleNamespace(name="model-b")],
        ),
    )

    adapter = _adapter()
    context = _context("run-failover", model_name="model-a")

    result = await adapter.run(context, {"prompt": "执行任务"})

    assert result == {"model": "model-b"}
    assert [config.model for config in FakeExecutor.captured] == ["model-a", "model-b"]
    assert context.model_name == "model-b"


@pytest.mark.asyncio
async def test_agent_adapter_raises_when_executor_fails(env: pytest.MonkeyPatch) -> None:
    class FailingExecutor(FakeExecutor):
        async def _aexecute(self, prompt: str) -> SimpleNamespace:
            return SimpleNamespace(status=_Status.FAILED, result=None, error=None)

    env.setattr(executor_module, "WorkflowSubagentExecutor", FailingExecutor)

    adapter = _adapter()
    with pytest.raises(RuntimeError, match="agent 'agent-uuid' failed with status"):
        await adapter.run(_context("run-3", node_id="n"), {"prompt": "hello"})


@pytest.mark.asyncio
async def test_agent_adapter_does_not_retry_execution_when_evidence_import_fails(env: pytest.MonkeyPatch) -> None:
    calls = 0

    class ImportFailingExecutor(FakeExecutor):
        async def _aexecute(self, prompt: str) -> SimpleNamespace:
            nonlocal calls
            calls += 1
            raise ImportError("dependency raised during execution")

    env.setattr(executor_module, "WorkflowSubagentExecutor", ImportFailingExecutor)

    adapter = _adapter()
    with pytest.raises(ImportError, match="dependency raised during execution"):
        await adapter.run(_context("run-import-error", node_id="n"), {"prompt": "hello"})

    assert calls == 1


@pytest.mark.asyncio
async def test_agent_adapter_adopts_valid_subagent_retrieval_evidence(env: pytest.MonkeyPatch) -> None:
    class EvidenceExecutor(FakeExecutor):
        async def _aexecute(self, prompt: str) -> SimpleNamespace:
            return SimpleNamespace(
                status=_Status.COMPLETED,
                result={"ok": True},
                error=None,
                task_id="child-task-1",
                retrieval_receipts=[
                    {
                        "receipt_id": "child-receipt-1",
                        "run_id": "run-evidence",
                        "logical_knowledge_base": "docs",
                        "parent_tool_receipt_id": "wf:run-evidence:node:evidence_collection",
                    }
                ],
            )

    env.setattr(executor_module, "WorkflowSubagentExecutor", EvidenceExecutor)

    adapter = _adapter()
    context = _context("run-evidence")
    binding = RunEvidenceBinding(
        [],
        AuthorizationContext("caller", "agent", "policy"),
        run_id="run-evidence",
        knowledge_scope={"bindings": {"docs": "dataset-1"}},
    )

    with bind_run_evidence(binding):
        assert await adapter.run(context, {"prompt": "提取证据"}) == {"ok": True}
        receipt = current_run_evidence().retrieval_receipts[0]

    assert receipt["delegated"] is True
    assert receipt["child_task_id"] == "child-task-1"
    assert receipt["child_agent_id"] == "agent-uuid"


class StreamingExecutor(FakeExecutor):
    """Executor that takes the per-turn progress_callback and emits tool calls."""

    def __init__(self, subagent, tools, app_config=None, thread_id=None) -> None:
        super().__init__(subagent, tools, app_config, thread_id)
        self.progress_callback = None

    async def _aexecute(self, prompt: str, progress_callback=None) -> SimpleNamespace:
        self.progress_callback = progress_callback
        await progress_callback({"type": "tool_call", "tool": "read_file", "args_summary": "/mnt/user-data/uploads/case/a.txt", "turn": 1})
        await progress_callback({"type": "tool_call", "tool": "grep", "args_summary": "fault", "turn": 2})
        return SimpleNamespace(status=_Status.COMPLETED, result={"ok": True}, error=None)


@pytest.mark.asyncio
async def test_agent_adapter_streams_per_turn_tool_call_progress(env: pytest.MonkeyPatch) -> None:
    """Each tool call made by the subagent must surface as an action_progress
    message on the astream, bracketed by 'started' and the final result."""
    env.setattr(executor_module, "WorkflowSubagentExecutor", StreamingExecutor)

    adapter = _adapter()
    updates = [update async for update in adapter.astream(_context("run-progress"), {"prompt": "提取证据", "system_prompt": "你是证据分析师"})]

    assert updates[0] == {"type": "progress", "message": "started"}
    assert updates[1]["message"] == "[回合 1] 调用工具 read_file → /mnt/user-data/uploads/case/a.txt"
    assert updates[2]["message"] == "[回合 2] 调用工具 grep → fault"
    assert updates[3] == {"type": "result", "value": {"ok": True}}


@pytest.mark.asyncio
async def test_agent_adapter_stream_surfaces_transient_llm_failure(env: pytest.MonkeyPatch) -> None:
    """The astream must apply the same transient-error markers as run(): an
    LLM-unavailable result inside a stream raises WorkflowTransientError."""

    class UnavailableStreamExecutor(StreamingExecutor):
        async def _aexecute(self, prompt: str, progress_callback=None) -> SimpleNamespace:
            await progress_callback({"type": "tool_call", "tool": "read_file", "args_summary": "a.txt", "turn": 1})
            return SimpleNamespace(
                status=_Status.COMPLETED,
                result="The configured LLM provider is temporarily unavailable after multiple retries. Please wait a moment and continue the conversation.",
                error=None,
            )

    env.setattr(executor_module, "WorkflowSubagentExecutor", UnavailableStreamExecutor)

    adapter = _adapter()
    with pytest.raises(WorkflowTransientError, match="LLM provider unavailable"):
        async for _ in adapter.astream(_context("run-progress-unavailable"), {"prompt": "提取证据"}):
            pass


@pytest.mark.asyncio
async def test_agent_adapter_stream_propagates_executor_exception_without_hanging(env: pytest.MonkeyPatch) -> None:
    """An executor exception must reach the workflow instead of leaving the
    adapter waiting forever for a queue sentinel."""

    class FailingStreamExecutor(StreamingExecutor):
        async def _aexecute(self, prompt: str, progress_callback=None) -> SimpleNamespace:
            raise RuntimeError("provider stream failed")

    env.setattr(executor_module, "WorkflowSubagentExecutor", FailingStreamExecutor)

    adapter = _adapter()
    with pytest.raises(RuntimeError, match="provider stream failed"):
        async with asyncio.timeout(1):
            async for _ in adapter.astream(_context("run-progress-exception", node_id="deductive_tree"), {"prompt": "构建故障树"}):
                pass
