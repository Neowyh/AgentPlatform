"""Phase 1 acceptance coverage for the durable workflow-v2 runtime.

These tests intentionally use SQLite-backed workflow state and a persistent
LangGraph checkpointer.  They must not be replaced by store or compiler mocks:
the acceptance boundary is a worker claiming durable tasks across restarts.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.command import upgrade
from alembic.config import Config as AlembicConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ideer.persistence.base import Base
from ideer.persistence.models.workflow_v2 import WorkflowLeaseAuditRow, WorkflowTaskRow
from ideer.workflows.v2.adapters import ActionAdapterRegistry
from ideer.workflows.v2.compiler import WorkflowGraphCompiler
from ideer.workflows.v2.parser import parse_workflow_v2
from ideer.workflows.v2.store import WorkflowV2Store
from ideer.workflows.v2.worker import WorkflowPaused, WorkflowWorker, workflow_snapshot

_APPROVAL_WORKFLOW = """
schema_version: 2
name: approval
inputs: {}
state: {}
entrypoint: prepare
nodes:
  - id: prepare
    type: action
    action: {kind: tool, name: record}
  - id: review
    type: interrupt
    roles: [super_admin]
  - id: finish
    type: action
    action: {kind: tool, name: record}
edges:
  - {from: prepare, to: review}
  - {from: review, to: finish}
"""


@pytest_asyncio.fixture
async def durable_store(tmp_path: Path):
    """A real workflow DB whose state survives a worker restart."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'workflow.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield WorkflowV2Store(async_sessionmaker(engine, expire_on_commit=False))
    finally:
        await engine.dispose()


def _executor(
    store: WorkflowV2Store,
    checkpoint_path: Path,
    calls: list[str],
) -> Callable[[WorkflowTaskRow], Awaitable[None]]:
    """Use the production graph/compiler path with an on-disk checkpointer."""

    async def execute(task: WorkflowTaskRow) -> None:
        run = await store.get_run(task.run_id)
        assert run is not None
        definition = parse_workflow_v2(_APPROVAL_WORKFLOW)

        class Adapter:
            async def run(self, context, params):
                calls.append(context.idempotency_key)
                return {"node": context.node_id}

        async def emit(event_type: str, payload: dict) -> None:
            await store.append_event(task.run_id, event_type, payload)

        async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
            await checkpointer.setup()
            graph = WorkflowGraphCompiler(
                definition,
                ActionAdapterRegistry({("tool", "record"): Adapter()}),
                emit_event=emit,
            ).compile(checkpointer=checkpointer)
            if task.resume_command_id is None:
                invocation = {"run_id": task.run_id, "inputs": run.inputs, "state": {}, "outputs": {}}
                event_type = "run_started"
            else:
                command = await store.get_command(task.resume_command_id)
                assert command is not None
                invocation = Command(resume=command.payload)
                event_type = "resumed"
            await store.append_event(task.run_id, event_type, {})
            result = await graph.ainvoke(invocation, config={"configurable": {"thread_id": run.checkpoint_thread_id}})
        snapshot = workflow_snapshot(result)
        assert await store.update_snapshot(task.run_id, snapshot, worker_id=task.lease_owner)
        if "__interrupt__" in result:
            await store.append_event(task.run_id, "interrupted", {})
            raise WorkflowPaused
        await store.append_event(task.run_id, "run_completed", {})

    return execute


@pytest.mark.asyncio
async def test_worker_restart_resumes_only_pending_nodes_from_persistent_command(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
) -> None:
    """A paused run resumes from its checkpointer after a fresh worker starts."""
    await durable_store.save_definition("approval", {}, "hash", "user-1")
    await durable_store.create_run("run-1", "approval", 1, {}, "user-1")
    calls: list[str] = []
    execute = _executor(durable_store, tmp_path / "checkpoints.db", calls)

    assert await WorkflowWorker(durable_store, execute).run_once() is True
    paused = await durable_store.get_run("run-1")
    assert paused is not None and paused.status == "paused"
    assert calls == ["wf:run-1:node:prepare"]

    await durable_store.submit_command("resume-1", "run-1", "resume", {"approved": True}, "super-admin")
    assert await WorkflowWorker(durable_store, execute).run_once() is True

    completed = await durable_store.get_run("run-1")
    assert completed is not None and completed.status == "completed"
    assert calls == ["wf:run-1:node:prepare", "wf:run-1:node:finish"]
    events = await durable_store.list_events("run-1")
    assert [event.seq for event in events] == list(range(1, len(events) + 1))
    assert [event.event_type for event in events] == [
        "run_started",
        "node_started",
        "node_completed",
        "node_started",
        "interrupted",
        "resumed",
        "node_started",
        "node_completed",
        "node_started",
        "node_completed",
        "run_completed",
    ]
    assert completed.snapshot["outputs"] == {"prepare": {"node": "prepare"}, "finish": {"node": "finish"}}

    from app.gateway.routers.workflows import workflow_event_stream

    replayed = [chunk async for chunk in workflow_event_stream(durable_store, "run-1", after_seq=5, poll_seconds=0)]
    assert [int(chunk.split("\n", 1)[0].removeprefix("id: ")) for chunk in replayed] == list(range(6, len(events) + 1))


