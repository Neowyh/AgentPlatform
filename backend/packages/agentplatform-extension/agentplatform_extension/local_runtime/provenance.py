"""Caller-safe provenance for a local tool invocation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class LocalToolProvenance:
    """Bind a local execution to its Run and Tool Call without exposing a device."""

    run_id: str
    thread_id: str
    tool_call_id: str
    capability: str

    def as_mapping(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "tool_call_id": self.tool_call_id,
            "capability": self.capability,
        }
