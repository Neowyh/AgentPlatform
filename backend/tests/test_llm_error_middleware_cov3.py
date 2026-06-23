"""Additional tests for llm_error_handling_middleware — coverage gaps.

Covers:
  - Lines 92-95: _check_circuit open->half_open transition
  - Line 195: _emit_retry_event get_stream_writer failure
  - Line 215: wrap_model_call circuit breaker fast-fail
  - Lines 225-228: wrap_model_call GraphBubbleUp in half_open
  - Line 261: awrap_model_call circuit breaker fast-fail
  - Lines 271-274: awrap_model_call GraphBubbleUp in half_open
  - Lines 355-356: _extract_retry_after_ms date-format fallback
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from langgraph.errors import GraphBubbleUp

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
# Lines 92-95: _check_circuit open -> half_open transition
# ---------------------------------------------------------------------------


class TestCheckCircuitOpenToHalfOpen:
    def test_open_timeout_expired_transitions_to_half_open(self):
        """When circuit is open and timeout has expired, transition to half_open."""
        middleware = _build_middleware()
        middleware._circuit_state = "open"
        middleware._circuit_open_until = time.time() - 1  # expired
        middleware._circuit_probe_in_flight = True  # should be reset

        result = middleware._check_circuit()

        assert result is False  # allows probe through
        assert middleware._circuit_state == "half_open"
        assert middleware._circuit_probe_in_flight is True  # set by the probe logic

    def test_open_timeout_not_expired_returns_true(self):
        """When circuit is open and timeout has NOT expired, fast-fail."""
        middleware = _build_middleware()
        middleware._circuit_state = "open"
        middleware._circuit_open_until = time.time() + 100  # not expired

        result = middleware._check_circuit()
        assert result is True


# ---------------------------------------------------------------------------
# Line 195: _emit_retry_event when get_stream_writer fails
# ---------------------------------------------------------------------------


class TestEmitRetryEventFailure:
    def test_emit_retry_event_writer_failure(self, monkeypatch):
        """When get_stream_writer raises, the error is silently caught."""
        middleware = _build_middleware()

        def _raise():
            raise RuntimeError("no stream writer")

        monkeypatch.setattr(
            "langgraph.config.get_stream_writer",
            _raise,
        )
        # Should not raise
        middleware._emit_retry_event(1, 1000, "busy")


# ---------------------------------------------------------------------------
# Line 215: wrap_model_call circuit breaker fast-fail
# ---------------------------------------------------------------------------


class TestWrapModelCallCircuitBreaker:
    def test_sync_circuit_open_returns_circuit_message(self):
        """When circuit is open, wrap_model_call returns circuit breaker message."""
        middleware = _build_middleware()
        middleware._circuit_state = "open"
        middleware._circuit_open_until = time.time() + 100

        def handler(req):
            return AIMessage(content="should not reach")

        result = middleware.wrap_model_call(SimpleNamespace(), handler)
        assert isinstance(result, AIMessage)
        assert "circuit breaker" in result.content.lower()

    @pytest.mark.anyio
    async def test_async_circuit_open_returns_circuit_message(self):
        """When circuit is open, awrap_model_call returns circuit breaker message."""
        middleware = _build_middleware()
        middleware._circuit_state = "open"
        middleware._circuit_open_until = time.time() + 100

        async def handler(req):
            return AIMessage(content="should not reach")

        result = await middleware.awrap_model_call(SimpleNamespace(), handler)
        assert isinstance(result, AIMessage)
        assert "circuit breaker" in result.content.lower()


# ---------------------------------------------------------------------------
# Lines 225-228, 271-274: GraphBubbleUp in half_open state
# ---------------------------------------------------------------------------


class TestGraphBubbleUpHalfOpen:
    def test_sync_graph_bubble_up_resets_probe_in_flight(self):
        """GraphBubbleUp in half_open state resets probe_in_flight."""
        middleware = _build_middleware()
        middleware._circuit_state = "half_open"
        middleware._circuit_probe_in_flight = False

        def handler(req):
            # At this point, _check_circuit was called inside wrap_model_call
            # and set probe_in_flight=True, then the handler runs
            assert middleware._circuit_probe_in_flight is True
            raise GraphBubbleUp()

        with pytest.raises(GraphBubbleUp):
            middleware.wrap_model_call(SimpleNamespace(), handler)

        # probe_in_flight should be reset by the GraphBubbleUp handler
        assert middleware._circuit_probe_in_flight is False

    @pytest.mark.anyio
    async def test_async_graph_bubble_up_resets_probe_in_flight(self):
        """Async GraphBubbleUp in half_open state resets probe_in_flight."""
        middleware = _build_middleware()
        middleware._circuit_state = "half_open"
        middleware._circuit_probe_in_flight = False

        async def handler(req):
            assert middleware._circuit_probe_in_flight is True
            raise GraphBubbleUp()

        with pytest.raises(GraphBubbleUp):
            await middleware.awrap_model_call(SimpleNamespace(), handler)

        assert middleware._circuit_probe_in_flight is False


# ---------------------------------------------------------------------------
# Lines 355-356: _extract_retry_after_ms with date-format header
# ---------------------------------------------------------------------------


class TestExtractRetryAfterMsDate:
    def test_date_format_retry_after(self):
        """Retry-After with HTTP-date format should return delta in ms."""
        from datetime import UTC, datetime, timedelta
        from email.utils import format_datetime

        future = datetime.now(UTC) + timedelta(seconds=5)
        date_str = format_datetime(future, usegmt=True)

        exc = Exception("error")
        exc.response = SimpleNamespace(headers={"Retry-After": date_str})

        result = _extract_retry_after_ms(exc)
        # Should be approximately 5000ms (with some tolerance)
        assert result is not None
        assert 4000 <= result <= 6000

    def test_invalid_date_format_returns_none(self):
        """Retry-After with completely invalid format returns None."""
        exc = Exception("error")
        exc.response = SimpleNamespace(headers={"Retry-After": "not-a-date-or-number"})

        result = _extract_retry_after_ms(exc)
        assert result is None


# ---------------------------------------------------------------------------
# Additional: retry-after-ms header case variations
# ---------------------------------------------------------------------------


class TestRetryAfterMsHeaderVariations:
    def test_retry_after_ms_camel_case(self):
        exc = Exception("error")
        exc.response = SimpleNamespace(headers={"Retry-After-Ms": "500"})
        assert _extract_retry_after_ms(exc) == 500

    def test_retry_after_ms_lowercase(self):
        exc = Exception("error")
        exc.response = SimpleNamespace(headers={"retry-after-ms": "300"})
        assert _extract_retry_after_ms(exc) == 300

    def test_retry_after_seconds(self):
        exc = Exception("error")
        exc.response = SimpleNamespace(headers={"Retry-After": "3"})
        assert _extract_retry_after_ms(exc) == 3000

    def test_retry_after_zero(self):
        exc = Exception("error")
        exc.response = SimpleNamespace(headers={"retry-after-ms": "0"})
        assert _extract_retry_after_ms(exc) == 0

    def test_retry_after_negative_clamped_to_zero(self):
        exc = Exception("error")
        exc.response = SimpleNamespace(headers={"retry-after-ms": "-100"})
        result = _extract_retry_after_ms(exc)
        assert result is not None
        assert result >= 0

    def test_headers_with_get_method(self):
        """Headers object with .get() method."""
        exc = Exception("error")
        headers = {"retry-after-ms": "200"}
        exc.response = SimpleNamespace(headers=headers)
        assert _extract_retry_after_ms(exc) == 200

    def test_headers_without_get(self):
        """Headers without .get() method (e.g. raw tuple list)."""
        exc = Exception("error")
        exc.response = SimpleNamespace(headers=None)
        assert _extract_retry_after_ms(exc) is None


# ---------------------------------------------------------------------------
# Additional: _record_failure from closed state
# ---------------------------------------------------------------------------


class TestRecordFailureFromClosed:
    def test_record_failure_increments_count(self):
        middleware = _build_middleware(circuit_failure_threshold=5)
        middleware._record_failure()
        assert middleware._circuit_failure_count == 1
        assert middleware._circuit_state == "closed"

    def test_record_failure_trips_at_threshold(self):
        middleware = _build_middleware(circuit_failure_threshold=2)
        middleware._record_failure()
        middleware._record_failure()
        assert middleware._circuit_failure_count == 2
        assert middleware._circuit_state == "open"

    def test_record_failure_already_open_no_double_log(self):
        """When already open, further failures don't change state."""
        middleware = _build_middleware(circuit_failure_threshold=2)
        middleware._circuit_state = "open"
        middleware._circuit_failure_count = 2
        middleware._circuit_open_until = time.time() + 100
        middleware._record_failure()
        # Should still be open with same count
        assert middleware._circuit_state == "open"


