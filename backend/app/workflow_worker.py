"""Process entrypoint for the single durable workflow worker."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from functools import partial
from typing import Any

import yaml
from langgraph.types import Command

from ideer.config import get_app_config
from ideer.persistence.engine import close_engine, get_session_factory, init_engine_from_config
from ideer.persistence.models.workflow_v2 import WorkflowTaskRow
from ideer.runtime.checkpointer.async_provider import make_checkpointer
from ideer.workflows.v2.adapters import build_default_registry
from ideer.workflows.v2.compiler import WorkflowCancelled, WorkflowGraphCompiler
from ideer.workflows.v2.file_roots import make_host_resolver, validate_read_roots, validate_workflow_roots, workflow_log_root
from ideer.workflows.v2.parser import parse_workflow_v2
from ideer.workflows.v2.run_record import RunRecordWriter
from ideer.workflows.v2.store import WorkflowV2Store
from ideer.workflows.v2.worker import WorkflowPaused, WorkflowWorker, workflow_snapshot


async def execute_workflow_task(
    task: WorkflowTaskRow,
    *,
    store: WorkflowV2Store,
    config: Any,
    registry_factory: Callable[[Any, str], Any] = build_default_registry,
    checkpointer_factory: Callable[[Any], AbstractAsyncContextManager[Any]] = make_checkpointer,
) -> None:
    """Execute one claimed task through the production graph and event chain."""
    run_id = task.run_id
    run = await store.get_run(run_id)
    if run is None:
        raise RuntimeError(f"workflow run '{run_id}' not found")
    version = await store.get_definition(run.workflow_name, run.definition_version)
    if version is None:
        raise RuntimeError(f"workflow definition {run.workflow_name}@{run.definition_version} not found")
    definition = parse_workflow_v2(yaml.safe_dump(version.definition))
    adapters = registry_factory(config, run.created_by)
    if task.resume_command_id is not None:
        command = await store.get_command(task.resume_command_id)
        if command is None:
            raise RuntimeError(f"workflow task '{task.task_id}' has no resume command")
        # LangGraph treats an empty dict as a resume map with no entries, so a
        # payload-less resume would never deliver a value and the interrupt gate
        # would re-raise on every attempt. Normalize to an explicit value.
        resume_value = command.payload if command.payload else {"resumed": True}
        invocation = Command(resume=resume_value)
        # The attempt-budget exemption applies to the immediate resume only;
        # a later crash/take-over must count as a fresh attempt again.
        await store.clear_resume_command(task.task_id)
    else:
        invocation = {"run_id": run_id, "inputs": run.inputs, "state": {}, "outputs": {}}

    event_limit = config.workflow_runtime.max_events_per_run

    async def emit_event(event_type: str, payload: dict) -> None:
        event = await store.append_event(
            run_id,
            event_type,
            payload,
            worker_id=task.lease_owner,
            max_events=event_limit - 1,
        )
        if event is None:
            raise RuntimeError("workflow_event_limit_exceeded")

    async def emit_terminal_event(event_type: str, payload: dict) -> None:
        await store.append_event(
            run_id,
            event_type,
            payload,
            worker_id=task.lease_owner,
            max_events=event_limit,
        )

    async with checkpointer_factory(config) as checkpointer:
        graph = WorkflowGraphCompiler(
            definition,
            adapters,
            emit_event=emit_event,
            is_cancelled=lambda: store.is_cancel_requested(run_id),
            node_timeout_seconds=config.workflow_runtime.node_timeout_seconds,
            artifact_resolver=make_host_resolver(run_id, run.created_by),
        ).compile(checkpointer=checkpointer)
        try:
            invalid_roots = validate_workflow_roots(definition.nodes, run.inputs)
            if invalid_roots:
                raise RuntimeError("invalid file_access roots: " + "; ".join(invalid_roots))
            missing_read_roots = validate_read_roots(definition.nodes, run.inputs, make_host_resolver(run_id, run.created_by))
            if missing_read_roots:
                raise RuntimeError("missing input roots: " + "; ".join(missing_read_roots))
            await emit_event("resumed" if task.resume_command_id is not None else "run_started", {"definition_version": run.definition_version})
            result = await graph.ainvoke(
                invocation,
                config={
                    "configurable": {"thread_id": run.checkpoint_thread_id},
                    "max_concurrency": config.workflow_runtime.max_parallel_actions,
                },
            )
        except WorkflowCancelled as exc:
            await emit_terminal_event("run_cancelled", {"error": str(exc)})
            raise
        except Exception as exc:
            await emit_terminal_event("run_failed", {"error": str(exc)})
            raise
    snapshot = workflow_snapshot(result)
    if not await store.update_snapshot(run_id, snapshot, worker_id=task.lease_owner):
        return
    if "__interrupt__" in result:
        await emit_event("interrupted", {"value": snapshot["interrupt"]})
        raise WorkflowPaused
    await emit_terminal_event("run_completed", {})


async def run_worker() -> None:
    config = get_app_config()
    if config.database.backend == "memory":
        raise RuntimeError("workflow-worker requires a durable database backend")
    await init_engine_from_config(config.database)
    sf = get_session_factory()
    if sf is None:
        raise RuntimeError("workflow-worker could not initialize persistence")
    store = WorkflowV2Store(sf)
    writers: dict[str, RunRecordWriter] = {}

    async def record_sink(run, event) -> None:
        writer = writers.get(run.run_id)
        if writer is None:
            writer = RunRecordWriter(make_host_resolver(run.run_id, str(run.created_by)), workflow_log_root())
            writers[run.run_id] = writer
        if event is not None:
            await writer.on_event(event)
        if run.status in {"completed", "failed", "cancelled"}:
            await writer.finalize(store, run)
            writers.pop(run.run_id, None)

    store.event_sink = record_sink

    try:
        runtime = config.workflow_runtime
        # Default to a per-process id: two workers on one machine must never
        # share the default lease owner, or they race to claim the same task.
        await WorkflowWorker(
            store,
            partial(execute_workflow_task, store=store, config=config),
            os.getenv("WORKFLOW_WORKER_ID") or f"workflow-worker-{os.getpid()}",
            lease_seconds=runtime.lease_seconds,
            heartbeat_seconds=runtime.heartbeat_seconds,
            max_attempts=runtime.max_attempts,
        ).run_forever()
    finally:
        await close_engine()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
