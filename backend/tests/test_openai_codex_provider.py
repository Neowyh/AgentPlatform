"""Comprehensive tests for the OpenAI Codex model provider.

Targets 98%+ coverage of ideer.models.openai_codex_provider.
"""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from ideer.models.credential_loader import CodexCliCredential
from ideer.models.openai_codex_provider import (
    CODEX_BASE_URL,
    MAX_RETRIES,
    CodexChatModel,
    _build_usage_metadata,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_model(**overrides) -> CodexChatModel:
    """Build a CodexChatModel with mocked credential loading."""
    defaults = dict(model="gpt-5.4", reasoning_effort="medium", retry_max_attempts=3)
    defaults.update(overrides)

    with patch.object(CodexChatModel, "_load_codex_auth", return_value=CodexCliCredential(access_token="test-token-abc", account_id="acct-12345678")):
        return CodexChatModel(**defaults)


def _make_sse_lines(events: list[dict]) -> list[str]:
    """Build a list of SSE text lines from event dicts."""
    lines = []
    for event in events:
        lines.append(f"data: {json.dumps(event)}")
        lines.append("")  # blank line separator
    return lines


def _build_mock_stream_response(events: list[dict], status_code: int = 200) -> MagicMock:
    """Create a mock httpx response that yields SSE events via iter_lines."""
    lines = _make_sse_lines(events)

    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.is_error = status_code >= 400
    mock_response.raise_for_status = MagicMock()

    if status_code >= 400:
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=mock_response,
        )

    # Use side_effect so each call gets a fresh iterator
    mock_response.iter_lines = MagicMock(side_effect=lambda: iter(lines))
    return mock_response


def _make_stream_ctx(resp: MagicMock) -> MagicMock:
    """Create a mock context manager that yields *resp*."""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=resp)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _make_mock_httpx_client(stream_responses: list[MagicMock]) -> MagicMock:
    """Build a fully-mocked ``httpx.Client`` chain for one or more stream calls.

    *stream_responses* is a list of mock httpx response objects.  Each call to
    ``client.stream(...)`` returns a context manager yielding the next response.
    """
    stream_ctxs = [_make_stream_ctx(r) for r in stream_responses]

    mock_client = MagicMock()
    mock_client.stream = MagicMock(side_effect=stream_ctxs)

    client_ctx = MagicMock()
    client_ctx.__enter__ = MagicMock(return_value=mock_client)
    client_ctx.__exit__ = MagicMock(return_value=False)
    return client_ctx


@contextmanager
def _patch_codex_stream(events: list[dict], status_code: int = 200):
    """Context manager that patches httpx.Client.stream with fake SSE events."""
    mock_resp = _build_mock_stream_response(events, status_code)
    client_ctx = _make_mock_httpx_client([mock_resp])

    with patch("ideer.models.openai_codex_provider.httpx.Client", return_value=client_ctx):
        yield mock_resp


# ---------------------------------------------------------------------------
# _build_usage_metadata
# ---------------------------------------------------------------------------


class TestBuildUsageMetadata:
    """Tests for _build_usage_metadata helper."""

    def test_basic_usage(self):
        result = _build_usage_metadata(
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
            }
        )
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        assert result["total_tokens"] == 150

    def test_total_tokens_defaults_to_sum(self):
        result = _build_usage_metadata(
            {
                "input_tokens": 10,
                "output_tokens": 20,
            }
        )
        assert result["total_tokens"] == 30

    def test_cache_read_tokens(self):
        result = _build_usage_metadata(
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "input_tokens_details": {"cached_tokens": 25},
            }
        )
        assert result["input_token_details"] == {"cache_read": 25}

    def test_reasoning_tokens(self):
        result = _build_usage_metadata(
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "output_tokens_details": {"reasoning_tokens": 10},
            }
        )
        assert result["output_token_details"] == {"reasoning": 10}

    def test_both_cache_and_reasoning(self):
        result = _build_usage_metadata(
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "input_tokens_details": {"cached_tokens": 30},
                "output_tokens_details": {"reasoning_tokens": 15},
            }
        )
        assert result["input_token_details"] == {"cache_read": 30}
        assert result["output_token_details"] == {"reasoning": 15}

    def test_empty_details(self):
        result = _build_usage_metadata(
            {
                "input_tokens": 5,
                "output_tokens": 3,
                "input_tokens_details": {},
                "output_tokens_details": {},
            }
        )
        assert "input_token_details" not in result
        assert "output_token_details" not in result

    def test_none_details(self):
        result = _build_usage_metadata(
            {
                "input_tokens": 5,
                "output_tokens": 3,
                "input_tokens_details": None,
                "output_tokens_details": None,
            }
        )
        assert "input_token_details" not in result
        assert "output_token_details" not in result

    def test_missing_tokens_defaults_to_zero(self):
        result = _build_usage_metadata({})
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 0
        assert result["total_tokens"] == 0