@pytest.mark.asyncio
async def test_expired_lease_is_taken_over_and_old_worker_cannot_finish(
    durable_store: WorkflowV2Store,
) -> None:
    await durable_store.save_definition("approval", {}, "hash", "user-1")
    await durable_store.create_run("run-takeover", "approval", 1, {}, "user-1")
    started = datetime.now(UTC)
    first = await durable_store.claim_next_task("worker-a", now=started, lease_seconds=1)
    assert first is not None
    second = await durable_store.claim_next_task("worker-b", now=started + timedelta(seconds=2), lease_seconds=30)
    assert second is not None and second.task_id == first.task_id

    assert await durable_store.finish_task(first.task_id, "completed", None, "worker-a") is False
    assert await durable_store.finish_task(second.task_id, "completed", None, "worker-b") is True
    run = await durable_store.get_run("run-takeover")
    assert run is not None and run.status == "completed"


@pytest.mark.asyncio
async def test_lease_claim_takeover_and_release_are_durably_audited(
    durable_store: WorkflowV2Store,
) -> None:
    await durable_store.save_definition("approval", {}, "hash", "user-1")
    await durable_store.create_run("run-lease-audit", "approval", 1, {}, "user-1")
    started = datetime.now(UTC)
    first = await durable_store.claim_next_task("worker-a", now=started, lease_seconds=1)
    assert first is not None
    second = await durable_store.claim_next_task("worker-b", now=started + timedelta(seconds=2), lease_seconds=30)
    assert second is not None
    assert await durable_store.finish_task(second.task_id, "completed", None, "worker-b")

    async with durable_store.session_factory() as session:
        audits = list((await session.execute(text("SELECT event_type, worker_id, attempt FROM workflow_lease_audit WHERE run_id = 'run-lease-audit' ORDER BY created_at, id"))).all())

    assert audits == [
        ("claimed", "worker-a", 1),
        ("taken_over", "worker-b", 2),
        ("released", "worker-b", 2),
    ]


@pytest.mark.asyncio
async def test_event_limit_reserves_a_durable_terminal_failure_event(
    durable_store: WorkflowV2Store,
) -> None:
    await durable_store.save_definition("approval", {}, "hash", "user-1")
    await durable_store.create_run("run-event-limit", "approval", 1, {}, "user-1")

    normal = await durable_store.append_event("run-event-limit", "run_started", {}, max_events=1)
    rejected = await durable_store.append_event("run-event-limit", "node_started", {}, max_events=1)
    terminal = await durable_store.append_event(
        "run-event-limit",
        "run_failed",
        {"error": "workflow_event_limit_exceeded"},
        max_events=2,
    )
    overflow = await durable_store.append_event("run-event-limit", "run_completed", {}, max_events=2)

    assert normal is not None and normal.seq == 1
    assert rejected is None
    assert terminal is not None and terminal.seq == 2
    assert overflow is None
    assert [event.event_type for event in await durable_store.list_events("run-event-limit")] == ["run_started", "run_failed"]


@pytest.mark.asyncio
async def test_max_attempts_exhaustion_persists_a_failure_event(
    durable_store: WorkflowV2Store,
) -> None:
    await durable_store.save_definition("approval", {}, "hash", "user-1")
    await durable_store.create_run("run-max-attempts", "approval", 1, {}, "user-1")

    assert await durable_store.claim_next_task("worker-a", max_attempts=0) is None

    run = await durable_store.get_run("run-max-attempts")
    assert run is not None
    assert (run.status, run.error) == ("failed", "workflow_max_attempts_exceeded")
    events = await durable_store.list_events("run-max-attempts")
    assert [(event.event_type, event.payload) for event in events] == [("run_failed", {"error": "workflow_max_attempts_exceeded"})]


