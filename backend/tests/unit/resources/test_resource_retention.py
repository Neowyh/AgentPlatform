from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import (
    Resource,
    ResourceDependency,
    ResourceType,
    ResourceVersion,
    RunResourceSnapshot,
)
from ideer.persistence.models.user import UserModel, UserRole
from ideer.resources.retention import RetentionPurgeError, build_retention_report, purge_eligible_versions
from ideer.resources.storage import ResourceStorage


@pytest.mark.asyncio
async def test_retention_report_never_marks_frozen_or_system_versions_eligible(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=100)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'retention.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            UserModel(
                id="owner",
                username="owner@test.com",
                role=UserRole.SUPER_ADMIN,
                disabled=False,
            )
        )
        for resource_id, system_owned in (("archived", False), ("system", True)):
            session.add(
                Resource(
                    id=resource_id,
                    type="skill",
                    slug=resource_id,
                    display_name=resource_id,
                    owner_id="owner",
                    visibility="private",
                    lifecycle_status="archived",
                    latest_version=2 if resource_id == "archived" else 1,
                    draft_revision=0,
                    storage_kind="filesystem",
                    storage_key=f"skills/{resource_id}",
                    provenance="bundled" if system_owned else "user",
                    system_owned=system_owned,
                    authz_revision=2,
                    created_at=old,
                    updated_at=old,
                )
            )
        session.add_all(
            [
                ResourceVersion(
                    id="version-1",
                    resource_id="archived",
                    version=1,
                    content_hash="a" * 64,
                    storage_key="skills/archived/versions/1",
                    scan_result={},
                    created_by="owner",
                    published_at=old,
                ),
                ResourceVersion(
                    id="version-2",
                    resource_id="archived",
                    version=2,
                    content_hash="b" * 64,
                    storage_key="skills/archived/versions/2",
                    scan_result={},
                    created_by="owner",
                    published_at=old,
                ),
                ResourceVersion(
                    id="system-version",
                    resource_id="system",
                    version=1,
                    content_hash="c" * 64,
                    storage_key="skills/system/versions/1",
                    scan_result={},
                    created_by="owner",
                    published_at=old,
                ),
                RunResourceSnapshot(
                    id="snapshot",
                    run_id="run",
                    root_resource_id="archived",
                    resource_id="archived",
                    version=1,
                    content_hash="a" * 64,
                    authz_revision=1,
                    resolved_at=old,
                ),
            ]
        )
        await session.commit()

        report = await build_retention_report(
            session,
            cutoff=now - timedelta(days=30),
        )

    by_key = {(item.resource_id, item.version): item for item in report}
    assert by_key[("archived", 1)].eligible is False
    assert by_key[("archived", 1)].blockers == ("run_snapshot_reference",)
    assert by_key[("archived", 2)].eligible is True
    assert by_key[("system", 1)].eligible is False
    assert "bundled" in by_key[("system", 1)].blockers
    assert "system_owned" in by_key[("system", 1)].blockers
    await engine.dispose()


def _write_version(runtime: Path, resource_type: str, resource_id: str, version: int, files: dict[str, str]) -> None:
    root = runtime / "resources" / resource_type / resource_id / "versions" / str(version)
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def _hash_of(storage: ResourceStorage, resource_type: str, resource_id: str, version: int) -> str:
    type_directory = storage._TYPE_DIRECTORIES[ResourceType(resource_type)]
    root = storage.resources_root / type_directory / resource_id / "versions" / str(version)
    return storage.inspect_directory(resource_type, root).content_hash


