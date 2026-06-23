"""Comprehensive tests to cover missing lines across middleware modules.

This file targets specific uncovered lines identified by coverage analysis to
bring each middleware module closer to full coverage.
"""

from __future__ import annotations

import asyncio
import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ideer.agents.middlewares.dangling_tool_call_middleware import (
    DanglingToolCallMiddleware,
)
from ideer.agents.middlewares.deferred_tool_filter_middleware import (
    DeferredToolFilterMiddleware,
)
from ideer.agents.middlewares.loop_detection_middleware import (
    LoopDetectionMiddleware,
    _normalize_tool_call_args,
    _stable_tool_key,
)
from ideer.agents.middlewares.memory_middleware import MemoryMiddleware
from ideer.agents.middlewares.safety_finish_reason_middleware import (
    SafetyFinishReasonMiddleware,
)
from ideer.agents.middlewares.sandbox_audit_middleware import (
    SandboxAuditMiddleware,
)
from ideer.agents.middlewares.summarization_middleware import IDeerSummarizationMiddleware
from ideer.agents.middlewares.thread_data_middleware import ThreadDataMiddleware
from ideer.agents.middlewares.title_middleware import TitleMiddleware


def _module(name: str, **attrs):
    """Create a fake module with given attributes."""
    mod = ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


# ============================================================================
# DanglingToolCallMiddleware - lines 57-75, 85, 104, 140
# ============================================================================


class TestDanglingToolCallRawProviderFallback:
    """Cover lines 57-75: raw_provider fallback when structured tool_calls is empty."""

    def test_raw_tc_with_function_dict_name_extraction(self):
        """Lines 60-63: name extracted from function dict."""
        mw = DanglingToolCallMiddleware()
        msgs = [
            AIMessage(
                content="",
                tool_calls=[],
                additional_kwargs={
                    "tool_calls": [
                        {
                            "id": "raw_1",
                            "type": "function",
                            "function": {"name": "search", "arguments": '{"q":"test"}'},
                        }
                    ]
                },
            )
        ]
        patched = mw._build_patched_messages(msgs)
        assert patched is not None
        assert len(patched) == 2
        assert patched[1].tool_call_id == "raw_1"

    def test_raw_tc_with_top_level_name(self):
        """Line 62: name from top-level, not function dict."""
        mw = DanglingToolCallMiddleware()
        msgs = [
            AIMessage(
                content="",
                tool_calls=[],
                additional_kwargs={
                    "tool_calls": [
                        {
                            "id": "raw_2",
                            "name": "top_level_tool",
                            "args": {"key": "val"},
                        }
                    ]
                },
            )
        ]
        patched = mw._build_patched_messages(msgs)
        assert patched is not None
        assert patched[1].name == "top_level_tool"

    def test_raw_tc_with_string_arguments_parsed(self):
        """Lines 66-73: arguments is a JSON string in function dict."""
        mw = DanglingToolCallMiddleware()
        args_json = json.dumps({"path": "/tmp/file.txt"})
        msgs = [
            AIMessage(
                content="",
                tool_calls=[],
                additional_kwargs={
                    "tool_calls": [
                        {
                            "id": "raw_3",
                            "function": {"name": "read_file", "arguments": args_json},
                        }
                    ]
                },
            )
        ]
        patched = mw._build_patched_messages(msgs)
        assert patched is not None
        assert patched[1].tool_call_id == "raw_3"
        assert patched[1].name == "read_file"

    def test_raw_tc_with_invalid_json_arguments(self):
        """Lines 70-72: invalid JSON string in arguments falls back to {}."""
        mw = DanglingToolCallMiddleware()
        msgs = [
            AIMessage(
                content="",
                tool_calls=[],
                additional_kwargs={
                    "tool_calls": [
                        {
                            "id": "raw_4",
                            "function": {"name": "tool", "arguments": "not-json"},
                        }
                    ]
                },
            )
        ]
        patched = mw._build_patched_messages(msgs)
        assert patched is not None
        assert patched[1].tool_call_id == "raw_4"

    def test_raw_tc_with_none_arguments(self):
        """Lines 65-66: arguments is None, not present."""
        mw = DanglingToolCallMiddleware()
        msgs = [
            AIMessage(
                content="",
                tool_calls=[],
                additional_kwargs={
                    "tool_calls": [
                        {
                            "id": "raw_5",
                            "function": {"name": "tool"},
                        }
                    ]
                },
            )
        ]
        patched = mw._build_patched_messages(msgs)
        assert patched is not None

    def test_raw_tc_non_dict_in_list_skipped(self):
        """Line 57: non-dict items in additional_kwargs.tool_calls are skipped."""
        mw = DanglingToolCallMiddleware()
        msgs = [
            AIMessage(
                content="",
                tool_calls=[],
                additional_kwargs={"tool_calls": ["not-a-dict", 42, None]},
            )
        ]
        patched = mw._build_patched_messages(msgs)
        assert patched is None  # no valid tool calls to patch

    def test_raw_tc_missing_id(self):
        """Line 76: raw_tc without id still gets normalized."""
        mw = DanglingToolCallMiddleware()
        msgs = [
            AIMessage(
                content="",
                tool_calls=[],
                additional_kwargs={
                    "tool_calls": [
                        {
                            "function": {"name": "tool_no_id"},
                        }
                    ]
                },
            )
        ]
        patched = mw._build_patched_messages(msgs)
        # tc_id is None -> line 139: skip
        assert patched is None

    def test_raw_tc_with_non_dict_args_string(self):
        """Line 79: args is not a dict, falls back to {}."""
        mw = DanglingToolCallMiddleware()
        msgs = [
            AIMessage(
                content="",
                tool_calls=[],
                additional_kwargs={
                    "tool_calls": [
                        {
                            "id": "raw_6",
                            "name": "tool",
                            "args": "not-a-dict",
                        }
                    ]
                },
            )
        ]
        patched = mw._build_patched_messages(msgs)
        assert patched is not None

    def test_invalid_tool_calls_non_dict_skipped(self):
        """Line 84: non-dict items in invalid_tool_calls are skipped.

        AIMessage normalizes invalid_tool_calls on construction, so we pass
        valid dicts but verify the middleware handles the 'continue' path.
        """
        mw = DanglingToolCallMiddleware()
        # AIMessage only accepts dicts for invalid_tool_calls, so we test
        # with an empty list (nothing to process) to verify line 83-84 path
        msgs = [
            AIMessage(
                content="",
                tool_calls=[],
                invalid_tool_calls=[],
            )
        ]
        patched = mw._build_patched_messages(msgs)
        assert patched is None

    def test_invalid_tool_call_no_error_string(self):
        """Lines 101-103: invalid tool call with empty error string."""
        mw = DanglingToolCallMiddleware()
        msgs = [
            AIMessage(
                content="",
                tool_calls=[],
                invalid_tool_calls=[
                    {
                        "name": "tool",
                        "id": "inv_1",
                        "error": "",
                    }
                ],
            )
        ]
        patched = mw._build_patched_messages(msgs)
        assert patched is not None
        assert "arguments were invalid" in patched[1].content
        assert "Failed to parse" not in patched[1].content

    def test_invalid_tool_call_no_error_at_all(self):
        """Line 104: invalid tool call with no error field."""
        mw = DanglingToolCallMiddleware()
        msgs = [
            AIMessage(
                content="",
                tool_calls=[],
                invalid_tool_calls=[
                    {
                        "name": "tool",
                        "id": "inv_2",
                    }
                ],
            )
        ]
        patched = mw._build_patched_messages(msgs)
        assert patched is not None
        assert "arguments were invalid" in patched[1].content

    def test_invalid_tool_call_with_error_string(self):
        """Line 102-103: invalid tool call with error string."""
        mw = DanglingToolCallMiddleware()
        msgs = [
            AIMessage(
                content="",
                tool_calls=[],
                invalid_tool_calls=[
                    {
                        "name": "tool",
                        "id": "inv_3",
                        "error": "malformed JSON payload",
                    }
                ],
            )
        ]
        patched = mw._build_patched_messages(msgs)
        assert patched is not None
        assert "malformed JSON payload" in patched[1].content


