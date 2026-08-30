"""Transport-independent MCP connector seam."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from langchain_core.tools import BaseTool


class ConnectorBackend(Protocol):
    async def tools(self) -> list[BaseTool]: ...


class McpConnector:
    """Hide MCP discovery and invocation behind one async interface."""

    def __init__(self, backend: ConnectorBackend | None = None) -> None:
        self._backend = backend
        self._tools: dict[str, BaseTool] | None = None

    async def tools(self) -> list[BaseTool]:
        if self._tools is None:
            if self._backend is None:
                from ideer.mcp.tools import get_mcp_tools

                loaded = await get_mcp_tools()
            else:
                loaded = await self._backend.tools()
            self._tools = {tool.name: tool for tool in loaded}
        return list(self._tools.values())

    async def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> Any:
        if self._tools is None:
            await self.tools()
        tool = (self._tools or {}).get(name)
        if tool is None:
            raise KeyError(f"Unknown MCP tool: {name}")
        return await tool.ainvoke(dict(arguments or {}))


__all__ = ["ConnectorBackend", "McpConnector"]
