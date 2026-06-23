"""Coverage tests for updater.py missed lines.

Targets: 43, 48, 53, 58, 77, 85, 128, 145, 172, 188, 219->216, 254->253,
         269, 272, 289-291, 329, 334, 422, 434-439, 526, 536, 554, 574->549, 610-611
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from ideer.agents.memory.updater import (
    MemoryUpdater,
    _create_empty_memory,
    _extract_text,
    _fact_content_key,
    _save_memory_to_file,
    _strip_upload_mentions_from_memory,
    clear_memory_data,
    create_memory_fact,
    delete_memory_fact,
    get_memory_data,
    import_memory_data,
    reload_memory_data,
    update_memory_fact,
    update_memory_from_conversation,
)
from ideer.config.memory_config import MemoryConfig


def _make_memory(facts=None):
    return {
        "version": "1.0",
        "lastUpdated": "",
        "user": {
            "workContext": {"summary": "", "updatedAt": ""},
            "personalContext": {"summary": "", "updatedAt": ""},
            "topOfMind": {"summary": "", "updatedAt": ""},
        },
        "history": {
            "recentMonths": {"summary": "", "updatedAt": ""},
            "earlierContext": {"summary": "", "updatedAt": ""},
            "longTermBackground": {"summary": "", "updatedAt": ""},
        },
        "facts": facts or [],
    }


def _memory_config(**overrides):
    config = MemoryConfig()
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


# --- Lines 43, 48, 53, 58: backward-compatible wrappers ---


def test_create_empty_memory_wrapper():
    """Line 43: _create_empty_memory() delegates to storage."""
    result = _create_empty_memory()
    assert result["version"] == "1.0"
    assert result["facts"] == []


def test_save_memory_to_file_wrapper():
    """Line 48: _save_memory_to_file() delegates to storage."""
    mock_storage = MagicMock()
    mock_storage.save.return_value = True
    with patch("ideer.agents.memory.updater.get_memory_storage", return_value=mock_storage):
        result = _save_memory_to_file({"test": True}, "agent1", user_id="u1")
    assert result is True
    mock_storage.save.assert_called_once_with({"test": True}, "agent1", user_id="u1")


def test_get_memory_data_wrapper():
    """Line 53: get_memory_data() delegates to storage."""
    mock_storage = MagicMock()
    mock_storage.load.return_value = {"version": "1.0"}
    with patch("ideer.agents.memory.updater.get_memory_storage", return_value=mock_storage):
        result = get_memory_data("agent1", user_id="u1")
    assert result == {"version": "1.0"}
    mock_storage.load.assert_called_once_with("agent1", user_id="u1")


def test_reload_memory_data_wrapper():
    """Line 58: reload_memory_data() delegates to storage."""
    mock_storage = MagicMock()
    mock_storage.reload.return_value = {"version": "1.0", "reloaded": True}
    with patch("ideer.agents.memory.updater.get_memory_storage", return_value=mock_storage):
        result = reload_memory_data("agent1", user_id="u1")
    assert result["reloaded"] is True
    mock_storage.reload.assert_called_once_with("agent1", user_id="u1")


# --- Line 77: import_memory_data save failure ---


def test_import_memory_data_raises_on_save_failure():
    """Line 77: import_memory_data raises OSError when save returns False."""
    mock_storage = MagicMock()
    mock_storage.save.return_value = False
    with patch("ideer.agents.memory.updater.get_memory_storage", return_value=mock_storage):
        with pytest.raises(OSError, match="Failed to save imported memory data"):
            import_memory_data(_make_memory())


# --- Line 85: clear_memory_data save failure ---


def test_clear_memory_data_raises_on_save_failure():
    """Line 85: clear_memory_data raises OSError when save returns False."""
    with patch("ideer.agents.memory.updater._save_memory_to_file", return_value=False):
        with pytest.raises(OSError, match="Failed to save cleared memory data"):
            clear_memory_data()


# --- Line 128: create_memory_fact save failure ---


def test_create_memory_fact_raises_on_save_failure():
    """Line 128: create_memory_fact raises OSError when save returns False."""
    with (
        patch("ideer.agents.memory.updater.get_memory_data", return_value=_make_memory()),
        patch("ideer.agents.memory.updater._save_memory_to_file", return_value=False),
    ):
        with pytest.raises(OSError, match="Failed to save memory data after creating fact"):
            create_memory_fact(content="User likes Python")


# --- Line 145: delete_memory_fact save failure ---


def test_delete_memory_fact_raises_on_save_failure():
    """Line 145: delete_memory_fact raises OSError when save returns False."""
    mem = _make_memory(facts=[{"id": "f1", "content": "test", "category": "context", "confidence": 0.9}])
    with (
        patch("ideer.agents.memory.updater.get_memory_data", return_value=mem),
        patch("ideer.agents.memory.updater._save_memory_to_file", return_value=False),
    ):
        with pytest.raises(OSError, match="Failed to save memory data after deleting fact"):
            delete_memory_fact("f1")


# --- Line 172: update_memory_fact empty content ---


def test_update_memory_fact_rejects_empty_content():
    """Line 172: update_memory_fact raises ValueError for empty content."""
    mem = _make_memory(facts=[{"id": "f1", "content": "test", "category": "context", "confidence": 0.9}])
    with patch("ideer.agents.memory.updater.get_memory_data", return_value=mem):
        with pytest.raises(ValueError, match="content"):
            update_memory_fact("f1", content="   ")


# --- Line 188: update_memory_fact save failure ---


def test_update_memory_fact_raises_on_save_failure():
    """Line 188: update_memory_fact raises OSError when save returns False."""
    mem = _make_memory(facts=[{"id": "f1", "content": "test", "category": "context", "confidence": 0.9}])
    with (
        patch("ideer.agents.memory.updater.get_memory_data", return_value=mem),
        patch("ideer.agents.memory.updater._save_memory_to_file", return_value=False),
    ):
        with pytest.raises(OSError, match="Failed to save memory data after updating fact"):
            update_memory_fact("f1", content="new content")


# --- Line 269, 272: _fact_content_key edge cases ---


def test_fact_content_key_non_string():
    """Line 269: _fact_content_key returns None for non-string."""
    assert _fact_content_key(42) is None
    assert _fact_content_key(None) is None
    assert _fact_content_key([]) is None


def test_fact_content_key_empty_after_strip():
    """Line 272: _fact_content_key returns None for whitespace-only."""
    assert _fact_content_key("   ") is None
    assert _fact_content_key("") is None


# --- Lines 289-291: _get_model ---


def test_get_model_uses_config_model_name():
    """Lines 289-291: _get_model creates model from config or explicit name."""
    updater = MemoryUpdater(model_name="test-model")
    mock_model = MagicMock()
    with (
        patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config()),
        patch("ideer.agents.memory.updater.create_chat_model", return_value=mock_model) as mock_create,
    ):
        result = updater._get_model()
    mock_create.assert_called_once_with(name="test-model", thinking_enabled=False)
    assert result is mock_model


def test_get_model_falls_back_to_config_model_name():
    """Lines 289-291: _get_model uses config.model_name when no explicit name."""
    updater = MemoryUpdater()
    mock_model = MagicMock()
    with (
        patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config(model_name="cfg-model")),
        patch("ideer.agents.memory.updater.create_chat_model", return_value=mock_model) as mock_create,
    ):
        updater._get_model()
    mock_create.assert_called_once_with(name="cfg-model", thinking_enabled=False)


# --- Line 329: _prepare_update_prompt with disabled config ---


def test_prepare_update_prompt_returns_none_when_disabled():
    """Line 329: returns None when memory is disabled."""
    updater = MemoryUpdater()
    with patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config(enabled=False)):
        result = updater._prepare_update_prompt([], None, False, False)
    assert result is None


# --- Line 334: _prepare_update_prompt with empty conversation ---


def test_prepare_update_prompt_returns_none_for_empty_conversation():
    """Line 334: returns None when conversation text is empty."""
    updater = MemoryUpdater()
    with (
        patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config(enabled=True)),
        patch("ideer.agents.memory.updater.get_memory_data", return_value=_make_memory()),
    ):
        msg = MagicMock()
        msg.type = "system"
        msg.content = ""
        result = updater._prepare_update_prompt([msg], None, False, False)
    assert result is None


# --- Line 422: _do_update_memory_sync when prepared is None ---


def test_do_update_memory_sync_returns_false_when_prepared_none():
    """Line 422: returns False when _prepare_update_prompt returns None."""
    updater = MemoryUpdater()
    with patch.object(updater, "_prepare_update_prompt", return_value=None):
        result = updater._do_update_memory_sync(messages=[])
    assert result is False


# --- Lines 434-439: _do_update_memory_sync exception handling ---


def test_do_update_memory_sync_returns_false_on_json_error():
    """Lines 434-435: returns False on JSONDecodeError."""
    updater = MemoryUpdater()
    mock_model = MagicMock()
    response = MagicMock()
    response.content = "not valid json"
    mock_model.invoke.return_value = response

    with (
        patch.object(updater, "_prepare_update_prompt", return_value=({}, "prompt")),
        patch.object(updater, "_get_model", return_value=mock_model),
    ):
        result = updater._do_update_memory_sync(messages=[])
    assert result is False


def test_do_update_memory_sync_returns_false_on_general_exception():
    """Lines 437-439: returns False on general Exception."""
    updater = MemoryUpdater()
    with patch.object(updater, "_prepare_update_prompt", side_effect=RuntimeError("boom")):
        result = updater._do_update_memory_sync(messages=[])
    assert result is False


# --- Line 526: _apply_updates history section ---


def test_apply_updates_updates_history_sections():
    """Line 526: _apply_updates applies history section updates."""
    updater = MemoryUpdater()
    mem = _make_memory()
    update_data = {
        "history": {
            "recentMonths": {"shouldUpdate": True, "summary": "Recent work summary"},
            "earlierContext": {"shouldUpdate": True, "summary": "Earlier context"},
            "longTermBackground": {"shouldUpdate": True, "summary": "Long term bg"},
        },
        "newFacts": [],
        "factsToRemove": [],
    }
    with patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config()):
        result = updater._apply_updates(mem, update_data)
    assert result["history"]["recentMonths"]["summary"] == "Recent work summary"
    assert result["history"]["earlierContext"]["summary"] == "Earlier context"
    assert result["history"]["longTermBackground"]["summary"] == "Long term bg"


# --- Line 554: _apply_updates with sourceError on non-string ---


def test_apply_updates_skips_non_string_source_error():
    """Line 554: _apply_updates skips sourceError that is not a string."""
    updater = MemoryUpdater()
    mem = _make_memory()
    update_data = {
        "newFacts": [
            {
                "content": "test fact",
                "category": "correction",
                "confidence": 0.95,
                "sourceError": 12345,
            }
        ],
    }
    with patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config()):
        result = updater._apply_updates(mem, update_data)
    assert "sourceError" not in result["facts"][0]


# --- Line 574->549: _apply_updates skips non-string content facts ---


def test_apply_updates_skips_non_string_content_facts():
    """Line 554/574: _apply_updates skips facts with non-string content."""
    updater = MemoryUpdater()
    mem = _make_memory()
    update_data = {
        "newFacts": [
            {"content": 12345, "category": "context", "confidence": 0.9},
            {"content": "valid fact", "category": "context", "confidence": 0.9},
        ],
    }
    with patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config()):
        result = updater._apply_updates(mem, update_data)
    assert len(result["facts"]) == 1
    assert result["facts"][0]["content"] == "valid fact"


# --- Lines 610-611: update_memory_from_conversation ---


def test_update_memory_from_conversation_delegates():
    """Lines 610-611: update_memory_from_conversation creates updater and delegates."""
    mock_model = MagicMock()
    response = MagicMock()
    response.content = '{"user": {}, "history": {}, "newFacts": [], "factsToRemove": []}'
    mock_model.invoke.return_value = response

    with (
        patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config(enabled=True)),
        patch("ideer.agents.memory.updater.get_memory_data", return_value=_make_memory()),
        patch("ideer.agents.memory.updater.get_memory_storage", return_value=MagicMock(save=MagicMock(return_value=True))),
        patch("ideer.agents.memory.updater.create_chat_model", return_value=mock_model),
    ):
        msg = MagicMock()
        msg.type = "human"
        msg.content = "Hello"
        ai_msg = MagicMock()
        ai_msg.type = "ai"
        ai_msg.content = "Hi"
        result = update_memory_from_conversation([msg, ai_msg])
    assert result is True


# --- _strip_upload_mentions_from_memory branches ---


def test_strip_upload_mentions_removes_upload_facts():
    """Test that upload-related facts are removed."""
    mem = _make_memory(
        facts=[
            {"id": "f1", "content": "User uploaded a file for analysis", "category": "context", "confidence": 0.5},
            {"id": "f2", "content": "User prefers Python", "category": "preference", "confidence": 0.9},
        ]
    )
    result = _strip_upload_mentions_from_memory(mem)
    assert len(result["facts"]) == 1
    assert result["facts"][0]["id"] == "f2"


def test_strip_upload_mentions_cleans_summaries():
    """Test that upload mentions are stripped from summaries."""
    mem = {
        "user": {
            "workContext": {"summary": "User uploaded files today. Works on Python."},
        },
        "history": {},
        "facts": [],
    }
    result = _strip_upload_mentions_from_memory(mem)
    assert "uploaded" not in result["user"]["workContext"]["summary"].lower()
    assert "Works on Python" in result["user"]["workContext"]["summary"]


# --- update_memory when running in event loop ---


def test_update_memory_in_running_loop():
    """Test that update_memory offloads to executor when loop is running."""
    updater = MemoryUpdater()
    valid_json = '{"user": {}, "history": {}, "newFacts": [], "factsToRemove": []}'
    model = MagicMock()
    response = MagicMock()
    response.content = valid_json
    model.invoke.return_value = response

    with (
        patch.object(updater, "_get_model", return_value=model),
        patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config(enabled=True)),
        patch("ideer.agents.memory.updater.get_memory_data", return_value=_make_memory()),
        patch("ideer.agents.memory.updater.get_memory_storage", return_value=MagicMock(save=MagicMock(return_value=True))),
    ):
        msg = MagicMock()
        msg.type = "human"
        msg.content = "Hello"
        ai_msg = MagicMock()
        ai_msg.type = "ai"
        ai_msg.content = "Hi"

        async def run():
            return updater.update_memory([msg, ai_msg])

        result = asyncio.run(run())
    assert result is True


# --- _apply_updates with user section updates ---


def test_apply_updates_user_sections():
    """_apply_updates applies user section updates."""
    updater = MemoryUpdater()
    mem = _make_memory()
    update_data = {
        "user": {
            "workContext": {"shouldUpdate": True, "summary": "Works on iDeer"},
            "personalContext": {"shouldUpdate": True, "summary": "Prefers Python"},
            "topOfMind": {"shouldUpdate": True, "summary": "Building memory system"},
        },
        "newFacts": [],
    }
    with patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config()):
        result = updater._apply_updates(mem, update_data)
    assert result["user"]["workContext"]["summary"] == "Works on iDeer"
    assert result["user"]["personalContext"]["summary"] == "Prefers Python"
    assert result["user"]["topOfMind"]["summary"] == "Building memory system"


# --- _extract_text with dict blocks missing 'text' key ---


def test_extract_text_dict_block_without_text():
    """_extract_text handles dict blocks without 'text' key."""
    content = [{"type": "image_url", "url": "http://img.png"}]
    assert _extract_text(content) == ""