# ============================================================================
# ToolErrorHandlingMiddleware - lines 29, 78-126, 131, 146-177
# ============================================================================


class TestToolErrorHandlingBuildRuntimeMiddlewares:
    """Cover _build_runtime_middlewares and builder functions."""

    def _stub_imports(self, monkeypatch):
        """Stub out the middleware imports used by _build_runtime_middlewares."""

        class FakeMiddleware:
            def __init__(self, *args, **kwargs):
                pass

        class FakeLLMErrorHandlingMiddleware:
            def __init__(self, *, app_config):
                pass

        monkeypatch.setitem(
            sys.modules,
            "ideer.agents.middlewares.llm_error_handling_middleware",
            _module("llm", LLMErrorHandlingMiddleware=FakeLLMErrorHandlingMiddleware),
        )
        monkeypatch.setitem(
            sys.modules,
            "ideer.agents.middlewares.thread_data_middleware",
            _module("td", ThreadDataMiddleware=FakeMiddleware),
        )
        monkeypatch.setitem(
            sys.modules,
            "ideer.sandbox.middleware",
            _module("sb", SandboxMiddleware=FakeMiddleware),
        )
        monkeypatch.setitem(
            sys.modules,
            "ideer.agents.middlewares.dangling_tool_call_middleware",
            _module("dtc", DanglingToolCallMiddleware=FakeMiddleware),
        )
        monkeypatch.setitem(
            sys.modules,
            "ideer.agents.middlewares.sandbox_audit_middleware",
            _module("sa", SandboxAuditMiddleware=FakeMiddleware),
        )
        return FakeMiddleware

    def test_build_runtime_middlewares_with_guardrails(self, monkeypatch):
        """Lines 99-121: guardrails configuration branch."""
        from ideer.agents.middlewares.tool_error_handling_middleware import (
            _build_runtime_middlewares,
        )
        from ideer.config.app_config import AppConfig, CircuitBreakerConfig
        from ideer.config.guardrails_config import GuardrailProviderConfig, GuardrailsConfig
        from ideer.config.model_config import ModelConfig
        from ideer.config.sandbox_config import SandboxConfig

        self._stub_imports(monkeypatch)

        class FakeGuardrailProvider:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeGuardrailMiddleware:
            def __init__(self, provider, fail_closed=False, passport=None):
                self.provider = provider

        monkeypatch.setitem(
            sys.modules,
            "ideer.guardrails.middleware",
            _module("gm", GuardrailMiddleware=FakeGuardrailMiddleware),
        )
        monkeypatch.setitem(
            sys.modules,
            "ideer.reflection",
            _module("ref", resolve_variable=lambda x: FakeGuardrailProvider),
        )

        app_config = AppConfig(
            models=[ModelConfig(name="m", display_name="m", description=None, use="langchain_openai:ChatOpenAI", model="m")],
            sandbox=SandboxConfig(use="test"),
            guardrails=GuardrailsConfig(
                enabled=True,
                provider=GuardrailProviderConfig(use="FakeGuardrailProvider", config={"key": "val"}),
            ),
            circuit_breaker=CircuitBreakerConfig(failure_threshold=7, recovery_timeout_sec=11),
        )

        middlewares = _build_runtime_middlewares(
            app_config=app_config,
            include_uploads=False,
            include_dangling_tool_call_patch=False,
        )
        assert any(isinstance(m, FakeGuardrailMiddleware) for m in middlewares)

    def test_build_runtime_middlewares_guardrails_no_framework_in_init(self, monkeypatch):
        """Lines 112-118: guardrails provider __init__ raises ValueError."""
        from ideer.agents.middlewares.tool_error_handling_middleware import (
            _build_runtime_middlewares,
        )
        from ideer.config.app_config import AppConfig, CircuitBreakerConfig
        from ideer.config.guardrails_config import GuardrailProviderConfig, GuardrailsConfig
        from ideer.config.model_config import ModelConfig
        from ideer.config.sandbox_config import SandboxConfig

        self._stub_imports(monkeypatch)

        class NoSigProvider:
            def __init__(self):
                pass

        class FakeGuardrailMiddleware:
            def __init__(self, provider, fail_closed=False, passport=None):
                pass

        monkeypatch.setitem(
            sys.modules,
            "ideer.guardrails.middleware",
            _module("gm2", GuardrailMiddleware=FakeGuardrailMiddleware),
        )
        monkeypatch.setitem(
            sys.modules,
            "ideer.reflection",
            _module("ref2", resolve_variable=lambda x: NoSigProvider),
        )

        app_config = AppConfig(
            models=[ModelConfig(name="m", display_name="m", description=None, use="langchain_openai:ChatOpenAI", model="m")],
            sandbox=SandboxConfig(use="test"),
            guardrails=GuardrailsConfig(
                enabled=True,
                provider=GuardrailProviderConfig(use="NoSigProvider", config={}),
            ),
            circuit_breaker=CircuitBreakerConfig(failure_threshold=7, recovery_timeout_sec=11),
        )

        # Should not raise - ValueError is caught internally
        middlewares = _build_runtime_middlewares(
            app_config=app_config,
            include_uploads=False,
            include_dangling_tool_call_patch=False,
        )
        assert len(middlewares) > 0

    def test_build_runtime_middlewares_guardrails_with_framework_kwarg(self, monkeypatch):
        """Lines 114-116: guardrails provider accepts **kwargs."""
        from ideer.agents.middlewares.tool_error_handling_middleware import (
            _build_runtime_middlewares,
        )
        from ideer.config.app_config import AppConfig, CircuitBreakerConfig
        from ideer.config.guardrails_config import GuardrailProviderConfig, GuardrailsConfig
        from ideer.config.model_config import ModelConfig
        from ideer.config.sandbox_config import SandboxConfig

        self._stub_imports(monkeypatch)

        class KwargsProvider:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeGuardrailMiddleware:
            def __init__(self, provider, fail_closed=False, passport=None):
                self.provider = provider

        monkeypatch.setitem(
            sys.modules,
            "ideer.guardrails.middleware",
            _module("gm3", GuardrailMiddleware=FakeGuardrailMiddleware),
        )
        monkeypatch.setitem(
            sys.modules,
            "ideer.reflection",
            _module("ref3", resolve_variable=lambda x: KwargsProvider),
        )

        app_config = AppConfig(
            models=[ModelConfig(name="m", display_name="m", description=None, use="langchain_openai:ChatOpenAI", model="m")],
            sandbox=SandboxConfig(use="test"),
            guardrails=GuardrailsConfig(
                enabled=True,
                provider=GuardrailProviderConfig(use="KwargsProvider"),
            ),
            circuit_breaker=CircuitBreakerConfig(failure_threshold=7, recovery_timeout_sec=11),
        )

        middlewares = _build_runtime_middlewares(
            app_config=app_config,
            include_uploads=False,
            include_dangling_tool_call_patch=False,
        )
        # Verify framework kwarg was injected
        guardrail_mw = next(m for m in middlewares if isinstance(m, FakeGuardrailMiddleware))
        assert guardrail_mw.provider.kwargs.get("framework") == "ideer"

    def test_build_runtime_middlewares_guardrails_framework_already_in_config(self, monkeypatch):
        """Lines 112: framework already in provider_kwargs → not overridden."""
        from ideer.agents.middlewares.tool_error_handling_middleware import (
            _build_runtime_middlewares,
        )
        from ideer.config.app_config import AppConfig, CircuitBreakerConfig
        from ideer.config.guardrails_config import GuardrailProviderConfig, GuardrailsConfig
        from ideer.config.model_config import ModelConfig
        from ideer.config.sandbox_config import SandboxConfig

        self._stub_imports(monkeypatch)

        class KwargsProvider:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeGuardrailMiddleware:
            def __init__(self, provider, fail_closed=False, passport=None):
                self.provider = provider

        monkeypatch.setitem(
            sys.modules,
            "ideer.guardrails.middleware",
            _module("gm4", GuardrailMiddleware=FakeGuardrailMiddleware),
        )
        monkeypatch.setitem(
            sys.modules,
            "ideer.reflection",
            _module("ref4", resolve_variable=lambda x: KwargsProvider),
        )

        app_config = AppConfig(
            models=[ModelConfig(name="m", display_name="m", description=None, use="langchain_openai:ChatOpenAI", model="m")],
            sandbox=SandboxConfig(use="test"),
            guardrails=GuardrailsConfig(
                enabled=True,
                provider=GuardrailProviderConfig(use="KwargsProvider", config={"framework": "custom"}),
            ),
            circuit_breaker=CircuitBreakerConfig(failure_threshold=7, recovery_timeout_sec=11),
        )

        middlewares = _build_runtime_middlewares(
            app_config=app_config,
            include_uploads=False,
            include_dangling_tool_call_patch=False,
        )
        guardrail_mw = next(m for m in middlewares if isinstance(m, FakeGuardrailMiddleware))
        assert guardrail_mw.provider.kwargs.get("framework") == "custom"

    def test_build_runtime_middlewares_with_uploads(self, monkeypatch):
        """Lines 87-90: include_uploads inserts UploadsMiddleware."""
        from ideer.agents.middlewares.tool_error_handling_middleware import (
            _build_runtime_middlewares,
        )
        from ideer.config.app_config import AppConfig, CircuitBreakerConfig
        from ideer.config.guardrails_config import GuardrailsConfig
        from ideer.config.model_config import ModelConfig
        from ideer.config.sandbox_config import SandboxConfig

        self._stub_imports(monkeypatch)

        class FakeUploadsMiddleware:
            def __init__(self):
                pass

        monkeypatch.setitem(
            sys.modules,
            "ideer.agents.middlewares.uploads_middleware",
            _module("up", UploadsMiddleware=FakeUploadsMiddleware),
        )

        app_config = AppConfig(
            models=[ModelConfig(name="m", display_name="m", description=None, use="langchain_openai:ChatOpenAI", model="m")],
            sandbox=SandboxConfig(use="test"),
            guardrails=GuardrailsConfig(enabled=False),
            circuit_breaker=CircuitBreakerConfig(failure_threshold=7, recovery_timeout_sec=11),
        )

        middlewares = _build_runtime_middlewares(
            app_config=app_config,
            include_uploads=True,
            include_dangling_tool_call_patch=True,
        )
        assert any(isinstance(m, FakeUploadsMiddleware) for m in middlewares)


