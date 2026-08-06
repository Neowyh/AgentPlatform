"""Write-after JSON schema gates: declared outputs must satisfy their schema.

Covers parse-time rejection of schema gates outside the node's roots and
runtime failure with a concrete schema-violation reason, plus a conforming
write letting the node complete.
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

_SCHEMA_GATED_WORKFLOW = """
schema_version: 2
name: schema-gated
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
        read:
          - "/mnt/user-data/outputs"
        write:
          - "/mnt/user-data/outputs/artifact.json"
    schemas:
      - file: "/mnt/user-data/outputs/artifact.json"
        schema_file: "/mnt/user-data/outputs/artifact.schema.json"
    retry:
      max_attempts: 2
      backoff_seconds: 0
edges: []
"""

_SCHEMA = json.dumps(
    {
        "type": "object",
        "required": ["status"],
        "properties": {"status": {"enum": ["confirmed", "rejected"]}},
    },
    ensure_ascii=False,
)


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
    payload: str,
    workflow_text: str = _SCHEMA_GATED_WORKFLOW,
    prompts: list[str] | None = None,
    payload_factory: Callable[[int], str] | None = None,
):
    async def execute(task: WorkflowTaskRow) -> None:
        run = await store.get_run(task.run_id)
        assert run is not None
        definition = parse_workflow_v2(workflow_text)
        import ideer.workflows.v2.file_roots as file_roots
        from ideer.config.paths import Paths

        file_roots.get_paths = lambda: Paths(str(base_dir))

        class Adapter:
            async def run(self, context, params):
                calls.append(context.idempotency_key)
                if prompts is not None:
                    prompts.append(str(params.get("prompt", params)))
                body = payload_factory(len(calls) - 1) if payload_factory is not None else payload
                for root in (context.file_access or {}).get("write", []):
                    host = make_host_resolver(run.run_id, "user-1")(root)
                    assert host is not None
                    path = Path(host)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(body, encoding="utf-8")
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


def test_parse_rejects_schema_gate_outside_node_roots() -> None:
    content = """
schema_version: 2
name: bad
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
        read:
          - "/mnt/user-data/outputs"
        write:
          - "/mnt/user-data/outputs/artifact.json"
    schemas:
      - file: "/etc/artifact.json"
        schema_file: "/mnt/user-data/outputs/artifact.schema.json"
