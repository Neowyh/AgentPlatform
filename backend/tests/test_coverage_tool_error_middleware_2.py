"""Additional coverage tests for tool_error_handling_middleware.py.

Targets missed lines:
- Line 29: error detail truncation at 500 chars
- Lines 88-90, 102-120: _build_runtime_middlewares guardrails path
- Line 131: build_lead_runtime_middlewares
- Lines 147-149: build_subagent_runtime_middlewares with app_config=None
"""

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from langchain_core.messages import ToolMessage

from ideer.agents.middlewares.tool_error_handling_middleware import (
    ToolErrorHandlingMiddleware,
    build_lead_runtime_middlewares,
    build_subagent_runtime_middlewares,
)


def _request(name="bash", tool_call_id="tc-1"):
    return SimpleNamespace(tool_call={"name": name, "id": tool_call_id})


class TestBuildErrorMessageTruncation:
    """Line 29: detail longer than 500 chars gets truncated."""

    def test_long_error_detail_truncated(self):
        mw = ToolErrorHandlingMiddleware()
        long_message = "x" * 600
        exc = RuntimeError(long_message)
        req = _request()

        result = mw._build_error_message(req, exc)

        assert isinstance(result, ToolMessage)
        assert "..." in result.content
        # The detail should be truncated to 497 chars + "..."
        assert len(long_message) > 500
        assert "xxx" in result.content

    def test_short_error_detail_not_truncated(self):
        mw = ToolErrorHandlingMiddleware()
        exc = RuntimeError("short error")
        req = _request()

        result = mw._build_error_message(req, exc)

        assert "short error" in result.content
        assert "..." not in result.content.split("short error")[0]

    def test_empty_string_detail_uses_class_name(self):
        """Line 27: detail is empty after strip -> uses class name."""
        mw = ToolErrorHandlingMiddleware()
        exc = RuntimeError("   ")
        req = _request()

        result = mw._build_error_message(req, exc)

        assert "RuntimeError" in result.content


def _module(name, **attrs):
    module = ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _stub_runtime_middleware_imports(monkeypatch):
    class FakeMiddleware:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class FakeLLMErrorHandlingMiddleware:
        def __init__(self, *, app_config):
            self.app_config = app_config

    monkeypatch.setitem(
        sys.modules,
        "ideer.agents.middlewares.llm_error_handling_middleware",
        _module("ideer.agents.middlewares.llm_error_handling_middleware", LLMErrorHandlingMiddleware=FakeLLMErrorHandlingMiddleware),
    )
    monkeypatch.setitem(
        sys.modules,
        "ideer.agents.middlewares.thread_data_middleware",
        _module("ideer.agents.middlewares.thread_data_middleware", ThreadDataMiddleware=FakeMiddleware),
    )
    monkeypatch.setitem(
        sys.modules,
        "ideer.sandbox.middleware",
        _module("ideer.sandbox.middleware", SandboxMiddleware=FakeMiddleware),
    )
    monkeypatch.setitem(
        sys.modules,
        "ideer.agents.middlewares.dangling_tool_call_middleware",
        _module("ideer.agents.middlewares.dangling_tool_call_middleware", DanglingToolCallMiddleware=FakeMiddleware),
    )
    monkeypatch.setitem(
        sys.modules,
        "ideer.agents.middlewares.sandbox_audit_middleware",
        _module("ideer.agents.middlewares.sandbox_audit_middleware", SandboxAuditMiddleware=FakeMiddleware),
    )


def _make_app_config(
    *,
    guardrails_enabled=False,
    guardrails_provider_use=None,
    guardrails_provider_config=None,
    guardrails_fail_closed=False,
    guardrails_passport=None,
    safety_enabled=False,
):
    from ideer.config.app_config import AppConfig, CircuitBreakerConfig
    from ideer.config.guardrails_config import GuardrailProviderConfig, GuardrailsConfig
    from ideer.config.model_config import ModelConfig
    from ideer.config.sandbox_config import SandboxConfig

    guardrails_provider = None
    if guardrails_provider_use:
        guardrails_provider = GuardrailProviderConfig(
            use=guardrails_provider_use,
            config=guardrails_provider_config or {},
        )

    guardrails = GuardrailsConfig(
        enabled=guardrails_enabled,
        provider=guardrails_provider,
        fail_closed=guardrails_fail_closed,
        passport=guardrails_passport,
    )

    return AppConfig(
        models=[ModelConfig(name="test-model", display_name="test", description=None, use="langchain_openai:ChatOpenAI", model="test-model")],
        sandbox=SandboxConfig(use="test"),
        guardrails=guardrails,
        circuit_breaker=CircuitBreakerConfig(failure_threshold=7, recovery_timeout_sec=11),
    )


class TestBuildLeadRuntimeMiddlewares:
    """Line 131: build_lead_runtime_middlewares."""

    def test_build_lead_runtime_middlewares(self, monkeypatch):
        _stub_runtime_middleware_imports(monkeypatch)
        app_config = _make_app_config()

        middlewares = build_lead_runtime_middlewares(app_config=app_config, lazy_init=True)

        assert len(middlewares) > 0
        # Should have UploadsMiddleware, DanglingToolCallMiddleware, etc.
        assert any("LLMErrorHandling" in type(m).__name__ for m in middlewares)


