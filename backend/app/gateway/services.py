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
from typing import Any

from fastapi import HTTPException, Request
from langchain_core.messages import BaseMessage
from langchain_core.messages.utils import convert_to_messages

from app.gateway.canonical_agent_run_preparation import (
    prepare_canonical_agent_run as _prepare_canonical_agent_run,
)
from app.gateway.deps import get_run_context, get_run_manager, get_stream_bridge
from app.gateway.utils import sanitize_log_param
from ideer.config.app_config import get_app_config
from ideer.runtime import (
    END_SENTINEL,
    HEARTBEAT_SENTINEL,
    ConflictError,
    DisconnectMode,
    RunManager,
    RunRecord,
    RunStatus,
    StreamBridge,
    UnsupportedStrategyError,
    run_agent,
)
from ideer.runtime.runs.naming import resolve_root_run_name

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
    }
)


def merge_run_context_overrides(config: dict[str, Any], context: Mapping[str, Any] | None) -> None:
    """Merge whitelisted keys from ``body.context`` into both ``config['configurable']``
    and ``config['context']`` so they are visible to legacy configurable readers and
    to LangGraph ``ToolRuntime.context`` consumers (e.g. the ``setup_agent`` tool —
    see issue #2677)."""
    if not context:
        return
    configurable = config.setdefault("configurable", {})
    runtime_context = config.setdefault("context", {})
    for key in _CONTEXT_CONFIGURABLE_KEYS:
        if key in context:
            if isinstance(configurable, dict):
                configurable.setdefault(key, context[key])
            if isinstance(runtime_context, dict):
                runtime_context.setdefault(key, context[key])


def inject_authenticated_user_context(config: dict[str, Any], request: Request) -> None:
    """Stamp the authenticated user into the run context for background tools.

    Tool execution may happen after the request handler has returned, so tools
    that persist user-scoped files should not rely only on ambient ContextVars.
    The value comes from server-side auth state, never from client context.
    """

    user = getattr(request.state, "user", None)
    user_id = getattr(user, "id", None)
    if user_id is None:
        return

    runtime_context = config.setdefault("context", {})
    if isinstance(runtime_context, dict):
        runtime_context["user_id"] = str(user_id)


