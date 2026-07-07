"""Tests for DeferredToolFilterMiddleware."""

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt.tool_node import ToolCallRequest

from ideer.agents.middlewares.deferred_tool_filter_middleware import DeferredToolFilterMiddleware
from ideer.tools.builtins.tool_search import DeferredToolRegistry, reset_deferred_registry, set_deferred_registry

# ── helpers ──


def _tool(name: str, description: str = "") -> StructuredTool:
    """Create a minimal StructuredTool stub with only the fields the middleware reads."""
    t = MagicMock(spec=StructuredTool)
    t.name = name
    t.description = description
    return t


def _model_request(tools=None):
    """Build a lightweight ModelRequest-compatible object."""
    from langchain.agents.middleware.types import ModelRequest

    return ModelRequest(
        model=MagicMock(),
        messages=[],
        tools=tools or [],
    )


def _tool_call_request(name: str = "web_search", tool_call_id: str = "tc-1") -> ToolCallRequest:
    tool_call = {"name": name, "id": tool_call_id, "args": {}}
    return ToolCallRequest(
        tool_call=tool_call,
        tool=None,
        state={},
        runtime=MagicMock(),
    )


# ── wrap_model_call (sync) ──


class TestWrapModelCall:
    def setup_method(self):
        self.mw = DeferredToolFilterMiddleware()
        self.registry = DeferredToolRegistry()
        set_deferred_registry(self.registry)

    def teardown_method(self):
        reset_deferred_registry()

    def test_no_registry_passes_all_tools_through(self):
        reset_deferred_registry()
        tools = [_tool("a"), _tool("b")]
        req = _model_request(tools=tools)
        captured = {}

        def handler(r):
            captured["tools"] = r.tools
            return MagicMock()

        self.mw.wrap_model_call(req, handler)
        assert captured["tools"] == tools

    def test_empty_registry_passes_all_tools(self):
        tools = [_tool("a"), _tool("b")]
        req = _model_request(tools=tools)
        captured = {}

        def handler(r):
            captured["tools"] = r.tools
            return MagicMock()

        self.mw.wrap_model_call(req, handler)
        assert captured["tools"] == tools

    def test_filters_deferred_tools(self):
        self.registry.register(_tool("tool_search"))
        self.registry.register(_tool("deploy_prod"))
        tools = [_tool("web_search"), _tool("tool_search"), _tool("deploy_prod"), _tool("read_file")]
        req = _model_request(tools=tools)
        captured = {}

        def handler(r):
            captured["tools"] = r.tools
            return MagicMock()

        self.mw.wrap_model_call(req, handler)
        assert [t.name for t in captured["tools"]] == ["web_search", "read_file"]

    def test_all_deferred_results_in_empty_tool_list(self):
        self.registry.register(_tool("x"))
        self.registry.register(_tool("y"))
        req = _model_request(tools=[_tool("x"), _tool("y")])
        captured = {}

        def handler(r):
            captured["tools"] = r.tools
            return MagicMock()

        self.mw.wrap_model_call(req, handler)
        assert captured["tools"] == []

    def test_empty_tool_list_remains_empty(self):
        self.registry.register(_tool("x"))
        req = _model_request(tools=[])
        captured = {}

        def handler(r):
            captured["tools"] = r.tools
            return MagicMock()

        self.mw.wrap_model_call(req, handler)
        assert captured["tools"] == []

    def test_promoted_tools_pass_through(self):
        self.registry.register(_tool("temp"))
        self.registry.promote({"temp"})
        tools = [_tool("temp"), _tool("other")]
        req = _model_request(tools=tools)
        captured = {}

        def handler(r):
            captured["tools"] = r.tools
            return MagicMock()

        self.mw.wrap_model_call(req, handler)
        assert [t.name for t in captured["tools"]] == ["temp", "other"]

    def test_handler_returns_its_result(self):
        tools = [_tool("a")]
        req = _model_request(tools=tools)
        sentinel = MagicMock()

        result = self.mw.wrap_model_call(req, lambda _r: sentinel)
        assert result is sentinel


# ── awrap_model_call (async) ──


