"""Extended coverage tests for memory/prompt.py, memory/queue.py, memory/storage.py,
and memory/updater.py modules.

Targets uncovered lines including _count_tokens fallbacks, format_memory_for_injection
edge cases, format_conversation_for_update content types, MemoryUpdateQueue additional
paths, FileMemoryStorage user-scoped and legacy paths, and MemoryUpdater helper methods.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ideer.agents.memory.prompt import (
    _count_tokens,
    format_conversation_for_update,
    format_memory_for_injection,
)
from ideer.agents.memory.queue import (
    ConversationContext,
    MemoryUpdateQueue,
    get_memory_queue,
    reset_memory_queue,
)
from ideer.agents.memory.storage import (
    FileMemoryStorage,
    create_empty_memory,
    utc_now_iso_z,
)
from ideer.agents.memory.updater import (
    MemoryUpdater,
    _extract_text,
    _fact_content_key,
    _strip_upload_mentions_from_memory,
    _validate_confidence,
    clear_memory_data,
    create_memory_fact,
    delete_memory_fact,
    import_memory_data,
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


# ---------------------------------------------------------------------------
# memory/prompt.py - _count_tokens
# ---------------------------------------------------------------------------


class TestCountTokens:
    def test_fallback_when_tiktoken_unavailable(self, monkeypatch):
        monkeypatch.setattr("ideer.agents.memory.prompt.TIKTOKEN_AVAILABLE", False)
        result = _count_tokens("hello world")
        assert result == len("hello world") // 4

    def test_fallback_on_exception(self, monkeypatch):
        """When tiktoken raises, should fallback to char-based estimation."""
        monkeypatch.setattr("ideer.agents.memory.prompt.TIKTOKEN_AVAILABLE", True)
        import ideer.agents.memory.prompt as prompt_mod

        prompt_mod.tiktoken if hasattr(prompt_mod, "tiktoken") else None

        fake_tiktoken = MagicMock()
        fake_tiktoken.get_encoding.side_effect = RuntimeError("encoding not found")
        monkeypatch.setattr(prompt_mod, "tiktoken", fake_tiktoken)

        result = _count_tokens("test text")
        assert result == len("test text") // 4

    def test_normal_counting(self):
        result = _count_tokens("hello world")
        assert isinstance(result, int)
        assert result > 0


# ---------------------------------------------------------------------------
# memory/prompt.py - format_memory_for_injection
# ---------------------------------------------------------------------------


class TestFormatMemoryForInjectionExtended:
    def test_empty_data_returns_empty(self):
        assert format_memory_for_injection({}) == ""
        assert format_memory_for_injection(None) == ""  # type: ignore[arg-type]

    def test_only_user_context(self):
        data = {
            "user": {
                "workContext": {"summary": "Engineer at Acme"},
                "personalContext": {"summary": "Speaks English and Chinese"},
                "topOfMind": {"summary": "Working on AI project"},
            },
            "history": {},
            "facts": [],
        }
        result = format_memory_for_injection(data, max_tokens=5000)
        assert "Work: Engineer at Acme" in result
        assert "Personal: Speaks English and Chinese" in result
        assert "Current Focus: Working on AI project" in result

    def test_only_history(self):
        data = {
            "user": {},
            "history": {
                "recentMonths": {"summary": "Recent activity"},
                "earlierContext": {"summary": "Earlier context"},
                "longTermBackground": {"summary": "Long-term background"},
            },
            "facts": [],
        }
        result = format_memory_for_injection(data, max_tokens=5000)
        assert "Recent: Recent activity" in result
        assert "Earlier: Earlier context" in result
        assert "Background: Long-term background" in result

    def test_facts_with_source_error(self):
        data = {
            "facts": [
                {
                    "content": "Use make dev",
                    "category": "correction",
                    "confidence": 0.95,
                    "sourceError": "Agent previously said npm start",
                }
            ]
        }
        result = format_memory_for_injection(data, max_tokens=5000)
        assert "avoid: Agent previously said npm start" in result

    def test_correction_without_source_error(self):
        data = {
            "facts": [
                {
                    "content": "Use make dev",
                    "category": "correction",
                    "confidence": 0.95,
                }
            ]
        }
        result = format_memory_for_injection(data, max_tokens=5000)
        assert "avoid:" not in result

    def test_correction_with_empty_source_error(self):
        data = {
            "facts": [
                {
                    "content": "Use make dev",
                    "category": "correction",
                    "confidence": 0.95,
                    "sourceError": "   ",
                }
            ]
        }
        result = format_memory_for_injection(data, max_tokens=5000)
        assert "avoid:" not in result

    def test_facts_non_list_ignored(self):
        data = {"facts": "not a list"}
        result = format_memory_for_injection(data, max_tokens=5000)
        assert result == ""

    def test_facts_empty_list_no_facts_section(self):
        data = {"facts": []}
        result = format_memory_for_injection(data, max_tokens=5000)
        assert result == ""

    def test_truncation_when_exceeds_token_limit(self, monkeypatch):
        """When result exceeds max_tokens, should be truncated."""
        monkeypatch.setattr("ideer.agents.memory.prompt._count_tokens", lambda text, **kw: len(text))

        data = {
            "user": {"workContext": {"summary": "A very long summary " * 100}},
            "facts": [],
        }
        result = format_memory_for_injection(data, max_tokens=50)
        assert result.endswith("\n...")

    def test_empty_summaries_not_included(self):
        data = {
            "user": {
                "workContext": {"summary": ""},
                "personalContext": {"summary": ""},
                "topOfMind": {"summary": ""},
            },
            "history": {
                "recentMonths": {"summary": ""},
                "earlierContext": {"summary": ""},
                "longTermBackground": {"summary": ""},
            },
            "facts": [],
        }
        result = format_memory_for_injection(data, max_tokens=5000)
        assert result == ""

    def test_facts_with_non_string_content_ignored(self):
        data = {
            "facts": [
                {"content": 42, "category": "knowledge", "confidence": 0.9},
                {"content": None, "category": "context", "confidence": 0.8},
                {"content": "  ", "category": "context", "confidence": 0.7},
                {"content": "Valid fact", "category": "context", "confidence": 0.6},
            ]
        }
        result = format_memory_for_injection(data, max_tokens=5000)
        assert "Valid fact" in result
        assert "42" not in result

    def test_facts_with_empty_category_defaults_to_context(self):
        data = {
            "facts": [
                {"content": "Some fact", "category": "", "confidence": 0.8},
            ]
        }
        result = format_memory_for_injection(data, max_tokens=5000)
        assert "context" in result

    def test_facts_with_whitespace_only_content_ignored(self):
        data = {
            "facts": [
                {"content": "   ", "category": "context", "confidence": 0.8},
            ]
        }
        result = format_memory_for_injection(data, max_tokens=5000)
        assert result == ""


# ---------------------------------------------------------------------------
# memory/prompt.py - format_conversation_for_update
# ---------------------------------------------------------------------------


class TestFormatConversationForUpdateExtended:
    def test_human_message_with_uploaded_files_tag(self):
        msg = MagicMock()
        msg.type = "human"
        msg.content = "<uploaded_files>file.txt</uploaded_files>\nWhat is this?"
        result = format_conversation_for_update([msg])
        assert "uploaded_files" not in result
        assert "What is this?" in result

    def test_human_message_only_uploads_tag_skipped(self):
        msg = MagicMock()
        msg.type = "human"
        msg.content = "<uploaded_files>file.txt</uploaded_files>"
        result = format_conversation_for_update([msg])
        assert result == ""

    def test_long_message_truncated(self):
        msg = MagicMock()
        msg.type = "human"
        msg.content = "x" * 2000
        result = format_conversation_for_update([msg])
        assert "..." in result
        assert len(result) < 2000

    def test_non_human_non_ai_messages_skipped(self):
        msg = MagicMock()
        msg.type = "system"
        msg.content = "System message"
        result = format_conversation_for_update([msg])
        assert "System message" not in result

    def test_unknown_role_messages_skipped(self):
        msg = MagicMock()
        msg.type = "tool"
        msg.content = "Tool result"
        result = format_conversation_for_update([msg])
        assert "Tool result" not in result

    def test_list_content_with_dict_text(self):
        msg = MagicMock()
        msg.type = "human"
        msg.content = [{"type": "text", "text": "structured content"}]
        result = format_conversation_for_update([msg])
        assert "structured content" in result

    def test_list_content_with_mixed_types(self):
        msg = MagicMock()
        msg.type = "human"
        msg.content = [
            "plain text",
            {"type": "image_url", "image_url": {"url": "http://img.png"}},
            {"type": "text", "text": "more text"},
        ]
        result = format_conversation_for_update([msg])
        assert "plain text" in result
        assert "more text" in result

    def test_list_content_empty_text_parts_falls_back_to_str(self):
        msg = MagicMock()
        msg.type = "human"
        msg.content = [{"type": "image_url", "image_url": {}}]
        result = format_conversation_for_update([msg])
        # Falls back to str(content) since no text parts
        assert len(result) > 0


# ---------------------------------------------------------------------------
# memory/queue.py - additional paths
# ---------------------------------------------------------------------------


class TestMemoryQueueExtended:
    def test_add_disabled_memory(self):
        queue = MemoryUpdateQueue()
        with patch("ideer.agents.memory.queue.get_memory_config", return_value=_memory_config(enabled=False)):
            queue.add(thread_id="t1", messages=["msg"])
        assert queue.pending_count == 0

    def test_add_nowait_disabled_memory(self):
        queue = MemoryUpdateQueue()
        with patch("ideer.agents.memory.queue.get_memory_config", return_value=_memory_config(enabled=False)):
            queue.add_nowait(thread_id="t1", messages=["msg"])
        assert queue.pending_count == 0

    def test_flush_cancels_timer(self):
        queue = MemoryUpdateQueue()
        timer_mock = MagicMock()
        queue._timer = timer_mock

        # Mock MemoryUpdater to avoid actual processing
        with patch("ideer.agents.memory.updater.MemoryUpdater"):
            queue.flush()
        timer_mock.cancel.assert_called_once()

    def test_flush_empty_queue(self):
        queue = MemoryUpdateQueue()
        queue.flush()  # should not raise

    def test_clear(self):
        queue = MemoryUpdateQueue()
        timer_mock = MagicMock()
        queue._timer = timer_mock
        queue._queue = [ConversationContext(thread_id="t1", messages=["msg"])]

        queue.clear()
        assert queue.pending_count == 0
        assert queue._timer is None
        assert queue._processing is False

    def test_process_queue_empty(self):
        queue = MemoryUpdateQueue()
        queue._process_queue()  # should not raise

    def test_process_queue_with_success(self):
        queue = MemoryUpdateQueue()
        queue._queue = [ConversationContext(thread_id="t1", messages=["msg"], user_id="u1")]
        mock_updater = MagicMock()
        mock_updater.update_memory.return_value = True

        with patch("ideer.agents.memory.updater.MemoryUpdater", return_value=mock_updater):
            queue.flush()

        mock_updater.update_memory.assert_called_once()

    def test_process_queue_with_failure(self):
        queue = MemoryUpdateQueue()
        queue._queue = [ConversationContext(thread_id="t1", messages=["msg"])]
        mock_updater = MagicMock()
        mock_updater.update_memory.return_value = False

        with patch("ideer.agents.memory.updater.MemoryUpdater", return_value=mock_updater):
            queue.flush()  # should not raise

    def test_process_queue_with_exception(self):
        queue = MemoryUpdateQueue()
        queue._queue = [ConversationContext(thread_id="t1", messages=["msg"])]
        mock_updater = MagicMock()
        mock_updater.update_memory.side_effect = RuntimeError("boom")

        with patch("ideer.agents.memory.updater.MemoryUpdater", return_value=mock_updater):
            queue.flush()  # should not raise

    def test_process_queue_multiple_with_delay(self):
        queue = MemoryUpdateQueue()
        queue._queue = [
            ConversationContext(thread_id="t1", messages=["msg1"]),
            ConversationContext(thread_id="t2", messages=["msg2"]),
        ]
        mock_updater = MagicMock()
        mock_updater.update_memory.return_value = True

        with (
            patch("ideer.agents.memory.updater.MemoryUpdater", return_value=mock_updater),
            patch("ideer.agents.memory.queue.time.sleep"),
        ):
            queue.flush()

        assert mock_updater.update_memory.call_count == 2

    def test_is_processing_property(self):
        queue = MemoryUpdateQueue()
        assert queue.is_processing is False

    def test_queue_key(self):
        key = MemoryUpdateQueue._queue_key("t1", "u1", "agent-a")
        assert key == ("t1", "u1", "agent-a")

    def test_queue_key_none_values(self):
        key = MemoryUpdateQueue._queue_key("t1", None, None)
        assert key == ("t1", None, None)


class TestMemoryQueueSingleton:
    def test_get_memory_queue_singleton(self):
        import ideer.agents.memory.queue as queue_mod

        old = queue_mod._memory_queue
        try:
            queue_mod._memory_queue = None
            q1 = get_memory_queue()
            q2 = get_memory_queue()
            assert q1 is q2
        finally:
            queue_mod._memory_queue = old

    def test_reset_memory_queue(self):
        import ideer.agents.memory.queue as queue_mod

        old = queue_mod._memory_queue
        try:
            queue_mod._memory_queue = None
            q1 = get_memory_queue()
            reset_memory_queue()
            q2 = get_memory_queue()
            assert q1 is not q2
        finally:
            queue_mod._memory_queue = old

    def test_reset_clears_existing(self):
        import ideer.agents.memory.queue as queue_mod

        old = queue_mod._memory_queue
        try:
            queue_mod._memory_queue = None
            q = get_memory_queue()
            with patch("ideer.agents.memory.queue.get_memory_config", return_value=_memory_config(enabled=True)):
                with patch.object(q, "_reset_timer"):
                    q.add(thread_id="t1", messages=["msg"])
            assert q.pending_count == 1
            reset_memory_queue()
            q2 = get_memory_queue()
            assert q2.pending_count == 0
        finally:
            queue_mod._memory_queue = old


# ---------------------------------------------------------------------------
# memory/storage.py - additional paths
# ---------------------------------------------------------------------------


class TestUtcNowIsoZ:
    def test_returns_string_with_z_suffix(self):
        result = utc_now_iso_z()
        assert isinstance(result, str)
        assert result.endswith("Z")
        assert "T" in result


class TestCreateEmptyMemory:
    def test_structure(self):
        m = create_empty_memory()
        assert m["version"] == "1.0"
        assert "lastUpdated" in m
        assert isinstance(m["user"], dict)
        assert isinstance(m["history"], dict)
        assert isinstance(m["facts"], list)


class TestFileMemoryStorageExtended:
    def test_get_memory_file_path_with_user_id(self, tmp_path):
        with (
            patch(
                "ideer.agents.memory.storage.get_paths",
                return_value=SimpleNamespace(
                    user_memory_file=lambda uid: tmp_path / "users" / uid / "memory.json",
                    user_agent_memory_file=lambda uid, name: tmp_path / "users" / uid / "agent-memory" / name / "memory.json",
                ),
            ),
            patch("ideer.agents.memory.storage.get_memory_config", return_value=MemoryConfig(storage_path="")),
        ):
            storage = FileMemoryStorage()
            path = storage._get_memory_file_path(None, user_id="u1")
            assert "u1" in str(path)

    def test_get_memory_file_path_with_user_id_and_agent(self, tmp_path):
        with (
            patch(
                "ideer.agents.memory.storage.get_paths",
                return_value=SimpleNamespace(
                    user_agent_memory_file=lambda uid, name: tmp_path / "users" / uid / "agent-memory" / name / "memory.json",
                ),
            ),
            patch("ideer.agents.memory.storage.get_memory_config", return_value=MemoryConfig(storage_path="")),
        ):
            storage = FileMemoryStorage()
            path = storage._get_memory_file_path("my-agent", user_id="u1")
            assert "my-agent" in str(path)
            assert "u1" in str(path)

    def test_get_memory_file_path_storage_path_absolute(self, tmp_path):
        abs_path = str(tmp_path / "custom_memory.json")
        with patch("ideer.agents.memory.storage.get_memory_config", return_value=MemoryConfig(storage_path=abs_path)):
            storage = FileMemoryStorage()
            path = storage._get_memory_file_path(None, user_id="u1")
            assert str(path) == abs_path

    def test_get_memory_file_path_storage_path_relative(self, tmp_path):
        with (
            patch("ideer.agents.memory.storage.get_paths", return_value=SimpleNamespace(base_dir=tmp_path)),
            patch("ideer.agents.memory.storage.get_memory_config", return_value=MemoryConfig(storage_path="custom/memory.json")),
        ):
            storage = FileMemoryStorage()
            path = storage._get_memory_file_path(None)
            assert str(path).endswith("custom/memory.json")

    def test_get_read_memory_file_path_legacy_fallback_no_user(self, tmp_path):
        """When the canonical path doesn't exist, fall back to legacy agent path."""
        legacy_path = tmp_path / "agents" / "test-agent" / "memory.json"
        legacy_path.parent.mkdir(parents=True)
        legacy_path.write_text('{"version": "1.0"}')

        mock_paths = SimpleNamespace(
            agent_memory_file=lambda name: tmp_path / "agent-memory" / name / "memory.json",
            legacy_agent_memory_file=lambda name: tmp_path / "agents" / name / "memory.json",
        )

        with (
            patch("ideer.agents.memory.storage.get_paths", return_value=mock_paths),
            patch("ideer.agents.memory.storage.get_memory_config", return_value=MemoryConfig(storage_path="")),
        ):
            storage = FileMemoryStorage()
            path = storage._get_read_memory_file_path("test-agent")
            assert path == legacy_path

    def test_get_read_memory_file_path_legacy_fallback_with_user(self, tmp_path):
        """When the canonical path doesn't exist, fall back to legacy user agent path."""
        legacy_path = tmp_path / "users" / "u1" / "agents" / "test-agent" / "memory.json"
        legacy_path.parent.mkdir(parents=True)
        legacy_path.write_text('{"version": "1.0"}')

        mock_paths = SimpleNamespace(
            user_agent_memory_file=lambda uid, name: tmp_path / "users" / uid / "agent-memory" / name / "memory.json",
            legacy_user_agent_memory_file=lambda uid, name: tmp_path / "users" / uid / "agents" / name / "memory.json",
        )

        with (
            patch("ideer.agents.memory.storage.get_paths", return_value=mock_paths),
            patch("ideer.agents.memory.storage.get_memory_config", return_value=MemoryConfig(storage_path="")),
        ):
            storage = FileMemoryStorage()
            path = storage._get_read_memory_file_path("test-agent", user_id="u1")
            assert path == legacy_path

    def test_load_returns_empty_on_json_error(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{")

        with (
            patch("ideer.agents.memory.storage.get_paths", return_value=SimpleNamespace(memory_file=bad_file)),
            patch("ideer.agents.memory.storage.get_memory_config", return_value=MemoryConfig(storage_path="")),
        ):
            storage = FileMemoryStorage()
            memory = storage._load_memory_from_file()
            assert memory["version"] == "1.0"

    def test_load_creates_empty_when_file_missing(self):
        with (
            patch("ideer.agents.memory.storage.get_paths", return_value=SimpleNamespace(memory_file=Path("/nonexistent/memory.json"))),
            patch("ideer.agents.memory.storage.get_memory_config", return_value=MemoryConfig(storage_path="")),
        ):
            storage = FileMemoryStorage()
            memory = storage._load_memory_from_file()
            assert memory["version"] == "1.0"


# ---------------------------------------------------------------------------
# memory/updater.py - additional paths
# ---------------------------------------------------------------------------


class TestUpdaterHelpers:
    def test_validate_confidence_valid(self):
        assert _validate_confidence(0.5) == 0.5
        assert _validate_confidence(0.0) == 0.0
        assert _validate_confidence(1.0) == 1.0

    def test_validate_confidence_invalid(self):
        with pytest.raises(ValueError):
            _validate_confidence(-0.1)
        with pytest.raises(ValueError):
            _validate_confidence(1.1)
        with pytest.raises(ValueError):
            _validate_confidence(float("nan"))
        with pytest.raises(ValueError):
            _validate_confidence(float("inf"))

    def test_fact_content_key_valid(self):
        assert _fact_content_key("hello") == "hello"
        assert _fact_content_key("  Hello  ") == "hello"
        assert _fact_content_key(None) is None
        assert _fact_content_key(42) is None
        assert _fact_content_key("") is None
        assert _fact_content_key("   ") is None

    def test_extract_text_fallback(self):
        assert _extract_text(42) == "42"
        assert _extract_text(None) == "None"
        assert _extract_text(3.14) == "3.14"

    def test_strip_upload_mentions_from_memory(self):
        memory = {
            "user": {
                "workContext": {"summary": "User uploaded files for analysis."},
                "personalContext": {"summary": "Loves Python."},
                "topOfMind": {"summary": "Working on AI."},
            },
            "history": {
                "recentMonths": {"summary": "User uploaded a report last week."},
            },
            "facts": [
                {"content": "User uploaded a document.", "id": "f1"},
                {"content": "User likes Python.", "id": "f2"},
            ],
        }
        result = _strip_upload_mentions_from_memory(memory)
        assert "uploaded" not in result["user"]["workContext"]["summary"].lower()
        assert "Loves Python" in result["user"]["personalContext"]["summary"]
        assert len(result["facts"]) == 1
        assert result["facts"][0]["id"] == "f2"

    def test_strip_upload_mentions_empty_memory(self):
        memory = _make_memory()
        result = _strip_upload_mentions_from_memory(memory)
        assert result["facts"] == []

    def test_create_memory_fact_empty_category_defaults(self):
        with (
            patch("ideer.agents.memory.updater.get_memory_data", return_value=_make_memory()),
            patch("ideer.agents.memory.updater._save_memory_to_file", return_value=True),
        ):
            result = create_memory_fact(content="Test fact", category="")
        assert result["facts"][0]["category"] == "context"


class TestMemoryUpdaterPrepareUpdatePrompt:
    def test_returns_none_when_disabled(self):
        updater = MemoryUpdater()
        with patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config(enabled=False)):
            result = updater._prepare_update_prompt([], None, False, False)
        assert result is None

    def test_returns_none_when_messages_empty(self):
        updater = MemoryUpdater()
        with patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config(enabled=True)):
            result = updater._prepare_update_prompt([], None, False, False)
        assert result is None

    def test_returns_none_when_conversation_empty(self):
        updater = MemoryUpdater()
        with (
            patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config(enabled=True)),
            patch("ideer.agents.memory.updater.get_memory_data", return_value=_make_memory()),
            patch("ideer.agents.memory.updater.format_conversation_for_update", return_value=""),
        ):
            result = updater._prepare_update_prompt([], None, False, False)
        assert result is None


