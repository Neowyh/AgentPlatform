"""DeerFlow-backed subagent surface for workflow v2 agent nodes.

deerflow's ``SubagentExecutor`` is the upstream evolution of the ideer
executor, but it has no concept of enterprise workflow nodes, so three
contracts that workflow agent nodes depend on have no upstream equivalent:

1. ``file_access`` — a node's declared read/write root policy, enforced by a
   ``FilesystemScopeMiddleware`` appended at agent assembly (ideer's executor
   did this in ``_create_agent``).
2. Frozen-run sandbox scoping — ideer propagated ``canonical_run_id`` through
   the run context so sandbox tools keyed the sandbox by
   ``canonical_sandbox_scope(thread_id, run_id)``. deerflow's tools key the
   sandbox on ``context["thread_id"]`` alone, so the bridge rewrites the
   thread id to the canonical scope for the duration of the execution.
3. ``progress_callback`` — ideer's ``_aexecute`` emitted one ``tool_call``
   progress event per new AI message; deerflow's signature has no callback.
   The bridge reproduces the events by streaming new messages off the result
   while the run executes.

No deerflow code is modified. The file-scope middleware is injected by wrapping
the executor module's ``create_agent`` binding behind a request-scoped
ContextVar, so the wrapper is inert for every non-workflow executor.
"""

from __future__ import annotations

import asyncio
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware

from app.agentplatform.workflows.v2.filesystem_scope import FilesystemScopeMiddleware
from deerflow.subagents import executor as _executor_module
from deerflow.subagents.config import SubagentConfig
from deerflow.subagents.executor import SubagentExecutor, SubagentStatus

__all__ = ["SubagentStatus", "WorkflowSubagentConfig", "WorkflowSubagentExecutor"]

_PENDING_FILE_SCOPE: ContextVar[list[Any] | None] = ContextVar("workflow_file_scope_middlewares", default=None)


class RunWorkspacePathsMiddleware(AgentMiddleware[AgentState]):
    """Pin ``thread_data`` to the run workspace while the sandbox is scoped.

    The bridge scopes the sandbox thread so the provider can recognize the
    frozen run (``canonical_sandbox_scope``), but the upstream thread-data
    middleware derives ``/mnt/user-data`` host paths from that scoped identity,
    while the workflow file-roots contract — and the artifact gate — key the
    run workspace on the raw run id (``thread_id == run_id``). Appended after
    the upstream middleware, this override re-points the workspace, uploads and
    outputs mappings at the run workspace so tool writes land where the gate
    verifies them.
    """

    def __init__(self, *, run_id: str) -> None:
        self.run_id = run_id

    @override
    def before_agent(self, state: AgentState, runtime: Any) -> dict[str, Any] | None:
        from app.agentplatform.workflows.v2.file_roots import make_host_resolver
        from deerflow.runtime.user_context import resolve_runtime_user_id

        user_id = resolve_runtime_user_id(runtime)
        resolver = make_host_resolver(self.run_id, user_id)
        thread_data = dict(state.get("thread_data") or {})
        updated = False
        for key, virtual in (
            ("workspace_path", "/mnt/user-data/workspace"),
            ("uploads_path", "/mnt/user-data/uploads"),
            ("outputs_path", "/mnt/user-data/outputs"),
        ):
            host = resolver(virtual)
            if host is not None and thread_data.get(key) != host:
                thread_data[key] = host
                updated = True
        return {"thread_data": thread_data} if updated else None


def _install_scope_aware_create_agent() -> None:
    """Wrap the executor module's ``create_agent`` once, at import time.

    Imports hold the import lock, so the check-then-install runs without a
    race. The wrapper appends the pending workflow middlewares only when a
    workflow execution set the ContextVar in the current task; every other
    caller is a passthrough.
    """
    original = _executor_module.create_agent
    if getattr(original, "_workflow_scope_aware", False):
        return

    def scope_aware_create_agent(*args: Any, **kwargs: Any):
        pending = _PENDING_FILE_SCOPE.get()
        if pending:
            kwargs["middleware"] = [*(kwargs.get("middleware") or []), *pending]
        return original(*args, **kwargs)

    scope_aware_create_agent._workflow_scope_aware = True  # type: ignore[attr-defined]
    _executor_module.create_agent = scope_aware_create_agent


