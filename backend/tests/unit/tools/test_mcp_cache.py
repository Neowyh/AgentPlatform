"""Tests for MCP tools cache (backend/packages/harness/ideer/mcp/cache.py).

Covers:
- _is_cache_stale() — config mtime-based staleness detection
- reset_mcp_tools_cache() — cache reset and session pool cleanup
- initialize_mcp_tools() — async initialization with lock
- get_cached_mcp_tools() — lazy initialization with thread lock
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# _is_cache_stale
# ---------------------------------------------------------------------------


class TestIsCacheStale:
    """Tests for config mtime-based staleness detection."""

    def setup_method(self):
        """Reset module-level globals before each test."""
        import ideer.mcp.cache as cache_mod

        self._cache_mod = cache_mod
        # Save original state
        self._orig_cache_initialized = cache_mod._cache_initialized
        self._orig_config_mtime = cache_mod._config_mtime

    def teardown_method(self):
        """Restore original state."""
        self._cache_mod._cache_initialized = self._orig_cache_initialized
        self._cache_mod._config_mtime = self._orig_config_mtime

    def test_not_stale_when_not_initialized(self):
        """Cache is not stale when not yet initialized."""
        self._cache_mod._cache_initialized = False
        assert self._cache_mod._is_cache_stale() is False

    def test_not_stale_when_mtime_unchanged(self):
        """Cache is not stale when config mtime hasn't changed."""
        self._cache_mod._cache_initialized = True
        self._cache_mod._config_mtime = 100.0

        with patch("ideer.mcp.cache._get_config_mtime", return_value=100.0):
            assert self._cache_mod._is_cache_stale() is False

    def test_stale_when_mtime_newer(self):
        """Cache is stale when config file has been modified."""
        self._cache_mod._cache_initialized = True
        self._cache_mod._config_mtime = 100.0

        with patch("ideer.mcp.cache._get_config_mtime", return_value=200.0):
            assert self._cache_mod._is_cache_stale() is True

    def test_not_stale_when_mtime_older(self):
        """Cache is not stale when config file mtime is older (clock skew)."""
        self._cache_mod._cache_initialized = True
        self._cache_mod._config_mtime = 200.0

        with patch("ideer.mcp.cache._get_config_mtime", return_value=100.0):
            assert self._cache_mod._is_cache_stale() is False

    def test_not_stale_when_no_previous_mtime(self):
        """Cache is not stale when we couldn't get mtime before."""
        self._cache_mod._cache_initialized = True
        self._cache_mod._config_mtime = None

        with patch("ideer.mcp.cache._get_config_mtime", return_value=100.0):
            assert self._cache_mod._is_cache_stale() is False

    def test_not_stale_when_current_mtime_none(self):
        """Cache is not stale when current mtime can't be determined."""
        self._cache_mod._cache_initialized = True
        self._cache_mod._config_mtime = 100.0

        with patch("ideer.mcp.cache._get_config_mtime", return_value=None):
            assert self._cache_mod._is_cache_stale() is False


# ---------------------------------------------------------------------------
# reset_mcp_tools_cache
# ---------------------------------------------------------------------------


class TestResetMcpToolsCache:
    """Tests for cache reset and session pool cleanup."""

    def setup_method(self):
        """Reset module-level globals before each test."""
        import ideer.mcp.cache as cache_mod

        self._cache_mod = cache_mod
        self._orig_cache_initialized = cache_mod._cache_initialized
        self._orig_config_mtime = cache_mod._config_mtime
        self._orig_mcp_tools_cache = cache_mod._mcp_tools_cache

    def teardown_method(self):
        """Restore original state."""
        self._cache_mod._cache_initialized = self._orig_cache_initialized
        self._cache_mod._config_mtime = self._orig_config_mtime
        self._cache_mod._mcp_tools_cache = self._orig_mcp_tools_cache

    @patch("ideer.mcp.session_pool.reset_session_pool")
    @patch("ideer.mcp.session_pool.get_session_pool")
    def test_reset_clears_cache_state(self, mock_get_pool, mock_reset_pool):
        """Reset clears all cache state."""
        mock_pool = MagicMock()
        mock_get_pool.return_value = mock_pool

        self._cache_mod._cache_initialized = True
        self._cache_mod._config_mtime = 100.0
        self._cache_mod._mcp_tools_cache = [MagicMock()]

        self._cache_mod.reset_mcp_tools_cache()

        assert self._cache_mod._cache_initialized is False
        assert self._cache_mod._config_mtime is None
        assert self._cache_mod._mcp_tools_cache is None
        mock_pool.close_all_sync.assert_called_once()
        mock_reset_pool.assert_called_once()

    @patch("ideer.mcp.session_pool.reset_session_pool")
    @patch("ideer.mcp.session_pool.get_session_pool")
    def test_reset_handles_pool_close_error(self, mock_get_pool, mock_reset_pool):
        """Reset handles errors during pool close gracefully."""
        mock_pool = MagicMock()
        mock_pool.close_all_sync.side_effect = RuntimeError("close failed")
        mock_get_pool.return_value = mock_pool

        # Should not raise
        self._cache_mod.reset_mcp_tools_cache()

        # Cache state should still be cleared
        assert self._cache_mod._cache_initialized is False
        mock_reset_pool.assert_called_once()


