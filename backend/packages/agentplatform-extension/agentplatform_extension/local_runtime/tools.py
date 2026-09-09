"""Tool descriptors and assembly-time filtering for local capabilities."""

from __future__ import annotations

from dataclasses import dataclass

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
