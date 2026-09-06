"""Extra coverage tests for mcp/cache.py missed lines.

Targets: config-state resolution, stale check, lazy init loop variants.
"""

from unittest.mock import MagicMock, patch

# --- _resolve_config_path / _current_config_state ---


class TestCurrentConfigState:
    """Tests for the config path/signature resolution helpers."""

    def test_returns_state_for_existing_config(self):
        """Returns (path, signature) when the config file resolves."""
        from deerflow.mcp.cache import _current_config_state

        mock_path = MagicMock()
        mock_signature = (12345.0, 100, "a" * 64)

        with (
            patch("deerflow.config.extensions_config.ExtensionsConfig.resolve_config_path", return_value=mock_path),
            patch("deerflow.mcp.cache._get_config_signature", return_value=mock_signature),
        ):
            result = _current_config_state()

        assert result == (mock_path, mock_signature)

    def test_returns_none_state_when_path_is_none(self):
        """Returns (None, None) when resolve_config_path returns None."""
        from deerflow.mcp.cache import _current_config_state

        with patch("deerflow.config.extensions_config.ExtensionsConfig.resolve_config_path", return_value=None):
            result = _current_config_state()

        assert result == (None, None)

    def test_resolve_config_path_swallows_missing_file_error(self):
        """A missing explicit config path is treated as unconfigured for staleness checks."""
        from deerflow.mcp.cache import _resolve_config_path

        with patch("deerflow.config.extensions_config.ExtensionsConfig.resolve_config_path", side_effect=FileNotFoundError("gone")):
            result = _resolve_config_path()

        assert result is None


# --- get_cached_mcp_tools stale check ---


class TestGetCachedMcpToolsStaleCheck:
    """Tests for stale cache detection in get_cached_mcp_tools."""

    def setup_method(self):
        import deerflow.mcp.cache as cache_mod

        self._cache_mod = cache_mod
        self._orig_initialized = cache_mod._cache_initialized
        self._orig_cache = cache_mod._mcp_tools_cache
        self._orig_config_path = cache_mod._config_path
        self._orig_config_signature = cache_mod._config_signature

    def teardown_method(self):
        self._cache_mod._cache_initialized = self._orig_initialized
        self._cache_mod._mcp_tools_cache = self._orig_cache
        self._cache_mod._config_path = self._orig_config_path
        self._cache_mod._config_signature = self._orig_config_signature

    def test_returns_cached_when_not_stale(self):
        """Returns cached tools when cache is not stale."""
        mock_tools = [MagicMock()]
        self._cache_mod._cache_initialized = True
        self._cache_mod._mcp_tools_cache = mock_tools
        self._cache_mod._config_path = "/cfg/extensions.json"
        self._cache_mod._config_signature = (100.0, 10, "a" * 64)

        with patch("deerflow.mcp.cache._is_cache_stale", return_value=False):
            result = self._cache_mod.get_cached_mcp_tools()

        assert result == mock_tools


# --- get_cached_mcp_tools with running loop ---


