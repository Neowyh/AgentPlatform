"""Canonical API draft contracts that require real persistence."""

from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from app.gateway.routers import resources
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource, ResourceDependency, ResourceDraft
from ideer.persistence.models.user import UserModel, UserRole
from ideer.resources.service import ResourceAction, ResourceActor, ResourceService


def _actor() -> ResourceActor:
    return ResourceActor(
        user_id="owner",
        department_id="dept-a",
        role="user",
        permissions=frozenset({ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE}),
    )


@pytest.mark.asyncio
async def test_workflow_draft_resolves_agent_alias_and_persists_uuid_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'resources-api.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    current_user = UserModel(
        id="owner",
        username="owner@test.com",
        role=UserRole.USER,
        department_id="dept-a",
        disabled=False,
    )
    async with factory() as session:
        session.add(current_user)
        await session.commit()
        service = ResourceService(session, _actor())
        agent = await service.create_resource(
            resource_type="agent",
            slug="review-agent",
            display_name="Review Agent",
            storage_kind="filesystem",
        )
        workflow = await service.create_resource(
            resource_type="workflow",
            slug="review-flow",
            display_name="Review Flow",
            storage_kind="database",
        )
        await session.commit()
        agent_id = agent.id
        workflow_id = workflow.id

    monkeypatch.setattr(resources, "get_session_factory", lambda: factory)
    monkeypatch.setattr(resources, "get_paths", lambda: SimpleNamespace(base_dir=tmp_path))

    result = await resources.save_workflow_draft(
        workflow_id,
        resources.WorkflowDraftRequest(
            content={
                "schema_version": 2,
                "name": "review-flow",
                "entrypoint": "review",
                "nodes": [
                    {
                        "id": "review",
                        "type": "action",
                        "action": {"kind": "agent", "name": "review-agent"},
                    }
                ],
                "edges": [],
            },
            expected_revision=0,
        ),
        current_user,
    )

    assert result["revision"] == 1
    async with factory() as session:
        draft = await session.get(ResourceDraft, workflow_id)
        dependency = (await session.execute(select(ResourceDependency).where(ResourceDependency.source_resource_id == workflow_id))).scalar_one()
        assert draft is not None
        assert draft.content["nodes"][0]["action"]["name"] == agent_id
        assert dependency.target_resource_id == agent_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_workflow_draft_dedupes_agent_reuse_across_nodes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'resources-dedup.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    current_user = UserModel(
        id="owner",
        username="owner@test.com",
        role=UserRole.USER,
        department_id="dept-a",
        disabled=False,
    )
    async with factory() as session:
        session.add(current_user)
        await session.commit()
        service = ResourceService(session, _actor())
        agent = await service.create_resource(
            resource_type="agent",
            slug="review-agent",
            display_name="Review Agent",
            storage_kind="filesystem",
        )
        workflow = await service.create_resource(
            resource_type="workflow",
            slug="review-flow",
            display_name="Review Flow",
            storage_kind="database",
        )
        await session.commit()
        agent_id = agent.id
        workflow_id = workflow.id

    monkeypatch.setattr(resources, "get_session_factory", lambda: factory)
    monkeypatch.setattr(resources, "get_paths", lambda: SimpleNamespace(base_dir=tmp_path))

    result = await resources.save_workflow_draft(
        workflow_id,
        resources.WorkflowDraftRequest(
            content={
                "schema_version": 2,
                "name": "review-flow",
                "entrypoint": "review",
                "nodes": [
                    {
                        "id": "review",
                        "type": "action",
                        "action": {"kind": "agent", "name": "review-agent"},
                    },
                    {
                        "id": "summarize",
                        "type": "action",
                        "action": {"kind": "agent", "name": "review-agent"},
                    },
                ],
                "edges": [{"from": "review", "to": "summarize"}],
            },
            expected_revision=0,
        ),
        current_user,
    )

    assert result["revision"] == 1
    async with factory() as session:
        draft = await session.get(ResourceDraft, workflow_id)
        dependencies = list((await session.execute(select(ResourceDependency).where(ResourceDependency.source_resource_id == workflow_id))).scalars())
        assert draft is not None
        names = [node["action"]["name"] for node in draft.content["nodes"]]
        assert names == [agent_id, agent_id]
        assert [item.target_resource_id for item in dependencies] == [agent_id]
    await engine.dispose()


