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

    def __init__(self, subagent, tools, app_config=None) -> None:
        FakeExecutor.captured.append(subagent)

    async def _aexecute(self, prompt: str) -> SimpleNamespace:
        return SimpleNamespace(status=_Status.COMPLETED, result={"ok": True}, error=None)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    FakeExecutor.captured = []
    monkeypatch.setattr(ideer.config, "get_app_config", lambda: SimpleNamespace())
    monkeypatch.setattr(ideer.config.agents_config, "load_agent_config", lambda name, user_id=None: _agent_config())
    monkeypatch.setattr(ideer.tools.tools, "get_available_tools", lambda app_config=None: [])
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
