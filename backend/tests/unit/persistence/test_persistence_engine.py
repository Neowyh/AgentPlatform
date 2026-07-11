"""Comprehensive tests for the persistence engine lifecycle management.

Tests cover:
- _json_serializer
- _stamp_alembic_head
- _auto_create_postgres_db
- init_engine (memory, sqlite, postgres backends)
- init_engine_from_config
- get_session_factory / get_engine
- close_engine
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_engine_module():
    """Reset the module-level singletons in engine.py."""
    import ideer.persistence.engine as mod

    mod._engine = None
    mod._session_factory = None
    return mod


# ---------------------------------------------------------------------------
# _json_serializer
# ---------------------------------------------------------------------------


class TestJsonSerializer:
    def test_returns_json_string(self):
        from ideer.persistence.engine import _json_serializer

        result = _json_serializer({"key": "value"})
        assert isinstance(result, str)
        assert json.loads(result) == {"key": "value"}

    def test_chinese_characters_preserved(self):
        from ideer.persistence.engine import _json_serializer

        result = _json_serializer({"name": "你好世界"})
        assert "你好世界" in result
        # ensure_ascii=False means no \\uXXXX escapes
        assert "\\u" not in result

    def test_nested_structure(self):
        from ideer.persistence.engine import _json_serializer

        data = {"a": [1, 2, {"b": "中文"}]}
        result = _json_serializer(data)
        assert json.loads(result) == data

    def test_list_input(self):
        from ideer.persistence.engine import _json_serializer

        result = _json_serializer([1, "two", 3.0])
        assert json.loads(result) == [1, "two", 3.0]


# ---------------------------------------------------------------------------
# _stamp_alembic_head
# ---------------------------------------------------------------------------


class TestStampAlembicHead:
    @pytest.mark.asyncio
    async def test_stamps_head_revision_successfully(self, tmp_path):
        """Normal case: finds head revision and stamps it."""
        import ideer.persistence.engine as engine_mod
        from ideer.persistence.engine import _stamp_alembic_head

        # Create a fake persistence directory structure
        persistence_dir = tmp_path / "persistence"
        versions_dir = persistence_dir / "migrations" / "versions"
        versions_dir.mkdir(parents=True)

        # Migration A: base (no down_revision)
        (versions_dir / "001_initial.py").write_text('revision: str = "abc123"\ndown_revision: str | None = None\n')
        # Migration B: depends on A
        (versions_dir / "002_add_users.py").write_text('revision: str = "def456"\ndown_revision: str | None = "abc123"\n')

        conn = AsyncMock()

        # Patch __file__ so the function computes the right directory
        original_file = engine_mod.__file__
        engine_mod.__file__ = str(persistence_dir / "engine.py")
        try:
            await _stamp_alembic_head(conn, "sqlite")
        finally:
            engine_mod.__file__ = original_file

        conn.execute.assert_called()
        calls = conn.execute.call_args_list
        insert_call = calls[-1]
        assert "def456" in str(insert_call)

    @pytest.mark.asyncio
    async def test_skips_when_versions_dir_missing(self, tmp_path):
        """No versions directory -> skip stamp."""
        import ideer.persistence.engine as engine_mod
        from ideer.persistence.engine import _stamp_alembic_head

        conn = AsyncMock()

        original_file = engine_mod.__file__
        engine_mod.__file__ = str(tmp_path / "engine.py")
        try:
            await _stamp_alembic_head(conn, "sqlite")
        finally:
            engine_mod.__file__ = original_file

        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_no_head_found(self, tmp_path):
        """All revisions are also down_revisions -> no head."""
        import ideer.persistence.engine as engine_mod
        from ideer.persistence.engine import _stamp_alembic_head

        persistence_dir = tmp_path / "persistence"
        versions_dir = persistence_dir / "migrations" / "versions"
        versions_dir.mkdir(parents=True)

        # Both revisions appear as down_revision of another (circular)
        (versions_dir / "m1.py").write_text('revision: str = "aaa"\ndown_revision: str | None = "bbb"\n')
        (versions_dir / "m2.py").write_text('revision: str = "bbb"\ndown_revision: str | None = "aaa"\n')

        conn = AsyncMock()

        original_file = engine_mod.__file__
        engine_mod.__file__ = str(persistence_dir / "engine.py")
        try:
            await _stamp_alembic_head(conn, "sqlite")
        finally:
            engine_mod.__file__ = original_file

        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_non_py_files(self, tmp_path):
        """Non-.py files and __init__.py are skipped."""
        import ideer.persistence.engine as engine_mod
        from ideer.persistence.engine import _stamp_alembic_head

        persistence_dir = tmp_path / "persistence"
        versions_dir = persistence_dir / "migrations" / "versions"
        versions_dir.mkdir(parents=True)

        # Only non-migration files
        (versions_dir / "__init__.py").write_text("")
        (versions_dir / "readme.txt").write_text("docs")
        (versions_dir / "001_ok.py").write_text('revision: str = "head1"\ndown_revision: str | None = None\n')

        conn = AsyncMock()

        original_file = engine_mod.__file__
        engine_mod.__file__ = str(persistence_dir / "engine.py")
        try:
            await _stamp_alembic_head(conn, "sqlite")
        finally:
            engine_mod.__file__ = original_file

        conn.execute.assert_called()

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self, tmp_path):
        """Exceptions during stamp are caught and logged."""
        import ideer.persistence.engine as engine_mod
        from ideer.persistence.engine import _stamp_alembic_head

        persistence_dir = tmp_path / "persistence"
        versions_dir = persistence_dir / "migrations" / "versions"
        versions_dir.mkdir(parents=True)

        (versions_dir / "001.py").write_text('revision: str = "abc"\ndown_revision: str | None = None\n')

        conn = AsyncMock()
        conn.execute.side_effect = RuntimeError("db error")

        original_file = engine_mod.__file__
        engine_mod.__file__ = str(persistence_dir / "engine.py")
        try:
            # Should not raise
            await _stamp_alembic_head(conn, "sqlite")
        finally:
            engine_mod.__file__ = original_file


# ---------------------------------------------------------------------------
# _auto_create_postgres_db
# ---------------------------------------------------------------------------


class _AsyncContextManager:
    """Helper to mock an async context manager."""

    def __init__(self, return_value):
        self._return_value = return_value

    async def __aenter__(self):
        return self._return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


class AsyncContextManagerForBegin(AsyncMock):
    """AsyncMock that also works as an async context manager for engine.begin()."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