class TestAWrapModelCall:
    def setup_method(self):
        self.mw = DeferredToolFilterMiddleware()
        self.registry = DeferredToolRegistry()
        set_deferred_registry(self.registry)

    def teardown_method(self):
        reset_deferred_registry()

    @pytest.mark.anyio
    async def test_filters_deferred_tools(self):
        self.registry.register(_tool("hidden"))
        tools = [_tool("visible"), _tool("hidden")]
        req = _model_request(tools=tools)
        captured = {}

        async def handler(r):
            captured["tools"] = r.tools
            return MagicMock()

        await self.mw.awrap_model_call(req, handler)
        assert [t.name for t in captured["tools"]] == ["visible"]

    @pytest.mark.anyio
    async def test_no_registry_passes_all(self):
        reset_deferred_registry()
        tools = [_tool("a")]
        req = _model_request(tools=tools)
        captured = {}

        async def handler(r):
            captured["tools"] = r.tools
            return MagicMock()

        await self.mw.awrap_model_call(req, handler)
        assert captured["tools"] == tools

    @pytest.mark.anyio
    async def test_handler_returns_its_result(self):
        sentinel = MagicMock()
        req = _model_request(tools=[])
        result = await self.mw.awrap_model_call(req, lambda _r: asyncio_coro(sentinel))
        assert result is sentinel

    @pytest.mark.anyio
    async def test_empty_registry_passes_all_tools(self):
        tools = [_tool("a"), _tool("b")]
        req = _model_request(tools=tools)
        captured = {}

        async def handler(r):
            captured["tools"] = r.tools
            return MagicMock()

        await self.mw.awrap_model_call(req, handler)
        assert captured["tools"] == tools

    @pytest.mark.anyio
    async def test_all_deferred_results_in_empty_tool_list(self):
        self.registry.register(_tool("x"))
        self.registry.register(_tool("y"))
        req = _model_request(tools=[_tool("x"), _tool("y")])
        captured = {}

        async def handler(r):
            captured["tools"] = r.tools
            return MagicMock()

        await self.mw.awrap_model_call(req, handler)
        assert captured["tools"] == []

    @pytest.mark.anyio
    async def test_empty_tool_list_remains_empty(self):
        self.registry.register(_tool("x"))
        req = _model_request(tools=[])
        captured = {}

        async def handler(r):
            captured["tools"] = r.tools
            return MagicMock()

        await self.mw.awrap_model_call(req, handler)
        assert captured["tools"] == []

    @pytest.mark.anyio
    async def test_promoted_tools_pass_through(self):
        self.registry.register(_tool("temp"))
        self.registry.promote({"temp"})
        tools = [_tool("temp"), _tool("other")]
        req = _model_request(tools=tools)
        captured = {}

        async def handler(r):
            captured["tools"] = r.tools
            return MagicMock()

        await self.mw.awrap_model_call(req, handler)
        assert [t.name for t in captured["tools"]] == ["temp", "other"]


async def asyncio_coro(val):
    return val


# ── wrap_tool_call (sync) ──


class TestWrapToolCall:
    def setup_method(self):
        self.mw = DeferredToolFilterMiddleware()
        self.registry = DeferredToolRegistry()
        set_deferred_registry(self.registry)

    def teardown_method(self):
        reset_deferred_registry()

    def test_no_registry_passes_through(self):
        reset_deferred_registry()
        req = _tool_call_request(name="web_search")
        sentinel = ToolMessage(content="ok", tool_call_id="tc-1")
        result = self.mw.wrap_tool_call(req, lambda _r: sentinel)
        assert result is sentinel

    def test_non_deferred_tool_passes_through(self):
        req = _tool_call_request(name="web_search")
        sentinel = ToolMessage(content="ok", tool_call_id="tc-1")
        result = self.mw.wrap_tool_call(req, lambda _r: sentinel)
        assert result is sentinel

    def test_deferred_tool_is_blocked(self):
        self.registry.register(_tool("hidden_tool"))
        req = _tool_call_request(name="hidden_tool", tool_call_id="tc-blocked")
        result = self.mw.wrap_tool_call(req, lambda _r: ToolMessage(content="should not run", tool_call_id="tc-blocked"))

        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert result.tool_call_id == "tc-blocked"
        assert result.name == "hidden_tool"
        assert "deferred" in result.text.lower()

    def test_handler_not_called_for_deferred_tool(self):
        self.registry.register(_tool("deferred_x"))
        req = _tool_call_request(name="deferred_x")
        called = False

        def handler(_r):
            nonlocal called
            called = True
            return MagicMock()

        self.mw.wrap_tool_call(req, handler)
        assert not called

    def test_empty_tool_call_name_passes_through(self):
        req = _tool_call_request(name="")
        sentinel = ToolMessage(content="ok", tool_call_id="tc-1")
        result = self.mw.wrap_tool_call(req, lambda _r: sentinel)
        assert result is sentinel

    def test_missing_tool_call_name_key_passes_through(self):
        """When tool_call dict lacks 'name' key entirely, .get('name') returns None → empty string → pass through."""
        tool_call = {"id": "tc-missing-name", "args": {}}
        req = ToolCallRequest(tool_call=tool_call, tool=None, state={}, runtime=MagicMock())
        sentinel = ToolMessage(content="ok", tool_call_id="tc-missing-name")
        result = self.mw.wrap_tool_call(req, lambda _r: sentinel)
        assert result is sentinel

    def test_missing_tool_call_id_uses_fallback(self):
        self.registry.register(_tool("deferred_y"))
        req = _tool_call_request(name="deferred_y", tool_call_id=None)
        result = self.mw.wrap_tool_call(req, lambda _r: MagicMock())

        assert isinstance(result, ToolMessage)
        assert result.tool_call_id == "missing_tool_call_id"

    def test_tool_call_dict_missing_id_key_uses_fallback(self):
        """When tool_call dict lacks 'id' key entirely, .get('id') returns None → fallback string."""
        self.registry.register(_tool("deferred_z"))
        tool_call = {"name": "deferred_z", "args": {}}
        req = ToolCallRequest(tool_call=tool_call, tool=None, state={}, runtime=MagicMock())
        result = self.mw.wrap_tool_call(req, lambda _r: MagicMock())

        assert isinstance(result, ToolMessage)
        assert result.tool_call_id == "missing_tool_call_id"

    def test_promoted_tool_passes_through_tool_call(self):
        """After promote, deferred tool should be callable (not blocked) via wrap_tool_call."""
        self.registry.register(_tool("was_deferred"))
        self.registry.promote({"was_deferred"})
        req = _tool_call_request(name="was_deferred")
        sentinel = ToolMessage(content="ok", tool_call_id="tc-1")
        called = False

        def handler(_r):
            nonlocal called
            called = True
            return sentinel

        result = self.mw.wrap_tool_call(req, handler)
        assert called
        assert result is sentinel


