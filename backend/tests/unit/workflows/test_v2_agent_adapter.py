"""Lock the _AgentAdapter system_prompt override behavior.

The adapter must compose the agent SOUL with the workflow node's
``system_prompt`` override, and stay backward compatible when either
part is absent.
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import pytest

import ideer.config
import ideer.config.agents_config
import ideer.tools.tools
from ideer.config.agents_config import AgentConfig
from ideer.resources.runtime import CanonicalAgentDefinition
from ideer.runtime.user_context import get_effective_user_id
from ideer.workflows.v2.adapters import ActionContext, _AgentAdapter, _CanonicalAgentAdapter
from ideer.workflows.v2.compiler import WorkflowTransientError

# conftest.py pre-injects a MagicMock for ideer.subagents.executor to dodge a
# circular import, so we grab the mock module and re-patch the names the
# adapter's run() imports lazily.
executor_module = sys.modules["ideer.subagents.executor"]

SOUL = "# Fault Zeroing Agent SOUL\n\n通用证据规则……"
OVERRIDE = "你是证据分析师。只负责读取资料、抽取证据、标注来源，不做根因结论。"


class _Status(Enum):
    COMPLETED = "completed"
    FAILED = "failed"


def _agent_config() -> SimpleNamespace:
    return SimpleNamespace(tool_groups=["file:read", "file:write"], skills=["fault-zeroing"], model="inherit")


class FakeExecutor:
    captured: list = []
    thread_ids: list[str | None] = []
    effective_user_ids: list[str] = []
    canonical_run_ids: list[str | None] = []

    def __init__(self, subagent, tools, app_config=None, thread_id=None) -> None:
        FakeExecutor.captured.append(subagent)
        FakeExecutor.thread_ids.append(thread_id)

    async def _aexecute(self, prompt: str) -> SimpleNamespace:
        FakeExecutor.effective_user_ids.append(get_effective_user_id())
        FakeExecutor.canonical_run_ids.append(getattr(self, "canonical_run_id", None))
        return SimpleNamespace(status=_Status.COMPLETED, result={"ok": True}, error=None)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    FakeExecutor.captured = []
    FakeExecutor.thread_ids = []
    FakeExecutor.effective_user_ids = []
    FakeExecutor.canonical_run_ids = []
    monkeypatch.setattr(ideer.config, "get_app_config", lambda: SimpleNamespace())
    monkeypatch.setattr(ideer.config.agents_config, "load_agent_config", lambda name, user_id=None: _agent_config())
    monkeypatch.setattr(ideer.tools.tools, "get_available_tools", lambda groups=None, app_config=None: [])
    monkeypatch.setattr(executor_module, "SubagentExecutor", FakeExecutor)
    monkeypatch.setattr(executor_module, "SubagentStatus", _Status)
    return monkeypatch


@pytest.mark.parametrize(
    ("soul", "override", "expected"),
    [
        (SOUL, OVERRIDE, f"{SOUL}\n\n## 当前阶段指令\n\n{OVERRIDE}"),
        (SOUL, "", SOUL),
        (None, OVERRIDE, OVERRIDE),
    ],
    ids=["soul-plus-override", "soul-only", "override-only"],
)
@pytest.mark.asyncio
async def test_agent_adapter_system_prompt_composition(env: pytest.MonkeyPatch, soul: str | None, override: str, expected: str) -> None:
    if soul is None:
        soul_provider = lambda name, user_id=None: None  # noqa: E731
    else:
        soul_provider = lambda name, user_id=None: soul  # noqa: E731
    env.setattr(ideer.config.agents_config, "load_agent_soul", soul_provider)

    adapter = _AgentAdapter("fault-zeroing", "user-1")
    context = ActionContext(
        workflow_name="fault-zeroing",
        run_id="run-1",
        node_id="evidence_collection",
        inputs={},
        state={},
        outputs={},
    )
    params = {"prompt": "执行任务"}
    if override:
        params["system_prompt"] = override

    result = await adapter.run(context, params)

    assert result == {"ok": True}
    assert len(FakeExecutor.captured) == 1
    assert FakeExecutor.captured[0].system_prompt == expected
    assert FakeExecutor.captured[0].description == "Workflow node: evidence_collection"


@pytest.mark.asyncio
async def test_agent_adapter_propagates_file_access_without_debug_stdout(
    env: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    previous_user_id = get_effective_user_id()
    env.setattr(ideer.config.agents_config, "load_agent_soul", lambda name, user_id=None: SOUL)
    adapter = _AgentAdapter("fault-zeroing", "user-1")
    context = ActionContext(
        workflow_name="fault-zeroing",
        run_id="run-scoped",
        node_id="evidence_collection",
        inputs={},
        state={},
        outputs={},
        file_access={"read": ["/inputs/case"], "write": ["/outputs/evidence"]},
    )

    await adapter.run(context, {"prompt": "执行任务"})

    assert FakeExecutor.captured[0].file_access == context.file_access
    assert FakeExecutor.thread_ids == ["run-scoped"]
    assert FakeExecutor.effective_user_ids == ["user-1"]
    assert get_effective_user_id() == previous_user_id
    assert capsys.readouterr().out == ""


@pytest.mark.asyncio
async def test_agent_adapter_filters_tools_by_tool_groups(env: pytest.MonkeyPatch) -> None:
    """SubagentConfig.tools is a tool-name allowlist, not a group allowlist.

    Group names like ``file:read`` would filter away every tool. The adapter
    must resolve groups via ``get_available_tools(groups=...)`` and leave the
    allowlist unset so the executor inherits the filtered set.
    """

    class FakeTool:
        def __init__(self, name: str, group: str) -> None:
            self.name = name
            self.group = group

    tools = [
        FakeTool("read_file", "file:read"),
        FakeTool("write_file", "file:write"),
        FakeTool("grep", "file:read"),
        FakeTool("bash", "shell"),
    ]
    captured_kwargs: list = []

    class CapturingExecutor(FakeExecutor):
        def __init__(self, subagent, tools, app_config=None, thread_id=None) -> None:
            super().__init__(subagent, tools, app_config, thread_id)
            captured_kwargs.append({"tools": tools})

    env.setattr(executor_module, "SubagentExecutor", CapturingExecutor)
    env.setattr(ideer.tools.tools, "get_available_tools", lambda groups=None, app_config=None: [t for t in tools if t.group in (groups or [])])

    adapter = _AgentAdapter("fault-zeroing", "user-1")
    context = ActionContext(
        workflow_name="fault-zeroing",
        run_id="run-4",
        node_id="evidence_collection",
        inputs={},
        state={},
        outputs={},
    )
    result = await adapter.run(context, {"prompt": "执行任务", "system_prompt": "你是证据分析师"})

    assert result == {"ok": True}
    assert len(captured_kwargs) == 1
    passed_tools = captured_kwargs[0]["tools"]
    assert {t.name for t in passed_tools} == {"read_file", "write_file", "grep"}
    assert all(t.group in ("file:read", "file:write") for t in passed_tools)
    assert FakeExecutor.captured[0].tools is None


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

    env.setattr(executor_module, "SubagentExecutor", CapturingExecutor)
    env.setattr(
        ideer.tools.tools,
        "get_available_tools",
        lambda groups=None, app_config=None: [tool for tool in tools if tool.group in (groups or [])],
    )
    env.setattr(
        ideer.config.agents_config,
        "load_agent_config",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("legacy path used")),
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
    context = ActionContext(
        workflow_name="flow",
        run_id="run-canonical",
        node_id="node",
        inputs={},
        state={},
        outputs={},
    )

    result = await adapter.run(context, {"prompt": "work"})

    assert result == {"ok": True}
    assert [tool.name for tool in captured_tools] == ["read_file"]
    assert FakeExecutor.captured[0].name == "agent-uuid"
    assert FakeExecutor.effective_user_ids == ["runner"]
    assert FakeExecutor.canonical_run_ids == ["run-canonical"]


@pytest.mark.asyncio
async def test_agent_adapter_respects_max_turns_param(env: pytest.MonkeyPatch) -> None:
    """Long-running nodes (e.g. report generation) can raise max_turns to
    avoid hitting the langgraph recursion limit mid-flight."""

    adapter = _AgentAdapter("fault-zeroing", "user-1")
    context = ActionContext(
        workflow_name="fault-zeroing",
        run_id="run-5",
        node_id="generate_outputs",
        inputs={},
        state={},
        outputs={},
    )

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

    env.setattr(executor_module, "SubagentExecutor", UnavailableExecutor)

    adapter = _AgentAdapter("fault-zeroing", "user-1")
    context = ActionContext(
        workflow_name="fault-zeroing",
        run_id="run-6",
        node_id="evidence_collection",
        inputs={},
        state={},
        outputs={},
    )
    with pytest.raises(WorkflowTransientError, match="LLM provider unavailable"):
        await adapter.run(context, {"prompt": "执行任务"})


@pytest.mark.asyncio
async def test_agent_adapter_raises_when_agent_missing(env: pytest.MonkeyPatch) -> None:
    env.setattr(ideer.config.agents_config, "load_agent_config", lambda name, user_id=None: None)

    from ideer.workflows.v2.adapters import ActionResolutionError

    adapter = _AgentAdapter("missing-agent", "user-1")
    context = ActionContext(
        workflow_name="wf",
        run_id="run-2",
        node_id="n",
        inputs={},
        state={},
        outputs={},
    )
    with pytest.raises(ActionResolutionError, match="agent 'missing-agent' not found"):
        await adapter.run(context, {"prompt": "hello"})


@pytest.mark.asyncio
async def test_agent_adapter_shared_agent_loads_owner_config_but_runs_as_runner(
    env: pytest.MonkeyPatch,
) -> None:
    """A shared agent reads config/SOUL from the declaring owner's directory
    while the execution context (sandbox, user) stays with the runner."""
    calls: dict[str, str | None] = {}

    def record_config(name, user_id=None):
        calls["config_user_id"] = user_id
        return _agent_config()

    def record_soul(name, user_id=None):
        calls["soul_user_id"] = user_id
        return SOUL

    env.setattr(ideer.config.agents_config, "load_agent_config", record_config)
    env.setattr(ideer.config.agents_config, "load_agent_soul", record_soul)

    adapter = _AgentAdapter("fault-zeroing", "user-1", owner_id="owner-1")
    context = ActionContext(
        workflow_name="fault-zeroing",
        run_id="run-shared",
        node_id="evidence_collection",
        inputs={},
        state={},
        outputs={},
    )

    result = await adapter.run(context, {"prompt": "执行任务"})

    assert calls == {"config_user_id": "owner-1", "soul_user_id": "owner-1"}
    assert FakeExecutor.effective_user_ids == ["user-1"]
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_agent_adapter_raises_when_executor_fails(env: pytest.MonkeyPatch) -> None:
    class FailingExecutor(FakeExecutor):
        async def _aexecute(self, prompt: str) -> SimpleNamespace:
            return SimpleNamespace(status=_Status.FAILED, result=None, error=None)

    env.setattr(executor_module, "SubagentExecutor", FailingExecutor)

    adapter = _AgentAdapter("fault-zeroing", "user-1")
    context = ActionContext(
        workflow_name="wf",
        run_id="run-3",
        node_id="n",
        inputs={},
        state={},
        outputs={},
    )
    with pytest.raises(RuntimeError, match="agent 'fault-zeroing' failed with status"):
        await adapter.run(context, {"prompt": "hello"})


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
    env.setattr(executor_module, "SubagentExecutor", StreamingExecutor)

    adapter = _AgentAdapter("fault-zeroing", "user-1")
    context = ActionContext(
        workflow_name="fault-zeroing",
        run_id="run-progress",
        node_id="evidence_collection",
        inputs={},
        state={},
        outputs={},
    )

    updates = [update async for update in adapter.astream(context, {"prompt": "提取证据", "system_prompt": "你是证据分析师"})]

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

    env.setattr(executor_module, "SubagentExecutor", UnavailableStreamExecutor)

    adapter = _AgentAdapter("fault-zeroing", "user-1")
    context = ActionContext(
        workflow_name="fault-zeroing",
        run_id="run-progress-unavailable",
        node_id="evidence_collection",
        inputs={},
        state={},
        outputs={},
    )

    with pytest.raises(WorkflowTransientError, match="LLM provider unavailable"):
        async for _ in adapter.astream(context, {"prompt": "提取证据"}):
            pass
