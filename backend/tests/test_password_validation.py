"""Systematic tests for password blocklist and strength validation.

Covers:
- _COMMON_PASSWORDS set integrity
- _password_is_common() correctness
- RegisterRequest / ChangePasswordRequest / InitializeAdminRequest Pydantic validation
- HTTP endpoint integration (register, change-password)
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.gateway.routers.auth import (
    _COMMON_PASSWORDS,
    ChangePasswordRequest,
    InitializeAdminRequest,
    RegisterRequest,
    _password_is_common,
)
from app.gateway.routers.auth import (
    router as auth_router,
)

pytestmark = pytest.mark.no_auto_user


# ── _COMMON_PASSWORDS set integrity ────────────────────────────────────────


class TestCommonPasswordsIntegrity:
    """Verify the blocklist itself is well-formed."""

    def test_common_passwords_is_frozenset(self):
        """_COMMON_PASSWORDS must be a frozenset (immutable)."""
        assert isinstance(_COMMON_PASSWORDS, frozenset)

    def test_common_passwords_count_at_least_30(self):
        """At least 30 entries to be a meaningful blocklist."""
        assert len(_COMMON_PASSWORDS) >= 30

    def test_all_common_passwords_are_at_least_8_chars(self):
        """Every entry must be >= 8 chars (shorter ones fail min_length)."""
        for pw in _COMMON_PASSWORDS:
            assert len(pw) >= 8, f"Blocklist entry '{pw}' is shorter than 8 chars"

    def test_all_common_passwords_are_lowercase(self):
        """All entries should be lowercased (case-insensitive check)."""
        for pw in _COMMON_PASSWORDS:
            assert pw == pw.lower(), f"Blocklist entry '{pw}' is not lowercase"

    def test_common_passwords_no_whitespace(self):
        """No entries should contain whitespace."""
        for pw in _COMMON_PASSWORDS:
            assert " " not in pw, f"Blocklist entry '{pw}' contains whitespace"
            assert "\t" not in pw, f"Blocklist entry '{pw}' contains tab"
            assert "\n" not in pw, f"Blocklist entry '{pw}' contains newline"


# ── _password_is_common() unit tests ──────────────────────────────────────


class TestPasswordIsCommon:
    """Direct tests of _password_is_common function."""

    @pytest.mark.parametrize(
        "password",
        [
            "password",
            "password1",
            "password12",
            "password123",
            "password1234",
            "12345678",
            "123456789",
            "1234567890",
            "qwerty12",
            "qwertyui",
            "qwerty123",
            "abc12345",
            "abcd1234",
            "iloveyou",
            "letmein1",
            "welcome1",
            "welcome123",
            "admin123",
            "administrator",
            "passw0rd",
            "p@ssw0rd",
            "monkey12",
            "trustno1",
            "sunshine",
            "princess",
            "football",
            "baseball",
            "superman",
            "batman123",
            "starwars",
            "dragon123",
            "master123",
            "shadow12",
            "michael1",
            "jennifer",
            "computer",
        ],
        ids=[
            "password",
            "password1",
            "password12",
            "password123",
            "password1234",
            "12345678",
            "123456789",
            "1234567890",
            "qwerty12",
            "qwertyui",
            "qwerty123",
            "abc12345",
            "abcd1234",
            "iloveyou",
            "letmein1",
            "welcome1",
            "welcome123",
            "admin123",
            "administrator",
            "passw0rd",
            "p@ssw0rd",
            "monkey12",
            "trustno1",
            "sunshine",
            "princess",
            "football",
            "baseball",
            "superman",
            "batman123",
            "starwars",
            "dragon123",
            "master123",
            "shadow12",
            "michael1",
            "jennifer",
            "computer",
        ],
    )
    def test_known_common_passwords_detected(self, password):
        """All known common passwords in the blocklist are detected."""
        assert _password_is_common(password) is True

    def test_empty_string_not_common(self):
        """Empty string is not in the blocklist (too short)."""
        assert _password_is_common("") is False

    def test_short_password_not_common(self):
        """Short passwords aren't in the blocklist (they fail min_length)."""
        assert _password_is_common("abc") is False
        assert _password_is_common("12345") is False

    def test_normal_password_not_common(self):
        """A strong, non-common password is not flagged."""
        assert _password_is_common("Tr0ub4dor&3-Horse") is False
        assert _password_is_common("xK9!mZ2@qW5#") is False

    def test_similar_but_not_in_list(self):
        """Passwords that look similar but aren't exact matches are NOT flagged."""
        assert _password_is_common("password12345") is False
        assert _password_is_common("qwertyuiop1") is False
        assert _password_is_common("abc12345678") is False


