"""Small, permission-aware adapter registry used by workflow nodes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Protocol

from agentplatform_extension.knowledge.runtime_adapter import adapt_knowledge_tools
from agentplatform_extension.knowledge.scope import KnowledgeScope


class ActionAdapter(Protocol):
    async def run(self, context: ActionContext, params: dict[str, Any]) -> Any: ...

    def astream(self, context: ActionContext, params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]: ...


class ActionResolutionError(RuntimeError):
    pass


def _agent_knowledge_scope(
    scope: KnowledgeScope | None,
    declared_resource_ids: frozenset[str],
) -> KnowledgeScope | None:
    """Restrict a workflow scope to the KBs declared by one Agent node."""

    if scope is None:
        return None
    if not declared_resource_ids:
        return KnowledgeScope()
    bindings = tuple((logical, dataset) for logical, dataset in scope.bindings if logical in declared_resource_ids)
    datasets = {dataset for _, dataset in bindings}
    return KnowledgeScope.from_bindings(
        bindings,
        ready_document_ids={dataset: ids for dataset, ids in scope.ready_document_ids if dataset in datasets},
        retrieval_profiles={dataset: dict(profile) for dataset, profile in scope.retrieval_profiles if dataset in datasets},
    )


@dataclass
class ActionContext:
    workflow_name: str
    run_id: str
    node_id: str
    inputs: dict[str, Any]
    state: dict[str, Any]
    outputs: dict[str, Any]
    file_access: dict[str, list[str]] | None = None
    model_name: str | None = None
    knowledge_scope: KnowledgeScope | None = None

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

    def _effective_tool(self, context: ActionContext) -> Any:
        if context.knowledge_scope is None:
            return self.tool
        adapted = adapt_knowledge_tools([self.tool], context.knowledge_scope)
        if not adapted:
            raise ActionResolutionError("knowledge tool is unavailable in this workflow scope")
        return adapted[0]

    def _build_runtime(self, context: ActionContext) -> Any:
        from langchain.tools import ToolRuntime

        from deerflow.config.paths import get_paths
        from deerflow.sandbox.sandbox_provider import get_sandbox_provider

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
            "code_evidence_path": str(paths.thread_dir(thread_id, user_id=self.user_id) / "user-data" / "code-evidence"),
            "workspace_path": str(paths.sandbox_work_dir(thread_id, user_id=self.user_id)),
            "uploads_path": str(paths.sandbox_uploads_dir(thread_id, user_id=self.user_id)),
            "outputs_path": str(paths.sandbox_outputs_dir(thread_id, user_id=self.user_id)),
        }
        state: dict[str, Any] = {"thread_data": thread_data, "artifacts": [], "todos": None}
        provider = get_sandbox_provider()
        sandbox_id = provider.acquire(thread_id)
        state["sandbox"] = {"sandbox_id": sandbox_id}
        tool = self._effective_tool(context)
        runtime = ToolRuntime(
            state=state,
            context={"thread_id": thread_id, "run_id": thread_id},
            config={"configurable": {"thread_id": thread_id}},
            stream_writer=lambda _update: None,
            tools=[tool],
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
        tool = self._effective_tool(context)
        if hasattr(tool, "ainvoke"):
            return await tool.ainvoke(tool_params)
        return await asyncio.to_thread(tool.invoke, tool_params)

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

    async def _build_executor(self, context: ActionContext, params: dict[str, Any], model_name: str | None = None):
        return await self._build_canonical_executor(context, params, model_name=model_name)

    async def _build_canonical_executor(self, context: ActionContext, params: dict[str, Any], *, model_name: str | None = None):
        import yaml
        from sqlalchemy import select

        from app.agentplatform.resource_models import Resource, ResourceDependency
        from app.agentplatform.resources.service import (
            ResourceAction,
            ResourceActor,
            ResourceNotFound,
            ResourceService,
        )
        from app.agentplatform.resources.storage import ResourceStorage
        from app.agentplatform.workflows.v2.executor_bridge import (
            WorkflowSubagentConfig as SubagentConfig,
        )
        from app.agentplatform.workflows.v2.executor_bridge import (
            WorkflowSubagentExecutor as SubagentExecutor,
        )
        from deerflow.config import get_app_config
        from deerflow.config.paths import get_paths
        from deerflow.persistence.engine import get_session_factory
        from deerflow.tools.tools import get_available_tools

        sf = get_session_factory()
        if sf is None:
            raise ActionResolutionError(f"agent '{self.name}' not found (catalog unavailable)")
        async with sf() as session:
            actor = ResourceActor(
                user_id=self.user_id,
                department_id=None,
                role="user",
                permissions=frozenset({ResourceAction.READ, ResourceAction.USE}),
            )
            service = ResourceService(session, actor)
            resource = await session.get(Resource, self.name)
            if resource is None or resource.type != "agent":
                try:
                    resource = await service.resolve_legacy_alias("agent", self.name)
                except ResourceNotFound as exc:
                    raise ActionResolutionError(f"agent '{self.name}' not found") from exc
            published = await service.get_published_content(resource.id)
            storage = ResourceStorage(get_paths().base_dir)
            root = storage.resources_root / published.storage_key
            config_yaml = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8")) or {}
            soul = ""
            soul_path = root / "SOUL.md"
            if soul_path.exists():
                soul = soul_path.read_text(encoding="utf-8")
            targets = list(
                (
                    await session.execute(
                        select(Resource)
                        .join(ResourceDependency, ResourceDependency.target_resource_id == Resource.id)
                        .where(
                            ResourceDependency.source_resource_id == resource.id,
                            Resource.type == "skill",
                        )
                        .order_by(Resource.slug, Resource.id)
                    )
                ).scalars()
            )
            by_slug = {target.slug: target for target in targets}
            by_id = {target.id: target for target in targets}
            requested = config_yaml.get("skills")
            selected = targets if requested is None else [target for name in requested if (target := by_id.get(name) or by_slug.get(name)) is not None]
            skill_names = [target.slug for target in selected]

        override = params.get("system_prompt", "")
        system_prompt = _compose_system_prompt(soul, override, context)

        subagent = SubagentConfig(
            name=self.name,
            description=f"Workflow node: {context.node_id}",
            system_prompt=system_prompt,
            skills=skill_names,
            model=model_name or config_yaml.get("model") or "inherit",
            max_turns=params.get("max_turns", 50),
            file_access=context.file_access,
            knowledge_scope=context.knowledge_scope,
        )
        tools = get_available_tools(groups=config_yaml.get("tool_groups"), app_config=get_app_config())
        if context.knowledge_scope is not None:
            tools = adapt_knowledge_tools(tools, context.knowledge_scope)
        executor = SubagentExecutor(
            subagent,
            tools,
            app_config=get_app_config(),
            thread_id=context.run_id,
        )
        prompt = params.get("prompt", params.get("input", params))
        return executor, str(prompt)

    def _finalize_result(self, result: Any) -> Any:
        from app.agentplatform.workflows.v2.compiler import WorkflowTransientError
        from app.agentplatform.workflows.v2.executor_bridge import SubagentStatus

        if result.status == SubagentStatus.COMPLETED:
            if _is_llm_unavailable_text(result.result):
                raise WorkflowTransientError(f"agent '{self.name}' failed: LLM provider unavailable")
            return result.result
        if _is_llm_unavailable_text(result.error):
            raise WorkflowTransientError(result.error or f"agent '{self.name}' failed: LLM provider unavailable")
        raise RuntimeError(result.error or f"agent '{self.name}' failed with status {result.status}")

    async def run(self, context: ActionContext, params: dict[str, Any]) -> Any:
        from app.agentplatform.workflows.v2.compiler import WorkflowTransientError
        from deerflow.config import get_app_config
        from deerflow.runtime.user_context import reset_current_user, set_current_user

        configured_models = [model.name for model in getattr(get_app_config(), "models", [])]
        candidates = [context.model_name] if context.model_name else [None]
        candidates.extend(model for model in configured_models if model not in candidates)
        last_error: Any = None
        for candidate in candidates:
            executor, prompt = await self._build_executor(context, params, model_name=candidate)
            user_token = set_current_user(SimpleNamespace(id=self.user_id))
            try:
                try:
                    from agentplatform_extension.evidence import DelegationEvidenceContext, bind_delegation_evidence
                except ImportError:
                    result = await executor._aexecute(prompt)
                else:
                    with bind_delegation_evidence(DelegationEvidenceContext(context.idempotency_key, self.name)):
                        result = await executor._aexecute(prompt)
            finally:
                reset_current_user(user_token)
            try:
                _adopt_subagent_retrieval_evidence(result, context=context, agent_id=self.name)
                value = self._finalize_result(result)
                context.model_name = candidate or getattr(executor, "model_name", None) or context.model_name
                return value
            except WorkflowTransientError as exc:
                last_error = exc
        raise last_error or WorkflowTransientError(f"agent '{self.name}' failed: LLM provider unavailable")

    async def astream(self, context: ActionContext, params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        from app.agentplatform.workflows.v2.compiler import WorkflowTransientError
        from deerflow.config import get_app_config
        from deerflow.runtime.user_context import reset_current_user, set_current_user

        yield {"type": "progress", "message": "started"}
        configured_models = [model.name for model in getattr(get_app_config(), "models", [])]
        candidates = [context.model_name] if context.model_name else [None]
        candidates.extend(model for model in configured_models if model not in candidates)
        queue: asyncio.Queue[Any] = asyncio.Queue()

        async def produce() -> Any:
            try:
                try:
                    from agentplatform_extension.evidence import DelegationEvidenceContext, bind_delegation_evidence
                except ImportError:
                    result = await executor._aexecute(prompt, progress_callback=queue.put)
                else:
                    with bind_delegation_evidence(DelegationEvidenceContext(context.idempotency_key, self.name)):
                        result = await executor._aexecute(prompt, progress_callback=queue.put)
            except Exception as exc:
                await queue.put(_STREAM_FAILURE(exc))
                return None
            await queue.put(_STREAM_END)
            return result

        for candidate in candidates:
            executor, prompt = await self._build_executor(context, params, model_name=candidate)
            user_token = set_current_user(SimpleNamespace(id=self.user_id))
            producer = asyncio.create_task(produce())
            stream_failure: BaseException | None = None
            try:
                while True:
                    update = await queue.get()
                    if update is _STREAM_END:
                        break
                    if isinstance(update, _STREAM_FAILURE):
                        stream_failure = update.error
                        break
                    if update.get("type") == "tool_call":
                        tool = update.get("tool", "?")
                        args = update.get("args_summary", "")
                        yield {"type": "progress", "message": f"[回合 {update.get('turn', '-')}] 调用工具 {tool} → {args}"}
                try:
                    result = await producer
                    if stream_failure is not None:
                        raise stream_failure
                    _adopt_subagent_retrieval_evidence(result, context=context, agent_id=self.name)
                    value = self._finalize_result(result)
                except WorkflowTransientError:
                    continue
                context.model_name = candidate or getattr(executor, "model_name", None) or context.model_name
                yield {"type": "result", "value": value}
                return
            except BaseException:
                producer.cancel()
                raise
            finally:
                reset_current_user(user_token)
        raise WorkflowTransientError(f"agent '{self.name}' failed: LLM provider unavailable")


class _CanonicalAgentAdapter(_AgentAdapter):
    """Run one frozen Agent definition with runner-scoped tools and Skills."""

    def __init__(self, definition: Any, skills: list[Any], user_id: str, *, allowed_tool_groups: frozenset[str] | None) -> None:
        super().__init__(definition.resource_id, user_id)
        self.definition = definition
        self.skills = list(skills)
        self.allowed_tool_groups = allowed_tool_groups

    async def _build_executor(self, context: ActionContext, params: dict[str, Any], model_name: str | None = None):
        from app.agentplatform.resources.runtime import intersect_tool_groups
        from app.agentplatform.workflows.v2.executor_bridge import (
            WorkflowSubagentConfig as SubagentConfig,
        )
        from app.agentplatform.workflows.v2.executor_bridge import (
            WorkflowSubagentExecutor as SubagentExecutor,
        )
        from deerflow.config import get_app_config
        from deerflow.tools.tools import get_available_tools

        config = self.definition.config
        agent_scope = _agent_knowledge_scope(context.knowledge_scope, self.definition.knowledge_resource_ids)
        override = params.get("system_prompt", "")
        system_prompt = _compose_system_prompt(self.definition.soul, override, context)
        subagent = SubagentConfig(
            name=self.definition.resource_id,
            description=f"Workflow node: {context.node_id}",
            system_prompt=system_prompt,
            skills=[skill.name for skill in self.skills],
            model=model_name or config.model or "inherit",
            max_turns=params.get("max_turns", 50),
            file_access=context.file_access,
            knowledge_scope=agent_scope,
        )
        frozen_skills = list(self.skills)

        class CanonicalSubagentExecutor(SubagentExecutor):
            async def _load_skills(self) -> list[Any]:
                return list(frozen_skills)

        app_config = get_app_config()
        groups = intersect_tool_groups(config.tool_groups, self.allowed_tool_groups)
        executor = CanonicalSubagentExecutor(
            subagent,
            adapt_knowledge_tools(get_available_tools(groups=groups, app_config=app_config), agent_scope) if agent_scope is not None else get_available_tools(groups=groups, app_config=app_config),
            app_config=app_config,
            thread_id=context.run_id,
        )
        executor.canonical_run_id = context.run_id
        prompt = params.get("prompt", params.get("input", params))
        return executor, str(prompt)


class _STREAM_END:
    """Sentinel that closes an agent progress stream."""


@dataclass
class _STREAM_FAILURE:
    """Carries an executor exception to the consumer without hanging the stream."""

    error: Exception


def _compose_system_prompt(soul: str, override: str, context: ActionContext) -> str:
    """Compose SOUL + explicit workflow-node marker + per-node instructions.

    The marker gives the model a deterministic signal that it is running as a
    workflow node (never present in standalone agent chats), so persona-level
    deliverable lists in SOUL.md/SKILL.md defer to the node's own instructions.
    """
    mode_header = (
        f"## 运行模式：工作流节点\n\n"
        f"当前以工作流「{context.workflow_name}」的节点「{context.node_id}」身份运行。"
        "只读取、只写入本节点任务指令中声明的文件；全局输出要求中与本节点无关的交付物"
        "（如其他阶段负责的图表或报告）不适用。写入被文件访问策略拒绝时，不要更换路径重试，"
        "继续完成本节点声明的工作。"
    )
    sections = [soul.strip(), mode_header]
    if override:
        sections.append(f"## 当前阶段指令\n\n{override}")
    return "\n\n".join(section for section in sections if section)


def _is_llm_unavailable_text(result: Any) -> bool:
    if not isinstance(result, str):
        return False
    lowered = result.lower()
    return any(marker in lowered for marker in _AgentAdapter._LLM_UNAVAILABLE_MARKERS)


def _adopt_subagent_retrieval_evidence(result: Any, *, context: ActionContext, agent_id: str) -> None:
    receipts = getattr(result, "retrieval_receipts", None)
    if receipts is None:
        return
    try:
        from agentplatform_extension.evidence import record_delegated_retrieval_receipts
    except ImportError:
        return
    record_delegated_retrieval_receipts(
        receipts,
        parent_tool_receipt_id=context.idempotency_key,
        child_task_id=str(getattr(result, "task_id", context.node_id)),
        child_agent_id=agent_id,
    )
