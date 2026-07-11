"""Targeted coverage tests for specific uncovered lines.

Covers uncovered lines in:
- aio_sandbox.py: base_url property, home_dir lazy fetch, exception paths,
  update_file, grep with glob, truncation, data-None paths
- aio_sandbox_provider.py: acquire_thread_lock_async failure, idle checker
  error handling, signal handler branches, async discover/create
- backend.py: wait_for_sandbox_ready and async variant
- image_search/tools.py: image_search_tool wrapper
- mcp/oauth.py: refresh_token grant, unsupported grant, missing token,
  expires_in fallback, interceptor passthrough
- mcp/cache.py: get_config_mtime, running-loop lazy init path
- models/patched_minimax.py: empty choices v1, delta-None, finish_reason
  metadata fields, reasoning in chunk
- models/patched_openai.py: fallback positional matching, no-match continue
- community/firecrawl/tools.py: exception paths, no-content path
"""

from __future__ import annotations

import asyncio
import errno
import json
import threading
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ===================================================================
# 1. aio_sandbox.py
# ===================================================================


class TestAioSandboxExtraCoverage:
    """Lines 45, 50-53, 89-91, 102-107, 139, 168-171, 188-190, 214,
    237-238, 249, 254, 267-268, 279-285."""

    @pytest.fixture()
    def sb(self):
        with patch("ideer.community.aio_sandbox.aio_sandbox.AioSandboxClient"):
            from ideer.community.aio_sandbox.aio_sandbox import AioSandbox

            return AioSandbox(id="t", base_url="http://localhost:8080")

    def test_base_url_property(self, sb):
        assert sb.base_url == "http://localhost:8080"

    def test_home_dir_fetched_from_sandbox(self, sb):
        sb._home_dir = None
        sb._client.sandbox.get_context.return_value = SimpleNamespace(home_dir="/root")
        assert sb.home_dir == "/root"
        assert sb._home_dir == "/root"

    def test_home_dir_cached(self, sb):
        sb._home_dir = "/cached"
        assert sb.home_dir == "/cached"

    def test_execute_command_exception_returns_error(self, sb):
        sb._client.shell.exec_command.side_effect = RuntimeError("boom")
        assert sb.execute_command("x") == "Error: boom"

    def test_execute_command_empty_output(self, sb):
        sb._client.shell.exec_command.return_value = SimpleNamespace(data=SimpleNamespace(output=""))
        assert sb.execute_command("x") == "(no output)"

    def test_execute_command_none_data(self, sb):
        sb._client.shell.exec_command.return_value = SimpleNamespace(data=None)
        assert sb.execute_command("x") == "(no output)"

    def test_read_file_success(self, sb):
        sb._client.file.read_file.return_value = SimpleNamespace(data=SimpleNamespace(content="hi"))
        assert sb.read_file("/f") == "hi"

    def test_read_file_exception(self, sb):
        sb._client.file.read_file.side_effect = OSError("no")
        assert sb.read_file("/f") == "Error: no"

    def test_read_file_none_data(self, sb):
        sb._client.file.read_file.return_value = SimpleNamespace(data=None)
        assert sb.read_file("/f") == ""

    def test_download_file_too_large(self, sb):
        from ideer.community.aio_sandbox.aio_sandbox import _MAX_DOWNLOAD_SIZE

        sb._client.file.download_file.return_value = [b"x" * (_MAX_DOWNLOAD_SIZE + 1)]
        with pytest.raises(OSError) as exc_info:
            sb.download_file("/mnt/user-data/outputs/big.bin")
        assert exc_info.value.errno == errno.EFBIG

    def test_list_dir_empty(self, sb):
        sb._client.shell.exec_command.return_value = SimpleNamespace(data=SimpleNamespace(output=""))
        assert sb.list_dir("/d") == []

    def test_list_dir_none_data(self, sb):
        sb._client.shell.exec_command.return_value = SimpleNamespace(data=None)
        assert sb.list_dir("/d") == []

    def test_list_dir_exception(self, sb):
        sb._client.shell.exec_command.side_effect = RuntimeError("fail")
        assert sb.list_dir("/d") == []

    def test_write_file_exception(self, sb):
        sb._client.file.write_file.side_effect = OSError("disk")
        with pytest.raises(IOError):
            sb.write_file("/f", "c")

    def test_glob_include_dirs_truncation(self, sb):
        entries = [SimpleNamespace(path=f"/r/f{i}.txt") for i in range(5)]
        sb._client.file.list_path.return_value = SimpleNamespace(data=SimpleNamespace(files=entries))
        result, truncated = sb.glob("/r", "*.txt", include_dirs=True, max_results=3)
        assert len(result) == 3
        assert truncated is True

    def test_grep_with_glob(self, sb):
        sb._client.file.find_files.return_value = SimpleNamespace(data=SimpleNamespace(files=["/r/a.py"]))
        sb._client.file.search_in_file.return_value = SimpleNamespace(data=SimpleNamespace(line_numbers=[1], matches=["hello"]))
        matches, _ = sb.grep("/r", "hello", glob="*.py")
        assert len(matches) == 1

    def test_grep_ignores_path(self, sb):
        sb._client.file.list_path.return_value = SimpleNamespace(
            data=SimpleNamespace(
                files=[
                    SimpleNamespace(path="/r/.git/config", is_directory=False),
                    SimpleNamespace(path="/r/app.py", is_directory=False),
                ]
            )
        )
        sb._client.file.search_in_file.return_value = SimpleNamespace(data=SimpleNamespace(line_numbers=[1], matches=["x"]))
        sb.grep("/r", "x")
        sb._client.file.search_in_file.assert_called_once()

    def test_grep_data_none(self, sb):
        sb._client.file.list_path.return_value = SimpleNamespace(
            data=SimpleNamespace(
                files=[
                    SimpleNamespace(path="/r/a.txt", is_directory=False),
                ]
            )
        )
        sb._client.file.search_in_file.return_value = SimpleNamespace(data=None)
        matches, _ = sb.grep("/r", "x")
        assert matches == []

    def test_grep_truncation(self, sb):
        sb._client.file.list_path.return_value = SimpleNamespace(data=SimpleNamespace(files=[SimpleNamespace(path=f"/r/f{i}.txt", is_directory=False) for i in range(5)]))
        sb._client.file.search_in_file.return_value = SimpleNamespace(data=SimpleNamespace(line_numbers=[1], matches=["m"]))
        matches, truncated = sb.grep("/r", "m", max_results=2)
        assert len(matches) == 2
        assert truncated is True

    def test_update_file(self, sb):
        import base64

        sb.update_file("/f", b"\x01\x02")
        sb._client.file.write_file.assert_called_once_with(
            file="/f",
            content=base64.b64encode(b"\x01\x02").decode(),
            encoding="base64",
        )

    def test_update_file_exception(self, sb):
        sb._client.file.write_file.side_effect = OSError("x")
        with pytest.raises(IOError):
            sb.update_file("/f", b"x")


