"""Lock the _AgentAdapter system_prompt override behavior.

The adapter must compose the agent SOUL with the workflow node's
``system_prompt`` override, and stay backward compatible when either
part is absent.
"""

from __future__ import annotations

import sys
from enum import Enum
from types import SimpleNamespace

import pytest

import ideer.config
import ideer.config.agents_config
import ideer.tools.tools
from ideer.runtime.user_context import get_effective_user_id
from ideer.workflows.v2.adapters import ActionContext, _AgentAdapter

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

    def __init__(self, subagent, tools, app_config=None, thread_id=None) -> None:
        FakeExecutor.captured.append(subagent)
        FakeExecutor.thread_ids.append(thread_id)

    async def _aexecute(self, prompt: str) -> SimpleNamespace:
        FakeExecutor.effective_user_ids.append(get_effective_user_id())
        return SimpleNamespace(status=_Status.COMPLETED, result={"ok": True}, error=None)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    FakeExecutor.captured = []
    FakeExecutor.thread_ids = []
    FakeExecutor.effective_user_ids = []
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
    the provider is down. A workflow node must treat that as a node failure
    (so the run can be retried) instead of silently producing empty output."""

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
    with pytest.raises(RuntimeError, match="LLM provider unavailable"):
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