class TestAutoCreatePostgresDb:
    @pytest.mark.asyncio
    async def test_creates_database(self):
        from ideer.persistence.engine import _auto_create_postgres_db

        mock_conn = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.connect.return_value = _AsyncContextManager(mock_conn)
        mock_engine.dispose = AsyncMock()

        mock_parsed = MagicMock()
        mock_parsed.database = "myapp"
        mock_parsed.set.return_value = "postgresql:///postgres"

        with (
            patch("ideer.persistence.engine.create_async_engine", return_value=mock_engine),
            patch("sqlalchemy.engine.url.make_url", return_value=mock_parsed),
        ):
            await _auto_create_postgres_db("postgresql:///myapp")

        mock_conn.execute.assert_called_once()
        mock_engine.dispose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_when_no_database_name(self):
        from ideer.persistence.engine import _auto_create_postgres_db

        mock_parsed = MagicMock()
        mock_parsed.database = None

        with patch("sqlalchemy.engine.url.make_url", return_value=mock_parsed):
            with pytest.raises(ValueError, match="no database name"):
                await _auto_create_postgres_db("postgresql:///")

    @pytest.mark.asyncio
    async def test_escapes_quotes_in_db_name(self):
        from ideer.persistence.engine import _auto_create_postgres_db

        mock_conn = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.connect.return_value = _AsyncContextManager(mock_conn)
        mock_engine.dispose = AsyncMock()

        mock_parsed = MagicMock()
        mock_parsed.database = 'my"db'
        mock_parsed.set.return_value = "postgresql:///postgres"

        with (
            patch("ideer.persistence.engine.create_async_engine", return_value=mock_engine),
            patch("sqlalchemy.engine.url.make_url", return_value=mock_parsed),
        ):
            await _auto_create_postgres_db("postgresql:///my%22db")

        # The SQL should have escaped quotes
        call_args = mock_conn.execute.call_args
        sql_text = str(call_args[0][0])
        assert 'my""db' in sql_text


