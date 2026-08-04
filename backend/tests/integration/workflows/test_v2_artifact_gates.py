"""Artifact gate acceptance: missing outputs pause the run, resume continues.

These tests exercise the production compiler with a real SQLite checkpointer
and an artifact resolver, covering:

- a node that declares write roots but produces nothing pauses the run with
  an ``artifacts_missing`` interrupt instead of completing
- the paused node re-runs from its checkpoint after resume and completes
- the artifact gate participates in the retry policy (a later attempt that
  writes the files passes)
- nodes without write roots are never gated
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import pytest_asyncio
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ideer.persistence.base import Base
from ideer.persistence.models.workflow_v2 import WorkflowTaskRow
from ideer.workflows.v2.adapters import ActionAdapterRegistry
from ideer.workflows.v2.compiler import WorkflowGraphCompiler
from ideer.workflows.v2.file_roots import make_host_resolver
from ideer.workflows.v2.parser import parse_workflow_v2
from ideer.workflows.v2.store import WorkflowV2Store
from ideer.workflows.v2.worker import WorkflowPaused, WorkflowWorker, workflow_snapshot

_GATED_WORKFLOW = """
schema_version: 2
name: gated
inputs: {}
state: {}
entrypoint: produce
nodes:
  - id: produce
    type: action
    action:
      kind: agent
      name: record
      file_access:
        read: []
        write:
          - "/mnt/user-data/outputs/artifact.json"
    retry:
      max_attempts: 2
      backoff_seconds: 0
  - id: plain
    type: action
    action: {kind: agent, name: record}
edges:
  - {from: produce, to: plain}
"""

_PLAIN_WORKFLOW = """
schema_version: 2
name: plain
inputs: {}
state: {}
entrypoint: produce
nodes:
  - id: produce
    type: action
    action: {kind: agent, name: record}