# ===================================================================
# 2. aio_sandbox_provider.py
# ===================================================================


def _provider():
    import importlib

    mod = importlib.import_module("ideer.community.aio_sandbox.aio_sandbox_provider")
    p = mod.AioSandboxProvider.__new__(mod.AioSandboxProvider)
    p._lock = threading.Lock()
    p._sandboxes = {}
    p._sandbox_infos = {}
    p._thread_sandboxes = {}
    p._thread_locks = {}
    p._last_activity = {}
    p._warm_pool = {}
    p._shutdown_called = False
    p._idle_checker_stop = threading.Event()
    p._idle_checker_thread = None
    p._config = {
        "image": "t:latest",
        "port": 8080,
        "container_prefix": "t",
        "idle_timeout": 600,
        "replicas": 3,
        "mounts": [],
        "environment": {},
        "provisioner_url": "",
    }
    p._backend = MagicMock()
    p._backend.list_running.return_value = []
    return p


def _info(sid="s1", url="http://localhost:8080"):
    from ideer.community.aio_sandbox.sandbox_info import SandboxInfo

    return SandboxInfo(sandbox_id=sid, sandbox_url=url, container_name=f"c-{sid}", container_id=f"cid-{sid}", created_at=time.time())


class TestIdleCheckerError:
    """Lines 362-363: loop continues after cleanup error."""

    def test_continues_after_error(self):
        import importlib

        mod = importlib.import_module("ideer.community.aio_sandbox.aio_sandbox_provider")
        p = _provider()
        count = [0]

        def cleanup(t):
            count[0] += 1
            if count[0] == 1:
                raise RuntimeError("err")
            p._idle_checker_stop.set()

        p._cleanup_idle_sandboxes = cleanup
        orig = mod.IDLE_CHECK_INTERVAL
        mod.IDLE_CHECK_INTERVAL = 0
        try:
            p._idle_checker_loop()
        finally:
            mod.IDLE_CHECK_INTERVAL = orig
        assert count[0] == 2


class TestCleanupIdleReverify:
    """Lines 396-405: re-verify skip and destroy error."""

    def test_already_gone_skip(self):
        p = _provider()
        p._last_activity["s1"] = time.time() - 1000
        p._sandboxes["s1"] = MagicMock()
        p._sandbox_infos["s1"] = _info()

        # Simulate: snapshot sees s1 idle, but by re-verify it's gone
        def mock_cleanup(idle_timeout):
            with p._lock:
                to_destroy = ["s1"]
                p._last_activity.pop("s1", None)  # simulate release
            for sid in to_destroy:
                with p._lock:
                    la = p._last_activity.get(sid)
                    if la is None:
                        continue  # line 396-397
                    if (time.time() - la) < idle_timeout:
                        continue  # line 400-401
                try:
                    p.destroy(sid)
                except Exception:
                    pass  # line 404-405

        p._cleanup_idle_sandboxes = mock_cleanup
        p._cleanup_idle_sandboxes(600)
        p._backend.destroy.assert_not_called()

    def test_reacquired_skip(self):
        p = _provider()
        p._last_activity["s1"] = time.time() - 1000
        p._sandboxes["s1"] = MagicMock()

        def mock_cleanup(idle_timeout):
            with p._lock:
                to_destroy = ["s1"]
            for sid in to_destroy:
                with p._lock:
                    p._last_activity[sid] = time.time()  # re-acquired
                    la = p._last_activity.get(sid)
                    if la is not None and (time.time() - la) < idle_timeout:
                        continue

        p._cleanup_idle_sandboxes = mock_cleanup
        p._cleanup_idle_sandboxes(600)
        p._backend.destroy.assert_not_called()

    def test_destroy_error_logged(self, caplog):
        p = _provider()
        p._last_activity["s1"] = time.time() - 1000
        p._sandboxes["s1"] = MagicMock()
        p._sandbox_infos["s1"] = _info()
        p._backend.destroy.side_effect = RuntimeError("down")
        with caplog.at_level("ERROR"):
            p._cleanup_idle_sandboxes(600)
        assert "Failed to destroy" in caplog.text


