"""Tests for ideer.mcp.session_pool — comprehensive coverage."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideer.mcp.session_pool import MCPSessionPool, get_session_pool, reset_session_pool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_pool():
    reset_session_pool()
    yield
    reset_session_pool()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session() -> MagicMock:
    session = MagicMock()
    session.initialize = AsyncMock()
    return session


def _make_mock_cm(session: MagicMock | None = None) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session or _make_mock_session())
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# MCPSessionPool unit tests
# ---------------------------------------------------------------------------


@pytest.mark.serial
class TestInit:
    def test_initial_state(self):
        pool = MCPSessionPool()
        assert len(pool._entries) == 0
        assert len(pool._context_managers) == 0
        assert pool.MAX_SESSIONS == 256
        assert pool.SESSION_CLOSE_TIMEOUT == 5.0


@pytest.mark.asyncio
async def test_get_session_creates_new():
    """First call for a key creates a new session."""
    pool = MCPSessionPool()
    mock_session = _make_mock_session()
    mock_cm = _make_mock_cm(mock_session)

    with patch("langchain_mcp_adapters.sessions.create_session", return_value=mock_cm):
        session = await pool.get_session("server", "thread-1", {"transport": "stdio", "command": "x", "args": []})

    assert session is mock_session
    mock_session.initialize.assert_awaited_once()
    assert ("server", "thread-1") in pool._entries


@pytest.mark.asyncio
async def test_get_session_reuses_existing():
    """Second call for the same key returns the cached session."""
    pool = MCPSessionPool()
    mock_session = _make_mock_session()
    mock_cm = _make_mock_cm(mock_session)

    with patch("langchain_mcp_adapters.sessions.create_session", return_value=mock_cm):
        s1 = await pool.get_session("server", "thread-1", {"transport": "stdio", "command": "x", "args": []})
        s2 = await pool.get_session("server", "thread-1", {"transport": "stdio", "command": "x", "args": []})

    assert s1 is s2
    assert mock_cm.__aenter__.await_count == 1


@pytest.mark.asyncio
async def test_different_scope_creates_different_session():
    """Different scope keys get different sessions."""
    pool = MCPSessionPool()
    sessions = [_make_mock_session(), _make_mock_session()]
    idx = 0

    class CmFactory:
        async def __aenter__(self):
            nonlocal idx
            s = sessions[idx]
            idx += 1
            return s

        async def __aexit__(self, *args):
            return False

    with patch("langchain_mcp_adapters.sessions.create_session", side_effect=lambda *a, **kw: CmFactory()):
        s1 = await pool.get_session("server", "thread-1", {"transport": "stdio", "command": "x", "args": []})
        s2 = await pool.get_session("server", "thread-2", {"transport": "stdio", "command": "x", "args": []})

    assert s1 is not s2
    assert s1 is sessions[0]
    assert s2 is sessions[1]


@pytest.mark.asyncio
async def test_lru_eviction():
    """Oldest entries are evicted when the pool is full."""
    pool = MCPSessionPool()
    pool.MAX_SESSIONS = 2

    class CmFactory:
        def __init__(self):
            self.closed = False

        async def __aenter__(self):
            return _make_mock_session()

        async def __aexit__(self, *args):
            self.closed = True
            return False

    cms: list[CmFactory] = []

    def make_cm(*a, **kw):
        cm = CmFactory()
        cms.append(cm)
        return cm

    with patch("langchain_mcp_adapters.sessions.create_session", side_effect=make_cm):
        await pool.get_session("s", "t1", {"transport": "stdio", "command": "x", "args": []})
        await pool.get_session("s", "t2", {"transport": "stdio", "command": "x", "args": []})
        # Pool is full (2). Adding t3 should evict t1.
        await pool.get_session("s", "t3", {"transport": "stdio", "command": "x", "args": []})

    assert cms[0].closed is True
    assert cms[1].closed is False
    assert cms[2].closed is False
    assert ("s", "t1") not in pool._entries
    assert ("s", "t3") in pool._entries


@pytest.mark.asyncio
async def test_evicts_session_from_different_loop():
    """Sessions from a different event loop are evicted and replaced."""
    pool = MCPSessionPool()
    old_session = _make_mock_session()
    old_cm = _make_mock_cm(old_session)
    fake_old_loop = MagicMock()

    # Manually insert an entry with a different loop
    pool._entries[("s1", "sc1")] = (old_session, fake_old_loop)
    pool._context_managers[("s1", "sc1")] = old_cm

    new_session = _make_mock_session()
    new_cm = _make_mock_cm(new_session)
    with patch("langchain_mcp_adapters.sessions.create_session", return_value=new_cm):
        result = await pool.get_session("s1", "sc1", {"url": "http://x"})

    assert result is new_session
    old_cm.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_race_condition_uses_existing():
    """When another coroutine inserts the key mid-flight, use theirs."""
    pool = MCPSessionPool()
    existing_session = _make_mock_session()
    existing_loop = asyncio.get_running_loop()

    def fake_create(connection):
        # Simulate the race: another coroutine inserts the key
        pool._entries[("s1", "sc1")] = (existing_session, existing_loop)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=_make_mock_session())
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    with patch("langchain_mcp_adapters.sessions.create_session", side_effect=fake_create):
        result = await pool.get_session("s1", "sc1", {"url": "http://x"})

    assert result is existing_session


@pytest.mark.asyncio
async def test_close_scope():
    """close_scope shuts down sessions for a specific scope key."""
    pool = MCPSessionPool()
    cm1 = _make_mock_cm()
    cm2 = _make_mock_cm()
    loop = asyncio.get_running_loop()
    pool._entries[("s1", "thread1")] = (MagicMock(), loop)
    pool._entries[("s2", "thread1")] = (MagicMock(), loop)
    pool._entries[("s3", "thread2")] = (MagicMock(), loop)
    pool._context_managers[("s1", "thread1")] = cm1
    pool._context_managers[("s2", "thread1")] = cm2

    await pool.close_scope("thread1")

    assert ("s1", "thread1") not in pool._entries
    assert ("s2", "thread1") not in pool._entries
    assert ("s3", "thread2") in pool._entries
    cm1.__aexit__.assert_awaited_once()
    cm2.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_scope_no_sessions():
    """close_scope on nonexistent scope is a no-op."""
    pool = MCPSessionPool()
    await pool.close_scope("nonexistent")


@pytest.mark.asyncio
async def test_close_scope_handles_close_error():
    """close_scope swallows errors from cm.__aexit__."""
    pool = MCPSessionPool()
    cm = _make_mock_cm()
    cm.__aexit__ = AsyncMock(side_effect=RuntimeError("close error"))
    loop = asyncio.get_running_loop()
    pool._entries[("s1", "t1")] = (MagicMock(), loop)
    pool._context_managers[("s1", "t1")] = cm

    # Should not raise
    await pool.close_scope("t1")


@pytest.mark.asyncio
async def test_close_server():
    """close_server shuts down all sessions for a given server."""
    pool = MCPSessionPool()
    cm1 = _make_mock_cm()
    cm2 = _make_mock_cm()
    cm3 = _make_mock_cm()
    loop = asyncio.get_running_loop()
    pool._entries[("srv1", "t1")] = (MagicMock(), loop)
    pool._entries[("srv1", "t2")] = (MagicMock(), loop)
    pool._entries[("srv2", "t1")] = (MagicMock(), loop)
    pool._context_managers[("srv1", "t1")] = cm1
    pool._context_managers[("srv1", "t2")] = cm2
    pool._context_managers[("srv2", "t1")] = cm3

    await pool.close_server("srv1")

    assert ("srv1", "t1") not in pool._entries
    assert ("srv1", "t2") not in pool._entries
    assert ("srv2", "t1") in pool._entries
    cm1.__aexit__.assert_awaited_once()
    cm2.__aexit__.assert_awaited_once()
    cm3.__aexit__.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_server_no_sessions():
    pool = MCPSessionPool()
    await pool.close_server("nonexistent")


@pytest.mark.asyncio
async def test_close_server_handles_error():
    pool = MCPSessionPool()
    cm = _make_mock_cm()
    cm.__aexit__ = AsyncMock(side_effect=RuntimeError("boom"))
    loop = asyncio.get_running_loop()
    pool._entries[("s1", "t1")] = (MagicMock(), loop)
    pool._context_managers[("s1", "t1")] = cm
    # Should not raise
    await pool.close_server("s1")


@pytest.mark.asyncio
async def test_close_all():
    """close_all shuts down every session."""
    pool = MCPSessionPool()
    cm1 = _make_mock_cm()
    cm2 = _make_mock_cm()
    loop = asyncio.get_running_loop()
    pool._entries[("s1", "t1")] = (MagicMock(), loop)
    pool._entries[("s2", "t2")] = (MagicMock(), loop)
    pool._context_managers[("s1", "t1")] = cm1
    pool._context_managers[("s2", "t2")] = cm2

    await pool.close_all()

    assert len(pool._entries) == 0
    assert len(pool._context_managers) == 0
    cm1.__aexit__.assert_awaited_once()
    cm2.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_all_empty():
    pool = MCPSessionPool()
    await pool.close_all()


@pytest.mark.asyncio
async def test_close_all_handles_error():
    pool = MCPSessionPool()
    cm = _make_mock_cm()
    cm.__aexit__ = AsyncMock(side_effect=RuntimeError("err"))
    loop = asyncio.get_running_loop()
    pool._entries[("s1", "t1")] = (MagicMock(), loop)
    pool._context_managers[("s1", "t1")] = cm
    # Should not raise
    await pool.close_all()


# ===================================================================
# close_all_sync
# ===================================================================


class TestCloseAllSync:
    def test_closes_sessions_on_running_loop(self):
        pool = MCPSessionPool()
        cm = _make_mock_cm()
        loop = MagicMock()
        loop.is_closed.return_value = False
        loop.is_running.return_value = True

        pool._entries[("s1", "t1")] = (MagicMock(), loop)
        pool._context_managers[("s1", "t1")] = cm

        mock_future = MagicMock()
        mock_future.result.return_value = None
        with patch("asyncio.run_coroutine_threadsafe", return_value=mock_future) as mock_rcs:
            pool.close_all_sync()
            mock_rcs.assert_called_once()
            mock_future.result.assert_called_once_with(timeout=pool.SESSION_CLOSE_TIMEOUT)

    def test_closes_sessions_on_stopped_loop(self):
        pool = MCPSessionPool()
        cm = _make_mock_cm()
        loop = MagicMock()
        loop.is_closed.return_value = False
        loop.is_running.return_value = False

        pool._entries[("s1", "t1")] = (MagicMock(), loop)
        pool._context_managers[("s1", "t1")] = cm

        pool.close_all_sync()
        loop.run_until_complete.assert_called_once()

    def test_skips_closed_loop(self):
        pool = MCPSessionPool()
        cm = _make_mock_cm()
        loop = MagicMock()
        loop.is_closed.return_value = True

        pool._entries[("s1", "t1")] = (MagicMock(), loop)
        pool._context_managers[("s1", "t1")] = cm

        pool.close_all_sync()
        cm.__aexit__.assert_not_awaited()

    def test_skips_missing_cm(self):
        pool = MCPSessionPool()
        loop = MagicMock()
        loop.is_closed.return_value = False
        loop.is_running.return_value = False

        pool._entries[("s1", "t1")] = (MagicMock(), loop)
        # No entry in _context_managers

        pool.close_all_sync()
        loop.run_until_complete.assert_not_called()

    def test_handles_close_error(self):
        pool = MCPSessionPool()
        cm = _make_mock_cm()
        loop = MagicMock()
        loop.is_closed.return_value = False
        loop.is_running.return_value = False
        loop.run_until_complete.side_effect = RuntimeError("boom")

        pool._entries[("s1", "t1")] = (MagicMock(), loop)
        pool._context_managers[("s1", "t1")] = cm

        # Should not raise
        pool.close_all_sync()

    def test_clears_entries(self):
        pool = MCPSessionPool()
        loop = MagicMock()
        loop.is_closed.return_value = True
        pool._entries[("s1", "t1")] = (MagicMock(), loop)

        pool.close_all_sync()
        assert len(pool._entries) == 0
        assert len(pool._context_managers) == 0


# ===================================================================
# _close_cm helper
# ===================================================================


class TestCloseCmHelper:
    @pytest.mark.asyncio
    async def test_close_cm_success(self):
        pool = MCPSessionPool()
        cm = _make_mock_cm()
        await pool._close_cm(("s", "t"), cm)
        cm.__aexit__.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_cm_error(self):
        pool = MCPSessionPool()
        cm = _make_mock_cm()
        cm.__aexit__ = AsyncMock(side_effect=RuntimeError("err"))
        # Should not raise
        await pool._close_cm(("s", "t"), cm)


# ---------------------------------------------------------------------------
# Singleton helpers
# ---------------------------------------------------------------------------


@pytest.mark.serial
def test_get_session_pool_singleton():
    """get_session_pool returns the same instance."""
    p1 = get_session_pool()
    p2 = get_session_pool()
    assert p1 is p2


@pytest.mark.serial
def test_reset_session_pool():
    """reset_session_pool clears the singleton."""
    p1 = get_session_pool()
    reset_session_pool()
    p2 = get_session_pool()
    assert p1 is not p2


@pytest.mark.serial
def test_thread_safety_of_singleton():
    """Multiple threads calling get_session_pool get the same instance."""
    import threading

    results = []
    barrier = threading.Barrier(5)

    def get_pool():
        barrier.wait()
        results.append(id(get_session_pool()))

    threads = [threading.Thread(target=get_pool) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(set(results)) == 1


# ---------------------------------------------------------------------------
# Integration: _make_session_pool_tool uses the pool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_pool_tool_wrapping():
    """The wrapper tool delegates to a pool-managed session."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    from ideer.mcp.tools import _make_session_pool_tool

    class Args(BaseModel):
        url: str = Field(..., description="url")

    original_tool = StructuredTool(
        name="playwright_navigate",
        description="Navigate browser",
        args_schema=Args,
        coroutine=AsyncMock(),
        response_format="content_and_artifact",
    )

    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=MagicMock(content=[], isError=False, structuredContent=None))
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    connection = {"transport": "stdio", "command": "pw", "args": []}

    with patch("langchain_mcp_adapters.sessions.create_session", return_value=mock_cm):
        wrapped = _make_session_pool_tool(original_tool, "playwright", connection)

        mock_runtime = MagicMock()
        mock_runtime.context = {"thread_id": "thread-42"}
        mock_runtime.config = {}

        await wrapped.coroutine(runtime=mock_runtime, url="https://example.com")

    mock_session.call_tool.assert_awaited_once_with("navigate", {"url": "https://example.com"})