# ---------------------------------------------------------------------------
# CodexChatModel - basic properties
# ---------------------------------------------------------------------------


class TestCodexChatModelProperties:
    def test_is_lc_serializable(self):
        assert CodexChatModel.is_lc_serializable() is True

    def test_llm_type(self):
        model = _make_model()
        assert model._llm_type == "codex-responses"

    def test_default_values(self):
        model = _make_model()
        assert model.model == "gpt-5.4"
        assert model.reasoning_effort == "medium"
        assert model.retry_max_attempts == 3

    def test_codex_base_url(self):
        assert CODEX_BASE_URL == "https://chatgpt.com/backend-api/codex"

    def test_max_retries_constant(self):
        assert MAX_RETRIES == 3


# ---------------------------------------------------------------------------
# _validate_retry_config
# ---------------------------------------------------------------------------


class TestValidateRetryConfig:
    def test_valid_config(self):
        model = _make_model(retry_max_attempts=1)
        # Should not raise
        model._validate_retry_config()

    def test_zero_attempts_raises(self):
        with patch.object(CodexChatModel, "_load_codex_auth", return_value=CodexCliCredential(access_token="t", account_id="a")):
            with pytest.raises(ValueError, match="retry_max_attempts must be >= 1"):
                CodexChatModel(retry_max_attempts=0)

    def test_negative_attempts_raises(self):
        with patch.object(CodexChatModel, "_load_codex_auth", return_value=CodexCliCredential(access_token="t", account_id="a")):
            with pytest.raises(ValueError, match="retry_max_attempts must be >= 1"):
                CodexChatModel(retry_max_attempts=-5)


# ---------------------------------------------------------------------------
# model_post_init
# ---------------------------------------------------------------------------


class TestModelPostInit:
    def test_success_loads_credentials(self):
        cred = CodexCliCredential(access_token="my-token", account_id="my-acct")
        with patch.object(CodexChatModel, "_load_codex_auth", return_value=cred):
            model = CodexChatModel()
            assert model._access_token == "my-token"
            assert model._account_id == "my-acct"

    def test_no_credential_raises(self):
        with patch.object(CodexChatModel, "_load_codex_auth", return_value=None):
            with pytest.raises(ValueError, match="Codex CLI credential not found"):
                CodexChatModel()

    def test_validates_retry_before_loading(self):
        with patch.object(CodexChatModel, "_load_codex_auth") as mock_load:
            with pytest.raises(ValueError, match="retry_max_attempts must be >= 1"):
                CodexChatModel(retry_max_attempts=0)
            mock_load.assert_not_called()


# ---------------------------------------------------------------------------
# _normalize_content
# ---------------------------------------------------------------------------


class TestNormalizeContent:
    def test_string_passthrough(self):
        assert CodexChatModel._normalize_content("hello") == "hello"

    def test_empty_string(self):
        assert CodexChatModel._normalize_content("") == ""

    def test_list_of_strings(self):
        result = CodexChatModel._normalize_content(["a", "b", "c"])
        assert result == "a\nb\nc"

    def test_list_with_empty_strings_filtered(self):
        result = CodexChatModel._normalize_content(["a", "", "b", ""])
        assert result == "a\nb"

    def test_nested_list(self):
        result = CodexChatModel._normalize_content([["x", "y"], "z"])
        assert result == "x\ny\nz"

    def test_dict_with_text_key(self):
        assert CodexChatModel._normalize_content({"text": "hello"}) == "hello"

    def test_dict_with_output_key(self):
        assert CodexChatModel._normalize_content({"output": "world"}) == "world"

    def test_dict_text_takes_precedence_over_output(self):
        result = CodexChatModel._normalize_content({"text": "t", "output": "o"})
        assert result == "t"

    def test_dict_with_nested_content(self):
        result = CodexChatModel._normalize_content({"content": "nested"})
        assert result == "nested"

    def test_dict_with_nested_content_list(self):
        result = CodexChatModel._normalize_content({"content": ["a", "b"]})
        assert result == "a\nb"

    def test_dict_json_fallback(self):
        d = {"key": "val"}
        result = CodexChatModel._normalize_content(d)
        assert json.loads(result) == d

    def test_dict_json_serialization_error(self):
        """When json.dumps raises TypeError, fall back to str()."""

        class NotSerializable:
            pass

        d = {"key": NotSerializable()}
        result = CodexChatModel._normalize_content(d)
        assert isinstance(result, str)

    def test_non_string_non_list_non_dict_json(self):
        result = CodexChatModel._normalize_content(42)
        assert result == "42"

    def test_non_serializable_fallback(self):
        class Bad:
            def __repr__(self):
                return "Bad()"

        result = CodexChatModel._normalize_content(Bad())
        assert isinstance(result, str)

    def test_none_content(self):
        result = CodexChatModel._normalize_content(None)
        assert isinstance(result, str)

    def test_dict_with_content_none(self):
        """dict with content=None should fall through to json.dumps."""
        result = CodexChatModel._normalize_content({"content": None, "other": 1})
        parsed = json.loads(result)
        assert parsed["other"] == 1