# ---------------------------------------------------------------------------
# init_engine
# ---------------------------------------------------------------------------


class TestInitEngine:
    @pytest.mark.asyncio
    async def test_memory_backend_is_noop(self):
        """Memory backend should not create any engine."""
        mod = _reset_engine_module()

        await mod.init_engine("memory")

        assert mod._engine is None
        assert mod._session_factory is None

    @pytest.mark.asyncio
    async def test_unknown_backend_raises(self):
        mod = _reset_engine_module()

        with pytest.raises(ValueError, match="Unknown persistence backend"):
            await mod.init_engine("mongodb")

    @pytest.mark.asyncio
    async def test_postgres_without_asyncpg_raises(self):
        """Postgres backend without asyncpg installed raises ImportError."""
        mod = _reset_engine_module()

        with patch.dict("sys.modules", {"asyncpg": None}):
            with pytest.raises(ImportError, match="asyncpg is not installed"):
                await mod.init_engine("postgres", url="postgresql:///test")

    @pytest.mark.asyncio
    async def test_sqlite_backend_creates_engine(self, tmp_path):
        """SQLite backend creates engine with WAL settings."""
        mod = _reset_engine_module()

        db_path = tmp_path / "test.db"
        url = f"sqlite+aiosqlite:///{db_path}"

        with patch("ideer.persistence.engine._stamp_alembic_head"):
            await mod.init_engine("sqlite", url=url, sqlite_dir=str(tmp_path))

        assert mod._engine is not None
        assert mod._session_factory is not None

        # Clean up
        await mod.close_engine()

    @pytest.mark.asyncio
    async def test_sqlite_engine_is_functional(self, tmp_path):
        """SQLite engine can create sessions and execute queries."""
        mod = _reset_engine_module()

        db_path = tmp_path / "test.db"
        url = f"sqlite+aiosqlite:///{db_path}"

        with patch("ideer.persistence.engine._stamp_alembic_head"):
            await mod.init_engine("sqlite", url=url, sqlite_dir=str(tmp_path))

        factory = mod.get_session_factory()
        assert factory is not None

        async with factory() as session:
            from sqlalchemy import text

            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

        await mod.close_engine()

    @pytest.mark.asyncio
    async def test_postgres_backend_creates_engine(self):
        """Postgres backend creates engine with pool settings."""
        mod = _reset_engine_module()

        mock_engine = MagicMock()
        mock_session_factory = MagicMock()

        mock_conn = AsyncMock()
        mock_conn.run_sync = AsyncMock(return_value=False)
        mock_conn.execute = AsyncMock()
        mock_engine.begin.return_value = _AsyncContextManager(mock_conn)

        with (
            patch.dict("sys.modules", {"asyncpg": MagicMock()}),
            patch("ideer.persistence.engine.create_async_engine", return_value=mock_engine),
            patch("ideer.persistence.engine.async_sessionmaker", return_value=mock_session_factory),
            patch("ideer.persistence.base.Base") as mock_base,
            patch("ideer.persistence.engine._stamp_alembic_head"),
        ):
            mock_base.metadata = MagicMock()

            await mod.init_engine("postgres", url="postgresql:///test", pool_size=10)

        assert mod._engine is mock_engine
        assert mod._session_factory is mock_session_factory

    @pytest.mark.asyncio
    async def test_postgres_auto_creates_db_on_does_not_exist(self):
        """When postgres DB doesn't exist, auto-creates and retries."""
        mod = _reset_engine_module()

        mock_engine = MagicMock()
        mock_session_factory = MagicMock()

        # First call to begin() raises "does not exist", second succeeds
        call_count = 0
        mock_conn_success = AsyncMock()
        mock_conn_success.run_sync = AsyncMock(return_value=False)
        mock_conn_success.execute = AsyncMock()

        class _FailingBegin:
            async def __aenter__(self_inner):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError('database "mydb" does not exist')
                return mock_conn_success

            async def __aexit__(self_inner, exc_type, exc_val, exc_tb):
                return False

        mock_engine.begin.return_value = _FailingBegin()
        mock_engine.dispose = AsyncMock()

        with (
            patch.dict("sys.modules", {"asyncpg": MagicMock()}),
            patch("ideer.persistence.engine.create_async_engine", return_value=mock_engine),
            patch("ideer.persistence.engine.async_sessionmaker", return_value=mock_session_factory),
            patch("ideer.persistence.base.Base") as mock_base,
            patch("ideer.persistence.engine._auto_create_postgres_db") as mock_auto_create,
            patch("ideer.persistence.engine._stamp_alembic_head"),
        ):
            mock_base.metadata = MagicMock()

            await mod.init_engine("postgres", url="postgresql:///mydb")

        mock_auto_create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_postgres_reraises_unrelated_errors(self):
        """Non-'does not exist' errors are re-raised."""
        mod = _reset_engine_module()

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.run_sync = AsyncMock(side_effect=RuntimeError("connection refused"))
        mock_engine.begin.return_value = _AsyncContextManager(mock_conn)

        with (
            patch.dict("sys.modules", {"asyncpg": MagicMock()}),
            patch("ideer.persistence.engine.create_async_engine", return_value=mock_engine),
            patch("ideer.persistence.engine.async_sessionmaker"),
            patch("ideer.persistence.base.Base"),
        ):
            with pytest.raises(RuntimeError, match="connection refused"):
                await mod.init_engine("postgres", url="postgresql:///test")

    @pytest.mark.asyncio
    async def test_skips_create_all_when_alembic_exists(self, tmp_path):
        """When alembic_version table exists, skip create_all."""
        mod = _reset_engine_module()

        db_path = tmp_path / "test.db"
        url = f"sqlite+aiosqlite:///{db_path}"

        # First init to create tables
        with patch("ideer.persistence.engine._stamp_alembic_head"):
            await mod.init_engine("sqlite", url=url, sqlite_dir=str(tmp_path))

        # Create the alembic_version table manually
        from sqlalchemy import text

        async with mod.get_session_factory()() as session:
            await session.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
            await session.commit()

        await mod.close_engine()
        mod._engine = None
        mod._session_factory = None

        # Second init should detect alembic_version and skip create_all
        with patch("ideer.persistence.engine._stamp_alembic_head") as mock_stamp:
            await mod.init_engine("sqlite", url=url, sqlite_dir=str(tmp_path))

        mock_stamp.assert_not_awaited()
        await mod.close_engine()

    @pytest.mark.asyncio
    async def test_stamps_when_tables_exist_but_no_alembic(self, tmp_path):
        """When tables exist but alembic_version is missing, stamps to head."""
        mod = _reset_engine_module()

        db_path = tmp_path / "test.db"
        url = f"sqlite+aiosqlite:///{db_path}"

        # First init to create tables
        with patch("ideer.persistence.engine._stamp_alembic_head"):
            await mod.init_engine("sqlite", url=url, sqlite_dir=str(tmp_path))

        await mod.close_engine()
        mod._engine = None
        mod._session_factory = None

        # Second init: tables exist but no alembic_version -> stamp
        with patch("ideer.persistence.engine._stamp_alembic_head") as mock_stamp:
            await mod.init_engine("sqlite", url=url, sqlite_dir=str(tmp_path))

        mock_stamp.assert_awaited_once()
        await mod.close_engine()

    @pytest.mark.asyncio
    async def test_import_error_on_models_is_handled(self, tmp_path):
        """When models package is not importable, logs and continues."""
        mod = _reset_engine_module()

        db_path = tmp_path / "test.db"
        url = f"sqlite+aiosqlite:///{db_path}"

        with (
            patch("ideer.persistence.engine._stamp_alembic_head"),
            patch.dict("sys.modules", {"ideer.persistence.models": None}),
        ):
            # Should not raise despite import error
            await mod.init_engine("sqlite", url=url, sqlite_dir=str(tmp_path))

        assert mod._engine is not None
        assert mod._session_factory is not None
        await mod.close_engine()


