"""AgentPlatform's HTTP-facing memory adapter.

The gateway owns authorization and caller identity; DeerFlow owns the memory
backend and persistence contract.  Keeping this small adapter at the control
plane boundary lets the legacy updater remain available to un-migrated runtime
callers while the Memory API moves to ``MemoryManager``.
"""

from __future__ import annotations

from typing import Any

from deerflow.agents.memory import get_memory_manager


def get_memory_data(*, user_id: str | None = None, agent_name: str | None = None) -> dict[str, Any]:
    return get_memory_manager().get_memory(user_id=user_id, agent_name=agent_name)


def reload_memory_data(*, user_id: str | None = None, agent_name: str | None = None) -> dict[str, Any]:
    manager = get_memory_manager()
    try:
        return manager.reload_memory(user_id=user_id, agent_name=agent_name)
    except NotImplementedError:
        return manager.get_memory(user_id=user_id, agent_name=agent_name)


def clear_memory_data(*, user_id: str | None = None, agent_name: str | None = None) -> dict[str, Any]:
    return get_memory_manager().clear_memory(user_id=user_id, agent_name=agent_name)


def create_memory_fact(
    content: str,
    category: str = "context",
    confidence: float = 0.5,
    *,
    user_id: str | None = None,
    agent_name: str | None = None,
) -> dict[str, Any]:
    memory_data, fact_id = get_memory_manager().create_fact(
        content=content,
        category=category,
        confidence=confidence,
        user_id=user_id,
        agent_name=agent_name,
    )
    if fact_id is None:
        raise ValueError("Fact was not stored because the configured memory capacity policy evicted it")
    return memory_data


def delete_memory_fact(
    fact_id: str,
    *,
    user_id: str | None = None,
    agent_name: str | None = None,
) -> dict[str, Any]:
    return get_memory_manager().delete_fact(fact_id, user_id=user_id, agent_name=agent_name)


def update_memory_fact(
    fact_id: str,
    content: str | None = None,
    category: str | None = None,
    confidence: float | None = None,
    *,
    user_id: str | None = None,
    agent_name: str | None = None,
) -> dict[str, Any]:
    return get_memory_manager().update_fact(
        fact_id=fact_id,
        content=content,
        category=category,
        confidence=confidence,
        user_id=user_id,
        agent_name=agent_name,
    )


def import_memory_data(
    memory_data: dict[str, Any],
    *,
    user_id: str | None = None,
    agent_name: str | None = None,
) -> dict[str, Any]:
    return get_memory_manager().import_memory(memory_data, user_id=user_id, agent_name=agent_name)