# ---------------------------------------------------------------------------
# _convert_messages
# ---------------------------------------------------------------------------


class TestConvertMessages:
    def test_system_message_becomes_instructions(self):
        model = _make_model()
        instructions, items = model._convert_messages([SystemMessage(content="Be helpful")])
        assert instructions == "Be helpful"
        assert items == []

    def test_empty_system_message_uses_default(self):
        model = _make_model()
        instructions, items = model._convert_messages([SystemMessage(content="")])
        assert instructions == "You are a helpful assistant."
        assert items == []

    def test_human_message(self):
        model = _make_model()
        _, items = model._convert_messages([HumanMessage(content="Hi")])
        assert items == [{"role": "user", "content": "Hi"}]

    def test_ai_message_with_content(self):
        model = _make_model()
        _, items = model._convert_messages([AIMessage(content="Hello")])
        assert items == [{"role": "assistant", "content": "Hello"}]

    def test_ai_message_empty_content_skipped(self):
        model = _make_model()
        _, items = model._convert_messages([AIMessage(content="")])
        assert items == []

    def test_ai_message_with_tool_calls(self):
        model = _make_model()
        msg = AIMessage(
            content="",
            tool_calls=[{"name": "search", "args": {"q": "test"}, "id": "tc_1"}],
        )
        _, items = model._convert_messages([msg])
        assert len(items) == 1
        assert items[0]["type"] == "function_call"
        assert items[0]["name"] == "search"
        assert items[0]["call_id"] == "tc_1"
        assert json.loads(items[0]["arguments"]) == {"q": "test"}

    def test_ai_message_tool_call_string_args(self):
        """When tool_calls args is not a dict (e.g. pre-serialised string), the
        source falls through to the ``else`` branch and uses the value directly."""
        model = _make_model()
        # AIMessage validates args as dict, so we mock the tool_calls property
        msg = AIMessage(content="", tool_calls=[{"name": "fn", "args": {"x": 1}, "id": "tc_2"}])
        msg.tool_calls = [{"name": "fn", "args": '{"a":1}', "id": "tc_2"}]
        _, items = model._convert_messages([msg])
        assert items[0]["arguments"] == '{"a":1}'

    def test_ai_message_content_and_tool_calls(self):
        model = _make_model()
        msg = AIMessage(
            content="Thinking...",
            tool_calls=[{"name": "fn", "args": {}, "id": "tc_3"}],
        )
        _, items = model._convert_messages([msg])
        assert len(items) == 2
        assert items[0] == {"role": "assistant", "content": "Thinking..."}
        assert items[1]["type"] == "function_call"

    def test_tool_message(self):
        model = _make_model()
        msg = ToolMessage(content="result", tool_call_id="tc_1")
        _, items = model._convert_messages([msg])
        assert items == [{"type": "function_call_output", "call_id": "tc_1", "output": "result"}]

    def test_multiple_system_messages_joined(self):
        model = _make_model()
        instructions, _ = model._convert_messages(
            [
                SystemMessage(content="Rule 1"),
                SystemMessage(content="Rule 2"),
            ]
        )
        assert instructions == "Rule 1\n\nRule 2"

    def test_mixed_messages(self):
        model = _make_model()
        instructions, items = model._convert_messages(
            [
                SystemMessage(content="System"),
                HumanMessage(content="User"),
                AIMessage(content="Assistant"),
                ToolMessage(content="tool result", tool_call_id="tc_1"),
            ]
        )
        assert instructions == "System"
        assert len(items) == 3


# ---------------------------------------------------------------------------
# _convert_tools
# ---------------------------------------------------------------------------


class TestConvertTools:
    def test_function_type_tool(self):
        model = _make_model()
        tools = [{"type": "function", "function": {"name": "search", "description": "Search", "parameters": {"type": "object"}}}]
        result = model._convert_tools(tools)
        assert result == [{"type": "function", "name": "search", "description": "Search", "parameters": {"type": "object"}}]

    def test_function_type_no_description(self):
        model = _make_model()
        tools = [{"type": "function", "function": {"name": "fn", "parameters": {}}}]
        result = model._convert_tools(tools)
        assert result[0]["description"] == ""

    def test_function_type_no_parameters(self):
        model = _make_model()
        tools = [{"type": "function", "function": {"name": "fn"}}]
        result = model._convert_tools(tools)
        assert result[0]["parameters"] == {}

    def test_name_based_tool(self):
        model = _make_model()
        tools = [{"name": "calc", "description": "Calculate", "parameters": {"type": "object"}}]
        result = model._convert_tools(tools)
        assert result == [{"type": "function", "name": "calc", "description": "Calculate", "parameters": {"type": "object"}}]

    def test_name_based_no_description_no_parameters(self):
        model = _make_model()
        tools = [{"name": "fn"}]
        result = model._convert_tools(tools)
        assert result[0]["description"] == ""
        assert result[0]["parameters"] == {}

    def test_unknown_tool_skipped(self):
        model = _make_model()
        tools = [{"type": "unknown"}]
        result = model._convert_tools(tools)
        assert result == []

    def test_empty_tools(self):
        model = _make_model()
        assert model._convert_tools([]) == []