class TestSignalHandlerBranches:
    """Lines 431-447: signal handler dispatch."""

    @pytest.fixture(autouse=True)
    def _restore_signal_handlers(self):
        import signal as sig

        original_sigterm = sig.getsignal(sig.SIGTERM)
        original_sigint = sig.getsignal(sig.SIGINT)
        original_sighup = sig.getsignal(sig.SIGHUP) if hasattr(sig, "SIGHUP") else None
        yield
        sig.signal(sig.SIGTERM, original_sigterm)
        sig.signal(sig.SIGINT, original_sigint)
        if hasattr(sig, "SIGHUP"):
            sig.signal(sig.SIGHUP, original_sighup)

    def test_sigterm_callable_original(self):
        import importlib
        import signal as sig

        importlib.import_module("ideer.community.aio_sandbox.aio_sandbox_provider")
        p = _provider()
        p.shutdown = MagicMock()
        p._register_signal_handlers()
        # Set mocks AFTER _register_signal_handlers (which overwrites _original_*)
        p._original_sigterm = MagicMock()
        p._original_sigint = MagicMock()
        p._original_sighup = MagicMock()
        handler = sig.getsignal(sig.SIGTERM)
        if callable(handler):
            handler(sig.SIGTERM, None)
            p.shutdown.assert_called_once()
            p._original_sigterm.assert_called_once()

    def test_sighup_dispatch(self):
        import importlib
        import signal as sig

        importlib.import_module("ideer.community.aio_sandbox.aio_sandbox_provider")
        p = _provider()
        p.shutdown = MagicMock()
        p._register_signal_handlers()
        # Set mocks AFTER _register_signal_handlers (which overwrites _original_*)
        p._original_sigterm = MagicMock()
        p._original_sigint = MagicMock()
        p._original_sighup = MagicMock()
        handler = sig.getsignal(sig.SIGTERM)
        if callable(handler) and hasattr(sig, "SIGHUP"):
            handler(sig.SIGHUP, None)
            p._original_sighup.assert_called_once_with(sig.SIGHUP, None)

    def test_sigint_sig_dfl(self):
        import importlib
        import signal as sig

        importlib.import_module("ideer.community.aio_sandbox.aio_sandbox_provider")
        p = _provider()
        p.shutdown = MagicMock()
        p._register_signal_handlers()
        # Set mocks AFTER _register_signal_handlers (which overwrites _original_*)
        p._original_sigterm = MagicMock()
        p._original_sigint = sig.SIG_DFL
        p._original_sighup = MagicMock()
        handler = sig.getsignal(sig.SIGTERM)
        if callable(handler):
            with patch.object(sig, "raise_signal"):
                handler(sig.SIGINT, None)
                p.shutdown.assert_called()
                sig.raise_signal.assert_called_once_with(sig.SIGINT)

    def test_sigterm_sig_dfl(self):
        import importlib
        import signal as sig

        importlib.import_module("ideer.community.aio_sandbox.aio_sandbox_provider")
        p = _provider()
        p.shutdown = MagicMock()
        p._register_signal_handlers()
        # Set mocks AFTER _register_signal_handlers (which overwrites _original_*)
        p._original_sigterm = sig.SIG_DFL
        p._original_sigint = MagicMock()
        p._original_sighup = MagicMock()
        handler = sig.getsignal(sig.SIGTERM)
        if callable(handler):
            with patch.object(sig, "raise_signal"):
                handler(sig.SIGTERM, None)
                p.shutdown.assert_called()
                sig.raise_signal.assert_called_once_with(sig.SIGTERM)

    def test_valueerror_on_register(self, caplog):
        import importlib
        import logging
        import signal as sig

        mod = importlib.import_module("ideer.community.aio_sandbox.aio_sandbox_provider")
        p = _provider()
        logger = logging.getLogger(mod.__name__)
        with patch.object(sig, "signal", side_effect=ValueError("no")):
            with caplog.at_level(logging.DEBUG, logger=logger.name):
                p._register_signal_handlers()
        assert "Could not register" in caplog.text


class TestDiscoverOrCreateAsync:
    """Lines 672-698: async discover/create with lock."""

    @pytest.mark.anyio
    async def test_discovers_existing(self, tmp_path, monkeypatch):
        import importlib

        mod = importlib.import_module("ideer.community.aio_sandbox.aio_sandbox_provider")
        from ideer.config.paths import Paths

        p = _provider()
        info = _info("d1")
        p._backend.discover.return_value = info
        monkeypatch.setattr(mod, "get_paths", lambda: Paths(base_dir=tmp_path))
        monkeypatch.setattr(mod, "get_effective_user_id", lambda: None)
        result = await p._discover_or_create_with_lock_async("t1", "sb")
        assert result == "d1"

    @pytest.mark.anyio
    async def test_creates_new(self, tmp_path, monkeypatch):
        import importlib

        mod = importlib.import_module("ideer.community.aio_sandbox.aio_sandbox_provider")
        from ideer.config.paths import Paths

        p = _provider()
        p._backend.discover.return_value = None
        p._backend.create.return_value = _info("n1")
        monkeypatch.setattr(mod, "get_paths", lambda: Paths(base_dir=tmp_path))
        monkeypatch.setattr(mod, "get_effective_user_id", lambda: None)

        async def fw(url, timeout=30, poll_interval=1.0):
            return True

        monkeypatch.setattr(mod, "wait_for_sandbox_ready_async", fw)
        result = await p._discover_or_create_with_lock_async("t1", "n1")
        assert result == "n1"

    @pytest.mark.anyio
    async def test_rechecks_cache(self, tmp_path, monkeypatch):
        import importlib

        mod = importlib.import_module("ideer.community.aio_sandbox.aio_sandbox_provider")
        from ideer.config.paths import Paths

        p = _provider()
        p._thread_sandboxes["t1"] = "c1"
        p._sandboxes["c1"] = MagicMock()
        monkeypatch.setattr(mod, "get_paths", lambda: Paths(base_dir=tmp_path))
        monkeypatch.setattr(mod, "get_effective_user_id", lambda: None)
        result = await p._discover_or_create_with_lock_async("t1", "c1")
        assert result == "c1"