def resolve_agent_factory(assistant_id: str | None):
    """Resolve the agent factory callable from config.

    Custom agents are implemented as ``lead_agent`` + an ``agent_name``
    injected into ``configurable`` or ``context`` — see
    :func:`build_run_config`.  All ``assistant_id`` values therefore map to the
    same factory; the routing happens inside ``make_lead_agent`` when it reads
    ``cfg["agent_name"]``.
    """
    from ideer.agents.lead_agent.agent import make_lead_agent

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

    from ideer.persistence.engine import get_session_factory
    from ideer.persistence.models.resource_catalog import Resource, ResourceVersion, RunResourceSnapshot

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

    from ideer.persistence.engine import get_session_factory
    from ideer.persistence.models.resource_catalog import RunResourceSnapshot

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
            config["context"] = context
        else:
            configurable = {"thread_id": thread_id}
            configurable.update(request_config.get("configurable", {}))
            config["configurable"] = configurable
        for k, v in request_config.items():
            if k not in ("configurable", "context"):
                config[k] = v
    else:
        config["configurable"] = {"thread_id": thread_id}

    # Inject custom agent name when the caller specified a non-default assistant.
    # Honour an explicit agent_name in the active runtime options container.
    if assistant_id and assistant_id != _DEFAULT_ASSISTANT_ID:
        normalized = assistant_id.strip().lower().replace("_", "-")
        if not normalized or not re.fullmatch(r"[a-z0-9-]+", normalized):
            raise ValueError(f"Invalid assistant_id {assistant_id!r}: must contain only letters, digits, and hyphens after normalization.")
        if "configurable" in config:
            target = config["configurable"]
        elif "context" in config:
            target = config["context"]
        else:
            target = config.setdefault("configurable", {})
        if target is not None and "agent_name" not in target:
            target["agent_name"] = normalized
        config.setdefault("run_name", resolve_root_run_name(config, normalized))
    if metadata:
        config.setdefault("metadata", {}).update(metadata)
    return config


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

    from ideer.persistence.engine import get_session_factory
    from ideer.persistence.models.user import UserModel
    from ideer.resources.service import (
        ResourceAction,
        ResourceActor,
        ResourceConflict,
        ResourceNotFound,
        ResourcePermissionDenied,
        ResourceService,
    )

    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Resource persistence is unavailable")
    try:
        async with session_factory() as session:
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

    body_context = getattr(body, "context", None) or {}
    model_name = body_context.get("model_name")

    canonical_resource_id = _canonical_assistant_id(getattr(body, "assistant_id", None))
    # The workspace and channel manager always send the default assistant id
    # and carry the requested agent in ``context.agent_name``; treat a UUID
    # there as a canonical resource the same way as an assistant_id UUID.
    if canonical_resource_id is None:
        canonical_resource_id = _canonical_assistant_id(body_context.get("agent_name"))
    # Legacy owner-directory reads are sealed: legacy-name assistants
    # resolve through the catalog alias resolver (owner-first, unique
    # visible shared), failing closed when unknown or ambiguous.
    # ``context.agent_name`` takes precedence over assistant_id because it is
    # where the workspace and channels actually carry the requested agent.
    # Bootstrap runs carry the name of the agent being created, which cannot
    # exist in the catalog yet — skip resolution so setup_agent can create it.
    if canonical_resource_id is None and not body_context.get("is_bootstrap"):
        candidate = body_context.get("agent_name") or getattr(body, "assistant_id", None)
        if candidate:
            canonical_resource_id = await _resolve_canonical_alias(candidate, request)

    # Coerce non-string model_name values to str before truncation.
    if model_name is not None and not isinstance(model_name, str):
        model_name = str(model_name)

    # Validate model against the allowlist when a model_name is provided.
    if model_name:
        app_config = get_app_config()
        resolved = app_config.get_model_config(model_name)
        if resolved is None:
            raise HTTPException(
                status_code=400,
                detail=f"Model {model_name!r} is not in the configured model allowlist",
            )

    canonical_run_id = str(uuid.uuid4()) if canonical_resource_id else None
    preferred_skill = body_context.get("skill_resource_id") or body_context.get("skill_name")
    if canonical_resource_id and canonical_run_id:
        prepare_kwargs = {"preferred_skill": preferred_skill} if preferred_skill else {}
        canonical_factory = await _prepare_canonical_agent_run(
            canonical_resource_id,
            request,
            canonical_run_id,
            **prepare_kwargs,
        )
    else:
        canonical_factory = None

    run_metadata = dict(body.metadata or {})
    if canonical_run_id and canonical_resource_id:
        run_metadata.update(await _canonical_selection_metadata(canonical_run_id, canonical_resource_id, body_context))

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
        record = await run_mgr.create_or_reject(thread_id, body.assistant_id, **create_kwargs)
    except ConflictError as exc:
        if canonical_run_id:
            await _discard_canonical_run_snapshot(canonical_run_id)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except UnsupportedStrategyError as exc:
        if canonical_run_id:
            await _discard_canonical_run_snapshot(canonical_run_id)
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except BaseException:
        if canonical_run_id:
            await _discard_canonical_run_snapshot(canonical_run_id)
        raise

    # Upsert thread metadata so the thread appears in /threads/search,
    # even for threads that were never explicitly created via POST /threads
    # (e.g. stateless runs).
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

    agent_factory = canonical_factory or resolve_agent_factory(body.assistant_id)
    graph_input = normalize_input(body.input)
    config = build_run_config(thread_id, body.config, body.metadata, assistant_id=body.assistant_id)

    if canonical_run_id:
        for container_name in ("context", "configurable"):
            container = config.setdefault(container_name, {})
            if isinstance(container, dict):
                container["canonical_run_id"] = canonical_run_id

    # Merge iDeer-specific context overrides into both ``configurable`` and ``context``.
    # The ``context`` field is a custom extension for the langgraph-compat layer
    # that carries agent configuration (model_name, thinking_enabled, etc.).
    # Only agent-relevant keys are forwarded; unknown keys (e.g. thread_id) are ignored.
    merge_run_context_overrides(config, getattr(body, "context", None))
    inject_authenticated_user_context(config, request)

    stream_modes = normalize_stream_modes(body.stream_mode)

    task = asyncio.create_task(
        run_agent(
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
    )
    record.task = task

    # Title sync is handled by worker.py's finally block which reads the
    # title from the checkpoint and calls thread_store.update_display_name
    # after the run completes.

    return record


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
