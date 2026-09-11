"""KnowledgeBase as the fourth first-class Resource: service-layer contracts (M2 ticket 02)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.agentplatform.audit_model  # noqa: F401 - register audit_logs
import app.agentplatform.rbac_models  # noqa: F401 - register users_ext
import app.agentplatform.resource_models  # noqa: F401 - register resource tables
import app.agentplatform.visibility_models  # noqa: F401 - register visibility tables
from app.agentplatform.knowledge.models import KnowledgeBase
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import (
    ResourceAction,
    ResourceActor,
    ResourceConflict,
    ResourceNotFound,
    ResourceService,
)
from deerflow.persistence.base import Base


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'knowledge.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


def _actor(
    user_id: str = "owner",
    *,
    department_id: str | None = "dept-a",
    role: str = "user",
    permissions: set[ResourceAction] | None = None,
) -> ResourceActor:
    return ResourceActor(
        user_id=user_id,
        department_id=department_id,
        role=role,
        permissions=frozenset(permissions or {ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE}),
    )


def _other_resource(resource_id: str, *, resource_type: str) -> Resource:
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    return Resource(
        id=resource_id,
        type=resource_type,
        slug=f"{resource_type}-{resource_id}",
        display_name=f"{resource_type} {resource_id}",
        owner_id="someone-else",
        visibility="public",
        scope_department_id=None,
        lifecycle_status="active",
        latest_version=1,
        draft_revision=0,
        storage_kind="database" if resource_type == "workflow" else "filesystem",
        storage_key=f"{resource_type}s/{resource_id}",
        system_owned=False,
        authz_revision=1,
        created_at=created_at,
        updated_at=created_at,
    )


@pytest.mark.asyncio
async def test_create_knowledge_base_requires_database_storage(session: AsyncSession) -> None:
    service = ResourceService(session, _actor())

    resource = await service.create_resource(
        resource_type="knowledge_base",
        slug="smoke-kb",
        display_name="Smoke Knowledge Base",
        storage_kind="database",
    )

    assert resource.type == "knowledge_base"
    assert resource.storage_kind == "database"
    assert resource.storage_key == f"knowledge_bases/{resource.id}"
    assert resource.visibility == "private"
    assert resource.lifecycle_status == "active"
    binding = await session.get(KnowledgeBase, resource.id)
    assert binding is not None
    assert binding.provider_dataset_id is None


@pytest.mark.asyncio
async def test_create_knowledge_base_rejects_filesystem_storage(session: AsyncSession) -> None:
    service = ResourceService(session, _actor())

    with pytest.raises(ValueError, match="database storage"):
        await service.create_resource(
            resource_type="knowledge_base",
            slug="smoke-kb",
            display_name="Smoke Knowledge Base",
            storage_kind="filesystem",
        )


@pytest.mark.asyncio
async def test_knowledge_base_cannot_depend_on_other_resources(session: AsyncSession) -> None:
    service = ResourceService(session, _actor())
    kb = await service.create_resource(
        resource_type="knowledge_base",
        slug="smoke-kb",
        display_name="Smoke Knowledge Base",
        storage_kind="database",
    )
    session.add(_other_resource("agent-target", resource_type="agent"))
    await session.commit()

    with pytest.raises(ResourceConflict, match="knowledge_base"):
        await service.replace_dependencies(kb.id, ["agent-target"])


@pytest.mark.asyncio
async def test_binding_is_opaque_and_unique_and_requires_owner(session: AsyncSession) -> None:
    service = ResourceService(session, _actor())
    kb = await service.create_resource(
        resource_type="knowledge_base",
        slug="smoke-kb",
        display_name="Smoke Knowledge Base",
        storage_kind="database",
    )

    binding = await service.bind_knowledge_dataset(kb.id, provider_dataset_id="ragflow-smoke-dataset")
    assert binding.provider_dataset_id == "ragflow-smoke-dataset"
    assert (await service.get_knowledge_binding(kb.id)).provider_dataset_id == "ragflow-smoke-dataset"

    other = await ResourceService(session, _actor("other")).create_resource(
        resource_type="knowledge_base",
        slug="other-kb",
        display_name="Other Knowledge Base",
        storage_kind="database",
    )
    with pytest.raises(ResourceConflict, match="already bound"):
        await ResourceService(session, _actor("other")).bind_knowledge_dataset(
            other.id,
            provider_dataset_id="ragflow-smoke-dataset",
        )

    with pytest.raises(ResourceNotFound):
        await ResourceService(session, _actor("intruder")).get_knowledge_binding(kb.id)