# ---------------------------------------------------------------------------
# _parse_sse_data_line
# ---------------------------------------------------------------------------


class TestParseSSEDataLine:
    def test_valid_json(self):
        result = CodexChatModel._parse_sse_data_line('data: {"type": "test"}')
        assert result == {"type": "test"}

    def test_non_data_prefix(self):
        assert CodexChatModel._parse_sse_data_line("event: something") is None

    def test_empty_data(self):
        assert CodexChatModel._parse_sse_data_line("data:") is None
        assert CodexChatModel._parse_sse_data_line("data: ") is None

    def test_done_marker(self):
        assert CodexChatModel._parse_sse_data_line("data: [DONE]") is None

    def test_invalid_json(self):
        assert CodexChatModel._parse_sse_data_line("data: {invalid") is None

    def test_non_dict_json(self):
        assert CodexChatModel._parse_sse_data_line("data: [1, 2]") is None
        assert CodexChatModel._parse_sse_data_line('data: "string"') is None
        assert CodexChatModel._parse_sse_data_line("data: 42") is None
        assert CodexChatModel._parse_sse_data_line("data: null") is None

    def test_whitespace_handling(self):
        result = CodexChatModel._parse_sse_data_line('data:   {"a": 1}  ')
        assert result == {"a": 1}

    def test_empty_line(self):
        assert CodexChatModel._parse_sse_data_line("") is None


# ---------------------------------------------------------------------------
# _parse_tool_call_arguments
# ---------------------------------------------------------------------------