class TestCreateSandboxAsyncEviction:
    """Lines 759-760: async eviction."""

    @pytest.mark.anyio
    async def test_evicts(self, tmp_path, monkeypatch):
        import importlib

        mod = importlib.import_module("ideer.community.aio_sandbox.aio_sandbox_provider")
        p = _provider()
        p._config["replicas"] = 1
        p._sandboxes = {"a": MagicMock()}
        p._warm_pool["w1"] = (_info("w1"), 100.0)
        p._backend.create.return_value = _info("n1")

        async def fw(url, timeout=30, poll_interval=1.0):
            return True

        monkeypatch.setattr(mod, "wait_for_sandbox_ready_async", fw)
        result = await p._create_sandbox_async("t1", "n1")
        assert result == "n1"
        p._backend.destroy.assert_called_once()


# ===================================================================
# 3. backend.py
# ===================================================================


class TestWaitReady:
    """Lines 28-37: wait_for_sandbox_ready."""

    def test_ready(self):
        from ideer.community.aio_sandbox.backend import wait_for_sandbox_ready

        with patch("ideer.community.aio_sandbox.backend.requests.get", return_value=SimpleNamespace(status_code=200)):
            with patch("ideer.community.aio_sandbox.backend.time.sleep"):
                assert wait_for_sandbox_ready("http://x:80", timeout=5) is True

    def test_timeout(self):
        import requests as req_lib

        from ideer.community.aio_sandbox.backend import wait_for_sandbox_ready

        call_count = 0

        def fake_time():
            nonlocal call_count
            call_count += 1
            # First call records start_time; all subsequent calls return inf
            # so the while-loop condition is immediately False.
            return 0.0 if call_count == 1 else float("inf")

        with patch("ideer.community.aio_sandbox.backend.requests.get", side_effect=req_lib.exceptions.ConnectionError("refused")):
            with patch("ideer.community.aio_sandbox.backend.time.time", side_effect=fake_time):
                with patch("ideer.community.aio_sandbox.backend.time.sleep"):
                    assert wait_for_sandbox_ready("http://x:80", timeout=5) is False

    def test_non_200(self):
        from ideer.community.aio_sandbox.backend import wait_for_sandbox_ready

        call_count = 0

        def fake_time():
            nonlocal call_count
            call_count += 1
            return 0.0 if call_count == 1 else float("inf")

        with patch("ideer.community.aio_sandbox.backend.requests.get", return_value=SimpleNamespace(status_code=503)):
            with patch("ideer.community.aio_sandbox.backend.time.time", side_effect=fake_time):
                with patch("ideer.community.aio_sandbox.backend.time.sleep"):
                    assert wait_for_sandbox_ready("http://x:80", timeout=5) is False


class TestWaitReadyAsync:
    """Line 63: async polling returns False on timeout."""

    @pytest.mark.anyio
    async def test_ready(self):
        from ideer.community.aio_sandbox.backend import wait_for_sandbox_ready_async

        class MC:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            async def get(self, url, **kwargs):
                return SimpleNamespace(status_code=200)

        with patch("ideer.community.aio_sandbox.backend.httpx.AsyncClient", MC):
            assert await wait_for_sandbox_ready_async("http://x:80", timeout=5) is True

    @pytest.mark.anyio
    async def test_timeout(self):
        import httpx

        from ideer.community.aio_sandbox.backend import wait_for_sandbox_ready_async

        class MC:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            async def get(self, url, **kwargs):
                raise httpx.RequestError("fail")

        times = iter([0.0, 0.0, 100.0])
        ml = SimpleNamespace(time=lambda: next(times))
        with patch("ideer.community.aio_sandbox.backend.httpx.AsyncClient", MC):
            with patch("ideer.community.aio_sandbox.backend.asyncio.get_running_loop", return_value=ml):
                assert await wait_for_sandbox_ready_async("http://x:80", timeout=5) is False

    @pytest.mark.anyio
    async def test_non_200(self):
        from ideer.community.aio_sandbox.backend import wait_for_sandbox_ready_async

        class MC:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            async def get(self, url, **kwargs):
                return SimpleNamespace(status_code=503)

        times = iter([0.0, 0.0, 100.0])
        ml = SimpleNamespace(time=lambda: next(times))
        with patch("ideer.community.aio_sandbox.backend.httpx.AsyncClient", MC):
            with patch("ideer.community.aio_sandbox.backend.asyncio.get_running_loop", return_value=ml):
                assert await wait_for_sandbox_ready_async("http://x:80", timeout=5) is False


# ===================================================================
# 4. image_search/tools.py
# ===================================================================


