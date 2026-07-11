"""Tests for ideer.runtime.checkpointer.async_provider — comprehensive coverage."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideer.runtime.checkpointer.async_provider import (
    _async_checkpointer,
    _async_checkpointer_from_database,
    _prepare_database_sqlite_checkpointer_path,
    _prepare_sqlite_checkpointer_path,
    make_checkpointer,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(backend_type: str = "memory", connection_string: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(type=backend_type, connection_string=connection_string)


def _make_db_config(backend: str = "memory", postgres_url: str | None = None, checkpointer_sqlite_path: str = "/tmp/test.db") -> SimpleNamespace:
    return SimpleNamespace(
        backend=backend,
        postgres_url=postgres_url,
        checkpointer_sqlite_path=checkpointer_sqlite_path,
    )


# ===================================================================
# _prepare_sqlite_checkpointer_path
# ===================================================================


class TestPrepareSqlitePath:
    def test_resolves_and_ensures_dir(self):
        with (
            patch("ideer.runtime.checkpointer.async_provider.resolve_sqlite_conn_str", return_value="/tmp/resolved.db") as mock_resolve,
            patch("ideer.runtime.checkpointer.async_provider.ensure_sqlite_parent_dir") as mock_ensure,
        ):
            result = _prepare_sqlite_checkpointer_path("store.db")
            assert result == "/tmp/resolved.db"
            mock_resolve.assert_called_once_with("store.db")
            mock_ensure.assert_called_once_with("/tmp/resolved.db")


# ===================================================================
# _prepare_database_sqlite_checkpointer_path
# ===================================================================


class TestPrepareDatabaseSqlitePath:
    def test_uses_checkpointer_sqlite_path(self):
        db_config = _make_db_config(checkpointer_sqlite_path="/data/cp.db")
        with patch("ideer.runtime.checkpointer.async_provider.ensure_sqlite_parent_dir") as mock_ensure:
            result = _prepare_database_sqlite_checkpointer_path(db_config)
            assert result == "/data/cp.db"
            mock_ensure.assert_called_once_with("/data/cp.db")


# ===================================================================
# _async_checkpointer — memory
# ===================================================================


class TestAsyncCheckpointerMemory:
    @pytest.mark.asyncio
    async def test_yields_in_memory_saver(self):
        mock_saver = MagicMock()
        with patch("langgraph.checkpoint.memory.InMemorySaver", return_value=mock_saver):
            async with _async_checkpointer(_make_config("memory")) as cp:
                assert cp is mock_saver


# ===================================================================
# _async_checkpointer — sqlite
# ===================================================================


class TestAsyncCheckpointerSqlite:
    @pytest.mark.asyncio
    async def test_sqlite_success(self):
        mock_saver = MagicMock()
        mock_saver.setup = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_sqlite_mod = MagicMock()
        mock_sqlite_mod.AsyncSqliteSaver.from_conn_string.return_value = mock_cm

        with (
            patch.dict("sys.modules", {"langgraph.checkpoint.sqlite.aio": mock_sqlite_mod}),
            patch("ideer.runtime.checkpointer.async_provider._prepare_sqlite_checkpointer_path", return_value="/tmp/test.db"),
        ):
            async with _async_checkpointer(_make_config("sqlite", "test.db")) as cp:
                assert cp is mock_saver
            mock_saver.setup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sqlite_default_connection_string(self):
        mock_saver = MagicMock()
        mock_saver.setup = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_sqlite_mod = MagicMock()
        mock_sqlite_mod.AsyncSqliteSaver.from_conn_string.return_value = mock_cm

        with (
            patch.dict("sys.modules", {"langgraph.checkpoint.sqlite.aio": mock_sqlite_mod}),
            patch("ideer.runtime.checkpointer.async_provider._prepare_sqlite_checkpointer_path", return_value="/tmp/store.db"),
        ):
            # connection_string is None → defaults to "store.db"
            async with _async_checkpointer(_make_config("sqlite", None)) as cp:
                assert cp is mock_saver

    @pytest.mark.asyncio
    async def test_sqlite_import_error(self):
        with patch.dict("sys.modules", {"langgraph.checkpoint.sqlite.aio": None}):
            with pytest.raises(ImportError, match="langgraph-checkpoint-sqlite"):
                async with _async_checkpointer(_make_config("sqlite", "x.db")):
                    pass


# ===================================================================
# _async_checkpointer — postgres
# ===================================================================


class TestAsyncCheckpointerPostgres:
    @pytest.mark.asyncio
    async def test_postgres_success(self):
        mock_saver = MagicMock()
        mock_saver.setup = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pg_mod = MagicMock()
        mock_pg_mod.AsyncPostgresSaver.from_conn_string.return_value = mock_cm

        with patch.dict("sys.modules", {"langgraph.checkpoint.postgres.aio": mock_pg_mod}):
            async with _async_checkpointer(_make_config("postgres", "postgresql://localhost/db")) as cp:
                assert cp is mock_saver
            mock_saver.setup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_postgres_no_connection_string_raises(self):
        mock_pg_mod = MagicMock()
        with patch.dict("sys.modules", {"langgraph.checkpoint.postgres.aio": mock_pg_mod}):
            with pytest.raises(ValueError, match="connection_string is required"):
                async with _async_checkpointer(_make_config("postgres", None)):
                    pass

    @pytest.mark.asyncio
    async def test_postgres_import_error(self):
        with patch.dict("sys.modules", {"langgraph.checkpoint.postgres.aio": None}):
            with pytest.raises(ImportError, match="langgraph-checkpoint-postgres"):
                async with _async_checkpointer(_make_config("postgres", "pg://x")):
                    pass


# ===================================================================
# _async_checkpointer — unknown type
# ===================================================================


class TestAsyncCheckpointerUnknown:
    @pytest.mark.asyncio
    async def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown checkpointer type"):
            async with _async_checkpointer(_make_config("redis")):
                pass


# ===================================================================
# _async_checkpointer_from_database — memory
# ===================================================================


class TestAsyncCheckpointerFromDatabaseMemory:
    @pytest.mark.asyncio
    async def test_memory(self):
        mock_saver = MagicMock()
        with patch("langgraph.checkpoint.memory.InMemorySaver", return_value=mock_saver):
            async with _async_checkpointer_from_database(_make_db_config("memory")) as cp:
                assert cp is mock_saver


# ===================================================================
# _async_checkpointer_from_database — sqlite
# ===================================================================


class TestAsyncCheckpointerFromDatabaseSqlite:
    @pytest.mark.asyncio
    async def test_sqlite_success(self):
        mock_saver = MagicMock()
        mock_saver.setup = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_sqlite_mod = MagicMock()
        mock_sqlite_mod.AsyncSqliteSaver.from_conn_string.return_value = mock_cm

        with (
            patch.dict("sys.modules", {"langgraph.checkpoint.sqlite.aio": mock_sqlite_mod}),
            patch("ideer.runtime.checkpointer.async_provider._prepare_database_sqlite_checkpointer_path", return_value="/tmp/test.db"),
        ):
            db_config = _make_db_config("sqlite")
            async with _async_checkpointer_from_database(db_config) as cp:
                assert cp is mock_saver

    @pytest.mark.asyncio
    async def test_sqlite_import_error(self):
        with patch.dict("sys.modules", {"langgraph.checkpoint.sqlite.aio": None}):
            with pytest.raises(ImportError, match="langgraph-checkpoint-sqlite"):
                async with _async_checkpointer_from_database(_make_db_config("sqlite")):
                    pass


# ===================================================================
# _async_checkpointer_from_database — postgres
# ===================================================================


class TestAsyncCheckpointerFromDatabasePostgres:
    @pytest.mark.asyncio
    async def test_postgres_success(self):
        mock_saver = MagicMock()
        mock_saver.setup = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pg_mod = MagicMock()
        mock_pg_mod.AsyncPostgresSaver.from_conn_string.return_value = mock_cm

        with patch.dict("sys.modules", {"langgraph.checkpoint.postgres.aio": mock_pg_mod}):
            db_config = _make_db_config("postgres", postgres_url="pg://localhost/db")
            async with _async_checkpointer_from_database(db_config) as cp:
                assert cp is mock_saver

    @pytest.mark.asyncio
    async def test_postgres_no_url_raises(self):
        mock_pg_mod = MagicMock()
        with patch.dict("sys.modules", {"langgraph.checkpoint.postgres.aio": mock_pg_mod}):
            db_config = _make_db_config("postgres", postgres_url=None)
            with pytest.raises(ValueError, match="postgres_url is required"):
                async with _async_checkpointer_from_database(db_config):
                    pass

    @pytest.mark.asyncio
    async def test_postgres_import_error(self):
        with patch.dict("sys.modules", {"langgraph.checkpoint.postgres.aio": None}):
            db_config = _make_db_config("postgres", postgres_url="pg://x")
            with pytest.raises(ImportError, match="langgraph-checkpoint-postgres"):
                async with _async_checkpointer_from_database(db_config):
                    pass


# ===================================================================
# _async_checkpointer_from_database — unknown
# ===================================================================


class TestAsyncCheckpointerFromDatabaseUnknown:
    @pytest.mark.asyncio
    async def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown database backend"):
            async with _async_checkpointer_from_database(_make_db_config("redis")):
                pass


# ===================================================================
# make_checkpointer — public API
# ===================================================================


class TestMakeCheckpointer:
    @pytest.mark.asyncio
    async def test_default_inmemory_when_no_config(self):
        mock_saver = MagicMock()
        mock_app = MagicMock()
        mock_app.checkpointer = None
        mock_app.database = None

        with (
            patch("ideer.runtime.checkpointer.async_provider.get_app_config", return_value=mock_app),
            patch("langgraph.checkpoint.memory.InMemorySaver", return_value=mock_saver),
        ):
            async with make_checkpointer() as cp:
                assert cp is mock_saver

    @pytest.mark.asyncio
    async def test_uses_legacy_checkpointer_config(self):
        mock_saver = MagicMock()
        mock_app = MagicMock()
        mock_app.checkpointer = _make_config("memory")
        mock_app.database = None

        with (
            patch("ideer.runtime.checkpointer.async_provider.get_app_config", return_value=mock_app),
            patch("langgraph.checkpoint.memory.InMemorySaver", return_value=mock_saver),
        ):
            async with make_checkpointer() as cp:
                assert cp is mock_saver

    @pytest.mark.asyncio
    async def test_uses_database_config(self):
        MagicMock()
        mock_app = MagicMock()
        mock_app.checkpointer = None
        mock_app.database = _make_db_config("sqlite")

        mock_sqlite_saver = MagicMock()
        mock_sqlite_saver.setup = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_sqlite_saver)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_sqlite_mod = MagicMock()
        mock_sqlite_mod.AsyncSqliteSaver.from_conn_string.return_value = mock_cm

        with (
            patch("ideer.runtime.checkpointer.async_provider.get_app_config", return_value=mock_app),
            patch.dict("sys.modules", {"langgraph.checkpoint.sqlite.aio": mock_sqlite_mod}),
            patch("ideer.runtime.checkpointer.async_provider._prepare_database_sqlite_checkpointer_path", return_value="/tmp/test.db"),
        ):
            async with make_checkpointer() as cp:
                assert cp is mock_sqlite_saver

    @pytest.mark.asyncio
    async def test_legacy_checkpointer_takes_priority_over_database(self):
        mock_saver = MagicMock()
        mock_app = MagicMock()
        mock_app.checkpointer = _make_config("memory")
        mock_app.database = _make_db_config("sqlite")

        with (
            patch("ideer.runtime.checkpointer.async_provider.get_app_config", return_value=mock_app),
            patch("langgraph.checkpoint.memory.InMemorySaver", return_value=mock_saver),
        ):
            async with make_checkpointer() as cp:
                assert cp is mock_saver

    @pytest.mark.asyncio
    async def test_explicit_app_config(self):
        mock_saver = MagicMock()
        mock_app = MagicMock()
        mock_app.checkpointer = _make_config("memory")

        with patch("langgraph.checkpoint.memory.InMemorySaver", return_value=mock_saver):
            async with make_checkpointer(app_config=mock_app) as cp:
                assert cp is mock_saver

    @pytest.mark.asyncio
    async def test_defaults_to_inmemory_when_db_is_memory(self):
        mock_saver = MagicMock()
        mock_app = MagicMock()
        mock_app.checkpointer = None
        mock_app.database = _make_db_config("memory")

        with (
            patch("ideer.runtime.checkpointer.async_provider.get_app_config", return_value=mock_app),
            patch("langgraph.checkpoint.memory.InMemorySaver", return_value=mock_saver),
        ):
            async with make_checkpointer() as cp:
                assert cp is mock_saver