# ---------------------------------------------------------------------------
# init_engine_from_config
# ---------------------------------------------------------------------------


class TestInitEngineFromConfig:
    @pytest.mark.asyncio
    async def test_memory_config(self):
        from ideer.persistence.engine import init_engine_from_config

        config = SimpleNamespace(backend="memory")

        with patch("ideer.persistence.engine.init_engine", new_callable=AsyncMock) as mock_init:
            await init_engine_from_config(config)

        mock_init.assert_awaited_once_with("memory")

    @pytest.mark.asyncio
    async def test_sqlite_config(self):
        from ideer.persistence.engine import init_engine_from_config

        config = SimpleNamespace(
            backend="sqlite",
            app_sqlalchemy_url="sqlite+aiosqlite:///test.db",
            echo_sql=True,
            pool_size=5,
            sqlite_dir="/tmp/sqlite",
        )

        with patch("ideer.persistence.engine.init_engine", new_callable=AsyncMock) as mock_init:
            await init_engine_from_config(config)

        mock_init.assert_awaited_once_with(
            backend="sqlite",
            url="sqlite+aiosqlite:///test.db",
            echo=True,
            pool_size=5,
            sqlite_dir="/tmp/sqlite",
        )

    @pytest.mark.asyncio
    async def test_postgres_config_no_sqlite_dir(self):
        from ideer.persistence.engine import init_engine_from_config

        config = SimpleNamespace(
            backend="postgres",
            app_sqlalchemy_url="postgresql:///test",
            echo_sql=False,
            pool_size=10,
            sqlite_dir="/tmp/sqlite",
        )

        with patch("ideer.persistence.engine.init_engine", new_callable=AsyncMock) as mock_init:
            await init_engine_from_config(config)

        mock_init.assert_awaited_once_with(
            backend="postgres",
            url="postgresql:///test",
            echo=False,
            pool_size=10,
            sqlite_dir="",  # Should be empty for non-sqlite
        )