class TestParseToolCallArguments:
    def test_dict_arguments(self):
        model = _make_model()
        args, invalid = model._parse_tool_call_arguments({"arguments": {"key": "val"}})
        assert args == {"key": "val"}
        assert invalid is None

    def test_valid_json_string(self):
        model = _make_model()
        args, invalid = model._parse_tool_call_arguments({"arguments": '{"key": "val"}'})
        assert args == {"key": "val"}
        assert invalid is None

    def test_empty_string_defaults(self):
        model = _make_model()
        args, invalid = model._parse_tool_call_arguments({"arguments": ""})
        assert args == {}
        assert invalid is None

    def test_missing_arguments_key(self):
        model = _make_model()
        args, invalid = model._parse_tool_call_arguments({})
        assert args == {}
        assert invalid is None

    def test_invalid_json_string(self):
        model = _make_model()
        args, invalid = model._parse_tool_call_arguments(
            {
                "arguments": "{bad json",
                "name": "my_fn",
                "call_id": "tc_1",
            }
        )
        assert args is None
        assert invalid is not None
        assert invalid["type"] == "invalid_tool_call"
        assert invalid["name"] == "my_fn"
        assert invalid["id"] == "tc_1"
        assert "Failed to parse" in invalid["error"]

    def test_non_dict_json(self):
        model = _make_model()
        args, invalid = model._parse_tool_call_arguments({"arguments": "[1, 2, 3]"})
        assert args is None
        assert invalid is not None
        assert "must decode to a JSON object" in invalid["error"]

    def test_json_null(self):
        model = _make_model()
        args, invalid = model._parse_tool_call_arguments({"arguments": "null"})
        assert args is None
        assert invalid is not None

    def test_type_error_in_json_loads(self):
        """When arguments is a non-string non-dict type that causes TypeError."""
        model = _make_model()
        # Passing an integer as arguments -- json.loads(int) raises TypeError
        args, invalid = model._parse_tool_call_arguments({"arguments": 12345})
        assert args is None
        assert invalid is not None
        assert "Failed to parse" in invalid["error"]


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_message_with_text(self):
        model = _make_model()
        response = {
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "Hello!"}]}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            "model": "gpt-5.4",
        }
        result = model._parse_response(response)
        msg = result.generations[0].message
        assert msg.content == "Hello!"
        assert msg.tool_calls == []
        assert result.llm_output["token_usage"]["prompt_tokens"] == 10

    def test_empty_response(self):
        model = _make_model()
        response = {"output": [], "usage": {}, "model": "gpt-5.4"}
        result = model._parse_response(response)
        msg = result.generations[0].message
        assert msg.content == ""

    def test_reasoning_output(self):
        model = _make_model()
        response = {
            "output": [
                {
                    "type": "reasoning",
                    "summary": [
                        {"type": "summary_text", "text": "Step 1: think"},
                        "Step 2: decide",
                    ],
                }
            ],
            "usage": {},
        }
        result = model._parse_response(response)
        msg = result.generations[0].message
        assert msg.additional_kwargs["reasoning_content"] == "Step 1: thinkStep 2: decide"

    def test_function_call_output(self):
        model = _make_model()
        response = {
            "output": [
                {
                    "type": "function_call",
                    "name": "search",
                    "arguments": '{"q": "test"}',
                    "call_id": "tc_1",
                }
            ],
            "usage": {},
        }
        result = model._parse_response(response)
        msg = result.generations[0].message
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0]["name"] == "search"
        assert msg.tool_calls[0]["id"] == "tc_1"

    def test_invalid_tool_call_output(self):
        model = _make_model()
        response = {
            "output": [
                {
                    "type": "function_call",
                    "name": "bad_fn",
                    "arguments": "{not json",
                    "call_id": "tc_bad",
                }
            ],
            "usage": {},
        }
        result = model._parse_response(response)
        msg = result.generations[0].message
        assert msg.tool_calls == []
        assert len(msg.invalid_tool_calls) == 1
        assert msg.invalid_tool_calls[0]["name"] == "bad_fn"

    def test_no_usage(self):
        model = _make_model()
        response = {"output": []}
        result = model._parse_response(response)
        assert result.generations[0].message.usage_metadata is None

    def test_model_fallback(self):
        model = _make_model()
        response = {"output": [], "usage": {"input_tokens": 1, "output_tokens": 1}}
        result = model._parse_response(response)
        assert result.llm_output["model_name"] == "gpt-5.4"

    def test_multiple_message_parts(self):
        model = _make_model()
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "Part 1. "},
                        {"type": "output_text", "text": "Part 2."},
                    ],
                },
            ],
            "usage": {},
        }
        result = model._parse_response(response)
        assert result.generations[0].message.content == "Part 1. Part 2."

    def test_unknown_output_type_ignored(self):
        model = _make_model()
        response = {
            "output": [
                {"type": "unknown_type", "data": "something"},
            ],
            "usage": {},
        }
        result = model._parse_response(response)
        assert result.generations[0].message.content == ""

    def test_reasoning_with_empty_summary(self):
        model = _make_model()
        response = {
            "output": [
                {"type": "reasoning", "summary": []},
            ],
            "usage": {},
        }
        result = model._parse_response(response)
        assert "reasoning_content" not in result.generations[0].message.additional_kwargs

    def test_function_call_with_dict_arguments(self):
        model = _make_model()
        response = {
            "output": [
                {
                    "type": "function_call",
                    "name": "fn",
                    "arguments": {"key": "val"},
                    "call_id": "tc_dict",
                }
            ],
            "usage": {},
        }
        result = model._parse_response(response)
        assert result.generations[0].message.tool_calls[0]["args"] == {"key": "val"}

    def test_function_call_missing_call_id(self):
        model = _make_model()
        response = {
            "output": [
                {
                    "type": "function_call",
                    "name": "fn",
                    "arguments": "{}",
                }
            ],
            "usage": {},
        }
        result = model._parse_response(response)
        assert result.generations[0].message.tool_calls[0]["id"] == ""


# ---------------------------------------------------------------------------
# _stream_response
# ---------------------------------------------------------------------------