class TestMemoryUpdaterDoUpdateSync:
    def test_returns_false_when_disabled(self):
        updater = MemoryUpdater()
        with patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config(enabled=False)):
            result = updater._do_update_memory_sync([], None, None)
        assert result is False

    def test_returns_false_on_json_error(self):
        updater = MemoryUpdater()
        mock_model = MagicMock()
        response = MagicMock()
        response.content = "not valid json"
        mock_model.invoke.return_value = response

        with (
            patch.object(updater, "_get_model", return_value=mock_model),
            patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config(enabled=True)),
            patch("ideer.agents.memory.updater.get_memory_data", return_value=_make_memory()),
            patch("ideer.agents.memory.updater.format_conversation_for_update", return_value="conversation"),
        ):
            msg = MagicMock()
            msg.type = "human"
            msg.content = "Hello"
            result = updater._do_update_memory_sync([msg], None, None)
        assert result is False

    def test_returns_false_on_generic_exception(self):
        updater = MemoryUpdater()
        mock_model = MagicMock()
        mock_model.invoke.side_effect = RuntimeError("LLM down")

        with (
            patch.object(updater, "_get_model", return_value=mock_model),
            patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config(enabled=True)),
            patch("ideer.agents.memory.updater.get_memory_data", return_value=_make_memory()),
            patch("ideer.agents.memory.updater.format_conversation_for_update", return_value="conversation"),
        ):
            msg = MagicMock()
            msg.type = "human"
            msg.content = "Hello"
            result = updater._do_update_memory_sync([msg], None, None)
        assert result is False


