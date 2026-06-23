"""Extra coverage tests for mcp/cache.py missed lines.

Targets: 26-31, 111, 119-123, 134-136
"""

from unittest.mock import MagicMock, patch

# --- Lines 26-31: _get_config_mtime ---


class TestGetConfigMtime:
    """Tests for _get_config_mtime function."""

    def test_returns_mtime_for_existing_config(self):
        """Lines 26-31: Returns mtime when config file exists."""
        from ideer.mcp.cache import _get_config_mtime

        mock_path = MagicMock()
        mock_path.exists.return_value = True

        with (
            patch("ideer.config.extensions_config.ExtensionsConfig.resolve_config_path", return_value=mock_path),
            patch("os.path.getmtime", return_value=12345.0),
        ):
            result = _get_config_mtime()

        assert result == 12345.0

    def test_returns_none_when_path_is_none(self):
        """Returns None when resolve_config_path returns None."""
        from ideer.mcp.cache import _get_config_mtime

        with patch("ideer.config.extensions_config.ExtensionsConfig.resolve_config_path", return_value=None):
            result = _get_config_mtime()

        assert result is None

    def test_returns_none_when_file_not_exists(self):
        """Returns None when config file doesn't exist."""
        from ideer.mcp.cache import _get_config_mtime

        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with patch("ideer.config.extensions_config.ExtensionsConfig.resolve_config_path", return_value=mock_path):
            result = _get_config_mtime()

        assert result is None


# --- Line 111: get_cached_mcp_tools stale check ---


class TestGetCachedMcpToolsStaleCheck:
    """Tests for stale cache detection in get_cached_mcp_tools."""

    def setup_method(self):
        import ideer.mcp.cache as cache_mod

        self._cache_mod = cache_mod
        self._orig_initialized = cache_mod._cache_initialized
        self._orig_cache = cache_mod._mcp_tools_cache
        self._orig_mtime = cache_mod._config_mtime

    def teardown_method(self):
        self._cache_mod._cache_initialized = self._orig_initialized
        self._cache_mod._mcp_tools_cache = self._orig_cache
        self._cache_mod._config_mtime = self._orig_mtime

    def test_returns_cached_when_not_stale(self):
        """Line 111: Returns cached tools when cache is not stale."""
        mock_tools = [MagicMock()]
        self._cache_mod._cache_initialized = True
        self._cache_mod._mcp_tools_cache = mock_tools
        self._cache_mod._config_mtime = 100.0

        with patch("ideer.mcp.cache._is_cache_stale", return_value=False):
            result = self._cache_mod.get_cached_mcp_tools()

        assert result == mock_tools


# --- Lines 119-123: get_cached_mcp_tools with running loop ---


class TestGetCachedMcpToolsRunningLoop:
    """Tests for lazy init when event loop is running."""

    def setup_method(self):
        import ideer.mcp.cache as cache_mod

        self._cache_mod = cache_mod
        self._orig_initialized = cache_mod._cache_initialized
        self._orig_cache = cache_mod._mcp_tools_cache
        self._orig_mtime = cache_mod._config_mtime

    def teardown_method(self):
        self._cache_mod._cache_initialized = self._orig_initialized
        self._cache_mod._mcp_tools_cache = self._orig_cache
        self._cache_mod._config_mtime = self._orig_mtime

    def test_lazy_init_with_running_loop(self):
        """Lines 119-123: Uses ThreadPoolExecutor when loop is running."""
        self._cache_mod._cache_initialized = False
        self._cache_mod._mcp_tools_cache = None

        mock_tools = [MagicMock()]

        # Simulate running loop scenario
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True

        with (
            patch("ideer.mcp.cache._is_cache_stale", return_value=False),
            patch("asyncio.get_event_loop", return_value=mock_loop),
            patch("concurrent.futures.ThreadPoolExecutor") as MockExecutor,
        ):
            mock_future = MagicMock()
            mock_future.result.return_value = None
            mock_executor_instance = MagicMock()
            mock_executor_instance.submit.return_value = mock_future
            mock_executor_instance.__enter__ = MagicMock(return_value=mock_executor_instance)
            mock_executor_instance.__exit__ = MagicMock(return_value=False)
            MockExecutor.return_value = mock_executor_instance

            # Set up the cache to be initialized after the executor call
            def set_initialized(*args, **kwargs):
                self._cache_mod._cache_initialized = True
                self._cache_mod._mcp_tools_cache = mock_tools

            mock_future.result.side_effect = set_initialized

            self._cache_mod.get_cached_mcp_tools()

    def test_lazy_init_with_no_running_loop(self):
        """Lines 125-126: Uses loop.run_until_complete when no loop running."""
        self._cache_mod._cache_initialized = False
        self._cache_mod._mcp_tools_cache = None

        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False

        def set_initialized():
            self._cache_mod._cache_initialized = True
            self._cache_mod._mcp_tools_cache = [MagicMock()]

        mock_loop.run_until_complete.side_effect = lambda coro: set_initialized()

        with (
            patch("ideer.mcp.cache._is_cache_stale", return_value=False),
            patch("asyncio.get_event_loop", return_value=mock_loop),
        ):
            self._cache_mod.get_cached_mcp_tools()


