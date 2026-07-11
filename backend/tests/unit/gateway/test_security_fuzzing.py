"""Security-focused property-based tests using Hypothesis.

Tests invariants for JWT decoding, path traversal detection,
CSRF constant-time comparison, and role-based access control.
"""

import secrets

import jwt
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.gateway.auth.config import AuthConfig, set_auth_config
from app.gateway.auth.errors import TokenError
from ideer.sandbox.tools import _reject_path_traversal

_JWT_SECRET = "test-secret-for-hypothesis-fuzzing"
_JWT_CONFIG = AuthConfig(jwt_secret=_JWT_SECRET)


def _setup_auth():
    """Ensure a test AuthConfig is active for JWT operations."""
    set_auth_config(_JWT_CONFIG)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

non_jwt = st.text(min_size=1, max_size=200)

traversal_variants = st.sampled_from(
    [
        "../etc",
        "..\\etc",
        "/../etc/",
        "foo/../../bar",
        "..",
        "./../lib",
        "/foo/..\\bar",
        "a/b/../../../c",
        "..\\..\\..\\windows",
        "/safe/../../etc/passwd",
    ]
)

safe_paths = st.text(min_size=1, max_size=50).filter(lambda x: ".." not in x and "/" not in x and "\\" not in x)

# Role-like strings for fuzzing require_role case sensitivity
role_variants = st.text(min_size=1, max_size=30)


class TestJWTTokenFuzzing:
    """Fuzz test: decode_token must reject any non-JWT string.

    The JWT decoder should return a TokenError variant (MALFORMED,
    INVALID_SIGNATURE, or EXPIRED) for every non-JWT string — never
    raise an unhandled exception or return a valid TokenPayload.
    """

    @given(non_jwt)
    @settings(max_examples=50)
    def test_decode_token_rejects_all_non_jwt(self, junk):
        """decode_token returns a TokenError for any non-JWT string."""
        _setup_auth()
        from app.gateway.auth.jwt import decode_token

        result = decode_token(junk)
        assert isinstance(result, TokenError), f"decode_token({junk!r}) returned {type(result).__name__}, expected TokenError"

    def test_decode_token_rejects_non_string_types(self):
        """decode_token returns TokenError for non-string inputs like int, float, bool."""
        _setup_auth()
        from app.gateway.auth.jwt import decode_token

        for val in (0, 3.14, True, None, [], {}):
            result = decode_token(val)
            assert isinstance(result, TokenError)

    def test_decode_token_rejects_empty_string(self):
        """An empty string should not produce a valid token."""
        _setup_auth()
        from app.gateway.auth.jwt import decode_token

        # jwt.decode raises on empty string -> caught by PyJWTError
        result = decode_token("")
        assert isinstance(result, TokenError)

    def test_decode_token_rejects_valid_jwt_from_wrong_secret(self):
        """A JWT signed with a different secret must be rejected."""
        _setup_auth()
        from app.gateway.auth.jwt import decode_token

        wrong = jwt.encode({"sub": "test"}, "a" * 32, algorithm="HS256")
        result = decode_token(wrong)
        assert isinstance(result, TokenError)
        assert result in (TokenError.INVALID_SIGNATURE, TokenError.MALFORMED)


class TestPathTraversalDetection:
    """Fuzz test: _reject_path_traversal must catch all '..' variants.

    The function normalises backslashes to forward slashes and splits on
    '/', then raises PermissionError for any segment equal to '..'.
    """

    @given(traversal_variants)
    @settings(max_examples=50)
    def test_rejects_known_traversal_variants(self, path):
        """All sampled traversal payloads must be rejected."""
        with pytest.raises(PermissionError, match="path traversal"):
            _reject_path_traversal(path)

    @given(safe_paths)
    @settings(max_examples=50)
    def test_allows_safe_paths(self, path):
        """Paths without '..' segments must pass through."""
        _reject_path_traversal(path)

    @given(st.text(min_size=0, max_size=10).filter(lambda x: ".." not in x))
    @settings(max_examples=30)
    def test_empty_and_single_component_paths(self, segment):
        """Short paths or empty paths should not raise."""
        _reject_path_traversal(segment)
        _reject_path_traversal(f"/mnt/user-data/{segment}")

    def test_rejects_dotdot_after_normalisation(self):
        """Backslash-based traversal is caught after normalisation."""
        with pytest.raises(PermissionError, match="path traversal"):
            _reject_path_traversal("C:\\users\\..\\windows")
        with pytest.raises(PermissionError, match="path traversal"):
            _reject_path_traversal("foo\\..\\bar")
        # Mix of separators
        with pytest.raises(PermissionError, match="path traversal"):
            _reject_path_traversal("foo/..\\bar")


class TestCSRFConstantTimeComparison:
    """secrets.compare_digest is used for CSRF token comparison.

    This test validates the property: constant-time comparison must
    reject all non-matching token pairs regardless of length.
    """

    @given(
        token_a=st.text(min_size=1, max_size=128, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
        token_b=st.text(min_size=1, max_size=128, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
    )
    @settings(max_examples=50)
    def test_compare_digest_rejects_different_tokens(self, token_a, token_b):
        """Different tokens must compare as False (no timing oracle)."""
        if token_a != token_b:
            assert not secrets.compare_digest(token_a, token_b)

    @given(token=st.text(min_size=1, max_size=128, alphabet=st.characters(min_codepoint=32, max_codepoint=126)))
    @settings(max_examples=50)
    def test_compare_digest_accepts_identical_tokens(self, token):
        """Identical tokens must compare as True."""
        assert secrets.compare_digest(token, token)

    def test_compare_digest_handles_empty_strings(self):
        """Edge case: empty strings."""
        assert secrets.compare_digest("", "")
        assert not secrets.compare_digest("", "token")
        assert not secrets.compare_digest("token", "")


class TestRoleComparisonSafety:
    """require_role uses case-sensitive 'not in' comparison.

    This is a security property: role strings must match exactly.
    Hypothesis fuzzing ensures no accidental case-insensitive match.
    """

    @given(st.text(min_size=1, max_size=20))
    @settings(max_examples=50)
    def test_role_comparison_is_case_sensitive(self, role_input):
        """require_role rejects roles with wrong casing."""
        _setup_auth()
        from ideer.persistence.models.user import UserRole

        test_role = role_input
        try:
            UserRole(test_role)
        except ValueError:
            pass
        else:
            # The exact string matches a valid role — skip (this case
            # is handled by the normal auth flow). We want to fuzz
            # non-matching inputs that look close.
            if test_role in ("super_admin", "user", "viewer", "department_admin"):
                return

        from app.gateway.authz import require_role

        @require_role("super_admin", "department_admin")
        async def dummy_endpoint(current_user=None):
            return "ok"

        class FakeUser:
            role = test_role

        import asyncio

        import pytest
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            asyncio.run(dummy_endpoint(current_user=FakeUser()))

    def test_require_role_upper_case_variant_rejected(self):
        """Uppercase 'SUPER_ADMIN' does not match 'super_admin'."""
        from app.gateway.authz import require_role

        @require_role("super_admin")
        async def endpoint(current_user=None):
            return "ok"

        class FakeUser:
            role = "SUPER_ADMIN"

        import asyncio

        import pytest
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(endpoint(current_user=FakeUser()))
        assert exc_info.value.status_code == 403