class TestMemoryUpdaterFinalizeUpdate:
    def test_strips_code_fences(self):
        updater = MemoryUpdater()
        json_content = '{"user": {}, "history": {}, "newFacts": [], "factsToRemove": []}'

        with (
            patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config(enabled=True, fact_confidence_threshold=0.7)),
            patch("ideer.agents.memory.updater.get_memory_storage") as mock_storage_fn,
        ):
            mock_storage = MagicMock()
            mock_storage.save.return_value = True
            mock_storage_fn.return_value = mock_storage

            result = updater._finalize_update(
                _make_memory(),
                f"```json\n{json_content}\n```",
                "t1",
                None,
            )
        assert result is True
        mock_storage.save.assert_called_once()

    def test_handles_response_without_closing_fence(self):
        updater = MemoryUpdater()
        json_content = '{"user": {}, "history": {}, "newFacts": [], "factsToRemove": []}'

        with (
            patch("ideer.agents.memory.updater.get_memory_config", return_value=_memory_config(enabled=True, fact_confidence_threshold=0.7)),
            patch("ideer.agents.memory.updater.get_memory_storage") as mock_storage_fn,
        ):
            mock_storage = MagicMock()
            mock_storage.save.return_value = True
            mock_storage_fn.return_value = mock_storage

            result = updater._finalize_update(
                _make_memory(),
                f"```\n{json_content}",
                "t1",
                "agent-a",
            )
        assert result is True