class TestStreamResponse:
    def test_successful_stream_with_completed_event(self):
        model = _make_model()
        completed_event = {
            "type": "response.completed",
            "response": {
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "Hi"}]}],
                "usage": {"input_tokens": 5, "output_tokens": 3},
                "model": "gpt-5.4",
            },
        }
        with _patch_codex_stream([completed_event]):
            result = model._stream_response({}, {})
            assert result["output"][0]["type"] == "message"

    def test_stream_merges_output_items(self):
        model = _make_model()
        events = [
            {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": {"type": "message", "content": [{"type": "output_text", "text": "Merged"}]},
            },
            {
                "type": "response.completed",
                "response": {
                    "output": [],
                    "usage": {},
                    "model": "gpt-5.4",
                },
            },
        ]
        with _patch_codex_stream(events):
            result = model._stream_response({}, {})
            assert result["output"][0]["content"][0]["text"] == "Merged"

    def test_stream_no_completed_raises(self):
        model = _make_model()
        with _patch_codex_stream([{"type": "other"}]):
            with pytest.raises(RuntimeError, match="without response.completed"):
                model._stream_response({}, {})

    def test_stream_merges_with_existing_output(self):
        model = _make_model()
        events = [
            {
                "type": "response.output_item.done",
                "output_index": 1,
                "item": {"type": "function_call", "name": "fn"},
            },
            {
                "type": "response.completed",
                "response": {
                    "output": [{"type": "message", "content": []}],
                    "usage": {},
                },
            },
        ]
        with _patch_codex_stream(events):
            result = model._stream_response({}, {})
            assert len(result["output"]) == 2
            assert result["output"][0]["type"] == "message"
            assert result["output"][1]["type"] == "function_call"

    def test_stream_non_dict_item_in_existing_output_replaced(self):
        model = _make_model()
        events = [
            {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": {"type": "message", "content": [{"type": "output_text", "text": "Replaced"}]},
            },
            {
                "type": "response.completed",
                "response": {
                    "output": [None],  # non-dict existing item
                    "usage": {},
                },
            },
        ]
        with _patch_codex_stream(events):
            result = model._stream_response({}, {})
            assert result["output"][0]["content"][0]["text"] == "Replaced"

    def test_stream_skips_non_data_lines(self):
        model = _make_model()
        # The _parse_sse_data_line will filter these out
        events = [
            {
                "type": "response.completed",
                "response": {"output": [], "usage": {}},
            },
        ]
        with _patch_codex_stream(events):
            result = model._stream_response({}, {})
            assert "output" in result

    def test_http_error_raises(self):
        model = _make_model()
        error_resp = MagicMock()
        error_resp.status_code = 403
        error_resp.raise_for_status.side_effect = httpx.HTTPStatusError("Forbidden", request=MagicMock(), response=error_resp)
        error_resp.is_error = True

        stream_ctx = MagicMock()
        stream_ctx.__enter__ = MagicMock(return_value=error_resp)
        stream_ctx.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=stream_ctx)

        client_ctx = MagicMock()
        client_ctx.__enter__ = MagicMock(return_value=mock_client)
        client_ctx.__exit__ = MagicMock(return_value=False)

        with patch("ideer.models.openai_codex_provider.httpx.Client", return_value=client_ctx):
            with pytest.raises(httpx.HTTPStatusError):
                model._stream_response({}, {})


# ---------------------------------------------------------------------------
# _call_codex_api
# ---------------------------------------------------------------------------


