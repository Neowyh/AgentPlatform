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
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from app.gateway.artifact_archive import ArtifactArchiveError, ArtifactArchiveResult, build_artifact_archive
from app.gateway.authz import require_permission
from app.gateway.deps import get_checkpointer, get_current_user, get_feedback_repo, get_run_event_store, get_run_manager, get_run_store, get_stream_bridge
from app.gateway.internal_auth import get_trusted_internal_owner_user_id
from app.gateway.services import sse_consumer, start_run
from app.gateway.utils import sanitize_log_param
from deerflow.authz.sandbox_authz import safe_app_config_async
from deerflow.config.paths import get_paths, make_safe_user_id
from deerflow.runtime import CancelOutcome, ConflictError, RunRecord, RunStatus, ThreadOperationKind, serialize_channel_values
from deerflow.runtime.secret_context import redact_config_secrets, redact_metadata_secrets
from deerflow.runtime.user_context import get_effective_user_id
from deerflow.utils.thread_id import ThreadId

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/threads", tags=["runs"])
_artifact_archive_slots = asyncio.Semaphore(4)


class ArtifactArchiveManifestResponse(BaseModel):
    file_count: int


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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


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
    record = await start_run(body, thread_id, request)

    if record.task is not None:
        try:
            await record.task
        except asyncio.CancelledError:
            pass

    checkpointer = get_checkpointer(request)
    config = {"configurable": {"thread_id": thread_id}}
    try:
        checkpoint_tuple = await checkpointer.aget_tuple(config)
        if checkpoint_tuple is not None:
            checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
            channel_values = checkpoint.get("channel_values", {})
            return serialize_channel_values(channel_values)
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
        sse_consumer(bridge, record, request, run_mgr),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.api_route("/{thread_id}/runs/{run_id}/stream", methods=["GET", "POST"], response_model=None)
@require_permission("runs", "read", owner_check=True)
async def stream_existing_run(
    thread_id: str,
    run_id: str,
    request: Request,
    action: Literal["interrupt", "rollback"] | None = Query(default=None, description="Cancel action"),
    wait: int = Query(default=0, description="Block until cancelled (1) or return immediately (0)"),
):
    """Join an existing run's SSE stream (GET), or cancel-then-stream (POST).

    The LangGraph SDK's ``joinStream`` and ``useStream`` stop button both use
    ``POST`` to this endpoint.  When ``action=interrupt`` or ``action=rollback``
    is present the run is cancelled first; the response then streams any
    remaining buffered events so the client observes a clean shutdown.
    """
    run_mgr = get_run_manager(request)
    record = await run_mgr.get(run_id)
    if record is None or record.thread_id != thread_id:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    if record.store_only and action is None:
        raise HTTPException(status_code=409, detail=f"Run {run_id} is not active on this worker and cannot be streamed")

    # Cancel if an action was requested (stop-button / interrupt flow)
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
    return StreamingResponse(
        sse_consumer(bridge, record, request, run_mgr),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
