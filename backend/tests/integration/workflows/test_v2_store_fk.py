"""Regression: create_run must persist the run row before the task row.

The production engine (persistence/engine.py) enables SQLite foreign keys via
PRAGMA on every connection. SQLAlchemy's flush ordering can emit the
workflow_tasks INSERT before the workflow_v2_runs INSERT, which fails the
foreign key check. This suite drives create_run through a real FK-enabled
database to lock the ordering in place.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ideer.persistence.base import Base
from ideer.persistence.models.workflow_v2 import WorkflowDefinitionVersionRow, WorkflowTaskRow, WorkflowV2RunRow
from ideer.workflows.v2.store import WorkflowV2Store


@pytest_asyncio.fixture
async def fk_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'workflow.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_conn, _record):  # noqa: ARG001 — SQLAlchemy contract
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_run_persists_run_and_task_with_fk_enabled(fk_engine) -> None:
    store = WorkflowV2Store(async_sessionmaker(fk_engine, expire_on_commit=False))

    run = await store.create_run("fk-run-1", "fault-zeroing", 1, {"upload_dir": "/tmp"}, "system")

    assert run.status == "queued"
    assert run.checkpoint_thread_id.startswith("wf-")
    assert ":" not in run.checkpoint_thread_id
    async with async_sessionmaker(fk_engine, expire_on_commit=False)() as session:
        persisted = await session.get(WorkflowV2RunRow, "fk-run-1")
        assert persisted is not None
        assert persisted.definition_version == 1
        task = (await session.execute(select(WorkflowTaskRow).where(WorkflowTaskRow.run_id == "fk-run-1"))).scalar_one()
        assert task.status == "queued"


@pytest.mark.asyncio
async def test_delete_definition_removes_all_versions_but_keeps_runs(fk_engine) -> None:
    store = WorkflowV2Store(async_sessionmaker(fk_engine, expire_on_commit=False))

    for version, definition in ((1, {"schema_version": 2, "v": 1}), (2, {"schema_version": 2, "v": 2})):
        await store.save_definition("fault-zeroing", definition, f"hash-{version}", "system")
    await store.create_run("fk-run-2", "fault-zeroing", 2, {"upload_dir": "/tmp"}, "system")

    deleted = await store.delete_definition("fault-zeroing")

    assert deleted == 2
    async with async_sessionmaker(fk_engine, expire_on_commit=False)() as session:
        rows = (await session.execute(select(WorkflowDefinitionVersionRow).where(WorkflowDefinitionVersionRow.workflow_name == "fault-zeroing"))).scalars().all()
        assert rows == []
        run = await session.get(WorkflowV2RunRow, "fk-run-2")
        assert run is not None
        assert run.definition_version == 2


@pytest.mark.asyncio
async def test_delete_definition_keeps_other_workflows_untouched(fk_engine) -> None:
    store = WorkflowV2Store(async_sessionmaker(fk_engine, expire_on_commit=False))

    await store.save_definition("delete-me", {"schema_version": 2}, "hash", "system")
    await store.save_definition("keep-me", {"schema_version": 2}, "hash", "system")

    deleted = await store.delete_definition("delete-me")

    assert deleted == 1
    async with async_sessionmaker(fk_engine, expire_on_commit=False)() as session:
        remaining = (await session.execute(select(WorkflowDefinitionVersionRow))).scalars().all()
        assert [row.workflow_name for row in remaining] == ["keep-me"]