@pytest.mark.asyncio
async def test_session_pool_tool_extracts_thread_id():
    """Thread ID is extracted from runtime.config when not in context."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    from ideer.mcp.tools import _make_session_pool_tool

    class Args(BaseModel):
        x: int = Field(..., description="x")

    original_tool = StructuredTool(
        name="server_tool",
        description="test",
        args_schema=Args,
        coroutine=AsyncMock(),
        response_format="content_and_artifact",
    )

    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=MagicMock(content=[], isError=False, structuredContent=None))
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("langchain_mcp_adapters.sessions.create_session", return_value=mock_cm):
        wrapped = _make_session_pool_tool(original_tool, "server", {"transport": "stdio", "command": "x", "args": []})

        mock_runtime = MagicMock()
        mock_runtime.context = {}
        mock_runtime.config = {"configurable": {"thread_id": "from-config"}}

        await wrapped.coroutine(runtime=mock_runtime, x=1)

    pool = get_session_pool()
    assert ("server", "from-config") in pool._entries


@pytest.mark.asyncio
async def test_session_pool_tool_default_scope():
    """When no thread_id is available, 'default' is used as scope key."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    from ideer.mcp.tools import _make_session_pool_tool

    class Args(BaseModel):
        x: int = Field(..., description="x")

    original_tool = StructuredTool(
        name="server_tool",
        description="test",
        args_schema=Args,
        coroutine=AsyncMock(),
        response_format="content_and_artifact",
    )

    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=MagicMock(content=[], isError=False, structuredContent=None))
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("langchain_mcp_adapters.sessions.create_session", return_value=mock_cm):
        wrapped = _make_session_pool_tool(original_tool, "server", {"transport": "stdio", "command": "x", "args": []})
        await wrapped.coroutine(runtime=None, x=1)

    pool = get_session_pool()
    assert ("server", "default") in pool._entries