@pytest.mark.asyncio
async def test_purge_moves_eligible_content_and_removes_catalog_rows(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=100)
    runtime = tmp_path / "runtime"
    storage = ResourceStorage(runtime)
    _write_version(runtime, "skills", "archived", 1, {"SKILL.md": "v1\n"})
    _write_version(runtime, "skills", "archived", 2, {"SKILL.md": "v2\n"})
    _write_version(runtime, "skills", "expired", 1, {"SKILL.md": "expired\n"})
    _write_version(runtime, "skills", "system", 1, {"SKILL.md": "system\n"})
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'purge.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(UserModel(id="owner", username="owner@test.com", role=UserRole.SUPER_ADMIN, disabled=False))
        session.add(
            Resource(
                id="archived",
                type="skill",
                slug="archived",
                display_name="archived",
                owner_id="owner",
                visibility="private",
                lifecycle_status="archived",
                latest_version=2,
                draft_revision=0,
                storage_kind="filesystem",
                storage_key="skills/archived",
                system_owned=False,
                authz_revision=1,
                created_at=old,
                updated_at=old,
            )
        )
        session.add(
            Resource(
                id="expired",
                type="skill",
                slug="expired",
                display_name="expired",
                owner_id="owner",
                visibility="private",
                lifecycle_status="archived",
                latest_version=1,
                draft_revision=0,
                storage_kind="filesystem",
                storage_key="skills/expired",
                system_owned=False,
                authz_revision=1,
                created_at=old,
                updated_at=old,
            )
        )
        session.add(
            Resource(
                id="system",
                type="skill",
                slug="system",
                display_name="system",
                owner_id="owner",
                visibility="private",
                lifecycle_status="archived",
                latest_version=1,
                draft_revision=0,
                storage_kind="filesystem",
                storage_key="skills/system",
                provenance="bundled",
                system_owned=True,
                authz_revision=1,
                created_at=old,
                updated_at=old,
            )
        )
        session.add_all(
            [
                ResourceVersion(
                    id="version-1",
                    resource_id="archived",
                    version=1,
                    content_hash=_hash_of(storage, "skill", "archived", 1),
                    storage_key="skills/archived/versions/1",
                    scan_result={},
                    created_by="owner",
                    published_at=old,
                ),
                ResourceVersion(
                    id="version-2",
                    resource_id="archived",
                    version=2,
                    content_hash=_hash_of(storage, "skill", "archived", 2),
                    storage_key="skills/archived/versions/2",
                    scan_result={},
                    created_by="owner",
                    published_at=old,
                ),
                ResourceVersion(
                    id="expired-version",
                    resource_id="expired",
                    version=1,
                    content_hash=_hash_of(storage, "skill", "expired", 1),
                    storage_key="skills/expired/versions/1",
                    scan_result={},
                    created_by="owner",
                    published_at=old,
                ),
                ResourceVersion(
                    id="system-version",
                    resource_id="system",
                    version=1,
                    content_hash=_hash_of(storage, "skill", "system", 1),
                    storage_key="skills/system/versions/1",
                    scan_result={},
                    created_by="owner",
                    published_at=old,
                ),
                RunResourceSnapshot(
                    id="snapshot",
                    run_id="run",
                    root_resource_id="archived",
                    resource_id="archived",
                    version=1,
                    content_hash=_hash_of(storage, "skill", "archived", 1),
                    authz_revision=1,
                    resolved_at=old,
                ),
            ]
        )
        await session.commit()

        result = await purge_eligible_versions(
            session,
            storage,
            cutoff=now - timedelta(days=30),
            backup_dir=tmp_path / "purge-backup",
            authorized_by="super_admin@test.com",
        )

    assert result.moved_storage_keys == ("skills/archived/versions/2", "skills/expired/versions/1")
    assert result.removed_version_ids == ("archived", "expired")
    assert result.removed_resources == ("expired",)
    assert result.blocked == ()
    assert not (runtime / "resources" / "skills" / "expired").exists()
    assert not (runtime / "resources" / "skills" / "archived" / "versions" / "2").exists()
    assert (runtime / "resources" / "skills" / "archived" / "versions" / "1" / "SKILL.md").exists()
    assert (tmp_path / "purge-backup" / "skills" / "expired" / "versions" / "1" / "SKILL.md").read_text() == "expired\n"
    assert (runtime / "resources" / "skills" / "system" / "versions" / "1" / "SKILL.md").exists()
    await engine.dispose()


@pytest.mark.asyncio
async def test_purge_requires_explicit_authorization_and_safe_backup(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=100)
    runtime = tmp_path / "runtime"
    storage = ResourceStorage(runtime)
    _write_version(runtime, "skills", "archived", 1, {"SKILL.md": "v1\n"})
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'purge.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(UserModel(id="owner", username="owner@test.com", role=UserRole.SUPER_ADMIN, disabled=False))
        session.add(
            Resource(
                id="archived",
                type="skill",
                slug="archived",
                display_name="archived",
                owner_id="owner",
                visibility="private",
                lifecycle_status="archived",
                latest_version=1,
                draft_revision=0,
                storage_kind="filesystem",
                storage_key="skills/archived",
                system_owned=False,
                authz_revision=1,
                created_at=old,
                updated_at=old,
            )
        )
        session.add(
            ResourceVersion(
                id="version-1",
                resource_id="archived",
                version=1,
                content_hash=_hash_of(storage, "skill", "archived", 1),
                storage_key="skills/archived/versions/1",
                scan_result={},
                created_by="owner",
                published_at=old,
            )
        )
        await session.commit()

        with pytest.raises(RetentionPurgeError, match="authorization"):
            await purge_eligible_versions(
                session,
                storage,
                cutoff=now - timedelta(days=30),
                backup_dir=tmp_path / "purge-backup",
                authorized_by="  ",
            )
        with pytest.raises(RetentionPurgeError, match="outside"):
            await purge_eligible_versions(
                session,
                storage,
                cutoff=now - timedelta(days=30),
                backup_dir=runtime / "resources" / "skills",
                authorized_by="super_admin@test.com",
            )
    await engine.dispose()