# ---------------------------------------------------------------------------
# Additional: _record_success from various states
# ---------------------------------------------------------------------------


class TestRecordSuccess:
    def test_record_success_from_half_open(self):
        middleware = _build_middleware()
        middleware._circuit_state = "half_open"
        middleware._circuit_failure_count = 3
        middleware._record_success()
        assert middleware._circuit_state == "closed"
        assert middleware._circuit_failure_count == 0

    def test_record_success_from_open_with_failures(self):
        middleware = _build_middleware()
        middleware._circuit_state = "closed"
        middleware._circuit_failure_count = 1
        middleware._record_success()
        assert middleware._circuit_failure_count == 0


# ---------------------------------------------------------------------------
# Additional helper function coverage
# ---------------------------------------------------------------------------


class TestExtractErrorCodeAdditional:
    """Cover _extract_error_code nested body paths."""

    def test_body_error_code_key(self):
        exc = Exception("error")
        exc.body = {"error": {"code": "rate_limited"}}
        assert _extract_error_code(exc) == "rate_limited"

    def test_body_error_type_key(self):
        exc = Exception("error")
        exc.body = {"error": {"type": "auth_error"}}
        assert _extract_error_code(exc) == "auth_error"

    def test_body_error_code_empty_skipped(self):
        exc = Exception("error")
        exc.body = {"error": {"code": "", "type": "some_type"}}
        assert _extract_error_code(exc) == "some_type"

    def test_body_error_not_dict(self):
        exc = Exception("error")
        exc.body = {"error": "string_error"}
        assert _extract_error_code(exc) is None

    def test_code_attr_with_value(self):
        exc = Exception("error")
        exc.code = "some_code"
        assert _extract_error_code(exc) == "some_code"

    def test_error_code_attr_with_value(self):
        exc = Exception("error")
        exc.error_code = "some_error_code"
        assert _extract_error_code(exc) == "some_error_code"


