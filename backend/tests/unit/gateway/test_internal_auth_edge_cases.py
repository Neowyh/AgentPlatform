"""Tests for app.gateway.internal_auth covering lines 54-56."""

from __future__ import annotations


class TestGetInternalTokenRandomFallback:
    """Lines 54-56: when neither IDEER_INTERNAL_AUTH_TOKEN nor AUTH_JWT_SECRET
    is set, a random token is generated with a warning."""

    def test_random_fallback_when_no_env_vars(self, monkeypatch):
        """Verify the warning path generates a random token."""
        import app.gateway.internal_auth as mod

        # Clear any cached token
        mod._internal_token = None
        # Ensure both env vars are empty
        monkeypatch.delenv("IDEER_INTERNAL_AUTH_TOKEN", raising=False)
        monkeypatch.delenv("AUTH_JWT_SECRET", raising=False)

        token = mod._get_internal_token()
        assert isinstance(token, str)
        assert len(token) > 0
        # Should be cached
        assert mod._get_internal_token() is token
        # Cleanup
        mod._internal_token = None

    def test_derived_from_jwt_secret(self, monkeypatch):
        """Lines 43-47: derive token from AUTH_JWT_SECRET."""
        import app.gateway.internal_auth as mod

        mod._internal_token = None
        monkeypatch.delenv("IDEER_INTERNAL_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-123")

        token = mod._get_internal_token()
        assert isinstance(token, str)
        assert len(token) > 0
        # Should be deterministic
        mod._internal_token = None
        token2 = mod._get_internal_token()
        assert token == token2
        mod._internal_token = None

    def test_explicit_env_var(self, monkeypatch):
        """Lines 37-40: explicit IDEER_INTERNAL_AUTH_TOKEN env var."""
        import app.gateway.internal_auth as mod

        mod._internal_token = None
        monkeypatch.setenv("IDEER_INTERNAL_AUTH_TOKEN", "my-explicit-token")

        token = mod._get_internal_token()
        assert token == "my-explicit-token"
        mod._internal_token = None
