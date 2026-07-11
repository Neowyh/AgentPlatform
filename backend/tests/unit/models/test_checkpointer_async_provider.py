"""Tests for ideer.runtime.checkpointer.async_provider — async checkpointer factory."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(type: str, connection_string: str | None = None):
    return SimpleNamespace(type=type, connection_string=connection_string)


def _make_db_config(backend: str, postgres_url: str | None = None, checkpointer_sqlite_path: str = "test.db"):
    return SimpleNamespace(
        backend=backend,
        postgres_url=postgres_url,
        checkpointer_sqlite_path=checkpointer_sqlite_path,
    )


def _make_app_config(checkpointer=None, database=None):
    return SimpleNamespace(checkpointer=checkpointer, database=database)


# ---------------------------------------------------------------------------
# _prepare_sqlite_checkpointer_path
# ---------------------------------------------------------------------------


class TestPrepareSqliteCheckpointerPath:
    @patch("ideer.runtime.checkpointer.async_provider.ensure_sqlite_parent_dir")
    @patch("ideer.runtime.checkpointer.async_provider.resolve_sqlite_conn_str", return_value="/resolved/path.db")
    def test_resolves_and_ensures_parent(self, mock_resolve, mock_ensure):
        from ideer.runtime.checkpointer.async_provider import _prepare_sqlite_checkpointer_path

        result = _prepare_sqlite_checkpointer_path("raw.db")
        assert result == "/resolved/path.db"
        mock_resolve.assert_called_once_with("raw.db")
        mock_ensure.assert_called_once_with("/resolved/path.db")


class TestPrepareDatabaseSqliteCheckpointerPath:
    @patch("ideer.runtime.checkpointer.async_provider.ensure_sqlite_parent_dir")
    def test_uses_db_config_path(self, mock_ensure):
        from ideer.runtime.checkpointer.async_provider import _prepare_database_sqlite_checkpointer_path

        db_config = SimpleNamespace(checkpointer_sqlite_path="/custom/path.db")
        result = _prepare_database_sqlite_checkpointer_path(db_config)
        assert result == "/custom/path.db"
        mock_ensure.assert_called_once_with("/custom/path.db")


# ---------------------------------------------------------------------------
# _async_checkpointer
# ---------------------------------------------------------------------------


class TestAsyncCheckpointer:
    @pytest.mark.asyncio
    async def test_memory_type(self):
        from ideer.runtime.checkpointer.async_provider import _async_checkpointer

        config = _make_config("memory")
        async with _async_checkpointer(config) as cp:
            # InMemorySaver is a real object
            assert cp is not None

    @pytest.mark.asyncio
    async def test_sqlite_type_import_error(self):
        from ideer.runtime.checkpointer.async_provider import _async_checkpointer

        config = _make_config("sqlite", "test.db")
        with patch.dict("sys.modules", {"langgraph.checkpoint.sqlite.aio": None}):
            with pytest.raises(ImportError):
                async with _async_checkpointer(config):
                    pass

    @pytest.mark.asyncio
    async def test_postgres_type_import_error(self):
        from ideer.runtime.checkpointer.async_provider import _async_checkpointer

        config = _make_config("postgres", "postgresql://localhost/db")
        with patch.dict("sys.modules", {"langgraph.checkpoint.postgres.aio": None}):
            with pytest.raises(ImportError):
                async with _async_checkpointer(config):
                    pass

    @pytest.mark.asyncio
    async def test_postgres_no_connection_string(self):
        from ideer.runtime.checkpointer.async_provider import _async_checkpointer

        config = _make_config("postgres", None)
        # Need to make postgres import succeed
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"langgraph.checkpoint.postgres.aio": mock_module}):
            with pytest.raises(ValueError, match="connection_string is required"):
                async with _async_checkpointer(config):
                    pass

    @pytest.mark.asyncio
    async def test_unknown_type(self):
        from ideer.runtime.checkpointer.async_provider import _async_checkpointer

        config = _make_config("unknown_backend")
        with pytest.raises(ValueError, match="Unknown checkpointer type"):
            async with _async_checkpointer(config):
                pass

    @pytest.mark.asyncio
    async def test_sqlite_type_success(self):
        from ideer.runtime.checkpointer.async_provider import _async_checkpointer

        mock_saver = AsyncMock()
        mock_saver.setup = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_module = MagicMock()
        mock_module.AsyncSqliteSaver.from_conn_string.return_value = mock_cm

        config = _make_config("sqlite", "test.db")
        with patch.dict("sys.modules", {"langgraph.checkpoint.sqlite.aio": mock_module}):
            with patch("ideer.runtime.checkpointer.async_provider._prepare_sqlite_checkpointer_path", return_value="/resolved.db"):
                async with _async_checkpointer(config) as cp:
                    assert cp is mock_saver

    @pytest.mark.asyncio
    async def test_postgres_type_success(self):
        from ideer.runtime.checkpointer.async_provider import _async_checkpointer

        mock_saver = AsyncMock()
        mock_saver.setup = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_module = MagicMock()
        mock_module.AsyncPostgresSaver.from_conn_string.return_value = mock_cm

        config = _make_config("postgres", "postgresql://localhost/db")
        with patch.dict("sys.modules", {"langgraph.checkpoint.postgres.aio": mock_module}):
            async with _async_checkpointer(config) as cp:
                assert cp is mock_saver


# ---------------------------------------------------------------------------
# _async_checkpointer_from_database
# ---------------------------------------------------------------------------


class TestAsyncCheckpointerFromDatabase:
    @pytest.mark.asyncio
    async def test_memory_backend(self):
        from ideer.runtime.checkpointer.async_provider import _async_checkpointer_from_database

        db_config = _make_db_config("memory")
        async with _async_checkpointer_from_database(db_config) as cp:
            assert cp is not None

    @pytest.mark.asyncio
    async def test_sqlite_backend(self):
        from ideer.runtime.checkpointer.async_provider import _async_checkpointer_from_database

        mock_saver = AsyncMock()
        mock_saver.setup = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_module = MagicMock()
        mock_module.AsyncSqliteSaver.from_conn_string.return_value = mock_cm

        db_config = _make_db_config("sqlite")
        with patch.dict("sys.modules", {"langgraph.checkpoint.sqlite.aio": mock_module}):
            with patch("ideer.runtime.checkpointer.async_provider._prepare_database_sqlite_checkpointer_path", return_value="/resolved.db"):
                async with _async_checkpointer_from_database(db_config) as cp:
                    assert cp is mock_saver

    @pytest.mark.asyncio
    async def test_postgres_backend_no_url(self):
        from ideer.runtime.checkpointer.async_provider import _async_checkpointer_from_database

        db_config = _make_db_config("postgres", postgres_url=None)
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"langgraph.checkpoint.postgres.aio": mock_module}):
            with pytest.raises(ValueError, match="postgres_url is required"):
                async with _async_checkpointer_from_database(db_config):
                    pass

    @pytest.mark.asyncio
    async def test_postgres_backend_success(self):
        from ideer.runtime.checkpointer.async_provider import _async_checkpointer_from_database

        mock_saver = AsyncMock()
        mock_saver.setup = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_module = MagicMock()
        mock_module.AsyncPostgresSaver.from_conn_string.return_value = mock_cm

        db_config = _make_db_config("postgres", postgres_url="postgresql://localhost/db")
        with patch.dict("sys.modules", {"langgraph.checkpoint.postgres.aio": mock_module}):
            async with _async_checkpointer_from_database(db_config) as cp:
                assert cp is mock_saver

    @pytest.mark.asyncio
    async def test_sqlite_import_error(self):
        from ideer.runtime.checkpointer.async_provider import _async_checkpointer_from_database

        db_config = _make_db_config("sqlite")
        with patch.dict("sys.modules", {"langgraph.checkpoint.sqlite.aio": None}):
            with pytest.raises(ImportError):
                async with _async_checkpointer_from_database(db_config):
                    pass

    @pytest.mark.asyncio
    async def test_postgres_import_error(self):
        from ideer.runtime.checkpointer.async_provider import _async_checkpointer_from_database

        db_config = _make_db_config("postgres", postgres_url="postgresql://localhost/db")
        with patch.dict("sys.modules", {"langgraph.checkpoint.postgres.aio": None}):
            with pytest.raises(ImportError):
                async with _async_checkpointer_from_database(db_config):
                    pass

    @pytest.mark.asyncio
    async def test_unknown_backend(self):
        from ideer.runtime.checkpointer.async_provider import _async_checkpointer_from_database

        db_config = _make_db_config("firestore")
        with pytest.raises(ValueError, match="Unknown database backend"):
            async with _async_checkpointer_from_database(db_config):
                pass


# ---------------------------------------------------------------------------
# make_checkpointer
# ---------------------------------------------------------------------------


class TestMakeCheckpointer:
    @pytest.mark.asyncio
    async def test_default_in_memory(self):
        from ideer.runtime.checkpointer.async_provider import make_checkpointer

        app_config = _make_app_config(checkpointer=None, database=None)
        async with make_checkpointer(app_config) as cp:
            assert cp is not None

    @pytest.mark.asyncio
    async def test_legacy_checkpointer_config(self):
        from ideer.runtime.checkpointer.async_provider import make_checkpointer

        app_config = _make_app_config(checkpointer=_make_config("memory"))
        async with make_checkpointer(app_config) as cp:
            assert cp is not None

    @pytest.mark.asyncio
    async def test_unified_database_config(self):
        from ideer.runtime.checkpointer.async_provider import make_checkpointer

        db_config = _make_db_config("memory")
        app_config = _make_app_config(checkpointer=None, database=db_config)
        async with make_checkpointer(app_config) as cp:
            assert cp is not None

    @pytest.mark.asyncio
    async def test_legacy_takes_precedence_over_database(self):
        from ideer.runtime.checkpointer.async_provider import make_checkpointer

        # Both set, legacy should win
        app_config = _make_app_config(
            checkpointer=_make_config("memory"),
            database=_make_db_config("sqlite"),
        )
        async with make_checkpointer(app_config) as cp:
            assert cp is not None

    @pytest.mark.asyncio
    async def test_no_config_uses_default(self):
        from ideer.runtime.checkpointer.async_provider import make_checkpointer

        with patch("ideer.runtime.checkpointer.async_provider.get_app_config") as mock_get:
            mock_get.return_value = _make_app_config(checkpointer=None, database=None)
            async with make_checkpointer() as cp:
                assert cp is not None

    @pytest.mark.asyncio
    async def test_database_memory_skipped(self):
        """When database.backend is 'memory', falls through to InMemorySaver."""
        from ideer.runtime.checkpointer.async_provider import make_checkpointer

        db_config = _make_db_config("memory")
        app_config = _make_app_config(checkpointer=None, database=db_config)
        async with make_checkpointer(app_config) as cp:
            assert cp is not None
