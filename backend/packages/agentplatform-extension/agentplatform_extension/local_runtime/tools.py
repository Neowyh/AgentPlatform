"""Tool descriptors and assembly-time filtering for local capabilities."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .authorization import LocalAuthorization

MCP_CAPABILITY_PREFIX = "local.mcp."
_MCP_SERVER_PATTERN = re.compile(r"[A-Za-z0-9_-]+\Z")


@dataclass(frozen=True)
class LocalTool:
    name: str
    description: str
    input_schema: dict[str, Any] | None = None


def _split_mcp_capability(name: str) -> tuple[str, str] | None:
    """Return ``(server, tool)`` for a well-formed projection name, else None."""
    if not isinstance(name, str) or not name.startswith(MCP_CAPABILITY_PREFIX):
        return None
    server, separator, tool = name[len(MCP_CAPABILITY_PREFIX) :].partition(".")
    if not separator or not server or not tool:
        return None
    if _MCP_SERVER_PATTERN.match(server) is None or any(
        character.isspace() for character in tool
    ):
        return None
    return server, tool


def is_local_mcp_capability(name: str) -> bool:
    """True for well-formed ``local.mcp.<server>.<tool>`` projection names."""
    return _split_mcp_capability(name) is not None


def _mcp_tool(name: str, input_schema: dict[str, Any] | None = None) -> LocalTool:
    server, tool = _split_mcp_capability(name) or ("", "")
    return LocalTool(
        name, f"Call the {tool} tool on the local MCP server {server}.", input_schema
    )


class LocalToolContributor:
    """Generic extension contribution consumed before host tool assembly."""

    def __init__(self, authorization: LocalAuthorization) -> None:
        self.authorization = authorization

    def contribute_tools(self, context: Mapping[str, Any]) -> tuple[LocalTool, ...]:
        descriptors = context.get("local_tool_descriptors", {})
        return assemble_local_tools(self.authorization, descriptors=descriptors)


LOCAL_TOOLS = (
    LocalTool("local.files.list", "List files under an explicitly allowed local root."),
    LocalTool(
        "local.files.read", "Read a file under an explicitly allowed local root."
    ),
    LocalTool("local.files.write", "Write a file after local consent."),
    LocalTool("local.python", "Run a Python task under an allowed local root."),
)


def assemble_local_tools(
    authorization: LocalAuthorization,
    *,
    descriptors: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[LocalTool, ...]:
    """Static capabilities plus the device's projected MCP tools.

    A ``local.mcp.<server>.<tool>`` name can only appear here when the device
    announced it (device_capabilities) and every other authorization factor
    allows it, because the projection is drawn from the effective intersection.
    """
    static = tuple(tool for tool in LOCAL_TOOLS if authorization.allows(tool.name))
    projected = tuple(
        _mcp_tool(
            name,
            dict(descriptors[name].get("input_schema", {}))
            if descriptors and name in descriptors
            else None,
        )
        for name in sorted(authorization.effective)
        if is_local_mcp_capability(name)
    )
    return static + projected


def filter_local_tools(
    tools: tuple[LocalTool, ...], authorization: LocalAuthorization
) -> tuple[LocalTool, ...]:
    """Apply local capability visibility while retaining ordinary server tools."""
    effective = authorization.effective
    return tuple(
        tool
        for tool in tools
        if not tool.name.startswith("local.") or tool.name in effective
    )


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
        if hasattr(route, "revalidate"):
            route.revalidate(authorization)

    async def invoke(self, capability: str, payload: Mapping[str, Any]) -> Any:
        if capability not in {
            tool.name for tool in LOCAL_TOOLS
        } and not is_local_mcp_capability(capability):
            raise ValueError(f"unknown local capability: {capability}")
        if not self.authorization.allows(capability):
            raise PermissionError(f"local capability is unavailable: {capability}")
        result = await self.route.dispatch(capability, payload, self.sender)
        receipt = getattr(result, "receipt", None)
        if receipt is not None:
            if self.receipt_sink is not None:
                self.receipt_sink(receipt)
            else:
                from agentplatform_extension.evidence import (
                    record_local_execution_receipt,
                )

                record_local_execution_receipt(
                    receipt, tool_call_id=str(payload.get("tool_call_id", "")) or None
                )
        return result


def build_langchain_local_tools(
    authorization: LocalAuthorization,
    executor: LocalToolExecutor,
    *,
    descriptors: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[Any, ...]:
    """Adapt authorized local descriptors to executable LangChain tools.

    The capability name is closed over in each coroutine, so it never becomes
    a model supplied routing parameter.  The executor still revalidates the
    frozen authorization and route before dispatch.
    """
    from langchain_core.tools import StructuredTool
    from pydantic import Field, create_model

    def schema_model(
        capability: str, schema: dict[str, Any] | None
    ) -> type[Any] | None:
        if not schema or schema.get("type") != "object":
            return None
        fields: dict[str, tuple[Any, Any]] = {}
        required = set(schema.get("required", ()))
        type_map: dict[str, Any] = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list[Any],
            "object": dict[str, Any],
        }
        for name, definition in schema.get("properties", {}).items():
            if not isinstance(definition, Mapping):
                continue
            annotation = type_map.get(str(definition.get("type")), Any)
            default = ... if name in required else None
            fields[str(name)] = (
                annotation,
                Field(default, description=definition.get("description")),
            )
        return create_model(
            "LocalTool_" + re.sub(r"[^A-Za-z0-9_]", "_", capability),
            **fields,
        )

    tools: list[Any] = []
    for descriptor in assemble_local_tools(authorization, descriptors=descriptors):
        capability = descriptor.name

        async def invoke(_capability: str = capability, **arguments: Any) -> Any:
            return await executor.invoke(_capability, arguments)

        args_schema = schema_model(capability, descriptor.input_schema)

        tools.append(
            StructuredTool.from_function(
                coroutine=invoke,
                name=capability,
                description=descriptor.description,
                args_schema=args_schema,
                infer_schema=args_schema is None,
            )
        )
    return tuple(tools)