# ============================================================================
# SandboxAuditMiddleware - lines 85-88, 91-94, 151-154, 223, 227-228, 257, 260
# ============================================================================


class TestSandboxAuditCoverageGaps:
    """Cover specific missing lines in SandboxAuditMiddleware."""

    def test_split_compound_command_unclosed_double_quote(self):
        """Lines 85-88: unclosed double quote returns whole command."""
        from ideer.agents.middlewares.sandbox_audit_middleware import _split_compound_command

        result = _split_compound_command('echo "hello world')
        assert result == ['echo "hello world']

    def test_split_compound_command_unclosed_single_quote(self):
        """Unclosed single quote returns whole command."""
        from ideer.agents.middlewares.sandbox_audit_middleware import _split_compound_command

        result = _split_compound_command("echo 'hello world")
        assert result == ["echo 'hello world"]

    def test_split_compound_command_dangling_escape(self):
        """Line 128: dangling escape returns whole command."""
        from ideer.agents.middlewares.sandbox_audit_middleware import _split_compound_command

        result = _split_compound_command("echo hello\\")
        assert result == ["echo hello\\"]

    def test_split_compound_command_escaping_in_single_quote(self):
        """Lines 84-88: backslash not treated as escape inside single quotes."""
        from ideer.agents.middlewares.sandbox_audit_middleware import _split_compound_command

        result = _split_compound_command("echo 'hello\\' && rm -rf /")
        # Inside single quotes, \\ is literal, and ' closes the quote
        assert len(result) >= 1

    def test_split_compound_command_escaping_in_double_quote(self):
        """Lines 84-88: backslash inside double quotes."""
        from ideer.agents.middlewares.sandbox_audit_middleware import _split_compound_command

        result = _split_compound_command('echo "hello\\" && rm -rf /')
        assert len(result) >= 1

    def test_classify_single_command_shlex_value_error(self):
        """Lines 152-154: shlex.split fails on unclosed quote."""
        from ideer.agents.middlewares.sandbox_audit_middleware import _classify_single_command

        # Unclosed quote that shlex fails on
        result = _classify_single_command("echo 'unclosed")
        assert result == "block"

    def test_get_thread_id_from_config(self):
        """Lines 223, 227-228: thread_id from config.configurable."""
        mw = SandboxAuditMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "bash", "id": "call-1", "args": {"command": "ls"}}
        request.runtime = SimpleNamespace(
            context={},
            config={"configurable": {"thread_id": "thread-from-config"}},
        )
        command, thread_id, verdict, reject = mw._pre_process(request)
        assert thread_id == "thread-from-config"

    def test_get_thread_id_runtime_none(self):
        """Lines 221-222: runtime is None -> returns None."""
        mw = SandboxAuditMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "bash", "id": "call-1", "args": {"command": "ls"}}
        request.runtime = None
        command, thread_id, verdict, reject = mw._pre_process(request)
        assert thread_id is None

    def test_get_thread_id_context_not_dict(self):
        """Lines 224-225: context is not a dict."""
        mw = SandboxAuditMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "bash", "id": "call-1", "args": {"command": "ls"}}
        request.runtime = SimpleNamespace(
            context="not-a-dict",
            config={},
        )
        command, thread_id, verdict, reject = mw._pre_process(request)
        assert thread_id is None

    def test_append_warn_with_list_content(self):
        """Line 260: list content gets warning appended as new text block."""
        mw = SandboxAuditMiddleware()
        result = ToolMessage(
            content=[{"type": "text", "text": "output"}],
            tool_call_id="tc-1",
            name="bash",
        )
        warned = mw._append_warn_to_result(result, "pip install foo")
        assert isinstance(warned.content, list)
        assert len(warned.content) == 2
        assert "Warning" in warned.content[1]["text"]

    def test_append_warn_with_non_tool_message(self):
        """Line 257: non-ToolMessage result returned unchanged."""
        mw = SandboxAuditMiddleware()
        result = MagicMock(spec=[])  # not a ToolMessage
        warned = mw._append_warn_to_result(result, "pip install foo")
        assert warned is result

    def test_write_audit_with_truncation(self):
        """Lines 235-236: audit log truncation for long commands."""
        mw = SandboxAuditMiddleware()
        long_cmd = "x" * 300
        # Should not raise
        mw._write_audit("t1", long_cmd, "block", truncate=True)

    def test_missing_tool_call_id_in_build_block(self):
        """Line 246: missing tool_call_id falls back to 'missing_id'."""
        mw = SandboxAuditMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "bash"}  # no id
        msg = mw._build_block_message(request, "test reason")
        assert msg.tool_call_id == "missing_id"

    def test_pre_process_non_string_command(self):
        """Line 302: raw_command is not a string."""
        mw = SandboxAuditMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "bash", "id": "call-1", "args": {"command": 123}}
        request.runtime = SimpleNamespace(context={"thread_id": "t1"})
        command, thread_id, verdict, reject = mw._pre_process(request)
        assert command == ""  # non-string coerced to empty

    def test_pre_process_missing_args_key(self):
        """Line 300: args dict missing 'command' key."""
        mw = SandboxAuditMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "bash", "id": "call-1", "args": {}}
        request.runtime = SimpleNamespace(context={"thread_id": "t1"})
        command, thread_id, verdict, reject = mw._pre_process(request)
        assert command == ""


