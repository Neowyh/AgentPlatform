"""Runs endpoints — create, stream, wait, cancel.

Implements the LangGraph Platform runs API on top of
:class:`deerflow.agents.runs.RunManager` and
:class:`deerflow.agents.stream_bridge.StreamBridge`.

SSE format is aligned with the LangGraph Platform protocol so that
the ``useStream`` React hook from ``@langchain/langgraph-sdk/react``
works without modification.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from app.gateway.artifact_archive import ArtifactArchiveError, ArtifactArchiveResult, build_artifact_archive
from app.gateway.authz import require_cancel_permission_if, require_permission
from app.gateway.checkpoint_lineage import (
    CheckpointLineageError,
    CheckpointParentMissingError,
    checkpoint_configurable,
    checkpoint_messages,
    find_checkpoint_before_message,
    find_checkpoint_before_message_chronologically,
    is_duration_only_checkpoint,
)
from app.gateway.deps import get_current_user, get_feedback_repo, get_run_event_store, get_run_manager, get_run_store, get_stream_bridge
from app.gateway.internal_auth import get_trusted_internal_owner_user_id
from app.gateway.services import build_checkpoint_state_accessor, build_thread_checkpoint_state_accessor, sse_consumer, start_run, wait_for_run_completion
from app.gateway.utils import sanitize_log_param
from deerflow.agents.middlewares.dynamic_context_middleware import strip_injected_user_message_id_suffix
from deerflow.authz.sandbox_authz import safe_app_config_async
from deerflow.config.paths import get_paths, make_safe_user_id
from deerflow.runtime import CancelOutcome, ConflictError, RunRecord, RunStatus, ThreadOperationKind, serialize_channel_values
from deerflow.runtime.secret_context import redact_config_secrets, redact_metadata_secrets
from deerflow.runtime.user_context import get_effective_user_id
from deerflow.utils.messages import ORIGINAL_USER_CONTENT_KEY, get_original_user_content_text, message_to_text
from deerflow.utils.thread_id import ThreadId

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/threads", tags=["runs"])
_artifact_archive_slots = asyncio.Semaphore(4)
REGENERATE_HISTORY_SCAN_LIMIT = 200
REGENERATE_HISTORY_RAW_SCAN_LIMIT = REGENERATE_HISTORY_SCAN_LIMIT * 2
_MISSING_REGENERATE_BASE_DETAIL = "Could not find an addressable checkpoint before the target user message"
_UNSAFE_REGENERATE_LINEAGE_DETAIL = "Could not safely resolve the checkpoint before the target user message"


class ArtifactArchiveManifestResponse(BaseModel):
    file_count: int


class RegeneratePrepareRequest(BaseModel):
    message_id: str = Field(..., min_length=1, description="Assistant message id to regenerate")


class RegeneratePrepareResponse(BaseModel):
    input: dict[str, Any]
    checkpoint: dict[str, Any]
    metadata: dict[str, Any]
    target_run_id: str


class EditRegeneratePrepareRequest(BaseModel):
    human_message_id: str = Field(..., min_length=1, description="Source human message id to edit and rerun")
    replacement_text: str = Field(..., min_length=1, description="Replacement user-visible text")


class EditRegeneratePrepareResponse(RegeneratePrepareResponse):
    replacement_human_message_id: str
    source_message_ids: list[str]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RunCreateRequest(BaseModel):
    assistant_id: str | None = Field(default=None, description="Agent / assistant to use")
    input: dict[str, Any] | None = Field(default=None, description="Graph input (e.g. {messages: [...]})")
    command: dict[str, Any] | None = Field(default=None, description="LangGraph Command")
    metadata: dict[str, Any] | None = Field(default=None, description="Run metadata")
    config: dict[str, Any] | None = Field(default=None, description="RunnableConfig overrides")
    context: dict[str, Any] | None = Field(default=None, description="iDeer context overrides (model_name, thinking_enabled, agent_resource_id, skill_resource_id, skill_name, skill_names, etc.)")
    webhook: str | None = Field(default=None, description="Completion callback URL")
    checkpoint_id: str | None = Field(default=None, description="Resume from checkpoint")
    checkpoint: dict[str, Any] | None = Field(default=None, description="Full checkpoint object")
    interrupt_before: list[str] | Literal["*"] | None = Field(default=None, description="Nodes to interrupt before")
    interrupt_after: list[str] | Literal["*"] | None = Field(default=None, description="Nodes to interrupt after")
    stream_mode: list[str] | str | None = Field(default=None, description="Stream mode(s)")
    stream_subgraphs: bool = Field(default=False, description="Include subgraph events")
    stream_resumable: bool | None = Field(default=None, description="SSE resumable mode")
    on_disconnect: Literal["cancel", "continue"] = Field(default="cancel", description="Behaviour on SSE disconnect")
    on_completion: Literal["delete", "keep"] = Field(default="keep", description="Delete temp thread on completion")
    multitask_strategy: Literal["reject", "rollback", "interrupt", "enqueue"] = Field(default="reject", description="Concurrency strategy")
    after_seconds: float | None = Field(default=None, description="Delayed execution")
    if_not_exists: Literal["reject", "create"] = Field(default="create", description="Thread creation policy")
    feedback_keys: list[str] | None = Field(default=None, description="LangSmith feedback keys")
    evidence_mode: Literal["document", "code", "hybrid"] = Field(default="hybrid", description="Internal evidence strategy for fault-analysis runs")
    code_package_id: str | None = Field(default=None, description="Validated Thread-private Code Evidence Package")


class RunResponse(BaseModel):
    run_id: str
    thread_id: str
    assistant_id: str | None = None
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    multitask_strategy: str = "reject"
    created_at: str = ""
    updated_at: str = ""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    llm_call_count: int = 0
    lead_agent_tokens: int = 0
    subagent_tokens: int = 0
    middleware_tokens: int = 0
    message_count: int = 0
    first_user_message: str | None = None
    last_assistant_message: str | None = None


class ThreadTokenUsageModelBreakdown(BaseModel):
    tokens: int = 0
    runs: int = 0


class ThreadTokenUsageCallerBreakdown(BaseModel):
    lead_agent: int = 0
    subagent: int = 0
    middleware: int = 0


class ThreadTokenUsageResponse(BaseModel):
    thread_id: str
    total_tokens: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_runs: int = 0
    by_model: dict[str, ThreadTokenUsageModelBreakdown] = Field(default_factory=dict)
    by_caller: ThreadTokenUsageCallerBreakdown = Field(default_factory=ThreadTokenUsageCallerBreakdown)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def require_cancel_permission_when_action(request: Request, action: str | None) -> None:
    """Conditionally require ``runs:cancel`` for cancel-then-stream requests.

    ``stream_existing_run`` is gated at ``runs:read`` so action-less stream
    joins keep working with read-only credentials, but its ``action`` branch
    cancels the run — a separate permission. A read-only PAT (or any read-only
    credential) must not reach the cancel path, and decorators cannot express
    query-parameter-conditional permissions, so the check lives here. See
    ``authz.require_cancel_permission_if`` — the shared primitive for every
    request dimension that carries cancel capability.
    """
    require_cancel_permission_if(request, action is not None)


def _cancel_conflict_detail(run_id: str, record: RunRecord) -> str:
    if record.status in (RunStatus.pending, RunStatus.running):
        return f"Run {run_id} is not active on this worker and cannot be cancelled"
    return f"Run {run_id} is not cancellable (status: {record.status.value})"


# Outcomes that mean the cancellation was accepted and the run is stopping:
# a local cancel, a durable request recorded for the live owner, or a takeover
# after the owner's lease expired. Every other outcome is a conflict (409) —
# ``cancel()`` returns a CancelOutcome (a non-empty StrEnum), so the old
# ``if not cancelled:`` truthiness test could never reject anything.
_CANCEL_ACCEPTED_OUTCOMES = frozenset({CancelOutcome.cancelled, CancelOutcome.requested, CancelOutcome.taken_over})


def _cancel_rejected(run_id: str, record: RunRecord, outcome: CancelOutcome) -> HTTPException:
    headers = {"Retry-After": "5"} if outcome is CancelOutcome.lease_valid_elsewhere else None
    return HTTPException(status_code=409, detail=_cancel_conflict_detail(run_id, record), headers=headers)


def _compute_retry_after(lease_expires_at: str | None, grace_seconds: int) -> int | None:
    """Return seconds until the lease expires + grace, for ``Retry-After``.

    Returns ``None`` when the lease is NULL or unparseable so the caller
    can decide whether to send a generic 409 without the header.

    The ``max(1, ...)`` floor means a lease just about to expire yields
    ``Retry-After: 1``.  This is a lower bound, not a recommended poll
    interval — clients that honour this header should apply minimum
    backoff / jitter rather than retrying every second.
    """
    if lease_expires_at is None:
        return None
    try:
        dt = datetime.fromisoformat(lease_expires_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return None
    remaining = (dt - datetime.now(UTC)).total_seconds() + grace_seconds
    return max(1, int(remaining))


def _record_to_response(record: RunRecord) -> RunResponse:
    redacted_kwargs = redact_config_secrets(record.kwargs)
    if isinstance(redacted_kwargs, dict) and isinstance(redacted_kwargs.get("config"), dict):
        redacted_kwargs = dict(redacted_kwargs)
        redacted_kwargs["config"] = redact_config_secrets(redacted_kwargs["config"])

    return RunResponse(
        run_id=record.run_id,
        thread_id=record.thread_id,
        assistant_id=record.assistant_id,
        status=record.status.value,
        metadata=redact_metadata_secrets(record.metadata),
        kwargs=redacted_kwargs,
        multitask_strategy=record.multitask_strategy,
        created_at=record.created_at,
        updated_at=record.updated_at,
        total_input_tokens=record.total_input_tokens,
        total_output_tokens=record.total_output_tokens,
        total_tokens=record.total_tokens,
        llm_call_count=record.llm_call_count,
        lead_agent_tokens=record.lead_agent_tokens,
        subagent_tokens=record.subagent_tokens,
        middleware_tokens=record.middleware_tokens,
        message_count=record.message_count,
    )


def _message_summary(row: dict) -> str | None:
    content = row.get("content")
    if isinstance(content, dict):
        content = content.get("content")
    if not isinstance(content, str):
        return None
    text = " ".join(content.split())
    return text[:240] if text else None


async def _response_with_message_summary(record: RunRecord, event_store) -> RunResponse:
    response = _record_to_response(record)
    rows = await event_store.list_messages_by_run(record.thread_id, record.run_id, limit=200)
    summaries = [(row.get("event_type"), _message_summary(row)) for row in rows]
    response.first_user_message = next((text for event_type, text in summaries if event_type == "human_message" and text), None)
    response.last_assistant_message = next((text for event_type, text in reversed(summaries) if event_type == "ai_message" and text), None)
    return response


def _message_id(message: Any) -> str | None:
    value = getattr(message, "id", None)
    if value is None and isinstance(message, dict):
        value = message.get("id")
    return str(value) if value else None


def _message_type(message: Any) -> str | None:
    value = getattr(message, "type", None)
    if value is None and isinstance(message, dict):
        value = message.get("type") or message.get("role")
    return "ai" if value == "assistant" else str(value) if value else None


def _message_name(message: Any) -> str | None:
    value = getattr(message, "name", None)
    if value is None and isinstance(message, dict):
        value = message.get("name")
    return str(value) if value else None


def _message_content(message: Any) -> Any:
    return message.get("content") if isinstance(message, dict) else getattr(message, "content", None)


def _message_text(message: Any) -> str:
    return message_to_text(message)


def _message_additional_kwargs(message: Any) -> dict[str, Any]:
    value = getattr(message, "additional_kwargs", None)
    if value is None and isinstance(message, dict):
        value = message.get("additional_kwargs")
    return dict(value or {}) if isinstance(value, dict) else {}


def _message_tool_calls(message: Any) -> list[Any]:
    value = getattr(message, "tool_calls", None)
    if value is None and isinstance(message, dict):
        value = message.get("tool_calls")
    if value is None:
        value = _message_additional_kwargs(message).get("tool_calls")
    return list(value) if isinstance(value, list) else []


def _is_hidden_or_control_message(message: Any) -> bool:
    return _message_type(message) == "remove" or _message_name(message) == "summary" or _message_additional_kwargs(message).get("hide_from_ui") is True


def _is_visible_human_message(message: Any) -> bool:
    return _message_type(message) == "human" and not _is_hidden_or_control_message(message)


def _is_visible_ai_message(message: Any) -> bool:
    return _message_type(message) == "ai" and not _is_hidden_or_control_message(message)


def _checkpoint_messages(snapshot: Any) -> list[Any]:
    return checkpoint_messages(snapshot)


def _checkpoint_values(snapshot: Any) -> dict[str, Any]:
    values = getattr(snapshot, "values", None)
    return dict(values) if isinstance(values, dict) else {}


def _checkpoint_configurable(checkpoint_tuple: Any) -> dict[str, Any]:
    return checkpoint_configurable(checkpoint_tuple)


def _checkpoint_response(checkpoint_tuple: Any) -> dict[str, Any]:
    configurable = _checkpoint_configurable(checkpoint_tuple)
    checkpoint_id = configurable.get("checkpoint_id")
    if not checkpoint_id:
        raise HTTPException(status_code=409, detail="Checkpoint is missing checkpoint_id")
    return {
        "checkpoint_ns": str(configurable.get("checkpoint_ns") or ""),
        "checkpoint_id": str(checkpoint_id),
        "checkpoint_map": configurable.get("checkpoint_map"),
    }


def _clean_human_message_for_regenerate(message: Any) -> dict[str, Any]:
    additional_kwargs = _message_additional_kwargs(message)
    content = get_original_user_content_text(_message_content(message), additional_kwargs)
    additional_kwargs.pop(ORIGINAL_USER_CONTENT_KEY, None)
    additional_kwargs.pop("hide_from_ui", None)
    clean_message: dict[str, Any] = {
        "type": "human",
        "content": [{"type": "text", "text": content}],
        "additional_kwargs": additional_kwargs,
    }
    message_id = strip_injected_user_message_id_suffix(_message_id(message))
    if message_id:
        clean_message["id"] = message_id
    if name := _message_name(message):
        clean_message["name"] = name
    return clean_message


def _clean_human_message_for_edit(message: Any, *, replacement_id: str, replacement_text: str) -> dict[str, Any]:
    source_kwargs = _message_additional_kwargs(message)
    additional_kwargs = {key: deepcopy(source_kwargs[key]) for key in ("files", "referenced_message_contexts") if key in source_kwargs}
    clean_message: dict[str, Any] = {
        "type": "human",
        "id": replacement_id,
        "content": [{"type": "text", "text": replacement_text}],
        "additional_kwargs": additional_kwargs,
    }
    if name := _message_name(message):
        clean_message["name"] = name
    return clean_message


def _is_terminal_assistant_text_message(message: Any) -> bool:
    return _is_visible_ai_message(message) and bool(_message_text(message).strip()) and not _message_tool_calls(message)


def _has_title(values: dict[str, Any]) -> bool:
    return isinstance(values.get("title"), str) and bool(values["title"])


def _has_active_goal(snapshot: Any) -> bool:
    goal = _checkpoint_values(snapshot).get("goal")
    return isinstance(goal, dict) and goal.get("status") == "active"


def _latest_editable_turn(messages: list[Any], human_message_id: str) -> tuple[int, Any, int, Any, list[str]]:
    latest_human_index = next((index for index in range(len(messages) - 1, -1, -1) if _is_visible_human_message(messages[index])), None)
    if latest_human_index is None or _message_id(messages[latest_human_index]) != human_message_id:
        raise HTTPException(status_code=409, detail="Only the latest completed user turn can be edited")
    source_human = messages[latest_human_index]
    last_ai_index: int | None = None
    for index, message in enumerate(messages[latest_human_index + 1 :], start=latest_human_index + 1):
        if _is_visible_human_message(message):
            break
        if _is_visible_ai_message(message):
            last_ai_index = index
    if last_ai_index is None or not _is_terminal_assistant_text_message(messages[last_ai_index]):
        raise HTTPException(status_code=409, detail="Only completed assistant text turns can be edited")
    source_message_ids = [message_id for message in messages[latest_human_index : last_ai_index + 1] if (message_id := _message_id(message))]
    return latest_human_index, source_human, last_ai_index, messages[last_ai_index], source_message_ids


def _event_message_id(row: dict[str, Any]) -> str | None:
    content = row.get("content")
    return _message_id(content) if isinstance(content, (BaseMessage, dict)) else None


def _run_last_ai_matches_message(record: RunRecord, message: Any) -> bool:
    last_ai_message = (record.last_ai_message or "").strip()
    target_text = _message_text(message).strip()
    return bool(last_ai_message and target_text) and last_ai_message == target_text[: len(last_ai_message)]


async def _find_target_run_id(thread_id: str, message_id: str, target_message: Any, source_human: Any, request: Request) -> str:
    rows = await get_run_event_store(request).list_messages(thread_id, limit=REGENERATE_HISTORY_SCAN_LIMIT)
    for row in reversed(rows):
        if row.get("event_type") in {"ai_message", "llm.ai.response"} and _event_message_id(row) == message_id:
            if isinstance(run_id := row.get("run_id"), str) and run_id:
                return run_id
    if isinstance(source_run_id := _message_additional_kwargs(source_human).get("run_id"), str) and source_run_id:
        return source_run_id
    run_mgr = get_run_manager(request)
    user_id = await get_current_user(request)
    records = await run_mgr.list_by_thread(thread_id, user_id=user_id, limit=10)
    if fallback_record := next((record for record in records if record.status == RunStatus.success and _run_last_ai_matches_message(record, target_message)), None):
        return fallback_record.run_id
    if len(rows) >= REGENERATE_HISTORY_SCAN_LIMIT:
        logger.warning("Could not find source run for regenerate message %s in recent run events for thread %s (limit=%s)", message_id, thread_id, REGENERATE_HISTORY_SCAN_LIMIT)
    raise HTTPException(status_code=409, detail="Could not find source run for assistant message")


async def _find_base_checkpoint_before_human(thread_id: str, human_message_id: str, request: Request, *, head_checkpoint: Any | None = None) -> Any:
    accessor, base_config = await build_thread_checkpoint_state_accessor(request, thread_id=thread_id)
    if head_checkpoint is not None:
        try:
            return await find_checkpoint_before_message(accessor, head_checkpoint, human_message_id, max_depth=REGENERATE_HISTORY_RAW_SCAN_LIMIT)
        except CheckpointParentMissingError:
            logger.debug("Could not resolve parent lineage for regenerate thread %s; falling back to history scan", sanitize_log_param(thread_id), exc_info=True)
        except CheckpointLineageError as exc:
            logger.warning("Rejected unsafe checkpoint lineage for regenerate thread %s", sanitize_log_param(thread_id), exc_info=True)
            raise HTTPException(status_code=409, detail=_UNSAFE_REGENERATE_LINEAGE_DETAIL) from exc
    try:
        raw_checkpoints = await accessor.ahistory(base_config, limit=REGENERATE_HISTORY_RAW_SCAN_LIMIT)
        checkpoints = [item for item in raw_checkpoints if not is_duration_only_checkpoint(item)]
    except Exception as exc:
        logger.exception("Failed to list checkpoints for regenerate thread %s", thread_id)
        raise HTTPException(status_code=500, detail="Failed to inspect checkpoint history") from exc
    previous_checkpoint, target_found = find_checkpoint_before_message_chronologically(raw_checkpoints, human_message_id)
    if target_found:
        if previous_checkpoint is None:
            raise HTTPException(status_code=409, detail=_MISSING_REGENERATE_BASE_DETAIL)
        return previous_checkpoint
    if len(checkpoints) >= REGENERATE_HISTORY_SCAN_LIMIT:
        logger.warning("Could not locate target user message %s in recent checkpoint history for thread %s (limit=%s)", human_message_id, thread_id, REGENERATE_HISTORY_SCAN_LIMIT)
    raise HTTPException(status_code=409, detail=f"Could not locate target user message in recent checkpoint history (limit={REGENERATE_HISTORY_SCAN_LIMIT})")


def _run_status_value(record: Any) -> str | None:
    status = getattr(record, "status", None)
    return status.value if isinstance(status, RunStatus) else str(status) if status is not None else None


async def _require_successful_source_run(thread_id: str, run_id: str, request: Request) -> RunRecord:
    run_mgr = get_run_manager(request)
    user_id = await get_current_user(request)
    record = await run_mgr.get(run_id, user_id=user_id)
    if record is None:
        records = await run_mgr.list_by_thread(thread_id, user_id=user_id, limit=20)
        record = next((candidate for candidate in records if getattr(candidate, "run_id", None) == run_id), None)
    if record is None or (record_thread_id := getattr(record, "thread_id", None)) and record_thread_id != thread_id:
        raise HTTPException(status_code=409, detail="Could not find source run for assistant message")
    if _run_status_value(record) != RunStatus.success.value:
        raise HTTPException(status_code=409, detail="Only successful assistant runs can be edited and rerun")
    return record


async def _find_interrupted_target_run_id(thread_id: str, source_human: Any, request: Request) -> str | None:
    source_run_id = _message_additional_kwargs(source_human).get("run_id")
    if not isinstance(source_run_id, str) or not source_run_id:
        return None
    run_mgr = get_run_manager(request)
    user_id = await get_current_user(request)
    record = await run_mgr.get(source_run_id, user_id=user_id)
    if record is None:
        records = await run_mgr.list_by_thread(thread_id, user_id=user_id, limit=20)
        record = next((candidate for candidate in records if getattr(candidate, "run_id", None) == source_run_id), None)
    if record is None or getattr(record, "thread_id", None) != thread_id or _run_status_value(record) != RunStatus.interrupted.value:
        return None
    return source_run_id


async def _prepare_regenerate_payload(thread_id: str, message_id: str, request: Request) -> RegeneratePrepareResponse:
    accessor, latest_config = await build_thread_checkpoint_state_accessor(request, thread_id=thread_id)
    try:
        latest_checkpoint = await accessor.aget(latest_config)
    except Exception as exc:
        logger.exception("Failed to read latest checkpoint for regenerate thread %s", thread_id)
        raise HTTPException(status_code=500, detail="Failed to read latest checkpoint") from exc
    if not _checkpoint_configurable(latest_checkpoint).get("checkpoint_id"):
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} has no checkpoint")

    messages = _checkpoint_messages(latest_checkpoint)
    target_index = next((index for index, message in enumerate(messages) if _message_id(message) == message_id), None)
    if target_index is None:
        previous_human = next((message for message in reversed(messages) if _is_visible_human_message(message)), None)
        target_run_id = await _find_interrupted_target_run_id(thread_id, previous_human, request) if previous_human is not None else None
        if target_run_id is None:
            raise HTTPException(status_code=404, detail=f"Message {message_id} not found")
    else:
        target_message = messages[target_index]
        if not _is_visible_ai_message(target_message):
            raise HTTPException(status_code=409, detail="Only visible assistant messages can be regenerated")
        latest_visible_ai = next((message for message in reversed(messages) if _is_visible_ai_message(message)), None)
        if _message_id(latest_visible_ai) != message_id:
            raise HTTPException(status_code=409, detail="Only the latest assistant message can be regenerated")
        previous_human = next((message for message in reversed(messages[:target_index]) if _is_visible_human_message(message)), None)
        target_run_id = await _find_target_run_id(thread_id, message_id, target_message, previous_human, request) if previous_human is not None else None
    if previous_human is None:
        raise HTTPException(status_code=409, detail="Could not find the user message for this assistant response")
    if target_run_id is None:
        raise HTTPException(status_code=409, detail="Could not find source run for assistant message")
    previous_human_id = _message_id(previous_human)
    if not previous_human_id:
        raise HTTPException(status_code=409, detail="The source user message is missing an id")

    checkpoint = _checkpoint_response(await _find_base_checkpoint_before_human(thread_id, previous_human_id, request, head_checkpoint=latest_checkpoint))
    regenerate_input: dict[str, Any] = {"messages": [_clean_human_message_for_regenerate(previous_human)]}
    latest_title = _checkpoint_values(latest_checkpoint).get("title")
    if isinstance(latest_title, str) and latest_title:
        regenerate_input["title"] = latest_title
    return RegeneratePrepareResponse(
        input=regenerate_input,
        checkpoint=checkpoint,
        metadata={
            "regenerate_from_message_id": message_id,
            "regenerate_from_run_id": target_run_id,
            "regenerate_checkpoint_id": checkpoint["checkpoint_id"],
        },
        target_run_id=target_run_id,
    )


async def _prepare_edit_regenerate_payload(
    thread_id: str,
    human_message_id: str,
    replacement_text: str,
    request: Request,
) -> EditRegeneratePrepareResponse:
    normalized_text = replacement_text.strip()
    if not normalized_text:
        raise HTTPException(status_code=409, detail="Edited message cannot be empty")
    accessor, latest_config = await build_thread_checkpoint_state_accessor(request, thread_id=thread_id)
    try:
        latest_checkpoint = await accessor.aget(latest_config)
    except Exception as exc:
        logger.exception("Failed to read latest checkpoint for edit replay thread %s", thread_id)
        raise HTTPException(status_code=500, detail="Failed to read latest checkpoint") from exc
    if not _checkpoint_configurable(latest_checkpoint).get("checkpoint_id"):
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} has no checkpoint")
    if _has_active_goal(latest_checkpoint):
        raise HTTPException(status_code=409, detail="Cannot edit while a goal is active")

    _, source_human, _, source_ai, source_message_ids = _latest_editable_turn(_checkpoint_messages(latest_checkpoint), human_message_id)
    source_text = get_original_user_content_text(_message_content(source_human), _message_additional_kwargs(source_human)).strip()
    if normalized_text == source_text:
        raise HTTPException(status_code=409, detail="Edited message is unchanged")
    source_human_id = _message_id(source_human)
    source_ai_id = _message_id(source_ai)
    if not source_human_id:
        raise HTTPException(status_code=409, detail="The source user message is missing an id")
    if not source_ai_id:
        raise HTTPException(status_code=409, detail="The source assistant message is missing an id")

    base_checkpoint = await _find_base_checkpoint_before_human(thread_id, source_human_id, request, head_checkpoint=latest_checkpoint)
    target_run_id = await _find_target_run_id(thread_id, source_ai_id, source_ai, source_human, request)
    source_record = await _require_successful_source_run(thread_id, target_run_id, request)
    checkpoint = _checkpoint_response(base_checkpoint)
    replacement_human_message_id = str(uuid.uuid4())
    source_metadata = getattr(source_record, "metadata", None) or {}
    existing_group_id = source_metadata.get("edit_version_group_id") if isinstance(source_metadata, dict) else None
    edit_version_group_id = existing_group_id if isinstance(existing_group_id, str) and existing_group_id else source_human_id
    edit_input: dict[str, Any] = {
        "messages": [
            _clean_human_message_for_edit(
                source_human,
                replacement_id=replacement_human_message_id,
                replacement_text=normalized_text,
            )
        ]
    }
    latest_title = _checkpoint_values(latest_checkpoint).get("title")
    if _has_title(_checkpoint_values(base_checkpoint)) and isinstance(latest_title, str) and latest_title:
        edit_input["title"] = latest_title
    return EditRegeneratePrepareResponse(
        input=edit_input,
        checkpoint=checkpoint,
        metadata={
            "replay_kind": "edit",
            "regenerate_from_message_id": source_ai_id,
            "regenerate_from_run_id": target_run_id,
            "regenerate_checkpoint_id": checkpoint["checkpoint_id"],
            "edit_from_message_id": source_human_id,
            "edit_message_id": replacement_human_message_id,
            "edit_version_group_id": edit_version_group_id,
        },
        target_run_id=target_run_id,
        replacement_human_message_id=replacement_human_message_id,
        source_message_ids=source_message_ids,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/{thread_id}/runs/regenerate/prepare", response_model=RegeneratePrepareResponse)
@require_permission("runs", "create", owner_check=True, require_existing=True)
async def prepare_regenerate_run(
    thread_id: ThreadId,
    body: RegeneratePrepareRequest,
    request: Request,
) -> RegeneratePrepareResponse:
    """Prepare input and checkpoint for regenerating the latest assistant turn."""
    return await _prepare_regenerate_payload(thread_id, body.message_id, request)


@router.post("/{thread_id}/runs/edit-regenerate/prepare", response_model=EditRegeneratePrepareResponse)
@require_permission("runs", "create", owner_check=True, require_existing=True)
async def prepare_edit_regenerate_run(
    thread_id: ThreadId,
    body: EditRegeneratePrepareRequest,
    request: Request,
) -> EditRegeneratePrepareResponse:
    """Prepare input and checkpoint for editing then rerunning the latest user turn."""
    return await _prepare_edit_regenerate_payload(thread_id, body.human_message_id, body.replacement_text, request)


@router.post("/{thread_id}/runs", response_model=RunResponse)
@require_permission("runs", "create", owner_check=True, require_existing=True)
async def create_run(thread_id: str, body: RunCreateRequest, request: Request) -> RunResponse:
    """Create a background run (returns immediately)."""
    record = await start_run(body, thread_id, request)
    return _record_to_response(record)


@router.post("/{thread_id}/runs/stream")
@require_permission("runs", "create", owner_check=True, require_existing=True)
async def stream_run(thread_id: str, body: RunCreateRequest, request: Request) -> StreamingResponse:
    """Create a run and stream events via SSE.

    The response includes a ``Content-Location`` header with the run's
    resource URL, matching the LangGraph Platform protocol.  The
    ``useStream`` React hook uses this to extract run metadata.
    """
    bridge = get_stream_bridge(request)
    run_mgr = get_run_manager(request)
    record = await start_run(body, thread_id, request)

    return StreamingResponse(
        sse_consumer(bridge, record, request, run_mgr),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            # LangGraph Platform includes run metadata in this header.
            # The SDK uses a greedy regex to extract the run id from this path,
            # so it must point at the canonical run resource without extra suffixes.
            "Content-Location": f"/api/threads/{thread_id}/runs/{record.run_id}",
        },
    )


@router.post("/{thread_id}/runs/wait", response_model=dict)
@require_permission("runs", "create", owner_check=True, require_existing=True)
async def wait_run(thread_id: str, body: RunCreateRequest, request: Request) -> dict:
    """Create a run and block until it completes, returning the final state."""
    bridge = get_stream_bridge(request)
    run_mgr = get_run_manager(request)
    record = await start_run(body, thread_id, request)

    completed = True
    if record.task is not None:
        completed = await wait_for_run_completion(bridge, record, request, run_mgr)

    if completed:
        try:
            accessor, config = build_checkpoint_state_accessor(
                request,
                thread_id=thread_id,
                assistant_id=body.assistant_id,
            )
            snapshot = await accessor.aget(config)
            if _checkpoint_configurable(snapshot).get("checkpoint_id"):
                return serialize_channel_values(snapshot.values)
        except Exception:
            logger.exception("Failed to fetch final state for run %s", record.run_id)

    return {"status": record.status.value, "error": record.error}


@router.get("/{thread_id}/runs", response_model=list[RunResponse])
@require_permission("runs", "read", owner_check=True)
async def list_runs(thread_id: str, request: Request) -> list[RunResponse]:
    """List all runs for a thread."""
    run_mgr = get_run_manager(request)
    event_store = get_run_event_store(request)
    user_id = await get_current_user(request)
    records = await run_mgr.list_by_thread(thread_id, user_id=user_id)
    return [await _response_with_message_summary(record, event_store) for record in records]


@router.get("/{thread_id}/runs/{run_id}", response_model=RunResponse)
@require_permission("runs", "read", owner_check=True)
async def get_run(thread_id: str, run_id: str, request: Request) -> RunResponse:
    """Get details of a specific run."""
    run_mgr = get_run_manager(request)
    user_id = await get_current_user(request)
    record = await run_mgr.get(run_id, user_id=user_id)
    if record is None or record.thread_id != thread_id:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return _record_to_response(record)


@router.post("/{thread_id}/runs/{run_id}/cancel")
@require_permission("runs", "cancel", owner_check=True, require_existing=True)
async def cancel_run(
    thread_id: str,
    run_id: str,
    request: Request,
    wait: bool = Query(default=False, description="Block until run completes after cancel"),
    action: Literal["interrupt", "rollback"] = Query(default="interrupt", description="Cancel action"),
) -> Response:
    """Cancel a running or pending run.

    - action=interrupt: Stop execution, keep current checkpoint (can be resumed)
    - action=rollback: Stop execution, revert to pre-run checkpoint state
    - wait=true: Block until the run fully stops, return 204
    - wait=false: Return immediately with 202
    """
    run_mgr = get_run_manager(request)
    record = await run_mgr.get(run_id)
    if record is None or record.thread_id != thread_id:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    cancelled = await run_mgr.cancel(run_id, action=action)
    if cancelled not in _CANCEL_ACCEPTED_OUTCOMES:
        raise _cancel_rejected(run_id, record, cancelled)

    if wait and record.task is not None:
        try:
            await record.task
        except asyncio.CancelledError:
            pass
        return Response(status_code=204)

    if wait and cancelled == CancelOutcome.requested:
        bridge = get_stream_bridge(request)
        if record.store_only and bridge.supports_cross_process:
            # wait=true observes the remote owner's finalization through the
            # shared bridge instead of answering 202 immediately.
            completed = await wait_for_run_completion(bridge, record, request, run_mgr)
            if completed:
                return Response(status_code=204)

    return Response(status_code=202)


@router.get("/{thread_id}/runs/{run_id}/join")
@require_permission("runs", "read", owner_check=True)
async def join_run(thread_id: str, run_id: str, request: Request) -> StreamingResponse:
    """Join an existing run's SSE stream."""
    run_mgr = get_run_manager(request)
    record = await run_mgr.get(run_id)
    if record is None or record.thread_id != thread_id:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    if record.store_only:
        raise HTTPException(status_code=409, detail=f"Run {run_id} is not active on this worker and cannot be streamed")

    bridge = get_stream_bridge(request)
    return StreamingResponse(
        sse_consumer(bridge, record, request, run_mgr, apply_on_disconnect=False),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _reject_get_stream_action(
    action: Literal["interrupt", "rollback"] | None = Query(default=None, include_in_schema=False),
) -> None:
    """Keep the GET join read-only before thread ownership or run lookup."""
    if action is not None:
        # SameSite=Lax still sends the session cookie on a cross-site top-level
        # safe navigation. Reject the state-changing action before the endpoint
        # wrapper performs its thread ownership lookup.
        raise HTTPException(
            status_code=405,
            detail="`action` is only supported on POST requests",
            headers={"Allow": "POST"},
        )


async def _stream_existing_run(
    thread_id: ThreadId,
    run_id: str,
    request: Request,
    *,
    action: Literal["interrupt", "rollback"] | None,
    wait: int,
) -> Response:
    """Join an existing run's SSE stream, optionally cancelling it first.

    The LangGraph SDK's ``joinStream`` and ``useStream`` stop button both use
    ``POST`` to this endpoint.  When ``action=interrupt`` or ``action=rollback``
    is present the run is cancelled first; the response then streams any
    remaining buffered events so the client observes a clean shutdown.
    """
    require_cancel_permission_when_action(request, action)
    run_mgr = get_run_manager(request)
    record = await run_mgr.get(run_id)
    if record is None or record.thread_id != thread_id:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    if record.store_only and action is None:
        raise HTTPException(status_code=409, detail=f"Run {run_id} is not active on this worker and cannot be streamed")

    # Cancel if an action was requested (stop-button / interrupt flow). The
    # cancel/reject outcomes resolve before the bridge dependency so a
    # rejected cancel never fails on missing stream state.
    if action is not None:
        cancelled = await run_mgr.cancel(run_id, action=action)
        if cancelled not in _CANCEL_ACCEPTED_OUTCOMES:
            raise _cancel_rejected(run_id, record, cancelled)
        if wait and record.task is not None:
            try:
                await record.task
            except (asyncio.CancelledError, Exception):
                pass
            return Response(status_code=204)

    bridge = get_stream_bridge(request)
    if action is not None:
        if record.store_only and not bridge.supports_cross_process:
            # The cancel request is durable (the store records ``cancel_action``),
            # but the run executes on another worker and this bridge cannot
            # observe the owner's stream — an SSE subscription here would hang
            # forever waiting for events it can never see.
            return Response(status_code=202)
        if wait and cancelled == CancelOutcome.requested:
            completed = await wait_for_run_completion(bridge, record, request, run_mgr)
            return Response(status_code=204 if completed else 202)

    return StreamingResponse(
        sse_consumer(bridge, record, request, run_mgr, apply_on_disconnect=False),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Register POST before GET to preserve the historical route precedence and
# Allow header, while separate signatures keep cancel-only parameters off the
# GET schema. The shared route name keeps generated operationIds stable.
@router.post("/{thread_id}/runs/{run_id}/stream", response_model=None, name="stream_existing_run")
@require_permission("runs", "read", owner_check=True)
async def stream_existing_run(
    thread_id: ThreadId,
    run_id: str,
    request: Request,
    action: Literal["interrupt", "rollback"] | None = Query(default=None, description="Cancel action"),
    wait: int = Query(default=0, description="Block until cancelled (1) or return immediately (0)"),
) -> Response:
    """Join an existing run's SSE stream, optionally cancelling it first."""
    return await _stream_existing_run(thread_id, run_id, request, action=action, wait=wait)


@router.get(
    "/{thread_id}/runs/{run_id}/stream",
    response_model=None,
    dependencies=[Depends(_reject_get_stream_action)],
    name="stream_existing_run",
)
@require_permission("runs", "read", owner_check=True)
async def join_existing_run_stream(thread_id: ThreadId, run_id: str, request: Request) -> Response:
    """Join an existing run's observation-only SSE stream."""
    return await _stream_existing_run(thread_id, run_id, request, action=None, wait=0)


# ---------------------------------------------------------------------------
# Messages / Events / Token usage endpoints
# ---------------------------------------------------------------------------


@router.get("/{thread_id}/messages")
@require_permission("runs", "read", owner_check=True)
async def list_thread_messages(
    thread_id: str,
    request: Request,
    limit: int = Query(default=50, le=200),
    before_seq: int | None = Query(default=None),
    after_seq: int | None = Query(default=None),
) -> list[dict]:
    """Return displayable messages for a thread (across all runs), with feedback attached."""
    event_store = get_run_event_store(request)
    messages = await event_store.list_messages(thread_id, limit=limit, before_seq=before_seq, after_seq=after_seq)

    # Attach feedback to the last AI message of each run
    feedback_repo = get_feedback_repo(request)
    user_id = await get_current_user(request)
    feedback_map = await feedback_repo.list_by_thread_grouped(thread_id, user_id=user_id)

    # Find the last ai_message per run_id
    last_ai_per_run: dict[str, int] = {}  # run_id -> index in messages list
    for i, msg in enumerate(messages):
        if msg.get("event_type") == "ai_message":
            last_ai_per_run[msg["run_id"]] = i

    # Attach feedback field
    last_ai_indices = set(last_ai_per_run.values())
    for i, msg in enumerate(messages):
        if i in last_ai_indices:
            run_id = msg["run_id"]
            fb = feedback_map.get(run_id)
            msg["feedback"] = (
                {
                    "feedback_id": fb["feedback_id"],
                    "rating": fb["rating"],
                    "comment": fb.get("comment"),
                }
                if fb
                else None
            )
        else:
            msg["feedback"] = None

    return messages


@router.get("/{thread_id}/runs/{run_id}/messages")
@require_permission("runs", "read", owner_check=True)
async def list_run_messages(
    thread_id: str,
    run_id: str,
    request: Request,
    limit: int = Query(default=50, le=200, ge=1),
    before_seq: int | None = Query(default=None),
    after_seq: int | None = Query(default=None),
) -> dict:
    """Return paginated messages for a specific run.

    Response: { data: [...], has_more: bool }
    """
    event_store = get_run_event_store(request)
    rows = await event_store.list_messages_by_run(
        thread_id,
        run_id,
        limit=limit + 1,
        before_seq=before_seq,
        after_seq=after_seq,
    )
    has_more = len(rows) > limit
    data = rows[:limit] if has_more else rows
    return {"data": data, "has_more": has_more}


def _archive_response_chunks(result: ArtifactArchiveResult):
    try:
        while chunk := result.file.read(1024 * 1024):
            yield chunk
    finally:
        result.file.close()


async def _build_archive_without_abandoning_worker(
    outputs_dir,
    user_data_dir,
    presented_paths: list[str],
    *,
    extra_reserved_dir_names: set[str],
) -> ArtifactArchiveResult:
    if _artifact_archive_slots.locked():
        raise ArtifactArchiveError("Too many artifact archives are being created; try again shortly", 429)
    await _artifact_archive_slots.acquire()
    build_task = asyncio.create_task(
        asyncio.to_thread(
            build_artifact_archive,
            outputs_dir,
            presented_paths,
            user_data_dir=user_data_dir,
            extra_reserved_dir_names=extra_reserved_dir_names,
        )
    )
    try:
        return await asyncio.shield(build_task)
    except asyncio.CancelledError:
        while not build_task.done():
            try:
                await asyncio.shield(build_task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not build_task.cancelled():
            try:
                build_task.result().file.close()
            except Exception:
                pass
        raise
    finally:
        _artifact_archive_slots.release()


def _presented_files_from_delivery(events: list[dict]) -> list[str]:
    if len(events) != 1:
        raise HTTPException(status_code=409, detail="This response has no verified artifact delivery")
    content = events[0].get("content")
    by_tool = content.get("by_tool") if isinstance(content, dict) else None
    presented = by_tool.get("present_files") if isinstance(by_tool, dict) else None
    if not isinstance(presented, list) or not presented or any(not isinstance(path, str) for path in presented):
        raise HTTPException(status_code=409, detail="This response has no verified artifact delivery")
    return presented


async def _archive_presented_paths(thread_id: ThreadId, run_id: str, request: Request) -> list[str]:
    run = await get_run_store(request).get(run_id)
    if run is None or run.get("thread_id") != thread_id or run.get("operation_kind", "run") != "run":
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    if run.get("status") in {RunStatus.pending.value, RunStatus.running.value}:
        raise HTTPException(status_code=409, detail="This run has not finished")

    events = await get_run_event_store(request).list_events(
        thread_id,
        run_id,
        event_types=["run.delivery"],
        limit=2,
    )
    return _presented_files_from_delivery(events)


@router.get(
    "/{thread_id}/runs/{run_id}/artifacts/archive",
    response_model=ArtifactArchiveManifestResponse,
)
@require_permission("runs", "read", owner_check=True, require_existing=True)
async def get_run_artifact_archive_manifest(
    thread_id: ThreadId,
    run_id: str,
    request: Request,
) -> ArtifactArchiveManifestResponse:
    """Return the verified terminal delivery count used by the archive."""
    presented_paths = await _archive_presented_paths(thread_id, run_id, request)
    return ArtifactArchiveManifestResponse(file_count=len(dict.fromkeys(presented_paths)))


@router.post("/{thread_id}/runs/{run_id}/artifacts/archive")
@require_permission("runs", "read", owner_check=True, require_existing=True)
async def create_run_artifact_archive(
    thread_id: ThreadId,
    run_id: str,
    request: Request,
) -> StreamingResponse:
    """Download the current contents of the files presented by one terminal run."""
    presented_paths = await _archive_presented_paths(thread_id, run_id, request)

    raw_owner_user_id = get_trusted_internal_owner_user_id(request)
    effective_user_id = make_safe_user_id(raw_owner_user_id) if raw_owner_user_id else get_effective_user_id()
    app_config = await safe_app_config_async()
    custom_tool_output_dir = getattr(getattr(app_config, "tool_output", None), "storage_subdir", None)
    extra_reserved_dir_names = {custom_tool_output_dir} if isinstance(custom_tool_output_dir, str) else set()
    paths = get_paths()
    user_data_dir = paths.sandbox_user_data_dir(thread_id, user_id=effective_user_id)
    outputs_dir = paths.sandbox_outputs_dir(thread_id, user_id=effective_user_id)

    try:
        async with get_run_manager(request).reserve_thread_operation(
            thread_id,
            kind=ThreadOperationKind.artifact_archive,
            user_id=effective_user_id,
        ):
            result = await _build_archive_without_abandoning_worker(
                outputs_dir,
                user_data_dir,
                presented_paths,
                extra_reserved_dir_names=extra_reserved_dir_names,
            )
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail="Artifacts are currently being modified; try again shortly") from exc
    except ArtifactArchiveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    safe_run_id = re.sub(r"[^A-Za-z0-9_-]", "", run_id)[:32] or "run"
    logger.info(
        "Created artifact archive thread_id=%s run_id=%s members=%d input_bytes=%d output_bytes=%d",
        sanitize_log_param(thread_id),
        sanitize_log_param(run_id),
        result.member_count,
        result.input_bytes,
        result.size,
    )
    return StreamingResponse(
        _archive_response_chunks(result),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="artifacts-{safe_run_id}.zip"',
            "Content-Length": str(result.size),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
        background=BackgroundTask(result.file.close),
    )


@router.get("/{thread_id}/runs/{run_id}/events")
@require_permission("runs", "read", owner_check=True)
async def list_run_events(
    thread_id: str,
    run_id: str,
    request: Request,
    event_types: str | None = Query(default=None),
    limit: int = Query(default=500, le=2000),
) -> list[dict]:
    """Return the full event stream for a run (debug/audit)."""
    event_store = get_run_event_store(request)
    types = event_types.split(",") if event_types else None
    return await event_store.list_events(thread_id, run_id, event_types=types, limit=limit)


@router.get("/{thread_id}/token-usage", response_model=ThreadTokenUsageResponse)
@require_permission("threads", "read", owner_check=True)
async def thread_token_usage(
    thread_id: str,
    request: Request,
    include_active: bool = Query(default=False, description="Include running run progress snapshots"),
) -> ThreadTokenUsageResponse:
    """Thread-level token usage aggregation."""
    run_store = get_run_store(request)
    if include_active:
        agg = await run_store.aggregate_tokens_by_thread(thread_id, include_active=True)
    else:
        agg = await run_store.aggregate_tokens_by_thread(thread_id)
    return ThreadTokenUsageResponse(thread_id=thread_id, **agg)