@pytest.mark.asyncio
async def test_session_pool_tool_get_config_fallback():
    """When runtime is None, get_config() provides thread_id as fallback."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    from ideer.mcp.tools import _make_session_pool_tool

    class Args(BaseModel):
        x: int = Field(..., description="x")

    original_tool = StructuredTool(
        name="server_tool",
        description="test",
        args_schema=Args,
        coroutine=AsyncMock(),
        response_format="content_and_artifact",
    )

    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=MagicMock(content=[], isError=False, structuredContent=None))
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    fake_config = {"configurable": {"thread_id": "from-langgraph-config"}}

    with (
        patch("langchain_mcp_adapters.sessions.create_session", return_value=mock_cm),
        patch("ideer.mcp.tools.get_config", return_value=fake_config),
    ):
        wrapped = _make_session_pool_tool(original_tool, "server", {"transport": "stdio", "command": "x", "args": []})
        await wrapped.coroutine(runtime=None, x=1)

    pool = get_session_pool()
    assert ("server", "from-langgraph-config") in pool._entries


def test_session_pool_tool_sync_wrapper_path_is_safe():
    """Sync wrapper (tool.func) invocation doesn't crash on cross-loop access."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    from ideer.mcp.tools import _make_session_pool_tool
    from ideer.tools.sync import make_sync_tool_wrapper

    class Args(BaseModel):
        url: str = Field(..., description="url")

    original_tool = StructuredTool(
        name="playwright_navigate",
        description="Navigate browser",
        args_schema=Args,
        coroutine=AsyncMock(),
        response_format="content_and_artifact",
    )

    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=MagicMock(content=[], isError=False, structuredContent=None))
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    connection = {"transport": "stdio", "command": "pw", "args": []}

    with patch("langchain_mcp_adapters.sessions.create_session", return_value=mock_cm):
        wrapped = _make_session_pool_tool(original_tool, "playwright", connection)
        wrapped.func = make_sync_tool_wrapper(wrapped.coroutine, wrapped.name)
        wrapped.func(url="https://example.com")

    mock_session.call_tool.assert_called_once_with("navigate", {"url": "https://example.com"})