# ---------------------------------------------------------------------------
# get_session_factory / get_engine / close_engine
# ---------------------------------------------------------------------------


class TestAccessors:
    def test_get_session_factory_returns_none_initially(self):
        mod = _reset_engine_module()
        assert mod.get_session_factory() is None

    def test_get_engine_returns_none_initially(self):
        mod = _reset_engine_module()
        assert mod.get_engine() is None

    def test_get_session_factory_returns_factory_after_set(self):
        mod = _reset_engine_module()
        mock_factory = MagicMock()
        mod._session_factory = mock_factory
        assert mod.get_session_factory() is mock_factory

    def test_get_engine_returns_engine_after_set(self):
        mod = _reset_engine_module()
        mock_engine = MagicMock()
        mod._engine = mock_engine
        assert mod.get_engine() is mock_engine

    @pytest.mark.asyncio
    async def test_close_engine_disposes_and_resets(self):
        mod = _reset_engine_module()
        mock_engine = AsyncMock()
        mod._engine = mock_engine
        mod._session_factory = MagicMock()

        await mod.close_engine()

        mock_engine.dispose.assert_awaited_once()
        assert mod._engine is None
        assert mod._session_factory is None

    @pytest.mark.asyncio
    async def test_close_engine_noop_when_no_engine(self):
        mod = _reset_engine_module()
        # Should not raise
        await mod.close_engine()
        assert mod._engine is None
        assert mod._session_factory is None


# ---------------------------------------------------------------------------
# SQLite WAL pragma listener
# ---------------------------------------------------------------------------


class TestSqliteWalPragma:
    @pytest.mark.asyncio
    async def test_wal_pragmas_are_set(self, tmp_path):
        """Verify the WAL pragma listener actually sets WAL mode on SQLite."""
        mod = _reset_engine_module()

        db_path = tmp_path / "test.db"
        url = f"sqlite+aiosqlite:///{db_path}"

        with patch("ideer.persistence.engine._stamp_alembic_head"):
            await mod.init_engine("sqlite", url=url, sqlite_dir=str(tmp_path))

        # Verify WAL mode is set by checking the journal_mode pragma
        from sqlalchemy import text

        async with mod.get_session_factory()() as session:
            result = await session.execute(text("PRAGMA journal_mode"))
            journal_mode = result.scalar()
            assert journal_mode == "wal"

        # Verify foreign_keys is enabled
        async with mod.get_session_factory()() as session:
            result = await session.execute(text("PRAGMA foreign_keys"))
            fk_enabled = result.scalar()
            assert fk_enabled == 1

        await mod.close_engine()