class TestMemoryUpdaterBuildCorrectionHint:
    def test_neither(self):
        updater = MemoryUpdater()
        assert updater._build_correction_hint(False, False) == ""

    def test_correction_only(self):
        updater = MemoryUpdater()
        hint = updater._build_correction_hint(True, False)
        assert "correction" in hint.lower()
        assert "reinforcement" not in hint.lower()

    def test_reinforcement_only(self):
        updater = MemoryUpdater()
        hint = updater._build_correction_hint(False, True)
        assert "reinforcement" in hint.lower()
        assert "correction" not in hint.lower()

    def test_both(self):
        updater = MemoryUpdater()
        hint = updater._build_correction_hint(True, True)
        assert "correction" in hint.lower()
        assert "reinforcement" in hint.lower()


class TestUpdateMemoryFromConvenience:
    def test_calls_updater(self):
        messages = [MagicMock(type="human", content="Hi")]
        with patch("ideer.agents.memory.updater.MemoryUpdater") as MockUpdater:
            mock_updater = MagicMock()
            mock_updater.update_memory.return_value = True
            MockUpdater.return_value = mock_updater

            result = update_memory_from_conversation(
                messages,
                thread_id="t1",
                agent_name="agent-a",
                correction_detected=True,
                reinforcement_detected=False,
                user_id="u1",
            )
        assert result is True
        mock_updater.update_memory.assert_called_once_with(
            messages,
            "t1",
            "agent-a",
            True,
            False,
            user_id="u1",
        )