# ---------------------------------------------------------------------------
# get_mcp_tools: HTTP transport should NOT be pooled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_transport_tools_not_pooled():
    """HTTP/SSE transport tools should NOT be wrapped with the session pool."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    from ideer.mcp.tools import get_mcp_tools

    class Args(BaseModel):
        query: str = Field(..., description="query")

    http_tool = StructuredTool(
        name="myserver_search",
        description="Search tool",
        args_schema=Args,
        coroutine=AsyncMock(),
        response_format="content_and_artifact",
    )

    stdio_tool = StructuredTool(
        name="playwright_navigate",
        description="Navigate browser",
        args_schema=Args,
        coroutine=AsyncMock(),
        response_format="content_and_artifact",
    )

    mock_session = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    extensions_config = MagicMock()
    extensions_config.get_enabled_mcp_servers.return_value = {
        "myserver": MagicMock(type="http", url="http://localhost:8000/mcp", headers=None, command=None, args=[], env=None),
        "playwright": MagicMock(type="stdio", command="npx", args=["-y", "@anthropic/mcp-server-playwright"], env=None, url=None, headers=None),
    }
    extensions_config.model_extra = {}

    servers_config = {
        "myserver": {"transport": "http", "url": "http://localhost:8000/mcp"},
        "playwright": {"transport": "stdio", "command": "npx", "args": ["-y", "@anthropic/mcp-server-playwright"]},
    }

    with (
        patch("ideer.mcp.tools.ExtensionsConfig.from_file", return_value=extensions_config),
        patch("ideer.mcp.tools.build_servers_config", return_value=servers_config),
        patch("ideer.mcp.tools.get_initial_oauth_headers", return_value={}),
        patch("ideer.mcp.tools.build_oauth_tool_interceptor", return_value=None),
        patch("langchain_mcp_adapters.client.MultiServerMCPClient") as MockClient,
        patch("langchain_mcp_adapters.sessions.create_session", return_value=mock_cm),
    ):
        mock_client_instance = MockClient.return_value
        mock_client_instance.get_tools = AsyncMock(return_value=[http_tool, stdio_tool])
        tools = await get_mcp_tools()

    pool = get_session_pool()
    assert list(pool._entries.keys()) == []

    http_tools = [t for t in tools if t.name == "myserver_search"]
    assert len(http_tools) == 1
    assert http_tools[0].coroutine is http_tool.coroutine

    stdio_tools = [t for t in tools if t.name == "playwright_navigate"]
    assert len(stdio_tools) == 1
    assert stdio_tools[0].coroutine is not stdio_tool.coroutine