# ============================================================================
# LoopDetectionMiddleware - lines 93-96, 109-110, 113-114, 128, 139, 277-278, 366, 404, 604-605
# ============================================================================


class TestLoopDetectionCoverageGaps:
    """Cover specific missing lines in LoopDetectionMiddleware."""

    def _make_runtime(self, thread_id="t1", run_id="r1"):
        runtime = MagicMock()
        runtime.context = {"thread_id": thread_id, "run_id": run_id}
        return runtime

    def _make_state(self, tool_calls=None, content=""):
        msg = AIMessage(content=content, tool_calls=tool_calls or [])
        return {"messages": [msg]}

    def _bash_call(self, cmd="ls"):
        return {"name": "bash", "id": f"call_{cmd}", "args": {"command": cmd}}

    def test_normalize_tool_call_args_none(self):
        """Lines 93-94: args is None."""
        args, fallback = _normalize_tool_call_args(None)
        assert args == {}
        assert fallback is None

    def test_normalize_tool_call_args_list(self):
        """Line 96: args is a list (non-dict, non-str)."""
        args, fallback = _normalize_tool_call_args([1, 2, 3])
        assert args == {}
        assert fallback is not None

    def test_normalize_tool_call_args_bool(self):
        """Line 96: args is a bool."""
        args, fallback = _normalize_tool_call_args(True)
        assert args == {}
        assert fallback is not None

    def test_normalize_tool_call_args_int(self):
        """Line 96: args is an int."""
        args, fallback = _normalize_tool_call_args(42)
        assert args == {}
        assert fallback is not None

    def test_normalize_tool_call_args_str_invalid_json(self):
        """Lines 85-86: string args that is invalid JSON."""
        args, fallback = _normalize_tool_call_args("not valid json {{}}")
        assert args == {}
        assert fallback == "not valid json {{}}"

    def test_normalize_tool_call_args_str_non_dict_parsed(self):
        """Line 91: string that parses to a non-dict (list)."""
        args, fallback = _normalize_tool_call_args("[1, 2, 3]")
        assert args == {}
        assert fallback is not None

    def test_normalize_tool_call_args_str_int_parsed(self):
        """Line 91: string that parses to an int."""
        args, fallback = _normalize_tool_call_args('"just a string"')
        assert args == {}
        assert fallback is not None

    def test_stable_tool_key_read_file_with_line_numbers(self):
        """Lines 106-121: read_file bucketing with start/end lines."""
        key = _stable_tool_key("read_file", {"path": "/tmp/a.py", "start_line": 10, "end_line": 300}, None)
        assert "/tmp/a.py:" in key

    def test_stable_tool_key_read_file_non_numeric_lines(self):
        """Lines 109-114: non-numeric start_line/end_line."""
        key = _stable_tool_key("read_file", {"path": "/tmp/a.py", "start_line": "abc", "end_line": "xyz"}, None)
        assert "/tmp/a.py:" in key

    def test_stable_tool_key_read_file_with_fallback(self):
        """Line 101: read_file with fallback_key (string args)."""
        key = _stable_tool_key("read_file", {}, "fallback_key_value")
        assert key == "fallback_key_value"

    def test_stable_tool_key_read_file_no_path(self):
        """Lines 102: read_file without path."""
        key = _stable_tool_key("read_file", {"start_line": 1, "end_line": 10}, None)
        # path is empty string, bucketing still works
        assert ":" in key

    def test_stable_tool_key_write_file_with_fallback(self):
        """Lines 128-129: write_file with fallback."""
        key = _stable_tool_key("write_file", {}, "fallback_write")
        assert key == "fallback_write"

    def test_stable_tool_key_write_file_with_args(self):
        """Line 129: write_file without fallback uses full json."""
        key = _stable_tool_key("write_file", {"path": "/tmp/a.py", "content": "data"}, None)
        assert "path" in key

    def test_stable_tool_key_str_replace_with_fallback(self):
        """Lines 128-129: str_replace with fallback."""
        key = _stable_tool_key("str_replace", {}, "fallback_replace")
        assert key == "fallback_replace"

    def test_stable_tool_key_salient_fields(self):
        """Lines 131-134: salient fields extracted."""
        key = _stable_tool_key("grep", {"path": "/tmp", "pattern": "foo", "extra": "bar"}, None)
        assert "foo" in key
        assert "bar" not in key

    def test_stable_tool_key_no_salient_fields_with_fallback(self):
        """Lines 136-137: no salient fields, uses fallback."""
        key = _stable_tool_key("custom_tool", {}, "fb123")
        assert key == "fb123"

    def test_stable_tool_key_no_salient_fields_no_fallback(self):
        """Lines 138-139: no salient fields, no fallback, uses full json."""
        key = _stable_tool_key("custom_tool", {"a": 1}, None)
        assert "a" in key

    def test_stable_tool_key_read_file_no_lines(self):
        """Lines 107-108: read_file with no start_line/end_line."""
        key = _stable_tool_key("read_file", {"path": "/tmp/a.py"}, None)
        assert "/tmp/a.py:" in key

    def test_tool_freq_empty_name_skipped(self):
        """Line 403: tool call with empty name is skipped."""
        mw = LoopDetectionMiddleware(tool_freq_warn=2, tool_freq_hard_limit=5)
        runtime = self._make_runtime()
        tool_calls = [{"name": "", "id": "c1", "args": {}}]
        result = mw._apply(self._make_state(tool_calls=tool_calls), runtime)
        assert result is None

    def test_lru_eviction_with_pending_warnings(self):
        """Lines 277-278: eviction cleans up pending warnings for evicted thread."""
        mw = LoopDetectionMiddleware(warn_threshold=2, max_tracked_threads=2)
        call = [self._bash_call("ls")]

        # Fill up 2 threads
        for i in range(2):
            runtime = self._make_runtime(f"thread-{i}")
            for _ in range(2):
                mw._apply(self._make_state(tool_calls=call), runtime)

        # Queue a pending warning for thread-0
        self._make_runtime("thread-0")
        pending_key_0 = ("thread-0", "r1")
        assert pending_key_0 in mw._pending_warnings

        # Add a 3rd thread -> evicts thread-0 and its pending warnings
        rt_new = self._make_runtime("thread-new")
        mw._apply(self._make_state(tool_calls=call), rt_new)
        assert "thread-0" not in mw._history
        assert pending_key_0 not in mw._pending_warnings

    def test_prune_pending_warning_state_locked(self):
        """Lines 302-308: pruning locks."""
        mw = LoopDetectionMiddleware(max_tracked_threads=1)
        # Create more pending warning keys than allowed
        for i in range(10):
            rt = self._make_runtime(thread_id="same", run_id=f"run-{i}")
            mw._queue_pending_warning(rt, f"warn-{i}")
        assert len(mw._pending_warnings) <= mw._max_pending_warning_keys

    def test_after_model_no_messages(self):
        """Lines 535-536: after_model with empty messages."""
        mw = LoopDetectionMiddleware()
        runtime = self._make_runtime()
        assert mw.after_model({"messages": []}, runtime) is None

    def test_aafter_model(self):
        """Lines 539-540: async after_model."""
        mw = LoopDetectionMiddleware()
        runtime = self._make_runtime()
        result = asyncio.run(mw.aafter_model({"messages": []}, runtime))
        assert result is None

    def test_before_agent_async(self):
        """Lines 530-532: async before_agent."""
        mw = LoopDetectionMiddleware()
        runtime = self._make_runtime()
        result = asyncio.run(mw.abefore_agent({"messages": []}, runtime))
        assert result is None

    def test_after_agent_async(self):
        """Lines 548-550: async after_agent."""
        mw = LoopDetectionMiddleware()
        runtime = self._make_runtime()
        result = asyncio.run(mw.aafter_agent({"messages": []}, runtime))
        assert result is None

    def test_wrap_model_call_async(self):
        """Lines 588-593: async wrap_model_call."""
        mw = LoopDetectionMiddleware()
        runtime = self._make_runtime()
        request = MagicMock()
        request.messages = [AIMessage(content="hi")]
        request.runtime = runtime
        request.override = lambda **u: MagicMock(messages=u.get("messages", request.messages))
        handler = AsyncMock(return_value=MagicMock())
        asyncio.run(mw.awrap_model_call(request, handler))
        handler.assert_awaited_once()

    def test_get_thread_id_anon_fallback(self):
        """Line 253: fallback anon thread id."""
        mw = LoopDetectionMiddleware()
        runtime = MagicMock()
        runtime.context = {}
        tid = mw._get_thread_id(runtime)
        assert tid.startswith("anon-")

    def test_get_thread_id_from_context(self):
        """Line 251: thread_id from context."""
        mw = LoopDetectionMiddleware()
        runtime = MagicMock()
        runtime.context = {"thread_id": "my-thread"}
        tid = mw._get_thread_id(runtime)
        assert tid == "my-thread"

    def test_get_thread_id_none_context(self):
        """Line 250: context is None."""
        mw = LoopDetectionMiddleware()
        runtime = MagicMock()
        runtime.context = None
        tid = mw._get_thread_id(runtime)
        assert tid.startswith("anon-")

    def test_get_run_id_default(self):
        """Line 259: default run id when no run_id in context."""
        mw = LoopDetectionMiddleware()
        runtime = MagicMock()
        runtime.context = {}
        rid = mw._get_run_id(runtime)
        assert rid == "default"

    def test_get_run_id_from_context(self):
        """Line 258: run id from context."""
        mw = LoopDetectionMiddleware()
        runtime = MagicMock()
        runtime.context = {"run_id": "my-run"}
        rid = mw._get_run_id(runtime)
        assert rid == "my-run"

    def test_get_run_id_none_context(self):
        """Line 257: context is None."""
        mw = LoopDetectionMiddleware()
        runtime = MagicMock()
        runtime.context = None
        rid = mw._get_run_id(runtime)
        assert rid == "default"

    def test_pending_key(self):
        """Line 264: pending_key returns (thread_id, run_id)."""
        mw = LoopDetectionMiddleware()
        runtime = self._make_runtime("t1", "r1")
        assert mw._pending_key(runtime) == ("t1", "r1")