class TestGetCachedMcpToolsRunningLoop:
    """Tests for lazy init when event loop is running."""

    def setup_method(self):
        import deerflow.mcp.cache as cache_mod

        self._cache_mod = cache_mod
        self._orig_initialized = cache_mod._cache_initialized
        self._orig_cache = cache_mod._mcp_tools_cache
        self._orig_config_path = cache_mod._config_path
        self._orig_config_signature = cache_mod._config_signature

    def teardown_method(self):
        self._cache_mod._cache_initialized = self._orig_initialized
        self._cache_mod._mcp_tools_cache = self._orig_cache
        self._cache_mod._config_path = self._orig_config_path
        self._cache_mod._config_signature = self._orig_config_signature

    def test_lazy_init_with_running_loop(self):
        """Uses ThreadPoolExecutor when loop is running."""
        self._cache_mod._cache_initialized = False
        self._cache_mod._mcp_tools_cache = None

        mock_tools = [MagicMock()]

        # Simulate running loop scenario
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True

        with (
            patch("deerflow.mcp.cache._is_cache_stale", return_value=False),
            patch("asyncio.get_event_loop", return_value=mock_loop),
            patch("concurrent.futures.ThreadPoolExecutor") as MockExecutor,
        ):
            mock_future = MagicMock()
            mock_future.result.return_value = None
            mock_executor_instance = MagicMock()
            mock_executor_instance.__enter__ = MagicMock(return_value=mock_executor_instance)
            mock_executor_instance.__exit__ = MagicMock(return_value=False)

            def fake_submit(fn, coro, *args, **kwargs):
                coro.close()  # the mocked executor never runs the coroutine
                return mock_future

            mock_executor_instance.submit.side_effect = fake_submit
            MockExecutor.return_value = mock_executor_instance

            # Set up the cache to be initialized after the executor call
            def set_initialized(*args, **kwargs):
                self._cache_mod._cache_initialized = True
                self._cache_mod._mcp_tools_cache = mock_tools

            mock_future.result.side_effect = set_initialized

            result = self._cache_mod.get_cached_mcp_tools()

        assert result == mock_tools

    def test_lazy_init_with_no_running_loop(self):
        """Uses loop.run_until_complete when no loop running."""
        self._cache_mod._cache_initialized = False
        self._cache_mod._mcp_tools_cache = None

        mock_tools = [MagicMock()]
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False

        def set_initialized():
            self._cache_mod._cache_initialized = True
            self._cache_mod._mcp_tools_cache = mock_tools

        def run_until_complete(coro):
            coro.close()
            set_initialized()

        mock_loop.run_until_complete.side_effect = run_until_complete

        with (
            patch("deerflow.mcp.cache._is_cache_stale", return_value=False),
            patch("asyncio.get_event_loop", return_value=mock_loop),
        ):
            result = self._cache_mod.get_cached_mcp_tools()

        assert result == mock_tools


# --- get_cached_mcp_tools RuntimeError handling ---


class TestGetCachedMcpToolsRuntimeError:
    """Tests for RuntimeError handling in get_cached_mcp_tools."""

    def setup_method(self):
        import deerflow.mcp.cache as cache_mod

        self._cache_mod = cache_mod
        self._orig_initialized = cache_mod._cache_initialized
        self._orig_cache = cache_mod._mcp_tools_cache
        self._orig_config_path = cache_mod._config_path
        self._orig_config_signature = cache_mod._config_signature

    def teardown_method(self):
        self._cache_mod._cache_initialized = self._orig_initialized
        self._cache_mod._mcp_tools_cache = self._orig_cache
        self._cache_mod._config_path = self._orig_config_path
        self._cache_mod._config_signature = self._orig_config_signature

    def test_handles_runtime_error_no_event_loop(self):
        """Handles RuntimeError when no event loop exists."""
        self._cache_mod._cache_initialized = False
        self._cache_mod._mcp_tools_cache = None

        mock_tools = [MagicMock()]

        def raise_runtime_error():
            raise RuntimeError("no event loop")

        def fake_run(coro):
            coro.close()
            self._cache_mod._cache_initialized = True
            self._cache_mod._mcp_tools_cache = mock_tools

        with (
            patch("deerflow.mcp.cache._is_cache_stale", return_value=False),
            patch("asyncio.get_event_loop", side_effect=raise_runtime_error),
            patch("asyncio.run", side_effect=fake_run),
        ):
            # asyncio.run should be called and succeed
            result = self._cache_mod.get_cached_mcp_tools()

        assert result == mock_tools

    def test_handles_general_exception_in_lazy_init(self):
        """Returns empty list on general exception."""
        self._cache_mod._cache_initialized = False
        self._cache_mod._mcp_tools_cache = None

        def failing_run(coro):
            coro.close()
            raise Exception("init failed")

        with (
            patch("deerflow.mcp.cache._is_cache_stale", return_value=False),
            patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")),
            patch("asyncio.run", side_effect=failing_run),
        ):
            result = self._cache_mod.get_cached_mcp_tools()

        assert result == []

    def test_inner_lock_returns_cache_when_set_by_another_thread(self):
        """Returns cache when another thread initializes it while we wait for lock."""
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
            patch("deerflow.mcp.cache._is_cache_stale", return_value=False),
            patch.object(cache_mod, "_init_lock", RaceLock()),
        ):
            result = cache_mod.get_cached_mcp_tools()

        assert result == mock_tools
