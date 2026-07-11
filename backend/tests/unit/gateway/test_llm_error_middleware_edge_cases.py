"""Additional tests for llm_error_handling_middleware — coverage gaps."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from ideer.agents.middlewares.llm_error_handling_middleware import (
    LLMErrorHandlingMiddleware,
    _extract_error_code,
    _extract_error_detail,
    _extract_retry_after_ms,
    _extract_status_code,
    _matches_any,
)
from ideer.config.app_config import AppConfig
from ideer.config.sandbox_config import SandboxConfig


def _make_app_config() -> AppConfig:
    return AppConfig(sandbox=SandboxConfig(use="test"))


def _build_middleware(**attrs: int) -> LLMErrorHandlingMiddleware:
    middleware = LLMErrorHandlingMiddleware(app_config=_make_app_config())
    for key, value in attrs.items():
        setattr(middleware, key, value)
    return middleware


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestMatchesAny:
    def test_match_found(self):
        assert _matches_any("server busy", ("server busy", "overloaded")) is True

    def test_no_match(self):
        assert _matches_any("all good", ("server busy", "overloaded")) is False

    def test_empty_patterns(self):
        assert _matches_any("anything", ()) is False

    def test_empty_detail(self):
        assert _matches_any("", ("busy",)) is False


class TestExtractErrorCode:
    def test_code_attr(self):
        exc = Exception()
        exc.code = "quota_exceeded"
        assert _extract_error_code(exc) == "quota_exceeded"

    def test_error_code_attr(self):
        exc = Exception()
        exc.error_code = "auth_failed"
        assert _extract_error_code(exc) == "auth_failed"

    def test_body_dict_nested(self):
        exc = Exception()
        exc.body = {"error": {"code": "rate_limited", "type": "too_many"}}
        assert _extract_error_code(exc) == "rate_limited"

    def test_body_dict_type_key(self):
        exc = Exception()
        exc.body = {"error": {"type": "auth_error"}}
        assert _extract_error_code(exc) == "auth_error"

    def test_no_code(self):
        exc = Exception()
        assert _extract_error_code(exc) is None

    def test_empty_code(self):
        exc = Exception()
        exc.code = ""
        assert _extract_error_code(exc) is None

    def test_body_not_dict(self):
        exc = Exception()
        exc.body = "string body"
        assert _extract_error_code(exc) is None


class TestExtractStatusCode:
    def test_status_code_attr(self):
        exc = Exception()
        exc.status_code = 503
        assert _extract_status_code(exc) == 503

    def test_status_attr(self):
        exc = Exception()
        exc.status = 429
        assert _extract_status_code(exc) == 429

    def test_response_attr(self):
        exc = Exception()
        exc.response = SimpleNamespace(status_code=500)
        assert _extract_status_code(exc) == 500

    def test_no_status(self):
        exc = Exception()
        assert _extract_status_code(exc) is None

    def test_non_int_status(self):
        exc = Exception()
        exc.status_code = "not_int"
        assert _extract_status_code(exc) is None


class TestExtractRetryAfterMs:
    def test_retry_after_ms_header(self):
        exc = Exception()
        exc.response = SimpleNamespace(headers={"retry-after-ms": "500"})
        assert _extract_retry_after_ms(exc) == 500

    def test_retry_after_seconds_header(self):
        exc = Exception()
        exc.response = SimpleNamespace(headers={"Retry-After": "2"})
        assert _extract_retry_after_ms(exc) == 2000

    def test_no_response(self):
        exc = Exception()
        assert _extract_retry_after_ms(exc) is None

    def test_no_headers(self):
        exc = Exception()
        exc.response = SimpleNamespace(headers=None)
        assert _extract_retry_after_ms(exc) is None

    def test_invalid_value(self):
        exc = Exception()
        exc.response = SimpleNamespace(headers={"retry-after-ms": "not_a_number"})
        result = _extract_retry_after_ms(exc)
        # Should try to parse as date or return None
        assert result is None or isinstance(result, int)

    def test_no_retry_after_header(self):
        exc = Exception()
        exc.response = SimpleNamespace(headers={"content-type": "text/plain"})
        assert _extract_retry_after_ms(exc) is None


class TestExtractErrorDetail:
    def test_str_repr(self):
        exc = ValueError("something broke")
        assert _extract_error_detail(exc) == "something broke"

    def test_empty_str_uses_message_attr(self):
        exc = Exception()
        exc.message = "fallback message"
        assert _extract_error_detail(exc) == "fallback message"

    def test_neither_str_nor_message(self):
        exc = ValueError()
        assert _extract_error_detail(exc) == "ValueError"


# ---------------------------------------------------------------------------
# _classify_error
# ---------------------------------------------------------------------------


class TestClassifyError:
    def test_quota_pattern(self):
        middleware = _build_middleware()
        exc = Exception("insufficient_quota for this account")
        retriable, reason = middleware._classify_error(exc)
        assert retriable is False
        assert reason == "quota"

    def test_auth_pattern(self):
        middleware = _build_middleware()
        exc = Exception("invalid api key")
        retriable, reason = middleware._classify_error(exc)
        assert retriable is False
        assert reason == "auth"

    def test_busy_pattern(self):
        middleware = _build_middleware()
        exc = Exception("server busy, try again")
        retriable, reason = middleware._classify_error(exc)
        assert retriable is True
        assert reason == "busy"

    def test_transient_by_status_code(self):
        middleware = _build_middleware()
        exc = Exception("error")
        exc.status_code = 503
        retriable, reason = middleware._classify_error(exc)
        assert retriable is True
        assert reason == "transient"

    def test_transient_by_class_name(self):
        middleware = _build_middleware()

        class APITimeoutError(Exception):
            pass

        exc = APITimeoutError("timeout")
        retriable, reason = middleware._classify_error(exc)
        assert retriable is True
        assert reason == "transient"

    def test_generic_error(self):
        middleware = _build_middleware()
        exc = Exception("something random")
        retriable, reason = middleware._classify_error(exc)
        assert retriable is False
        assert reason == "generic"

    def test_quota_by_error_code(self):
        middleware = _build_middleware()
        exc = Exception("error")
        exc.code = "billing"
        retriable, reason = middleware._classify_error(exc)
        assert retriable is False
        assert reason == "quota"

    def test_chinese_busy_pattern(self):
        middleware = _build_middleware()
        exc = Exception("服务繁忙")
        retriable, reason = middleware._classify_error(exc)
        assert retriable is True
        assert reason == "busy"

    def test_chinese_quota_pattern(self):
        middleware = _build_middleware()
        exc = Exception("额度不足")
        retriable, reason = middleware._classify_error(exc)
        assert retriable is False
        assert reason == "quota"

    def test_chinese_auth_pattern(self):
        middleware = _build_middleware()
        exc = Exception("未授权访问")
        retriable, reason = middleware._classify_error(exc)
        assert retriable is False
        assert reason == "auth"


# ---------------------------------------------------------------------------
# _build_retry_delay_ms
# ---------------------------------------------------------------------------


class TestBuildRetryDelayMs:
    def test_uses_retry_after_header(self):
        middleware = _build_middleware(retry_base_delay_ms=1000)
        exc = Exception("error")
        exc.response = SimpleNamespace(headers={"retry-after-ms": "300"})
        delay = middleware._build_retry_delay_ms(1, exc)
        assert delay == 300

    def test_exponential_backoff(self):
        middleware = _build_middleware(retry_base_delay_ms=1000, retry_cap_delay_ms=8000)
        exc = Exception("error")
        delay1 = middleware._build_retry_delay_ms(1, exc)
        delay2 = middleware._build_retry_delay_ms(2, exc)
        delay3 = middleware._build_retry_delay_ms(3, exc)
        assert delay1 == 1000
        assert delay2 == 2000
        assert delay3 == 4000

    def test_cap_delay(self):
        middleware = _build_middleware(retry_base_delay_ms=1000, retry_cap_delay_ms=3000)
        exc = Exception("error")
        delay = middleware._build_retry_delay_ms(10, exc)
        assert delay == 3000


# ---------------------------------------------------------------------------
# _build_retry_message
# ---------------------------------------------------------------------------


class TestBuildRetryMessage:
    def test_busy_reason(self):
        middleware = _build_middleware(retry_max_attempts=3)
        msg = middleware._build_retry_message(1, 2000, "busy")
        assert "provider is busy" in msg
        assert "1/3" in msg
        assert "2s" in msg

    def test_transient_reason(self):
        middleware = _build_middleware(retry_max_attempts=3)
        msg = middleware._build_retry_message(2, 1500, "transient")
        assert "provider request failed temporarily" in msg
        assert "2/3" in msg
        assert "2s" in msg


# ---------------------------------------------------------------------------
# _build_user_message
# ---------------------------------------------------------------------------


class TestBuildUserMessage:
    def test_quota_message(self):
        middleware = _build_middleware()
        msg = middleware._build_user_message(Exception("err"), "quota")
        assert "out of quota" in msg.lower() or "quota" in msg.lower()

    def test_auth_message(self):
        middleware = _build_middleware()
        msg = middleware._build_user_message(Exception("err"), "auth")
        assert "authentication" in msg.lower() or "credentials" in msg.lower()

    def test_busy_transient_message(self):
        middleware = _build_middleware()
        for reason in ("busy", "transient"):
            msg = middleware._build_user_message(Exception("err"), reason)
            assert "temporarily unavailable" in msg.lower()

    def test_generic_message(self):
        middleware = _build_middleware()
        msg = middleware._build_user_message(Exception("something broke"), "generic")
        assert "something broke" in msg


# ---------------------------------------------------------------------------
# _build_circuit_breaker_message
# ---------------------------------------------------------------------------


class TestBuildCircuitBreakerMessage:
    def test_contains_circuit_breaker_text(self):
        middleware = _build_middleware()
        msg = middleware._build_circuit_breaker_message()
        assert "circuit breaker" in msg.lower()
        assert "unavailable" in msg.lower()


# ---------------------------------------------------------------------------
# wrap_model_call sync — additional paths
# ---------------------------------------------------------------------------


class TestWrapModelCallSync:
    def test_sync_success(self):
        middleware = _build_middleware()

        def handler(req):
            return AIMessage(content="ok")

        result = middleware.wrap_model_call(SimpleNamespace(), handler)
        assert result.content == "ok"

    def test_sync_non_retriable_returns_user_message(self):
        middleware = _build_middleware(retry_max_attempts=3)

        def handler(req):
            raise Exception("generic failure")

        result = middleware.wrap_model_call(SimpleNamespace(), handler)
        assert isinstance(result, AIMessage)
        assert "generic failure" in result.content

    def test_sync_all_retries_exhausted(self):
        middleware = _build_middleware(retry_max_attempts=2, retry_base_delay_ms=0, retry_cap_delay_ms=0)
        attempts = 0

        def handler(req):
            nonlocal attempts
            attempts += 1
            raise Exception("server busy")

        result = middleware.wrap_model_call(SimpleNamespace(), handler)
        assert isinstance(result, AIMessage)
        assert attempts == 2

    def test_sync_quota_error_no_retry(self):
        middleware = _build_middleware(retry_max_attempts=5)

        def handler(req):
            raise Exception("insufficient_quota")

        result = middleware.wrap_model_call(SimpleNamespace(), handler)
        assert "out of quota" in result.content.lower()

    def test_sync_auth_error_no_retry(self):
        middleware = _build_middleware(retry_max_attempts=5)

        def handler(req):
            raise Exception("unauthorized access")

        result = middleware.wrap_model_call(SimpleNamespace(), handler)
        assert "authentication" in result.content.lower() or "credentials" in result.content.lower()


# ---------------------------------------------------------------------------
# awrap_model_call async — additional paths
# ---------------------------------------------------------------------------


class TestAwrapModelCallAsync:
    @pytest.mark.anyio
    async def test_async_success(self):
        middleware = _build_middleware()

        async def handler(req):
            return AIMessage(content="ok")

        result = await middleware.awrap_model_call(SimpleNamespace(), handler)
        assert result.content == "ok"

    @pytest.mark.anyio
    async def test_async_non_retriable_returns_user_message(self):
        middleware = _build_middleware(retry_max_attempts=3)

        async def handler(req):
            raise Exception("generic failure")

        result = await middleware.awrap_model_call(SimpleNamespace(), handler)
        assert isinstance(result, AIMessage)
        assert "generic failure" in result.content

    @pytest.mark.anyio
    async def test_async_all_retries_exhausted(self):
        middleware = _build_middleware(retry_max_attempts=2, retry_base_delay_ms=0, retry_cap_delay_ms=0)
        attempts = 0

        async def handler(req):
            nonlocal attempts
            attempts += 1
            raise Exception("server busy")

        result = await middleware.awrap_model_call(SimpleNamespace(), handler)
        assert isinstance(result, AIMessage)
        assert attempts == 2

    @pytest.mark.anyio
    async def test_async_quota_error_no_retry(self):
        middleware = _build_middleware(retry_max_attempts=5)

        async def handler(req):
            raise Exception("insufficient_quota")

        result = await middleware.awrap_model_call(SimpleNamespace(), handler)
        assert "out of quota" in result.content.lower()

    @pytest.mark.anyio
    async def test_async_busy_pattern_chinese(self):
        middleware = _build_middleware(retry_max_attempts=2, retry_base_delay_ms=0, retry_cap_delay_ms=0)
        attempts = 0

        async def handler(req):
            nonlocal attempts
            attempts += 1
            raise Exception("服务繁忙")

        result = await middleware.awrap_model_call(SimpleNamespace(), handler)
        assert isinstance(result, AIMessage)
        assert attempts == 2


# ---------------------------------------------------------------------------
# Circuit Breaker — additional edge cases
# ---------------------------------------------------------------------------


class TestCircuitBreakerEdgeCases:
    def test_check_circuit_closed_default(self):
        middleware = _build_middleware()
        assert middleware._check_circuit() is False
        assert middleware._circuit_state == "closed"

    def test_record_success_resets(self):
        middleware = _build_middleware()
        middleware._circuit_failure_count = 5
        middleware._record_success()
        assert middleware._circuit_failure_count == 0
        assert middleware._circuit_state == "closed"

    def test_record_failure_below_threshold(self):
        middleware = _build_middleware(circuit_failure_threshold=3)
        middleware._record_failure()
        assert middleware._circuit_failure_count == 1
        assert middleware._circuit_state == "closed"

    def test_record_failure_at_threshold(self):
        middleware = _build_middleware(circuit_failure_threshold=2)
        middleware._record_failure()
        middleware._record_failure()
        assert middleware._circuit_failure_count == 2
        assert middleware._circuit_state == "open"

    def test_half_open_probe_in_flight_blocks(self):
        middleware = _build_middleware()
        middleware._circuit_state = "half_open"
        middleware._circuit_probe_in_flight = True
        assert middleware._check_circuit() is True  # blocks

    def test_half_open_probe_not_in_flight_allows(self):
        middleware = _build_middleware()
        middleware._circuit_state = "half_open"
        middleware._circuit_probe_in_flight = False
        assert middleware._check_circuit() is False  # allows
        assert middleware._circuit_probe_in_flight is True

    def test_record_failure_from_half_open_reopens(self):
        middleware = _build_middleware(circuit_recovery_timeout_sec=10)
        middleware._circuit_state = "half_open"
        middleware._record_failure()
        assert middleware._circuit_state == "open"
        assert middleware._circuit_probe_in_flight is False
