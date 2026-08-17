"""Filesystem and database publication consistency contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from zipfile import ZipFile

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource, ResourceDraft, ResourceVersion
from ideer.resources.publisher import ResourcePublisher
from ideer.resources.service import ResourceAction, ResourceActor, ResourceService
from ideer.resources.storage import ResourceStorage


@pytest_asyncio.fixture
async def session_factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'publisher.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _actor(user_id: str = "owner") -> ResourceActor:
    return ResourceActor(
        user_id=user_id,
        department_id="dept-a",
        role="user",
        permissions=frozenset({ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE}),
    )


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir(exist_ok=True)
    (source / "config.yaml").write_text("name: example\n")
    return source


async def _create_resource(factory: async_sessionmaker[AsyncSession]) -> str:
    async with factory() as session:
        resource = await ResourceService(session, _actor()).create_resource(
            resource_type="agent",
            slug="example",
            display_name="Example",
            storage_kind="filesystem",
        )
        await session.commit()
        return resource.id


@pytest.mark.asyncio
async def test_publish_commits_only_after_version_directory_exists_and_removes_draft(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    resource_id = await _create_resource(session_factory)
    storage = ResourceStorage(tmp_path)
    async with session_factory() as session:
        publisher = ResourcePublisher(ResourceService(session, _actor()), storage)
        draft = await publisher.save_filesystem_draft(
            resource_id,
            source_dir=_source(tmp_path),
            expected_revision=0,
        )
        version = await publisher.publish_filesystem(
            resource_id,
            expected_draft_revision=draft.revision,
            scan_result={"status": "clean"},
        )

    async with session_factory() as verification:
        resource = await verification.get(Resource, resource_id)
        persisted = (await verification.execute(select(ResourceVersion).where(ResourceVersion.resource_id == resource_id))).scalar_one()
        assert resource is not None and resource.latest_version == 1
        assert persisted.storage_key == version.storage_key
        assert (storage.resources_root / persisted.storage_key).is_dir()
        assert await verification.get(ResourceDraft, resource_id) is None
        assert not (storage.resources_root / f"agents/{resource_id}/draft/1").exists()


@pytest.mark.asyncio
async def test_archive_draft_is_validated_and_stored_in_canonical_draft_directory(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    resource_id = await _create_resource(session_factory)
    archive = tmp_path / "agent.zip"
    with ZipFile(archive, "w") as value:
        value.writestr("config.yaml", "name: archived-agent\n")

    storage = ResourceStorage(tmp_path)
    async with session_factory() as session:
        publisher = ResourcePublisher(ResourceService(session, _actor()), storage)
        draft = await publisher.save_archive_draft(
            resource_id,
            archive_path=archive,
            expected_revision=0,
        )

    assert draft.revision == 1
    assert (storage.resources_root / draft.storage_key / "config.yaml").read_text() == "name: archived-agent\n"


@pytest.mark.asyncio
async def test_publisher_fork_copies_files_before_committing_independent_private_v1(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    resource_id = await _create_resource(session_factory)
    storage = ResourceStorage(tmp_path)
    async with session_factory() as session:
        publisher = ResourcePublisher(ResourceService(session, _actor()), storage)
        draft = await publisher.save_filesystem_draft(resource_id, source_dir=_source(tmp_path), expected_revision=0)
        await publisher.publish_filesystem(resource_id, expected_draft_revision=draft.revision, scan_result={})
        resource = await session.get(Resource, resource_id)
        assert resource is not None
        resource.visibility = "public"
        await session.commit()

    async with session_factory() as session:
        publisher = ResourcePublisher(ResourceService(session, _actor("fork-owner")), storage)
        forked = await publisher.fork(
            resource_id,
            slug="forked-example",
            display_name="Forked Example",
        )

    assert forked.owner_id == "fork-owner"
    assert forked.visibility == "private"
    assert (storage.resources_root / f"agents/{forked.id}/versions/1/config.yaml").is_file()


@pytest.mark.asyncio
async def test_database_commit_failure_leaves_reconcilable_unreferenced_version_and_preserves_draft(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resource_id = await _create_resource(session_factory)
    storage = ResourceStorage(tmp_path)
    async with session_factory() as session:
        publisher = ResourcePublisher(ResourceService(session, _actor()), storage)
        draft = await publisher.save_filesystem_draft(
            resource_id,
            source_dir=_source(tmp_path),
            expected_revision=0,
        )

        async def fail_commit() -> None:
            raise RuntimeError("injected commit failure")

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="injected commit failure"):
            await publisher.publish_filesystem(
                resource_id,
                expected_draft_revision=draft.revision,
                scan_result={"status": "clean"},
            )

    async with session_factory() as verification:
        resource = await verification.get(Resource, resource_id)
        persisted_draft = await verification.get(ResourceDraft, resource_id)
        versions = list((await verification.execute(select(ResourceVersion).where(ResourceVersion.resource_id == resource_id))).scalars())
        assert resource is not None and resource.latest_version == 0
        assert persisted_draft is not None
        assert versions == []
        report = storage.reconcile({}, expected_drafts={persisted_draft.storage_key: persisted_draft.content_hash})
        assert report.unreferenced_versions == [f"agents/{resource_id}/versions/1"]
        assert report.missing_drafts == []


@pytest.mark.asyncio
async def test_workflow_database_publication_is_immutable_and_hashes_canonical_json(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    async with session_factory() as session:
        resource = await ResourceService(session, _actor()).create_resource(
            resource_type="workflow",
            slug="flow",
            display_name="Flow",
            storage_kind="database",
        )
        await session.commit()
        resource_id = resource.id

    async with session_factory() as session:
        publisher = ResourcePublisher(ResourceService(session, _actor()), ResourceStorage(tmp_path))
        content = {
            "schema_version": 2,
            "name": "flow",
            "entrypoint": "start",
            "nodes": [{"id": "start", "type": "action", "action": {"kind": "tool", "name": "noop"}}],
            "edges": [],
        }
        draft = await publisher.save_database_draft(
            resource_id,
            content=content,
            expected_revision=0,
        )
        version = await publisher.publish_database(
            resource_id,
            expected_draft_revision=draft.revision,
            scan_result={"status": "valid"},
        )

    assert version.storage_key == f"workflows/{resource_id}/versions/1"
    assert version.content == content
    assert len(version.content_hash) == 64
    async with session_factory() as verification:
        persisted = (await verification.execute(select(ResourceVersion).where(ResourceVersion.resource_id == resource_id))).scalar_one()
        assert persisted.content == version.content


@pytest.mark.asyncio
@pytest.mark.parametrize("resource_type", ["agent", "workflow"])
async def test_rollback_copies_old_content_into_a_new_version(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    resource_type: str,
) -> None:
    storage = ResourceStorage(tmp_path)
    async with session_factory() as session:
        resource = await ResourceService(session, _actor()).create_resource(
            resource_type=resource_type,
            slug=f"rollback-{resource_type}",
            display_name="Rollback",
            storage_kind="database" if resource_type == "workflow" else "filesystem",
        )
        await session.commit()
        resource_id = resource.id

    async with session_factory() as session:
        publisher = ResourcePublisher(ResourceService(session, _actor()), storage)
        if resource_type == "workflow":
            content = {
                "schema_version": 2,
                "name": "rollback-workflow",
                "entrypoint": "start",
                "nodes": [{"id": "start", "type": "action", "action": {"kind": "tool", "name": "noop"}}],
                "edges": [],
            }
            draft = await publisher.save_database_draft(resource_id, content=content, expected_revision=0)
            first = await publisher.publish_database(resource_id, expected_draft_revision=draft.revision, scan_result={})
            rolled_back = await publisher.rollback_database(resource_id, source_version=1)
        else:
            draft = await publisher.save_filesystem_draft(resource_id, source_dir=_source(tmp_path), expected_revision=0)
            first = await publisher.publish_filesystem(resource_id, expected_draft_revision=draft.revision, scan_result={})
            rolled_back = await publisher.rollback_filesystem(resource_id, source_version=1)

    assert (first.version, rolled_back.version) == (1, 2)
    assert rolled_back.storage_key != first.storage_key
    assert rolled_back.content_hash == first.content_hash
    assert (rolled_back.source_resource_id, rolled_back.source_version) == (resource_id, 1)
    if resource_type == "agent":
        assert (storage.resources_root / rolled_back.storage_key).is_dir()
    else:
        assert rolled_back.content == first.content


@pytest.mark.asyncio
async def test_invalid_workflow_contract_cannot_be_published(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    async with session_factory() as session:
        resource = await ResourceService(session, _actor()).create_resource(
            resource_type="workflow",
            slug="invalid-flow",
            display_name="Invalid Flow",
            storage_kind="database",
        )
        await session.commit()
        resource_id = resource.id

    async with session_factory() as session:
        publisher = ResourcePublisher(ResourceService(session, _actor()), ResourceStorage(tmp_path))
        draft = await publisher.save_database_draft(
            resource_id,
            content={"schema_version": 2, "nodes": []},
            expected_revision=0,
        )
        with pytest.raises(ValueError, match="name|entrypoint|nodes"):
            await publisher.publish_database(
                resource_id,
                expected_draft_revision=draft.revision,
                scan_result={},
            )

    async with session_factory() as verification:
        resource = await verification.get(Resource, resource_id)
        assert resource is not None and resource.latest_version == 0


@pytest.mark.asyncio
async def test_agent_with_plaintext_credentials_cannot_be_published(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    resource_id = await _create_resource(session_factory)
    source = _source(tmp_path)
    (source / "config.yaml").write_text("name: example\npassword: plaintext\n")
    storage = ResourceStorage(tmp_path)
    async with session_factory() as session:
        publisher = ResourcePublisher(ResourceService(session, _actor()), storage)
        draft = await publisher.save_filesystem_draft(resource_id, source_dir=source, expected_revision=0)
        with pytest.raises(Exception, match="credential"):
            await publisher.publish_filesystem(
                resource_id,
                expected_draft_revision=draft.revision,
                scan_result={"status": "clean"},
            )

    async with session_factory() as verification:
        resource = await verification.get(Resource, resource_id)
        assert resource is not None and resource.latest_version == 0
        assert not (storage.resources_root / f"agents/{resource_id}/versions/1").exists()


@pytest.mark.asyncio
async def test_bundled_workflow_database_flow_draft_publish_and_rollback_succeed(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    async with session_factory() as session:
        resource = await ResourceService(session, _actor()).create_resource(
            resource_type="workflow",
            slug="bundled-flow",
            display_name="Bundled Flow",
            storage_kind="database",
        )
        resource.provenance = "bundled"
        await session.commit()
        resource_id = resource.id

    storage = ResourceStorage(tmp_path)
    async with session_factory() as session:
        publisher = ResourcePublisher(ResourceService(session, _actor()), storage)
        content = {
            "schema_version": 2,
            "name": "bundled-flow",
            "entrypoint": "start",
            "nodes": [{"id": "start", "type": "action", "action": {"kind": "tool", "name": "noop"}}],
            "edges": [],
        }
        draft = await publisher.save_database_draft(resource_id, content=content, expected_revision=0)
        first = await publisher.publish_database(
            resource_id,
            expected_draft_revision=draft.revision,
            scan_result={"status": "valid"},
        )
        rolled_back = await publisher.rollback_database(resource_id, source_version=1)

    assert (first.version, rolled_back.version) == (1, 2)
    async with session_factory() as verification:
        resource = await verification.get(Resource, resource_id)
        assert resource is not None and resource.provenance == "bundled"
        assert resource.latest_version == 2
