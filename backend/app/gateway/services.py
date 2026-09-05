"""Run lifecycle service layer.

Centralizes the business logic for creating runs, formatting SSE
frames, and consuming stream bridge events.  Router modules
(``thread_runs``, ``runs``) are thin HTTP handlers that delegate here.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException, Request
from langchain_core.messages import BaseMessage
from langchain_core.messages.utils import convert_to_messages

from app.gateway.auth_disabled import AUTH_SOURCE_INTERNAL
from app.gateway.authz import _cached_rbac_identity
from app.gateway.deps import get_checkpointer, get_run_context, get_run_manager, get_stream_bridge
from app.gateway.internal_auth import INTERNAL_OWNER_USER_ID_HEADER_NAME, INTERNAL_SYSTEM_ROLE, get_internal_user
from app.gateway.utils import sanitize_log_param
from deerflow.config import get_app_config
from deerflow.runtime import (
    END_SENTINEL,
    HEARTBEAT_SENTINEL,
    CheckpointStateAccessor,
    ConflictError,
    DisconnectMode,
    RunManager,
    RunRecord,
    RunStatus,
    StreamBridge,
    UnsupportedStrategyError,
    build_state_mutation_graph,
    run_agent,
)
from deerflow.runtime.checkpoint_mode import (
    CheckpointModeMismatchError,
    checkpoint_tuple_uses_delta,
    inject_checkpoint_mode,
)
from deerflow.runtime.checkpoint_state import graph_state_schema
from deerflow.runtime.runs.naming import resolve_root_run_name
from deerflow.trace_context import ensure_trace_context

logger = logging.getLogger(__name__)


def prompt_template_hash(prompt_template: str) -> str:
    """Return the stable content hash stored with a Task Chip selection."""
    return hashlib.sha256(prompt_template.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# SSE formatting
# ---------------------------------------------------------------------------


def format_sse(event: str, data: Any, *, event_id: str | None = None) -> str:
    """Format a single SSE frame.

    Field order: ``event:`` -> ``data:`` -> ``id:`` (optional) -> blank line.
    This matches the LangGraph Platform wire format consumed by the
    ``useStream`` React hook and the Python ``langgraph-sdk`` SSE decoder.
    """
    payload = json.dumps(data, default=str, ensure_ascii=False)
    parts = [f"event: {event}", f"data: {payload}"]
    if event_id:
        parts.append(f"id: {event_id}")
    parts.append("")
    parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Input / config helpers
# ---------------------------------------------------------------------------


def normalize_stream_modes(raw: list[str] | str | None) -> list[str]:
    """Normalize the stream_mode parameter to a list.

    Default matches what ``useStream`` expects: values + messages-tuple.
    """
    if raw is None:
        return ["values"]
    if isinstance(raw, str):
        return [raw]
    return raw if raw else ["values"]


def normalize_input(raw_input: dict[str, Any] | None) -> dict[str, Any]:
    """Convert LangGraph Platform input format to LangChain state dict.

    Delegates dict→message coercion to ``langchain_core.messages.utils.convert_to_messages``
    so that ``additional_kwargs`` (e.g. uploaded-file metadata — gh #3132), ``id``,
    ``name``, and non-human roles (ai/system/tool) survive unchanged.  An earlier
    hand-rolled version only forwarded ``content`` and collapsed every role to
    ``HumanMessage``, which silently stripped frontend-supplied attachments.

    Malformed message dicts (missing ``role``/``type``/``content``, unsupported
    role, etc.) raise ``HTTPException(400)`` with the offending index, instead
    of bubbling up as a 500.  The gateway is a system boundary, so per-entry
    validation errors are the right shape for clients to retry against.
    """
    if raw_input is None:
        return {}
    messages = raw_input.get("messages")
    if messages and isinstance(messages, list):
        converted: list[Any] = []
        for index, msg in enumerate(messages):
            if isinstance(msg, BaseMessage):
                converted.append(msg)
            elif isinstance(msg, dict):
                try:
                    converted.extend(convert_to_messages([msg]))
                except (ValueError, TypeError, NotImplementedError) as exc:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid message at input.messages[{index}]: {exc}",
                    ) from exc
            else:
                converted.append(msg)
        return {**raw_input, "messages": converted}
    return raw_input


def validate_evidence_selection(evidence_mode: str | None, code_package_id: str | None) -> tuple[str, str | None]:
    """Normalize the hidden hybrid mode and validate an optional code package."""
    mode = evidence_mode or "hybrid"
    if mode not in {"document", "code", "hybrid"}:
        raise HTTPException(status_code=400, detail="evidence_mode must be document, code, or hybrid")
    if mode == "code" and not code_package_id:
        raise HTTPException(status_code=400, detail=f"{mode} mode requires a Code Evidence Package")
    if mode == "document" and code_package_id:
        raise HTTPException(status_code=400, detail="document mode cannot include a Code Evidence Package")
    return mode, str(code_package_id) if code_package_id else None


_DEFAULT_ASSISTANT_ID = "lead_agent"


# Whitelist of run-context keys that the langgraph-compat layer forwards from
# ``body.context`` into the run config. ``config["context"]`` exists in
# LangGraph >=0.6, but these values must be written to both ``configurable``
# (for legacy ``_get_runtime_config`` consumers) and ``context`` because
# LangGraph >=1.1.9 no longer makes ``ToolRuntime.context`` fall back to
# ``configurable`` for consumers like ``setup_agent``.
_CONTEXT_CONFIGURABLE_KEYS: frozenset[str] = frozenset(
    {
        "model_name",
        "mode",
        "thinking_enabled",
        "reasoning_effort",
        "is_plan_mode",
        "subagent_enabled",
        "max_concurrent_subagents",
        "agent_name",
        "agent_resource_id",
        "is_bootstrap",
        "skill_name",
        "skill_resource_id",
        "skill_names",
        "evidence_mode",
        "code_package_id",
        "code_evidence_source",
        "code_evidence_manifest",
    }
)

_CONTEXT_INTERNAL_CALLER_KEYS: frozenset[str] = frozenset({"non_interactive"})
_SERVER_OWNED_AUTHZ_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "is_internal",
        "authz_attributes",
        "channel_user_id",
        "langgraph_auth_user",
        "langgraph_auth_user_id",
        "sandbox_lease_owner_id",
        "sandbox_command_scope_id",
    }
)

_DEFAULT_RECURSION_LIMIT = 100
_DEFAULT_MAX_RECURSION_LIMIT = 1000


def _resolve_max_recursion_limit() -> int:
    """Read the configured execution ceiling, with a safe fallback."""

    try:
        return int(get_app_config().max_recursion_limit)
    except Exception:
        return _DEFAULT_MAX_RECURSION_LIMIT


def _clamp_recursion_limit(value: Any, max_limit: int) -> int:
    """Clamp untrusted recursion settings to a positive server-owned range."""

    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return _DEFAULT_RECURSION_LIMIT
    return min(value, max(1, int(max_limit)))


def merge_run_context_overrides(
    config: dict[str, Any],
    context: Mapping[str, Any] | None,
    *,
    internal: bool = False,
) -> None:
    """Merge whitelisted keys from ``body.context`` into both ``config['configurable']``
    and ``config['context']`` so they are visible to legacy configurable readers and
    to LangGraph ``ToolRuntime.context`` consumers (e.g. the ``setup_agent`` tool —
    see issue #2677)."""
    if not context:
        return
    configurable = config.setdefault("configurable", {})
    runtime_context = config.setdefault("context", {})
    keys = _CONTEXT_CONFIGURABLE_KEYS | _CONTEXT_INTERNAL_CALLER_KEYS if internal else _CONTEXT_CONFIGURABLE_KEYS
    for key in keys:
        if key in context:
            if isinstance(configurable, dict):
                configurable.setdefault(key, context[key])
            if isinstance(runtime_context, dict):
                runtime_context.setdefault(key, context[key])
    if "user_id" in context and isinstance(runtime_context, dict):
        runtime_context.setdefault("user_id", context["user_id"])
    if internal and "channel_user_id" in context and isinstance(runtime_context, dict):
        runtime_context.setdefault("channel_user_id", context["channel_user_id"])


def strip_internal_context_keys(config: dict[str, Any]) -> None:
    """Remove internal-only execution flags from client-supplied config."""

    for section in ("context", "configurable"):
        value = config.get(section)
        if isinstance(value, dict):
            for key in _CONTEXT_INTERNAL_CALLER_KEYS:
                value.pop(key, None)


def inject_authenticated_user_context(
    config: dict[str, Any],
    request: Request,
    *,
    request_context: Mapping[str, Any] | None = None,
) -> None:
    """Stamp the authenticated user into the run context for background tools.

    Tool execution may happen after the request handler has returned, so tools
    that persist user-scoped files should not rely only on ambient ContextVars.
    The value comes from server-side auth state, never from client context.
    """

    runtime_context = config.setdefault("context", {})
    if not isinstance(runtime_context, dict):
        raise TypeError("run context must be a mapping")
    for key in _SERVER_OWNED_AUTHZ_CONTEXT_KEYS:
        runtime_context.pop(key, None)
    configurable = config.get("configurable")
    if isinstance(configurable, dict):
        for key in _SERVER_OWNED_AUTHZ_CONTEXT_KEYS:
            configurable.pop(key, None)

    auth_source = getattr(getattr(request, "state", None), "auth_source", None)
    runtime_context["is_internal"] = auth_source == AUTH_SOURCE_INTERNAL
    if auth_source == AUTH_SOURCE_INTERNAL and request_context is not None:
        channel_user_id = request_context.get("channel_user_id")
        if channel_user_id is not None:
            runtime_context["channel_user_id"] = channel_user_id

    user = getattr(request.state, "user", None)
    user_id = getattr(user, "id", None)
    if user_id is None:
        return

    if getattr(user, "system_role", None) == INTERNAL_SYSTEM_ROLE:
        runtime_context.pop("user_role", None)
        runtime_context.pop("oauth_provider", None)
        runtime_context.pop("oauth_id", None)
        return

    runtime_context["user_id"] = str(user_id)
    cached_identity = getattr(getattr(request, "state", None), "_ideer_rbac_user", None)
    resolved_role = cached_identity.get("role") if isinstance(cached_identity, dict) else None
    runtime_context["user_role"] = resolved_role or getattr(user, "system_role", None)
    runtime_context["oauth_provider"] = getattr(user, "oauth_provider", None)
    runtime_context["oauth_id"] = getattr(user, "oauth_id", None)
    department_id = cached_identity.get("department_id") if isinstance(cached_identity, dict) else None
    if department_id is not None:
        runtime_context["authz_attributes"] = {"department_id": str(department_id)}


def resolve_agent_factory(assistant_id: str | None):
    """Resolve the agent factory callable from config.

    Custom agents are implemented as ``lead_agent`` + an ``agent_name``
    injected into ``configurable`` or ``context`` — see
    :func:`build_run_config`.  All ``assistant_id`` values therefore map to the
    same factory; the routing happens inside ``make_lead_agent`` when it reads
    ``cfg["agent_name"]``.
    """
    from deerflow.agents.lead_agent.agent import make_lead_agent

    return make_lead_agent


def _canonical_assistant_id(assistant_id: str | None) -> str | None:
    if not assistant_id or assistant_id == _DEFAULT_ASSISTANT_ID:
        return None
    try:
        return str(uuid.UUID(assistant_id))
    except ValueError:
        return None


async def _canonical_selection_metadata(
    run_id: str,
    agent_resource_id: str,
    body_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Return immutable resource identities alongside user-facing entry labels."""
    from sqlalchemy import select

    from app.agentplatform.resource_models import Resource, ResourceVersion, RunResourceSnapshot
    from deerflow.persistence.engine import get_session_factory

    session_factory = get_session_factory()
    if session_factory is None:
        return {}
    async with session_factory() as session:
        rows = list(
            (
                await session.execute(
                    select(Resource, ResourceVersion, RunResourceSnapshot)
                    .join(RunResourceSnapshot, RunResourceSnapshot.resource_id == Resource.id)
                    .join(
                        ResourceVersion,
                        (ResourceVersion.resource_id == Resource.id) & (ResourceVersion.version == RunResourceSnapshot.version),
                    )
                    .where(RunResourceSnapshot.run_id == run_id)
                )
            ).all()
        )
    by_id = {resource.id: (resource, version) for resource, version, _snapshot in rows}
    agent, agent_version = by_id.get(agent_resource_id, (None, None))
    if agent is None or agent_version is None:
        return {}
    selected_skill = body_context.get("skill_resource_id") or body_context.get("skill_name")
    skill_entry = None
    if selected_skill:
        for resource, version in by_id.values():
            if resource.type == "skill" and (resource.id == selected_skill or resource.slug == selected_skill):
                skill_entry = {
                    "resource_id": resource.id,
                    "display_name": resource.display_name,
                    "slug": resource.slug,
                    "version": version.version,
                    "content_hash": version.content_hash,
                }
                break
    selection: dict[str, Any] = {
        "agent": {
            "resource_id": agent.id,
            "display_name": agent.display_name,
            "slug": agent.slug,
            "version": agent_version.version,
            "content_hash": agent_version.content_hash,
        },
        "resolved_skill_ids": sorted(resource.id for resource, _version in by_id.values() if resource.type == "skill"),
        "resource_snapshots": [
            {
                "resource_id": snapshot.resource_id,
                "version": snapshot.version,
                "content_hash": snapshot.content_hash,
                "selection_role": snapshot.selection_role,
            }
            for _resource, _version, snapshot in rows
        ],
        "policy_revision": str(max(snapshot.authz_revision for _resource, _version, snapshot in rows)),
    }
    if skill_entry is not None:
        selection["preferred_skill"] = skill_entry
    for key in ("scenario_id", "agent_label", "task_id", "task_label", "prompt_template"):
        if key in body_context:
            selection[key] = body_context[key]
    task_id = body_context.get("task_id")
    if isinstance(task_id, str):
        selection["prompt_template_id"] = task_id
    prompt_template = body_context.get("prompt_template")
    if isinstance(prompt_template, str):
        selection["prompt_template_hash"] = prompt_template_hash(prompt_template)
    return {"selection_snapshot": selection}


async def _discard_canonical_run_snapshot(run_id: str) -> None:
    """Compensate a prepared snapshot when Run creation is rejected."""

    from sqlalchemy import delete

    from app.agentplatform.resource_models import RunResourceSnapshot
    from deerflow.persistence.engine import get_session_factory

    session_factory = get_session_factory()
    if session_factory is None:
        return
    async with session_factory() as session:
        await session.execute(delete(RunResourceSnapshot).where(RunResourceSnapshot.run_id == run_id))
        await session.commit()


def build_run_config(
    thread_id: str,
    request_config: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
    *,
    assistant_id: str | None = None,
) -> dict[str, Any]:
    """Build a RunnableConfig dict for the agent.

    When *assistant_id* refers to a custom agent (anything other than
    ``"lead_agent"`` / ``None``), the name is forwarded as ``agent_name`` in
    whichever runtime options container is active: ``context`` for
    LangGraph >= 0.6.0 requests, otherwise ``configurable``.
    ``make_lead_agent`` reads this key to load the matching
    ``agents/<name>/SOUL.md`` and per-agent config — without it the agent
    silently runs as the default lead agent.

    This mirrors the channel manager's ``_resolve_run_params`` logic so that
    the LangGraph Platform-compatible HTTP API and the IM channel path behave
    identically.
    """
    config: dict[str, Any] = {"recursion_limit": 100}
    if request_config:
        # LangGraph >= 0.6.0 introduced ``context`` as the preferred way to
        # pass thread-level data and rejects requests that include both
        # ``configurable`` and ``context``.  If the caller already sends
        # ``context``, honour it and skip our own ``configurable`` dict.
        if "context" in request_config:
            if "configurable" in request_config:
                logger.warning(
                    "build_run_config: client sent both 'context' and 'configurable'; preferring 'context' (LangGraph >= 0.6.0). thread_id=%s, caller_configurable keys=%s",
                    thread_id,
                    list(request_config.get("configurable", {}).keys()),
                )
            context_value = request_config["context"]
            if context_value is None:
                context = {}
            elif isinstance(context_value, Mapping):
                context = dict(context_value)
            else:
                raise ValueError("request config 'context' must be a mapping or null.")
            context.setdefault("thread_id", thread_id)
            config["context"] = context
            # Keep the thread id in the checkpoint-facing container while
            # dropping any caller-supplied configurable overrides.
            config["configurable"] = {"thread_id": thread_id}
        else:
            configurable = {"thread_id": thread_id}
            configurable.update(request_config.get("configurable", {}))
            configurable["thread_id"] = thread_id
            config["configurable"] = configurable
        for k, v in request_config.items():
            if k not in ("configurable", "context"):
                config[k] = v
    else:
        config["configurable"] = {"thread_id": thread_id}

    # The checkpoint channel mode is a server-owned control field.  The
    # checkpoint preparation seam applies it after request authentication;
    # never allow a client to smuggle a mode through either config container.
    from deerflow.runtime.checkpoint_mode import INTERNAL_CHECKPOINT_MODE_KEY

    for section in ("context", "configurable"):
        value = config.get(section)
        if isinstance(value, dict):
            value.pop(INTERNAL_CHECKPOINT_MODE_KEY, None)

    # Inject custom agent name when the caller specified a non-default assistant.
    # Honour an explicit agent_name in the active runtime options container.
    if assistant_id and assistant_id != _DEFAULT_ASSISTANT_ID:
        normalized = assistant_id.strip().lower().replace("_", "-")
        if not normalized or not re.fullmatch(r"[a-z0-9-]+", normalized):
            raise ValueError(f"Invalid assistant_id {assistant_id!r}: must contain only letters, digits, and hyphens after normalization.")
        context_target = config.setdefault("context", {})
        configurable_target = config.setdefault("configurable", {"thread_id": thread_id})
        if not isinstance(context_target, dict) or not isinstance(configurable_target, dict):
            raise TypeError("run config containers must be mappings")
        effective_agent_name = context_target.get("agent_name") or configurable_target.get("agent_name") or normalized
        context_target["agent_name"] = effective_agent_name
        configurable_target["agent_name"] = effective_agent_name
        config.setdefault("run_name", resolve_root_run_name(config, normalized))
    if metadata:
        merged_metadata = dict(config.get("metadata") or {})
        merged_metadata.update(metadata)
        config["metadata"] = merged_metadata
    config["recursion_limit"] = _clamp_recursion_limit(
        config.get("recursion_limit"),
        _resolve_max_recursion_limit(),
    )
    return config


def build_checkpoint_state_mutation_accessor(
    request: Request,
    *,
    thread_id: str,
    as_node: str,
    checkpoint_id: str | None = None,
    state_schema: Any | None = None,
) -> tuple[CheckpointStateAccessor, dict[str, Any]]:
    """Build a state-only graph whose writer node finishes immediately.

    ``state_schema`` should be the thread's effective schema (from
    :func:`graph_state_schema` on the assistant graph) whenever the write
    carries materialized state; with the base-schema fallback, channels
    contributed by custom middleware are silently discarded.
    """
    mode = getattr(request.app.state, "checkpoint_channel_mode", "full")
    config: dict[str, Any] = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
        }
    }
    if checkpoint_id is not None:
        config["configurable"]["checkpoint_id"] = checkpoint_id
    inject_checkpoint_mode(config, mode)

    graph = build_state_mutation_graph(as_node, mode, state_schema)
    accessor = CheckpointStateAccessor.bind(
        graph,
        get_checkpointer(request),
        store=getattr(request.app.state, "store", None),
        mode=mode,
    )
    return accessor, config


# Cache of factory-built accessor graphs. Accessor operations (aget_state /
# aupdate_state) never execute graph nodes or middleware, so per-request
# variations (user, model, skills) cannot affect materialization semantics;
# the compiled graph is stable per (assistant_id, mode, app_config). The
# factory and app_config identities are re-validated on every call so patched
# factories take effect immediately and a config.yaml hot-reload (which
# rebuilds the AppConfig object) never serves a stale compiled graph — the
# cached reference keeps the old config alive, so id-reuse cannot produce a
# false hit. Bounded: cleared when too many distinct assistants appear.
_STATE_ACCESSOR_GRAPH_CACHE_MAX = 64
_state_accessor_graph_cache: dict[tuple[str | None, str], tuple[Any, Any, Any]] = {}


def _state_accessor_graph(agent_factory: Any, assistant_id: str | None, mode: str, config: dict[str, Any]) -> Any:
    app_config = (config.get("context") or {}).get("app_config")
    key = (assistant_id, mode)
    cached = _state_accessor_graph_cache.get(key)
    if cached is not None and cached[0] is agent_factory and cached[1] is app_config:
        return cached[2]
    if len(_state_accessor_graph_cache) >= _STATE_ACCESSOR_GRAPH_CACHE_MAX:
        _state_accessor_graph_cache.clear()
    graph = agent_factory(config=config)
    _state_accessor_graph_cache[key] = (agent_factory, app_config, graph)
    return graph


class _RawCheckpointSnapshot:
    """StateSnapshot-shaped view over a raw checkpoint tuple (full mode only).

    ``next``/``tasks`` are not derivable without the compiled graph and
    degrade to empty; everything the read endpoints serialize (values,
    metadata, config ancestry, created_at) comes straight from the tuple.
    """

    __slots__ = ("config", "values", "metadata", "parent_config", "created_at", "tasks", "tasks_known", "next")

    def __init__(self, config: dict[str, Any], tup: Any | None) -> None:
        self.config = getattr(tup, "config", None) or config
        checkpoint = getattr(tup, "checkpoint", None) or {}
        self.values = dict(checkpoint.get("channel_values") or {})
        self.metadata = dict(getattr(tup, "metadata", None) or {})
        self.parent_config = getattr(tup, "parent_config", None)
        self.created_at = checkpoint.get("ts") or self.metadata.get("created_at", "")
        self.tasks: tuple = ()
        self.tasks_known = False
        self.next: tuple = ()


class _RawCheckpointReadAccessor:
    """Degraded full-mode read accessor for when the agent factory is down.

    Full-mode checkpoints persist complete ``channel_values``, so reads do not
    need the compiled graph. The fail-closed delta gate still applies: delta
    checkpoints are rejected with :class:`CheckpointModeMismatchError` instead
    of being served as partial state. Writes are unsupported — mutation paths
    keep using the graph-backed accessor.
    """

    def __init__(self, checkpointer: Any, mode: str) -> None:
        self.checkpointer = checkpointer
        self.mode = mode

    @staticmethod
    def _gate(tup: Any) -> None:
        if checkpoint_tuple_uses_delta(tup):
            raise CheckpointModeMismatchError("Thread requires delta mode; materialize and convert its checkpoints before using full mode.")

    async def aget(self, config: dict[str, Any]) -> _RawCheckpointSnapshot:
        tup = await self.checkpointer.aget_tuple(config)
        self._gate(tup)
        return _RawCheckpointSnapshot(config, tup)

    async def ahistory(self, config: dict[str, Any], *, limit: int | None = None) -> list[_RawCheckpointSnapshot]:
        if limit is not None and limit <= 0:
            return []
        result: list[_RawCheckpointSnapshot] = []
        before = None
        walk_config = config
        if config.get("configurable", {}).get("checkpoint_id"):
            # Pregel's get_state_history treats config.checkpoint_id as the
            # inclusive start of the walk, while alist(before=...) is
            # exclusive — fetch the anchor explicitly so the degraded path
            # matches the graph path.
            before = config
            walk_config = {
                **config,
                "configurable": {k: v for k, v in config.get("configurable", {}).items() if k != "checkpoint_id"},
            }
            anchor = await self.checkpointer.aget_tuple(before)
            self._gate(anchor)
            if anchor is not None:
                result.append(_RawCheckpointSnapshot(config, anchor))
        if limit is None or len(result) < limit:
            remaining = None if limit is None else limit - len(result)
            async for tup in self.checkpointer.alist(walk_config, before=before, limit=remaining):
                self._gate(tup)
                result.append(_RawCheckpointSnapshot(config, tup))
                if limit is not None and len(result) >= limit:
                    break
        return result


def build_checkpoint_state_accessor(
    request: Request,
    *,
    thread_id: str,
    assistant_id: str | None = None,
    checkpoint_id: str | None = None,
) -> tuple[CheckpointStateAccessor, dict[str, Any]]:
    """Build the mode-selected lead graph used for materialized checkpoint state."""
    ctx = get_run_context(request)
    config = build_run_config(thread_id, None, None, assistant_id=assistant_id)
    configurable = config.setdefault("configurable", {})
    configurable["checkpoint_ns"] = ""
    if checkpoint_id is not None:
        configurable["checkpoint_id"] = checkpoint_id

    if ctx.app_config is not None:
        config.setdefault("context", {})["app_config"] = ctx.app_config
    inject_checkpoint_mode(config, ctx.checkpoint_channel_mode)

    agent_factory = resolve_agent_factory(assistant_id)
    try:
        graph = _state_accessor_graph(agent_factory, assistant_id, ctx.checkpoint_channel_mode, config)
    except Exception:
        if ctx.checkpoint_channel_mode != "full":
            # Delta materialization needs the graph's channel table; there is
            # no degraded path. Surface the factory failure as-is.
            raise
        # Full-mode checkpoints carry complete channel_values: degrade to raw
        # checkpointer reads so state endpoints survive a broken agent factory
        # (bad model config, MCP server down, misconfigured skill).
        logger.warning(
            "Agent factory unavailable for thread %s; falling back to raw checkpointer reads",
            thread_id,
            exc_info=True,
        )
        return _RawCheckpointReadAccessor(ctx.checkpointer, ctx.checkpoint_channel_mode), config
    accessor = CheckpointStateAccessor.bind(
        graph,
        ctx.checkpointer,
        store=ctx.store,
        mode=ctx.checkpoint_channel_mode,
    )
    return accessor, config


async def resolve_thread_assistant_id(
    request: Request,
    thread_id: str,
    *,
    fail_closed: bool = False,
) -> str | None:
    """Return the assistant_id recorded in thread metadata, or ``None``.

    Missing records degrade to ``None`` (the default lead agent). Store
    failures do the same for read callers, while mutation callers set
    ``fail_closed`` so they cannot compile a write graph with the wrong schema.
    """
    from app.gateway.deps import get_thread_store

    try:
        thread_store = get_thread_store(request)
        record = await thread_store.get(thread_id)
    except Exception:
        logger.warning("Failed to resolve assistant_id for thread %s", thread_id, exc_info=True)
        if fail_closed:
            raise
        return None
    return record.get("assistant_id") if isinstance(record, dict) else None


async def build_thread_checkpoint_state_accessor(
    request: Request,
    *,
    thread_id: str,
    checkpoint_id: str | None = None,
    fail_closed: bool = False,
) -> tuple[CheckpointStateAccessor, dict[str, Any]]:
    """Single resolution boundary for state endpoints.

    Thread metadata -> assistant_id -> effective assistant graph. Materializing
    with the default lead schema would drop channels contributed by a custom
    ``AgentMiddleware.state_schema`` from the response.
    """
    assistant_id = await resolve_thread_assistant_id(request, thread_id, fail_closed=fail_closed)
    return build_checkpoint_state_accessor(
        request,
        thread_id=thread_id,
        assistant_id=assistant_id,
        checkpoint_id=checkpoint_id,
    )


async def build_thread_checkpoint_state_mutation_accessor(
    request: Request,
    *,
    thread_id: str,
    as_node: str,
    checkpoint_id: str | None = None,
) -> tuple[CheckpointStateAccessor, dict[str, Any]]:
    """Mutation accessor compiled with the thread's effective state schema.

    Derives the schema through :func:`build_thread_checkpoint_state_accessor`
    so writes carrying materialized state do not silently discard
    extension-owned channels.
    """
    read_accessor, _read_config = await build_thread_checkpoint_state_accessor(
        request,
        thread_id=thread_id,
        checkpoint_id=checkpoint_id,
        fail_closed=True,
    )
    state_schema = graph_state_schema(getattr(read_accessor, "graph", None))
    return build_checkpoint_state_mutation_accessor(
        request,
        thread_id=thread_id,
        as_node=as_node,
        checkpoint_id=checkpoint_id,
        state_schema=state_schema,
    )


async def apply_checkpoint_to_run_config(
    config: dict[str, Any],
    *,
    body: Any,
    thread_id: str,
    request: Request,
) -> None:
    """Validate a requested checkpoint and attach its server-owned fields."""

    checkpoint = getattr(body, "checkpoint", None)
    checkpoint_id = getattr(body, "checkpoint_id", None)
    checkpoint_ns = ""
    checkpoint_map = None
    if checkpoint:
        if not isinstance(checkpoint, Mapping):
            raise HTTPException(status_code=400, detail="checkpoint must be an object")
        checkpoint_thread_id = checkpoint.get("thread_id")
        if checkpoint_thread_id is not None and str(checkpoint_thread_id) != thread_id:
            raise HTTPException(status_code=400, detail="checkpoint thread_id does not match request thread_id")
        if checkpoint.get("checkpoint_id"):
            checkpoint_id = str(checkpoint["checkpoint_id"])
        if checkpoint.get("checkpoint_ns") is not None:
            checkpoint_ns = str(checkpoint["checkpoint_ns"])
        checkpoint_map = checkpoint.get("checkpoint_map")

    if not checkpoint_id:
        return

    read_config: dict[str, Any] = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": str(checkpoint_id),
        }
    }
    if checkpoint_map is not None:
        read_config["configurable"]["checkpoint_map"] = checkpoint_map
    try:
        checkpoint_tuple = await get_checkpointer(request).aget_tuple(read_config)
    except Exception as exc:
        logger.exception("Failed to validate checkpoint %s for thread %s", checkpoint_id, sanitize_log_param(thread_id))
        raise HTTPException(status_code=500, detail="Failed to validate checkpoint") from exc
    if checkpoint_tuple is None:
        raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} not found")

    configurable = config.setdefault("configurable", {})
    if not isinstance(configurable, dict):
        raise HTTPException(status_code=400, detail="request config configurable must be an object")
    configurable.update(
        {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": str(checkpoint_id),
        }
    )
    if checkpoint_map is not None:
        configurable["checkpoint_map"] = checkpoint_map


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------


async def _resolve_canonical_alias(assistant_id: str | None, request: Request) -> str | None:
    """Resolve a legacy-name assistant through the catalog alias resolver.

    Legacy owner-directory reads are sealed, so names must map to an active
    catalog resource — owner-first, then a unique visible shared resource.
    Unknown names (404) and ambiguous names (409) fail closed instead of
    leaking legacy behavior. The default assistant is preserved and returns
    ``None``.
    """

    if not assistant_id or assistant_id == _DEFAULT_ASSISTANT_ID:
        return None

    user_id = getattr(getattr(request.state, "user", None), "id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    from sqlalchemy import select

    from app.agentplatform.rbac_models import UserModel
    from app.agentplatform.resource_service import (
        ResourceAction,
        ResourceActor,
        ResourceConflict,
        ResourceNotFound,
        ResourcePermissionDenied,
        ResourceService,
    )
    from deerflow.persistence.engine import get_session_factory

    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Resource persistence is unavailable")
    try:
        # T2: reuse the identity _authenticate already resolved instead of
        # issuing a duplicate UserModel SELECT on every first turn.
        cached = _cached_rbac_identity(request, str(user_id))
        async with session_factory() as session:
            if cached is not None:
                actor = ResourceActor(
                    user_id=cached["user_id"],
                    department_id=cached["department_id"],
                    role=cached["role"],
                    permissions=frozenset({ResourceAction.READ, ResourceAction.USE}),
                    tool_groups=None,
                )
            else:
                user = (
                    await session.execute(
                        select(UserModel).where(
                            UserModel.id == str(user_id),
                            UserModel.disabled.is_not(True),
                        )
                    )
                ).scalar_one_or_none()
                if user is None:
                    raise ResourcePermissionDenied("Active RBAC user is required")
                actor = ResourceActor(
                    user_id=str(user.id),
                    department_id=str(user.department_id) if user.department_id is not None else None,
                    role=str(user.role),
                    permissions=frozenset({ResourceAction.READ, ResourceAction.USE}),
                    tool_groups=None,
                )
            resource = await ResourceService(session, actor).resolve_legacy_alias("agent", assistant_id)
        return resource.id
    except ResourceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ResourcePermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ResourceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def start_run(
    body: Any,
    thread_id: str,
    request: Request,
    *,
    idempotency_key: str | None = None,
) -> RunRecord:
    """Create a RunRecord and launch the background agent task.

    Parameters
    ----------
    body : RunCreateRequest
        The validated request body (typed as Any to avoid circular import
        with the router module that defines the Pydantic model).
    thread_id : str
        Target thread.
    request : Request
        FastAPI request — used to retrieve singletons from ``app.state``.
    """
    bridge = get_stream_bridge(request)
    run_mgr = get_run_manager(request)
    run_ctx = get_run_context(request)

    disconnect = DisconnectMode.cancel if body.on_disconnect == "cancel" else DisconnectMode.continue_

    # Deep module owns evidence/manifest/alias parallelism and snapshot freeze.
    from app.gateway.run_preparation import discard_canonical_snapshot, prepare_run

    prepared = await prepare_run(body, thread_id, request)
    body_context = prepared.body_context
    canonical_run_id = prepared.canonical_run_id
    canonical_factory = prepared.canonical_factory
    model_name = prepared.model_name
    run_metadata = prepared.run_metadata

    try:
        create_kwargs = {
            "on_disconnect": disconnect,
            "metadata": run_metadata,
            "kwargs": {"input": body.input, "config": body.config},
            "multitask_strategy": body.multitask_strategy,
            "model_name": model_name,
        }
        if canonical_run_id:
            create_kwargs["run_id"] = canonical_run_id
        if idempotency_key is not None:
            create_kwargs["idempotency_key"] = idempotency_key
        record = await run_mgr.create_or_reject(thread_id, body.assistant_id, **create_kwargs)
    except ConflictError as exc:
        await discard_canonical_snapshot(canonical_run_id)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except UnsupportedStrategyError as exc:
        await discard_canonical_snapshot(canonical_run_id)
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except BaseException:
        await discard_canonical_snapshot(canonical_run_id)
        raise

    # Upsert thread metadata so the thread appears in /threads/search,
    # even for threads that were never explicitly created via POST /threads
    # (e.g. stateless runs).
    # T2: runs in the background — thread listing freshness must not block
    # the first token. Failures were and remain non-fatal (warning only).
    async def _upsert_thread_meta() -> None:
        try:
            existing = await run_ctx.thread_store.get(thread_id)
            if existing is None:
                await run_ctx.thread_store.create(
                    thread_id,
                    assistant_id=body.assistant_id,
                    metadata=run_metadata,
                )
            else:
                await run_ctx.thread_store.update_status(thread_id, "running")
        except Exception:
            logger.warning("Failed to upsert thread_meta for %s (non-fatal)", sanitize_log_param(thread_id))

    _upsert_task = asyncio.create_task(_upsert_thread_meta())

    agent_factory = canonical_factory or resolve_agent_factory(body.assistant_id)
    graph_input = normalize_input(body.input)
    config = build_run_config(thread_id, body.config, body.metadata, assistant_id=body.assistant_id)
    await apply_checkpoint_to_run_config(config, body=body, thread_id=thread_id, request=request)

    if canonical_run_id:
        for container_name in ("context", "configurable"):
            container = config.setdefault(container_name, {})
            if isinstance(container, dict):
                container["canonical_run_id"] = canonical_run_id

    # Merge iDeer-specific context overrides into both ``configurable`` and ``context``.
    # The ``context`` field is a custom extension for the langgraph-compat layer
    # that carries agent configuration (model_name, thinking_enabled, etc.).
    # Only agent-relevant keys are forwarded; unknown keys (e.g. thread_id) are ignored.
    is_internal_caller = getattr(getattr(request, "state", None), "auth_source", None) == AUTH_SOURCE_INTERNAL
    merge_run_context_overrides(config, body_context, internal=is_internal_caller)
    if not is_internal_caller:
        strip_internal_context_keys(config)
    inject_authenticated_user_context(config, request, request_context=body_context)

    stream_modes = normalize_stream_modes(body.stream_mode)

    # T5: retrieve the Memory warmer as late as possible for maximum overlap
    # with the work above. It is done by now in the common case (instant
    # await); a slow disk degrades to the status quo, never to a failed Run.
    if prepared.memory_preload_task is not None:
        try:
            await prepared.memory_preload_task
        except Exception:
            logger.debug("Memory preload did not complete for %s (non-fatal)", sanitize_log_param(thread_id))

    run_evidence_binding = getattr(prepared, "evidence_binding", None)

    async def _execute_run() -> None:
        await run_agent(
            bridge,
            run_mgr,
            record,
            ctx=run_ctx,
            agent_factory=agent_factory,
            graph_input=graph_input,
            config=config,
            stream_modes=stream_modes,
            stream_subgraphs=body.stream_subgraphs,
            interrupt_before=body.interrupt_before,
            interrupt_after=body.interrupt_after,
        )

    if run_evidence_binding is not None:
        from agentplatform_extension.evidence import bind_run_evidence

        with bind_run_evidence(run_evidence_binding):
            task = asyncio.create_task(_execute_run())
    else:
        task = asyncio.create_task(_execute_run())
    record.task = task

    # Title sync is handled by worker.py's finally block which reads the
    # title from the checkpoint and calls thread_store.update_display_name
    # after the run completes.

    return record


def _resolve_scheduler_recursion_limit() -> int:
    """Resolve and clamp the live scheduler recursion setting per dispatch."""

    try:
        scheduler = getattr(get_app_config(), "scheduler", None)
        configured = int(getattr(scheduler, "recursion_limit", _DEFAULT_RECURSION_LIMIT))
        ceiling = _resolve_max_recursion_limit()
        if configured > ceiling:
            logger.warning(
                "scheduler.recursion_limit %s exceeds max_recursion_limit %s; clamping",
                configured,
                ceiling,
            )
        return _clamp_recursion_limit(configured, ceiling)
    except Exception:
        logger.warning("failed to load app config; falling back to recursion_limit=%s", _DEFAULT_RECURSION_LIMIT)
        return _DEFAULT_RECURSION_LIMIT


async def launch_scheduled_thread_run(
    *,
    thread_id: str,
    assistant_id: str | None,
    prompt: str,
    request: Request | None = None,
    app: Any | None = None,
    owner_user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Launch one scheduler occurrence through the normal Run admission seam."""

    if metadata and "auth_token" in metadata:
        raise HTTPException(status_code=422, detail="legacy auth_token is unsupported; use config.context.secrets")
    if request is None:
        if app is None:
            raise ValueError("launch_scheduled_thread_run requires request or app")
        request = SimpleNamespace(
            app=app,
            headers=({INTERNAL_OWNER_USER_ID_HEADER_NAME: owner_user_id} if owner_user_id else {}),
            state=SimpleNamespace(user=get_internal_user(), auth_source=AUTH_SOURCE_INTERNAL),
            cookies={},
        )

    # Keep the HTTP router's validated model for compatibility with callers
    # that pass scheduled bodies through the same request boundary.
    from app.gateway.routers.thread_runs import RunCreateRequest

    body = RunCreateRequest(
        assistant_id=assistant_id,
        input={"messages": [{"role": "user", "content": prompt}]},
        metadata=metadata or {},
        config={"recursion_limit": _resolve_scheduler_recursion_limit()},
        context={"non_interactive": True, **({"user_id": owner_user_id} if owner_user_id else {})},
    )
    # Scheduler runs never request temporary-thread cleanup; keep the
    # internal launch contract explicit even while the legacy HTTP model
    # defaults this field to ``keep``.
    body.on_completion = None
    scheduled_task_run_id = (metadata or {}).get("scheduled_task_run_id")
    idempotency_key = f"scheduled-task:{scheduled_task_run_id}" if isinstance(scheduled_task_run_id, str) else None
    with ensure_trace_context():
        record = await start_run(body, thread_id, request, idempotency_key=idempotency_key)
    return {"run_id": record.run_id, "thread_id": record.thread_id}


async def sse_consumer(
    bridge: StreamBridge,
    record: RunRecord,
    request: Request,
    run_mgr: RunManager,
):
    """Async generator that yields SSE frames from the bridge.

    The ``finally`` block implements ``on_disconnect`` semantics:
    - ``cancel``: abort the background task on client disconnect.
    - ``continue``: let the task run; events are discarded.
    """
    last_event_id = request.headers.get("Last-Event-ID")
    try:
        async for entry in bridge.subscribe(record.run_id, last_event_id=last_event_id):
            if await request.is_disconnected():
                break

            if entry is HEARTBEAT_SENTINEL:
                yield ": heartbeat\n\n"
                continue

            if entry is END_SENTINEL:
                yield format_sse("end", None, event_id=entry.id or None)
                return

            yield format_sse(entry.event, entry.data, event_id=entry.id or None)

    finally:
        if record.status in (RunStatus.pending, RunStatus.running):
            if record.on_disconnect == DisconnectMode.cancel:
                await run_mgr.cancel(record.run_id)
