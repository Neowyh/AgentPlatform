"""Deep module for Run preparation.

This module owns the **seam** for turning a raw ``RunCreateRequest`` into a
ready-to-execute **Run**.  Behind one small **interface**
``prepare_run(body, thread_id, request)`` it concentrates:

* evidence validation + ``body_context`` enrichment,
* parallel manifest verification (file IO) and canonical alias resolution (DB),
* single-transaction canonical snapshot freeze + factory build,
* selection metadata fetch,
* unified compensating discard on failure,
* background Memory cache warming for the graph-time injection read.

Callers learn one function; all orchestration, parallelism, and cleanup have
**locality** here.  Deleting the module would scatter 6 sequential awaits and
3 duplicate discard branches back to each caller — the deletion test passes.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request

from app.gateway.canonical_agent_run_preparation import (
    prepare_canonical_agent_run as _prepare_canonical_agent_run,
)
from app.gateway.services import (
    _canonical_assistant_id,
    _canonical_selection_metadata,
    _discard_canonical_run_snapshot,
    validate_evidence_selection,
)
from ideer.agents.memory import get_memory_data
from ideer.config.app_config import get_app_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedRun:
    """Result of :func:`prepare_run` — everything ``start_run`` needs after preparation."""

    canonical_resource_id: str | None
    canonical_factory: Any | None
    canonical_run_id: str | None
    evidence_mode: str
    code_package_id: str | None
    body_context: dict[str, Any]
    model_name: str | None
    run_metadata: dict[str, Any]
    # T5: background Memory cache warmer (may be None when injection is off
    # or no user is on the request). start_run retrieves it before spawning
    # the worker; the graph-time load then hits the warmed cache.
    memory_preload_task: asyncio.Task | None = None


async def _read_manifest_if_needed(thread_id: str, code_package_id: str | None) -> dict[str, Any] | None:
    if not code_package_id:
        return
    from ideer.uploads.code_evidence import read_manifest

    try:
        return await asyncio.to_thread(read_manifest, thread_id, str(code_package_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail="Code Evidence Package was not found for this Thread") from exc


async def _resolve_candidate_alias(candidate: str | None, request: Request) -> str | None:
    if not candidate:
        return None
    # Import lazily to avoid circular import at module load.
    from app.gateway.services import _resolve_canonical_alias

    return await _resolve_canonical_alias(candidate, request)


def _memory_injection_enabled() -> bool:
    """Whether a graph-time Memory read will happen (gate the preload)."""
    try:
        memory_config = get_app_config().memory
    except Exception:
        return False
    return bool(getattr(memory_config, "enabled", False)) and bool(getattr(memory_config, "injection_enabled", False))


async def _preload_memory(agent_name: str | None, user_id: str) -> None:
    """Warm the Memory storage cache in a worker thread. Never raises."""
    try:
        await asyncio.to_thread(get_memory_data, agent_name, user_id=user_id)
    except Exception:
        logger.debug("Memory preload failed (non-fatal)", exc_info=True)


async def prepare_run(body: Any, thread_id: str, request: Request) -> PreparedRun:
    """Prepare a Run, parallelising independent IO.

    The **interface** is one function; the **implementation** parallelises the
    two independent pre-steps (manifest file check vs alias DB lookup) via
    ``asyncio.gather``, then does the dependent snapshot freeze sequentially.
    """

    # 1. Validate evidence and enrich body_context (sync, no IO).
    body_context: dict[str, Any] = dict(getattr(body, "context", None) or {})
    evidence_mode, code_package_id = validate_evidence_selection(
        getattr(body, "evidence_mode", None) or body_context.get("evidence_mode"),
        getattr(body, "code_package_id", None) or body_context.get("code_package_id"),
    )
    body_context = {**body_context, "evidence_mode": evidence_mode}
    if code_package_id:
        body_context["code_package_id"] = str(code_package_id)
    body_context["code_evidence_source"] = f"/mnt/user-data/code-evidence/{code_package_id}/source" if code_package_id else None

    model_name = body_context.get("model_name")
    if model_name is not None and not isinstance(model_name, str):
        model_name = str(model_name)
        body_context["model_name"] = model_name

    if model_name:
        app_config = get_app_config()
        if app_config.get_model_config(model_name) is None:
            raise HTTPException(
                status_code=400,
                detail=f"Model {model_name!r} is not in the configured model allowlist",
            )

    # 2. Determine canonical resource id — direct UUID vs alias path.
    canonical_resource_id = _canonical_assistant_id(getattr(body, "assistant_id", None))
    if canonical_resource_id is None:
        canonical_resource_id = _canonical_assistant_id(body_context.get("agent_name"))

    needs_alias = canonical_resource_id is None and not body_context.get("is_bootstrap") and (body_context.get("agent_name") or getattr(body, "assistant_id", None))
    candidate = (body_context.get("agent_name") or getattr(body, "assistant_id", None)) if needs_alias else None

    # 3. Parallelise independent IO: manifest file check vs alias DB lookup.
    manifest_task = None
    alias_task = None
    if code_package_id:
        manifest_task = asyncio.create_task(_read_manifest_if_needed(thread_id, code_package_id))
    if candidate:
        alias_task = asyncio.create_task(_resolve_candidate_alias(candidate, request))

    if manifest_task is not None:
        manifest = await manifest_task
        if manifest:
            # Only pass server-derived summary fields to the runtime. The
            # expert receives a fixed virtual root, never an arbitrary host path.
            body_context["code_evidence_manifest"] = {
                "package_id": str(manifest.get("package_id", code_package_id)),
                "original_filename": str(manifest.get("original_filename", "")),
                "accepted_count": len(manifest.get("accepted", [])),
                "excluded_count": len(manifest.get("excluded", [])),
                "rejected_count": len(manifest.get("rejected", [])),
            }
    if alias_task is not None:
        resolved = await alias_task
        if resolved:
            canonical_resource_id = resolved

    # T5: warm the Memory cache concurrently with the snapshot freeze below.
    # The graph-time load uses (canonical id | None, user id) as its key, so
    # warming the same key turns it into a single stat call. First turns need
    # Memory the most (full reminder injection), so there is no no-history skip.
    memory_preload_task: asyncio.Task | None = None
    preload_user_id = getattr(getattr(request.state, "user", None), "id", None)
    if preload_user_id is not None and _memory_injection_enabled():
        memory_preload_task = asyncio.create_task(_preload_memory(canonical_resource_id, str(preload_user_id)))

    # 4. Freeze canonical snapshot + factory (dependent on canonical_resource_id).
    # T1 first-token timing: snapshot freeze is the heaviest pre-token segment.
    snapshot_started = time.perf_counter()
    canonical_run_id = str(uuid.uuid4()) if canonical_resource_id else None
    preferred_skill = body_context.get("skill_resource_id") or body_context.get("skill_name")
    canonical_factory = None
    if canonical_resource_id and canonical_run_id:
        prepare_kwargs = {"preferred_skill": preferred_skill} if preferred_skill else {}
        prepare_kwargs.update(
            diagnostic_context=body_context,
            thread_id=thread_id,
        )
        canonical_factory = await _prepare_canonical_agent_run(
            canonical_resource_id,
            request,
            canonical_run_id,
            **prepare_kwargs,
        )

    # 5. Build run metadata (depends on snapshot).
    run_metadata: dict[str, Any] = dict(getattr(body, "metadata", None) or {})
    run_metadata["evidence_mode"] = evidence_mode
    if code_package_id:
        run_metadata["code_package_id"] = str(code_package_id)
    if canonical_run_id and canonical_resource_id:
        run_metadata.update(await _canonical_selection_metadata(canonical_run_id, canonical_resource_id, body_context))

    logger.info(
        "first_token_timing stage=snapshot elapsed_ms=%.1f thread_id=%s has_canonical=%s",
        (time.perf_counter() - snapshot_started) * 1000,
        thread_id,
        canonical_resource_id is not None,
    )
    return PreparedRun(
        canonical_resource_id=canonical_resource_id,
        canonical_factory=canonical_factory,
        canonical_run_id=canonical_run_id,
        evidence_mode=evidence_mode,
        code_package_id=code_package_id,
        body_context=body_context,
        model_name=model_name,
        run_metadata=run_metadata,
        memory_preload_task=memory_preload_task,
    )


async def discard_canonical_snapshot(run_id: str | None) -> None:
    """Unified compensating action — one place to discard a prepared snapshot."""
    if run_id:
        await _discard_canonical_run_snapshot(run_id)