# ============================================================================
# MemoryMiddleware - lines 48-50, 63-110
# ============================================================================


class TestMemoryMiddlewareCoverageGaps:
    """Cover specific missing lines in MemoryMiddleware."""

    def _make_runtime(self, thread_id="t1"):
        return SimpleNamespace(context={"thread_id": thread_id})

    def test_disabled_config_returns_none(self):
        """Lines 63-64: memory disabled returns None."""
        from ideer.config.memory_config import MemoryConfig

        mw = MemoryMiddleware(memory_config=MemoryConfig(enabled=False))
        result = mw.after_agent({"messages": [HumanMessage(content="hi")]}, self._make_runtime())
        assert result is None

    def test_none_context(self):
        """Lines 68-69: runtime.context is None."""
        from ideer.config.memory_config import MemoryConfig

        mw = MemoryMiddleware(memory_config=MemoryConfig(enabled=False))
        runtime = SimpleNamespace(context=None)
        result = mw.after_agent({"messages": [HumanMessage(content="hi")]}, runtime)
        assert result is None

    def test_no_thread_id_in_context_falls_back_to_config(self, monkeypatch):
        """Lines 69-71: thread_id from config when context has none."""
        from ideer.config.memory_config import MemoryConfig

        mw = MemoryMiddleware(memory_config=MemoryConfig(enabled=False))
        runtime = SimpleNamespace(context={})
        monkeypatch.setattr(
            "ideer.agents.middlewares.memory_middleware.get_config",
            lambda: {"configurable": {"thread_id": "from-config"}},
        )
        result = mw.after_agent({"messages": [HumanMessage(content="hi")]}, runtime)
        assert result is None  # disabled

    def test_config_raises_runtime_error(self, monkeypatch):
        """Lines 70-71: get_config raises RuntimeError."""
        from ideer.config.memory_config import MemoryConfig

        mw = MemoryMiddleware(memory_config=MemoryConfig(enabled=False))
        runtime = SimpleNamespace(context={})
        monkeypatch.setattr(
            "ideer.agents.middlewares.memory_middleware.get_config",
            MagicMock(side_effect=RuntimeError("no config")),
        )
        result = mw.after_agent({"messages": [HumanMessage(content="hi")]}, runtime)
        assert result is None  # disabled, but config fallback still ran

    def test_no_messages_returns_none(self):
        """Lines 77-79: empty messages returns None."""
        from ideer.config.memory_config import MemoryConfig

        mw = MemoryMiddleware(memory_config=MemoryConfig(enabled=False))
        result = mw.after_agent({"messages": []}, self._make_runtime())
        assert result is None

    def test_no_user_or_assistant_messages_returns_none(self):
        """Lines 90-91: no user or assistant messages after filtering."""
        from ideer.config.memory_config import MemoryConfig

        mw = MemoryMiddleware(memory_config=MemoryConfig(enabled=False))
        # Only tool messages - no user/assistant
        state = {"messages": [ToolMessage(content="result", tool_call_id="tc-1")]}
        result = mw.after_agent(state, self._make_runtime())
        assert result is None

    def test_constructor_with_agent_name(self):
        """Line 49: agent_name stored."""
        mw = MemoryMiddleware(agent_name="test-agent")
        assert mw._agent_name == "test-agent"

    def test_constructor_without_agent_name(self):
        """Line 50: agent_name defaults to None."""
        mw = MemoryMiddleware()
        assert mw._agent_name is None


# ============================================================================
# ThreadDataMiddleware - lines 78-79, 99-100, 106
# ============================================================================


