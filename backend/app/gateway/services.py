"""Run lifecycle service layer.

Centralizes the business logic for creating runs, formatting SSE
frames, and consuming stream bridge events.  Router modules
(``thread_runs``, ``runs``) are thin HTTP handlers that delegate here.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

from deerflow_extension_api import PROVENANCE_KEYS
from fastapi import HTTPException, Request
from langchain_core.messages import BaseMessage
from langchain_core.messages.utils import convert_to_messages
from langgraph.types import Command

# Canonical (Resource-catalog) bootstrap for in-run agent creation. The gateway
# composition owns the enterprise behavior, so the wrap is installed once at
# import — before any lead-agent graph can be assembled in this process.
from app.agentplatform.agent_bootstrap import (
    install as _install_canonical_agent_bootstrap,
)
from app.agentplatform.resources.canonical_sandbox import (
    install_run_skill_view_resolver as _install_run_skill_view_resolver,
)
from app.gateway.auth_disabled import AUTH_SOURCE_INTERNAL
from app.gateway.authz import _cached_rbac_identity
from app.gateway.deps import (
    get_checkpointer,
    get_local_provider,
    get_run_context,
    get_run_manager,
    get_stream_bridge,
)
from app.gateway.internal_auth import (
    INTERNAL_OWNER_USER_ID_HEADER_NAME,
    INTERNAL_SYSTEM_ROLE,
    get_internal_user,
    get_trusted_internal_owner_user_id,
)
from app.gateway.utils import sanitize_log_param
from app.mcp_tasks.errors import PermanentNotificationError
from deerflow.agents.middlewares.dynamic_context_middleware import (
    _DYNAMIC_CONTEXT_REMINDER_KEY,
    _REMINDER_DATE_KEY,
)
from deerflow.agents.middlewares.input_sanitization_middleware import (
    frame_untrusted_text,
)
from deerflow.agents.middlewares.tool_receipt import (
    TOOL_RECEIPT_KEY,
    TOOL_RECEIPT_LEDGER_KEY,
)
from deerflow.agents.middlewares.tool_transform_meta import TOOL_TRANSFORMS_KEY
from deerflow.agents.middlewares.view_image_middleware import (
    _IMAGE_CONTEXT_MESSAGE_MARKER_KEY,
)
from deerflow.config import get_app_config
from deerflow.config.database_config import resolve_checkpoint_graph_cache_max
from deerflow.runtime import (
    END_SENTINEL,
    HEARTBEAT_SENTINEL,
    ORPHAN_RECOVERY_STOP_REASON,
    CheckpointStateAccessor,
    ConflictError,
    DisconnectMode,
    RunContext,
    RunManager,
    RunRecord,
    RunStatus,
    StreamBridge,
    StreamGap,
    ThreadOperationKind,
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
from deerflow.runtime.events.message_identity import MESSAGE_SEQ_KEY
from deerflow.runtime.goal import goal_thread_lock
from deerflow.runtime.journal import build_checkpoint_history_seed_events
from deerflow.runtime.runs.naming import resolve_root_run_name
from deerflow.runtime.secret_context import (
    LegacyRunMetadataSecretError,
    redact_config_secrets,
    validate_run_metadata_secrets,
)
from deerflow.runtime.user_context import reset_current_user, set_current_user
from deerflow.subagents.status_contract import (
    SUBAGENT_ACCEPTANCE_VERDICT_KEY,
    SUBAGENT_RECEIPT_VERDICT_KEY,
    SUBAGENT_TOOL_RECEIPTS_KEY,
)
from deerflow.trace_context import (
    DEERFLOW_TRACE_METADATA_KEY,
    ensure_trace_context,
    ensure_trace_id,
)
from deerflow.utils.messages import ORIGINAL_USER_CONTENT_KEY
from deerflow.utils.thread_id import validate_thread_id

_install_canonical_agent_bootstrap()
# Canonical runs key their sandboxes on a run-scoped identity; teach the
# runtime's local provider to mount the run's frozen read-only skill view.
_install_run_skill_view_resolver()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def reserve_checkpoint_write(
    request: Request,
    thread_id: str,
    *,
    user_id: str | None = None,
) -> AsyncIterator[None]:
    """Serialize an out-of-run checkpoint writer against thread operations."""
    run_manager = get_run_manager(request)
    async with goal_thread_lock(thread_id):
        async with run_manager.reserve_thread_operation(
            thread_id,
            kind=ThreadOperationKind.checkpoint_write,
            user_id=user_id,
        ):
            yield


_THREAD_METADATA_SETUP_TIMEOUT_SECONDS = 5.0
_SERVER_OWNED_MESSAGE_METADATA_KEYS = (
    frozenset(
        {
            _DYNAMIC_CONTEXT_REMINDER_KEY,
            _REMINDER_DATE_KEY,
            _IMAGE_CONTEXT_MESSAGE_MARKER_KEY,
            TOOL_RECEIPT_KEY,
            TOOL_RECEIPT_LEDGER_KEY,
            TOOL_TRANSFORMS_KEY,
            SUBAGENT_TOOL_RECEIPTS_KEY,
            SUBAGENT_RECEIPT_VERDICT_KEY,
            SUBAGENT_ACCEPTANCE_VERDICT_KEY,
        }
    )
    | PROVENANCE_KEYS
)


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
    modes = [raw] if isinstance(raw, str) else (raw if raw else ["values"])
    supported = {"values", "messages-tuple", "updates", "custom"}
    unsupported = [mode for mode in modes if mode not in supported]
    if unsupported:
        raise ValueError(f"Unsupported stream mode: {unsupported[0]}")
    return modes


def _strip_external_message_metadata(message: Any) -> Any:
    if isinstance(message, dict) and isinstance(message.get("additional_kwargs"), dict):
        additional_kwargs = {
            key: value
            for key, value in message["additional_kwargs"].items()
            if key != ORIGINAL_USER_CONTENT_KEY
            and key != MESSAGE_SEQ_KEY
            and key not in _SERVER_OWNED_MESSAGE_METADATA_KEYS
        }
        return {**message, "additional_kwargs": additional_kwargs}
    if not isinstance(message, BaseMessage):
        return message
    additional_kwargs = dict(message.additional_kwargs)
    additional_kwargs.pop(ORIGINAL_USER_CONTENT_KEY, None)
    additional_kwargs.pop(MESSAGE_SEQ_KEY, None)
    for key in _SERVER_OWNED_MESSAGE_METADATA_KEYS:
        additional_kwargs.pop(key, None)
    if additional_kwargs == message.additional_kwargs:
        return message
    return message.model_copy(update={"additional_kwargs": additional_kwargs})


def _strip_external_delegation_verdict(entry: Any) -> Any:
    if isinstance(entry, dict):
        return {
            key: value
            for key, value in entry.items()
            if key not in {"receipt_verdict", "acceptance_verdict"}
        }
    return entry


def normalize_input(
    raw_input: dict[str, Any] | None, *, trusted_internal: bool = False
) -> dict[str, Any]:
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
        if not trusted_internal:
            converted = [
                _strip_external_message_metadata(message) for message in converted
            ]
        result = {**raw_input, "messages": converted}
    else:
        result = raw_input
    if not trusted_internal and isinstance(result.get("delegations"), list):
        result = {
            **result,
            "delegations": [
                _strip_external_delegation_verdict(item)
                for item in result["delegations"]
            ],
        }
    return result


def strip_server_owned_state_metadata(values: Mapping[str, Any]) -> dict[str, Any]:
    """Strip host-owned metadata from message-like values in every channel."""
    cleaned: dict[str, Any] = {}
    for channel, value in values.items():
        if channel == "delegations" and isinstance(value, list):
            cleaned[channel] = [
                _strip_external_delegation_verdict(item) for item in value
            ]
        elif isinstance(value, list):
            cleaned[channel] = [
                _strip_external_message_metadata(item) for item in value
            ]
        else:
            cleaned[channel] = _strip_external_message_metadata(value)
    return cleaned


def validate_evidence_selection(
    evidence_mode: str | None, code_package_id: str | None
) -> tuple[str, str | None]:
    """Normalize the hidden hybrid mode and validate an optional code package."""
    mode = evidence_mode or "hybrid"
    if mode not in {"document", "code", "hybrid"}:
        raise HTTPException(
            status_code=400, detail="evidence_mode must be document, code, or hybrid"
        )
    if mode == "code" and not code_package_id:
        raise HTTPException(
            status_code=400, detail=f"{mode} mode requires a Code Evidence Package"
        )
    if mode == "document" and code_package_id:
        raise HTTPException(
            status_code=400,
            detail="document mode cannot include a Code Evidence Package",
        )
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
        "max_total_subagents",
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

_CONTEXT_ONLY_KEYS: frozenset[str] = frozenset(
    {"github_token", "disable_clarification"}
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
    keys = (
        _CONTEXT_CONFIGURABLE_KEYS | _CONTEXT_INTERNAL_CALLER_KEYS
        if internal
        else _CONTEXT_CONFIGURABLE_KEYS
    )
    for key in keys:
        if key in context:
            if isinstance(configurable, dict):
                configurable.setdefault(key, context[key])
            if isinstance(runtime_context, dict):
                runtime_context.setdefault(key, context[key])
    if isinstance(runtime_context, dict):
        for key in _CONTEXT_ONLY_KEYS:
            if key in context:
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
    internal_owner_user: Any | None = None,
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

    user = internal_owner_user or getattr(request.state, "user", None)
    user_id = getattr(user, "id", None)
    if user_id is None:
        runtime_context.pop("user_id", None)
        if isinstance(configurable, dict):
            configurable.pop("user_id", None)
        return

    if (
        internal_owner_user is None
        and getattr(user, "system_role", None) == INTERNAL_SYSTEM_ROLE
    ):
        runtime_context.pop("user_role", None)
        runtime_context.pop("oauth_provider", None)
        runtime_context.pop("oauth_id", None)
        return

    runtime_context["user_id"] = str(user_id)
    # The platform identity cache is the only role source. The middleware (or
    # _authenticate) resolves users_ext before handlers run, so the cache is
    # always present here for session/PAT callers; when it is absent (direct
    # embedded calls) the role is omitted rather than falling back to the
    # legacy auth-table value, which would silently re-escalate a downgraded
    # or unprovisioned account.
    cached_identity = getattr(getattr(request, "state", None), "_ideer_rbac_user", None)
    resolved_role = (
        cached_identity.get("role") if isinstance(cached_identity, dict) else None
    )
    # Direct embedded callers and focused contract tests do not pass the
    # middleware's RBAC cache. Preserve the authenticated user's role there;
    # requests that went through middleware always use the server-resolved
    # cache above.
    if resolved_role is None and cached_identity is None and auth_source is None:
        resolved_role = getattr(user, "system_role", None)
    if resolved_role is None and internal_owner_user is not None:
        resolved_role = getattr(internal_owner_user, "system_role", None)
    if resolved_role is not None:
        runtime_context["user_role"] = resolved_role
    runtime_context["oauth_provider"] = getattr(user, "oauth_provider", None)
    runtime_context["oauth_id"] = getattr(user, "oauth_id", None)
    department_id = (
        cached_identity.get("department_id")
        if isinstance(cached_identity, dict)
        else None
    )
    if department_id is not None:
        runtime_context["authz_attributes"] = {"department_id": str(department_id)}


async def resolve_trusted_internal_owner_for_attribution(
    request: Request, owner_user_id: str | None
) -> Any | None:
    if not owner_user_id:
        return None
    user = getattr(request.state, "user", None)
    if getattr(user, "system_role", None) != INTERNAL_SYSTEM_ROLE:
        return None
    try:
        return await get_local_provider().get_user(owner_user_id)
    except Exception:
        logger.exception(
            "Failed to resolve trusted internal owner %s",
            sanitize_log_param(owner_user_id),
        )
        return None


def resolve_agent_factory(assistant_id: str | None):
    """Resolve the agent factory callable from config.

    Custom agents are implemented as ``lead_agent`` + an ``agent_name``
    injected into ``configurable`` or ``context`` — see
    :func:`build_run_config`.  All ``assistant_id`` values therefore map to the
    same factory; the routing happens inside ``make_lead_agent`` when it reads
    ``cfg["agent_name"]``.
    """
    from deerflow.agents.lead_agent.agent import assemble_lead_agent

    return assemble_lead_agent


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

    from app.agentplatform.resource_models import (
        Resource,
        ResourceVersion,
        RunResourceSnapshot,
    )
    from deerflow.persistence.engine import get_session_factory

    session_factory = get_session_factory()
    if session_factory is None:
        return {}
    async with session_factory() as session:
        rows = list(
            (
                await session.execute(
                    select(Resource, ResourceVersion, RunResourceSnapshot)
                    .join(
                        RunResourceSnapshot,
                        RunResourceSnapshot.resource_id == Resource.id,
                    )
                    .outerjoin(
                        ResourceVersion,
                        (ResourceVersion.resource_id == Resource.id)
                        & (ResourceVersion.version == RunResourceSnapshot.version),
                    )
                    .where(RunResourceSnapshot.run_id == run_id)
                )
            ).all()
        )
    by_id = {
        resource.id: (resource, version, snapshot)
        for resource, version, snapshot in rows
    }
    agent, agent_version, agent_snapshot = by_id.get(
        agent_resource_id, (None, None, None)
    )
    if agent is None or (agent_version is None and agent_snapshot is None):
        return {}
    selected_skill = body_context.get("skill_resource_id") or body_context.get(
        "skill_name"
    )
    skill_entry = None
    if selected_skill:
        for resource, version, snapshot in by_id.values():
            if resource.type == "skill" and (
                resource.id == selected_skill or resource.slug == selected_skill
            ):
                if version is None and snapshot is None:
                    continue
                skill_entry = {
                    "resource_id": resource.id,
                    "display_name": resource.display_name,
                    "slug": resource.slug,
                    "version": version.version if version is not None else snapshot.version,
                    "content_hash": (
                        version.content_hash
                        if version is not None
                        else snapshot.content_hash
                    ),
                }
                break
    agent_version_number = (
        agent_version.version if agent_version is not None else agent_snapshot.version
    )
    agent_content_hash = (
        agent_version.content_hash
        if agent_version is not None
        else agent_snapshot.content_hash
    )
    selection: dict[str, Any] = {
        "agent": {
            "resource_id": agent.id,
            "display_name": agent.display_name,
            "slug": agent.slug,
            "version": agent_version_number,
            "content_hash": agent_content_hash,
        },
        "resolved_skill_ids": sorted(
            resource.id
            for resource, _version, _snapshot in by_id.values()
            if resource.type == "skill"
        ),
        "resource_snapshots": [
            {
                "resource_id": snapshot.resource_id,
                "version": snapshot.version,
                "content_hash": snapshot.content_hash,
                "selection_role": snapshot.selection_role,
                **(
                    {
                        "knowledge_revision_id": snapshot.knowledge_revision_id,
                        "knowledge_revision_no": snapshot.knowledge_revision_no,
                        "knowledge_manifest_hash": snapshot.manifest_hash,
                    }
                    if snapshot.knowledge_revision_id
                    else {}
                ),
            }
            for _resource, _version, snapshot in rows
        ],
        "policy_revision": str(
            max(snapshot.authz_revision for _resource, _version, snapshot in rows)
        ),
    }
    if skill_entry is not None:
        selection["preferred_skill"] = skill_entry
    for key in (
        "scenario_id",
        "agent_label",
        "task_id",
        "task_label",
        "prompt_template",
    ):
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
        await session.execute(
            delete(RunResourceSnapshot).where(RunResourceSnapshot.run_id == run_id)
        )
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
                    list((request_config.get("configurable") or {}).keys()),
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
            request_configurable = request_config.get("configurable")
            if isinstance(request_configurable, Mapping):
                configurable.update(request_configurable)
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
            # Double-underscore entries are reserved for server-created
            # runtime state (secret bindings, journals, and policy decisions).
            # Never carry caller-supplied private keys across the gateway
            # boundary; trusted code adds them after authentication.
            for key in list(value):
                if isinstance(key, str) and key.startswith("__"):
                    value.pop(key, None)

    # Inject custom agent name when the caller specified a non-default assistant.
    # Honour an explicit agent_name in the active runtime options container.
    if assistant_id and assistant_id != _DEFAULT_ASSISTANT_ID:
        normalized = assistant_id.strip().lower().replace("_", "-")
        if not normalized or not re.fullmatch(r"[a-z0-9-]+", normalized):
            raise ValueError(
                f"Invalid assistant_id {assistant_id!r}: must contain only letters, digits, and hyphens after normalization."
            )
        context_target = config.setdefault("context", {})
        configurable_target = config.setdefault(
            "configurable", {"thread_id": thread_id}
        )
        if not isinstance(context_target, dict) or not isinstance(
            configurable_target, dict
        ):
            raise TypeError("run config containers must be mappings")
        effective_agent_name = (
            context_target.get("agent_name")
            or configurable_target.get("agent_name")
            or normalized
        )
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
_state_accessor_graph_cache: dict[
    tuple[str | None, str, int | None], tuple[Any, Any, Any]
] = {}


def _accessor_graph_cache_max(app_config: Any) -> int:
    return resolve_checkpoint_graph_cache_max(
        getattr(app_config, "database", None),
        "accessor_graph_max",
        _STATE_ACCESSOR_GRAPH_CACHE_MAX,
    )


def _state_accessor_graph(
    agent_factory: Any,
    assistant_id: str | None,
    mode: str,
    snapshot_frequency: int | None,
    config: dict[str, Any],
) -> Any:
    app_config = (config.get("context") or {}).get("app_config")
    key = (assistant_id, mode, snapshot_frequency)
    cached = _state_accessor_graph_cache.get(key)
    if cached is not None and cached[0] is agent_factory and cached[1] is app_config:
        return cached[2]
    if len(_state_accessor_graph_cache) >= _accessor_graph_cache_max(app_config):
        _state_accessor_graph_cache.clear()
    graph = agent_factory(config=config)
    try:
        from deerflow.agents.lead_agent.agent import unwrap_agent_graph

        graph = unwrap_agent_graph(graph)
    except Exception:
        pass
    _state_accessor_graph_cache[key] = (agent_factory, app_config, graph)
    return graph


class _RawCheckpointSnapshot:
    """StateSnapshot-shaped view over a raw checkpoint tuple (full mode only).

    ``next``/``tasks`` are not derivable without the compiled graph and
    degrade to empty; everything the read endpoints serialize (values,
    metadata, config ancestry, created_at) comes straight from the tuple.
    """

    __slots__ = (
        "config",
        "values",
        "metadata",
        "parent_config",
        "created_at",
        "tasks",
        "tasks_known",
        "next",
    )

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
            raise CheckpointModeMismatchError(
                "Thread requires delta mode; materialize and convert its checkpoints before using full mode."
            )

    async def aget(self, config: dict[str, Any]) -> _RawCheckpointSnapshot:
        tup = await self.checkpointer.aget_tuple(config)
        self._gate(tup)
        return _RawCheckpointSnapshot(config, tup)

    async def ahistory(
        self, config: dict[str, Any], *, limit: int | None = None
    ) -> list[_RawCheckpointSnapshot]:
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
                "configurable": {
                    k: v
                    for k, v in config.get("configurable", {}).items()
                    if k != "checkpoint_id"
                },
            }
            anchor = await self.checkpointer.aget_tuple(before)
            self._gate(anchor)
            if anchor is not None:
                result.append(_RawCheckpointSnapshot(config, anchor))
        if limit is None or len(result) < limit:
            remaining = None if limit is None else limit - len(result)
            async for tup in self.checkpointer.alist(
                walk_config, before=before, limit=remaining
            ):
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
        graph = _state_accessor_graph(
            agent_factory,
            assistant_id,
            ctx.checkpoint_channel_mode,
            getattr(ctx, "snapshot_frequency", None),
            config,
        )
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
        return _RawCheckpointReadAccessor(
            ctx.checkpointer, ctx.checkpoint_channel_mode
        ), config
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
        logger.warning(
            "Failed to resolve assistant_id for thread %s", thread_id, exc_info=True
        )
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
    assistant_id = await resolve_thread_assistant_id(
        request, thread_id, fail_closed=fail_closed
    )
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
            raise HTTPException(
                status_code=400,
                detail="checkpoint thread_id does not match request thread_id",
            )
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
        logger.exception(
            "Failed to validate checkpoint %s for thread %s",
            checkpoint_id,
            sanitize_log_param(thread_id),
        )
        raise HTTPException(
            status_code=500, detail="Failed to validate checkpoint"
        ) from exc
    if checkpoint_tuple is None:
        raise HTTPException(
            status_code=404, detail=f"Checkpoint {checkpoint_id} not found"
        )

    configurable = config.setdefault("configurable", {})
    if not isinstance(configurable, dict):
        raise HTTPException(
            status_code=400, detail="request config configurable must be an object"
        )
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


async def _resolve_canonical_alias(
    assistant_id: str | None, request: Request
) -> str | None:
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
        raise HTTPException(
            status_code=503, detail="Resource persistence is unavailable"
        )
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
                    department_id=str(user.department_id)
                    if user.department_id is not None
                    else None,
                    role=str(user.role),
                    permissions=frozenset({ResourceAction.READ, ResourceAction.USE}),
                    tool_groups=None,
                )
            resource = await ResourceService(session, actor).resolve_legacy_alias(
                "agent", assistant_id
            )
        return resource.id
    except ResourceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ResourcePermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ResourceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def ensure_checkpoint_history_seeded(
    request: Request,
    *,
    thread_id: str,
    assistant_id: str | None,
) -> None:
    """Backfill an empty run-event feed from an existing checkpoint head."""
    event_store = request.app.state.run_event_store
    existing_messages = event_store.list_messages(thread_id, limit=1, user_id=None)
    if inspect.isawaitable(existing_messages):
        existing_messages = await existing_messages
    if existing_messages:
        return
    checkpoint_config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    checkpoint = get_checkpointer(request).aget_tuple(checkpoint_config)
    if inspect.isawaitable(checkpoint):
        checkpoint = await checkpoint
    if checkpoint is None:
        return
    accessor, config = build_checkpoint_state_accessor(
        request,
        thread_id=thread_id,
        assistant_id=assistant_id,
    )
    snapshot = await accessor.aget(config)
    values = getattr(snapshot, "values", None)
    messages = values.get("messages") if isinstance(values, dict) else None
    if not isinstance(messages, list) or not messages:
        return
    events = build_checkpoint_history_seed_events(
        messages,
        thread_id=thread_id,
        run_id_prefix=f"checkpoint-seed-{thread_id}",
    )
    if events:
        await event_store.put_batch(events)
        logger.info(
            "Seeded %d checkpoint-history events for thread %s", len(events), thread_id
        )


def _consume_task_result(task: asyncio.Task) -> None:
    if not task.cancelled():
        task.exception()


def _log_thread_metadata_task_result(task: asyncio.Task, *, thread_id: str) -> None:
    if task.cancelled():
        return
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception:
        logger.warning(
            "Failed to ensure thread_meta for %s after worker detached (non-fatal)",
            sanitize_log_param(thread_id),
            exc_info=True,
        )


async def _ensure_thread_metadata(
    run_ctx: RunContext,
    record: RunRecord,
    *,
    owner_user_id: str | None,
    require_existing_thread: bool = False,
    metadata: dict[str, Any] | None = None,
) -> None:
    thread_store = run_ctx.thread_store
    existing = await thread_store.get(record.thread_id)
    if existing is None and owner_user_id:
        unscoped = await thread_store.get(record.thread_id, user_id=None)
        if unscoped is not None:
            if unscoped.get("user_id") != owner_user_id:
                await thread_store.update_owner(
                    record.thread_id, owner_user_id, user_id=None
                )
            existing = await thread_store.get(record.thread_id)
    if existing is None:
        if require_existing_thread:
            raise LookupError(
                f"Thread {record.thread_id} was deleted during run admission"
            )
        await thread_store.create(
            record.thread_id,
            assistant_id=record.assistant_id,
            metadata=record.metadata if metadata is None else metadata,
        )


async def start_run(
    body: Any,
    thread_id: str,
    request: Request,
    *,
    idempotency_key: str | None = None,
    require_existing_thread: bool = False,
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
    try:
        validate_thread_id(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        validate_run_metadata_secrets(getattr(body, "metadata", None))
        config_metadata = (getattr(body, "config", None) or {}).get("metadata")
        validate_run_metadata_secrets(config_metadata)
    except LegacyRunMetadataSecretError as exc:
        raise HTTPException(
            status_code=422,
            detail="legacy auth_token is unsupported; use config.context.secrets",
        ) from exc

    # ``interrupt`` and ``rollback`` can terminate an already-active run.
    # Keep this check at the shared service choke point so stateless routes and
    # internal callers cannot bypass the cancel capability requirement.
    from app.gateway.authz import require_cancel_permission_if

    require_cancel_permission_if(request, body.multitask_strategy != "reject")

    bridge = get_stream_bridge(request)
    run_mgr = get_run_manager(request)
    run_ctx = get_run_context(request)

    disconnect = (
        DisconnectMode.cancel
        if body.on_disconnect == "cancel"
        else DisconnectMode.continue_
    )

    # Deep module owns evidence/manifest/alias parallelism and snapshot freeze.
    from app.gateway.run_preparation import discard_canonical_snapshot, prepare_run

    preparation_started = asyncio.get_running_loop().time()
    trace_id = ensure_trace_id()
    prepared = await prepare_run(body, thread_id, request, trace_id=trace_id)
    logger.info(
        "first_token_timing trace_id=%s stage=run_preparation thread_id=%s run_preparation_ms=%.1f pre_llm_stage=completed",
        trace_id,
        thread_id,
        (asyncio.get_running_loop().time() - preparation_started) * 1000,
    )
    body_context = prepared.body_context
    canonical_run_id = prepared.canonical_run_id
    canonical_factory = prepared.canonical_factory
    model_name = prepared.model_name
    run_metadata = prepared.run_metadata
    if prepared.evidence_mode == "hybrid" and "evidence_mode" not in (
        getattr(body, "metadata", None) or {}
    ):
        run_metadata = {
            key: value for key, value in run_metadata.items() if key != "evidence_mode"
        }
    run_metadata = {**run_metadata, DEERFLOW_TRACE_METADATA_KEY: trace_id}

    owner_user_id = get_trusted_internal_owner_user_id(request)
    if owner_user_id is None:
        owner_user_id = getattr(getattr(request, "state", None), "user", None)
        owner_user_id = getattr(owner_user_id, "id", None)
        if owner_user_id is not None:
            # Session JWTs carry UUID ids; every store column and lookup key
            # is the canonical string form.
            owner_user_id = str(owner_user_id)

    if require_existing_thread:
        if not await run_ctx.thread_store.check_access(
            thread_id, owner_user_id, require_existing=True
        ):
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    # Validate checkpoint admission before the durable run row is created.
    if getattr(body, "command", None) is not None:
        graph_input = Command(**body.command)
    else:
        graph_input = normalize_input(
            body.input,
            trusted_internal=getattr(
                getattr(request, "state", None), "auth_source", None
            )
            == AUTH_SOURCE_INTERNAL,
        )
    config = build_run_config(
        thread_id, body.config, run_metadata, assistant_id=body.assistant_id
    )
    await apply_checkpoint_to_run_config(
        config, body=body, thread_id=thread_id, request=request
    )

    try:
        await ensure_checkpoint_history_seeded(
            request,
            thread_id=thread_id,
            assistant_id=body.assistant_id,
        )
        if require_existing_thread and not await run_ctx.thread_store.check_access(
            thread_id, owner_user_id, require_existing=True
        ):
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        create_kwargs = {
            "on_disconnect": disconnect,
            "metadata": run_metadata,
            "kwargs": {
                "input": body.input,
                "config": redact_config_secrets(body.config),
            },
            "multitask_strategy": body.multitask_strategy,
            "model_name": model_name,
            "user_id": owner_user_id,
        }
        if canonical_run_id:
            create_kwargs["run_id"] = canonical_run_id
        if idempotency_key is not None:
            create_kwargs["idempotency_key"] = idempotency_key
        record = await run_mgr.create_or_reject(
            thread_id, body.assistant_id, **create_kwargs
        )
    except ConflictError as exc:
        await discard_canonical_snapshot(canonical_run_id)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except UnsupportedStrategyError as exc:
        await discard_canonical_snapshot(canonical_run_id)
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except BaseException:
        await discard_canonical_snapshot(canonical_run_id)
        raise

    agent_factory = canonical_factory or resolve_agent_factory(body.assistant_id)
    if canonical_run_id:
        for container_name in ("context", "configurable"):
            container = config.setdefault(container_name, {})
            if isinstance(container, dict):
                container["canonical_run_id"] = canonical_run_id

    # Merge iDeer-specific context overrides into both ``configurable`` and ``context``.
    # The ``context`` field is a custom extension for the langgraph-compat layer
    # that carries agent configuration (model_name, thinking_enabled, etc.).
    # Only agent-relevant keys are forwarded; unknown keys (e.g. thread_id) are ignored.
    is_internal_caller = (
        getattr(getattr(request, "state", None), "auth_source", None)
        == AUTH_SOURCE_INTERNAL
    )
    merge_run_context_overrides(config, body_context, internal=is_internal_caller)
    if not is_internal_caller:
        strip_internal_context_keys(config)
    request_context_values = getattr(body, "config", None) or {}
    needs_owner_attribution = isinstance(
        request_context_values.get("context"), dict
    ) and any(
        key in request_context_values["context"]
        for key in ("user_role", "oauth_provider", "oauth_id", "authz_attributes")
    )
    internal_owner_user = (
        await resolve_trusted_internal_owner_for_attribution(request, owner_user_id)
        if needs_owner_attribution
        else None
    )
    inject_authenticated_user_context(
        config,
        request,
        internal_owner_user=internal_owner_user,
        request_context=body_context,
    )

    stream_modes = normalize_stream_modes(body.stream_mode)

    # T5: retrieve the Memory warmer as late as possible for maximum overlap
    # with the work above. It is done by now in the common case (instant
    # await); a slow disk degrades to the status quo, never to a failed Run.
    if prepared.memory_preload_task is not None:
        try:
            await prepared.memory_preload_task
        except Exception:
            logger.debug(
                "Memory preload did not complete for %s (non-fatal)",
                sanitize_log_param(thread_id),
            )

    run_evidence_binding = getattr(prepared, "evidence_binding", None)
    if run_evidence_binding is not None and run_evidence_binding.run_id is None:
        from dataclasses import replace

        run_evidence_binding = replace(run_evidence_binding, run_id=record.run_id)

    async def _execute_run() -> None:
        metadata_task = asyncio.create_task(
            _ensure_thread_metadata(
                run_ctx,
                record,
                owner_user_id=owner_user_id,
                require_existing_thread=require_existing_thread,
                metadata=getattr(body, "metadata", None) or {},
            )
        )
        abort_task = asyncio.create_task(record.abort_event.wait())
        metadata_failure: Exception | None = None
        metadata_failure_logged = False
        try:
            done, _ = await asyncio.wait(
                (metadata_task, abort_task),
                timeout=_THREAD_METADATA_SETUP_TIMEOUT_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if metadata_task in done:
                try:
                    metadata_task.result()
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    metadata_failure = exc
                    metadata_failure_logged = True
                    logger.warning(
                        "Failed to ensure thread_meta for %s%s",
                        sanitize_log_param(thread_id),
                        "" if require_existing_thread else " (non-fatal)",
                        exc_info=True,
                    )
            elif abort_task not in done:
                logger.warning(
                    "Timed out ensuring thread_meta for %s after %.1fs",
                    sanitize_log_param(thread_id),
                    _THREAD_METADATA_SETUP_TIMEOUT_SECONDS,
                )
                if require_existing_thread:
                    metadata_failure = TimeoutError(
                        "Timed out verifying existing thread metadata"
                    )
        finally:
            if metadata_task.done():
                if not metadata_failure_logged:
                    _log_thread_metadata_task_result(metadata_task, thread_id=thread_id)
            else:
                metadata_task.cancel()
                metadata_task.add_done_callback(
                    lambda task: _log_thread_metadata_task_result(
                        task, thread_id=thread_id
                    )
                )
            if not abort_task.done():
                abort_task.cancel()
                abort_task.add_done_callback(_consume_task_result)
        if metadata_failure is not None and require_existing_thread:
            await run_mgr.fail_start_if_pending(
                record.run_id, error=str(metadata_failure)
            )
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

    async def _archive_retrieval_receipt(receipt: dict) -> bool:
        """Make a retrieval item readable before exposing its citation."""
        from agentplatform_extension.evidence import current_run_evidence

        binding = current_run_evidence()
        if binding is None:
            return False
        archived_receipt = {**receipt, "archive_status": "archived"}
        receipts = tuple(
            archived_receipt
            if item.get("receipt_id") == receipt.get("receipt_id")
            else item
            for item in binding.retrieval_receipts
        )
        record.metadata = {
            **(record.metadata or {}),
            "run_evidence": {
                **binding.as_mapping(),
                "retrieval_receipts": list(receipts),
                "archive_status": "archived",
            },
        }
        persisted = await run_mgr.persist_current_record(record.run_id)
        if not persisted:
            failed = tuple(
                {**item, "archive_status": "failed"}
                if item.get("receipt_id") == receipt.get("receipt_id")
                else item
                for item in binding.retrieval_receipts
            )
            record.metadata = {
                **(record.metadata or {}),
                "run_evidence": {
                    **binding.as_mapping(),
                    "retrieval_receipts": list(failed),
                    "archive_status": "failed",
                },
            }
        return persisted

    owner_context_token = (
        set_current_user(SimpleNamespace(id=owner_user_id)) if owner_user_id else None
    )
    try:
        if run_evidence_binding is not None:
            from agentplatform_extension.evidence import (
                bind_receipt_archiver,
                bind_run_evidence,
            )

            with (
                bind_run_evidence(run_evidence_binding),
                bind_receipt_archiver(_archive_retrieval_receipt),
            ):
                task = asyncio.create_task(_execute_run())
        else:
            task = asyncio.create_task(_execute_run())
    finally:
        if owner_context_token is not None:
            reset_current_user(owner_context_token)
    record.task = task

    # Title sync is handled by worker.py's finally block which reads the
    # title from the checkpoint and calls thread_store.update_display_name
    # after the run completes.

    return record


def _resolve_scheduler_recursion_limit() -> int:
    """Resolve and clamp the live scheduler recursion setting per dispatch."""

    try:
        scheduler = getattr(get_app_config(), "scheduler", None)
        configured = int(
            getattr(scheduler, "recursion_limit", _DEFAULT_RECURSION_LIMIT)
        )
        ceiling = _resolve_max_recursion_limit()
        if configured > ceiling:
            logger.warning(
                "scheduler.recursion_limit %s exceeds max_recursion_limit %s; clamping",
                configured,
                ceiling,
            )
        return _clamp_recursion_limit(configured, ceiling)
    except Exception:
        logger.warning(
            "failed to load app config; falling back to recursion_limit=%s",
            _DEFAULT_RECURSION_LIMIT,
        )
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
        raise HTTPException(
            status_code=422,
            detail="legacy auth_token is unsupported; use config.context.secrets",
        )
    if request is None:
        if app is None:
            raise ValueError("launch_scheduled_thread_run requires request or app")
        request = SimpleNamespace(
            app=app,
            headers=(
                {INTERNAL_OWNER_USER_ID_HEADER_NAME: owner_user_id}
                if owner_user_id
                else {}
            ),
            state=SimpleNamespace(
                user=get_internal_user(), auth_source=AUTH_SOURCE_INTERNAL
            ),
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
        context={
            "non_interactive": True,
            **({"user_id": owner_user_id} if owner_user_id else {}),
        },
    )
    # Scheduler runs never request temporary-thread cleanup; keep the
    # internal launch contract explicit even while the legacy HTTP model
    # defaults this field to ``keep``.
    body.on_completion = None
    scheduled_task_run_id = (metadata or {}).get("scheduled_task_run_id")
    idempotency_key = (
        f"scheduled-task:{scheduled_task_run_id}"
        if isinstance(scheduled_task_run_id, str)
        else None
    )
    with ensure_trace_context():
        record = await start_run(
            body, thread_id, request, idempotency_key=idempotency_key
        )
    return {"run_id": record.run_id, "thread_id": record.thread_id}


def _mcp_task_notification_prompt(event: dict[str, Any]) -> str:
    payload = frame_untrusted_text(
        json.dumps(
            event,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )
    instruction = (
        "A durable background MCP task has an update that requires the user's attention. "
        "Explain the update clearly and concisely. Do not expose or ask for a remote task ID. "
        "When status is input_required, show the question but explain that this MCP integration "
        "cannot resume the remote task with user input yet. When tracking_degraded is true, explain "
        "that DeerFlow will continue retrying at a lower frequency."
    )
    return f"{instruction}\n\n{payload}"


async def launch_mcp_task_notification_run(
    *,
    app: Any,
    thread_id: str,
    assistant_id: str | None,
    owner_user_id: str,
    task_id: str,
    dispatch_version: int,
    dispatch_attempt: int,
    event: dict[str, Any],
) -> dict[str, Any]:
    from app.gateway.routers.thread_runs import RunCreateRequest

    request = SimpleNamespace(
        app=app,
        headers={INTERNAL_OWNER_USER_ID_HEADER_NAME: owner_user_id},
        state=SimpleNamespace(
            user=get_internal_user(), auth_source=AUTH_SOURCE_INTERNAL
        ),
        cookies={},
    )
    body = RunCreateRequest(
        assistant_id=assistant_id,
        input={
            "messages": [
                {
                    "role": "user",
                    "content": _mcp_task_notification_prompt(event),
                    "additional_kwargs": {"hide_from_ui": True},
                }
            ]
        },
        metadata={
            "mcp_task_notification": {
                "task_id": task_id,
                "dispatch_version": dispatch_version,
                "dispatch_attempt": dispatch_attempt,
            }
        },
        context={"non_interactive": True, "user_id": owner_user_id},
    )
    try:
        with ensure_trace_context():
            record = await start_run(
                body,
                thread_id,
                request,
                idempotency_key=f"mcp-task:{task_id}:{dispatch_version}:{dispatch_attempt}",
                require_existing_thread=True,
            )
    except HTTPException as exc:
        if exc.status_code == 409:
            raise ConflictError(str(exc.detail)) from exc
        if exc.status_code == 404:
            raise PermanentNotificationError(str(exc.detail)) from exc
        raise
    return {"run_id": record.run_id, "thread_id": record.thread_id}


_TERMINAL_RUN_STATUSES = {
    RunStatus.success,
    RunStatus.error,
    RunStatus.timeout,
    RunStatus.interrupted,
}


def _run_is_terminal(record: RunRecord) -> bool:
    return record.status in _TERMINAL_RUN_STATUSES


async def _terminal_record_stream_missing(
    bridge: StreamBridge, record: RunRecord
) -> bool:
    """True when a terminal run has no retained stream on bridges that can tell."""
    if not _run_is_terminal(record):
        return False
    stream_exists = getattr(bridge, "stream_exists", None)
    if stream_exists is None:
        return False
    try:
        return not bool(await stream_exists(record.run_id))
    except Exception:
        logger.debug(
            "Failed to probe stream existence for terminal run %s",
            sanitize_log_param(record.run_id),
            exc_info=True,
        )
        return False


async def _orphan_recovery_observed_after_heartbeat(
    record: RunRecord,
    run_mgr: RunManager,
) -> bool:
    """Return whether durable orphan recovery is the consumer's liveness edge.

    A normal terminal status is not sufficient: the producer persists status
    before publishing its final error/data frames and END. Orphan recovery is
    different because the producer is known to be gone and the durable
    ``stop_reason`` is written atomically with the terminal status. Only that
    explicit signal may synthesize END after a heartbeat.
    """
    if getattr(record, "store_only", False) is not True:
        return False
    getter = getattr(run_mgr, "get", None)
    if getter is None:
        return False
    refreshed_result = getter(record.run_id, user_id=record.user_id)
    if not inspect.isawaitable(refreshed_result):
        return False
    refreshed = await refreshed_result
    return (
        refreshed is not None
        and _run_is_terminal(refreshed)
        and refreshed.stop_reason == ORPHAN_RECOVERY_STOP_REASON
    )


async def wait_for_run_completion(
    bridge: StreamBridge,
    record: RunRecord,
    request: Request,
    run_mgr: RunManager,
) -> bool:
    """Block until the run publishes ``END_SENTINEL``, honouring on_disconnect.

    The non-streaming ``/wait`` endpoints used to ``await record.task``
    directly with no disconnect handling.  When the client (or an
    intermediate HTTP proxy) timed out during a long tool call such as
    ``pip install``, the handler would swallow ``CancelledError`` and
    serialize whatever checkpoint happened to exist — masking a half-finished
    run as a normal completion (issue #3265).

    This helper consumes the same bridge that ``sse_consumer`` does so the
    wait path shares its disconnect semantics: each wake-up polls
    ``request.is_disconnected()``; on a real disconnect it cancels the
    background run when ``record.on_disconnect`` is ``cancel``.  The bridge's
    heartbeat sentinels guarantee at least one wake-up per
    ``heartbeat_interval`` even when the agent emits no events for a while.

    Returns:
        ``True`` when ``END_SENTINEL`` was observed (run reached a terminal
        state), ``False`` when the loop exited because the client
        disconnected.  Callers must skip checkpoint serialization on
        ``False`` so a partial checkpoint is not returned as a normal
        response.
    """
    completed = False
    if await _terminal_record_stream_missing(bridge, record):
        return True

    resume_from_event_id: str | None = None
    try:
        while True:
            gap_seen = False
            async for entry in bridge.subscribe(
                record.run_id, last_event_id=resume_from_event_id
            ):
                # END_SENTINEL means the run reached a terminal state; honour it
                # even if the client just disconnected so the caller still serializes
                # the real final checkpoint.
                if entry is END_SENTINEL:
                    completed = True
                    return True
                if isinstance(entry, StreamGap):
                    # The wait API only needs terminal completion, not a complete
                    # event replay. Resume at the retained tail rather than
                    # treating a bridge gap as a client disconnect.
                    resume_from_event_id = entry.latest_available_event_id
                    gap_seen = True
                    break
                if (
                    entry is HEARTBEAT_SENTINEL
                    and await _orphan_recovery_observed_after_heartbeat(record, run_mgr)
                ):
                    completed = True
                    return True
                if await request.is_disconnected():
                    return False
                # Heartbeats and regular events: keep waiting for END_SENTINEL.
            if not gap_seen:
                return completed
    finally:
        if not completed and record.status in (RunStatus.pending, RunStatus.running):
            if record.on_disconnect == DisconnectMode.cancel:
                await run_mgr.cancel(record.run_id)


async def sse_consumer(
    bridge: StreamBridge,
    record: RunRecord,
    request: Request,
    run_mgr: RunManager,
    *,
    apply_on_disconnect: bool = True,
):
    """Async generator that yields SSE frames from the bridge.

    The ``finally`` block implements ``on_disconnect`` semantics, but only for
    the stream returned by the *creating* endpoint (``apply_on_disconnect=True``):

    - ``cancel``: abort the background task on client disconnect.
    - ``continue``: let the task run; events are discarded.

    Join/observer streams pass ``apply_on_disconnect=False``: the creator's
    cancel-on-disconnect policy expresses the creator's intent for their own
    connection, and a read-only observer closing a join must not cancel the
    run (a runs:read-only credential would otherwise cancel without
    runs:cancel just by disconnecting).
    """
    last_event_id = request.headers.get("Last-Event-ID")
    if await _terminal_record_stream_missing(bridge, record):
        # A terminal run with no retained stream will never publish END;
        # emit it immediately so joiners don't hang on an empty bridge.
        yield format_sse("end", None)
        return
    gap_emitted = False
    try:
        async for entry in bridge.subscribe(record.run_id, last_event_id=last_event_id):
            if await request.is_disconnected():
                break

            if isinstance(entry, StreamGap):
                gap_emitted = True
                yield format_sse(
                    "gap",
                    {
                        "code": "stream_replay_gap",
                        "run_id": record.run_id,
                        "requested_event_id": entry.requested_event_id,
                        "earliest_available_event_id": entry.earliest_available_event_id,
                        "latest_available_event_id": entry.latest_available_event_id,
                        "recovery": "reload_durable_state",
                    },
                )
                return

            if entry is HEARTBEAT_SENTINEL:
                if await _orphan_recovery_observed_after_heartbeat(record, run_mgr):
                    yield format_sse("end", None)
                    return
                yield ": heartbeat\n\n"
                continue

            if entry is END_SENTINEL:
                yield format_sse("end", None, event_id=entry.id or None)
                return

            yield format_sse(entry.event, entry.data, event_id=entry.id or None)

    finally:
        # Only the creator's own stream may cancel-on-disconnect — never an
        # observer join, and never a run executing on another worker.
        if (
            apply_on_disconnect
            and not gap_emitted
            and not record.store_only
            and record.status in (RunStatus.pending, RunStatus.running)
        ):
            if record.on_disconnect == DisconnectMode.cancel:
                await run_mgr.cancel(record.run_id)