@pytest.mark.asyncio
async def test_purge_refuses_tampered_content_and_compensates_midway(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=100)
    runtime = tmp_path / "runtime"
    storage = ResourceStorage(runtime)
    _write_version(runtime, "skills", "first", 1, {"SKILL.md": "first\n"})
    _write_version(runtime, "skills", "second", 1, {"SKILL.md": "second\n"})
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'purge.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(UserModel(id="owner", username="owner@test.com", role=UserRole.SUPER_ADMIN, disabled=False))
        for resource_id in ("first", "second"):
            session.add(
                Resource(
                    id=resource_id,
                    type="skill",
                    slug=resource_id,
                    display_name=resource_id,
                    owner_id="owner",
                    visibility="private",
                    lifecycle_status="archived",
                    latest_version=1,
                    draft_revision=0,
                    storage_kind="filesystem",
                    storage_key=f"skills/{resource_id}",
                    system_owned=False,
                    authz_revision=1,
                    created_at=old,
                    updated_at=old,
                )
            )
        session.add_all(
            [
                ResourceVersion(
                    id=f"{resource_id}-version",
                    resource_id=resource_id,
                    version=1,
                    content_hash=_hash_of(storage, "skill", resource_id, 1),
                    storage_key=f"skills/{resource_id}/versions/1",
                    scan_result={},
                    created_by="owner",
                    published_at=old,
                )
                for resource_id in ("first", "second")
            ]
        )
        await session.commit()

        tampered = runtime / "resources" / "skills" / "second" / "versions" / "1" / "SKILL.md"
        tampered.chmod(0o644)
        tampered.write_text("tampered\n")

        with pytest.raises(RetentionPurgeError, match="hash mismatch"):
            await purge_eligible_versions(
                session,
                storage,
                cutoff=now - timedelta(days=30),
                backup_dir=tmp_path / "purge-backup",
                authorized_by="super_admin@test.com",
            )

        assert (runtime / "resources" / "skills" / "first" / "versions" / "1" / "SKILL.md").exists()
        assert not (tmp_path / "purge-backup").exists() or not list((tmp_path / "purge-backup").rglob("SKILL.md"))
    await engine.dispose()


@pytest.mark.asyncio
async def test_purge_blocks_resource_with_incoming_dependency(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=100)
    runtime = tmp_path / "runtime"
    storage = ResourceStorage(runtime)
    _write_version(runtime, "skills", "blocked-skill", 1, {"SKILL.md": "blocked\n"})
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'purge.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(UserModel(id="owner", username="owner@test.com", role=UserRole.SUPER_ADMIN, disabled=False))
        session.add(
            Resource(
                id="blocked-skill",
                type="skill",
                slug="blocked-skill",
                display_name="blocked-skill",
                owner_id="owner",
                visibility="private",
                lifecycle_status="archived",
                latest_version=1,
                draft_revision=0,
                storage_kind="filesystem",
                storage_key="skills/blocked-skill",
                system_owned=False,
                authz_revision=1,
                created_at=old,
                updated_at=old,
            )
        )
        session.add(
            Resource(
                id="dependent-agent",
                type="agent",
                slug="dependent-agent",
                display_name="dependent-agent",
                owner_id="owner",
                visibility="private",
                lifecycle_status="active",
                latest_version=1,
                draft_revision=0,
                storage_kind="filesystem",
                storage_key="agents/dependent-agent",
                system_owned=False,
                authz_revision=1,
                created_at=old,
                updated_at=old,
            )
        )
        session.add(
            ResourceVersion(
                id="blocked-version",
                resource_id="blocked-skill",
                version=1,
                content_hash=_hash_of(storage, "skill", "blocked-skill", 1),
                storage_key="skills/blocked-skill/versions/1",
                scan_result={},
                created_by="owner",
                published_at=old,
            )
        )
        session.add(
            ResourceDependency(
                id="incoming-edge",
                source_resource_id="dependent-agent",
                target_resource_id="blocked-skill",
            )
        )
        await session.commit()

        result = await purge_eligible_versions(
            session,
            storage,
            cutoff=now - timedelta(days=30),
            backup_dir=tmp_path / "purge-backup",
            authorized_by="super_admin@test.com",
        )

        assert result.moved_storage_keys == ("skills/blocked-skill/versions/1",)
        assert result.blocked == ("blocked-skill",)
        assert result.removed_resources == ()
        assert (await session.execute(select(Resource.id).where(Resource.id == "blocked-skill"))).scalar_one() == "blocked-skill"
    await engine.dispose()