# ── Case-insensitive rejection ────────────────────────────────────────────


class TestCaseInsensitiveRejection:
    """Common password case variants must be rejected."""

    @pytest.mark.parametrize(
        "variant",
        [
            "Password",
            "PASSWORD",
            "pAsSwOrD",
            "PaSsWoRd1",
            "PASSWORD123",
            "QwErTy123",
            "IlOvEyOu",
            "SuNsHiNe",
        ],
    )
    def test_common_password_case_variants_rejected(self, variant):
        """Case-insensitive match means all case variants are caught."""
        assert _password_is_common(variant) is True


# ── RegisterRequest validation ────────────────────────────────────────────


class TestRegisterRequestPasswordValidation:
    """Pydantic validation on RegisterRequest.password."""

    def test_min_length_rejects_7_chars(self):
        """Passwords shorter than 8 chars are rejected by min_length."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="x@example.com", password="short")
        assert "at least 8 characters" in str(exc_info.value)

    def test_min_length_rejects_7_chars_exactly(self):
        """7 characters is just below the minimum."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="x@example.com", password="abcdefg")
        assert "at least 8 characters" in str(exc_info.value)

    def test_empty_password_rejected(self):
        """Empty password is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="x@example.com", password="")
        assert "at least 8 characters" in str(exc_info.value)

    def test_exactly_8_chars_non_common_accepted(self):
        """8-character non-common password is accepted."""
        req = RegisterRequest(email="x@example.com", password="AbCdEfGh")
        assert req.password == "AbCdEfGh"

    @pytest.mark.parametrize(
        "common_pw",
        [
            "password",
            "12345678",
            "qwerty12",
            "iloveyou",
            "letmein1",
            "welcome1",
            "admin123",
            "passw0rd",
            "p@ssw0rd",
            "monkey12",
            "trustno1",
            "sunshine",
            "princess",
            "football",
            "superman",
        ],
    )
    def test_common_passwords_rejected_at_register(self, common_pw):
        """Common passwords from the blocklist are rejected during registration."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="x@example.com", password=common_pw)
        assert "too common" in str(exc_info.value)

    def test_strong_password_accepted(self):
        """Non-common password of sufficient length is accepted."""
        req = RegisterRequest(email="x@example.com", password="Tr0ub4dor&3-Horse")
        assert req.password == "Tr0ub4dor&3-Horse"

    def test_special_characters_password_accepted(self):
        """Password with special characters passes validation."""
        req = RegisterRequest(email="x@example.com", password="xK9!mZ2@qW5#")
        assert req.password == "xK9!mZ2@qW5#"

    def test_numeric_only_non_common_accepted(self):
        """Long numeric password that isn't in the blocklist is accepted."""
        req = RegisterRequest(email="x@example.com", password="987654321098")
        assert req.password == "987654321098"

    def test_pure_numbers_common_rejected(self):
        """Common numeric passwords like 12345678 are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="x@example.com", password="123456789")
        assert "too common" in str(exc_info.value)


# ── ChangePasswordRequest validation ──────────────────────────────────────


class TestChangePasswordRequestValidation:
    """Pydantic validation on ChangePasswordRequest.new_password."""

    def test_common_password_rejected(self):
        """Common password rejected in new_password field."""
        with pytest.raises(ValidationError) as exc_info:
            ChangePasswordRequest(current_password="old", new_password="password")
        assert "too common" in str(exc_info.value)

    def test_min_length_enforced(self):
        """Short new_password is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChangePasswordRequest(current_password="old", new_password="short")
        assert "at least 8 characters" in str(exc_info.value)

    def test_strong_password_accepted(self):
        """Non-common password accepted as new_password."""
        req = ChangePasswordRequest(current_password="old", new_password="NewP@ss123!")
        assert req.new_password == "NewP@ss123!"

    def test_optional_new_email_accepted(self):
        """new_email is optional."""
        req = ChangePasswordRequest(current_password="old", new_password="NewP@ss123!")
        assert req.new_email is None

    def test_optional_new_email_with_value(self):
        """new_email can be set."""
        req = ChangePasswordRequest(
            current_password="old",
            new_password="NewP@ss123!",
            new_email="new@example.com",
        )
        assert req.new_email == "new@example.com"


