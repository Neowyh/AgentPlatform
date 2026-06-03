"""Tool registry for iDeer software factory.

Provides a unified view of all registered tools with metadata,
used by the tools API router.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    name: str
    description: str
    group: str
    requires_network: bool = False
    configurable: bool = False
    config_schema: dict = field(default_factory=dict)
    param_schema: dict = field(default_factory=dict)


class ToolRegistry:
    """Central registry of all available tools."""

    def __init__(self):
        self._tools: dict[str, ToolInfo] = {}

    def register(self, tool: ToolInfo):
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolInfo | None:
        return self._tools.get(name)

    def list_all(self) -> list[ToolInfo]:
        return list(self._tools.values())

    def list_by_group(self, group: str) -> list[ToolInfo]:
        return [t for t in self._tools.values() if t.group == group]

    def search(self, query: str) -> list[ToolInfo]:
        q = query.lower()
        return [t for t in self._tools.values() if q in t.name.lower() or q in t.description.lower()]


# Global registry instance
_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    return _registry
