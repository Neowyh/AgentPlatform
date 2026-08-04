"""Small, permission-aware adapter registry used by workflow nodes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Protocol


class ActionAdapter(Protocol):
    async def run(self, context: ActionContext, params: dict[str, Any]) -> Any: ...

    def astream(self, context: ActionContext, params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]: ...


class ActionResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ActionContext:
    workflow_name: str
    run_id: str
    node_id: str
    inputs: dict[str, Any]
    state: dict[str, Any]
    outputs: dict[str, Any]
    file_access: dict[str, list[str]] | None = None

    @property
    def idempotency_key(self) -> str:
        return f"wf:{self.run_id}:node:{self.node_id}"


class ActionAdapterRegistry:
    def __init__(self, adapters: dict[tuple[str, str], ActionAdapter] | None = None) -> None:
        self._adapters = dict(adapters or {})

    def register(self, kind: str, name: str, adapter: ActionAdapter) -> None:
        self._adapters[(kind, name)] = adapter

    def resolve(self, kind: str, name: str) -> ActionAdapter:
        adapter = self._adapters.get((kind, name))
        if adapter is None:
            raise ActionResolutionError(f"unknown {kind} adapter '{name}'")
        return adapter


class _ToolAdapter:
    def __init__(self, tool: Any) -> None:
        self.tool = tool

    async def run(self, context: ActionContext, params: dict[str, Any]) -> Any:
        if hasattr(self.tool, "ainvoke"):
            return await self.tool.ainvoke(params)
        return await asyncio.to_thread(self.tool.invoke, params)

    async def astream(self, context: ActionContext, params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "progress", "message": "started"}
        result = await self.run(context, params)
        yield {"type": "result", "value": result}


class _AgentAdapter:
    # Graceful fallback texts produced by LLMErrorHandlingMiddleware when the
    # provider is down. In a workflow node they signal failure, not output.
    _LLM_UNAVAILABLE_MARKERS = (
        "temporarily unavailable after multiple retries",
        "circuit breaker is engaged",
        "account is out of quota",
        "authentication or access is invalid",
    )

    def __init__(self, name: str, user_id: str) -> None:
        self.name = name
        self.user_id = user_id

    async def run(self, context: ActionContext, params: dict[str, Any]) -> Any:
        from ideer.config import get_app_config
        from ideer.config.agents_config import load_agent_config, load_agent_soul
        from ideer.runtime.user_context import reset_current_user, set_current_user
        from ideer.subagents.config import SubagentConfig
        from ideer.subagents.executor import SubagentExecutor, SubagentStatus
        from ideer.tools.tools import get_available_tools
        from ideer.workflows.v2.compiler import WorkflowTransientError

        config = load_agent_config(self.name, user_id=self.user_id)
        if config is None:
            raise ActionResolutionError(f"agent '{self.name}' not found")

        soul = load_agent_soul(self.name, user_id=self.user_id) or ""
        override = params.get("system_prompt", "")
        if soul and override:
            system_prompt = f"{soul}\n\n## 当前阶段指令\n\n{override}"
        else:
            system_prompt = soul or override

        subagent = SubagentConfig(
            name=self.name,
            description=f"Workflow node: {context.node_id}",
            system_prompt=system_prompt,
            skills=config.skills,
            model=config.model or "inherit",
            max_turns=params.get("max_turns", 50),
            file_access=context.file_access,
        )
        executor = SubagentExecutor(
            subagent,
            get_available_tools(groups=config.tool_groups, app_config=get_app_config()),
            app_config=get_app_config(),
            thread_id=context.run_id,
        )
        prompt = params.get("prompt", params.get("input", params))
        user_token = set_current_user(SimpleNamespace(id=self.user_id))
        try:
            result = await executor._aexecute(str(prompt))
        finally:
            reset_current_user(user_token)
        if result.status == SubagentStatus.COMPLETED:
            if _is_llm_unavailable_text(result.result):
                raise WorkflowTransientError(f"agent '{self.name}' failed: LLM provider unavailable")
            return result.result
        if _is_llm_unavailable_text(result.error):
            raise WorkflowTransientError(result.error or f"agent '{self.name}' failed: LLM provider unavailable")
        raise RuntimeError(result.error or f"agent '{self.name}' failed with status {result.status}")

    async def astream(self, context: ActionContext, params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "progress", "message": "started"}
        yield {"type": "result", "value": await self.run(context, params)}


def _is_llm_unavailable_text(result: Any) -> bool:
    if not isinstance(result, str):
        return False
    lowered = result.lower()
    return any(marker in lowered for marker in _AgentAdapter._LLM_UNAVAILABLE_MARKERS)


def build_default_registry(app_config: Any, user_id: str) -> ActionAdapterRegistry:
    """Resolve configured tools and agents for one workflow run."""
    from ideer.config.agents_config import list_custom_agents
    from ideer.tools.tools import get_available_tools

    registry = ActionAdapterRegistry()
    for tool in get_available_tools(app_config=app_config):
        registry.register("tool", tool.name, _ToolAdapter(tool))
    for agent in list_custom_agents(user_id=user_id):
        registry.register("agent", agent.name, _AgentAdapter(agent.name, user_id))
    return registry
