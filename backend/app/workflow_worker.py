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
from ideer.workflows.v2.parser import parse_workflow_v2
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
        invocation = Command(resume=command.payload)
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
        ).compile(checkpointer=checkpointer)
        try:
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

    try:
        runtime = config.workflow_runtime
        await WorkflowWorker(
            store,
            partial(execute_workflow_task, store=store, config=config),
            os.getenv("WORKFLOW_WORKER_ID", "workflow-worker"),
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