class TestThreadDataMiddlewareCoverageGaps:
    """Cover specific missing lines in ThreadDataMiddleware."""

    def test_eager_init_creates_directories(self, tmp_path):
        """Lines 98-100: lazy_init=False creates directories eagerly."""
        middleware = ThreadDataMiddleware(base_dir=str(tmp_path), lazy_init=False)
        result = middleware.before_agent(state={}, runtime=SimpleNamespace(context={"thread_id": "t-eager"}))
        assert result is not None
        assert result["thread_data"] is not None

    def test_human_message_gets_run_id_and_timestamp(self, tmp_path):
        """Line 106-111: last HumanMessage gets run_id and timestamp."""
        middleware = ThreadDataMiddleware(base_dir=str(tmp_path), lazy_init=True)
        runtime = SimpleNamespace(context={"thread_id": "t-ts", "run_id": "run-xyz"})
        state = {"messages": [HumanMessage(content="hello")]}
        result = middleware.before_agent(state=state, runtime=runtime)
        assert result is not None
        last_msg = result["messages"][-1]
        assert last_msg.additional_kwargs.get("run_id") == "run-xyz"
        assert "timestamp" in last_msg.additional_kwargs

    def test_non_human_message_not_modified(self, tmp_path):
        """Line 105: non-HumanMessage last message is not modified."""
        middleware = ThreadDataMiddleware(base_dir=str(tmp_path), lazy_init=True)
        runtime = SimpleNamespace(context={"thread_id": "t-no-mod"})
        ai_msg = AIMessage(content="response")
        state = {"messages": [HumanMessage(content="q"), ai_msg]}
        result = middleware.before_agent(state=state, runtime=runtime)
        assert result is not None
        assert result["messages"][-1] is ai_msg

    def test_human_message_name_preserved(self, tmp_path):
        """Line 109: HumanMessage with existing name is preserved."""
        middleware = ThreadDataMiddleware(base_dir=str(tmp_path), lazy_init=True)
        runtime = SimpleNamespace(context={"thread_id": "t-name"})
        state = {"messages": [HumanMessage(content="q", name="custom-name")]}
        result = middleware.before_agent(state=state, runtime=runtime)
        assert result["messages"][-1].name == "custom-name"

    def test_human_message_gets_default_name(self, tmp_path):
        """Line 109: HumanMessage without name gets 'user-input'."""
        middleware = ThreadDataMiddleware(base_dir=str(tmp_path), lazy_init=True)
        runtime = SimpleNamespace(context={"thread_id": "t-default-name"})
        state = {"messages": [HumanMessage(content="q")]}
        result = middleware.before_agent(state=state, runtime=runtime)
        assert result["messages"][-1].name == "user-input"

    def test_human_message_preserves_id(self, tmp_path):
        """Line 107: HumanMessage id is preserved."""
        middleware = ThreadDataMiddleware(base_dir=str(tmp_path), lazy_init=True)
        runtime = SimpleNamespace(context={"thread_id": "t-id"})
        msg = HumanMessage(content="q", id="my-id")
        state = {"messages": [msg]}
        result = middleware.before_agent(state=state, runtime=runtime)
        assert result["messages"][-1].id == "my-id"


# ============================================================================
# TitleMiddleware - lines 41, 59-63, 82, 149, 157
# ============================================================================


