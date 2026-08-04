"""Restrict workflow subagent filesystem tools to declared roots."""

from __future__ import annotations

import posixpath
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

_READ_TOOLS = {"read_file", "ls", "glob", "grep", "view_image"}
_WRITE_TOOLS = {"write_file", "str_replace"}


class FilesystemScopeMiddleware(AgentMiddleware[AgentState]):
    """Block governed file tool calls outside a node's declared roots."""

    def __init__(self, *, read_roots: list[str], write_roots: list[str]) -> None:
        self.read_roots = tuple(_validate_absolute_path(root) for root in read_roots)
        self.write_roots = tuple(_validate_absolute_path(root) for root in write_roots)

    def _blocked_message(self, request: ToolCallRequest) -> ToolMessage | None:
        name = str(request.tool_call.get("name") or "")
        if name not in _READ_TOOLS | _WRITE_TOOLS:
            return None
        args = request.tool_call.get("args") or {}
        path_key = "image_path" if name == "view_image" else "path"
        raw_path = args.get(path_key) if isinstance(args, dict) else None
        try:
            path = _validate_absolute_path(raw_path)
            roots = self.read_roots if name in _READ_TOOLS else self.write_roots
            if not any(_is_within(path, root) for root in roots):
                raise ValueError(f"path '{path}' is outside declared {('read' if name in _READ_TOOLS else 'write')} roots")
        except (TypeError, ValueError) as exc:
            return ToolMessage(
                content=f"Error: Tool '{name}' denied by workflow file_access: {exc}",
                tool_call_id=str(request.tool_call.get("id") or "missing_tool_call_id"),
                name=name,
                status="error",
            )
        return None

    @override
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        blocked = self._blocked_message(request)
        return blocked if blocked is not None else handler(request)

    @override
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        blocked = self._blocked_message(request)
        return blocked if blocked is not None else await handler(request)


def _validate_absolute_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError("an absolute path is required")
    if "\\" in value:
        raise ValueError("backslash path traversal is not allowed")
    if not value.startswith("/"):
        raise ValueError("an absolute path is required")
    if ".." in value.split("/"):
        raise ValueError("path traversal is not allowed")
    return posixpath.normpath(value)


def _is_within(path: str, root: str) -> bool:
    return posixpath.commonpath((path, root)) == root
