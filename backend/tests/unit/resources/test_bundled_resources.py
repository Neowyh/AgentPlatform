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


def test_repository_bundled_manifest_has_unique_stable_ids_and_existing_sources() -> None:
    manifest = load_bundled_manifest(REPO_ROOT / "bundled-resources.json")

    assert manifest.schema_version == 1
    assert len(manifest.resources) == 27
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
                        "visibility": "public",
                        "source": "skills/review",
                    },
                    {
                        "id": agent_id,
                        "type": "agent",
                        "slug": "reviewer",
                        "visibility": "public",
                        "source": "agents/reviewer",
                    },
                    {
                        "id": workflow_id,
                        "type": "workflow",
                        "slug": "review-flow",
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
        assert all(item.system_owned for item in resources.values())
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

    assert report.created == 27
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Resource)) == 27
        assert await session.scalar(select(func.count()).select_from(ResourceVersion)) == 27
    await engine.dispose()
