"""Tests for MCP tools cache (packages/harness/deerflow/mcp/cache.py).

Covers:
- _is_cache_stale() — config path + content-signature based staleness detection
- reset_mcp_tools_cache() — cache reset and session pool cleanup
- initialize_mcp_tools() — async initialization with lock
- get_cached_mcp_tools() — lazy initialization with thread lock
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# A config content signature is (mtime, size, sha256); see
# deerflow.config.file_signature.ConfigSignature.
_SIG_A = (100.0, 10, "a" * 64)
_SIG_B = (200.0, 12, "b" * 64)

# ---------------------------------------------------------------------------
# _is_cache_stale
# ---------------------------------------------------------------------------


class TestIsCacheStale:
    """Tests for config path/signature-based staleness detection."""

    def setup_method(self):
        """Reset module-level globals before each test."""
        import deerflow.mcp.cache as cache_mod

        self._cache_mod = cache_mod
        # Save original state
        self._orig_cache_initialized = cache_mod._cache_initialized
        self._orig_config_path = cache_mod._config_path
        self._orig_config_signature = cache_mod._config_signature

    def teardown_method(self):
        """Restore original state."""
        self._cache_mod._cache_initialized = self._orig_cache_initialized
        self._cache_mod._config_path = self._orig_config_path
        self._cache_mod._config_signature = self._orig_config_signature

    def test_not_stale_when_not_initialized(self):
        """Cache is not stale when not yet initialized."""
        self._cache_mod._cache_initialized = False
        assert self._cache_mod._is_cache_stale() is False

    def test_not_stale_when_signature_unchanged(self):
        """Cache is not stale when config path and signature are unchanged."""
        self._cache_mod._cache_initialized = True
        self._cache_mod._config_path = "/cfg/extensions.json"
        self._cache_mod._config_signature = _SIG_A

        with patch("deerflow.mcp.cache._current_config_state", return_value=("/cfg/extensions.json", _SIG_A)):
            assert self._cache_mod._is_cache_stale() is False

    def test_stale_when_signature_changes(self):
        """Cache is stale when the config content signature differs."""
        self._cache_mod._cache_initialized = True
        self._cache_mod._config_path = "/cfg/extensions.json"
        self._cache_mod._config_signature = _SIG_A

        with patch("deerflow.mcp.cache._current_config_state", return_value=("/cfg/extensions.json", _SIG_B)):
            assert self._cache_mod._is_cache_stale() is True

    def test_stale_when_mtime_moves_backward(self):
        """Cache is stale even when only the mtime moves backward.

        Unlike the legacy strict ``mtime >`` comparison, a content-signature
        difference (e.g. ``git checkout`` restoring an older mtime with
        different content) invalidates the cache.
        """
        self._cache_mod._cache_initialized = True
        self._cache_mod._config_path = "/cfg/extensions.json"
        self._cache_mod._config_signature = _SIG_B

        older = (100.0, _SIG_B[1], _SIG_B[2])
        with patch("deerflow.mcp.cache._current_config_state", return_value=("/cfg/extensions.json", older)):
            assert self._cache_mod._is_cache_stale() is True

    def test_stale_when_config_path_changes(self):
        """Cache is stale when a different config file is resolved, even with an equal signature."""
        self._cache_mod._cache_initialized = True
        self._cache_mod._config_path = "/cfg/extensions.json"
        self._cache_mod._config_signature = _SIG_A

        with patch("deerflow.mcp.cache._current_config_state", return_value=("/cfg/other.json", _SIG_A)):
            assert self._cache_mod._is_cache_stale() is True

    def test_not_stale_when_no_previous_signature(self):
        """Cache is not stale when no signature could be recorded at init time."""
        self._cache_mod._cache_initialized = True
        self._cache_mod._config_signature = None

        with patch("deerflow.mcp.cache._current_config_state", return_value=("/cfg/extensions.json", _SIG_A)):
            assert self._cache_mod._is_cache_stale() is False

    def test_not_stale_when_current_signature_none(self):
        """Cache is not stale when the current config can't be stat-ed/read."""
        self._cache_mod._cache_initialized = True
        self._cache_mod._config_path = "/cfg/extensions.json"
        self._cache_mod._config_signature = _SIG_A

        with patch("deerflow.mcp.cache._current_config_state", return_value=("/cfg/extensions.json", None)):
            assert self._cache_mod._is_cache_stale() is False


