"""Comprehensive tests for ideer.models.vllm_provider.

Covers every function and code path:
  - _normalize_vllm_chat_template_kwargs
  - _reasoning_to_text
  - _convert_delta_to_message_chunk_with_reasoning
  - _restore_reasoning_field
  - VllmChatModel._llm_type, _get_request_payload, _create_chat_result,
    _convert_chunk_to_generation_chunk
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import openai
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessageChunk,
    ChatMessageChunk,
    FunctionMessageChunk,
    HumanMessage,
    HumanMessageChunk,
    SystemMessageChunk,
    ToolMessageChunk,
)
from langchain_openai import ChatOpenAI

from ideer.models.vllm_provider import (
    VllmChatModel,
    _convert_delta_to_message_chunk_with_reasoning,
    _normalize_vllm_chat_template_kwargs,
    _reasoning_to_text,
    _restore_reasoning_field,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_model(**overrides: Any) -> VllmChatModel:
    return VllmChatModel(
        model="Qwen/QwQ-32B",
        api_key="dummy",
        base_url="http://localhost:8000/v1",
        **overrides,
    )


# ===================================================================
# _normalize_vllm_chat_template_kwargs
# ===================================================================


class TestNormalizeVllmChatTemplateKwargs:
    """Tests for _normalize_vllm_chat_template_kwargs."""

    def test_no_extra_body_is_noop(self):
        payload: dict[str, Any] = {"messages": []}
        _normalize_vllm_chat_template_kwargs(payload)
        assert "extra_body" not in payload

    def test_extra_body_not_dict_is_noop(self):
        payload: dict[str, Any] = {"extra_body": "not-a-dict"}
        _normalize_vllm_chat_template_kwargs(payload)
        assert payload["extra_body"] == "not-a-dict"

    def test_no_chat_template_kwargs_is_noop(self):
        payload: dict[str, Any] = {"extra_body": {"other": True}}
        _normalize_vllm_chat_template_kwargs(payload)
        assert payload["extra_body"] == {"other": True}

    def test_chat_template_kwargs_not_dict_is_noop(self):
        payload: dict[str, Any] = {"extra_body": {"chat_template_kwargs": "bad"}}
        _normalize_vllm_chat_template_kwargs(payload)
        assert payload["extra_body"]["chat_template_kwargs"] == "bad"

    def test_no_thinking_key_is_noop(self):
        payload: dict[str, Any] = {
            "extra_body": {"chat_template_kwargs": {"enable_thinking": True, "foo": "bar"}},
        }
        _normalize_vllm_chat_template_kwargs(payload)
        assert payload["extra_body"]["chat_template_kwargs"] == {"enable_thinking": True, "foo": "bar"}

    def test_thinking_true_normalized_to_enable_thinking(self):
        payload: dict[str, Any] = {
            "extra_body": {"chat_template_kwargs": {"thinking": True}},
        }
        _normalize_vllm_chat_template_kwargs(payload)
        assert payload["extra_body"]["chat_template_kwargs"] == {"enable_thinking": True}
        assert "thinking" not in payload["extra_body"]["chat_template_kwargs"]

    def test_thinking_false_normalized_to_enable_thinking(self):
        payload: dict[str, Any] = {
            "extra_body": {"chat_template_kwargs": {"thinking": False}},
        }
        _normalize_vllm_chat_template_kwargs(payload)
        assert payload["extra_body"]["chat_template_kwargs"] == {"enable_thinking": False}

    def test_thinking_does_not_overwrite_existing_enable_thinking(self):
        payload: dict[str, Any] = {
            "extra_body": {"chat_template_kwargs": {"thinking": True, "enable_thinking": False}},
        }
        _normalize_vllm_chat_template_kwargs(payload)
        # enable_thinking should keep its original value (False), not be overwritten by thinking (True)
        assert payload["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
        assert "thinking" not in payload["extra_body"]["chat_template_kwargs"]

    def test_thinking_with_extra_keys_preserved(self):
        payload: dict[str, Any] = {
            "extra_body": {"chat_template_kwargs": {"thinking": True, "custom_key": 42}},
        }
        _normalize_vllm_chat_template_kwargs(payload)
        assert payload["extra_body"]["chat_template_kwargs"] == {
            "enable_thinking": True,
            "custom_key": 42,
        }


# ===================================================================
# _reasoning_to_text
# ===================================================================


class TestReasoningToText:
    """Tests for _reasoning_to_text."""

    def test_string_input(self):
        assert _reasoning_to_text("hello") == "hello"

    def test_empty_string(self):
        assert _reasoning_to_text("") == ""

    def test_list_of_strings(self):
        assert _reasoning_to_text(["a", "b", "c"]) == "abc"

    def test_list_with_empty_strings_filtered(self):
        assert _reasoning_to_text(["a", "", "b", ""]) == "ab"

    def test_list_with_nested_structures(self):
        result = _reasoning_to_text([{"text": "x"}, "y", {"content": "z"}])
        assert result == "xyz"

    def test_list_with_all_empty_items(self):
        assert _reasoning_to_text(["", "", ""]) == ""

    def test_dict_with_text_key(self):
        assert _reasoning_to_text({"text": "hello"}) == "hello"

    def test_dict_with_content_key(self):
        assert _reasoning_to_text({"content": "world"}) == "world"

    def test_dict_with_reasoning_key(self):
        assert _reasoning_to_text({"reasoning": "thought"}) == "thought"

    def test_dict_text_takes_precedence(self):
        assert _reasoning_to_text({"text": "first", "content": "second"}) == "first"

    def test_dict_content_takes_precedence_over_reasoning(self):
        assert _reasoning_to_text({"content": "second", "reasoning": "third"}) == "second"

    def test_dict_with_nested_dict_value(self):
        result = _reasoning_to_text({"text": {"content": "nested"}})
        assert result == "nested"

    def test_dict_with_list_value_recursed(self):
        result = _reasoning_to_text({"text": ["a", "b"]})
        assert result == "ab"

    def test_dict_no_known_keys_falls_back_to_json_dumps(self):
        result = _reasoning_to_text({"unknown": "value"})
        parsed = json.loads(result)
        assert parsed == {"unknown": "value"}

    def test_dict_with_non_serializable_value_falls_back_to_str(self):
        # set is not JSON-serializable
        bad = {"key": object()}
        result = _reasoning_to_text(bad)
        assert isinstance(result, str)

    def test_dict_known_key_with_none_value_skips(self):
        # text=None, content=None, reasoning=None => json.dumps fallback
        result = _reasoning_to_text({"text": None, "content": None, "reasoning": None, "x": 1})
        parsed = json.loads(result)
        assert parsed["x"] == 1

    def test_dict_known_key_with_non_string_non_none_recurses(self):
        result = _reasoning_to_text({"text": [1, 2, 3]})
        assert result == "123"

    def test_integer_input_json_dumps(self):
        assert _reasoning_to_text(42) == "42"

    def test_list_input_recurses_and_joins(self):
        # [1, 2] is a list so it recurses: _reasoning_to_text(1) -> "1", _reasoning_to_text(2) -> "2"
        assert _reasoning_to_text([1, 2]) == "12"

    def test_non_serializable_input_falls_back_to_str(self):
        result = _reasoning_to_text(object())
        assert isinstance(result, str)

    def test_none_input_json_dumps(self):
        assert _reasoning_to_text(None) == "null"

    def test_bool_input(self):
        assert _reasoning_to_text(True) == "true"


# ===================================================================
# _convert_delta_to_message_chunk_with_reasoning
# ===================================================================


class TestConvertDeltaToMessageChunkWithReasoning:
    """Tests for _convert_delta_to_message_chunk_with_reasoning."""

    def test_user_role(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"role": "user", "content": "hi", "id": "msg-1"},
            AIMessageChunk,
        )
        assert isinstance(result, HumanMessageChunk)
        assert result.content == "hi"
        assert result.id == "msg-1"

    def test_assistant_role(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"role": "assistant", "content": "reply", "id": "msg-2"},
            AIMessageChunk,
        )
        assert isinstance(result, AIMessageChunk)
        assert result.content == "reply"

    def test_system_role(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"role": "system", "content": "sys", "id": "msg-3"},
            SystemMessageChunk,
        )
        assert isinstance(result, SystemMessageChunk)
        assert result.content == "sys"

    def test_developer_role(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"role": "developer", "content": "dev", "id": "msg-4"},
            SystemMessageChunk,
        )
        assert isinstance(result, SystemMessageChunk)
        assert result.additional_kwargs["__openai_role__"] == "developer"

    def test_function_role(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"role": "function", "content": "fn", "name": "my_func", "id": "msg-5"},
            FunctionMessageChunk,
        )
        assert isinstance(result, FunctionMessageChunk)
        assert result.name == "my_func"

    def test_tool_role(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"role": "tool", "content": "out", "tool_call_id": "tc-1", "id": "msg-6"},
            ToolMessageChunk,
        )
        assert isinstance(result, ToolMessageChunk)
        assert result.tool_call_id == "tc-1"

    def test_unknown_role_with_chat_message_chunk_default(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"role": "custom_role", "content": "data", "id": "msg-7"},
            ChatMessageChunk,
        )
        assert isinstance(result, ChatMessageChunk)
        assert result.content == "data"

    def test_no_role_falls_back_to_default_class(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"content": "data", "id": "msg-8"},
            HumanMessageChunk,
        )
        assert isinstance(result, HumanMessageChunk)

    def test_no_role_with_chat_message_chunk_default(self):
        """When role is empty string but default_class is ChatMessageChunk, still uses ChatMessageChunk."""
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"role": "custom", "content": "fallback"},
            ChatMessageChunk,
        )
        assert isinstance(result, ChatMessageChunk)

    def test_no_role_falls_through_to_default_class(self):
        """When no role and default_class is not a special type, uses default_class."""
        # Use HumanMessageChunk as default since it matches the "user" branch
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"content": "fallback"},
            HumanMessageChunk,
        )
        assert isinstance(result, HumanMessageChunk)

    def test_fallback_to_default_class_when_no_role_and_not_known_type(self):
        """Line 147: when role is falsy and default_class is not any known type.
        We create a minimal custom chunk class that accepts content and id."""

        # Create a custom BaseMessageChunk subclass with a fixed type
        class CustomMessageChunk(BaseMessageChunk):
            type: str = "custom"

        result = _convert_delta_to_message_chunk_with_reasoning(
            {"content": "fallback"},
            CustomMessageChunk,
        )
        assert isinstance(result, CustomMessageChunk)
        assert result.content == "fallback"

    def test_reasoning_preserved_in_assistant_chunk(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {
                "role": "assistant",
                "content": "ans",
                "reasoning": "I thought about it",
            },
            AIMessageChunk,
        )
        assert result.additional_kwargs["reasoning"] == "I thought about it"
        assert result.additional_kwargs["reasoning_content"] == "I thought about it"

    def test_reasoning_dict_preserved(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {
                "role": "assistant",
                "content": "ans",
                "reasoning": {"text": "deep thought"},
            },
            AIMessageChunk,
        )
        assert result.additional_kwargs["reasoning"] == {"text": "deep thought"}
        assert result.additional_kwargs["reasoning_content"] == "deep thought"

    def test_empty_reasoning_no_reasoning_content_key(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {
                "role": "assistant",
                "content": "ans",
                "reasoning": "",
            },
            AIMessageChunk,
        )
        assert result.additional_kwargs["reasoning"] == ""
        assert "reasoning_content" not in result.additional_kwargs

    def test_function_call_none_name_normalized(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {
                "role": "assistant",
                "content": "",
                "function_call": {"name": None, "arguments": "{}"},
            },
            AIMessageChunk,
        )
        assert result.additional_kwargs["function_call"]["name"] == ""

    def test_function_call_with_valid_name(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {
                "role": "assistant",
                "content": "",
                "function_call": {"name": "my_func", "arguments": "{}"},
            },
            AIMessageChunk,
        )
        assert result.additional_kwargs["function_call"]["name"] == "my_func"

    def test_tool_calls_parsed(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {"name": "bash", "arguments": '{"cmd":"ls"}'},
                        "id": "tc-1",
                        "index": 0,
                    }
                ],
            },
            AIMessageChunk,
        )
        assert len(result.tool_call_chunks) == 1
        # tool_call_chunk returns a dict
        assert result.tool_call_chunks[0]["name"] == "bash"

    def test_tool_calls_key_error_passes(self):
        """Malformed tool_call missing 'function' key is silently skipped."""
        result = _convert_delta_to_message_chunk_with_reasoning(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"bad_key": True, "index": 0}],
            },
            AIMessageChunk,
        )
        assert result.tool_call_chunks == []

    def test_default_class_override_for_user(self):
        """HumanMessageChunk as default_class forces HumanMessageChunk even without role."""
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"content": "test"},
            HumanMessageChunk,
        )
        assert isinstance(result, HumanMessageChunk)

    def test_default_class_override_for_system(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"content": "test"},
            SystemMessageChunk,
        )
        assert isinstance(result, SystemMessageChunk)

    def test_default_class_override_for_function(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"content": "test", "name": "fn"},
            FunctionMessageChunk,
        )
        assert isinstance(result, FunctionMessageChunk)

    def test_default_class_override_for_tool(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"content": "test", "tool_call_id": "tc-1"},
            ToolMessageChunk,
        )
        assert isinstance(result, ToolMessageChunk)

    def test_content_defaults_to_empty_string(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"role": "assistant"},
            AIMessageChunk,
        )
        assert result.content == ""

    def test_id_preserved(self):
        result = _convert_delta_to_message_chunk_with_reasoning(
            {"role": "assistant", "content": "x", "id": "custom-id"},
            AIMessageChunk,
        )
        assert result.id == "custom-id"


# ===================================================================
# _restore_reasoning_field
# ===================================================================


class TestRestoreReasoningField:
    """Tests for _restore_reasoning_field."""

    def test_restores_reasoning_from_additional_kwargs(self):
        payload_msg: dict[str, Any] = {"role": "assistant", "content": ""}
        orig_msg = AIMessage(
            content="",
            additional_kwargs={"reasoning": "my reasoning"},
        )
        _restore_reasoning_field(payload_msg, orig_msg)
        assert payload_msg["reasoning"] == "my reasoning"

    def test_restores_reasoning_content_as_fallback(self):
        payload_msg: dict[str, Any] = {"role": "assistant", "content": ""}
        orig_msg = AIMessage(
            content="",
            additional_kwargs={"reasoning_content": "fallback text"},
        )
        _restore_reasoning_field(payload_msg, orig_msg)
        assert payload_msg["reasoning"] == "fallback text"

    def test_reasoning_takes_precedence_over_reasoning_content(self):
        payload_msg: dict[str, Any] = {"role": "assistant", "content": ""}
        orig_msg = AIMessage(
            content="",
            additional_kwargs={"reasoning": "primary", "reasoning_content": "secondary"},
        )
        _restore_reasoning_field(payload_msg, orig_msg)
        assert payload_msg["reasoning"] == "primary"

    def test_no_reasoning_key_ignored(self):
        payload_msg: dict[str, Any] = {"role": "assistant", "content": ""}
        orig_msg = AIMessage(content="", additional_kwargs={})
        _restore_reasoning_field(payload_msg, orig_msg)
        assert "reasoning" not in payload_msg

    def test_reasoning_value_can_be_dict(self):
        payload_msg: dict[str, Any] = {"role": "assistant", "content": ""}
        orig_msg = AIMessage(
            content="",
            additional_kwargs={"reasoning": {"text": "complex"}},
        )
        _restore_reasoning_field(payload_msg, orig_msg)
        assert payload_msg["reasoning"] == {"text": "complex"}


# ===================================================================
# VllmChatModel
# ===================================================================


class TestVllmChatModelLlmType:
    def test_llm_type(self):
        model = _make_model()
        assert model._llm_type == "vllm-openai-compatible"


class TestVllmChatModelGetRequestPayload:
    """Tests for VllmChatModel._get_request_payload."""

    def test_restores_reasoning_in_request_payload(self):
        model = _make_model()
        payload = model._get_request_payload(
            [
                AIMessage(
                    content="",
                    tool_calls=[{"name": "bash", "args": {"cmd": "pwd"}, "id": "tool-1", "type": "tool_call"}],
                    additional_kwargs={"reasoning": "Need to inspect the workspace first."},
                ),
                HumanMessage(content="Continue"),
            ]
        )
        assistant_message = payload["messages"][0]
        assert assistant_message["role"] == "assistant"
        assert assistant_message["reasoning"] == "Need to inspect the workspace first."
        assert assistant_message["tool_calls"][0]["function"]["name"] == "bash"

    def test_normalizes_legacy_thinking_kwarg_to_enable_thinking(self):
        model = VllmChatModel(
            model="qwen3",
            api_key="dummy",
            base_url="http://localhost:8000/v1",
            extra_body={"chat_template_kwargs": {"thinking": True}},
        )
        payload = model._get_request_payload([HumanMessage(content="Hello")])
        assert payload["extra_body"]["chat_template_kwargs"] == {"enable_thinking": True}

    def test_preserves_explicit_enable_thinking_kwarg(self):
        model = VllmChatModel(
            model="qwen3",
            api_key="dummy",
            base_url="http://localhost:8000/v1",
            extra_body={"chat_template_kwargs": {"enable_thinking": False, "foo": "bar"}},
        )
        payload = model._get_request_payload([HumanMessage(content="Hello")])
        assert payload["extra_body"]["chat_template_kwargs"] == {
            "enable_thinking": False,
            "foo": "bar",
        }

    def test_different_length_messages_matches_assistants(self):
        """When messages differ in length, match assistant payloads with AI messages."""
        model = _make_model()
        # Use multiple assistant and human messages to trigger the different-length path.
        # LangChain's _convert_input may add system messages or change message count.
        messages = [
            AIMessage(
                content="step1",
                additional_kwargs={"reasoning": "r1"},
            ),
            HumanMessage(content="q1"),
            AIMessage(
                content="step2",
                additional_kwargs={"reasoning": "r2"},
            ),
            HumanMessage(content="q2"),
            AIMessage(
                content="step3",
                additional_kwargs={"reasoning_content": "r3_fallback"},
            ),
        ]
        payload = model._get_request_payload(messages)
        assistant_msgs = [m for m in payload["messages"] if m.get("role") == "assistant"]
        # At least one assistant message should have reasoning restored
        assert any("reasoning" in m for m in assistant_msgs)

    def test_no_extra_body_no_normalization(self):
        model = _make_model()
        payload = model._get_request_payload([HumanMessage(content="Hi")])
        # No extra_body means normalization is skipped
        assert "extra_body" not in payload or isinstance(payload.get("extra_body"), dict)

    def test_different_length_messages_uses_fallback_matching(self):
        """Lines 186-189: when payload messages count differs from original, match by role."""
        model = _make_model()
        # Use a prompt value that may get expanded with a system message by the parent
        from langchain_core.prompt_values import ChatPromptValue

        prompt = ChatPromptValue(
            messages=[
                AIMessage(content="step1", additional_kwargs={"reasoning": "r1"}),
                HumanMessage(content="q1"),
                AIMessage(content="step2", additional_kwargs={"reasoning": "r2"}),
            ]
        )
        # Patch super()._get_request_payload to return a different number of messages
        original_super = ChatOpenAI._get_request_payload

        def patched_super(self_inner, input_, *, stop=None, **kwargs):
            result = original_super(self_inner, input_, stop=stop, **kwargs)
            # Inject an extra non-assistant message to change the count
            result["messages"].insert(0, {"role": "system", "content": "extra"})
            return result

        with patch.object(ChatOpenAI, "_get_request_payload", patched_super):
            payload = model._get_request_payload(prompt)

        assistant_msgs = [m for m in payload["messages"] if m.get("role") == "assistant"]
        # At least one should have reasoning restored via the fallback matching path
        assert any("reasoning" in m for m in assistant_msgs)


class TestVllmChatModelCreateChatResult:
    """Tests for VllmChatModel._create_chat_result."""

    def test_preserves_reasoning_in_chat_result_from_dict(self):
        model = _make_model()
        result = model._create_chat_result(
            {
                "model": "Qwen/QwQ-32B",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "42",
                            "reasoning": "I compared the two numbers directly.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        )
        message = result.generations[0].message
        assert message.additional_kwargs["reasoning"] == "I compared the two numbers directly."
        assert message.additional_kwargs["reasoning_content"] == "I compared the two numbers directly."

    def test_preserves_reasoning_from_openai_base_model(self):
        """When response is an openai.BaseModel, model_dump() is called."""
        model = _make_model()

        # Create a mock BaseModel that model_dump returns the expected dict
        mock_response = MagicMock(spec=openai.BaseModel)
        mock_response.model_dump.return_value = {
            "model": "Qwen/QwQ-32B",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "answer",
                        "reasoning": {"text": "deep think"},
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

        result = model._create_chat_result(mock_response)
        message = result.generations[0].message
        assert message.additional_kwargs["reasoning"] == {"text": "deep think"}
        assert message.additional_kwargs["reasoning_content"] == "deep think"

    def test_no_reasoning_in_choice_leaves_additional_kwargs_unchanged(self):
        model = _make_model()
        result = model._create_chat_result(
            {
                "model": "Qwen/QwQ-32B",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "42",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        )
        message = result.generations[0].message
        assert "reasoning" not in message.additional_kwargs

    def test_reasoning_is_none_in_choice_skipped(self):
        model = _make_model()
        result = model._create_chat_result(
            {
                "model": "Qwen/QwQ-32B",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "42",
                            "reasoning": None,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        )
        message = result.generations[0].message
        assert "reasoning" not in message.additional_kwargs

    def test_empty_reasoning_value_preserved_without_reasoning_content(self):
        model = _make_model()
        result = model._create_chat_result(
            {
                "model": "Qwen/QwQ-32B",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "42",
                            "reasoning": "",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        )
        message = result.generations[0].message
        assert message.additional_kwargs["reasoning"] == ""
        assert "reasoning_content" not in message.additional_kwargs

    def test_generation_info_passed_through(self):
        model = _make_model()
        gen_info = {"custom": "info"}
        result = model._create_chat_result(
            {
                "model": "Qwen/QwQ-32B",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "x"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
            generation_info=gen_info,
        )
        assert result.generations[0].generation_info.get("custom") == "info"

    def test_non_chat_generation_is_skipped(self):
        """Line 200: non-ChatGeneration items in generations are skipped."""
        from langchain_core.outputs import ChatGeneration, ChatResult

        model = _make_model()
        # Build a ChatResult and then replace generations with a non-ChatGeneration mock
        mock_gen = ChatGeneration(message=AIMessage(content="x"))
        real_result = ChatResult(generations=[mock_gen], llm_output={})
        # Bypass pydantic validation by setting generations to non-ChatGeneration items
        mock_non_gen = MagicMock()
        real_result.generations = [mock_non_gen]

        with patch.object(ChatOpenAI, "_create_chat_result", return_value=real_result):
            response = {
                "model": "test",
                "choices": [{"message": {"role": "assistant", "content": "x", "reasoning": "r"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
            result = model._create_chat_result(response)
        # The non-ChatGeneration item was skipped, so no reasoning was set
        assert result.generations[0] is mock_non_gen

    def test_non_ai_message_is_skipped(self):
        """Line 203: non-AIMessage in ChatGeneration is skipped."""
        from langchain_core.outputs import ChatGeneration, ChatResult

        model = _make_model()
        mock_gen = ChatGeneration(message=HumanMessage(content="human"))
        mock_result = ChatResult(generations=[mock_gen], llm_output={})
        with patch.object(ChatOpenAI, "_create_chat_result", return_value=mock_result):
            response = {
                "model": "test",
                "choices": [{"message": {"role": "assistant", "content": "x", "reasoning": "r"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
            result = model._create_chat_result(response)
        # The non-AIMessage was skipped
        assert "reasoning" not in result.generations[0].message.additional_kwargs


class TestVllmChatModelConvertChunkToGenerationChunk:
    """Tests for VllmChatModel._convert_chunk_to_generation_chunk."""

    def test_content_delta_type_returns_none(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {"type": "content.delta", "choices": []},
            AIMessageChunk,
            {},
        )
        assert result is None

    def test_no_choices_creates_empty_generation_chunk(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {"model": "test", "choices": []},
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert result.message.content == ""

    def test_no_choices_with_none_choices(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {"model": "test", "choices": None},
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert result.message.content == ""

    def test_output_version_v1_sets_empty_list_content(self):
        model = _make_model()
        model.output_version = "v1"
        result = model._convert_chunk_to_generation_chunk(
            {"model": "test", "choices": []},
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert result.message.content == []
        assert result.message.response_metadata["output_version"] == "v1"

    def test_choice_delta_is_none_returns_none(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "choices": [{"delta": None, "finish_reason": None}],
            },
            AIMessageChunk,
            {},
        )
        assert result is None

    def test_finish_reason_populates_generation_info(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "Qwen/QwQ-32B",
                "system_fingerprint": "fp-123",
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": "done"},
                        "finish_reason": "stop",
                    }
                ],
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert result.generation_info["finish_reason"] == "stop"
        assert result.generation_info["model_name"] == "Qwen/QwQ-32B"
        assert result.generation_info["system_fingerprint"] == "fp-123"

    def test_finish_reason_without_model_name(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": "done"},
                        "finish_reason": "stop",
                    }
                ],
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert result.generation_info["finish_reason"] == "stop"
        assert "model_name" not in result.generation_info

    def test_finish_reason_with_service_tier(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "service_tier": "premium",
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": "done"},
                        "finish_reason": "stop",
                    }
                ],
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert result.generation_info["service_tier"] == "premium"

    def test_finish_reason_without_system_fingerprint(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": "done"},
                        "finish_reason": "stop",
                    }
                ],
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert "system_fingerprint" not in result.generation_info

    def test_finish_reason_without_service_tier(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": "done"},
                        "finish_reason": "stop",
                    }
                ],
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert "service_tier" not in result.generation_info

    def test_logprobs_populated(self):
        model = _make_model()
        logprobs_data = {"tokens": ["a"], "token_logprobs": [-0.5]}
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": "a"},
                        "finish_reason": None,
                        "logprobs": logprobs_data,
                    }
                ],
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert result.generation_info["logprobs"] == logprobs_data

    def test_logprobs_absent_not_in_generation_info(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": "a"},
                        "finish_reason": None,
                    }
                ],
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        # generation_info may be None or a dict without logprobs
        if result.generation_info is not None:
            assert "logprobs" not in result.generation_info

    def test_token_usage_creates_usage_metadata(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": "done"},
                        "finish_reason": "stop",
                    }
                ],
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert result.message.usage_metadata is not None
        assert result.message.usage_metadata["input_tokens"] == 10
        assert result.message.usage_metadata["output_tokens"] == 20

    def test_token_usage_on_no_choices_chunk(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 5,
                    "total_tokens": 10,
                },
                "choices": [],
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert result.message.usage_metadata is not None

    def test_choices_from_chunk_key(self):
        """Choices can come from chunk.choices fallback."""
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "chunk": {
                    "choices": [
                        {
                            "delta": {"role": "assistant", "content": "from chunk"},
                            "finish_reason": None,
                        }
                    ]
                },
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert result.message.content == "from chunk"

    def test_reasoning_in_streaming_delta(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "Qwen/QwQ-32B",
                "choices": [
                    {
                        "delta": {
                            "role": "assistant",
                            "reasoning": "First, call the weather tool.",
                            "content": "Calling tool...",
                        },
                        "finish_reason": None,
                    }
                ],
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert result.message.additional_kwargs["reasoning"] == "First, call the weather tool."
        assert result.message.additional_kwargs["reasoning_content"] == "First, call the weather tool."
        assert result.message.content == "Calling tool..."

    def test_empty_reasoning_in_streaming_delta(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "Qwen/QwQ-32B",
                "choices": [
                    {
                        "delta": {
                            "role": "assistant",
                            "reasoning": "",
                            "content": "Still replying...",
                        },
                        "finish_reason": None,
                    }
                ],
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert "reasoning" in result.message.additional_kwargs
        assert result.message.additional_kwargs["reasoning"] == ""
        assert "reasoning_content" not in result.message.additional_kwargs

    def test_base_generation_info_preserved(self):
        model = _make_model()
        base_info = {"base_key": "base_value"}
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": "x"},
                        "finish_reason": None,
                    }
                ],
            },
            AIMessageChunk,
            base_info,
        )
        assert result is not None
        assert result.generation_info["base_key"] == "base_value"

    def test_base_generation_info_merged_with_finish_reason(self):
        model = _make_model()
        base_info = {"base_key": "base_value"}
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": "x"},
                        "finish_reason": "stop",
                    }
                ],
            },
            AIMessageChunk,
            base_info,
        )
        assert result is not None
        assert result.generation_info["base_key"] == "base_value"
        assert result.generation_info["finish_reason"] == "stop"

    def test_model_provider_in_response_metadata(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": "x"},
                        "finish_reason": None,
                    }
                ],
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert result.message.response_metadata["model_provider"] == "openai"

    def test_no_finish_reason_no_extra_generation_info_keys(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": "x"},
                        "finish_reason": None,
                    }
                ],
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        # When base is empty dict and no finish_reason, generation_info becomes None
        # because {} or None evaluates to None
        if result.generation_info is not None:
            assert "finish_reason" not in result.generation_info
            assert "model_name" not in result.generation_info
            assert "system_fingerprint" not in result.generation_info

    def test_generation_info_is_none_when_empty_and_no_finish(self):
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": "x"},
                        "finish_reason": None,
                    }
                ],
            },
            AIMessageChunk,
            None,
        )
        assert result is not None
        # When base_generation_info is None and no finish_reason/logprobs,
        # generation_info should be None
        assert result.generation_info is None

    def test_service_tier_on_token_usage(self):
        """service_tier is passed to _create_usage_metadata."""
        model = _make_model()
        result = model._convert_chunk_to_generation_chunk(
            {
                "model": "test",
                "service_tier": "default",
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": "x"},
                        "finish_reason": None,
                    }
                ],
            },
            AIMessageChunk,
            {},
        )
        assert result is not None
        assert result.message.usage_metadata is not None