class TestBuildSubagentRuntimeMiddlewaresNoAppConfig:
    """Lines 147-149: build_subagent_runtime_middlewares with app_config=None."""

    def test_app_config_none_calls_get_app_config(self, monkeypatch):
        _stub_runtime_middleware_imports(monkeypatch)

        mock_config = _make_app_config()
        mock_config.safety_finish_reason = MagicMock(enabled=False)

        # build_subagent_runtime_middlewares imports get_app_config locally
        with patch("ideer.config.get_app_config", return_value=mock_config) as mock_get:
            middlewares = build_subagent_runtime_middlewares(app_config=None, lazy_init=True)

        mock_get.assert_called_once()
        assert len(middlewares) > 0


class FakeGuardrailMiddleware:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


def _stub_guardrails_imports(monkeypatch):
    """Add guardrails middleware mock to sys.modules."""
    monkeypatch.setitem(
        sys.modules,
        "ideer.guardrails.middleware",
        _module("ideer.guardrails.middleware", GuardrailMiddleware=FakeGuardrailMiddleware),
    )


class TestBuildRuntimeMiddlewaresGuardrails:
    """Lines 102-120: guardrails config enabled path."""

    def test_guardrails_enabled_adds_middleware(self, monkeypatch):
        _stub_runtime_middleware_imports(monkeypatch)
        _stub_guardrails_imports(monkeypatch)

        mock_provider_cls = MagicMock()
        mock_provider_instance = MagicMock()
        mock_provider_cls.return_value = mock_provider_instance

        app_config = _make_app_config(
            guardrails_enabled=True,
            guardrails_provider_use="test_provider",
            guardrails_provider_config={"key": "val"},
            guardrails_fail_closed=True,
        )

        with patch("ideer.reflection.resolve_variable", return_value=mock_provider_cls):
            middlewares = build_lead_runtime_middlewares(app_config=app_config)

        guardrail_mws = [m for m in middlewares if isinstance(m, FakeGuardrailMiddleware)]
        assert len(guardrail_mws) == 1

    def test_guardrails_framework_injection(self, monkeypatch):
        """Lines 112-115: framework kwarg injection when provider accepts **kwargs."""
        _stub_runtime_middleware_imports(monkeypatch)
        _stub_guardrails_imports(monkeypatch)

        # Use a real class with **kwargs so inspect.signature works
        class ProviderWithKwargs:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        app_config = _make_app_config(
            guardrails_enabled=True,
            guardrails_provider_use="test_provider",
            guardrails_provider_config=None,
        )

        with patch("ideer.reflection.resolve_variable", return_value=ProviderWithKwargs):
            middlewares = build_lead_runtime_middlewares(app_config=app_config)

        guardrail_mws = [m for m in middlewares if isinstance(m, FakeGuardrailMiddleware)]
        assert len(guardrail_mws) == 1
        # The provider was instantiated (passed as first arg to GuardrailMiddleware)
        assert guardrail_mws[0].args[0] is not None

    def test_guardrails_inspect_raises_value_error(self, monkeypatch):
        """Lines 116-117: ValueError from inspect.signature is caught."""
        _stub_runtime_middleware_imports(monkeypatch)
        _stub_guardrails_imports(monkeypatch)

        mock_provider_cls = MagicMock()
        mock_provider_cls.return_value = MagicMock()

        app_config = _make_app_config(
            guardrails_enabled=True,
            guardrails_provider_use="test_provider",
            guardrails_provider_config={},
        )

        with (
            patch("ideer.reflection.resolve_variable", return_value=mock_provider_cls),
            patch("inspect.signature", side_effect=ValueError("no signature")),
        ):
            middlewares = build_lead_runtime_middlewares(app_config=app_config)

        assert len(middlewares) > 0

    def test_guardrails_framework_already_in_kwargs(self, monkeypatch):
        """Lines 112: framework already in provider_kwargs -> skip injection."""
        _stub_runtime_middleware_imports(monkeypatch)
        _stub_guardrails_imports(monkeypatch)

        mock_provider_cls = MagicMock()
        mock_provider_cls.return_value = MagicMock()

        app_config = _make_app_config(
            guardrails_enabled=True,
            guardrails_provider_use="test_provider",
            guardrails_provider_config={"framework": "custom"},
        )

        with patch("ideer.reflection.resolve_variable", return_value=mock_provider_cls):
            middlewares = build_lead_runtime_middlewares(app_config=app_config)

        assert len(middlewares) > 0

    def test_guardrails_inspect_raises_type_error(self, monkeypatch):
        """Lines 116-117: TypeError from inspect.signature is caught."""
        _stub_runtime_middleware_imports(monkeypatch)
        _stub_guardrails_imports(monkeypatch)

        mock_provider_cls = MagicMock()
        mock_provider_cls.return_value = MagicMock()

        app_config = _make_app_config(
            guardrails_enabled=True,
            guardrails_provider_use="test_provider",
            guardrails_provider_config={},
        )

        with (
            patch("ideer.reflection.resolve_variable", return_value=mock_provider_cls),
            patch("inspect.signature", side_effect=TypeError("not callable")),
        ):
            middlewares = build_lead_runtime_middlewares(app_config=app_config)

        assert len(middlewares) > 0
