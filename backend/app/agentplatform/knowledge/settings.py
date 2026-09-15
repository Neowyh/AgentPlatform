"""Shared accessors for the optional ``knowledge`` config section."""

from __future__ import annotations

from typing import Any


def knowledge_config() -> Any:
    """Return the ``knowledge`` config section (dict or object), or None."""

    from deerflow.config.app_config import get_app_config

    knowledge = getattr(get_app_config(), "knowledge", None)
    if isinstance(knowledge, dict):
        return knowledge
    return knowledge


def config_value(name: str, default: Any = None) -> Any:
    """Read one key from the ``knowledge`` section, tolerating absence."""

    knowledge = knowledge_config()
    if knowledge is None:
        return default
    raw = knowledge.get(name) if isinstance(knowledge, dict) else getattr(knowledge, name, None)
    return default if raw is None else raw