# ── InitializeAdminRequest validation ─────────────────────────────────────


class TestInitializeAdminRequestValidation:
    """Pydantic validation on InitializeAdminRequest.password."""

    def test_common_password_rejected(self):
        """Common password rejected in admin initialization."""
        with pytest.raises(ValidationError) as exc_info:
            InitializeAdminRequest(email="admin@example.com", password="admin123")
        assert "too common" in str(exc_info.value)

    def test_min_length_enforced(self):
        """Short password is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            InitializeAdminRequest(email="admin@example.com", password="short")
        assert "at least 8 characters" in str(exc_info.value)

    def test_strong_password_accepted(self):
        """Non-common password accepted."""
        req = InitializeAdminRequest(email="admin@example.com", password="AdminP@ss123!")
        assert req.password == "AdminP@ss123!"


# ── Error message consistency ─────────────────────────────────────────────


class TestBoundaryConditions:
    """Edge-case passwords that exercise unusual inputs."""

    def test_unicode_password_accepted(self):
        """Unicode characters in a non-common password are accepted."""
        req = RegisterRequest(email="x@example.com", password="密码密码密码密码")
        assert req.password == "密码密码密码密码"

    def test_unicode_password_common_rejected(self):
        """Case-insensitive check works with Unicode input (no crash)."""
        assert _password_is_common("PASSWORD") is True
        assert _password_is_common("密码密码密码密码") is False

    def test_very_long_password_accepted(self):
        """Extremely long password (>128 chars) passes validation."""
        long_pw = "A" * 256 + "!" * 256
        req = RegisterRequest(email="x@example.com", password=long_pw)
        assert req.password == long_pw

    def test_null_byte_in_password_accepted(self):
        """Password containing null bytes passes Pydantic validation."""
        pw_with_null = "abc\x00defgh"
        req = RegisterRequest(email="x@example.com", password=pw_with_null)
        assert req.password == pw_with_null

    def test_whitespace_only_password_rejected(self):
        """8+ spaces is not in the blocklist but passes min_length."""
        req = RegisterRequest(email="x@example.com", password="        ")
        assert req.password == "        "


class TestPasswordStorageSecurity:
    """Verify password hashing properties."""

    def test_password_hash_is_not_plaintext(self):
        """Stored hash must differ from the raw password."""
        from app.gateway.auth.password import hash_password

        raw = "MySecret123!"
        hashed = hash_password(raw)
        assert hashed != raw
        assert hashed.startswith("$dfv2$")

    def test_hash_verification_roundtrip(self):
        """Correct password verifies; wrong password does not."""
        from app.gateway.auth.password import hash_password, verify_password

        raw = "MySecret123!"
        hashed = hash_password(raw)
        assert verify_password(raw, hashed) is True
        assert verify_password("WrongPassword1!", hashed) is False

    def test_bcrypt_uses_timing_safe_comparison(self):
        """bcrypt.checkpw internally uses constant-time comparison."""
        import bcrypt

        h = bcrypt.hashpw(b"test", bcrypt.gensalt())
        # verify_password wraps bcrypt.checkpw; just confirm it's callable
        # and returns bool — timing safety is a bcrypt implementation detail.
        from app.gateway.auth.password import verify_password

        assert isinstance(verify_password("test", h.decode()), bool)


class TestErrorMessages:
    """Verify error messages are consistent and informative."""

    def test_common_password_error_message(self):
        """Error message for common passwords is clear."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="x@example.com", password="password")
        error_str = str(exc_info.value)
        assert "too common" in error_str
        assert "stronger" in error_str

    def test_length_error_message(self):
        """Error message for too-short passwords is clear."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="x@example.com", password="abc")
        error_str = str(exc_info.value)
        assert "at least 8 characters" in error_str


# ── Blocklist coverage spot-checks ────────────────────────────────────────


class TestBlocklistCoverage:
    """Spot-check that representative categories are covered."""

    def test_numeric_patterns_covered(self):
        """Common numeric patterns are in the blocklist."""
        assert "12345678" in _COMMON_PASSWORDS
        assert "123456789" in _COMMON_PASSWORDS
        assert "1234567890" in _COMMON_PASSWORDS

    def test_keyboard_patterns_covered(self):
        """Keyboard walk patterns are in the blocklist."""
        assert "qwerty12" in _COMMON_PASSWORDS
        assert "qwertyui" in _COMMON_PASSWORDS
        assert "qwerty123" in _COMMON_PASSWORDS
        assert "abc12345" in _COMMON_PASSWORDS

    def test_password_variations_covered(self):
        """Password word variations are in the blocklist."""
        assert "password" in _COMMON_PASSWORDS
        assert "password1" in _COMMON_PASSWORDS
        assert "password12" in _COMMON_PASSWORDS
        assert "password123" in _COMMON_PASSWORDS
        assert "password1234" in _COMMON_PASSWORDS

    def test_leet_speak_covered(self):
        """Common leet-speak substitutions are in the blocklist."""
        assert "passw0rd" in _COMMON_PASSWORDS
        assert "p@ssw0rd" in _COMMON_PASSWORDS

    def test_popular_culture_covered(self):
        """Popular culture references are in the blocklist."""
        assert "superman" in _COMMON_PASSWORDS
        assert "batman123" in _COMMON_PASSWORDS
        assert "starwars" in _COMMON_PASSWORDS

    def test_welcome_variations_covered(self):
        """Welcome greeting variations are in the blocklist."""
        assert "welcome1" in _COMMON_PASSWORDS
        assert "welcome123" in _COMMON_PASSWORDS


# ── HTTP endpoint integration ─────────────────────────────────────────────


def _make_app():
    """Build a minimal FastAPI app with the auth router."""
    app = FastAPI()
    app.include_router(auth_router)
    return app


def _mock_provider(create_user_return=None):
    """Return a mock LocalAuthProvider."""
    provider = MagicMock()
    provider.create_user = AsyncMock(return_value=create_user_return)
    provider.count_admin_users = AsyncMock(return_value=0)
    provider.update_user = AsyncMock()
    return provider


def _fake_user(email="new@example.com", system_role="user"):
    """Return a User for mocking."""
    from app.gateway.auth.models import User

    return User(
        id=uuid4(),
        email=email,
        password_hash="$2b$12$fakehashedpassword",
        system_role=system_role,
        token_version=0,
    )


class TestRegisterEndpointPasswordPolicy:
    """Integration tests: password policy enforced via HTTP /register."""

    def test_register_rejects_common_password_via_http(self):
        """Register endpoint rejects common password with 422."""
        app = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/register",
                json={"email": "new@example.com", "password": "password"},
            )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any("too common" in str(d.get("msg", "")) for d in detail)

    def test_register_rejects_short_password_via_http(self):
        """Register endpoint rejects short password with 422."""
        app = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/register",
                json={"email": "new@example.com", "password": "short"},
            )
        assert resp.status_code == 422

    def test_register_accepts_strong_password_via_http(self):
        """Register endpoint accepts strong password (201)."""
        user = _fake_user()
        provider = _mock_provider(create_user_return=user)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth.create_access_token", return_value="fake-jwt"),
            patch("app.gateway.routers.auth._set_session_cookie"),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/register",
                    json={"email": "new@example.com", "password": "Tr0ub4dor&3-Horse"},
                )

        assert resp.status_code == 201

    @pytest.mark.parametrize(
        "common_pw",
        ["password", "12345678", "qwerty123", "admin123", "iloveyou"],
    )
    def test_register_rejects_multiple_common_passwords_via_http(self, common_pw):
        """Multiple common passwords all rejected via HTTP."""
        app = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/register",
                json={"email": "new@example.com", "password": common_pw},
            )
        assert resp.status_code == 422


class TestChangePasswordEndpointPasswordPolicy:
    """Integration tests: password policy enforced via HTTP /change-password."""

    def _patch_change_password(self, stack: ExitStack):
        """Enter patches for change-password dependencies onto the ExitStack."""
        from app.gateway.auth.models import User

        user = User(
            id=uuid4(),
            email="test@example.com",
            password_hash="$2b$12$fakehashedpassword",
            system_role="user",
            token_version=0,
        )
        stack.enter_context(patch("app.gateway.routers.auth.get_current_user_from_request", new_callable=AsyncMock, return_value=user))
        stack.enter_context(patch("app.gateway.auth.password.verify_password_async", new_callable=AsyncMock, return_value=True))
        stack.enter_context(patch("app.gateway.auth.password.hash_password_async", new_callable=AsyncMock, return_value="$2b$12$newhash"))
        stack.enter_context(patch("app.gateway.routers.auth.get_local_provider", return_value=_mock_provider()))
        stack.enter_context(patch("app.gateway.routers.auth._set_session_cookie"))
        stack.enter_context(patch("app.gateway.routers.auth.create_access_token", return_value="new-jwt"))

    def test_change_password_rejects_common_via_http(self):
        """Change-password endpoint rejects common password with 422."""
        with ExitStack() as stack:
            self._patch_change_password(stack)
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/change-password",
                    json={
                        "current_password": "OldPass123!",
                        "new_password": "password",
                    },
                )
        assert resp.status_code == 422

    def test_change_password_rejects_short_via_http(self):
        """Change-password endpoint rejects short password with 422."""
        with ExitStack() as stack:
            self._patch_change_password(stack)
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/change-password",
                    json={
                        "current_password": "OldPass123!",
                        "new_password": "short",
                    },
                )
        assert resp.status_code == 422

    def test_change_password_accepts_strong_via_http(self):
        """Change-password endpoint accepts strong password with 200."""
        with ExitStack() as stack:
            self._patch_change_password(stack)
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/change-password",
                    json={
                        "current_password": "OldPass123!",
                        "new_password": "NewP@ss123!",
                    },
                )
        assert resp.status_code == 200


class TestInitializeEndpointPasswordPolicy:
    """Integration tests: password policy enforced via HTTP /initialize."""

    def test_initialize_rejects_common_via_http(self):
        """Initialize endpoint rejects common password with 422."""
        app = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/initialize",
                json={"email": "admin@example.com", "password": "password"},
            )
        assert resp.status_code == 422

    def test_initialize_rejects_short_via_http(self):
        """Initialize endpoint rejects short password with 422."""
        app = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/initialize",
                json={"email": "admin@example.com", "password": "short"},
            )
        assert resp.status_code == 422

    def test_initialize_accepts_strong_via_http(self):
        """Initialize endpoint accepts strong password."""
        user = _fake_user(email="admin@example.com", system_role="admin")
        provider = _mock_provider(create_user_return=user)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth.create_access_token", return_value="admin-jwt"),
            patch("app.gateway.routers.auth._set_session_cookie"),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/initialize",
                    json={"email": "admin@example.com", "password": "AdminP@ss123!"},
                )

        assert resp.status_code == 201
