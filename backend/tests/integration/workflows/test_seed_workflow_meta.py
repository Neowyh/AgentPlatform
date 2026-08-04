"""Seed must create workflow resource_metadata so API run endpoints resolve.

Real deployment enables SQLite foreign keys; owner_id references users_ext.
An unknown owner (e.g. default 'system') must not fail the seed — the
definition is still persisted, only the meta row is skipped.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ideer.persistence.base import Base
from ideer.persistence.models.resource_metadata import ResourceMetadata

REPO_ROOT = Path(__file__).resolve().parents[4]
SEED_PATH = REPO_ROOT / "scripts" / "seed_fault_zeroing_workflow.py"
BUNDLED_YAML = REPO_ROOT / "workflows" / "fault-zeroing.yaml"


def load_seed_script():
    spec = importlib.util.spec_from_file_location("seed_fault_zeroing_workflow", SEED_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest_asyncio.fixture
async def seed_env(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_conn, _record):  # noqa: ARG001 — SQLAlchemy contract
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    yield sf
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_creates_resource_metadata_for_owner(seed_env) -> None:
    seed = load_seed_script()
    from ideer.persistence.models.user import UserModel

    async with seed_env() as session:
        session.add(UserModel(id="user-1", username="owner@test.com", role="user"))
        await session.commit()

    from ideer.workflows.v2.store import WorkflowV2Store

    result = await seed.seed_workflow(WorkflowV2Store(seed_env), BUNDLED_YAML, created_by="user-1", session_factory=seed_env)

    assert result["status"] == "created"
    async with seed_env() as session:
        meta = (
            await session.execute(
                select(ResourceMetadata).where(
                    ResourceMetadata.resource_type == "workflow",
                    ResourceMetadata.resource_id == "fault-zeroing",
                )
            )
        ).scalar_one()
        assert meta.owner_id == "user-1"
        assert meta.visibility == "private"


@pytest.mark.asyncio
async def test_seed_tolerates_unknown_owner(seed_env) -> None:
    seed = load_seed_script()

    from ideer.workflows.v2.store import WorkflowV2Store

    result = await seed.seed_workflow(
        WorkflowV2Store(seed_env),
        BUNDLED_YAML,
        created_by="system",
        session_factory=seed_env,
    )

    assert result["status"] == "created"
    async with seed_env() as session:
        rows = (await session.execute(select(ResourceMetadata).where(ResourceMetadata.resource_type == "workflow"))).fetchall()
    assert rows == []


@pytest.mark.asyncio
async def test_seed_refreshes_meta_on_skip(seed_env) -> None:
    """Skipped re-seeds must still ensure the meta row exists (first seed may
    have run before meta support or with an unknown owner)."""
    seed = load_seed_script()
    from ideer.persistence.models.user import UserModel

    async with seed_env() as session:
        session.add(UserModel(id="user-2", username="owner2@test.com", role="user"))
        await session.commit()

    from ideer.workflows.v2.store import WorkflowV2Store

    store = WorkflowV2Store(seed_env)
    first = await seed.seed_workflow(store, BUNDLED_YAML, created_by="user-2", session_factory=seed_env)
    assert first["status"] == "created"

    second = await seed.seed_workflow(store, BUNDLED_YAML, created_by="user-2", session_factory=seed_env)
    assert second["status"] == "skipped"
    async with seed_env() as session:
        meta = (
            await session.execute(
                select(ResourceMetadata).where(
                    ResourceMetadata.resource_type == "workflow",
                    ResourceMetadata.resource_id == "fault-zeroing",
                )
            )
        ).scalar_one()
        assert meta.owner_id == "user-2"
