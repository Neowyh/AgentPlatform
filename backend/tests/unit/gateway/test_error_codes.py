"""Unit tests for app.gateway.error_codes module.

Covers:
- Every error code → HTTP status code mapping correctness
- ApiException construction: code, message, status_code, detail fields
- ApiException as HTTPException subclass behaviour
- Error code registry completeness
- Unknown/invalid error code handling
- Custom message override and empty-message fallback
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.gateway.error_codes import ERROR_CODES, ApiException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_CODE_NAMES = [
    "PERMISSION_DENIED",
    "RESOURCE_NOT_FOUND",
    "RESOURCE_CONFLICT",
    "VERSION_CONFLICT",
    "ADMIN_LIMIT_EXCEEDED",
    "INVALID_VISIBILITY",
    "PENDING_APPLICATION_EXISTS",
    "APPROVER_NOT_FOUND",
    "SELF_REVIEW_FORBIDDEN",
    "USER_DISABLED",
    "FILE_FORMAT_INVALID",
    "TRANSFER_REQUIRED",
    "INVALID_REQUEST_BODY",
    "INTERNAL_ERROR",
]


# ---------------------------------------------------------------------------
# 1. ERROR_CODES registry integrity
# ---------------------------------------------------------------------------


class TestErrorCodesRegistry:
    """Verify the ERROR_CODES dict is well-formed."""

    def test_registry_is_non_empty_dict(self):
        assert isinstance(ERROR_CODES, dict)
        assert len(ERROR_CODES) > 0

    @pytest.mark.parametrize("code", ALL_CODE_NAMES)
    def test_all_expected_codes_present(self, code: str):
        assert code in ERROR_CODES, f"Missing error code: {code}"

    def test_no_unexpected_keys(self):
        assert set(ERROR_CODES.keys()) == set(ALL_CODE_NAMES)

    @pytest.mark.parametrize("code", ALL_CODE_NAMES)
    def test_entry_has_status_code_and_message(self, code: str):
        entry = ERROR_CODES[code]
        assert "status_code" in entry, f"{code} missing status_code"
        assert "message" in entry, f"{code} missing message"

    @pytest.mark.parametrize("code", ALL_CODE_NAMES)
    def test_status_code_is_int(self, code: str):
        assert isinstance(ERROR_CODES[code]["status_code"], int)

    @pytest.mark.parametrize("code", ALL_CODE_NAMES)
    def test_message_is_non_empty_string(self, code: str):
        msg = ERROR_CODES[code]["message"]
        assert isinstance(msg, str)
        assert len(msg) > 0


# ---------------------------------------------------------------------------
# 2. Error code → HTTP status code mapping
# ---------------------------------------------------------------------------


class TestStatusCodeMapping:
    """Each error code must map to the correct HTTP status code."""

    @pytest.mark.parametrize(
        "code,expected_status",
        [
            ("PERMISSION_DENIED", 403),
            ("RESOURCE_NOT_FOUND", 404),
            ("RESOURCE_CONFLICT", 409),
            ("VERSION_CONFLICT", 409),
            ("ADMIN_LIMIT_EXCEEDED", 400),
            ("INVALID_VISIBILITY", 400),
            ("PENDING_APPLICATION_EXISTS", 409),
            ("APPROVER_NOT_FOUND", 400),
            ("SELF_REVIEW_FORBIDDEN", 403),
            ("USER_DISABLED", 403),
            ("FILE_FORMAT_INVALID", 400),
            ("TRANSFER_REQUIRED", 400),
            ("INVALID_REQUEST_BODY", 400),
            ("INTERNAL_ERROR", 500),
        ],
        ids=ALL_CODE_NAMES,
    )
    def test_status_code_mapping(self, code: str, expected_status: int):
        assert ERROR_CODES[code]["status_code"] == expected_status


# ---------------------------------------------------------------------------
# 3. ApiException — construction
# ---------------------------------------------------------------------------


class TestApiExceptionConstruction:
    """Test ApiException constructor with various inputs."""

    @pytest.mark.parametrize("code", ALL_CODE_NAMES)
    def test_default_message_from_registry(self, code: str):
        exc = ApiException(code, "custom msg")
        assert exc.code == code
        assert exc.message == "custom msg"

    @pytest.mark.parametrize("code", ALL_CODE_NAMES)
    def test_default_message_fallback_when_empty(self, code: str):
        exc = ApiException(code, "")
        assert exc.message == ERROR_CODES[code]["message"]

    @pytest.mark.parametrize("code", ALL_CODE_NAMES)
    def test_default_message_fallback_when_none(self, code: str):
        exc = ApiException(code, None)  # type: ignore[arg-type]
        assert exc.message == ERROR_CODES[code]["message"]

    @pytest.mark.parametrize("code", ALL_CODE_NAMES)
    def test_status_code_from_registry(self, code: str):
        exc = ApiException(code, "msg")
        assert exc.status_code == ERROR_CODES[code]["status_code"]

    @pytest.mark.parametrize("code", ALL_CODE_NAMES)
    def test_status_code_override(self, code: str):
        exc = ApiException(code, "msg", status_code=418)
        assert exc.status_code == 418

    @pytest.mark.parametrize("code", ALL_CODE_NAMES)
    def test_detail_matches_message(self, code: str):
        exc = ApiException(code, "hello")
        assert exc.detail == "hello"


# ---------------------------------------------------------------------------
# 4. ApiException — subclass behaviour
# ---------------------------------------------------------------------------


class TestApiExceptionSubclassBehaviour:
    """ApiException must behave as a proper HTTPException subclass."""

    def test_is_http_exception(self):
        exc = ApiException("PERMISSION_DENIED", "msg")
        assert isinstance(exc, HTTPException)

    def test_can_be_caught_as_http_exception(self):
        with pytest.raises(HTTPException):
            raise ApiException("INTERNAL_ERROR", "boom")

    def test_repr_contains_status_and_detail(self):
        exc = ApiException("RESOURCE_NOT_FOUND", "not here")
        r = repr(exc)
        assert "404" in r
        assert "not here" in r

    def test_str_contains_detail(self):
        exc = ApiException("USER_DISABLED", "disabled")
        assert "disabled" in str(exc)

    def test_attributes_accessible(self):
        exc = ApiException("FILE_FORMAT_INVALID", "bad format")
        assert exc.code == "FILE_FORMAT_INVALID"
        assert exc.message == "bad format"
        assert exc.status_code == 400
        assert exc.detail == "bad format"


# ---------------------------------------------------------------------------
# 5. Unknown / invalid error code
# ---------------------------------------------------------------------------


class TestUnknownErrorCode:
    """Unknown error codes should raise ValueError."""

    def test_completely_unknown_code(self):
        with pytest.raises(ValueError, match="Unknown error code"):
            ApiException("DOES_NOT_EXIST", "msg")

    def test_empty_string_code(self):
        with pytest.raises(ValueError, match="Unknown error code"):
            ApiException("", "msg")

    def test_similar_but_wrong_code(self):
        with pytest.raises(ValueError, match="Unknown error code"):
            ApiException("PERMISSION_DENIED_X", "msg")

    def test_case_sensitive(self):
        with pytest.raises(ValueError, match="Unknown error code"):
            ApiException("permission_denied", "msg")


# ---------------------------------------------------------------------------
# 6. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Boundary conditions and unusual inputs."""

    def test_custom_message_preserved_over_default(self):
        exc = ApiException("INTERNAL_ERROR", "自定义错误信息")
        assert exc.message == "自定义错误信息"
        assert exc.detail == "自定义错误信息"

    def test_unicode_message(self):
        exc = ApiException("RESOURCE_NOT_FOUND", "资源没有找到，请检查")
        assert exc.message == "资源没有找到，请检查"

    def test_long_message(self):
        long_msg = "x" * 10000
        exc = ApiException("INTERNAL_ERROR", long_msg)
        assert exc.message == long_msg

    def test_explicit_none_status_code_falls_back_to_registry(self):
        exc = ApiException("INTERNAL_ERROR", "msg", status_code=None)
        assert exc.status_code == 500

    def test_status_code_zero_falls_back_to_registry(self):
        # status_code=0 is falsy in Python, so `0 or entry["status_code"]`
        # evaluates to the registry default. This documents actual behaviour.
        exc = ApiException("INTERNAL_ERROR", "msg", status_code=0)
        assert exc.status_code == 500

    def test_negative_status_code_override(self):
        exc = ApiException("INTERNAL_ERROR", "msg", status_code=-1)
        assert exc.status_code == -1

    def test_high_status_code_override(self):
        exc = ApiException("INTERNAL_ERROR", "msg", status_code=999)
        assert exc.status_code == 999


# ---------------------------------------------------------------------------
# 7. Multiple exceptions coexistence
# ---------------------------------------------------------------------------


class TestMultipleExceptions:
    """Ensure multiple ApiException instances don't share state."""

    def test_distinct_instances(self):
        a = ApiException("PERMISSION_DENIED", "a")
        b = ApiException("RESOURCE_NOT_FOUND", "b")
        assert a.code != b.code
        assert a.message != b.message
        assert a.status_code != b.status_code

    def test_same_code_distinct_messages(self):
        a = ApiException("INTERNAL_ERROR", "first")
        b = ApiException("INTERNAL_ERROR", "second")
        assert a.message == "first"
        assert b.message == "second"
