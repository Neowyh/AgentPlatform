import pytest
from fastapi import HTTPException

from app.gateway.services import validate_evidence_selection


def test_document_mode_is_backward_compatible():
    assert validate_evidence_selection(None, None) == ("document", None)
    assert validate_evidence_selection("document", None) == ("document", None)


@pytest.mark.parametrize("mode", ["code", "hybrid"])
def test_code_modes_require_a_package(mode):
    with pytest.raises(HTTPException, match="requires"):
        validate_evidence_selection(mode, None)


def test_document_mode_rejects_code_package():
    with pytest.raises(HTTPException, match="cannot include"):
        validate_evidence_selection("document", "package-1")


def test_invalid_mode_fails_closed():
    with pytest.raises(HTTPException, match="evidence_mode"):
        validate_evidence_selection("guess", None)


def test_code_mode_preserves_package_identity():
    assert validate_evidence_selection("code", "package-1") == ("code", "package-1")