_install_scope_aware_create_agent()


@dataclass
class WorkflowSubagentConfig(SubagentConfig):
    """Subagent config plus the workflow-node ``file_access`` policy.

    The upstream dataclass has no ``file_access`` field (upstream has no
    workflow file-access concept); the field rides on this subclass so node
    declarations reach the executor untouched.
    """

    file_access: dict[str, list[str]] | None = None


class WorkflowSubagentExecutor(SubagentExecutor):
    """Subagent executor with the enterprise workflow-node contracts restored.

    See the module docstring for the three contracts this class re-establishes
    on top of the deerflow executor.
    """

    _PROGRESS_POLL_INTERVAL_SECONDS = 0.05

    async def _aexecute(
        self,
        task: str,
        result_holder: Any = None,
        *,
        progress_callback: Any = None,
    ) -> Any:
        file_access = getattr(self.config, "file_access", None)
        canonical_run_id = getattr(self, "canonical_run_id", None)

        original_thread_id = self.thread_id
        scoped = False
        if canonical_run_id and original_thread_id:
            from app.agentplatform.resources.canonical_sandbox import canonical_sandbox_scope

            self.thread_id = canonical_sandbox_scope(original_thread_id, str(canonical_run_id))
            scoped = True

        pending_middlewares: list[Any] | None = None
        if file_access is not None or scoped:
            pending_middlewares = []
            if scoped:
                pending_middlewares.append(RunWorkspacePathsMiddleware(run_id=str(canonical_run_id) if not isinstance(canonical_run_id, str) else canonical_run_id))
            if file_access is not None:
                pending_middlewares.append(
                    FilesystemScopeMiddleware(
                        read_roots=file_access.get("read", []),
                        write_roots=file_access.get("write", []),
                    )
                )
            if not pending_middlewares:
                pending_middlewares = None
        token = _PENDING_FILE_SCOPE.set(pending_middlewares)
        try:
            if progress_callback is None:
                return await super()._aexecute(task, result_holder)
            return await self._aexecute_with_progress(task, result_holder, progress_callback)
        finally:
            _PENDING_FILE_SCOPE.reset(token)
            if scoped:
                self.thread_id = original_thread_id

    async def _aexecute_with_progress(self, task: str, result_holder: Any, progress_callback: Any) -> Any:
        """Drive the run while emitting ideer-compatible per-turn events.

        ideer emitted ``{"type": "tool_call", ...}`` from inside its streaming
        loop as each new AI message landed. deerflow appends the same message
        dicts to ``result.ai_messages`` as it streams, so polling the holder
        reproduces the identical event sequence (one event per tool call, with
        the 1-based message index as ``turn``).
        """
        from deerflow.subagents.executor import SubagentResult, SubagentStatus

        result = result_holder
        if result is None:
            result = SubagentResult(
                task_id=str(uuid.uuid4())[:8],
                trace_id=self.trace_id,
                status=SubagentStatus.PENDING,
            )
        driver = asyncio.ensure_future(super()._aexecute(task, result))
        seen = 0
        try:
            while True:
                done, _pending = await asyncio.wait({driver}, timeout=self._PROGRESS_POLL_INTERVAL_SECONDS)
                messages = result.ai_messages or []
                while seen < len(messages):
                    seen += 1
                    message = messages[seen - 1]
                    if not isinstance(message, dict):
                        continue
                    for call in message.get("tool_calls") or []:
                        await progress_callback(
                            {
                                "type": "tool_call",
                                "tool": call.get("name"),
                                "turn": seen,
                                "args_summary": str(call.get("args"))[:300],
                            }
                        )
                if done:
                    return driver.result()
        except BaseException:
            driver.cancel()
            raise
