"""Extra coverage tests for prompt.py missed lines.

Targets: 11-12, 175, 180-182, 194-195, 212, 219-234, 242-257, 278, 281,
         300-304, 313-315, 329-363
"""

from unittest.mock import MagicMock, patch

from ideer.agents.memory.prompt import (
    _coerce_confidence,
    _count_tokens,
    format_conversation_for_update,
    format_memory_for_injection,
)

# --- Lines 11-12, 175: tiktoken not available fallback ---


def test_count_tokens_fallback_when_tiktoken_unavailable():
    """Lines 174-175: Falls back to char//4 when tiktoken is not available."""
    with patch("ideer.agents.memory.prompt.TIKTOKEN_AVAILABLE", False):
        result = _count_tokens("hello world test")
    assert result == len("hello world test") // 4


# --- Lines 180-182: tiktoken exception fallback ---


def test_count_tokens_fallback_on_tiktoken_exception():
    """Lines 180-182: Falls back to char//4 when tiktoken raises."""
    with (
        patch("ideer.agents.memory.prompt.TIKTOKEN_AVAILABLE", True),
        patch("ideer.agents.memory.prompt.tiktoken.get_encoding", side_effect=RuntimeError("bad encoding")),
    ):
        result = _count_tokens("hello world test")
    assert result == len("hello world test") // 4


# --- Lines 194-195: _coerce_confidence with non-finite values ---


def test_coerce_confidence_non_finite_returns_default():
    """Lines 196-197: Non-finite values fall back to default."""
    assert _coerce_confidence(float("nan"), default=0.5) == 0.5
    assert _coerce_confidence(float("inf"), default=0.3) == 0.3
    assert _coerce_confidence(float("-inf"), default=0.3) == 0.3


def test_coerce_confidence_type_error_returns_default():
    """Line 194-195: TypeError falls back to default."""
    assert _coerce_confidence(None, default=0.5) == 0.5
    assert _coerce_confidence("not_a_number", default=0.7) == 0.7


# --- Line 212: format_memory_for_injection with empty data ---


def test_format_memory_for_injection_empty_data():
    """Line 212: Returns empty string for empty/falsy memory_data."""
    assert format_memory_for_injection({}) == ""
    assert format_memory_for_injection(None) == ""
    assert format_memory_for_injection({"user": {}, "history": {}}) == ""


# --- Lines 219-234: user context sections ---


def test_format_memory_includes_all_user_sections():
    """Lines 219-234: workContext, personalContext, topOfMind are included."""
    memory_data = {
        "user": {
            "workContext": {"summary": "Software engineer at TechCorp"},
            "personalContext": {"summary": "Bilingual EN/ZH"},
            "topOfMind": {"summary": "Building memory system for iDeer"},
        },
        "history": {},
        "facts": [],
    }
    result = format_memory_for_injection(memory_data, max_tokens=2000)
    assert "Work: Software engineer at TechCorp" in result
    assert "Personal: Bilingual EN/ZH" in result
    assert "Current Focus: Building memory system for iDeer" in result


# --- Lines 242-257: history sections ---


def test_format_memory_includes_all_history_sections():
    """Lines 242-257: recentMonths, earlierContext, longTermBackground are included."""
    memory_data = {
        "user": {},
        "history": {
            "recentMonths": {"summary": "Explored LangGraph"},
            "earlierContext": {"summary": "Built REST APIs"},
            "longTermBackground": {"summary": "10 years Python experience"},
        },
        "facts": [],
    }
    result = format_memory_for_injection(memory_data, max_tokens=2000)
    assert "Recent: Explored LangGraph" in result
    assert "Earlier: Built REST APIs" in result
    assert "Background: 10 years Python experience" in result


# --- Lines 278, 281: facts with non-string or empty content ---


def test_format_memory_skips_facts_with_non_string_content():
    """Line 278: Facts with non-string content are skipped."""
    memory_data = {
        "facts": [
            {"content": 42, "category": "knowledge", "confidence": 0.9},
            {"content": "valid", "category": "context", "confidence": 0.8},
        ],
    }
    result = format_memory_for_injection(memory_data, max_tokens=2000)
    assert "42" not in result
    assert "valid" in result


def test_format_memory_skips_facts_with_empty_content():
    """Line 281: Facts with empty string content are skipped."""
    memory_data = {
        "facts": [
            {"content": "   ", "category": "knowledge", "confidence": 0.9},
            {"content": "real fact", "category": "context", "confidence": 0.8},
        ],
    }
    result = format_memory_for_injection(memory_data, max_tokens=2000)
    assert "real fact" in result


# --- Lines 300-304: correction facts with sourceError ---


