"""Precondition gates: unsatisfied node inputs fail loudly with specific errors.

Covers parse-time rejection of precondition files outside a node's read roots
and runtime failure with a concrete reason (missing file, no matching JSON
value), plus a satisfied precondition letting the node run.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
import pytest_asyncio
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ideer.persistence.base import Base
from ideer.persistence.models.workflow_v2 import WorkflowTaskRow
from ideer.workflows.v2.adapters import ActionAdapterRegistry
from ideer.workflows.v2.compiler import WorkflowGraphCompiler
from ideer.workflows.v2.file_roots import make_host_resolver
from ideer.workflows.v2.parser import parse_workflow_v2
from ideer.workflows.v2.store import WorkflowV2Store
from ideer.workflows.v2.worker import WorkflowWorker, workflow_snapshot

_PRECOND_WORKFLOW = """
schema_version: 2
name: precond
inputs: {}
state: {}
entrypoint: gate
nodes:
  - id: gate
    type: action
    action:
      kind: agent
      name: record
      file_access:
        read:
          - "/mnt/user-data/outputs"
        write: []
    preconditions:
      - file: "/mnt/user-data/outputs/fault_tree.json"
        non_empty: true
        json_path: "$.root_causes[*].status"
        some_equals: confirmed
  - id: done
    type: action
    action: {kind: agent, name: record}
edges:
  - {from: gate, to: done}
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
    base_dir: Path,
):
    async def execute(task: WorkflowTaskRow) -> None:
        run = await store.get_run(task.run_id)
        assert run is not None
        definition = parse_workflow_v2(_PRECOND_WORKFLOW)
        import ideer.workflows.v2.file_roots as file_roots
        from ideer.config.paths import Paths

        file_roots.get_paths = lambda: Paths(str(base_dir))

        class Adapter:
            async def run(self, context, params):
                calls.append(context.node_id)
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
            result = await graph.ainvoke(
                {"run_id": task.run_id, "inputs": run.inputs, "state": {}, "outputs": {}},
                config={"configurable": {"thread_id": run.checkpoint_thread_id}},
            )
        snapshot = workflow_snapshot(result)
        await store.update_snapshot(task.run_id, snapshot, worker_id=task.lease_owner)
        await store.append_event(task.run_id, "run_completed", {})

    return execute


def test_parse_rejects_precondition_file_outside_read_roots() -> None:
    content = """
schema_version: 2
name: bad
inputs: {}
state: {}
entrypoint: gate
nodes:
  - id: gate
    type: action
    action: {kind: agent, name: record}
    preconditions:
      - file: "/etc/passwd"
        non_empty: true
edges: []
"""
    with pytest.raises(ValueError, match="is not under its read roots"):
        parse_workflow_v2(content)


def test_parse_rejects_invalid_precondition_combinations() -> None:
    content = """
schema_version: 2
name: bad
inputs: {}
state: {}
entrypoint: gate
nodes:
  - id: gate
    type: action
    action:
      kind: agent
      name: record
      file_access:
        read:
          - "/mnt/user-data/outputs"
        write: []
    preconditions:
      - file: "/mnt/user-data/outputs/fault_tree.json"
        some_equals: confirmed
        none_equals: pending
edges: []
"""
    with pytest.raises(ValueError, match="cannot set both some_equals and none_equals"):
        parse_workflow_v2(content)


async def _run_to_terminal(store: WorkflowV2Store, run_id: str, execute) -> None:
    assert await WorkflowWorker(store, execute).run_once() is True


@pytest.mark.asyncio
async def test_precondition_failure_fails_node_with_specific_reason(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
) -> None:
    import ideer.workflows.v2.file_roots as file_roots
    from ideer.config.paths import Paths

    file_roots.get_paths = lambda: Paths(str(tmp_path))
    await durable_store.save_definition("precond", {}, "hash", "user-1")
    await durable_store.create_run("run-pre", "precond", 1, {}, "user-1")

    outputs = make_host_resolver("run-pre", "user-1")("/mnt/user-data/outputs")
    assert outputs is not None
    tree_path = Path(outputs)
    tree_path.mkdir(parents=True, exist_ok=True)
    (tree_path / "fault_tree.json").write_text(
        json.dumps({"root_causes": [{"id": "RC-01", "status": "to_verify"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    calls: list[str] = []
    execute = _executor(durable_store, tmp_path / "checkpoints.db", calls, base_dir=tmp_path)
    await _run_to_terminal(durable_store, "run-pre", execute)

    failed = await durable_store.get_run("run-pre")
    assert failed is not None and failed.status == "failed"
    assert failed.error is not None
    assert "precondition" in failed.error and "confirmed" in failed.error
    assert calls == []  # node never ran its adapter
    events = await durable_store.list_events("run-pre")
    details = [event.payload.get("error", "") for event in events if event.event_type == "node_failed"]
    assert details and details[0].startswith("node 'gate' precondition failed:")


@pytest.mark.asyncio
async def test_precondition_pass_runs_the_node(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
) -> None:
    import ideer.workflows.v2.file_roots as file_roots
    from ideer.config.paths import Paths

    file_roots.get_paths = lambda: Paths(str(tmp_path))
    await durable_store.save_definition("precond", {}, "hash", "user-1")
    await durable_store.create_run("run-ok", "precond", 1, {}, "user-1")

    outputs = make_host_resolver("run-ok", "user-1")("/mnt/user-data/outputs")
    assert outputs is not None
    tree_path = Path(outputs)
    tree_path.mkdir(parents=True, exist_ok=True)
    (tree_path / "fault_tree.json").write_text(
        json.dumps({"root_causes": [{"id": "RC-01", "status": "confirmed"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    calls: list[str] = []
    execute = _executor(durable_store, tmp_path / "checkpoints.db", calls, base_dir=tmp_path)
    await _run_to_terminal(durable_store, "run-ok", execute)

    completed = await durable_store.get_run("run-ok")
    assert completed is not None and completed.status == "completed"
    assert calls == ["gate", "done"]