edges: []
"""


@pytest_asyncio.fixture
async def durable_store(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'workflow.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield WorkflowV2Store(async_sessionmaker(engine, expire_on_commit=False))
    finally:
        await engine.dispose()


def _resolver(run_id: str) -> Callable[[str], str | None]:
    return make_host_resolver(run_id, "user-1")


def _executor(
    store: WorkflowV2Store,
    checkpoint_path: Path,
    calls: list[str],
    *,
    definition_yaml: str = _GATED_WORKFLOW,
    should_write: Callable[[int], bool] = lambda _attempt: True,
    base_dir: Path,
) -> Callable[[WorkflowTaskRow], None]:
    """Production graph path with an artifact resolver pinned to base_dir."""

    async def execute(task: WorkflowTaskRow) -> None:
        run = await store.get_run(task.run_id)
        assert run is not None
        definition = parse_workflow_v2(definition_yaml)
        import ideer.workflows.v2.file_roots as file_roots
        from ideer.config.paths import Paths

        file_roots.get_paths = lambda: Paths(str(base_dir))

        class Adapter:
            async def run(self, context, params):
                calls.append(context.idempotency_key)
                attempt = len(calls)
                if should_write(attempt):
                    for root in (context.file_access or {}).get("write", []):
                        host = make_host_resolver(run.run_id, "user-1")(root)
                        assert host is not None
                        path = Path(host)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text("{}", encoding="utf-8")
                return {"node": context.node_id}

        async def emit(event_type: str, payload: dict) -> None:
            await store.append_event(task.run_id, event_type, payload)

        async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
            await checkpointer.setup()
            graph = WorkflowGraphCompiler(
                definition,
                ActionAdapterRegistry({("agent", "record"): Adapter()}),
                emit_event=emit,
                artifact_resolver=_resolver(run.run_id),
            ).compile(checkpointer=checkpointer)
            if task.resume_command_id is None:
                invocation = {"run_id": task.run_id, "inputs": run.inputs, "state": {}, "outputs": {}}
            else:
                command = await store.get_command(task.resume_command_id)
                assert command is not None
                invocation = Command(resume=command.payload)
            result = await graph.ainvoke(invocation, config={"configurable": {"thread_id": run.checkpoint_thread_id}})
        snapshot = workflow_snapshot(result)
        assert await store.update_snapshot(task.run_id, snapshot, worker_id=task.lease_owner)
        if "__interrupt__" in result:
            await store.append_event(task.run_id, "interrupted", {"value": snapshot["interrupt"]})
            raise WorkflowPaused
        await store.append_event(task.run_id, "run_completed", {})

    return execute


async def _create_gated_run(store: WorkflowV2Store, run_id: str) -> None:
    await store.save_definition("gated", {}, "hash", "user-1")
    await store.create_run(run_id, "gated", 1, {}, "user-1")


@pytest.mark.asyncio
async def test_missing_artifacts_pause_then_resume_continues(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
) -> None:
    await _create_gated_run(durable_store, "run-gate")
    calls: list[str] = []
    write_fixed = {"fixed": False}
    execute = _executor(
        durable_store,
        tmp_path / "checkpoints.db",
        calls,
        should_write=lambda _attempt: write_fixed["fixed"],
        base_dir=tmp_path,
    )

    assert await WorkflowWorker(durable_store, execute).run_once() is True
    paused = await durable_store.get_run("run-gate")
    assert paused is not None and paused.status == "paused"
    assert calls == ["wf:run-gate:node:produce", "wf:run-gate:node:produce"]  # 2 attempts, then paused
    interrupt_value = paused.snapshot["interrupt"][0]
    assert interrupt_value == {
        "type": "artifacts_missing",
        "node_id": "produce",
        "missing": ["/mnt/user-data/outputs/artifact.json"],
    }
    events = await durable_store.list_events("run-gate")
    assert [event.event_type for event in events].count("node_failed") == 0

    await durable_store.submit_command("resume-1", "run-gate", "resume", {"approved": True}, "super-admin")
    assert await WorkflowWorker(durable_store, execute).run_once() is True

    re_paused = await durable_store.get_run("run-gate")
    assert re_paused is not None and re_paused.status == "paused"  # environment not fixed yet

    write_fixed["fixed"] = True
    await durable_store.submit_command("resume-2", "run-gate", "resume", {"approved": True}, "super-admin")
    assert await WorkflowWorker(durable_store, execute).run_once() is True

    completed = await durable_store.get_run("run-gate")
    assert completed is not None and completed.status == "completed"
    assert calls == [
        "wf:run-gate:node:produce",
        "wf:run-gate:node:produce",
        "wf:run-gate:node:produce",  # resume re-run from checkpoint
        "wf:run-gate:node:produce",  # still missing -> paused again
        "wf:run-gate:node:produce",  # second resume re-run writes the file
        "wf:run-gate:node:plain",
    ]
    assert completed.snapshot["outputs"] == {"produce": {"node": "produce"}, "plain": {"node": "plain"}}


@pytest.mark.asyncio
async def test_retry_policy_covers_the_artifact_gate(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
) -> None:
    await _create_gated_run(durable_store, "run-gate-retry")
    calls: list[str] = []
    execute = _executor(
        durable_store,
        tmp_path / "checkpoints.db",
        calls,
        should_write=lambda attempt: attempt == 2,
        base_dir=tmp_path,
    )

    assert await WorkflowWorker(durable_store, execute).run_once() is True

    completed = await durable_store.get_run("run-gate-retry")
    assert completed is not None and completed.status == "completed"
    assert calls == ["wf:run-gate-retry:node:produce", "wf:run-gate-retry:node:produce", "wf:run-gate-retry:node:plain"]
    events = await durable_store.list_events("run-gate-retry")
    assert [event.event_type for event in events].count("interrupted") == 0


@pytest.mark.asyncio
async def test_nodes_without_write_roots_are_not_gated(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
) -> None:
    await durable_store.save_definition("plain", {}, "hash", "user-1")
    await durable_store.create_run("run-gate-plain", "plain", 1, {}, "user-1")
    calls: list[str] = []
    execute = _executor(
        durable_store,
        tmp_path / "checkpoints.db",
        calls,
        definition_yaml=_PLAIN_WORKFLOW,
        should_write=lambda _attempt: False,
        base_dir=tmp_path,
    )

    assert await WorkflowWorker(durable_store, execute).run_once() is True

    completed = await durable_store.get_run("run-gate-plain")
    assert completed is not None and completed.status == "completed"
    assert calls == ["wf:run-gate-plain:node:produce"]
