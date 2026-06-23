"""Comprehensive tests for ideer.mcp.tools module.

Covers:
  - _extract_thread_id: all branches (runtime provided, context/config sources, get_config fallback, RuntimeError)
  - _convert_call_tool_result: ToolMessage passthrough, Command passthrough (with/without langgraph),
    all MCP content block types, isError handling, structuredContent artifact
  - _make_session_pool_tool: prefix stripping, interceptor chaining, StructuredTool construction
  - get_mcp_tools: import guard, empty config, OAuth header injection, stdio vs non-stdio wrapping,
    sync wrapper patching, exception handling
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# _extract_thread_id
# ---------------------------------------------------------------------------


class TestExtractThreadId:
    """Tests for _extract_thread_id."""

    def _call(self, runtime=None):
        from ideer.mcp.tools import _extract_thread_id

        return _extract_thread_id(runtime)

    def test_runtime_context_has_thread_id(self):
        runtime = SimpleNamespace(context={"thread_id": "ctx-tid"}, config=None)
        assert self._call(runtime) == "ctx-tid"

    def test_runtime_context_thread_id_is_int(self):
        runtime = SimpleNamespace(context={"thread_id": 42}, config=None)
        assert self._call(runtime) == "42"

    def test_runtime_context_none_falls_through(self):
        """runtime.context is None -> falls through to config / get_config."""
        runtime = SimpleNamespace(context=None, config={"configurable": {"thread_id": "cfg-tid"}})
        assert self._call(runtime) == "cfg-tid"

    def test_runtime_context_missing_thread_id_uses_config(self):
        runtime = SimpleNamespace(context={}, config={"configurable": {"thread_id": "from-config"}})
        assert self._call(runtime) == "from-config"

    def test_runtime_config_thread_id(self):
        runtime = SimpleNamespace(context={}, config={"configurable": {"thread_id": "c-tid"}})
        assert self._call(runtime) == "c-tid"

    def test_runtime_config_no_configurable(self):
        """config dict without 'configurable' key -> falls to get_config."""
        with patch("ideer.mcp.tools.get_config", return_value={"configurable": {"thread_id": "gc-tid"}}):
            runtime = SimpleNamespace(context={}, config={})
            assert self._call(runtime) == "gc-tid"

    def test_runtime_config_none_falls_to_get_config(self):
        with patch("ideer.mcp.tools.get_config", return_value={"configurable": {"thread_id": "gc2"}}):
            runtime = SimpleNamespace(context={}, config=None)
            assert self._call(runtime) == "gc2"

    def test_runtime_none_uses_get_config(self):
        with patch("ideer.mcp.tools.get_config", return_value={"configurable": {"thread_id": "langgraph-tid"}}):
            assert self._call(None) == "langgraph-tid"

    def test_runtime_none_get_config_no_thread_id_returns_default(self):
        with patch("ideer.mcp.tools.get_config", return_value={}):
            assert self._call(None) == "default"

    def test_runtime_none_get_config_configurable_no_thread_id(self):
        with patch("ideer.mcp.tools.get_config", return_value={"configurable": {}}):
            assert self._call(None) == "default"

    def test_runtime_none_get_config_runtime_error_returns_default(self):
        with patch("ideer.mcp.tools.get_config", side_effect=RuntimeError("no config")):
            assert self._call(None) == "default"

    def test_runtime_config_empty_configurable(self):
        """config has 'configurable' but no 'thread_id' -> falls to get_config."""
        with patch("ideer.mcp.tools.get_config", return_value={"configurable": {"thread_id": "fallback"}}):
            runtime = SimpleNamespace(context={}, config={"configurable": {}})
            assert self._call(runtime) == "fallback"


# ---------------------------------------------------------------------------
# _convert_call_tool_result
# ---------------------------------------------------------------------------


class TestConvertCallToolResult:
    """Tests for _convert_call_tool_result."""

    def _call(self, result):
        from ideer.mcp.tools import _convert_call_tool_result

        return _convert_call_tool_result(result)

    def test_tool_message_passthrough(self):
        from langchain_core.messages import ToolMessage

        msg = ToolMessage(content="ok", tool_call_id="tc1")
        content, artifact = self._call(msg)
        assert content is msg
        assert artifact is None

    def test_langgraph_command_passthrough(self):
        """When langgraph.types.Command is available and result is a Command, pass through."""
        from unittest.mock import MagicMock as _MagicMock

        cmd = _MagicMock()
        # Make isinstance check work by patching the import
        with patch.dict("sys.modules", {"langgraph.types": SimpleNamespace(Command=type(cmd))}):
            # Re-import to pick up the patched Command type
            import importlib

            import ideer.mcp.tools as mod

            importlib.reload(mod)
            content, artifact = mod._convert_call_tool_result(cmd)
            assert content is cmd
            assert artifact is None
        # Reload again to restore normal state
        import importlib

        importlib.reload(mod)

    def test_langgraph_import_error_continues(self):
        """If langgraph.types import fails, conversion continues with MCP content blocks."""
        from mcp.types import CallToolResult, TextContent

        result = CallToolResult(
            content=[TextContent(type="text", text="hello")],
            isError=False,
        )
        with patch.dict("sys.modules", {"langgraph.types": None}):
            content, artifact = self._call(result)
        assert isinstance(content, list)
        assert len(content) == 1

    def test_text_content(self):
        from mcp.types import CallToolResult, TextContent

        result = CallToolResult(
            content=[TextContent(type="text", text="hello world")],
            isError=False,
        )
        content, artifact = self._call(result)
        assert len(content) == 1
        assert content[0]["type"] == "text"
        assert content[0]["text"] == "hello world"
        assert artifact is None

    def test_image_content(self):
        from mcp.types import CallToolResult, ImageContent

        result = CallToolResult(
            content=[ImageContent(type="image", data="base64data", mimeType="image/png")],
            isError=False,
        )
        content, artifact = self._call(result)
        assert len(content) == 1
        assert content[0]["type"] == "image"

    def test_resource_link_image(self):
        from mcp.types import CallToolResult, ResourceLink

        result = CallToolResult(
            content=[ResourceLink(type="resource_link", name="img", uri="https://example.com/img.png", mimeType="image/png")],
            isError=False,
        )
        content, artifact = self._call(result)
        assert len(content) == 1
        assert content[0]["type"] == "image"

    def test_resource_link_non_image(self):
        from mcp.types import CallToolResult, ResourceLink

        result = CallToolResult(
            content=[ResourceLink(type="resource_link", name="doc", uri="https://example.com/doc.pdf", mimeType="application/pdf")],
            isError=False,
        )
        content, artifact = self._call(result)
        assert len(content) == 1
        assert content[0]["type"] == "file"

    def test_resource_link_no_mime(self):
        from mcp.types import CallToolResult, ResourceLink

        result = CallToolResult(
            content=[ResourceLink(type="resource_link", name="data", uri="https://example.com/data")],
            isError=False,
        )
        content, artifact = self._call(result)
        assert len(content) == 1
        # None mimeType -> falls to file block
        assert content[0]["type"] == "file"

    def test_embedded_resource_text(self):
        from mcp.types import CallToolResult, EmbeddedResource, TextResourceContents

        result = CallToolResult(
            content=[
                EmbeddedResource(
                    type="resource",
                    resource=TextResourceContents(uri="file:///t.txt", text="embedded text", mimeType="text/plain"),
                )
            ],
            isError=False,
        )
        content, artifact = self._call(result)
        assert len(content) == 1
        assert content[0]["type"] == "text"
        assert content[0]["text"] == "embedded text"

    def test_embedded_resource_blob_image(self):
        from mcp.types import BlobResourceContents, CallToolResult, EmbeddedResource

        result = CallToolResult(
            content=[
                EmbeddedResource(
                    type="resource",
                    resource=BlobResourceContents(uri="file:///img.png", blob="base64img", mimeType="image/png"),
                )
            ],
            isError=False,
        )
        content, artifact = self._call(result)
        assert len(content) == 1
        assert content[0]["type"] == "image"

    def test_embedded_resource_blob_non_image(self):
        from mcp.types import BlobResourceContents, CallToolResult, EmbeddedResource

        result = CallToolResult(
            content=[
                EmbeddedResource(
                    type="resource",
                    resource=BlobResourceContents(uri="file:///f.bin", blob="base64bin", mimeType="application/octet-stream"),
                )
            ],
            isError=False,
        )
        content, artifact = self._call(result)
        assert len(content) == 1
        assert content[0]["type"] == "file"

    def test_embedded_resource_blob_non_image_mime(self):
        """BlobResourceContents with non-image mimeType -> file block."""
        from mcp.types import BlobResourceContents, CallToolResult, EmbeddedResource

        result = CallToolResult(
            content=[
                EmbeddedResource(
                    type="resource",
                    resource=BlobResourceContents(uri="file:///x", blob="data", mimeType="application/pdf"),
                )
            ],
            isError=False,
        )
        content, artifact = self._call(result)
        assert len(content) == 1
        assert content[0]["type"] == "file"

    def test_embedded_resource_other_type(self):
        """EmbeddedResource with resource that is neither Text nor Blob -> str(res)."""
        from mcp.types import EmbeddedResource

        # Build a mock EmbeddedResource whose resource is neither TextResourceContents
        # nor BlobResourceContents, to exercise the else branch (line 91).
        fake_resource = MagicMock(spec=[])  # empty spec so isinstance checks fail
        embedded = MagicMock(spec=EmbeddedResource)
        embedded.resource = fake_resource
        embedded.__class__ = EmbeddedResource  # for isinstance(item, EmbeddedResource)

        # Build a mock CallToolResult
        result = MagicMock()
        result.content = [embedded]
        result.isError = False
        result.structuredContent = None

        content, artifact = self._call(result)
        assert len(content) == 1
        assert content[0]["type"] == "text"

    def test_unknown_content_type(self):
        """Content block that is not a known MCP type -> str(item)."""

        # Build an unknown content item that is not any of the known MCP types
        unknown = MagicMock()
        # Ensure isinstance checks fail for all known types
        unknown.__class__ = type("UnknownContent", (), {})

        result = MagicMock()
        result.content = [unknown]
        result.isError = False
        result.structuredContent = None

        content, artifact = self._call(result)
        assert len(content) == 1
        assert content[0]["type"] == "text"

    def test_is_error_raises_tool_exception(self):
        from langchain_core.tools import ToolException
        from mcp.types import CallToolResult, TextContent

        result = CallToolResult(
            content=[TextContent(type="text", text="something failed")],
            isError=True,
        )
        with pytest.raises(ToolException, match="something failed"):
            self._call(result)

    def test_is_error_no_text_items_raises_with_str(self):
        """isError=True but no text content items -> ToolException with str(lc_content)."""
        from langchain_core.tools import ToolException
        from mcp.types import CallToolResult, ImageContent

        result = CallToolResult(
            content=[ImageContent(type="image", data="img", mimeType="image/png")],
            isError=True,
        )
        with pytest.raises(ToolException):
            self._call(result)

    def test_structured_content_produces_artifact(self):
        from mcp.types import CallToolResult, TextContent

        result = CallToolResult(
            content=[TextContent(type="text", text="ok")],
            isError=False,
            structuredContent={"key": "value"},
        )
        content, artifact = self._call(result)
        assert artifact == {"structured_content": {"key": "value"}}

    def test_structured_content_none_artifact_is_none(self):
        from mcp.types import CallToolResult, TextContent

        result = CallToolResult(
            content=[TextContent(type="text", text="ok")],
            isError=False,
            structuredContent=None,
        )
        _, artifact = self._call(result)
        assert artifact is None

    def test_multiple_content_blocks(self):
        from mcp.types import CallToolResult, ImageContent, TextContent

        result = CallToolResult(
            content=[
                TextContent(type="text", text="first"),
                ImageContent(type="image", data="img", mimeType="image/jpeg"),
                TextContent(type="text", text="third"),
            ],
            isError=False,
        )
        content, artifact = self._call(result)
        assert len(content) == 3

    def test_empty_content_list(self):
        from mcp.types import CallToolResult

        result = CallToolResult(content=[], isError=False)
        content, artifact = self._call(result)
        assert content == []
        assert artifact is None


# ---------------------------------------------------------------------------
# _make_session_pool_tool
# ---------------------------------------------------------------------------


class TestMakeSessionPoolTool:
    """Tests for _make_session_pool_tool."""

    def _make_mock_tool(self, name="server1_toolA", description="desc", args_schema=None):
        tool = MagicMock()
        tool.name = name
        tool.description = description
        tool.args_schema = args_schema
        tool.metadata = {"meta": "data"}
        return tool

    def test_strips_server_prefix(self):
        from ideer.mcp.tools import _make_session_pool_tool

        mock_tool = self._make_mock_tool(name="srv_myTool")
        pool = MagicMock()
        with patch("ideer.mcp.tools.get_session_pool", return_value=pool):
            result = _make_session_pool_tool(mock_tool, "srv", {"transport": "stdio"})

        assert result.name == "srv_myTool"
        assert result.description == "desc"

    def test_no_prefix_match_keeps_original_name(self):
        from ideer.mcp.tools import _make_session_pool_tool

        mock_tool = self._make_mock_tool(name="otherPrefix_tool")
        pool = MagicMock()
        with patch("ideer.mcp.tools.get_session_pool", return_value=pool):
            result = _make_session_pool_tool(mock_tool, "server1", {"transport": "stdio"})

        assert result.name == "otherPrefix_tool"

    def test_returns_structured_tool(self):
        from langchain_core.tools import StructuredTool

        from ideer.mcp.tools import _make_session_pool_tool

        mock_tool = self._make_mock_tool()
        pool = MagicMock()
        with patch("ideer.mcp.tools.get_session_pool", return_value=pool):
            result = _make_session_pool_tool(mock_tool, "server1", {"transport": "stdio"})

        assert isinstance(result, StructuredTool)
        assert result.response_format == "content_and_artifact"
        assert result.metadata == {"meta": "data"}

    def test_call_without_interceptors(self):
        """call_with_persistent_session delegates to session.call_tool when no interceptors."""
        from ideer.mcp.tools import _make_session_pool_tool

        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=MagicMock(content=[], isError=False, structuredContent=None))

        pool = AsyncMock()
        pool.get_session = AsyncMock(return_value=mock_session)

        mock_tool = self._make_mock_tool(name="srv_tool1")
        with (
            patch("ideer.mcp.tools.get_session_pool", return_value=pool),
            patch("ideer.mcp.tools._extract_thread_id", return_value="t1"),
            patch("ideer.mcp.tools._convert_call_tool_result", return_value=("converted", None)),
        ):
            wrapped = _make_session_pool_tool(mock_tool, "srv", {"transport": "stdio"}, tool_interceptors=None)
            result = asyncio.run(wrapped.coroutine(runtime=None, arg1="val1"))

        pool.get_session.assert_awaited_once_with("srv", "t1", {"transport": "stdio"})
        mock_session.call_tool.assert_awaited_once_with("tool1", {"arg1": "val1"})
        assert result == ("converted", None)

    def test_call_with_interceptors(self):
        """call_with_persistent_session chains interceptors before session.call_tool."""
        from ideer.mcp.tools import _make_session_pool_tool

        mock_session = AsyncMock()
        call_result = MagicMock(content=[], isError=False, structuredContent=None)
        mock_session.call_tool = AsyncMock(return_value=call_result)

        pool = AsyncMock()
        pool.get_session = AsyncMock(return_value=mock_session)

        interceptor_called = []

        async def my_interceptor(request, handler):
            interceptor_called.append(request)
            return await handler(request)

        mock_tool = self._make_mock_tool(name="srv_toolX")
        with (
            patch("ideer.mcp.tools.get_session_pool", return_value=pool),
            patch("ideer.mcp.tools._extract_thread_id", return_value="t2"),
            patch("ideer.mcp.tools._convert_call_tool_result", return_value=("ok", None)),
        ):
            wrapped = _make_session_pool_tool(mock_tool, "srv", {"transport": "stdio"}, tool_interceptors=[my_interceptor])
            result = asyncio.run(wrapped.coroutine(runtime=None))

        assert len(interceptor_called) == 1
        assert result == ("ok", None)

    def test_call_with_multiple_interceptors(self):
        """Multiple interceptors are chained in order (reversed for wrapping)."""
        from ideer.mcp.tools import _make_session_pool_tool

        mock_session = AsyncMock()
        call_result = MagicMock(content=[], isError=False, structuredContent=None)
        mock_session.call_tool = AsyncMock(return_value=call_result)

        pool = AsyncMock()
        pool.get_session = AsyncMock(return_value=mock_session)

        order = []

        async def interceptor_a(request, handler):
            order.append("a")
            return await handler(request)

        async def interceptor_b(request, handler):
            order.append("b")
            return await handler(request)

        mock_tool = self._make_mock_tool(name="srv_toolY")
        with (
            patch("ideer.mcp.tools.get_session_pool", return_value=pool),
            patch("ideer.mcp.tools._extract_thread_id", return_value="t3"),
            patch("ideer.mcp.tools._convert_call_tool_result", return_value=("ok", None)),
        ):
            wrapped = _make_session_pool_tool(mock_tool, "srv", {"transport": "stdio"}, tool_interceptors=[interceptor_a, interceptor_b])
            result = asyncio.run(wrapped.coroutine(runtime=None))

        # interceptors are reversed for wrapping, so execution order is a -> b
        assert order == ["a", "b"]
        assert result == ("ok", None)


# ---------------------------------------------------------------------------
# get_mcp_tools
# ---------------------------------------------------------------------------


class TestGetMcpTools:
    """Tests for get_mcp_tools."""

    def _base_patches(
        self,
        *,
        servers_config=None,
        oauth_headers=None,
        oauth_interceptor=None,
        model_extra=None,
    ):
        """Return a dict of common patch context managers."""
        if servers_config is None:
            servers_config = {}
        if oauth_headers is None:
            oauth_headers = {}
        if model_extra is None:
            model_extra = {}

        mock_ext_config = MagicMock()
        mock_ext_config.model_extra = model_extra

        return {
            "from_file": patch(
                "ideer.config.extensions_config.ExtensionsConfig.from_file",
                return_value=mock_ext_config,
            ),
            "build_servers": patch(
                "ideer.mcp.tools.build_servers_config",
                return_value=servers_config,
            ),
            "oauth_headers": patch(
                "ideer.mcp.tools.get_initial_oauth_headers",
                new_callable=AsyncMock,
                return_value=oauth_headers,
            ),
            "oauth_interceptor": patch(
                "ideer.mcp.tools.build_oauth_tool_interceptor",
                return_value=oauth_interceptor,
            ),
        }

    def test_import_error_returns_empty(self):
        """If langchain_mcp_adapters is not importable, returns []."""
        import importlib

        import ideer.mcp.tools as mod

        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def fake_import(name, *args, **kwargs):
            if name == "langchain_mcp_adapters.client":
                raise ImportError("no such module")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            importlib.reload(mod)
            result = asyncio.run(mod.get_mcp_tools())

        # Reload to restore normal state
        importlib.reload(mod)
        assert result == []

    def test_empty_servers_config_returns_empty(self):
        p = self._base_patches(servers_config={})
        with (
            p["from_file"],
            p["build_servers"],
            p["oauth_headers"],
            p["oauth_interceptor"],
        ):
            from ideer.mcp.tools import get_mcp_tools

            result = asyncio.run(get_mcp_tools())
        assert result == []

    def test_oauth_headers_injected_for_sse_server(self):
        """OAuth Authorization header is injected into sse/http server configs."""
        servers_config = {
            "sse-srv": {"transport": "sse", "headers": {}},
        }
        p = self._base_patches(
            servers_config=servers_config,
            oauth_headers={"sse-srv": "Bearer token123"},
        )
        mock_client = MagicMock()
        mock_client.get_tools = AsyncMock(return_value=[])

        with (
            p["from_file"],
            p["build_servers"],
            p["oauth_headers"],
            p["oauth_interceptor"],
            patch("langchain_mcp_adapters.client.MultiServerMCPClient", return_value=mock_client),
        ):
            from ideer.mcp.tools import get_mcp_tools

            asyncio.run(get_mcp_tools())

        assert servers_config["sse-srv"]["headers"]["Authorization"] == "Bearer token123"

    def test_oauth_headers_not_injected_for_stdio(self):
        """OAuth headers are not injected into stdio server configs."""
        servers_config = {
            "stdio-srv": {"transport": "stdio", "command": "node"},
        }
        p = self._base_patches(
            servers_config=servers_config,
            oauth_headers={"stdio-srv": "Bearer tok"},
        )
        mock_client = MagicMock()
        mock_client.get_tools = AsyncMock(return_value=[])

        with (
            p["from_file"],
            p["build_servers"],
            p["oauth_headers"],
            p["oauth_interceptor"],
            patch("langchain_mcp_adapters.client.MultiServerMCPClient", return_value=mock_client),
        ):
            from ideer.mcp.tools import get_mcp_tools

            asyncio.run(get_mcp_tools())

        # stdio-srv should NOT have Authorization header injected
        assert "Authorization" not in servers_config["stdio-srv"]

    def test_oauth_headers_unknown_server_skipped(self):
        """OAuth headers for a server not in servers_config are ignored."""
        servers_config = {"real-srv": {"transport": "http", "url": "http://x"}}
        p = self._base_patches(
            servers_config=servers_config,
            oauth_headers={"unknown-srv": "Bearer x"},
        )
        mock_client = MagicMock()
        mock_client.get_tools = AsyncMock(return_value=[])

        with (
            p["from_file"],
            p["build_servers"],
            p["oauth_headers"],
            p["oauth_interceptor"],
            patch("langchain_mcp_adapters.client.MultiServerMCPClient", return_value=mock_client),
        ):
            from ideer.mcp.tools import get_mcp_tools

            asyncio.run(get_mcp_tools())

        assert "Authorization" not in servers_config["real-srv"].get("headers", {})

    def test_oauth_interceptor_added_to_tool_interceptors(self):
        """When build_oauth_tool_interceptor returns a function, it is included."""
        oauth_fn = AsyncMock()
        servers_config = {"s1": {"transport": "stdio", "command": "x"}}
        p = self._base_patches(servers_config=servers_config, oauth_interceptor=oauth_fn)
        mock_client = MagicMock()
        mock_client.get_tools = AsyncMock(return_value=[])

        with (
            p["from_file"],
            p["build_servers"],
            p["oauth_headers"],
            patch("ideer.mcp.tools.build_oauth_tool_interceptor", return_value=oauth_fn),
            patch("langchain_mcp_adapters.client.MultiServerMCPClient", return_value=mock_client) as mock_cls,
        ):
            from ideer.mcp.tools import get_mcp_tools

            asyncio.run(get_mcp_tools())

        interceptors = mock_cls.call_args.kwargs.get("tool_interceptors") or mock_cls.call_args[1].get("tool_interceptors", [])
        assert oauth_fn in interceptors

    def test_stdio_tool_wrapped_with_session_pool(self):
        """Tools from stdio servers are wrapped via _make_session_pool_tool."""
        mock_tool = MagicMock()
        mock_tool.name = "s1_myTool"
        mock_tool.description = "d"
        mock_tool.args_schema = None
        mock_tool.metadata = {}

        mock_client = MagicMock()
        mock_client.get_tools = AsyncMock(return_value=[mock_tool])

        servers_config = {"s1": {"transport": "stdio", "command": "node"}}
        p = self._base_patches(servers_config=servers_config)

        with (
            p["from_file"],
            p["build_servers"],
            p["oauth_headers"],
            p["oauth_interceptor"],
            patch("langchain_mcp_adapters.client.MultiServerMCPClient", return_value=mock_client),
            patch("ideer.mcp.tools._make_session_pool_tool") as mock_wrap,
        ):
            mock_wrap.return_value = MagicMock(name="wrapped_tool")
            from ideer.mcp.tools import get_mcp_tools

            result = asyncio.run(get_mcp_tools())

        mock_wrap.assert_called_once()
        assert len(result) == 1

    def test_non_stdio_tool_not_wrapped(self):
        """Tools from http/sse servers are returned without session-pool wrapping."""
        mock_tool = MagicMock()
        mock_tool.name = "s2_httpTool"
        mock_tool.description = "d"
        mock_tool.args_schema = None
        mock_tool.metadata = {}

        mock_client = MagicMock()
        mock_client.get_tools = AsyncMock(return_value=[mock_tool])

        servers_config = {"s2": {"transport": "http", "url": "http://x"}}
        p = self._base_patches(servers_config=servers_config)

        with (
            p["from_file"],
            p["build_servers"],
            p["oauth_headers"],
            p["oauth_interceptor"],
            patch("langchain_mcp_adapters.client.MultiServerMCPClient", return_value=mock_client),
            patch("ideer.mcp.tools._make_session_pool_tool") as mock_wrap,
        ):
            from ideer.mcp.tools import get_mcp_tools

            result = asyncio.run(get_mcp_tools())

        mock_wrap.assert_not_called()
        assert len(result) == 1
        assert result[0] is mock_tool

    def test_tool_with_no_matching_server_returned_as_is(self):
        """A tool whose name does not match any server prefix is returned as-is."""
        mock_tool = MagicMock()
        mock_tool.name = "orphan_tool"
        mock_tool.description = "d"
        mock_tool.args_schema = None
        mock_tool.metadata = {}

        mock_client = MagicMock()
        mock_client.get_tools = AsyncMock(return_value=[mock_tool])

        servers_config = {"s1": {"transport": "stdio", "command": "x"}}
        p = self._base_patches(servers_config=servers_config)

        with (
            p["from_file"],
            p["build_servers"],
            p["oauth_headers"],
            p["oauth_interceptor"],
            patch("langchain_mcp_adapters.client.MultiServerMCPClient", return_value=mock_client),
        ):
            from ideer.mcp.tools import get_mcp_tools

            result = asyncio.run(get_mcp_tools())

        assert len(result) == 1
        assert result[0] is mock_tool

    def test_sse_tool_returned_as_is(self):
        """SSE transport tools are returned directly (no session-pool wrap)."""
        mock_tool = MagicMock()
        mock_tool.name = "s1_sseTool"
        mock_tool.description = "d"
        mock_tool.args_schema = None
        mock_tool.metadata = {}

        mock_client = MagicMock()
        mock_client.get_tools = AsyncMock(return_value=[mock_tool])

        servers_config = {"s1": {"transport": "sse", "url": "http://x"}}
        p = self._base_patches(servers_config=servers_config)

        with (
            p["from_file"],
            p["build_servers"],
            p["oauth_headers"],
            p["oauth_interceptor"],
            patch("langchain_mcp_adapters.client.MultiServerMCPClient", return_value=mock_client),
        ):
            from ideer.mcp.tools import get_mcp_tools

            result = asyncio.run(get_mcp_tools())

        assert len(result) == 1
        assert result[0] is mock_tool

    def test_sync_wrapper_patched_for_async_only_tools(self):
        """Tools without .func get a sync wrapper via make_sync_tool_wrapper."""
        mock_tool = MagicMock()
        mock_tool.name = "s1_syncTool"
        mock_tool.description = "d"
        mock_tool.args_schema = None
        mock_tool.metadata = {}
        mock_tool.func = None
        mock_tool.coroutine = AsyncMock()

        mock_client = MagicMock()
        mock_client.get_tools = AsyncMock(return_value=[mock_tool])

        servers_config = {"s1": {"transport": "stdio", "command": "x"}}
        p = self._base_patches(servers_config=servers_config)

        with (
            p["from_file"],
            p["build_servers"],
            p["oauth_headers"],
            p["oauth_interceptor"],
            patch("langchain_mcp_adapters.client.MultiServerMCPClient", return_value=mock_client),
            patch("ideer.mcp.tools._make_session_pool_tool", return_value=mock_tool),
            patch("ideer.mcp.tools.make_sync_tool_wrapper", return_value=lambda: "sync") as mock_sync,
        ):
            from ideer.mcp.tools import get_mcp_tools

            asyncio.run(get_mcp_tools())

        mock_sync.assert_called_once_with(mock_tool.coroutine, "s1_syncTool")
        assert mock_tool.func is not None

    def test_sync_wrapper_not_patched_when_func_exists(self):
        """Tools that already have .func are not patched with a sync wrapper."""
        mock_tool = MagicMock()
        mock_tool.name = "s1_hasFunc"
        mock_tool.description = "d"
        mock_tool.args_schema = None
        mock_tool.metadata = {}
        mock_tool.func = lambda: "existing"
        mock_tool.coroutine = AsyncMock()

        mock_client = MagicMock()
        mock_client.get_tools = AsyncMock(return_value=[mock_tool])

        servers_config = {"s1": {"transport": "stdio", "command": "x"}}
        p = self._base_patches(servers_config=servers_config)

        with (
            p["from_file"],
            p["build_servers"],
            p["oauth_headers"],
            p["oauth_interceptor"],
            patch("langchain_mcp_adapters.client.MultiServerMCPClient", return_value=mock_client),
            patch("ideer.mcp.tools._make_session_pool_tool", return_value=mock_tool),
            patch("ideer.mcp.tools.make_sync_tool_wrapper") as mock_sync,
        ):
            from ideer.mcp.tools import get_mcp_tools

            asyncio.run(get_mcp_tools())

        mock_sync.assert_not_called()

    def test_exception_in_client_returns_empty(self):
        """If MultiServerMCPClient raises, get_mcp_tools returns []."""
        p = self._base_patches(servers_config={"s1": {"transport": "stdio"}})

        with (
            p["from_file"],
            p["build_servers"],
            p["oauth_headers"],
            p["oauth_interceptor"],
            patch("langchain_mcp_adapters.client.MultiServerMCPClient", side_effect=RuntimeError("boom")),
        ):
            from ideer.mcp.tools import get_mcp_tools

            result = asyncio.run(get_mcp_tools())

        assert result == []

    def test_exception_in_get_tools_returns_empty(self):
        """If client.get_tools() raises, get_mcp_tools returns []."""
        mock_client = MagicMock()
        mock_client.get_tools = AsyncMock(side_effect=Exception("discovery failed"))

        p = self._base_patches(servers_config={"s1": {"transport": "stdio", "command": "x"}})

        with (
            p["from_file"],
            p["build_servers"],
            p["oauth_headers"],
            p["oauth_interceptor"],
            patch("langchain_mcp_adapters.client.MultiServerMCPClient", return_value=mock_client),
        ):
            from ideer.mcp.tools import get_mcp_tools

            result = asyncio.run(get_mcp_tools())

        assert result == []

    def test_full_flow_stdio_and_http_tools(self):
        """Full integration: mix of stdio and http tools, wrapping only stdio."""
        stdio_tool = MagicMock()
        stdio_tool.name = "srv1_toolA"
        stdio_tool.description = "A"
        stdio_tool.args_schema = None
        stdio_tool.metadata = {}

        http_tool = MagicMock()
        http_tool.name = "srv2_toolB"
        http_tool.description = "B"
        http_tool.args_schema = None
        http_tool.metadata = {}

        mock_client = MagicMock()
        mock_client.get_tools = AsyncMock(return_value=[stdio_tool, http_tool])

        servers_config = {
            "srv1": {"transport": "stdio", "command": "node"},
            "srv2": {"transport": "http", "url": "http://x"},
        }
        p = self._base_patches(servers_config=servers_config)

        wrapped_stdio = MagicMock(name="wrapped_stdio")
        wrapped_stdio.func = None
        wrapped_stdio.coroutine = AsyncMock()

        with (
            p["from_file"],
            p["build_servers"],
            p["oauth_headers"],
            p["oauth_interceptor"],
            patch("langchain_mcp_adapters.client.MultiServerMCPClient", return_value=mock_client),
            patch("ideer.mcp.tools._make_session_pool_tool", return_value=wrapped_stdio) as mock_wrap,
            patch("ideer.mcp.tools.make_sync_tool_wrapper", return_value=lambda: "sync"),
        ):
            from ideer.mcp.tools import get_mcp_tools

            result = asyncio.run(get_mcp_tools())

        # Only the stdio tool should be wrapped
        mock_wrap.assert_called_once()
        assert len(result) == 2
        assert result[0] is wrapped_stdio
        assert result[1] is http_tool
