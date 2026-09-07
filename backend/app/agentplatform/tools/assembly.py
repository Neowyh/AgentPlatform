"""Explicit tool binding seam for Agent construction."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from langchain_core.tools import BaseTool


@dataclass(frozen=True)
class ToolSet:
    """The tools visible to the model and the tools discoverable on demand."""

    active: tuple[BaseTool, ...] = ()
    deferred: tuple[BaseTool, ...] = ()

    @property
    def deferred_names(self) -> frozenset[str]:
        return frozenset(tool.name for tool in self.deferred)


def assemble_tools(
    tools: Iterable[BaseTool],
    *,
    deferred_names: Iterable[str] = (),
) -> ToolSet:
    """Partition tools into an immutable active/deferred value.

    Configuration loading stays outside this pure seam.  Callers can apply
    offline, allow-list, and model-specific policy before invoking it.
    """
    deferred = frozenset(deferred_names)
    active_tools: list[BaseTool] = []
    deferred_tools: list[BaseTool] = []
    seen: set[str] = set()
    for tool in tools:
        if tool.name in seen:
            continue
        seen.add(tool.name)
        (deferred_tools if tool.name in deferred else active_tools).append(tool)
    return ToolSet(tuple(active_tools), tuple(deferred_tools))


__all__ = ["ToolSet", "assemble_tools"]
