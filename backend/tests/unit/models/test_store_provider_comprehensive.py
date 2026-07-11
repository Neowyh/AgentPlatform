"""Tests for ideer.runtime.store.provider — sync store factory (gap coverage)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# _sync_store_cm
# ---------------------------------------------------------------------------


class TestSyncStoreCm:
    def test_memory_type(self):
        from ideer.runtime.store.provider import _sync_store_cm

        config = SimpleNamespace(type="memory", connection_string=None)
        with _sync_store_cm(config) as store:
            assert store is not None

    def test_sqlite_type_success(self):
        from ideer.runtime.store.provider import _sync_store_cm

        mock_store = MagicMock()
        mock_store.setup = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_store)
        mock_cm.__exit__ = MagicMock(return_value=False)

        mock_module = MagicMock()
        mock_module.SqliteStore.from_conn_string.return_value = mock_cm

        config = SimpleNamespace(type="sqlite", connection_string="test.db")
        with patch.dict("sys.modules", {"langgraph.store.sqlite": mock_module}):
            with patch("ideer.runtime.store.provider.resolve_sqlite_conn_str", return_value="/resolved.db"):
                with patch("ideer.runtime.store.provider.ensure_sqlite_parent_dir"):
                    with _sync_store_cm(config) as store:
                        assert store is mock_store

    def test_sqlite_default_conn_string(self):
        from ideer.runtime.store.provider import _sync_store_cm

        mock_store = MagicMock()
        mock_store.setup = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_store)
        mock_cm.__exit__ = MagicMock(return_value=False)

        mock_module = MagicMock()
        mock_module.SqliteStore.from_conn_string.return_value = mock_cm

        config = SimpleNamespace(type="sqlite", connection_string=None)
        with patch.dict("sys.modules", {"langgraph.store.sqlite": mock_module}):
            with patch("ideer.runtime.store.provider.resolve_sqlite_conn_str", return_value="/default.db"):
                with patch("ideer.runtime.store.provider.ensure_sqlite_parent_dir"):
                    with _sync_store_cm(config):
                        mock_module.SqliteStore.from_conn_string.assert_called_with("/default.db")

    def test_sqlite_import_error(self):
        from ideer.runtime.store.provider import _sync_store_cm

        config = SimpleNamespace(type="sqlite", connection_string="test.db")
        with patch.dict("sys.modules", {"langgraph.store.sqlite": None}):
            with pytest.raises(ImportError):
                with _sync_store_cm(config):
                    pass

    def test_postgres_type_success(self):
        from ideer.runtime.store.provider import _sync_store_cm

        mock_store = MagicMock()
        mock_store.setup = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_store)
        mock_cm.__exit__ = MagicMock(return_value=False)

        mock_module = MagicMock()
        mock_module.PostgresStore.from_conn_string.return_value = mock_cm

        config = SimpleNamespace(type="postgres", connection_string="postgresql://localhost/db")
        with patch.dict("sys.modules", {"langgraph.store.postgres": mock_module}):
            with _sync_store_cm(config) as store:
                assert store is mock_store

    def test_postgres_no_connection_string(self):
        from ideer.runtime.store.provider import _sync_store_cm

        config = SimpleNamespace(type="postgres", connection_string=None)
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"langgraph.store.postgres": mock_module}):
            with pytest.raises(ValueError, match="connection_string is required"):
                with _sync_store_cm(config):
                    pass

    def test_postgres_import_error(self):
        from ideer.runtime.store.provider import _sync_store_cm

        config = SimpleNamespace(type="postgres", connection_string="postgresql://localhost/db")
        with patch.dict("sys.modules", {"langgraph.store.postgres": None}):
            with pytest.raises(ImportError):
                with _sync_store_cm(config):
                    pass

    def test_unknown_type(self):
        from ideer.runtime.store.provider import _sync_store_cm

        config = SimpleNamespace(type="firestore", connection_string=None)
        with pytest.raises(ValueError, match="Unknown store backend type"):
            with _sync_store_cm(config):
                pass


# ---------------------------------------------------------------------------
# get_store singleton
# ---------------------------------------------------------------------------


class TestGetStore:
    def setup_method(self):
        from ideer.runtime.store.provider import reset_store

        reset_store()

    def teardown_method(self):
        from ideer.runtime.store.provider import reset_store

        reset_store()

    def test_no_config_returns_in_memory(self):
        from ideer.runtime.store.provider import get_store

        with patch("ideer.config.checkpointer_config.get_checkpointer_config", return_value=None):
            with patch("ideer.config.app_config._app_config", None):
                with patch("ideer.config.app_config.get_app_config", side_effect=FileNotFoundError):
                    store = get_store()
                    assert store is not None

    def test_caches_singleton(self):
        from ideer.runtime.store.provider import get_store

        with patch("ideer.config.checkpointer_config.get_checkpointer_config", return_value=None):
            with patch("ideer.config.app_config._app_config", None):
                with patch("ideer.config.app_config.get_app_config", side_effect=FileNotFoundError):
                    s1 = get_store()
                    s2 = get_store()
                    assert s1 is s2

    def test_with_checkpointer_config(self):
        from ideer.runtime.store.provider import get_store

        config = SimpleNamespace(type="memory", connection_string=None)
        with patch("ideer.config.checkpointer_config.get_checkpointer_config", return_value=config):
            store = get_store()
            assert store is not None


# ---------------------------------------------------------------------------
# reset_store
# ---------------------------------------------------------------------------


class TestResetStore:
    def test_resets_singleton(self):
        from ideer.runtime.store.provider import get_store, reset_store

        with patch("ideer.config.checkpointer_config.get_checkpointer_config", return_value=None):
            with patch("ideer.config.app_config._app_config", None):
                with patch("ideer.config.app_config.get_app_config", side_effect=FileNotFoundError):
                    get_store()
                    reset_store()
                    s2 = get_store()
                    assert s2 is not None

    def test_closes_context_manager(self):
        from ideer.runtime.store.provider import reset_store

        mock_ctx = MagicMock()
        with patch("ideer.runtime.store.provider._store_ctx", mock_ctx):
            with patch("ideer.runtime.store.provider._store", MagicMock()):
                reset_store()
                mock_ctx.__exit__.assert_called_once()

    def test_handles_cleanup_error(self):
        from ideer.runtime.store.provider import reset_store

        mock_ctx = MagicMock()
        mock_ctx.__exit__.side_effect = Exception("cleanup error")
        with patch("ideer.runtime.store.provider._store_ctx", mock_ctx):
            with patch("ideer.runtime.store.provider._store", MagicMock()):
                # Should not raise
                reset_store()


# ---------------------------------------------------------------------------
# store_context
# ---------------------------------------------------------------------------


class TestStoreContext:
    def test_no_checkpointer_returns_in_memory(self):
        from ideer.runtime.store.provider import store_context

        app_config = SimpleNamespace(checkpointer=None)
        with patch("ideer.runtime.store.provider.get_app_config", return_value=app_config):
            with store_context() as store:
                assert store is not None

    def test_with_checkpointer(self):
        from ideer.runtime.store.provider import store_context

        config = SimpleNamespace(type="memory", connection_string=None)
        app_config = SimpleNamespace(checkpointer=config)
        with patch("ideer.runtime.store.provider.get_app_config", return_value=app_config):
            with store_context() as store:
                assert store is not None