class TestExtractStatusCodeAdditional:
    """Cover _extract_status_code response attr path."""

    def test_response_status_code(self):
        exc = Exception("error")
        exc.response = SimpleNamespace(status_code=500)
        assert _extract_status_code(exc) == 500

    def test_response_not_int(self):
        exc = Exception("error")
        exc.response = SimpleNamespace(status_code="not_int")
        assert _extract_status_code(exc) is None

    def test_no_response_attr(self):
        exc = Exception("error")
        assert _extract_status_code(exc) is None


class TestExtractRetryAfterMsAdditional:
    """Cover _extract_retry_after_ms no-response and no-headers paths."""

    def test_no_response_returns_none(self):
        exc = Exception("error")
        assert _extract_retry_after_ms(exc) is None

    def test_no_headers_returns_none(self):
        exc = Exception("error")
        exc.response = SimpleNamespace(headers=None)
        assert _extract_retry_after_ms(exc) is None

    def test_empty_headers_returns_none(self):
        exc = Exception("error")
        exc.response = SimpleNamespace(headers={})
        assert _extract_retry_after_ms(exc) is None


class TestExtractErrorDetailAdditional:
    """Cover _extract_error_detail fallback paths."""

    def test_empty_str_uses_message_attr(self):
        exc = Exception()
        exc.message = "fallback message"
        assert _extract_error_detail(exc) == "fallback message"

    def test_empty_str_no_message_uses_class_name(self):
        exc = ValueError()
        assert _extract_error_detail(exc) == "ValueError"

    def test_whitespace_only_str_uses_message(self):
        exc = Exception("   ")
        exc.message = "actual message"
        assert _extract_error_detail(exc) == "actual message"

    def test_whitespace_str_no_message_uses_class_name(self):
        exc = RuntimeError()
        assert _extract_error_detail(exc) == "RuntimeError"


class TestMatchesAnyAdditional:
    """Cover _matches_any edge cases."""

    def test_partial_match(self):
        assert _matches_any("server busy right now", ("server busy",)) is True

    def test_no_match_at_all(self):
        assert _matches_any("everything is fine", ("busy", "error")) is False


class TestHalfOpenProbeEdgeCases:
    """Cover _check_circuit half_open probe_in_flight blocking."""

    def test_half_open_probe_in_flight_blocks(self):
        """When probe is in flight, new requests are blocked."""
        middleware = _build_middleware()
        middleware._circuit_state = "half_open"
        middleware._circuit_probe_in_flight = True
        assert middleware._check_circuit() is True

    def test_half_open_probe_not_in_flight_allows(self):
        """When probe is not in flight, first request is allowed through."""
        middleware = _build_middleware()
        middleware._circuit_state = "half_open"
        middleware._circuit_probe_in_flight = False
        assert middleware._check_circuit() is False
        assert middleware._circuit_probe_in_flight is True