# ── awrap_tool_call (async) ──


class TestAWrapToolCall:
    def setup_method(self):
        self.mw = DeferredToolFilterMiddleware()
        self.registry = DeferredToolRegistry()
        set_deferred_registry(self.registry)

    def teardown_method(self):
        reset_deferred_registry()

    @pytest.mark.anyio
    async def test_deferred_tool_is_blocked(self):
        self.registry.register(_tool("async_hidden"))
        req = _tool_call_request(name="async_hidden", tool_call_id="tc-a1")
        result = await self.mw.awrap_tool_call(req, lambda _r: async_identity(ToolMessage(content="no", tool_call_id="tc-a1")))
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert "deferred" in result.text.lower()

    @pytest.mark.anyio
    async def test_non_deferred_tool_passes_through(self):
        req = _tool_call_request(name="open_tool")
        sentinel = ToolMessage(content="ok", tool_call_id="tc-a2")
        result = await self.mw.awrap_tool_call(req, lambda _r: async_identity(sentinel))
        assert result is sentinel

    @pytest.mark.anyio
    async def test_no_registry_passes_through(self):
        reset_deferred_registry()
        req = _tool_call_request(name="anything")
        sentinel = ToolMessage(content="ok", tool_call_id="tc-a3")
        result = await self.mw.awrap_tool_call(req, lambda _r: async_identity(sentinel))
        assert result is sentinel

    @pytest.mark.anyio
    async def test_handler_not_called_for_deferred_tool(self):
        self.registry.register(_tool("async_deferred"))
        req = _tool_call_request(name="async_deferred")
        called = False

        async def handler(_r):
            nonlocal called
            called = True
            return MagicMock()

        await self.mw.awrap_tool_call(req, handler)
        assert not called

    @pytest.mark.anyio
    async def test_empty_tool_call_name_passes_through(self):
        req = _tool_call_request(name="")
        sentinel = ToolMessage(content="ok", tool_call_id="tc-a4")
        result = await self.mw.awrap_tool_call(req, lambda _r: async_identity(sentinel))
        assert result is sentinel

    @pytest.mark.anyio
    async def test_missing_tool_call_name_key_passes_through(self):
        tool_call = {"id": "tc-async-missing", "args": {}}
        req = ToolCallRequest(tool_call=tool_call, tool=None, state={}, runtime=MagicMock())
        sentinel = ToolMessage(content="ok", tool_call_id="tc-async-missing")
        result = await self.mw.awrap_tool_call(req, lambda _r: async_identity(sentinel))
        assert result is sentinel

    @pytest.mark.anyio
    async def test_tool_call_dict_missing_id_key_uses_fallback(self):
        self.registry.register(_tool("async_deferred_z"))
        tool_call = {"name": "async_deferred_z", "args": {}}
        req = ToolCallRequest(tool_call=tool_call, tool=None, state={}, runtime=MagicMock())
        result = await self.mw.awrap_tool_call(req, lambda _r: async_identity(MagicMock()))
        assert isinstance(result, ToolMessage)
        assert result.tool_call_id == "missing_tool_call_id"

    @pytest.mark.anyio
    async def test_promoted_tool_passes_through_tool_call(self):
        self.registry.register(_tool("async_was_deferred"))
        self.registry.promote({"async_was_deferred"})
        req = _tool_call_request(name="async_was_deferred")
        sentinel = ToolMessage(content="ok", tool_call_id="tc-a5")
        called = False

        async def handler(_r):
            nonlocal called
            called = True
            return sentinel

        result = await self.mw.awrap_tool_call(req, handler)
        assert called
        assert result is sentinel


async def async_identity(val):
    return val
