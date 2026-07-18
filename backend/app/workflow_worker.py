"""Process entrypoint for the single durable workflow worker."""

from __future__ import annotations

import asyncio
import os

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


async def run_worker() -> None:
    config = get_app_config()
    if config.database.backend == "memory":
        raise RuntimeError("workflow-worker requires a durable database backend")
    await init_engine_from_config(config.database)
    sf = get_session_factory()
    if sf is None:
        raise RuntimeError("workflow-worker could not initialize persistence")
    store = WorkflowV2Store(sf)

    async def execute(task: WorkflowTaskRow) -> None:
        run_id = task.run_id
        run = await store.get_run(run_id)
        if run is None:
            raise RuntimeError(f"workflow run '{run_id}' not found")
        version = await store.get_definition(run.workflow_name, run.definition_version)
        if version is None:
            raise RuntimeError(f"workflow definition {run.workflow_name}@{run.definition_version} not found")
        definition = parse_workflow_v2(yaml.safe_dump(version.definition))
        adapters = build_default_registry(config, run.created_by)
        if task.resume_command_id is not None:
            command = await store.get_command(task.resume_command_id)
            if command is None:
                raise RuntimeError(f"workflow task '{task.task_id}' has no resume command")
            invocation = Command(resume=command.payload)
        else:
            invocation = {"run_id": run_id, "inputs": run.inputs, "state": {}, "outputs": {}}

        async def emit_event(event_type: str, payload: dict) -> None:
            await store.append_event(run_id, event_type, payload)

        async with make_checkpointer(config) as checkpointer:
            graph = WorkflowGraphCompiler(
                definition,
                adapters,
                emit_event=emit_event,
                is_cancelled=lambda: store.is_cancel_requested(run_id),
            ).compile(checkpointer=checkpointer)
            await store.append_event(run_id, "resumed" if task.resume_command_id is not None else "run_started", {"definition_version": run.definition_version})
            try:
                result = await graph.ainvoke(invocation, config={"configurable": {"thread_id": run.checkpoint_thread_id}})
            except WorkflowCancelled as exc:
                await store.append_event(run_id, "run_cancelled", {"error": str(exc)})
                raise
            except Exception as exc:
                await store.append_event(run_id, "run_failed", {"error": str(exc)})
                raise
        snapshot = workflow_snapshot(result)
        await store.update_snapshot(run_id, snapshot)
        if "__interrupt__" in result:
            await store.append_event(run_id, "interrupted", {"value": snapshot["interrupt"]})
            raise WorkflowPaused
        else:
            await store.append_event(run_id, "run_completed", {})

    try:
        await WorkflowWorker(store, execute, os.getenv("WORKFLOW_WORKER_ID", "workflow-worker")).run_forever()
    finally:
        await close_engine()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