class TestCallCodexApi:
    def test_successful_call(self):
        model = _make_model()
        completed = {
            "type": "response.completed",
            "response": {
                "output": [],
                "usage": {},
                "model": "gpt-5.4",
            },
        }
        with _patch_codex_stream([completed]):
            result = model._call_codex_api([HumanMessage(content="Hi")])
            assert "output" in result

    def test_with_tools(self):
        model = _make_model()
        completed = {
            "type": "response.completed",
            "response": {"output": [], "usage": {}},
        }
        tools = [{"type": "function", "function": {"name": "fn"}}]
        with _patch_codex_stream([completed]):
            model._call_codex_api([HumanMessage(content="Hi")], tools=tools)

    def test_reasoning_effort_none(self):
        model = _make_model(reasoning_effort="none")
        completed = {
            "type": "response.completed",
            "response": {"output": [], "usage": {}},
        }
        with _patch_codex_stream([completed]):
            result = model._call_codex_api([HumanMessage(content="Hi")])
            assert "output" in result

    def test_retry_on_429(self):
        model = _make_model(retry_max_attempts=3)
        success_response = {"output": [], "usage": {}, "model": "gpt-5.4"}

        error_resp = MagicMock()
        error_resp.status_code = 429

        call_count = 0

        def mock_stream(headers, payload):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=error_resp)
            return success_response

        with patch.object(model, "_stream_response", side_effect=mock_stream):
            with patch("ideer.models.openai_codex_provider.time.sleep"):
                result = model._call_codex_api([HumanMessage(content="Hi")])
                assert "output" in result

    def test_retry_on_500(self):
        model = _make_model(retry_max_attempts=2)
        success_response = {"output": [], "usage": {}, "model": "gpt-5.4"}

        error_resp = MagicMock()
        error_resp.status_code = 500

        call_count = 0

        def mock_stream(headers, payload):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError("Server error", request=MagicMock(), response=error_resp)
            return success_response

        with patch.object(model, "_stream_response", side_effect=mock_stream):
            with patch("ideer.models.openai_codex_provider.time.sleep"):
                result = model._call_codex_api([HumanMessage(content="Hi")])
                assert "output" in result

    def test_retry_on_529(self):
        model = _make_model(retry_max_attempts=2)
        success_response = {"output": [], "usage": {}, "model": "gpt-5.4"}

        error_resp = MagicMock()
        error_resp.status_code = 529

        call_count = 0

        def mock_stream(headers, payload):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError("Overloaded", request=MagicMock(), response=error_resp)
            return success_response

        with patch.object(model, "_stream_response", side_effect=mock_stream):
            with patch("ideer.models.openai_codex_provider.time.sleep"):
                result = model._call_codex_api([HumanMessage(content="Hi")])
                assert "output" in result

    def test_retry_exhausted_raises(self):
        model = _make_model(retry_max_attempts=2)

        error_resp = MagicMock()
        error_resp.status_code = 429
        error_resp.raise_for_status.side_effect = httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=error_resp)
        error_resp.is_error = True

        stream_ctx = MagicMock()
        stream_ctx.__enter__ = MagicMock(return_value=error_resp)
        stream_ctx.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=stream_ctx)

        client_ctx = MagicMock()
        client_ctx.__enter__ = MagicMock(return_value=mock_client)
        client_ctx.__exit__ = MagicMock(return_value=False)

        with patch("ideer.models.openai_codex_provider.httpx.Client", return_value=client_ctx):
            with patch("ideer.models.openai_codex_provider.time.sleep"):
                with pytest.raises(httpx.HTTPStatusError):
                    model._call_codex_api([HumanMessage(content="Hi")])

    def test_non_retryable_error_raises_immediately(self):
        model = _make_model(retry_max_attempts=3)

        error_resp = MagicMock()
        error_resp.status_code = 403
        error_resp.raise_for_status.side_effect = httpx.HTTPStatusError("Forbidden", request=MagicMock(), response=error_resp)
        error_resp.is_error = True

        stream_ctx = MagicMock()
        stream_ctx.__enter__ = MagicMock(return_value=error_resp)
        stream_ctx.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=stream_ctx)

        client_ctx = MagicMock()
        client_ctx.__enter__ = MagicMock(return_value=mock_client)
        client_ctx.__exit__ = MagicMock(return_value=False)

        with patch("ideer.models.openai_codex_provider.httpx.Client", return_value=client_ctx):
            with pytest.raises(httpx.HTTPStatusError):
                model._call_codex_api([HumanMessage(content="Hi")])

    def test_generic_exception_propagates(self):
        model = _make_model(retry_max_attempts=3)

        mock_client = MagicMock()
        mock_client.stream.side_effect = ConnectionError("Network down")

        client_ctx = MagicMock()
        client_ctx.__enter__ = MagicMock(return_value=mock_client)
        client_ctx.__exit__ = MagicMock(return_value=False)

        with patch("ideer.models.openai_codex_provider.httpx.Client", return_value=client_ctx):
            with pytest.raises(ConnectionError, match="Network down"):
                model._call_codex_api([HumanMessage(content="Hi")])

    def test_wait_time_exponential_backoff(self):
        model = _make_model(retry_max_attempts=3)

        error_resp = MagicMock()
        error_resp.status_code = 429
        error_resp.raise_for_status.side_effect = httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=error_resp)
        error_resp.is_error = True

        stream_ctx = MagicMock()
        stream_ctx.__enter__ = MagicMock(return_value=error_resp)
        stream_ctx.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=stream_ctx)

        client_ctx = MagicMock()
        client_ctx.__enter__ = MagicMock(return_value=mock_client)
        client_ctx.__exit__ = MagicMock(return_value=False)

        with patch("ideer.models.openai_codex_provider.httpx.Client", return_value=client_ctx):
            with patch("ideer.models.openai_codex_provider.time.sleep") as mock_sleep:
                with pytest.raises(httpx.HTTPStatusError):
                    model._call_codex_api([HumanMessage(content="Hi")])
                # First retry: 2000 * 2^0 = 2000ms -> 2.0s
                # Second retry: 2000 * 2^1 = 4000ms -> 4.0s
                calls = [c.args[0] for c in mock_sleep.call_args_list]
                assert calls[0] == 2.0
                assert calls[1] == 4.0


# ---------------------------------------------------------------------------
# _generate
# ---------------------------------------------------------------------------


class TestGenerate:
    def test_generate_calls_api_and_parses(self):
        model = _make_model()
        mock_response = {
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "Result"}]}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "model": "gpt-5.4",
        }
        with patch.object(model, "_call_codex_api", return_value=mock_response) as mock_api:
            result = model._generate([HumanMessage(content="Hi")])
            mock_api.assert_called_once_with([HumanMessage(content="Hi")], tools=None)
            assert result.generations[0].message.content == "Result"

    def test_generate_passes_tools(self):
        model = _make_model()
        mock_response = {"output": [], "usage": {}}
        tools = [{"name": "fn"}]
        with patch.object(model, "_call_codex_api", return_value=mock_response) as mock_api:
            model._generate([HumanMessage(content="Hi")], **{"tools": tools})
            mock_api.assert_called_once_with([HumanMessage(content="Hi")], tools=tools)

    def test_generate_with_stop_and_run_manager(self):
        model = _make_model()
        mock_response = {"output": [], "usage": {}}
        with patch.object(model, "_call_codex_api", return_value=mock_response):
            result = model._generate(
                [HumanMessage(content="Hi")],
                stop=["STOP"],
                run_manager=MagicMock(),
            )
            assert result is not None


# ---------------------------------------------------------------------------
# bind_tools
# ---------------------------------------------------------------------------