# ---------------------------------------------------------------------------
# initialize_mcp_tools
# ---------------------------------------------------------------------------


class TestInitializeMcpTools:
    """Tests for async initialization with lock."""

    def setup_method(self):
        """Reset module-level globals before each test."""
        import ideer.mcp.cache as cache_mod

        self._cache_mod = cache_mod
        self._orig_cache_initialized = cache_mod._cache_initialized
        self._orig_config_mtime = cache_mod._config_mtime
        self._orig_mcp_tools_cache = cache_mod._mcp_tools_cache

    def teardown_method(self):
        """Restore original state."""
        self._cache_mod._cache_initialized = self._orig_cache_initialized
        self._cache_mod._config_mtime = self._orig_config_mtime
        self._cache_mod._mcp_tools_cache = self._orig_mcp_tools_cache

    @pytest.mark.asyncio
    async def test_initialize_loads_tools(self):
        """Initialize loads tools from get_mcp_tools."""
        self._cache_mod._cache_initialized = False
        self._cache_mod._mcp_tools_cache = None

        mock_tools = [MagicMock(), MagicMock()]

        with (
            patch("ideer.mcp.tools.get_mcp_tools", new_callable=AsyncMock, return_value=mock_tools),
            patch("ideer.mcp.cache._get_config_mtime", return_value=100.0),
        ):
            result = await self._cache_mod.initialize_mcp_tools()

        assert result == mock_tools
        assert self._cache_mod._cache_initialized is True
        assert self._cache_mod._config_mtime == 100.0

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """Second call returns cached tools without reloading."""
        self._cache_mod._cache_initialized = True
        self._cache_mod._mcp_tools_cache = [MagicMock()]

        result = await self._cache_mod.initialize_mcp_tools()

        assert result == self._cache_mod._mcp_tools_cache

    @pytest.mark.asyncio
    async def test_initialize_records_config_mtime(self):
        """Initialize records config file mtime."""
        self._cache_mod._cache_initialized = False
        self._cache_mod._mcp_tools_cache = None

        with (
            patch("ideer.mcp.tools.get_mcp_tools", new_callable=AsyncMock, return_value=[]),
            patch("ideer.mcp.cache._get_config_mtime", return_value=42.0),
        ):
            await self._cache_mod.initialize_mcp_tools()

        assert self._cache_mod._config_mtime == 42.0


# ---------------------------------------------------------------------------
# get_cached_mcp_tools
# ---------------------------------------------------------------------------


class TestGetCachedMcpTools:
    """Tests for lazy initialization with thread lock."""

    def setup_method(self):
        """Reset module-level globals before each test."""
        import ideer.mcp.cache as cache_mod

        self._cache_mod = cache_mod
        self._orig_cache_initialized = cache_mod._cache_initialized
        self._orig_config_mtime = cache_mod._config_mtime
        self._orig_mcp_tools_cache = cache_mod._mcp_tools_cache

    def teardown_method(self):
        """Restore original state."""
        self._cache_mod._cache_initialized = self._orig_cache_initialized
        self._cache_mod._config_mtime = self._orig_config_mtime
        self._cache_mod._mcp_tools_cache = self._orig_mcp_tools_cache

    def test_returns_cached_tools_when_initialized(self):
        """Returns cached tools when already initialized and not stale."""
        mock_tools = [MagicMock()]
        self._cache_mod._cache_initialized = True
        self._cache_mod._mcp_tools_cache = mock_tools
        self._cache_mod._config_mtime = 100.0

        with patch("ideer.mcp.cache._is_cache_stale", return_value=False):
            result = self._cache_mod.get_cached_mcp_tools()

        assert result == mock_tools

    def test_resets_when_stale(self):
        """Resets cache when stale, then re-initializes."""
        self._cache_mod._cache_initialized = True
        self._cache_mod._mcp_tools_cache = [MagicMock()]
        self._cache_mod._config_mtime = 100.0

        new_tools = [MagicMock(), MagicMock()]

        # The real reset_mcp_tools_cache sets _cache_initialized=False,
        # which triggers lazy init. We patch _is_cache_stale to return True
        # and patch the lazy init path to set our new tools.

        def _reset_and_set_state():
            self._cache_mod._mcp_tools_cache = None
            self._cache_mod._cache_initialized = False
            self._cache_mod._config_mtime = None

        with (
            patch("ideer.mcp.cache._is_cache_stale", return_value=True),
            patch("ideer.mcp.cache.reset_mcp_tools_cache", side_effect=_reset_and_set_state),
            patch("ideer.mcp.tools.get_mcp_tools", new_callable=AsyncMock, return_value=new_tools),
            patch("ideer.mcp.cache._get_config_mtime", return_value=200.0),
        ):
            result = self._cache_mod.get_cached_mcp_tools()

        assert result == new_tools

    def test_returns_empty_list_on_init_failure(self):
        """Returns empty list when initialization fails."""
        self._cache_mod._cache_initialized = False
        self._cache_mod._mcp_tools_cache = None

        with (
            patch("ideer.mcp.cache._is_cache_stale", return_value=False),
            patch("ideer.mcp.cache.initialize_mcp_tools", side_effect=RuntimeError("init failed")),
        ):
            result = self._cache_mod.get_cached_mcp_tools()

        assert result == []