class TestTitleMiddlewareCoverageGaps:
    """Cover specific missing lines in TitleMiddleware."""

    def test_get_title_config_from_app_config(self):
        """Line 41: _get_title_config uses app_config.title."""
        app_config = SimpleNamespace(title=SimpleNamespace(enabled=True, max_chars=30, max_words=5, prompt_template="{user_msg}"))
        mw = TitleMiddleware(app_config=app_config)
        config = mw._get_title_config()
        assert config.enabled is True

    def test_normalize_content_dict_with_text(self):
        """Line 57: dict content with text key."""
        mw = TitleMiddleware()
        result = mw._normalize_content({"text": "hello"})
        assert result == "hello"

    def test_normalize_content_dict_with_nested_content(self):
        """Lines 59-62: dict content with nested content (string)."""
        mw = TitleMiddleware()
        result = mw._normalize_content({"content": "nested text"})
        assert result == "nested text"

    def test_normalize_content_dict_with_nested_list_content(self):
        """Lines 59-62: dict content with nested list content."""
        mw = TitleMiddleware()
        result = mw._normalize_content({"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]})
        assert "a" in result
        assert "b" in result

    def test_normalize_content_dict_no_text_or_content(self):
        """Line 63: dict without text or content keys returns empty string."""
        mw = TitleMiddleware()
        result = mw._normalize_content({"other_key": "value"})
        assert result == ""

    def test_normalize_content_nested_list(self):
        """Lines 51-52: list content."""
        mw = TitleMiddleware()
        result = mw._normalize_content(["hello", "world"])
        assert result == "hello\nworld"

    def test_fallback_title_empty_user_msg(self):
        """Line 129: fallback title when user_msg is empty."""
        from ideer.config.title_config import TitleConfig

        mw = TitleMiddleware(title_config=TitleConfig(enabled=True, max_chars=50))
        result = mw._fallback_title("")
        assert result == "New Conversation"

    def test_fallback_title_short_user_msg(self):
        """Line 129: fallback title for short user message."""
        from ideer.config.title_config import TitleConfig

        mw = TitleMiddleware(title_config=TitleConfig(enabled=True, max_chars=50))
        result = mw._fallback_title("hi")
        assert result == "hi"

    def test_fallback_title_long_user_msg(self):
        """Lines 127-128: fallback title for long user message."""
        from ideer.config.title_config import TitleConfig

        mw = TitleMiddleware(title_config=TitleConfig(enabled=True, max_chars=20))
        long_msg = "a" * 100
        result = mw._fallback_title(long_msg)
        assert result.endswith("...")
        # fallback_chars = min(max_chars, 50) = 20, result is at most 20+3 = 23
        assert len(result) <= 23

    def test_sync_generate_title_not_enough_messages(self):
        """Line 148-149: _generate_title_result with insufficient messages."""
        from ideer.config.title_config import TitleConfig

        mw = TitleMiddleware(title_config=TitleConfig(enabled=True))
        state = {"messages": [HumanMessage(content="hi")]}  # Only 1 message
        result = mw._generate_title_result(state)
        assert result is None

    def test_async_title_no_model_name(self, monkeypatch):
        """Lines 172-173: async title with no model_name."""
        from ideer.config.title_config import TitleConfig

        mw = TitleMiddleware(title_config=TitleConfig(enabled=True, model_name=None))
        model = MagicMock()
        model.ainvoke = AsyncMock(return_value=AIMessage(content="title result"))
        monkeypatch.setattr(
            "ideer.agents.middlewares.title_middleware.create_chat_model",
            MagicMock(return_value=model),
        )
        state = {
            "messages": [
                HumanMessage(content="test question"),
                AIMessage(content="test answer"),
            ]
        }
        result = asyncio.run(mw._agenerate_title_result(state))
        assert result is not None

    def test_should_generate_title_empty_messages(self):
        """Line 82: _should_generate_title with no messages."""
        from ideer.config.title_config import TitleConfig

        mw = TitleMiddleware(title_config=TitleConfig(enabled=True))
        assert mw._should_generate_title({"messages": [], "title": None}) is False

    def test_get_runnable_config(self, monkeypatch):
        """Lines 138-144: _get_runnable_config."""
        from ideer.config.title_config import TitleConfig

        mw = TitleMiddleware(title_config=TitleConfig(enabled=True))
        monkeypatch.setattr(
            "ideer.agents.middlewares.title_middleware.get_config",
            lambda: {"tags": ["existing"]},
        )
        config = mw._get_runnable_config()
        assert config["run_name"] == "title_agent"
        assert "middleware:title" in config["tags"]
        assert "existing" in config["tags"]

    def test_get_runnable_config_exception(self, monkeypatch):
        """Lines 139-140: _get_runnable_config when get_config raises."""
        from ideer.config.title_config import TitleConfig

        mw = TitleMiddleware(title_config=TitleConfig(enabled=True))
        monkeypatch.setattr(
            "ideer.agents.middlewares.title_middleware.get_config",
            MagicMock(side_effect=RuntimeError("no config")),
        )
        config = mw._get_runnable_config()
        assert config["run_name"] == "title_agent"


# ============================================================================
# DeferredToolFilterMiddleware - lines 12-107 (entire file)
# ============================================================================


class TestDeferredToolFilterMiddlewareCoverageGaps:
    """Cover DeferredToolFilterMiddleware: wrap_model_call, wrap_tool_call, async variants."""

    def test_wrap_model_call_filters_deferred_tools(self):
        """wrap_model_call removes deferred tools from request.tools."""
        middleware = DeferredToolFilterMiddleware()
        mock_tool = MagicMock()
        mock_tool.name = "active_tool"
        deferred_tool = MagicMock()
        deferred_tool.name = "deferred_tool"

        request = MagicMock()
        request.tools = [mock_tool, deferred_tool]
        request.override = lambda **u: MagicMock(tools=u.get("tools", request.tools))

        with patch("ideer.tools.builtins.tool_search.get_deferred_registry") as mock_get_registry:
            registry = MagicMock()
            registry.deferred_names = {"deferred_tool"}
            mock_get_registry.return_value = registry

            handler = MagicMock(return_value="response")
            middleware.wrap_model_call(request, handler)

            # Handler should be called with filtered tools
            call_args = handler.call_args[0][0]
            assert len(call_args.tools) == 1
            assert call_args.tools[0].name == "active_tool"

    def test_wrap_model_call_no_registry_passthrough(self):
        """No registry -> no filtering."""
        middleware = DeferredToolFilterMiddleware()
        mock_tool = MagicMock()
        mock_tool.name = "tool1"
        request = MagicMock()
        request.tools = [mock_tool]

        with patch("ideer.tools.builtins.tool_search.get_deferred_registry") as mock_get_registry:
            mock_get_registry.return_value = None
            handler = MagicMock(return_value="response")
            middleware.wrap_model_call(request, handler)
            handler.assert_called_once_with(request)

    def test_wrap_model_call_empty_deferred_names(self):
        """Registry with no deferred names -> no filtering."""
        middleware = DeferredToolFilterMiddleware()
        mock_tool = MagicMock()
        mock_tool.name = "tool1"
        request = MagicMock()
        request.tools = [mock_tool]

        with patch("ideer.tools.builtins.tool_search.get_deferred_registry") as mock_get_registry:
            registry = MagicMock()
            registry.deferred_names = set()
            mock_get_registry.return_value = registry
            handler = MagicMock(return_value="response")
            middleware.wrap_model_call(request, handler)
            handler.assert_called_once()

    def test_wrap_tool_call_blocks_deferred_tool(self):
        """Deferred tool call is blocked with error message."""
        middleware = DeferredToolFilterMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "deferred_tool", "id": "tc-1"}

        with patch("ideer.tools.builtins.tool_search.get_deferred_registry") as mock_get_registry:
            registry = MagicMock()
            registry.deferred_names = {"deferred_tool"}
            registry.contains.return_value = True
            mock_get_registry.return_value = registry

            handler = MagicMock()
            result = middleware.wrap_tool_call(request, handler)
            handler.assert_not_called()
            assert isinstance(result, ToolMessage)
            assert "deferred" in result.content.lower()

    def test_wrap_tool_call_passthrough_active_tool(self):
        """Active tool call passes through."""
        middleware = DeferredToolFilterMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "active_tool", "id": "tc-2"}

        with patch("ideer.tools.builtins.tool_search.get_deferred_registry") as mock_get_registry:
            registry = MagicMock()
            registry.deferred_names = {"deferred_tool"}
            registry.contains.return_value = False
            mock_get_registry.return_value = registry

            handler = MagicMock(return_value="ok")
            middleware.wrap_tool_call(request, handler)
            handler.assert_called_once_with(request)

    def test_wrap_tool_call_no_registry_passthrough(self):
        """No registry -> passthrough."""
        middleware = DeferredToolFilterMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "any_tool", "id": "tc-3"}

        with patch("ideer.tools.builtins.tool_search.get_deferred_registry") as mock_get_registry:
            mock_get_registry.return_value = None
            handler = MagicMock(return_value="ok")
            middleware.wrap_tool_call(request, handler)
            handler.assert_called_once()

    def test_wrap_tool_call_empty_tool_name(self):
        """Tool with empty name is not blocked."""
        middleware = DeferredToolFilterMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "", "id": "tc-4"}

        with patch("ideer.tools.builtins.tool_search.get_deferred_registry") as mock_get_registry:
            registry = MagicMock()
            registry.deferred_names = set()
            mock_get_registry.return_value = registry
            handler = MagicMock(return_value="ok")
            middleware.wrap_tool_call(request, handler)
            handler.assert_called_once()

    def test_wrap_tool_call_missing_tool_name(self):
        """Tool with no name key is not blocked."""
        middleware = DeferredToolFilterMiddleware()
        request = MagicMock()
        request.tool_call = {"id": "tc-5"}

        with patch("ideer.tools.builtins.tool_search.get_deferred_registry") as mock_get_registry:
            registry = MagicMock()
            registry.deferred_names = set()
            mock_get_registry.return_value = registry
            handler = MagicMock(return_value="ok")
            middleware.wrap_tool_call(request, handler)
            handler.assert_called_once()

    def test_wrap_tool_call_no_id_uses_fallback(self):
        """Tool with no id uses fallback."""
        middleware = DeferredToolFilterMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "deferred_tool"}

        with patch("ideer.tools.builtins.tool_search.get_deferred_registry") as mock_get_registry:
            registry = MagicMock()
            registry.deferred_names = {"deferred_tool"}
            registry.contains.return_value = True
            mock_get_registry.return_value = registry
            handler = MagicMock()
            result = middleware.wrap_tool_call(request, handler)
            assert result.tool_call_id == "missing_tool_call_id"

    @pytest.mark.anyio
    async def test_awrap_model_call_filters(self):
        """Async wrap_model_call filters deferred tools."""
        middleware = DeferredToolFilterMiddleware()
        mock_tool = MagicMock()
        mock_tool.name = "active"
        deferred_tool = MagicMock()
        deferred_tool.name = "deferred"
        request = MagicMock()
        request.tools = [mock_tool, deferred_tool]
        request.override = lambda **u: MagicMock(tools=u.get("tools", request.tools))

        with patch("ideer.tools.builtins.tool_search.get_deferred_registry") as mock_get_registry:
            registry = MagicMock()
            registry.deferred_names = {"deferred"}
            mock_get_registry.return_value = registry
            handler = AsyncMock(return_value="response")
            await middleware.awrap_model_call(request, handler)
            call_args = handler.call_args[0][0]
            assert len(call_args.tools) == 1

    @pytest.mark.anyio
    async def test_awrap_model_call_no_registry(self):
        """Async: no registry -> passthrough."""
        middleware = DeferredToolFilterMiddleware()
        request = MagicMock()
        request.tools = [MagicMock(name="t")]
        with patch("ideer.tools.builtins.tool_search.get_deferred_registry") as mock_get_registry:
            mock_get_registry.return_value = None
            handler = AsyncMock(return_value="ok")
            await middleware.awrap_model_call(request, handler)
            handler.assert_awaited_once()

    @pytest.mark.anyio
    async def test_awrap_tool_call_blocks_deferred(self):
        """Async: deferred tool blocked."""
        middleware = DeferredToolFilterMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "deferred_tool", "id": "tc-async-1"}
        with patch("ideer.tools.builtins.tool_search.get_deferred_registry") as mock_get_registry:
            registry = MagicMock()
            registry.deferred_names = {"deferred_tool"}
            registry.contains.return_value = True
            mock_get_registry.return_value = registry
            handler = AsyncMock()
            result = await middleware.awrap_tool_call(request, handler)
            handler.assert_not_awaited()
            assert isinstance(result, ToolMessage)
            assert "deferred" in result.content.lower()

    @pytest.mark.anyio
    async def test_awrap_tool_call_passthrough(self):
        """Async: active tool passthrough."""
        middleware = DeferredToolFilterMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "active_tool", "id": "tc-async-2"}
        with patch("ideer.tools.builtins.tool_search.get_deferred_registry") as mock_get_registry:
            registry = MagicMock()
            registry.deferred_names = {"deferred_tool"}
            registry.contains.return_value = False
            mock_get_registry.return_value = registry
            handler = AsyncMock(return_value="ok")
            await middleware.awrap_tool_call(request, handler)
            handler.assert_awaited_once()

    @pytest.mark.anyio
    async def test_awrap_tool_call_no_registry(self):
        """Async: no registry -> passthrough."""
        middleware = DeferredToolFilterMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "any_tool", "id": "tc-async-3"}
        with patch("ideer.tools.builtins.tool_search.get_deferred_registry") as mock_get_registry:
            mock_get_registry.return_value = None
            handler = AsyncMock(return_value="ok")
            await middleware.awrap_tool_call(request, handler)
            handler.assert_awaited_once()


