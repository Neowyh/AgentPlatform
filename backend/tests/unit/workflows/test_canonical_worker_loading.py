"""Worker definition loading selects the frozen canonical resource when present."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from app.workflow_worker import load_workflow_definition_for_run
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource, ResourceVersion, RunResourceSnapshot
from ideer.resources.storage import ResourceStorage


@pytest.mark.asyncio
async def test_canonical_worker_definition_never_reloads_legacy_name(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    resource_id = "a234742a-9df8-4d2a-b7f4-b3f39f63ab65"
    content = {"schema_version": 2, "nodes": [], "edges": []}
    from ideer.resources.runtime import _json_hash

    content_hash = _json_hash(content)
    async with factory() as session:
        session.add_all(
            [
                Resource(
                    id=resource_id,
                    type="workflow",
                    slug="flow",
                    display_name="Flow",
                    owner_id="owner",
                    visibility="public",
                    scope_department_id=None,
                    lifecycle_status="active",
                    latest_version=1,
                    draft_revision=0,
                    storage_kind="database",
                    storage_key=f"workflows/{resource_id}",
                    system_owned=False,
                    authz_revision=1,
                ),
                ResourceVersion(
                    id="workflow-version",
                    resource_id=resource_id,
                    version=1,
                    content_hash=content_hash,
                    storage_key=f"workflows/{resource_id}/versions/1",
                    scan_result={},
                    content=content,
                    created_by="owner",
                ),
                RunResourceSnapshot(
                    id="workflow-snapshot",
                    run_id="run-1",
                    root_resource_id=resource_id,
                    resource_id=resource_id,
                    version=1,
                    content_hash=content_hash,
                    authz_revision=1,
                ),
            ]
        )
        await session.commit()
    store = SimpleNamespace(get_definition=AsyncMock())
    run = SimpleNamespace(
        run_id="run-1",
        workflow_resource_id=resource_id,
        workflow_name="legacy-name",
        definition_version=99,
    )

    loaded = await load_workflow_definition_for_run(run, store, factory, ResourceStorage(tmp_path))

    assert loaded == content
    store.get_definition.assert_not_awaited()
    await engine.dispose()