@pytest.mark.asyncio
async def test_second_worker_takes_over_a_dead_holder_from_durable_snapshot(
    durable_store: WorkflowV2Store,
) -> None:
    """Two real worker loops share one SQLite task without duplicating prior work."""
    await durable_store.save_definition("approval", {}, "hash", "user-1")
    await durable_store.create_run("run-dual-worker", "approval", 1, {}, "user-1")
    first_started = asyncio.Event()
    terminate_first = asyncio.Event()
    completed_actions: list[str] = []

    async def first_executor(task: WorkflowTaskRow) -> None:
        assert await durable_store.update_snapshot(
            task.run_id,
            {"outputs": {"prepare": {"node": "prepare"}}},
            worker_id="worker-a",
        )
        first_started.set()
        await terminate_first.wait()

    async def second_executor(task: WorkflowTaskRow) -> None:
        run = await durable_store.get_run(task.run_id)
        assert run is not None
        assert run.snapshot == {"outputs": {"prepare": {"node": "prepare"}}}
        completed_actions.append("finish")

    first = WorkflowWorker(
        durable_store,
        first_executor,
        worker_id="worker-a",
        lease_seconds=1,
        heartbeat_seconds=10,
    )
    second = WorkflowWorker(durable_store, second_executor, worker_id="worker-b", lease_seconds=30)
    first_task = asyncio.create_task(first.run_once())
    await first_started.wait()
    await asyncio.sleep(1.1)

    assert await second.run_once() is True
    terminate_first.set()
    assert await first_task is True

    run = await durable_store.get_run("run-dual-worker")
    assert run is not None and run.status == "completed"
    assert completed_actions == ["finish"]


@pytest.mark.asyncio
async def test_concurrent_claims_never_duplicate_a_task(durable_store: WorkflowV2Store) -> None:
    """Simultaneous claims from two workers must hand out each task at most once.

    Regression test for the pre-atomic claim race: workers SELECTed the same
    queued task before either UPDATE ran, so two workers executed one task.
    """
    await durable_store.save_definition("approval", {}, "hash", "user-1")
    for index in range(8):
        await durable_store.create_run(f"run-race-{index}", "approval", 1, {}, "user-1")

    claims = await asyncio.gather(*[durable_store.claim_next_task(f"worker-{index % 2}", lease_seconds=5) for index in range(32)])
    claimed = [task for task in claims if task is not None]
    task_ids = [task.task_id for task in claimed]
    assert len(task_ids) == len(set(task_ids)), f"duplicate claims: {task_ids}"
    assert len(task_ids) == 8

    async with durable_store.session_factory() as session:
        counts = dict((await session.execute(select(WorkflowLeaseAuditRow.task_id, func.count()).group_by(WorkflowLeaseAuditRow.task_id))).all())
    assert counts == {task_id: 1 for task_id in task_ids}


@pytest.mark.serial
def test_v1_runs_stay_readable_but_active_runs_are_failed_by_the_v2_migration(tmp_path: Path) -> None:
    """Upgrade a real v1 database instead of asserting migration call shapes."""
    migrations_dir = Path(__file__).resolve().parents[3] / "packages" / "harness" / "ideer" / "persistence" / "migrations"
    db_path = tmp_path / "legacy.db"
    config = AlembicConfig(str(migrations_dir / "alembic.ini"))
    config.set_main_option("script_location", str(migrations_dir))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    upgrade(config, "9a8b7c6d5e4f")

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO workflow_runs "
                "(run_id, workflow_name, workflow_yaml, status, inputs, steps_state, current_step, error, review_result, loop_vars, created_at, updated_at) "
                "VALUES ('legacy-active', 'approval', 'name: approval', 'running', '{}', '{}', NULL, NULL, NULL, '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
    engine.dispose()

    upgrade(config, "20260715_workflow_v2")
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as connection:
        row = connection.execute(text("SELECT status, error FROM workflow_runs WHERE run_id = 'legacy-active'")).one()
        v2_count = connection.execute(text("SELECT COUNT(*) FROM workflow_v2_runs")).scalar_one()
    engine.dispose()

    assert row == ("failed", "workflow_runtime_replaced")
    assert v2_count == 0
