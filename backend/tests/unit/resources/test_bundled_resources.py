from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import (
    Resource,
    ResourceDependency,
    ResourceVersion,
)
from ideer.persistence.models.user import UserModel, UserRole
from ideer.resources.bundled import load_bundled_manifest, seed_bundled_resources
from ideer.resources.storage import ResourceStorage

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_manifest_system_owned_is_optional_and_validated(tmp_path: Path) -> None:
    manifest_path = tmp_path / "bundled-resources.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "resources": [
                    {
                        "id": "11111111-1111-5111-8111-111111111111",
                        "type": "skill",
                        "slug": "protected",
                        "display_name": "受保护技能",
                        "visibility": "private",
                        "source": "skills/protected",
                        "system_owned": True,
                    },
                    {
                        "id": "22222222-2222-5222-8222-222222222222",
                        "type": "agent",
                        "slug": "managed",
                        "display_name": "受管智能体",
                        "visibility": "private",
                        "source": "agents/managed",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = load_bundled_manifest(manifest_path)
    assert manifest.resources[0].system_owned is True
    assert manifest.resources[1].system_owned is False

    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "resources": [
                    {
                        "id": "11111111-1111-5111-8111-111111111111",
                        "type": "skill",
                        "slug": "protected",
                        "display_name": "受保护技能",
                        "visibility": "private",
                        "source": "skills/protected",
                        "system_owned": "yes",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="system_owned"):
        load_bundled_manifest(manifest_path)


def test_repository_bundled_manifest_has_unique_stable_ids_and_existing_sources() -> None:
    manifest = load_bundled_manifest(REPO_ROOT / "bundled-resources.json")

    assert manifest.schema_version == 1
    assert len(manifest.resources) == 72
    assert len({item.id for item in manifest.resources}) == len(manifest.resources)
    assert len({(item.type, item.slug) for item in manifest.resources}) == len(manifest.resources)
    assert {(item.type, item.slug): item.id for item in manifest.resources}[("workflow", "fault-zeroing")] == "018ce2c1-4d43-5db4-b4e3-d8d40624260d"
    assert all((REPO_ROOT / item.source).exists() for item in manifest.resources)


@pytest.mark.asyncio
async def test_bundled_seed_is_idempotent_and_rewrites_dependencies_to_stable_ids(
    tmp_path: Path,
) -> None:
    skill_id = "11111111-1111-5111-8111-111111111111"
    agent_id = "22222222-2222-5222-8222-222222222222"
    workflow_id = "33333333-3333-5333-8333-333333333333"
    source_root = tmp_path / "source"
    skill_dir = source_root / "skills" / "review"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: review\ndescription: Review\n---\nReview carefully.\n",
        encoding="utf-8",
    )
    agent_dir = source_root / "agents" / "reviewer"
    agent_dir.mkdir(parents=True)
    (agent_dir / "config.yaml").write_text(
        "name: reviewer\ndescription: Reviewer\nskills:\n  - review\n",
        encoding="utf-8",
    )
    (agent_dir / "SOUL.md").write_text("Review carefully.\n", encoding="utf-8")
    workflow_path = source_root / "workflows" / "review.yaml"
    workflow_path.parent.mkdir(parents=True)
    workflow_path.write_text(
        """schema_version: 2
name: review-flow
entrypoint: review
nodes:
  - id: review
    type: action
    action:
      kind: agent
      name: reviewer
edges: []
""",
        encoding="utf-8",
    )
    manifest_path = source_root / "bundled-resources.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "resources": [
                    {
                        "id": skill_id,
                        "type": "skill",
                        "slug": "review",
                        "display_name": "评审",
                        "visibility": "public",
                        "source": "skills/review",
                    },
                    {
                        "id": agent_id,
                        "type": "agent",
                        "slug": "reviewer",
                        "display_name": "评审智能体",
                        "visibility": "public",
                        "source": "agents/reviewer",
                    },
                    {
                        "id": workflow_id,
                        "type": "workflow",
                        "slug": "review-flow",
                        "display_name": "评审工作流",
                        "visibility": "public",
                        "source": "workflows/review.yaml",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bundled.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            UserModel(
                id="system-owner",
                username="system@test.com",
                role=UserRole.SUPER_ADMIN,
                disabled=False,
            )
        )
        await session.commit()

    storage = ResourceStorage(tmp_path / "runtime")
    first = await seed_bundled_resources(
        factory,
        storage,
        manifest_path=manifest_path,
        source_root=source_root,
        owner_id="system-owner",
    )
    second = await seed_bundled_resources(
        factory,
        storage,
        manifest_path=manifest_path,
        source_root=source_root,
        owner_id="system-owner",
    )

    assert first.created == 3
    assert first.updated == 0
    assert second.created == 0
    assert second.unchanged == 3
    async with factory() as session:
        assert (await session.scalar(select(func.count()).select_from(Resource))) == 3
        resources = {item.id: item for item in (await session.execute(select(Resource))).scalars()}
        assert all(not item.system_owned for item in resources.values())
        dependencies = {(item.source_resource_id, item.target_resource_id) for item in (await session.execute(select(ResourceDependency))).scalars()}
        assert dependencies == {(agent_id, skill_id), (workflow_id, agent_id)}
        agent_version = await session.scalar(select(ResourceVersion).where(ResourceVersion.resource_id == agent_id))
        workflow_version = await session.scalar(select(ResourceVersion).where(ResourceVersion.resource_id == workflow_id))
        assert agent_version is not None
        agent_config = yaml.safe_load((storage.resources_root / agent_version.storage_key / "config.yaml").read_text(encoding="utf-8"))
        assert agent_config["skills"] == [skill_id]
        assert workflow_version is not None
        assert workflow_version.content["nodes"][0]["action"]["name"] == agent_id

    await engine.dispose()


@pytest.mark.asyncio
async def test_repository_bundle_can_be_seeded_offline_as_one_complete_set(
    tmp_path: Path,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'repository.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            UserModel(
                id="system-owner",
                username="system@test.com",
                role=UserRole.SUPER_ADMIN,
                disabled=False,
            )
        )
        await session.commit()

    manifest = load_bundled_manifest(REPO_ROOT / "bundled-resources.json")
    report = await seed_bundled_resources(
        factory,
        ResourceStorage(
            tmp_path / "runtime",
            allow_scanned_executables=True,
        ),
        manifest_path=REPO_ROOT / "bundled-resources.json",
        source_root=REPO_ROOT,
        owner_id="system-owner",
    )

    assert report.created == 72
    second_report = await seed_bundled_resources(
        factory,
        ResourceStorage(
            tmp_path / "runtime",
            allow_scanned_executables=True,
        ),
        manifest_path=REPO_ROOT / "bundled-resources.json",
        source_root=REPO_ROOT,
        owner_id="system-owner",
    )
    assert second_report.created == 0
    assert second_report.updated == 0
    assert second_report.unchanged == len(manifest.resources)
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Resource)) == 72
        assert await session.scalar(select(func.count()).select_from(ResourceVersion)) == 72
        resources = {resource.id: resource for resource in (await session.execute(select(Resource))).scalars()}
        assert set(resources) == {resource.id for resource in manifest.resources}
        assert all(resource.visibility == "public" for resource in resources.values())
        assert all(resource.latest_version == 1 for resource in resources.values())
    await engine.dispose()


