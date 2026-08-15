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
    def __init__(self, tool: Any, user_id: str | None = None) -> None:
        self.tool = tool
        self.user_id = user_id
        self._runtime_cache: dict[str, Any] = {}

    def _build_runtime(self, context: ActionContext) -> Any:
        from langchain.tools import ToolRuntime

        from ideer.config.paths import get_paths
        from ideer.sandbox.sandbox_provider import get_sandbox_provider

        # The sandbox tools resolve virtual paths through runtime.state.thread_data
        # and lazily acquire a sandbox through runtime.context.thread_id; mirror
        # the thread-scoped paths the local sandbox derives for agent runs so
        # workflow `kind: tool` nodes behave identically (thread_id == run_id).
        thread_id = context.run_id
        cached = self._runtime_cache.get(thread_id)
        if cached is not None:
            return cached
        paths = get_paths()
        thread_data = {
            "workspace_path": str(paths.sandbox_work_dir(thread_id, user_id=self.user_id)),
            "uploads_path": str(paths.sandbox_uploads_dir(thread_id, user_id=self.user_id)),
            "outputs_path": str(paths.sandbox_outputs_dir(thread_id, user_id=self.user_id)),
        }
        state: dict[str, Any] = {"thread_data": thread_data, "artifacts": [], "todos": None}
        provider = get_sandbox_provider()
        sandbox_id = provider.acquire(thread_id)
        state["sandbox"] = {"sandbox_id": sandbox_id}
        runtime = ToolRuntime(
            state=state,
            context={"thread_id": thread_id, "run_id": thread_id},
            config={"configurable": {"thread_id": thread_id}},
            stream_writer=lambda _update: None,
            tools=[self.tool],
            tool_call_id=None,
            store=None,
        )
        self._runtime_cache[thread_id] = runtime
        return runtime

    async def run(self, context: ActionContext, params: dict[str, Any]) -> Any:
        runtime = self._build_runtime(context)
        tool_params = dict(params)
        if "runtime" in tool_params:
            del tool_params["runtime"]
        tool_params["runtime"] = runtime
        if hasattr(self.tool, "ainvoke"):
            return await self.tool.ainvoke(tool_params)
        return await asyncio.to_thread(self.tool.invoke, tool_params)

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

    def __init__(self, name: str, user_id: str, *, owner_id: str | None = None) -> None:
        self.name = name
        self.user_id = user_id
        # For shared agents the config/SOUL are read from the declaring owner's
        # directory while the runtime context (sandbox, user) stays with the
        # runner.
        self.owner_id = owner_id

    def _build_executor(self, context: ActionContext, params: dict[str, Any]):
        from ideer.config import get_app_config
        from ideer.config.agents_config import load_agent_config, load_agent_soul
        from ideer.subagents.config import SubagentConfig
        from ideer.subagents.executor import SubagentExecutor
        from ideer.tools.tools import get_available_tools

        config_user_id = self.owner_id or self.user_id
        config = load_agent_config(self.name, user_id=config_user_id)
        if config is None:
            raise ActionResolutionError(f"agent '{self.name}' not found")

        soul = load_agent_soul(self.name, user_id=config_user_id) or ""
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
        return executor, str(prompt)

    def _finalize_result(self, result: Any) -> Any:
        from ideer.subagents.executor import SubagentStatus
        from ideer.workflows.v2.compiler import WorkflowTransientError

        if result.status == SubagentStatus.COMPLETED:
            if _is_llm_unavailable_text(result.result):
                raise WorkflowTransientError(f"agent '{self.name}' failed: LLM provider unavailable")
            return result.result
        if _is_llm_unavailable_text(result.error):
            raise WorkflowTransientError(result.error or f"agent '{self.name}' failed: LLM provider unavailable")
        raise RuntimeError(result.error or f"agent '{self.name}' failed with status {result.status}")

    async def run(self, context: ActionContext, params: dict[str, Any]) -> Any:
        from ideer.runtime.user_context import reset_current_user, set_current_user

        executor, prompt = self._build_executor(context, params)
        user_token = set_current_user(SimpleNamespace(id=self.user_id))
        try:
            result = await executor._aexecute(prompt)
        finally:
            reset_current_user(user_token)
        return self._finalize_result(result)

    async def astream(self, context: ActionContext, params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        from ideer.runtime.user_context import reset_current_user, set_current_user

        yield {"type": "progress", "message": "started"}
        executor, prompt = self._build_executor(context, params)
        queue: asyncio.Queue[Any] = asyncio.Queue()

        async def produce() -> Any:
            result = await executor._aexecute(prompt, progress_callback=queue.put)
            await queue.put(_STREAM_END)
            return result

        user_token = set_current_user(SimpleNamespace(id=self.user_id))
        producer = asyncio.create_task(produce())
        try:
            while True:
                update = await queue.get()
                if update is _STREAM_END:
                    break
                if update.get("type") == "tool_call":
                    tool = update.get("tool", "?")
                    args = update.get("args_summary", "")
                    yield {"type": "progress", "message": f"[回合 {update.get('turn', '-')}] 调用工具 {tool} → {args}"}
        except BaseException:
            producer.cancel()
            raise
        finally:
            reset_current_user(user_token)
        yield {"type": "result", "value": self._finalize_result(await producer)}


class _CanonicalAgentAdapter(_AgentAdapter):
    """Run one frozen Agent definition with runner-scoped tools and Skills."""

    def __init__(self, definition: Any, skills: list[Any], user_id: str, *, allowed_tool_groups: frozenset[str] | None) -> None:
        super().__init__(definition.resource_id, user_id)
        self.definition = definition
        self.skills = list(skills)
        self.allowed_tool_groups = allowed_tool_groups

    def _build_executor(self, context: ActionContext, params: dict[str, Any]):
        from ideer.config import get_app_config
        from ideer.resources.runtime import intersect_tool_groups
        from ideer.subagents.config import SubagentConfig
        from ideer.subagents.executor import SubagentExecutor
        from ideer.tools.tools import get_available_tools

        config = self.definition.config
        override = params.get("system_prompt", "")
        if self.definition.soul and override:
            system_prompt = f"{self.definition.soul}\n\n## 当前阶段指令\n\n{override}"
        else:
            system_prompt = self.definition.soul or override
        subagent = SubagentConfig(
            name=self.definition.resource_id,
            description=f"Workflow node: {context.node_id}",
            system_prompt=system_prompt,
            skills=[skill.name for skill in self.skills],
            model=config.model or "inherit",
            max_turns=params.get("max_turns", 50),
            file_access=context.file_access,
        )
        frozen_skills = list(self.skills)

        class CanonicalSubagentExecutor(SubagentExecutor):
            async def _load_skills(self) -> list[Any]:
                return list(frozen_skills)

        app_config = get_app_config()
        groups = intersect_tool_groups(config.tool_groups, self.allowed_tool_groups)
        executor = CanonicalSubagentExecutor(
            subagent,
            get_available_tools(groups=groups, app_config=app_config),
            app_config=app_config,
            thread_id=context.run_id,
        )
        executor.canonical_run_id = context.run_id
        prompt = params.get("prompt", params.get("input", params))
        return executor, str(prompt)


class _STREAM_END:
    """Sentinel that closes an agent progress stream."""


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
        registry.register("tool", tool.name, _ToolAdapter(tool, user_id=user_id))
    for agent in list_custom_agents(user_id=user_id):
        registry.register("agent", agent.name, _AgentAdapter(agent.name, user_id))
    return registry
