"""Tests for ideer.runtime.store.provider — comprehensive coverage."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import ideer.runtime.store.provider as mod

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(backend_type: str = "memory", connection_string: str | None = None) -> SimpleNamespace:
    """Build a minimal CheckpointerConfig-like object."""
    return SimpleNamespace(type=backend_type, connection_string=connection_string)


# ---------------------------------------------------------------------------
# Autouse fixture: reset singleton between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singleton():
    mod.reset_store()
    yield
    mod.reset_store()


# ===================================================================
# _sync_store_cm — memory backend
# ===================================================================


class TestSyncStoreCmMemory:
    def test_memory_yields_in_memory_store(self):
        with patch.dict("sys.modules", {"langgraph.store.memory": MagicMock()}) as _:
            config = _make_config("memory")
            with mod._sync_store_cm(config) as store:
                assert store is not None


# ===================================================================
# _sync_store_cm — sqlite backend
# ===================================================================


class TestSyncStoreCmSqlite:
    def test_sqlite_success(self):
        mock_sqlite_mod = MagicMock()
        mock_store = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_store)
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_sqlite_mod.SqliteStore.from_conn_string.return_value = mock_cm

        with (
            patch.dict("sys.modules", {"langgraph.store.sqlite": mock_sqlite_mod}),
            patch.object(mod, "resolve_sqlite_conn_str", return_value="/tmp/test.db"),
            patch.object(mod, "ensure_sqlite_parent_dir"),
        ):
            config = _make_config("sqlite", "test.db")
            with mod._sync_store_cm(config) as store:
                assert store is mock_store
            mock_store.setup.assert_called_once()

    def test_sqlite_import_error(self):
        with patch.dict("sys.modules", {"langgraph.store.sqlite": None}):
            # Force ImportError
            with patch.dict("sys.modules", {"langgraph.store.sqlite": None}):
                config = _make_config("sqlite")
                with pytest.raises(ImportError, match="langgraph-checkpoint-sqlite"):
                    with mod._sync_store_cm(config):
                        pass


# ===================================================================
# _sync_store_cm — postgres backend
# ===================================================================


class TestSyncStoreCmPostgres:
    def test_postgres_success(self):
        mock_pg_mod = MagicMock()
        mock_store = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_store)
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_pg_mod.PostgresStore.from_conn_string.return_value = mock_cm

        with patch.dict("sys.modules", {"langgraph.store.postgres": mock_pg_mod}):
            config = _make_config("postgres", "postgresql://localhost/db")
            with mod._sync_store_cm(config) as store:
                assert store is mock_store
            mock_store.setup.assert_called_once()

    def test_postgres_import_error(self):
        with patch.dict("sys.modules", {"langgraph.store.postgres": None}):
            config = _make_config("postgres", "postgresql://localhost/db")
            with pytest.raises(ImportError, match="langgraph-checkpoint-postgres"):
                with mod._sync_store_cm(config):
                    pass

    def test_postgres_no_connection_string(self):
        mock_pg_mod = MagicMock()
        with patch.dict("sys.modules", {"langgraph.store.postgres": mock_pg_mod}):
            config = _make_config("postgres", None)
            with pytest.raises(ValueError, match="connection_string is required"):
                with mod._sync_store_cm(config):
                    pass


# ===================================================================
# _sync_store_cm — unknown backend
# ===================================================================


class TestSyncStoreCmUnknown:
    def test_unknown_backend_raises(self):
        config = _make_config("redis")
        with pytest.raises(ValueError, match="Unknown store backend type"):
            with mod._sync_store_cm(config):
                pass


# ===================================================================
# get_store — singleton
# ===================================================================


class TestGetStore:
    def test_returns_singleton(self):
        mock_inmem = MagicMock()
        with (
            patch("ideer.config.checkpointer_config.get_checkpointer_config", return_value=None),
            patch("ideer.config.app_config._app_config", None),
            patch("ideer.runtime.store.provider.get_app_config", side_effect=FileNotFoundError),
            patch("langgraph.store.memory.InMemoryStore", return_value=mock_inmem),
        ):
            store1 = mod.get_store()
            store2 = mod.get_store()
            assert store1 is store2 is mock_inmem

    def test_returns_configured_store(self):
        mock_store = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_store)
        mock_cm.__exit__ = MagicMock(return_value=False)
        config = _make_config("memory")

        with (
            patch("ideer.config.checkpointer_config.get_checkpointer_config", return_value=config),
            patch.object(mod, "_sync_store_cm", return_value=mock_cm),
        ):
            store = mod.get_store()
            assert store is mock_store

    def test_no_config_no_app_config_fallback_inmemory(self):
        mock_inmem = MagicMock()
        with (
            patch("ideer.config.checkpointer_config.get_checkpointer_config", return_value=None),
            patch("ideer.config.app_config._app_config", None),
            patch("ideer.runtime.store.provider.get_app_config", side_effect=FileNotFoundError),
            patch("langgraph.store.memory.InMemoryStore", return_value=mock_inmem),
        ):
            store = mod.get_store()
            assert store is mock_inmem

    def test_no_config_but_app_config_exists_then_gets_config(self):
        mock_inmem = MagicMock()
        mock_app = MagicMock()
        with (
            patch("ideer.config.checkpointer_config.get_checkpointer_config", side_effect=[None, None]),
            patch("ideer.config.app_config._app_config", None),
            patch("ideer.runtime.store.provider.get_app_config", return_value=mock_app),
            patch("langgraph.store.memory.InMemoryStore", return_value=mock_inmem),
        ):
            store = mod.get_store()
            assert store is mock_inmem


# ===================================================================
# reset_store
# ===================================================================


class TestResetStore:
    def test_reset_clears_singleton(self):
        mock_inmem = MagicMock()
        with (
            patch("ideer.config.checkpointer_config.get_checkpointer_config", return_value=None),
            patch("ideer.config.app_config._app_config", None),
            patch("ideer.runtime.store.provider.get_app_config", side_effect=FileNotFoundError),
            patch("langgraph.store.memory.InMemoryStore", return_value=mock_inmem),
        ):
            mod.get_store()
            assert mod._store is not None
            mod.reset_store()
            assert mod._store is None

    def test_reset_with_context_manager(self):
        mock_cm = MagicMock()
        mock_cm.__exit__ = MagicMock(return_value=False)
        mod._store_ctx = mock_cm
        mod._store = MagicMock()
        mod.reset_store()
        mock_cm.__exit__.assert_called_once_with(None, None, None)
        assert mod._store is None

    def test_reset_with_context_manager_exception(self):
        mock_cm = MagicMock()
        mock_cm.__exit__ = MagicMock(side_effect=RuntimeError("boom"))
        mod._store_ctx = mock_cm
        mod._store = MagicMock()
        # Should not raise — exception is swallowed with a warning
        mod.reset_store()
        assert mod._store is None


# ===================================================================
# store_context — sync context manager
# ===================================================================


class TestStoreContext:
    def test_yields_inmemory_when_no_checkpointer(self):
        mock_inmem = MagicMock()
        mock_app = MagicMock()
        mock_app.checkpointer = None
        with (
            patch("ideer.runtime.store.provider.get_app_config", return_value=mock_app),
            patch("langgraph.store.memory.InMemoryStore", return_value=mock_inmem),
        ):
            with mod.store_context() as store:
                assert store is mock_inmem

    def test_yields_from_sync_store_cm(self):
        mock_store = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_store)
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_app = MagicMock()
        mock_app.checkpointer = _make_config("memory")

        with (
            patch("ideer.runtime.store.provider.get_app_config", return_value=mock_app),
            patch.object(mod, "_sync_store_cm", return_value=mock_cm),
        ):
            with mod.store_context() as store:
                assert store is mock_store
