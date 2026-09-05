"""AgentPlatform boundary for DeerFlow tool assembly."""

from __future__ import annotations

from typing import Any

from deerflow.tools import get_available_tools as _get_available_tools


def get_available_tools(**kwargs: Any) -> list[Any]:
    """Assemble tools with DeerFlow's runtime factory.

    The gateway deliberately does not pass its legacy AppConfig object. The
    DeerFlow factory resolves the active runtime config, while AgentPlatform
    applies enterprise visibility and authorization after assembly.
    """
    return _get_available_tools(**kwargs)