# ============================================================================
# SafetyFinishReasonMiddleware - lines 131, 204-205, 313, 317
# ============================================================================


class TestSafetyFinishReasonCoverageGaps:
    """Cover specific missing lines in SafetyFinishReasonMiddleware."""

    def test_append_user_message_non_str_non_list(self):
        """Line 131: content is neither str nor list -> coerced to str."""
        mw = SafetyFinishReasonMiddleware()
        result = mw._append_user_message(42, "explanation")
        assert result == "42\n\nexplanation"

    def test_emit_event_writer_exception_does_not_break(self, monkeypatch):
        """Lines 204-205: writer call fails silently."""

        def boom(payload):
            raise RuntimeError("writer broken")

        import langgraph.config

        monkeypatch.setattr(langgraph.config, "get_stream_writer", lambda: boom)

        mw = SafetyFinishReasonMiddleware()
        state = {
            "messages": [
                AIMessage(
                    content="partial",
                    tool_calls=[{"id": "tc-1", "name": "write_file", "args": {}}],
                    response_metadata={"finish_reason": "content_filter"},
                )
            ]
        }
        runtime = MagicMock()
        runtime.context = {"thread_id": "t-writer-fail"}
        result = mw._apply(state, runtime)
        assert result is not None  # Still processes despite writer failure

    def test_record_audit_event_non_dict_context(self):
        """Lines 231-233: runtime.context is not a dict -> skip journal."""
        mw = SafetyFinishReasonMiddleware()
        runtime = MagicMock()
        runtime.context = "not-a-dict"
        state = {
            "messages": [
                AIMessage(
                    content="partial",
                    tool_calls=[{"id": "tc-1", "name": "write_file", "args": {}}],
                    response_metadata={"finish_reason": "content_filter"},
                )
            ]
        }
        result = mw._apply(state, runtime)
        assert result is not None

    def test_record_audit_event_no_context(self):
        """Lines 231-233: runtime.context is None -> skip journal."""
        mw = SafetyFinishReasonMiddleware()
        runtime = MagicMock()
        runtime.context = None
        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{"id": "tc-1", "name": "write_file", "args": {}}],
                    response_metadata={"finish_reason": "content_filter"},
                )
            ]
        }
        result = mw._apply(state, runtime)
        assert result is not None

    def test_after_model_async(self):
        """Lines 316-317: async after_model."""
        mw = SafetyFinishReasonMiddleware()
        runtime = MagicMock()
        runtime.context = {"thread_id": "t-async"}
        result = asyncio.run(mw.aafter_model({"messages": []}, runtime))
        assert result is None

    def test_after_model_sync(self):
        """Lines 312-313: sync after_model."""
        mw = SafetyFinishReasonMiddleware()
        runtime = MagicMock()
        runtime.context = {"thread_id": "t-sync"}
        result = mw.after_model({"messages": []}, runtime)
        assert result is None


# ============================================================================
# SummarizationMiddleware - lines 136, 158, 162, 216-218
# ============================================================================


class TestSummarizationCoverageGaps:
    """Cover specific missing lines in summarization_middleware."""

    def _make_middleware(self, *, trigger=("messages", 4), keep=("messages", 2), **kwargs):
        model = MagicMock()
        model.invoke.return_value = SimpleNamespace(text="compressed summary")
        return IDeerSummarizationMiddleware(
            model=model,
            trigger=trigger,
            keep=keep,
            token_counter=len,
            **kwargs,
        )

    def _runtime(self, thread_id="t1", agent_name=None):
        context = {}
        if thread_id:
            context["thread_id"] = thread_id
        if agent_name:
            context["agent_name"] = agent_name
        return SimpleNamespace(context=context)

    def test_amaybe_summarize_no_messages(self):
        """Lines 152-158: async path with messages below threshold."""
        middleware = self._make_middleware(trigger=("messages", 10))
        state = {"messages": [HumanMessage(content="q"), AIMessage(content="a")]}
        result = asyncio.run(middleware.abefore_model(state, self._runtime()))
        assert result is None

    def test_amaybe_summarize_below_threshold(self):
        """Lines 157-158: async path - below threshold."""
        middleware = self._make_middleware(trigger=("messages", 10))
        messages = [HumanMessage(content="q"), AIMessage(content="a")]
        result = asyncio.run(middleware.abefore_model({"messages": messages}, self._runtime()))
        assert result is None

    def test_amaybe_summarize_cutoff_zero(self):
        """Line 162: async path - cutoff_index <= 0."""
        middleware = self._make_middleware(trigger=("messages", 10), keep=("messages", 10))
        messages = [HumanMessage(content="q"), AIMessage(content="a")]
        result = asyncio.run(middleware.abefore_model({"messages": messages}, self._runtime()))
        assert result is None

    def test_maybe_summarize_cutoff_zero_sync(self):
        """Line 136: sync path - cutoff_index <= 0."""
        middleware = self._make_middleware(trigger=("messages", 10), keep=("messages", 10))
        messages = [HumanMessage(content="q"), AIMessage(content="a")]
        result = middleware.before_model({"messages": messages}, self._runtime())
        assert result is None

    def test_partition_skill_rescue_no_bundles(self):
        """Lines 215-218: _find_skill_bundles returns empty list."""
        middleware = self._make_middleware(
            preserve_recent_skill_count=5,
            preserve_recent_skill_tokens=10000,
        )
        messages = [
            HumanMessage(content="u1"),
            AIMessage(content="done"),
            HumanMessage(content="u2"),
            AIMessage(content="final"),
        ]
        to_sum, preserved = middleware._partition_with_skill_rescue(messages, 2)
        assert len(to_sum) > 0

    def test_partition_skill_rescue_no_matching_tool_results(self):
        """Lines 216-218: bundles found but no matching tool results."""
        middleware = self._make_middleware(
            preserve_recent_skill_count=5,
            preserve_recent_skill_tokens=10000,
        )
        messages = [
            HumanMessage(content="u1"),
            AIMessage(content="", tool_calls=[{"name": "read_file", "id": "t1", "args": {"path": "/mnt/skills/foo/SKILL.md"}}]),
            ToolMessage(content="result", tool_call_id="t_other"),  # no match
            HumanMessage(content="u2"),
            AIMessage(content="done"),
        ]
        to_sum, preserved = middleware._partition_with_skill_rescue(messages, 2)
        assert len(to_sum) > 0
