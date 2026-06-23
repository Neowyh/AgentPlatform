"""Tests for ideer.runtime.store.async_provider — async store factory."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_config(type: str, connection_string: str | None = None):
    return SimpleNamespace(type=type, connection_string=connection_string)


def _make_app_config(checkpointer=None):
    return SimpleNamespace(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# _async_store
# ---------------------------------------------------------------------------


class TestAsyncStore:
    @pytest.mark.asyncio
    async def test_memory_type(self):
        from ideer.runtime.store.async_provider import _async_store

        config = _make_config("memory")
        async with _async_store(config) as store:
            assert store is not None

    @pytest.mark.asyncio
    async def test_sqlite_type_success(self):
        from ideer.runtime.store.async_provider import _async_store

        mock_store = AsyncMock()
        mock_store.setup = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_store)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_module = MagicMock()
        mock_module.AsyncSqliteStore.from_conn_string.return_value = mock_cm

        config = _make_config("sqlite", "test.db")
        with patch.dict("sys.modules", {"langgraph.store.sqlite.aio": mock_module}):
            with patch("ideer.runtime.store.async_provider.resolve_sqlite_conn_str", return_value="/resolved.db"):
                with patch("ideer.runtime.store.async_provider.ensure_sqlite_parent_dir"):
                    async with _async_store(config) as store:
                        assert store is mock_store

    @pytest.mark.asyncio
    async def test_sqlite_type_default_conn_string(self):
        from ideer.runtime.store.async_provider import _async_store

        mock_store = AsyncMock()
        mock_store.setup = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_store)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_module = MagicMock()
        mock_module.AsyncSqliteStore.from_conn_string.return_value = mock_cm

        config = _make_config("sqlite", None)  # no connection_string
        with patch.dict("sys.modules", {"langgraph.store.sqlite.aio": mock_module}):
            with patch("ideer.runtime.store.async_provider.resolve_sqlite_conn_str", return_value="/default.db"):
                with patch("ideer.runtime.store.async_provider.ensure_sqlite_parent_dir"):
                    async with _async_store(config) as store:
                        assert store is mock_store
                    mock_module.AsyncSqliteStore.from_conn_string.assert_called_with("/default.db")

    @pytest.mark.asyncio
    async def test_sqlite_import_error(self):
        from ideer.runtime.store.async_provider import _async_store

        config = _make_config("sqlite", "test.db")
        with patch.dict("sys.modules", {"langgraph.store.sqlite.aio": None}):
            with pytest.raises(ImportError):
                async with _async_store(config):
                    pass

    @pytest.mark.asyncio
    async def test_postgres_type_success(self):
        from ideer.runtime.store.async_provider import _async_store

        mock_store = AsyncMock()
        mock_store.setup = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_store)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_module = MagicMock()
        mock_module.AsyncPostgresStore.from_conn_string.return_value = mock_cm

        config = _make_config("postgres", "postgresql://localhost/db")
        with patch.dict("sys.modules", {"langgraph.store.postgres.aio": mock_module}):
            async with _async_store(config) as store:
                assert store is mock_store

    @pytest.mark.asyncio
    async def test_postgres_no_connection_string(self):
        from ideer.runtime.store.async_provider import _async_store

        config = _make_config("postgres", None)
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"langgraph.store.postgres.aio": mock_module}):
            with pytest.raises(ValueError, match="connection_string is required"):
                async with _async_store(config):
                    pass

    @pytest.mark.asyncio
    async def test_postgres_import_error(self):
        from ideer.runtime.store.async_provider import _async_store

        config = _make_config("postgres", "postgresql://localhost/db")
        with patch.dict("sys.modules", {"langgraph.store.postgres.aio": None}):
            with pytest.raises(ImportError):
                async with _async_store(config):
                    pass

    @pytest.mark.asyncio
    async def test_unknown_type(self):
        from ideer.runtime.store.async_provider import _async_store

        config = _make_config("firestore")
        with pytest.raises(ValueError, match="Unknown store backend type"):
            async with _async_store(config):
                pass


# ---------------------------------------------------------------------------
# make_store
# ---------------------------------------------------------------------------


class TestMakeStore:
    @pytest.mark.asyncio
    async def test_no_checkpointer_config_warns(self):
        from ideer.runtime.store.async_provider import make_store

        app_config = _make_app_config(checkpointer=None)
        async with make_store(app_config) as store:
            assert store is not None

    @pytest.mark.asyncio
    async def test_with_checkpointer_config(self):
        from ideer.runtime.store.async_provider import make_store

        app_config = _make_app_config(checkpointer=_make_config("memory"))
        async with make_store(app_config) as store:
            assert store is not None

    @pytest.mark.asyncio
    async def test_default_app_config(self):
        from ideer.runtime.store.async_provider import make_store

        with patch("ideer.runtime.store.async_provider.get_app_config") as mock_get:
            mock_get.return_value = _make_app_config(checkpointer=_make_config("memory"))
            async with make_store() as store:
                assert store is not None
