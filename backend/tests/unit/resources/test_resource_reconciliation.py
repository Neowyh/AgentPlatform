"""Database/filesystem consistency gates for canonical resource startup."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from ideer.persistence.base import Base
from ideer.resources.publisher import ResourcePublisher
from ideer.resources.reconciliation import CatalogConsistencyError, reconcile_catalog_storage
from ideer.resources.service import ResourceAction, ResourceActor, ResourceService
from ideer.resources.storage import ResourceStorage


@pytest_asyncio.fixture
async def session_factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reconcile.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _actor() -> ResourceActor:
    return ResourceActor(
        user_id="owner",
        department_id="dept-a",
        role="user",
        permissions=frozenset({ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE}),
    )


@pytest.mark.asyncio
async def test_reconcile_accepts_consistent_catalog_and_fails_closed_when_version_disappears(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "config.yaml").write_text("name: example\n")
    storage = ResourceStorage(tmp_path)
    async with session_factory() as session:
        service = ResourceService(session, _actor())
        resource = await service.create_resource(
            resource_type="agent",
            slug="example",
            display_name="Example",
            storage_kind="filesystem",
        )
        await session.commit()
        publisher = ResourcePublisher(service, storage)
        draft = await publisher.save_filesystem_draft(resource.id, source_dir=source, expected_revision=0)
        version = await publisher.publish_filesystem(resource.id, expected_draft_revision=draft.revision, scan_result={})

    async with session_factory() as session:
        report = await reconcile_catalog_storage(session, storage)
    assert report.missing_versions == []
    assert report.hash_mismatches == []

    version_path = storage.resources_root / version.storage_key
    version_path.chmod(0o755)
    (version_path / "config.yaml").chmod(0o644)
    (version_path / "config.yaml").unlink()
    async with session_factory() as session:
        with pytest.raises(CatalogConsistencyError, match="hash_mismatches"):
            await reconcile_catalog_storage(session, storage)