@pytest.mark.asyncio
async def test_canonical_agent_zip_import_creates_private_uuid_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'agent-import.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    current_user = UserModel(
        id="owner",
        username="owner@test.com",
        role=UserRole.USER,
        department_id="dept-a",
        disabled=False,
    )
    async with factory() as session:
        session.add(current_user)
        await session.commit()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(
            "config.yaml",
            "name: imported-agent\ndescription: Imported\n",
        )
        bundle.writestr("SOUL.md", "Review carefully.\n")
    archive.seek(0)
    monkeypatch.setattr(resources, "get_session_factory", lambda: factory)
    monkeypatch.setattr(
        resources,
        "get_paths",
        lambda: SimpleNamespace(base_dir=tmp_path),
    )

    async def _audit(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(resources, "record_audit", _audit)
    payload = await resources.import_agent_resource(
        UploadFile(filename="imported.zip", file=archive),
        current_user,
    )

    assert payload["slug"] == "imported-agent"
    assert payload["visibility"] == "private"
    assert payload["latest_version"] == 1
    assert (tmp_path / "resources" / "agents" / payload["id"] / "versions" / "1" / "config.yaml").is_file()
    await engine.dispose()


@pytest.mark.asyncio
async def test_agent_draft_rewrites_skill_alias_to_uuid_content_and_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'agent-draft.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    current_user = UserModel(
        id="owner",
        username="owner@test.com",
        role=UserRole.USER,
        department_id="dept-a",
        disabled=False,
    )
    async with factory() as session:
        session.add(current_user)
        await session.commit()
        service = ResourceService(session, _actor())
        skill = await service.create_resource(
            resource_type="skill",
            slug="review-skill",
            display_name="Review Skill",
            storage_kind="filesystem",
        )
        agent = await service.create_resource(
            resource_type="agent",
            slug="review-agent",
            display_name="Review Agent",
            storage_kind="filesystem",
        )
        await session.commit()
        skill_id = skill.id
        agent_id = agent.id

    monkeypatch.setattr(resources, "get_session_factory", lambda: factory)
    monkeypatch.setattr(resources, "get_paths", lambda: SimpleNamespace(base_dir=tmp_path))

    result = await resources.save_agent_draft(
        agent_id,
        resources.AgentDraftRequest(
            config={"description": "Reviewer", "skills": ["review-skill"]},
            soul="Review carefully.",
            expected_revision=0,
        ),
        current_user,
    )

    assert result["revision"] == 1
    async with factory() as session:
        draft = await session.get(ResourceDraft, agent_id)
        dependency = (await session.execute(select(ResourceDependency).where(ResourceDependency.source_resource_id == agent_id))).scalar_one()
        assert draft is not None
        config = yaml.safe_load((tmp_path / "resources" / draft.storage_key / "config.yaml").read_text())
        assert config["skills"] == [skill_id]
        assert config["name"] == "review-agent"
        assert dependency.target_resource_id == skill_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_bundled_workflow_draft_save_succeeds_with_deduped_agent_reuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bundled-draft.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    current_user = UserModel(
        id="owner",
        username="owner@test.com",
        role=UserRole.USER,
        department_id="dept-a",
        disabled=False,
    )
    async with factory() as session:
        session.add(current_user)
        await session.commit()
        service = ResourceService(session, _actor())
        agent = await service.create_resource(
            resource_type="agent",
            slug="review-agent",
            display_name="Review Agent",
            storage_kind="filesystem",
        )
        await session.flush()
        workflow = Resource(
            id=str(uuid.uuid4()),
            type="workflow",
            slug="fault-zeroing",
            display_name="Fault Zeroing",
            owner_id="owner",
            visibility="private",
            lifecycle_status="active",
            latest_version=0,
            draft_revision=0,
            storage_kind="database",
            storage_key="workflows/bundled",
            provenance="bundled",
            system_owned=False,
            authz_revision=1,
        )
        session.add(workflow)
        await session.commit()
        agent_id = agent.id
        workflow_id = workflow.id

    monkeypatch.setattr(resources, "get_session_factory", lambda: factory)
    monkeypatch.setattr(resources, "get_paths", lambda: SimpleNamespace(base_dir=tmp_path))

    result = await resources.save_workflow_draft(
        workflow_id,
        resources.WorkflowDraftRequest(
            content={
                "schema_version": 2,
                "name": "fault-zeroing",
                "entrypoint": "review",
                "nodes": [
                    {
                        "id": "review",
                        "type": "action",
                        "action": {"kind": "agent", "name": "review-agent"},
                    },
                    {
                        "id": "summarize",
                        "type": "action",
                        "action": {"kind": "agent", "name": "review-agent"},
                    },
                ],
                "edges": [{"from": "review", "to": "summarize"}],
            },
            expected_revision=0,
        ),
        current_user,
    )

    assert result["revision"] == 1
    async with factory() as session:
        draft = await session.get(ResourceDraft, workflow_id)
        dependencies = list((await session.execute(select(ResourceDependency).where(ResourceDependency.source_resource_id == workflow_id))).scalars())
        assert draft is not None
        names = [node["action"]["name"] for node in draft.content["nodes"]]
        assert names == [agent_id, agent_id]
        assert [item.target_resource_id for item in dependencies] == [agent_id]
    await engine.dispose()
