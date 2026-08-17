"""Contract for the global HTTPException response payload builder.

Structured dict details (visibility closure violations) must keep the
envelope while passing through as the ``detail`` field so the frontend can
render localized, actionable messages; every other detail keeps the legacy
envelope verbatim.
"""

from fastapi import HTTPException

from app.gateway.app import _http_exception_payload


def test_visibility_closure_violation_keeps_envelope_with_structured_detail():
    detail = {
        "code": "visibility_closure_violation",
        "message": 'Dependency violates visibility closure: agent "fault-zeroing" cannot be made public',
        "violations": [
            {
                "source": {"slug": "fault-zeroing", "display_name": "fault-zeroing", "type": "agent"},
                "target": {"slug": "fault-zeroing", "display_name": "fault-zeroing", "type": "skill", "visibility": "private"},
                "required_visibility": "public",
                "owned_by_actor": True,
            }
        ],
    }
    exc = HTTPException(status_code=409, detail=detail)

    payload = _http_exception_payload(exc)

    assert payload == {
        "success": False,
        "data": None,
        "error": {"code": "INTERNAL_ERROR", "message": detail["message"]},
        "detail": detail,
    }


def test_string_detail_keeps_legacy_envelope():
    exc = HTTPException(status_code=404, detail="Resource not found")

    payload = _http_exception_payload(exc)

    assert payload == {
        "success": False,
        "data": None,
        "error": {"code": "INTERNAL_ERROR", "message": "Resource not found"},
        "detail": "Resource not found",
    }


def test_non_whitelisted_dict_detail_keeps_legacy_envelope():
    detail = {"code": "invalid_credentials", "message": "Incorrect email or password"}
    exc = HTTPException(status_code=401, detail=detail)

    payload = _http_exception_payload(exc)

    assert payload == {
        "success": False,
        "data": None,
        "error": {"code": "INTERNAL_ERROR", "message": str(detail)},
        "detail": str(detail),
    }