class TestBindTools:
    def test_bind_with_base_tool(self):
        model = _make_model()

        mock_tool = MagicMock(spec=BaseTool)
        mock_tool.name = "search"
        mock_tool.description = "Search the web"

        with patch("langchain_core.utils.function_calling.convert_to_openai_function") as mock_convert:
            mock_convert.return_value = {
                "name": "search",
                "description": "Search the web",
                "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
            }
            result = model.bind_tools([mock_tool])
            assert result.bound is model
            assert "tools" in result.kwargs
            assert result.kwargs["tools"][0]["name"] == "search"

    def test_bind_with_base_tool_convert_exception(self):
        model = _make_model()

        mock_tool = MagicMock(spec=BaseTool)
        mock_tool.name = "broken"
        mock_tool.description = "Broken tool"

        with patch("langchain_core.utils.function_calling.convert_to_openai_function", side_effect=Exception("fail")):
            result = model.bind_tools([mock_tool])
            tool = result.kwargs["tools"][0]
            assert tool["name"] == "broken"
            assert tool["description"] == "Broken tool"
            assert tool["parameters"] == {"type": "object", "properties": {}}

    def test_bind_with_dict_function(self):
        model = _make_model()
        tool_dict = {
            "type": "function",
            "function": {"name": "calc", "description": "Calculate", "parameters": {}},
        }
        result = model.bind_tools([tool_dict])
        assert result.kwargs["tools"][0]["name"] == "calc"

    def test_bind_with_plain_dict(self):
        model = _make_model()
        tool_dict = {"name": "plain", "description": "Plain tool"}
        result = model.bind_tools([tool_dict])
        assert result.kwargs["tools"][0] is tool_dict

    def test_bind_with_mixed_tools(self):
        model = _make_model()

        mock_tool = MagicMock(spec=BaseTool)
        mock_tool.name = "search"
        mock_tool.description = "Search"

        dict_fn = {
            "type": "function",
            "function": {"name": "calc", "description": "Calc"},
        }
        plain_dict = {"name": "plain"}

        with patch("langchain_core.utils.function_calling.convert_to_openai_function") as mock_convert:
            mock_convert.return_value = {"name": "search", "description": "Search", "parameters": {}}
            result = model.bind_tools([mock_tool, dict_fn, plain_dict])
            assert len(result.kwargs["tools"]) == 3


# ---------------------------------------------------------------------------
# Integration-style: end-to-end _generate via mocked stream
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_full_generate_flow(self):
        model = _make_model()
        completed = {
            "type": "response.completed",
            "response": {
                "output": [
                    {"type": "reasoning", "summary": [{"type": "summary_text", "text": "Thinking..."}]},
                    {"type": "message", "content": [{"type": "output_text", "text": "The answer is 42."}]},
                ],
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "total_tokens": 120,
                    "input_tokens_details": {"cached_tokens": 50},
                    "output_tokens_details": {"reasoning_tokens": 10},
                },
                "model": "gpt-5.4",
            },
        }
        with _patch_codex_stream([completed]):
            result = model._generate(
                [
                    SystemMessage(content="You are a math tutor."),
                    HumanMessage(content="What is 6*7?"),
                ]
            )
            msg = result.generations[0].message
            assert msg.content == "The answer is 42."
            assert msg.additional_kwargs["reasoning_content"] == "Thinking..."
            assert msg.usage_metadata["input_tokens"] == 100
            assert msg.usage_metadata["output_tokens"] == 20
            assert msg.usage_metadata["input_token_details"]["cache_read"] == 50
            assert msg.usage_metadata["output_token_details"]["reasoning"] == 10
            assert result.llm_output["model_name"] == "gpt-5.4"

    def test_full_generate_with_tool_calls(self):
        model = _make_model()
        completed = {
            "type": "response.completed",
            "response": {
                "output": [
                    {
                        "type": "function_call",
                        "name": "search",
                        "arguments": '{"query": "weather"}',
                        "call_id": "tc_weather",
                    },
                ],
                "usage": {"input_tokens": 50, "output_tokens": 15, "total_tokens": 65},
                "model": "gpt-5.4",
            },
        }
        with _patch_codex_stream([completed]):
            result = model._generate([HumanMessage(content="What is the weather?")])
            msg = result.generations[0].message
            assert len(msg.tool_calls) == 1
            assert msg.tool_calls[0]["name"] == "search"
            assert msg.tool_calls[0]["args"] == {"query": "weather"}

    def test_full_generate_with_streamed_items(self):
        model = _make_model()
        events = [
            {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": {"type": "message", "content": [{"type": "output_text", "text": "Streamed!"}]},
            },
            {
                "type": "response.completed",
                "response": {
                    "output": [],
                    "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                    "model": "gpt-5.4",
                },
            },
        ]
        with _patch_codex_stream(events):
            result = model._generate([HumanMessage(content="Hello")])
            msg = result.generations[0].message
            assert msg.content == "Streamed!"