# ---------------------------------------------------------------------------
# reset_mcp_tools_cache
# ---------------------------------------------------------------------------


class TestResetMcpToolsCache:
    """Tests for cache reset and session pool cleanup."""

    def setup_method(self):
        """Reset module-level globals before each test."""
        import deerflow.mcp.cache as cache_mod

        self._cache_mod = cache_mod
        self._orig_cache_initialized = cache_mod._cache_initialized
        self._orig_config_path = cache_mod._config_path
        self._orig_config_signature = cache_mod._config_signature
        self._orig_mcp_tools_cache = cache_mod._mcp_tools_cache

    def teardown_method(self):
        """Restore original state."""
        self._cache_mod._cache_initialized = self._orig_cache_initialized
        self._cache_mod._config_path = self._orig_config_path
        self._cache_mod._config_signature = self._orig_config_signature
        self._cache_mod._mcp_tools_cache = self._orig_mcp_tools_cache

    @patch("deerflow.mcp.session_pool.reset_session_pool")
    def test_reset_clears_cache_state(self, mock_reset_pool):
        """Reset clears all cache state and closes the retired pool."""
        retired_pool = MagicMock()
        mock_reset_pool.return_value = retired_pool

        self._cache_mod._cache_initialized = True
        self._cache_mod._config_path = "/cfg/extensions.json"
        self._cache_mod._config_signature = _SIG_A
        self._cache_mod._mcp_tools_cache = [MagicMock()]

        self._cache_mod.reset_mcp_tools_cache()

        assert self._cache_mod._cache_initialized is False
        assert self._cache_mod._config_path is None
        assert self._cache_mod._config_signature is None
        assert self._cache_mod._mcp_tools_cache is None
        mock_reset_pool.assert_called_once()
        retired_pool.close_all_sync.assert_called_once()

    @patch("deerflow.mcp.session_pool.reset_session_pool")
    def test_reset_handles_pool_close_error(self, mock_reset_pool):
        """Reset handles errors during pool close gracefully."""
        retired_pool = MagicMock()
        retired_pool.close_all_sync.side_effect = RuntimeError("close failed")
        mock_reset_pool.return_value = retired_pool

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
        import deerflow.mcp.cache as cache_mod

        self._cache_mod = cache_mod
        self._orig_cache_initialized = cache_mod._cache_initialized
        self._orig_config_path = cache_mod._config_path
        self._orig_config_signature = cache_mod._config_signature
        self._orig_mcp_tools_cache = cache_mod._mcp_tools_cache

    def teardown_method(self):
        """Restore original state."""
        self._cache_mod._cache_initialized = self._orig_cache_initialized
        self._cache_mod._config_path = self._orig_config_path
        self._cache_mod._config_signature = self._orig_config_signature
        self._cache_mod._mcp_tools_cache = self._orig_mcp_tools_cache

    @pytest.mark.asyncio
    async def test_initialize_loads_tools(self):
        """Initialize loads tools from get_mcp_tools."""
        self._cache_mod._cache_initialized = False
        self._cache_mod._mcp_tools_cache = None

        mock_tools = [MagicMock(), MagicMock()]
        config_state = ("/cfg/extensions.json", _SIG_A)

        with (
            patch("deerflow.mcp.tools.get_mcp_tools", new_callable=AsyncMock, return_value=mock_tools),
            patch("deerflow.mcp.cache._current_config_state", return_value=config_state),
        ):
            result = await self._cache_mod.initialize_mcp_tools()

        assert result == mock_tools
        assert self._cache_mod._cache_initialized is True
        assert self._cache_mod._config_path == "/cfg/extensions.json"
        assert self._cache_mod._config_signature == _SIG_A

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """Second call returns cached tools without reloading."""
        self._cache_mod._cache_initialized = True
        self._cache_mod._mcp_tools_cache = [MagicMock()]

        result = await self._cache_mod.initialize_mcp_tools()

        assert result == self._cache_mod._mcp_tools_cache

    @pytest.mark.asyncio
    async def test_initialize_records_config_state(self):
        """Initialize records the resolved config path and content signature."""
        self._cache_mod._cache_initialized = False
        self._cache_mod._mcp_tools_cache = None
        config_state = ("/cfg/extensions.json", _SIG_B)

        with (
            patch("deerflow.mcp.tools.get_mcp_tools", new_callable=AsyncMock, return_value=[]),
            patch("deerflow.mcp.cache._current_config_state", return_value=config_state),
        ):
            await self._cache_mod.initialize_mcp_tools()

        assert self._cache_mod._config_path == "/cfg/extensions.json"
        assert self._cache_mod._config_signature == _SIG_B


