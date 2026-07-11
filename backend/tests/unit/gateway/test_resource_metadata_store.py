"""Tests for gateway resource metadata persistence helpers."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _Result:
    def __init__(self, resource=None):
        self._resource = resource

    def scalar_one_or_none(self):
        return self._resource


def _session_factory(session):
    sf = MagicMock()
    sf.return_value.__aenter__ = AsyncMock(return_value=session)
    sf.return_value.__aexit__ = AsyncMock(return_value=False)
    return sf


@pytest.mark.asyncio
class TestResourceMetadataStore:
    async def test_load_meta_returns_resource_fields(self):
        from app.gateway.utils import ResourceMetadataStore

        created_at = datetime(2026, 1, 2, 3, 4, 5)
        resource = MagicMock(
            visibility="department",
            owner_id="u1",
            department_id="dept-1",
            version=3,
            is_favorited=True,
            created_at=created_at,
        )
        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result(resource))

        with patch("app.gateway.utils.get_session_factory", return_value=_session_factory(session)):
            meta = await ResourceMetadataStore("agent").load_meta("agent-a")

        assert meta == {
            "visibility": "department",
            "owner_id": "u1",
            "department_id": "dept-1",
            "version": 3,
            "is_favorited": True,
            "created_at": str(created_at),
        }

    async def test_load_meta_returns_empty_when_missing_db_or_query_fails(self):
        from app.gateway.utils import ResourceMetadataStore

        store = ResourceMetadataStore("agent")

        with patch("app.gateway.utils.get_session_factory", return_value=None):
            assert await store.load_meta("agent-a") == {}

        session = MagicMock()
        session.execute = AsyncMock(side_effect=RuntimeError("database error"))
        with patch("app.gateway.utils.get_session_factory", return_value=_session_factory(session)):
            assert await store.load_meta("agent-a") == {}

    async def test_save_meta_updates_existing_resource(self):
        from app.gateway.utils import ResourceMetadataStore

        resource = MagicMock(visibility="private", department_id=None, version=1)
        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result(resource))
        session.commit = AsyncMock()

        with patch("app.gateway.utils.get_session_factory", return_value=_session_factory(session)):
            saved = await ResourceMetadataStore("workflow").save_meta(
                "daily-report",
                {"visibility": "public", "department_id": "dept-1"},
            )

        assert saved is True
        assert resource.visibility == "public"
        assert resource.department_id == "dept-1"
        assert resource.version == 2
        session.add.assert_not_called()
        session.commit.assert_awaited_once()

    async def test_save_meta_creates_missing_resource_with_defaults(self):
        from app.gateway.utils import ResourceMetadataStore

        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result(None))
        session.commit = AsyncMock()

        with patch("app.gateway.utils.get_session_factory", return_value=_session_factory(session)):
            saved = await ResourceMetadataStore("tool").save_meta("search", {})

        assert saved is True
        added = session.add.call_args[0][0]
        assert added.resource_type == "tool"
        assert added.resource_id == "search"
        assert added.owner_id == "system"
        assert added.visibility == "private"
        session.commit.assert_awaited_once()

    async def test_save_meta_returns_false_when_missing_db_or_query_fails(self):
        from app.gateway.utils import ResourceMetadataStore

        store = ResourceMetadataStore("agent")

        with patch("app.gateway.utils.get_session_factory", return_value=None):
            assert await store.save_meta("agent-a", {}) is False

        session = MagicMock()
        session.execute = AsyncMock(side_effect=RuntimeError("database error"))
        with patch("app.gateway.utils.get_session_factory", return_value=_session_factory(session)):
            assert await store.save_meta("agent-a", {}) is False

    async def test_soft_delete_sets_timestamp_when_resource_exists(self):
        from app.gateway.utils import ResourceMetadataStore

        resource = MagicMock(deleted_at=None)
        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result(resource))
        session.commit = AsyncMock()

        with patch("app.gateway.utils.get_session_factory", return_value=_session_factory(session)):
            deleted = await ResourceMetadataStore("skill").soft_delete("skill-a")

        assert deleted is True
        assert resource.deleted_at is not None
        session.commit.assert_awaited_once()

    async def test_soft_delete_succeeds_without_resource_and_handles_failures(self):
        from app.gateway.utils import ResourceMetadataStore

        store = ResourceMetadataStore("skill")

        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result(None))
        session.commit = AsyncMock()
        with patch("app.gateway.utils.get_session_factory", return_value=_session_factory(session)):
            assert await store.soft_delete("missing") is True
        session.commit.assert_not_called()

        with patch("app.gateway.utils.get_session_factory", return_value=None):
            assert await store.soft_delete("missing") is False

        session.execute = AsyncMock(side_effect=RuntimeError("database error"))
        with patch("app.gateway.utils.get_session_factory", return_value=_session_factory(session)):
            assert await store.soft_delete("missing") is False