class TestImageSearchToolWrapper:
    """Lines 49-74."""

    def test_config_override(self):
        from ideer.community.image_search.tools import image_search_tool

        with (
            patch("ideer.community.image_search.tools.get_app_config") as mc,
            patch("ideer.community.image_search.tools._search_images", return_value=[{"title": "t", "thumbnail": "u"}]) as ms,
        ):
            cfg = MagicMock()
            cfg.model_extra = {"max_results": 10}
            mc.return_value.get_tool_config.return_value = cfg
            image_search_tool.func(query="q", max_results=5)
        assert ms.call_args[1]["max_results"] == 10

    def test_no_results(self):
        from ideer.community.image_search.tools import image_search_tool

        with (
            patch("ideer.community.image_search.tools.get_app_config") as mc,
            patch("ideer.community.image_search.tools._search_images", return_value=[]),
        ):
            mc.return_value.get_tool_config.return_value = None
            result = image_search_tool.func(query="q")
        data = json.loads(result)
        assert "error" in data

    def test_with_filters(self):
        from ideer.community.image_search.tools import image_search_tool

        with (
            patch("ideer.community.image_search.tools.get_app_config") as mc,
            patch("ideer.community.image_search.tools._search_images", return_value=[{"title": "t", "thumbnail": "u"}]) as ms,
        ):
            mc.return_value.get_tool_config.return_value = None
            image_search_tool.func(query="q", max_results=3, size="Large", type_image="photo", layout="Wide")
        kw = ms.call_args[1]
        assert kw["size"] == "Large"
        assert kw["type_image"] == "photo"
        assert kw["layout"] == "Wide"

    def test_result_normalization(self):
        from ideer.community.image_search.tools import image_search_tool

        results = [
            {"title": "A", "thumbnail": "http://a.jpg"},
            {"title": "B", "thumbnail": "http://b.jpg"},
        ]
        with (
            patch("ideer.community.image_search.tools.get_app_config") as mc,
            patch("ideer.community.image_search.tools._search_images", return_value=results),
        ):
            mc.return_value.get_tool_config.return_value = None
            result = image_search_tool.func(query="q")
        data = json.loads(result)
        assert data["total_results"] == 2
        assert data["results"][0]["image_url"] == "http://a.jpg"


# ===================================================================
# 5. mcp/oauth.py
# ===================================================================