# ---------------------------------------------------------------------------
# get_cached_mcp_tools
# ---------------------------------------------------------------------------


class TestGetCachedMcpTools:
    """Tests for lazy initialization with thread lock."""

    def setup_method(self):
        """Reset module-level globals before each test."""
        import deerflow.mcp.cache as cache_mod

        self._cache_mod = cache_mod
        self._orig_cache_initialized = cache_mod._cache_initialized
        self._orig_config_path = cache_mod._config_path
        self._orig_config_signature = cache_mod._config_signature
        self._orig_mcp_tools_cache = cache_mod._mcp_tools_cache

    def teardown_method(self):
        """Restore original state."""
        self._cache_mod._cache_initialized = self._orig_cache_initialized
        self._cache_mod._config_path = self._orig_config_path
        self._cache_mod._config_signature = self._orig_config_signature
        self._cache_mod._mcp_tools_cache = self._orig_mcp_tools_cache

    def test_returns_cached_tools_when_initialized(self):
        """Returns cached tools when already initialized and not stale."""
        mock_tools = [MagicMock()]
        self._cache_mod._cache_initialized = True
        self._cache_mod._mcp_tools_cache = mock_tools
        self._cache_mod._config_path = "/cfg/extensions.json"
        self._cache_mod._config_signature = _SIG_A

        with patch("deerflow.mcp.cache._is_cache_stale", return_value=False):
            result = self._cache_mod.get_cached_mcp_tools()

        assert result == mock_tools

    def test_resets_when_stale(self):
        """Resets cache when stale, then re-initializes."""
        self._cache_mod._cache_initialized = True
        self._cache_mod._mcp_tools_cache = [MagicMock()]
        self._cache_mod._config_path = "/cfg/extensions.json"
        self._cache_mod._config_signature = _SIG_A

        new_tools = [MagicMock(), MagicMock()]
        config_state = ("/cfg/extensions.json", _SIG_B)

        # The real invalidation retires the session pool and clears the state,
        # which triggers lazy init. We patch the locked invalidation helper to
        # do exactly that and hand back a (mock) retired pool.
        def _invalidate_and_reset_state():
            self._cache_mod._mcp_tools_cache = None
            self._cache_mod._cache_initialized = False
            self._cache_mod._config_path = None
            self._cache_mod._config_signature = None
            return MagicMock()

        with (
            patch("deerflow.mcp.cache._is_cache_stale", return_value=True),
            patch("deerflow.mcp.cache._reset_mcp_tools_cache_state_and_retire_pool_locked", side_effect=_invalidate_and_reset_state),
            patch("deerflow.mcp.tools.get_mcp_tools", new_callable=AsyncMock, return_value=new_tools),
            patch("deerflow.mcp.cache._current_config_state", return_value=config_state),
        ):
            result = self._cache_mod.get_cached_mcp_tools()

        assert result == new_tools

    def test_returns_empty_list_on_init_failure(self):
        """Returns empty list when initialization fails."""
        self._cache_mod._cache_initialized = False
        self._cache_mod._mcp_tools_cache = None

        with (
            patch("deerflow.mcp.cache._is_cache_stale", return_value=False),
            patch("deerflow.mcp.cache.initialize_mcp_tools", side_effect=RuntimeError("init failed")),
        ):
            result = self._cache_mod.get_cached_mcp_tools()

        assert result == []
