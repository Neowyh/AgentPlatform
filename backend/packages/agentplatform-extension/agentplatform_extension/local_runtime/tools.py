"""Tool descriptors and assembly-time filtering for local capabilities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .authorization import LocalAuthorization


@dataclass(frozen=True)
class LocalTool:
    name: str
    description: str


LOCAL_TOOLS = (
    LocalTool("local.files.list", "List files under an explicitly allowed local root."),
    LocalTool("local.files.read", "Read a file under an explicitly allowed local root."),
    LocalTool("local.files.write", "Write a file after local consent."),
    LocalTool("local.python", "Run a Python task under an allowed local root."),
)


def assemble_local_tools(authorization: LocalAuthorization) -> tuple[LocalTool, ...]:
    return tuple(tool for tool in LOCAL_TOOLS if authorization.allows(tool.name))


def filter_local_tools(tools: tuple[LocalTool, ...], authorization: LocalAuthorization) -> tuple[LocalTool, ...]:
    """Apply local capability visibility while retaining ordinary server tools."""
    effective = authorization.effective
    return tuple(tool for tool in tools if not tool.name.startswith("local.") or tool.name in effective)


def local_tool_names(authorization: LocalAuthorization) -> frozenset[str]:
    """Return the only local names eligible for model assembly."""
    return frozenset(tool.name for tool in assemble_local_tools(authorization))


class LocalToolExecutor:
    """Execute a model-visible logical tool through a frozen run route."""

    def __init__(
        self,
        authorization: LocalAuthorization,
        route: Any,
        sender: Callable[[str, str, Mapping[str, Any]], Awaitable[Any]],
        *,
        receipt_sink: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> None:
        self.authorization = authorization
        self.route = route
        self.sender = sender
        self.receipt_sink = receipt_sink

    async def invoke(self, capability: str, payload: Mapping[str, Any]) -> Any:
        if capability not in {tool.name for tool in LOCAL_TOOLS}:
            raise ValueError(f"unknown local capability: {capability}")
        if not self.authorization.allows(capability):
            raise PermissionError(f"local capability is unavailable: {capability}")
        result = await self.route.dispatch(capability, payload, self.sender)
        receipt = getattr(result, "receipt", None)
        if receipt is not None and self.receipt_sink is not None:
            self.receipt_sink(receipt)
        return result