class TestOAuthExtraCoverage:
    """Lines 50, 60, 81, 83, 87, 90-99, 108, 115-116, 131, 144."""

    def _cfg(self, **kw):
        from ideer.config.extensions_config import ExtensionsConfig

        base = {
            "mcpServers": {
                "s1": {
                    "enabled": True,
                    "type": "http",
                    "url": "https://api.example.com/mcp",
                    "oauth": {
                        "enabled": True,
                        "token_url": "https://auth.example.com/token",
                        "grant_type": "client_credentials",
                        "client_id": "cid",
                        "client_secret": "cs",
                        **kw,
                    },
                }
            }
        }
        return ExtensionsConfig.model_validate(base)

    def test_no_server_returns_none(self):
        from ideer.mcp.oauth import OAuthTokenManager

        mgr = OAuthTokenManager({})
        assert asyncio.run(mgr.get_authorization_header("x")) is None

    def test_cached_token(self):
        from ideer.mcp.oauth import OAuthTokenManager, _OAuthToken

        mock_oauth = MagicMock()
        mock_oauth.refresh_skew_seconds = 60
        mgr = OAuthTokenManager({"s1": mock_oauth})
        mgr._tokens["s1"] = _OAuthToken(
            access_token="tok",
            token_type="Bearer",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert asyncio.run(mgr.get_authorization_header("s1")) == "Bearer tok"

    def test_scope_in_request(self, monkeypatch):
        calls = []

        class MC:
            def __init__(self, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            async def post(self, url, data):
                calls.append(data)
                return SimpleNamespace(
                    raise_for_status=lambda: None,
                    json=lambda: {"access_token": "t", "token_type": "Bearer", "expires_in": 3600},
                )

        monkeypatch.setattr("httpx.AsyncClient", MC)
        from ideer.mcp.oauth import OAuthTokenManager

        mgr = OAuthTokenManager.from_extensions_config(self._cfg(scope="r w"))
        asyncio.run(mgr.get_authorization_header("s1"))
        assert calls[0]["scope"] == "r w"

    def test_audience_in_request(self, monkeypatch):
        calls = []

        class MC:
            def __init__(self, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            async def post(self, url, data):
                calls.append(data)
                return SimpleNamespace(
                    raise_for_status=lambda: None,
                    json=lambda: {"access_token": "t", "token_type": "Bearer", "expires_in": 3600},
                )

        monkeypatch.setattr("httpx.AsyncClient", MC)
        from ideer.mcp.oauth import OAuthTokenManager

        mgr = OAuthTokenManager.from_extensions_config(self._cfg(audience="https://api.example.com"))
        asyncio.run(mgr.get_authorization_header("s1"))
        assert calls[0]["audience"] == "https://api.example.com"

    def test_client_credentials_missing_raises(self):
        from ideer.config.extensions_config import ExtensionsConfig
        from ideer.mcp.oauth import OAuthTokenManager

        cfg = ExtensionsConfig.model_validate({"mcpServers": {"s1": {"enabled": True, "type": "http", "url": "x", "oauth": {"enabled": True, "token_url": "x", "grant_type": "client_credentials"}}}})
        mgr = OAuthTokenManager.from_extensions_config(cfg)
        with pytest.raises(ValueError, match="client_id and client_secret"):
            asyncio.run(mgr.get_authorization_header("s1"))

    def test_refresh_token_grant(self, monkeypatch):
        calls = []

        class MC:
            def __init__(self, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            async def post(self, url, data):
                calls.append(data)
                return SimpleNamespace(
                    raise_for_status=lambda: None,
                    json=lambda: {"access_token": "t", "token_type": "Bearer", "expires_in": 3600},
                )

        monkeypatch.setattr("httpx.AsyncClient", MC)
        from ideer.config.extensions_config import ExtensionsConfig
        from ideer.mcp.oauth import OAuthTokenManager

        cfg = ExtensionsConfig.model_validate(
            {"mcpServers": {"s1": {"enabled": True, "type": "http", "url": "x", "oauth": {"enabled": True, "token_url": "x", "grant_type": "refresh_token", "refresh_token": "rt", "client_id": "c", "client_secret": "s"}}}}
        )
        mgr = OAuthTokenManager.from_extensions_config(cfg)
        asyncio.run(mgr.get_authorization_header("s1"))
        assert calls[0]["refresh_token"] == "rt"
        assert calls[0]["client_id"] == "c"

    def test_refresh_token_no_client(self, monkeypatch):
        calls = []

        class MC:
            def __init__(self, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            async def post(self, url, data):
                calls.append(data)
                return SimpleNamespace(
                    raise_for_status=lambda: None,
                    json=lambda: {"access_token": "t", "token_type": "Bearer", "expires_in": 3600},
                )

        monkeypatch.setattr("httpx.AsyncClient", MC)
        from ideer.config.extensions_config import ExtensionsConfig
        from ideer.mcp.oauth import OAuthTokenManager

        cfg = ExtensionsConfig.model_validate({"mcpServers": {"s1": {"enabled": True, "type": "http", "url": "x", "oauth": {"enabled": True, "token_url": "x", "grant_type": "refresh_token", "refresh_token": "rt"}}}})
        mgr = OAuthTokenManager.from_extensions_config(cfg)
        asyncio.run(mgr.get_authorization_header("s1"))
        assert "client_id" not in calls[0]

    def test_unsupported_grant_raises(self):
        from ideer.config.extensions_config import ExtensionsConfig

        with pytest.raises(Exception):
            ExtensionsConfig.model_validate({"mcpServers": {"s1": {"enabled": True, "type": "http", "url": "x", "oauth": {"enabled": True, "token_url": "x", "grant_type": "password", "client_id": "c", "client_secret": "s"}}}})

    def test_missing_token_raises(self, monkeypatch):
        class MC:
            def __init__(self, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            async def post(self, url, data):
                return SimpleNamespace(
                    raise_for_status=lambda: None,
                    json=lambda: {"token_type": "Bearer"},
                )

        monkeypatch.setattr("httpx.AsyncClient", MC)
        from ideer.mcp.oauth import OAuthTokenManager

        mgr = OAuthTokenManager.from_extensions_config(self._cfg())
        with pytest.raises(ValueError, match="missing"):
            asyncio.run(mgr.get_authorization_header("s1"))

    def test_expires_in_non_int(self, monkeypatch):
        class MC:
            def __init__(self, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            async def post(self, url, data):
                return SimpleNamespace(
                    raise_for_status=lambda: None,
                    json=lambda: {"access_token": "t", "expires_in": "bad"},
                )

        monkeypatch.setattr("httpx.AsyncClient", MC)
        from ideer.mcp.oauth import OAuthTokenManager

        mgr = OAuthTokenManager.from_extensions_config(self._cfg())
        result = asyncio.run(mgr.get_authorization_header("s1"))
        assert result == "Bearer t"

    def test_interceptor_no_oauth_passthrough(self):
        from ideer.config.extensions_config import ExtensionsConfig
        from ideer.mcp.oauth import build_oauth_tool_interceptor

        cfg = ExtensionsConfig.model_validate({"mcpServers": {}})
        assert build_oauth_tool_interceptor(cfg) is None

    def test_get_initial_empty(self):
        from ideer.config.extensions_config import ExtensionsConfig
        from ideer.mcp.oauth import get_initial_oauth_headers

        cfg = ExtensionsConfig.model_validate({"mcpServers": {}})
        assert asyncio.run(get_initial_oauth_headers(cfg)) == {}

    def test_interceptor_passthrough_no_auth(self, monkeypatch):
        from ideer.config.extensions_config import ExtensionsConfig
        from ideer.mcp.oauth import build_oauth_tool_interceptor

        cfg = ExtensionsConfig.model_validate({"mcpServers": {"s1": {"enabled": True, "type": "http", "url": "x", "oauth": {"enabled": True, "token_url": "x", "grant_type": "client_credentials", "client_id": "c", "client_secret": "s"}}}})
        interceptor = build_oauth_tool_interceptor(cfg)

        class R:
            server_name = "unknown"
            headers = {}

            def override(self, **kw):
                r = R()
                r.headers = kw.get("headers", {})
                return r

        async def h(req):
            return "ok"

        assert asyncio.run(interceptor(R(), h)) == "ok"


# ===================================================================
# 6. mcp/cache.py
# ===================================================================


class TestMcpCacheExtra:
    """Lines 30, 111, 116-126, 134-136."""

    def setup_method(self):
        import ideer.mcp.cache as cm

        self.m = cm
        self._oi = cm._cache_initialized
        self._om = cm._config_mtime
        self._ot = cm._mcp_tools_cache

    def teardown_method(self):
        self.m._cache_initialized = self._oi
        self.m._config_mtime = self._om
        self.m._mcp_tools_cache = self._ot

    def test_get_config_mtime_with_file(self, tmp_path):
        from ideer.config.extensions_config import ExtensionsConfig

        f = tmp_path / "ext.json"
        f.write_text("{}")
        with patch.object(ExtensionsConfig, "resolve_config_path", return_value=f):
            assert self.m._get_config_mtime() is not None

    def test_get_config_mtime_no_file(self):
        from ideer.config.extensions_config import ExtensionsConfig

        with patch.object(ExtensionsConfig, "resolve_config_path", return_value=None):
            assert self.m._get_config_mtime() is None

    def test_thread_double_check(self):
        self.m._cache_initialized = True
        self.m._mcp_tools_cache = [MagicMock()]
        assert self.m.get_cached_mcp_tools() == self.m._mcp_tools_cache

    def test_running_loop_path(self):
        self.m._cache_initialized = False
        self.m._mcp_tools_cache = None
        tools = [MagicMock()]
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True

        async def mock_init():
            self.m._mcp_tools_cache = tools
            self.m._cache_initialized = True

        with (
            patch("ideer.mcp.cache._is_cache_stale", return_value=False),
            patch("asyncio.get_event_loop", return_value=mock_loop),
            patch("ideer.mcp.cache.initialize_mcp_tools", side_effect=mock_init),
        ):
            result = self.m.get_cached_mcp_tools()
        assert result == tools

    def test_no_loop_run_until_complete(self):
        self.m._cache_initialized = False
        self.m._mcp_tools_cache = None
        tools = [MagicMock()]
        ml = MagicMock()
        ml.is_running.return_value = False
        # Make run_until_complete actually execute the coroutine
        ml.run_until_complete.side_effect = lambda coro: asyncio.run(coro)

        async def mock_init():
            self.m._mcp_tools_cache = tools
            self.m._cache_initialized = True

        with (
            patch("ideer.mcp.cache._is_cache_stale", return_value=False),
            patch("asyncio.get_event_loop", return_value=ml),
            patch("ideer.mcp.cache.initialize_mcp_tools", side_effect=mock_init),
        ):
            result = self.m.get_cached_mcp_tools()
        assert result == tools

    def test_no_loop_runtime_error_fallback(self):
        self.m._cache_initialized = False
        self.m._mcp_tools_cache = None
        tools = [MagicMock()]

        async def mock_init():
            self.m._mcp_tools_cache = tools
            self.m._cache_initialized = True

        with (
            patch("ideer.mcp.cache._is_cache_stale", return_value=False),
            patch("asyncio.get_event_loop", side_effect=RuntimeError("no")),
            patch("ideer.mcp.cache.initialize_mcp_tools", side_effect=mock_init),
        ):
            result = self.m.get_cached_mcp_tools()
        assert result == tools

    def test_no_loop_init_fails(self):
        self.m._cache_initialized = False
        self.m._mcp_tools_cache = None
        with (
            patch("ideer.mcp.cache._is_cache_stale", return_value=False),
            patch("asyncio.get_event_loop", side_effect=RuntimeError("no")),
            patch("asyncio.run", side_effect=RuntimeError("fail")),
        ):
            result = self.m.get_cached_mcp_tools()
        assert result == []


# ===================================================================
# 7. models/patched_minimax.py
# ===================================================================


class TestMiniMaxExtra:
    """Lines 42, 84, 116, 126, 133-140, 145, 155, 157, 161, 169."""

    def _model(self):
        from ideer.models.patched_minimax import PatchedChatMiniMax

        return PatchedChatMiniMax(model="m", api_key="k", base_url="https://x.com/v1")

    def test_extract_non_mapping_item(self):
        from ideer.models.patched_minimax import _extract_reasoning_text

        assert _extract_reasoning_text([123, {"text": "ok"}]) == "ok"

    def test_extract_non_list(self):
        from ideer.models.patched_minimax import _extract_reasoning_text

        assert _extract_reasoning_text("str") is None

    def test_extract_whitespace_only(self):
        from ideer.models.patched_minimax import _extract_reasoning_text

        assert _extract_reasoning_text([{"text": "   "}]) is None

    def test_with_reasoning_empty(self):
        from langchain_core.messages import AIMessage

        from ideer.models.patched_minimax import _with_reasoning_content

        msg = AIMessage(content="x")
        assert _with_reasoning_content(msg, None) is msg

    def test_get_payload_no_extra_body(self):
        m = self._model()
        from langchain_core.messages import HumanMessage

        p = m._get_request_payload([HumanMessage(content="hi")])
        assert p["extra_body"]["reasoning_split"] is True

    def test_chunk_content_delta(self):
        m = self._model()
        from langchain_core.messages import AIMessageChunk

        assert m._convert_chunk_to_generation_chunk({"type": "content.delta"}, AIMessageChunk, {}) is None

    def test_chunk_empty_choices_v1(self):
        m = self._model()
        m.output_version = "v1"
        from langchain_core.messages import AIMessageChunk

        r = m._convert_chunk_to_generation_chunk({"choices": []}, AIMessageChunk, {"k": "v"})
        assert r is not None
        assert r.message.content == []
        assert r.message.response_metadata.get("output_version") == "v1"

    def test_chunk_empty_choices_no_v1(self):
        m = self._model()
        m.output_version = "v2"
        from langchain_core.messages import AIMessageChunk

        r = m._convert_chunk_to_generation_chunk({"choices": []}, AIMessageChunk, {})
        assert r is not None
        assert r.message.content == ""

    def test_chunk_delta_none(self):
        m = self._model()
        from langchain_core.messages import AIMessageChunk

        assert m._convert_chunk_to_generation_chunk({"choices": [{"delta": None}]}, AIMessageChunk, {}) is None

    def test_chunk_system_fingerprint(self):
        m = self._model()
        from langchain_core.messages import AIMessageChunk

        r = m._convert_chunk_to_generation_chunk({"choices": [{"delta": {"content": "x"}, "finish_reason": "stop"}], "system_fingerprint": "fp"}, AIMessageChunk, {})
        assert r.generation_info["system_fingerprint"] == "fp"

    def test_chunk_service_tier(self):
        m = self._model()
        from langchain_core.messages import AIMessageChunk

        r = m._convert_chunk_to_generation_chunk({"choices": [{"delta": {"content": "x"}, "finish_reason": "stop"}], "service_tier": "p"}, AIMessageChunk, {})
        assert r.generation_info["service_tier"] == "p"

    def test_chunk_logprobs(self):
        m = self._model()
        from langchain_core.messages import AIMessageChunk

        r = m._convert_chunk_to_generation_chunk({"choices": [{"delta": {"content": "x"}, "finish_reason": "stop", "logprobs": {"t": 0.5}}]}, AIMessageChunk, {})
        assert r.generation_info["logprobs"] == {"t": 0.5}

    def test_chunk_reasoning_and_usage(self):
        m = self._model()
        from langchain_core.messages import AIMessageChunk

        r = m._convert_chunk_to_generation_chunk(
            {"choices": [{"delta": {"content": "", "reasoning_details": [{"type": "reasoning.text", "text": "think"}]}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}, AIMessageChunk, {}
        )
        assert "reasoning_content" in r.message.additional_kwargs

    def test_create_chat_result_both_reasoning(self):
        m = self._model()
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "<think>t</think>\na",
                        "reasoning_details": [{"type": "reasoning.text", "text": "split"}],
                    },
                    "finish_reason": "stop",
                }
            ]
        }
        r = m._create_chat_result(response)
        assert "reasoning_content" in r.generations[0].message.additional_kwargs

    def test_create_chat_result_no_content_change(self):
        m = self._model()
        response = {"choices": [{"message": {"role": "assistant", "content": "plain"}, "finish_reason": "stop"}]}
        r = m._create_chat_result(response)
        assert r.generations[0].message.content == "plain"


# ===================================================================
# 8. models/patched_openai.py
# ===================================================================


class TestOpenAIExtra:
    """Lines 86-89, 127."""

    def test_fallback_positional_matching(self):
        from langchain_core.messages import AIMessage

        from ideer.models.patched_openai import _restore_tool_call_signatures

        # Payload tool call has id "c2" which doesn't match raw id "c1",
        # triggering the positional fallback in _restore_tool_call_signatures.
        payload_msg = {"role": "assistant", "content": "", "tool_calls": [{"id": "c2", "type": "function", "function": {"name": "fn", "arguments": "{}"}}]}
        orig_msg = AIMessage(content="", additional_kwargs={"tool_calls": [{"id": "c1", "thought_signature": "S=="}]})
        _restore_tool_call_signatures(payload_msg, orig_msg)
        assert payload_msg["tool_calls"][0]["thought_signature"] == "S=="

    def test_no_raw_no_positional_continue(self):
        from langchain_core.messages import AIMessage

        from ideer.models.patched_openai import _restore_tool_call_signatures

        raw = [{"id": "c1", "type": "function", "function": {"name": "f", "arguments": "{}"}, "thought_signature": "S=="}]
        payload_msg = {
            "role": "assistant",
            "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "f", "arguments": "{}"}},
                {"id": "c99", "type": "function", "function": {"name": "g", "arguments": "{}"}},
            ],
        }
        orig = AIMessage(content="", additional_kwargs={"tool_calls": raw})
        _restore_tool_call_signatures(payload_msg, orig)
        assert payload_msg["tool_calls"][0]["thought_signature"] == "S=="
        assert "thought_signature" not in payload_msg["tool_calls"][1]


# ===================================================================
# 9. community/firecrawl/tools.py
# ===================================================================


class TestFirecrawlExtra:
    """Lines 45-46, 69-71."""

    def test_search_exception(self):
        from ideer.community.firecrawl.tools import web_search_tool

        with (
            patch("ideer.community.firecrawl.tools.get_app_config") as mc,
            patch("ideer.community.firecrawl.tools.FirecrawlApp") as mf,
        ):
            mc.return_value.get_tool_config.return_value = None
            mf.return_value.search.side_effect = RuntimeError("down")
            result = web_search_tool.func(query="q")
        assert result.startswith("Error:")

    def test_fetch_no_content(self):
        from ideer.community.firecrawl.tools import web_fetch_tool

        with (
            patch("ideer.community.firecrawl.tools.get_app_config") as mc,
            patch("ideer.community.firecrawl.tools.FirecrawlApp") as mf,
        ):
            mc.return_value.get_tool_config.return_value = None
            r = MagicMock()
            r.markdown = ""
            r.metadata = MagicMock(title="T")
            mf.return_value.scrape.return_value = r
            result = web_fetch_tool.func(url="https://x.com")
        assert result == "Error: No content found"

    def test_fetch_exception(self):
        from ideer.community.firecrawl.tools import web_fetch_tool

        with (
            patch("ideer.community.firecrawl.tools.get_app_config") as mc,
            patch("ideer.community.firecrawl.tools.FirecrawlApp") as mf,
        ):
            mc.return_value.get_tool_config.return_value = None
            mf.return_value.scrape.side_effect = RuntimeError("timeout")
            result = web_fetch_tool.func(url="https://x.com")
        assert result.startswith("Error:")
        assert "timeout" in result

    def test_fetch_no_metadata_title(self):
        from ideer.community.firecrawl.tools import web_fetch_tool

        with (
            patch("ideer.community.firecrawl.tools.get_app_config") as mc,
            patch("ideer.community.firecrawl.tools.FirecrawlApp") as mf,
        ):
            mc.return_value.get_tool_config.return_value = None
            r = MagicMock()
            r.markdown = "content"
            r.metadata = MagicMock(title=None)
            mf.return_value.scrape.return_value = r
            result = web_fetch_tool.func(url="https://x.com")
        assert result.startswith("# Untitled")

    def test_fetch_none_metadata(self):
        from ideer.community.firecrawl.tools import web_fetch_tool

        with (
            patch("ideer.community.firecrawl.tools.get_app_config") as mc,
            patch("ideer.community.firecrawl.tools.FirecrawlApp") as mf,
        ):
            mc.return_value.get_tool_config.return_value = None
            r = MagicMock()
            r.markdown = "content"
            r.metadata = None
            mf.return_value.scrape.return_value = r
            result = web_fetch_tool.func(url="https://x.com")
        assert result.startswith("# Untitled")
