"""Small, permission-aware adapter registry used by workflow nodes."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol


class ActionAdapter(Protocol):
    async def run(self, context: ActionContext, params: dict[str, Any]) -> Any: ...


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


class _AgentAdapter:
    def __init__(self, name: str, user_id: str) -> None:
        self.name = name
        self.user_id = user_id

    async def run(self, context: ActionContext, params: dict[str, Any]) -> Any:
        from ideer.config import get_app_config
        from ideer.config.agents_config import load_agent_config, load_agent_soul
        from ideer.subagents.config import SubagentConfig
        from ideer.subagents.executor import SubagentExecutor, SubagentStatus
        from ideer.tools.tools import get_available_tools

        config = load_agent_config(self.name, user_id=self.user_id)
        if config is None:
            raise ActionResolutionError(f"agent '{self.name}' not found")
        subagent = SubagentConfig(
            name=self.name,
            description=f"Workflow node: {context.node_id}",
            system_prompt=load_agent_soul(self.name, user_id=self.user_id),
            tools=config.tool_groups,
            skills=config.skills,
            model=config.model or "inherit",
        )
        executor = SubagentExecutor(subagent, get_available_tools(app_config=get_app_config()), app_config=get_app_config())
        prompt = params.get("prompt", params.get("input", params))
        result = await executor._aexecute(str(prompt))
        if result.status == SubagentStatus.COMPLETED:
            return result.result
        raise RuntimeError(result.error or f"agent '{self.name}' failed with status {result.status}")


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