async def _make_factory(tmp_path: Path, db_name: str):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / db_name}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            UserModel(
                id="system-owner",
                username="system@test.com",
                role=UserRole.SUPER_ADMIN,
                disabled=False,
            )
        )
        await session.commit()
    return engine, factory


def _write_workflow_manifest(path: Path, description: str) -> None:
    workflow_path = path.parent / "workflows" / "review.yaml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    agent_dir = path.parent / "agents" / "reviewer"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "config.yaml").write_text(
        "name: reviewer\ndescription: Reviewer\n",
        encoding="utf-8",
    )
    (agent_dir / "SOUL.md").write_text("Review carefully.\n", encoding="utf-8")
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "resources": [
                    {
                        "id": "22222222-2222-5222-8222-222222222222",
                        "type": "agent",
                        "slug": "reviewer",
                        "display_name": "评审智能体",
                        "visibility": "public",
                        "source": "agents/reviewer",
                    },
                    {
                        "id": "33333333-3333-5333-8333-333333333333",
                        "type": "workflow",
                        "slug": "review-flow",
                        "display_name": "评审工作流",
                        "visibility": "public",
                        "source": "workflows/review.yaml",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    workflow_path.write_text(
        f"""schema_version: 2
name: review-flow
description: {description}
entrypoint: review
nodes:
  - id: review
    type: action
    action:
      kind: agent
      name: reviewer
edges: []
""",
        encoding="utf-8",
    )


async def _latest_version(factory, resource_id: str) -> tuple[ResourceVersion, int]:
    async with factory() as session:
        resource = await session.get(Resource, resource_id)
        version = await session.scalar(
            select(ResourceVersion).where(
                ResourceVersion.resource_id == resource_id,
                ResourceVersion.version == resource.latest_version,
            )
        )
        return version, resource.latest_version


@pytest.mark.asyncio
async def test_bundled_seed_self_heals_existing_system_owned(tmp_path: Path) -> None:
    engine, factory = await _make_factory(tmp_path, "self-heal.db")
    resource_id = "33333333-3333-5333-8333-333333333333"
    source_root = tmp_path / "source"
    _write_workflow_manifest(source_root / "bundled-resources.json", "Review v1")
    manifest_path = source_root / "bundled-resources.json"

    storage = ResourceStorage(tmp_path / "runtime")
    first = await seed_bundled_resources(
        factory,
        storage,
        manifest_path=manifest_path,
        source_root=source_root,
        owner_id="system-owner",
    )
    assert first.created == 2

    async with factory() as session:
        resource = await session.get(Resource, resource_id)
        resource.system_owned = True
        await session.commit()

    second = await seed_bundled_resources(
        factory,
        storage,
        manifest_path=manifest_path,
        source_root=source_root,
        owner_id="system-owner",
    )
    assert second.unchanged == 2
    async with factory() as session:
        resource = await session.get(Resource, resource_id)
        assert resource.system_owned is False
    await engine.dispose()


@pytest.mark.asyncio
async def test_bundled_seed_syncs_existing_display_name(tmp_path: Path) -> None:
    engine, factory = await _make_factory(tmp_path, "display-name.db")
    resource_id = "33333333-3333-5333-8333-333333333333"
    source_root = tmp_path / "source"
    manifest_path = source_root / "bundled-resources.json"
    _write_workflow_manifest(manifest_path, "Review v1")
    storage = ResourceStorage(tmp_path / "runtime")
    first = await seed_bundled_resources(
        factory,
        storage,
        manifest_path=manifest_path,
        source_root=source_root,
        owner_id="system-owner",
    )
    assert first.created == 2

    async with factory() as session:
        resource = await session.get(Resource, resource_id)
        assert resource.display_name == "评审工作流"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["resources"]:
        if item["slug"] == "review-flow":
            item["display_name"] = "评审工作流（新名）"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    second = await seed_bundled_resources(
        factory,
        storage,
        manifest_path=manifest_path,
        source_root=source_root,
        owner_id="system-owner",
    )
    assert second.unchanged == 2
    async with factory() as session:
        resource = await session.get(Resource, resource_id)
        assert resource.display_name == "评审工作流（新名）"
    await engine.dispose()


@pytest.mark.asyncio
async def test_bundled_seed_keep_skips_modified_resource(tmp_path: Path) -> None:
    engine, factory = await _make_factory(tmp_path, "keep.db")
    resource_id = "33333333-3333-5333-8333-333333333333"
    source_root = tmp_path / "source"
    manifest_path = source_root / "bundled-resources.json"
    _write_workflow_manifest(manifest_path, "Review v1")
    storage = ResourceStorage(tmp_path / "runtime")
    await seed_bundled_resources(
        factory,
        storage,
        manifest_path=manifest_path,
        source_root=source_root,
        owner_id="system-owner",
    )

    user_content = {
        "schema_version": 2,
        "name": "review-flow",
        "description": "User edit",
        "entrypoint": "review",
        "nodes": [{"id": "review", "type": "action", "action": {"kind": "agent", "name": "reviewer"}}],
        "edges": [],
    }
    async with factory() as session:
        resource = await session.get(Resource, resource_id)
        resource.latest_version = 2
        session.add(
            ResourceVersion(
                id="user-v2",
                resource_id=resource_id,
                version=2,
                content_hash="e" * 64,
                storage_key=f"workflows/{resource_id}/versions/2",
                scan_result={"status": "published"},
                content=user_content,
                created_by="system-owner",
            )
        )
        await session.commit()

    _write_workflow_manifest(manifest_path, "Review v2 bundled")
    report = await seed_bundled_resources(
        factory,
        storage,
        manifest_path=manifest_path,
        source_root=source_root,
        owner_id="system-owner",
        conflict_policy="keep",
    )
    assert report.skipped == 1
    assert report.updated == 0
    latest, latest_version = await _latest_version(factory, resource_id)
    assert latest_version == 2
    assert latest.content_hash == "e" * 64
    assert latest.content == user_content
    await engine.dispose()


@pytest.mark.asyncio
async def test_bundled_seed_override_publishes_bundled_version(tmp_path: Path) -> None:
    engine, factory = await _make_factory(tmp_path, "override.db")
    resource_id = "33333333-3333-5333-8333-333333333333"
    source_root = tmp_path / "source"
    manifest_path = source_root / "bundled-resources.json"
    _write_workflow_manifest(manifest_path, "Review v1")
    storage = ResourceStorage(tmp_path / "runtime")
    await seed_bundled_resources(
        factory,
        storage,
        manifest_path=manifest_path,
        source_root=source_root,
        owner_id="system-owner",
    )

    async with factory() as session:
        resource = await session.get(Resource, resource_id)
        resource.latest_version = 2
        session.add(
            ResourceVersion(
                id="user-v2",
                resource_id=resource_id,
                version=2,
                content_hash="e" * 64,
                storage_key=f"workflows/{resource_id}/versions/2",
                scan_result={"status": "published"},
                content={"description": "User edit"},
                created_by="system-owner",
            )
        )
        await session.commit()

    _write_workflow_manifest(manifest_path, "Review v2 bundled")
    report = await seed_bundled_resources(
        factory,
        storage,
        manifest_path=manifest_path,
        source_root=source_root,
        owner_id="system-owner",
        conflict_policy="override",
    )
    assert report.skipped == 0
    assert report.updated == 1
    latest, latest_version = await _latest_version(factory, resource_id)
    assert latest_version == 3
    assert latest.scan_result["status"] == "trusted_bundled_manifest"
    assert latest.content["description"] == "Review v2 bundled"
    await engine.dispose()


@pytest.mark.asyncio
async def test_bundled_seed_keep_still_updates_untouched_resource(tmp_path: Path) -> None:
    engine, factory = await _make_factory(tmp_path, "untouched.db")
    resource_id = "33333333-3333-5333-8333-333333333333"
    source_root = tmp_path / "source"
    manifest_path = source_root / "bundled-resources.json"
    _write_workflow_manifest(manifest_path, "Review v1")
    storage = ResourceStorage(tmp_path / "runtime")
    await seed_bundled_resources(
        factory,
        storage,
        manifest_path=manifest_path,
        source_root=source_root,
        owner_id="system-owner",
    )

    _write_workflow_manifest(manifest_path, "Review v2 bundled")
    report = await seed_bundled_resources(
        factory,
        storage,
        manifest_path=manifest_path,
        source_root=source_root,
        owner_id="system-owner",
        conflict_policy="keep",
    )
    assert report.skipped == 0
    assert report.updated == 1
    latest, latest_version = await _latest_version(factory, resource_id)
    assert latest_version == 2
    assert latest.content["description"] == "Review v2 bundled"
    await engine.dispose()


@pytest.mark.asyncio
async def test_bundled_seed_rejects_invalid_conflict_policy(tmp_path: Path) -> None:
    engine, factory = await _make_factory(tmp_path, "invalid-policy.db")
    source_root = tmp_path / "source"
    _write_workflow_manifest(source_root / "bundled-resources.json", "Review v1")
    with pytest.raises(ValueError, match="conflict policy"):
        await seed_bundled_resources(
            factory,
            ResourceStorage(tmp_path / "runtime"),
            manifest_path=source_root / "bundled-resources.json",
            source_root=source_root,
            owner_id="system-owner",
            conflict_policy="force",
        )
    await engine.dispose()
