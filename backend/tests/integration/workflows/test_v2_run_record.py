"""Run record persistence: JSONL event log + terminal Markdown summary.

These tests drive the production ``WorkflowV2Store`` with a real SQLite
database and the production ``RunRecordWriter`` resolver chain, covering:

- every appended event is mirrored to ``.workflow/logs/run_record.jsonl``
- the exhausted-run event written inside ``claim_next_task`` also reaches the
  record (the sink fires for it)
- a terminal run renders a Markdown summary with node sections
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ideer.persistence.base import Base
from ideer.persistence.models.workflow_v2 import WorkflowTaskRow
from ideer.workflows.v2.file_roots import make_host_resolver, workflow_log_root, workflow_record_path
from ideer.workflows.v2.run_record import RunRecordWriter
from ideer.workflows.v2.store import WorkflowV2Store


@pytest_asyncio.fixture
async def durable_store(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'workflow.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield WorkflowV2Store(async_sessionmaker(engine, expire_on_commit=False))
    finally:
        await engine.dispose()


def _resolver(base_dir: Path):
    import ideer.workflows.v2.file_roots as file_roots
    from ideer.config.paths import Paths

    file_roots.get_paths = lambda: Paths(str(base_dir))
    return make_host_resolver("run-1", "user-1")


@pytest.mark.asyncio
async def test_events_are_mirrored_to_jsonl_and_terminal_renders_markdown(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
) -> None:
    await durable_store.save_definition("wf", {}, "hash", "user-1")
    await durable_store.create_run("run-1", "wf", 1, {"case": "x"}, "user-1")

    writer = RunRecordWriter(_resolver(tmp_path), workflow_log_root())

    async def sink(run, event) -> None:
        if event is not None:
            await writer.on_event(event)
        if run.status in {"completed", "failed", "cancelled"}:
            await writer.finalize(durable_store, run)

    durable_store.event_sink = sink

    task = await durable_store.claim_next_task("worker-1", max_attempts=3)
    assert task is not None

    await durable_store.append_event("run-1", "run_started", {"definition_version": 1})
    await durable_store.append_event("run-1", "node_started", {"node_id": "a", "started_at": "2026-01-01T00:00:00+00:00"})
    await durable_store.append_event("run-1", "action_progress", {"node_id": "a", "message": "[回合 1] 调用工具 read_file → /mnt/user-data/uploads/case/a.txt"})
    await durable_store.append_event("run-1", "node_completed", {"node_id": "a", "result": "done", "finished_at": "2026-01-01T00:01:00+00:00"})

    jsonl_path = tmp_path / "users" / "user-1" / "threads" / "run-1" / "user-data" / "workspace" / ".workflow" / "logs" / "run_record.jsonl"
    assert jsonl_path.is_file()
    lines = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert [line["type"] for line in lines] == ["run_started", "node_started", "action_progress", "node_completed"]
    assert lines[2]["payload"]["message"].startswith("[回合 1] 调用工具 read_file")

    md_path = jsonl_path.with_suffix(".md")
    assert not md_path.exists()  # run not terminal yet

    await durable_store.append_event("run-1", "run_completed", {})
    assert not md_path.exists()  # status flips only when the worker releases the task
    assert await durable_store.finish_task(task.task_id, "completed", None, "worker-1") is True

    assert md_path.is_file()
    content = md_path.read_text(encoding="utf-8")
    assert "`run-1`" in content
    assert "`wf`" in content
    assert "节点执行摘要" in content
    assert "| `a` | completed |" in content
    assert "事件时间线" in content
    assert "| `node_completed` |" in content


@pytest.mark.asyncio
async def test_record_virtual_path_resolves_under_workspace(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
) -> None:
    await durable_store.save_definition("wf", {}, "hash", "user-1")
    await durable_store.create_run("run-1", "wf", 1, {}, "user-1")
    resolver = _resolver(tmp_path)

    host = resolver(workflow_record_path("jsonl"))
    assert host is not None
    assert str(host).endswith(".workflow/logs/run_record.jsonl")


@pytest.mark.asyncio
async def test_exhausted_run_still_reaches_the_record(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
) -> None:
    """The run_failed event written inside claim_next_task is mirrored too, so
    a max_attempts kill still produces a record."""
    await durable_store.save_definition("wf", {}, "hash", "user-1")
    await durable_store.create_run("run-1", "wf", 1, {}, "user-1")

    writer = RunRecordWriter(_resolver(tmp_path), workflow_log_root())

    async def sink(run, event) -> None:
        if event is not None:
            await writer.on_event(event)
        if run.status in {"completed", "failed", "cancelled"}:
            await writer.finalize(durable_store, run)

    durable_store.event_sink = sink

    async with durable_store.session_factory() as session:
        task = (await session.execute(select(WorkflowTaskRow).where(WorkflowTaskRow.run_id == "run-1"))).scalar_one()
        task.attempts = 3
        task.status = "queued"
        task.lease_owner = None
        task.lease_expires_at = None
        await session.commit()

    assert await durable_store.claim_next_task("worker-1", max_attempts=3) is None

    jsonl_path = tmp_path / "users" / "user-1" / "threads" / "run-1" / "user-data" / "workspace" / ".workflow" / "logs" / "run_record.jsonl"
    lines = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert [line["type"] for line in lines] == ["run_failed"]
    assert lines[0]["payload"]["error"] == "workflow_max_attempts_exceeded"
    assert jsonl_path.with_suffix(".md").is_file()


@pytest.mark.asyncio
async def test_terminal_notify_without_event_still_finalizes_markdown(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
) -> None:
    """finish_task notifies the sink with a None event after flipping the run
    status; the writer must tolerate that and still render the summary."""
    await durable_store.save_definition("wf", {}, "hash", "user-1")
    await durable_store.create_run("run-1", "wf", 1, {}, "user-1")

    writer = RunRecordWriter(_resolver(tmp_path), workflow_log_root())

    async def sink(run, event) -> None:
        await writer.on_event(event)
        if run.status in {"completed", "failed", "cancelled"}:
            await writer.finalize(durable_store, run)

    durable_store.event_sink = sink

    task = await durable_store.claim_next_task("worker-1", max_attempts=3)
    assert task is not None
    await durable_store.append_event("run-1", "run_started", {})
    assert await durable_store.finish_task(task.task_id, "completed", None, "worker-1") is True

    md_path = tmp_path / "users" / "user-1" / "threads" / "run-1" / "user-data" / "workspace" / ".workflow" / "logs" / "run_record.md"
    assert md_path.is_file()
    assert "`completed`" in md_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_null_event_is_a_noop_for_the_record_writer(tmp_path: Path) -> None:
    """A None sink event (e.g. an event-limit drop) must not crash the writer."""
    writer = RunRecordWriter(_resolver(tmp_path), workflow_log_root())

    await writer.on_event(None)

    jsonl_path = tmp_path / "users" / "user-1" / "threads" / "run-1" / "user-data" / "workspace" / ".workflow" / "logs" / "run_record.jsonl"
    assert not jsonl_path.exists()