def test_format_memory_correction_with_source_error():
    """Lines 300-304: Correction facts with sourceError show 'avoid:' prefix."""
    memory_data = {
        "facts": [
            {
                "content": "Use make dev",
                "category": "correction",
                "confidence": 0.95,
                "sourceError": "Previously used npm start",
            },
        ],
    }
    result = format_memory_for_injection(memory_data, max_tokens=2000)
    assert "avoid: Previously used npm start" in result


def test_format_memory_correction_without_source_error():
    """Lines 300-304: Correction facts without sourceError render normally."""
    memory_data = {
        "facts": [
            {
                "content": "Use make dev",
                "category": "correction",
                "confidence": 0.95,
            },
        ],
    }
    result = format_memory_for_injection(memory_data, max_tokens=2000)
    assert "avoid:" not in result
    assert "Use make dev" in result


def test_format_memory_correction_with_empty_source_error():
    """Lines 300-304: Correction facts with empty sourceError render normally."""
    memory_data = {
        "facts": [
            {
                "content": "Use make dev",
                "category": "correction",
                "confidence": 0.95,
                "sourceError": "   ",
            },
        ],
    }
    result = format_memory_for_injection(memory_data, max_tokens=2000)
    assert "avoid:" not in result


# --- Lines 313-315: token truncation ---


def test_format_memory_truncates_when_over_token_limit(monkeypatch):
    """Lines 313-315: Truncates result when it exceeds max_tokens."""
    monkeypatch.setattr("ideer.agents.memory.prompt._count_tokens", lambda text, **kw: len(text))
    memory_data = {
        "user": {
            "workContext": {"summary": "A" * 500},
        },
        "history": {},
        "facts": [],
    }
    result = format_memory_for_injection(memory_data, max_tokens=100)
    assert result.endswith("\n...")
    assert len(result) < 200  # well under the original size


# --- Lines 329-363: format_conversation_for_update ---


def test_format_conversation_for_update_basic():
    """Lines 329-363: Formats human and AI messages."""
    human = MagicMock()
    human.type = "human"
    human.content = "Hello"

    ai = MagicMock()
    ai.type = "ai"
    ai.content = "Hi there"

    result = format_conversation_for_update([human, ai])
    assert "User: Hello" in result
    assert "Assistant: Hi there" in result


def test_format_conversation_for_update_list_content():
    """Lines 335-344: Handles list content (multimodal)."""
    msg = MagicMock()
    msg.type = "human"
    msg.content = ["text part", {"type": "text", "text": "block part"}]

    result = format_conversation_for_update([msg])
    assert "text part" in result
    assert "block part" in result


def test_format_conversation_for_update_strips_uploaded_files():
    """Lines 349-352: Strips uploaded_files tags from human messages."""
    msg = MagicMock()
    msg.type = "human"
    msg.content = "<uploaded_files>/mnt/user-data/uploads/file.pdf</uploaded_files>\nWhat is this?"

    result = format_conversation_for_update([msg])
    assert "uploaded_files" not in result
    assert "What is this?" in result


def test_format_conversation_for_update_skips_upload_only_messages():
    """Lines 349-352: Skips messages that are only upload tags."""
    msg = MagicMock()
    msg.type = "human"
    msg.content = "<uploaded_files>/mnt/user-data/uploads/file.pdf</uploaded_files>"

    result = format_conversation_for_update([msg])
    assert result == ""


def test_format_conversation_for_update_truncates_long_messages():
    """Lines 355-356: Truncates messages longer than 1000 chars."""
    msg = MagicMock()
    msg.type = "ai"
    msg.content = "A" * 1500

    result = format_conversation_for_update([msg])
    assert "..." in result
    assert len(result) < 1200


def test_format_conversation_for_update_ignores_unknown_roles():
    """Lines 358-361: Ignores messages with unknown roles."""
    msg = MagicMock()
    msg.type = "system"
    msg.content = "System message"

    result = format_conversation_for_update([msg])
    assert "System message" not in result


def test_format_conversation_for_update_handles_fallback_content():
    """Lines 333: Falls back to str(msg) when no content attr."""

    class NoContentMsg:
        type = "human"

        def __str__(self):
            return "fallback content"

    result = format_conversation_for_update([NoContentMsg()])
    assert "fallback content" in result


def test_format_memory_facts_with_mixed_dict_and_non_dict():
    """Facts list containing non-dict entries is handled."""
    memory_data = {
        "facts": [
            "not a dict",
            {"content": "valid fact", "category": "context", "confidence": 0.8},
        ],
    }
    result = format_memory_for_injection(memory_data, max_tokens=2000)
    assert "valid fact" in result
