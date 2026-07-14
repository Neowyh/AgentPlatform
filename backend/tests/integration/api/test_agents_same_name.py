"""Tests for agent same-name isolation across users.

Verifies that (name, owner_id) scoping in ResourceMetadata queries prevents
cross-user metadata corruption when two users create agents with the same name.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete as sql_delete
from sqlalchemy import select

USER_A = "user-a"
USER_B = "user-b"
AGENT_NAME = "shared-name-agent"


@pytest.fixture(autouse=True)
def _engine():
    """Initialize and clean the SQLite DB for each test."""
    import asyncio

    from ideer.persistence.engine import close_engine, get_session_factory, init_engine
    from ideer.persistence.models.resource_metadata import ResourceMetadata
    from ideer.persistence.models.user import UserModel, UserRole

    async def _setup():
        await init_engine("sqlite", url="sqlite+aiosqlite://")
        sf = get_session_factory()
        async with sf() as session:
            for uid in (USER_A, USER_B):
                existing = await session.execute(select(UserModel).where(UserModel.id == uid))
                if existing.scalar_one_or_none() is None:
                    session.add(UserModel(id=uid, username=uid, role=UserRole.USER))
            await session.commit()

    asyncio.run(_setup())
    yield

    async def _clean():
        sf = get_session_factory()
        async with sf() as session:
            await session.execute(sql_delete(ResourceMetadata))
            await session.commit()
        await close_engine()

    asyncio.run(_clean())


@pytest.mark.asyncio
async def test_load_agent_meta_for_owner_filters_correctly():
    """_load_agent_meta with for_owner= returns only that user's record."""
    from app.gateway.routers.agents import _load_agent_meta, _save_agent_meta

    await _save_agent_meta(AGENT_NAME, USER_A, {"visibility": "private", "owner_id": USER_A})
    await _save_agent_meta(AGENT_NAME, USER_B, {"visibility": "public", "owner_id": USER_B})

    meta_a = await _load_agent_meta(AGENT_NAME, USER_A, for_owner=USER_A)
    assert meta_a.get("owner_id") == USER_A
    assert meta_a.get("visibility") == "private"

    meta_b = await _load_agent_meta(AGENT_NAME, USER_B, for_owner=USER_B)
    assert meta_b.get("owner_id") == USER_B
    assert meta_b.get("visibility") == "public"

    meta_read = await _load_agent_meta(AGENT_NAME, USER_A)
    assert meta_read.get("owner_id") in (USER_A, USER_B)


@pytest.mark.asyncio
async def test_save_agent_meta_upsert_respects_owner_id():
    """_save_agent_meta upsert only updates the caller's own record."""
    from app.gateway.routers.agents import _load_agent_meta, _save_agent_meta
    from ideer.persistence.engine import get_session_factory
    from ideer.persistence.models.resource_metadata import ResourceMetadata

    await _save_agent_meta(AGENT_NAME, USER_A, {"visibility": "private", "owner_id": USER_A})
    await _save_agent_meta(AGENT_NAME, USER_B, {"visibility": "private", "owner_id": USER_B})

    await _save_agent_meta(AGENT_NAME, USER_A, {"visibility": "public", "owner_id": USER_A})

    meta_a = await _load_agent_meta(AGENT_NAME, USER_A, for_owner=USER_A)
    assert meta_a.get("visibility") == "public"

    meta_b = await _load_agent_meta(AGENT_NAME, USER_B, for_owner=USER_B)
    assert meta_b.get("visibility") == "private"

    sf = get_session_factory()
    async with sf() as session:
        stmt = select(ResourceMetadata).where(
            ResourceMetadata.resource_id == AGENT_NAME,
        )
        result = await session.execute(stmt)
        records = result.scalars().all()
        assert len(records) == 2


@pytest.mark.asyncio
async def test_toggle_agent_favorite_respects_owner_id():
    """toggle_agent_favorite only toggles the current user's record."""
    from app.gateway.routers.agents import _load_agent_meta, _save_agent_meta
    from ideer.persistence.engine import get_session_factory
    from ideer.persistence.models.resource_metadata import ResourceMetadata

    await _save_agent_meta(AGENT_NAME, USER_A, {"visibility": "private", "owner_id": USER_A})
    await _save_agent_meta(AGENT_NAME, USER_B, {"visibility": "private", "owner_id": USER_B})

    sf = get_session_factory()
    async with sf() as session:
        stmt = select(ResourceMetadata).where(
            ResourceMetadata.resource_type == "agent",
            ResourceMetadata.resource_id == AGENT_NAME,
            ResourceMetadata.owner_id == USER_A,
        )
        resource = (await session.execute(stmt)).scalar_one()
        resource.is_favorited = True
        resource.version = ResourceMetadata.version + 1
        await session.commit()

    meta_a = await _load_agent_meta(AGENT_NAME, USER_A, for_owner=USER_A)
    assert meta_a.get("is_favorited") is True

    meta_b = await _load_agent_meta(AGENT_NAME, USER_B, for_owner=USER_B)
    assert meta_b.get("is_favorited") is False


@pytest.mark.asyncio
async def test_delete_agent_hard_delete_respects_owner_id():
    """Hard-deleting metadata only removes the current user's record."""
    from sqlalchemy import delete as sql_delete

    from app.gateway.routers.agents import _load_agent_meta, _save_agent_meta
    from ideer.persistence.engine import get_session_factory
    from ideer.persistence.models.resource_metadata import ResourceMetadata

    await _save_agent_meta(AGENT_NAME, USER_A, {"visibility": "private", "owner_id": USER_A})
    await _save_agent_meta(AGENT_NAME, USER_B, {"visibility": "public", "owner_id": USER_B})

    sf = get_session_factory()
    async with sf() as session:
        await session.execute(
            sql_delete(ResourceMetadata).where(
                ResourceMetadata.resource_type == "agent",
                ResourceMetadata.resource_id == AGENT_NAME,
                ResourceMetadata.owner_id == USER_A,
            )
        )
        await session.commit()

    meta_a = await _load_agent_meta(AGENT_NAME, USER_A, for_owner=USER_A)
    assert meta_a == {}

    meta_b = await _load_agent_meta(AGENT_NAME, USER_B, for_owner=USER_B)
    assert meta_b.get("owner_id") == USER_B
    assert meta_b.get("visibility") == "public"