# --- Lines 134-136: get_cached_mcp_tools RuntimeError ---


class TestGetCachedMcpToolsRuntimeError:
    """Tests for RuntimeError handling in get_cached_mcp_tools."""

    def setup_method(self):
        import ideer.mcp.cache as cache_mod

        self._cache_mod = cache_mod
        self._orig_initialized = cache_mod._cache_initialized
        self._orig_cache = cache_mod._mcp_tools_cache
        self._orig_mtime = cache_mod._config_mtime

    def teardown_method(self):
        self._cache_mod._cache_initialized = self._orig_initialized
        self._cache_mod._mcp_tools_cache = self._orig_cache
        self._cache_mod._config_mtime = self._orig_mtime

    def test_handles_runtime_error_no_event_loop(self):
        """Lines 128-136: Handles RuntimeError when no event loop exists."""
        self._cache_mod._cache_initialized = False
        self._cache_mod._mcp_tools_cache = None

        mock_tools = [MagicMock()]

        def raise_runtime_error():
            raise RuntimeError("no event loop")

        with (
            patch("ideer.mcp.cache._is_cache_stale", return_value=False),
            patch("asyncio.get_event_loop", side_effect=raise_runtime_error),
            patch("asyncio.run") as mock_run,
        ):
            # asyncio.run should be called and succeed
            def set_state():
                self._cache_mod._cache_initialized = True
                self._cache_mod._mcp_tools_cache = mock_tools

            mock_run.side_effect = lambda coro: set_state()
            self._cache_mod.get_cached_mcp_tools()

    def test_handles_general_exception_in_lazy_init(self):
        """Lines 134-136: Returns empty list on general exception."""
        self._cache_mod._cache_initialized = False
        self._cache_mod._mcp_tools_cache = None

        with (
            patch("ideer.mcp.cache._is_cache_stale", return_value=False),
            patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")),
            patch("asyncio.run", side_effect=Exception("init failed")),
        ):
            result = self._cache_mod.get_cached_mcp_tools()

        assert result == []

    def test_inner_lock_returns_cache_when_set_by_another_thread(self):
        """Line 111: Returns cache when another thread initializes it while we wait for lock."""
        cache_mod = self._cache_mod

        cache_mod._cache_initialized = False
        cache_mod._mcp_tools_cache = None

        mock_tools = [MagicMock()]

        class RaceLock:
            """Simulates another thread winning the race to initialize."""

            def __enter__(self_):
                # Another thread set the cache
                cache_mod._cache_initialized = True
                cache_mod._mcp_tools_cache = mock_tools
                return self_

            def __exit__(self_, *args):
                pass

        with (
            patch("ideer.mcp.cache._is_cache_stale", return_value=False),
            patch.object(cache_mod, "_thread_init_lock", RaceLock()),
        ):
            result = cache_mod.get_cached_mcp_tools()

        assert result == mock_tools
