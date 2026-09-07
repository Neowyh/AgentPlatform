from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.agentplatform import memory_adapter


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch) -> Mock:
    value = Mock()
    monkeypatch.setattr(memory_adapter, "get_memory_manager", lambda: value)
    return value


def test_crud_adapter_preserves_caller_scope(manager: Mock) -> None:
    manager.get_memory.return_value = {"facts": []}
    manager.clear_memory.return_value = {"facts": []}
    manager.delete_fact.return_value = {"facts": []}
    manager.update_fact.return_value = {"facts": []}

    assert memory_adapter.get_memory_data(user_id="u1", agent_name="a1") == {"facts": []}
    memory_adapter.clear_memory_data(user_id="u1", agent_name="a1")
    memory_adapter.delete_memory_fact("f1", user_id="u1", agent_name="a1")
    memory_adapter.update_memory_fact("f1", content="new", user_id="u1", agent_name="a1")

    manager.get_memory.assert_called_once_with(user_id="u1", agent_name="a1")
    manager.clear_memory.assert_called_once_with(user_id="u1", agent_name="a1")
    manager.delete_fact.assert_called_once_with("f1", user_id="u1", agent_name="a1")
    manager.update_fact.assert_called_once_with(
        fact_id="f1",
        content="new",
        category=None,
        confidence=None,
        user_id="u1",
        agent_name="a1",
    )


def test_create_fact_requires_persisted_fact_id(manager: Mock) -> None:
    manager.create_fact.return_value = ({"facts": []}, None)

    with pytest.raises(ValueError, match="capacity policy"):
        memory_adapter.create_memory_fact("fact", user_id="u1")


def test_reload_falls_back_to_get_memory(manager: Mock) -> None:
    manager.reload_memory.side_effect = NotImplementedError
    manager.get_memory.return_value = {"facts": []}

    assert memory_adapter.reload_memory_data(user_id="u1") == {"facts": []}
    manager.get_memory.assert_called_once_with(user_id="u1", agent_name=None)


def test_import_adapter_preserves_scope(manager: Mock) -> None:
    payload = {"facts": [{"id": "f1"}]}
    manager.import_memory.return_value = payload

    assert memory_adapter.import_memory_data(payload, user_id="u1") == payload
    manager.import_memory.assert_called_once_with(payload, user_id="u1", agent_name=None)
