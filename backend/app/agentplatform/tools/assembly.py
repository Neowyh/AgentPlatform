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
    allowed_names: Iterable[str] | None = None,
    local_allowed_names: Iterable[str] | None = None,
) -> ToolSet:
    """Partition tools into an immutable active/deferred value.

    Configuration loading stays outside this pure seam.  Callers can apply
    offline, allow-list, and model-specific policy before invoking it.
    """
    deferred = frozenset(deferred_names)
    allowed = None if allowed_names is None else frozenset(allowed_names)
    local_allowed = None if local_allowed_names is None else frozenset(local_allowed_names)
    active_tools: list[BaseTool] = []
    deferred_tools: list[BaseTool] = []
    seen: set[str] = set()
    for tool in tools:
        if allowed is not None and tool.name not in allowed:
            continue
        if local_allowed is not None and tool.name.startswith("local.") and tool.name not in local_allowed:
            continue
        if tool.name in seen:
            continue
        seen.add(tool.name)
        (deferred_tools if tool.name in deferred else active_tools).append(tool)
    return ToolSet(tuple(active_tools), tuple(deferred_tools))


__all__ = ["ToolSet", "assemble_tools"]