edges: []
"""
    with pytest.raises(ValueError, match="schema target '/etc/artifact.json' is not under its write roots"):
        parse_workflow_v2(content)


@pytest.mark.asyncio
async def test_schema_violation_fails_node_with_specific_reason(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
) -> None:
    import ideer.workflows.v2.file_roots as file_roots
    from ideer.config.paths import Paths

    file_roots.get_paths = lambda: Paths(str(tmp_path))
    await durable_store.save_definition("schema-gated", {}, "hash", "user-1")
    await durable_store.create_run("run-bad-schema", "schema-gated", 1, {}, "user-1")

    outputs = make_host_resolver("run-bad-schema", "user-1")("/mnt/user-data/outputs")
    assert outputs is not None
    outputs_path = Path(outputs)
    outputs_path.mkdir(parents=True, exist_ok=True)
    (outputs_path / "artifact.schema.json").write_text(_SCHEMA, encoding="utf-8")

    calls: list[str] = []
    execute = _executor(
        durable_store,
        tmp_path / "checkpoints.db",
        calls,
        base_dir=tmp_path,
        payload=json.dumps({"status": "to_verify"}, ensure_ascii=False),
    )
    assert await WorkflowWorker(durable_store, execute).run_once() is True

    failed = await durable_store.get_run("run-bad-schema")
    assert failed is not None and failed.status == "failed"
    assert failed.error is not None
    assert "schema validation failed" in failed.error and "confirmed" in failed.error
    events = await durable_store.list_events("run-bad-schema")
    details = [event.payload.get("error", "") for event in events if event.event_type == "node_failed"]
    assert details and "schema validation failed" in details[0]


@pytest.mark.asyncio
async def test_schema_conforming_write_completes_the_node(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
) -> None:
    import ideer.workflows.v2.file_roots as file_roots
    from ideer.config.paths import Paths

    file_roots.get_paths = lambda: Paths(str(tmp_path))
    await durable_store.save_definition("schema-gated", {}, "hash", "user-1")
    await durable_store.create_run("run-ok-schema", "schema-gated", 1, {}, "user-1")

    outputs = make_host_resolver("run-ok-schema", "user-1")("/mnt/user-data/outputs")
    assert outputs is not None
    outputs_path = Path(outputs)
    outputs_path.mkdir(parents=True, exist_ok=True)
    (outputs_path / "artifact.schema.json").write_text(_SCHEMA, encoding="utf-8")

    calls: list[str] = []
    execute = _executor(
        durable_store,
        tmp_path / "checkpoints.db",
        calls,
        base_dir=tmp_path,
        payload=json.dumps({"status": "confirmed"}, ensure_ascii=False),
    )
    assert await WorkflowWorker(durable_store, execute).run_once() is True

    completed = await durable_store.get_run("run-ok-schema")
    assert completed is not None and completed.status == "completed"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_schema_violation_feedback_injected_on_retry(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
) -> None:
    import ideer.workflows.v2.file_roots as file_roots
    from ideer.config.paths import Paths

    file_roots.get_paths = lambda: Paths(str(tmp_path))
    await durable_store.save_definition("schema-gated", {}, "hash", "user-1")
    await durable_store.create_run("run-feedback-schema", "schema-gated", 1, {}, "user-1")

    outputs = make_host_resolver("run-feedback-schema", "user-1")("/mnt/user-data/outputs")
    assert outputs is not None
    outputs_path = Path(outputs)
    outputs_path.mkdir(parents=True, exist_ok=True)
    (outputs_path / "artifact.schema.json").write_text(_SCHEMA, encoding="utf-8")

    calls: list[str] = []
    prompts: list[str] = []
    execute = _executor(
        durable_store,
        tmp_path / "checkpoints.db",
        calls,
        base_dir=tmp_path,
        payload="",
        prompts=prompts,
        payload_factory=lambda attempt: json.dumps(
            {"status": "to_verify"} if attempt == 0 else {"status": "confirmed"},
            ensure_ascii=False,
        ),
    )
    assert await WorkflowWorker(durable_store, execute).run_once() is True

    completed = await durable_store.get_run("run-feedback-schema")
    assert completed is not None and completed.status == "completed"
    assert len(calls) == 2
    assert len(prompts) == 2
    assert prompts[1] != prompts[0]
    assert "schema" in prompts[1]
    assert "$.status" in prompts[1]
    assert "'to_verify'" in prompts[1]

    events = await durable_store.list_events("run-feedback-schema")
    progress = [event.payload.get("message", "") for event in events if event.event_type == "action_progress"]
    assert progress and "第 1 次尝试" in progress[0] and "$.status" in progress[0]


@pytest.mark.asyncio
async def test_schema_violations_aggregated_in_error(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
) -> None:
    import ideer.workflows.v2.file_roots as file_roots
    from ideer.config.paths import Paths

    aggregate_schema = json.dumps(
        {
            "type": "object",
            "required": ["status", "grade"],
            "properties": {
                "status": {"enum": ["confirmed", "rejected"]},
                "grade": {"enum": ["A", "B"]},
            },
        },
        ensure_ascii=False,
    )

    file_roots.get_paths = lambda: Paths(str(tmp_path))
    await durable_store.save_definition("schema-gated", {}, "hash", "user-1")
    await durable_store.create_run("run-agg-schema", "schema-gated", 1, {}, "user-1")

    outputs = make_host_resolver("run-agg-schema", "user-1")("/mnt/user-data/outputs")
    assert outputs is not None
    outputs_path = Path(outputs)
    outputs_path.mkdir(parents=True, exist_ok=True)
    (outputs_path / "artifact.schema.json").write_text(aggregate_schema, encoding="utf-8")

    calls: list[str] = []
    execute = _executor(
        durable_store,
        tmp_path / "checkpoints.db",
        calls,
        base_dir=tmp_path,
        payload=json.dumps({"status": "to_verify", "grade": "Z"}, ensure_ascii=False),
    )
    assert await WorkflowWorker(durable_store, execute).run_once() is True

    failed = await durable_store.get_run("run-agg-schema")
    assert failed is not None and failed.status == "failed"
    assert failed.error is not None
    assert "schema validation failed" in failed.error
    assert "to_verify" in failed.error and "'Z'" in failed.error
