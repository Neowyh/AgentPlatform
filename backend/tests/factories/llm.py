"""LLM 响应 factories — 替代 _make_llm_response 等 ad-hoc builder。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


class LLMResponseFactory:
    """构建模拟的 LLM 响应对象。

    Usage::

        from tests.factories import LLMResponseFactory

        resp = LLMResponseFactory.build()
        resp = LLMResponseFactory.build(content="custom answer", tool_calls=[...])
    """

    @staticmethod
    def build(**kwargs) -> SimpleNamespace:
        defaults = {
            "content": "Test response",
            "usage_metadata": {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
            },
            "tool_calls": [],
            "finish_reason": "stop",
            "response_metadata": {},
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    @staticmethod
    def build_with_usage(input_tokens: int = 100, output_tokens: int = 50, **kwargs):
        """构建带有指定 token 用量的响应。"""
        return LLMResponseFactory.build(
            usage_metadata={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            **kwargs,
        )

    @staticmethod
    def build_with_tool_calls(tool_calls: list | None = None, **kwargs):
        """构建带有 tool calls 的响应。"""
        if tool_calls is None:
            tool_calls = [
                {
                    "name": "test_tool",
                    "args": {"query": "test"},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ]
        return LLMResponseFactory.build(tool_calls=tool_calls, **kwargs)


class ToolCallModelFactory:
    """构建模拟的 ToolCallingModel。

    Usage::

        from tests.factories import ToolCallModelFactory

        model = ToolCallModelFactory.build()
        model = ToolCallModelFactory.build(response_text="custom")
    """

    @staticmethod
    def build(**kwargs) -> MagicMock:
        response_text = kwargs.pop("response_text", "Test response")
        tool_calls = kwargs.pop("tool_calls", [])
        input_tokens = kwargs.pop("input_tokens", 10)
        output_tokens = kwargs.pop("output_tokens", 5)

        model = MagicMock()
        model.invoke = MagicMock(
            content=response_text,
            tool_calls=tool_calls,
            usage_metadata={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        )
        return model