class TestImportMemoryDataFailure:
    def test_raises_on_save_failure(self):
        mock_storage = MagicMock()
        mock_storage.save.return_value = False

        with patch("ideer.agents.memory.updater.get_memory_storage", return_value=mock_storage):
            with pytest.raises(OSError, match="Failed to save"):
                import_memory_data({"version": "1.0"})


class TestClearMemoryDataFailure:
    def test_raises_on_save_failure(self):
        with patch("ideer.agents.memory.updater._save_memory_to_file", return_value=False):
            with pytest.raises(OSError, match="Failed to save"):
                clear_memory_data()


class TestDeleteMemoryFactSaveFailure:
    def test_raises_on_save_failure(self):
        memory = _make_memory(facts=[{"id": "f1", "content": "test"}])
        with (
            patch("ideer.agents.memory.updater.get_memory_data", return_value=memory),
            patch("ideer.agents.memory.updater._save_memory_to_file", return_value=False),
        ):
            with pytest.raises(OSError, match="Failed to save"):
                delete_memory_fact("f1")


class TestUpdateMemoryFactSaveFailure:
    def test_raises_on_save_failure(self):
        memory = _make_memory(facts=[{"id": "f1", "content": "test", "category": "ctx", "confidence": 0.5}])
        with (
            patch("ideer.agents.memory.updater.get_memory_data", return_value=memory),
            patch("ideer.agents.memory.updater._save_memory_to_file", return_value=False),
        ):
            with pytest.raises(OSError, match="Failed to save"):
                update_memory_fact("f1", content="updated")

    def test_raises_on_empty_content(self):
        memory = _make_memory(facts=[{"id": "f1", "content": "test"}])
        with patch("ideer.agents.memory.updater.get_memory_data", return_value=memory):
            with pytest.raises(ValueError, match="content"):
                update_memory_fact("f1", content="   ")

    def test_category_empty_defaults_to_context(self):
        memory = _make_memory(facts=[{"id": "f1", "content": "test", "category": "old"}])
        with (
            patch("ideer.agents.memory.updater.get_memory_data", return_value=memory),
            patch("ideer.agents.memory.updater._save_memory_to_file", return_value=True),
        ):
            result = update_memory_fact("f1", category="")
        assert result["facts"][0]["category"] == "context"


class TestCreateMemoryFactSaveFailure:
    def test_raises_on_save_failure(self):
        with (
            patch("ideer.agents.memory.updater.get_memory_data", return_value=_make_memory()),
            patch("ideer.agents.memory.updater._save_memory_to_file", return_value=False),
        ):
            with pytest.raises(OSError, match="Failed to save"):
                create_memory_fact(content="test fact")
