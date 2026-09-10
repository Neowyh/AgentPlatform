"""Tests for Gateway internal auth token handling."""

from __future__ import annotations

import importlib


def test_internal_auth_uses_shared_env_token(monkeypatch):
    import app.gateway.internal_auth as internal_auth

    monkeypatch.setenv("IDEER_INTERNAL_AUTH_TOKEN", "shared-token")
    reloaded = importlib.reload(internal_auth)
    try:
        headers = reloaded.create_internal_auth_headers()

        assert headers[reloaded.INTERNAL_AUTH_HEADER_NAME] == "shared-token"
        assert reloaded.is_valid_internal_auth_token("shared-token") is True
        assert reloaded.is_valid_internal_auth_token("other-token") is False
    finally:
        monkeypatch.delenv("IDEER_INTERNAL_AUTH_TOKEN", raising=False)
        importlib.reload(reloaded)


def test_internal_auth_generates_process_local_fallback(monkeypatch):
    import app.gateway.internal_auth as internal_auth

    monkeypatch.delenv("IDEER_INTERNAL_AUTH_TOKEN", raising=False)
    reloaded = importlib.reload(internal_auth)
    try:
        token = reloaded.create_internal_auth_headers()[reloaded.INTERNAL_AUTH_HEADER_NAME]

        assert token
        assert reloaded.is_valid_internal_auth_token(token) is True
    finally:
        importlib.reload(reloaded)


def test_internal_auth_rejects_non_string_header_values(monkeypatch):
    """Header lookups must never raise on malformed values.

    ``_is_internal_caller`` reads ``request.headers.get(...)``; alternative ASGI
    stacks and test doubles can return non-string objects. Token validation is a
    boolean gate, so any non-string value is simply not a valid token.
    """
    import app.gateway.internal_auth as internal_auth

    monkeypatch.setenv("IDEER_INTERNAL_AUTH_TOKEN", "shared-token")
    reloaded = importlib.reload(internal_auth)
    try:
        assert reloaded.is_valid_internal_auth_token(object()) is False
        assert reloaded.is_valid_internal_auth_token(None) is False
        assert reloaded.is_valid_internal_auth_token("") is False
        assert reloaded.is_valid_internal_auth_token(b"shared-token") is False
    finally:
        monkeypatch.delenv("IDEER_INTERNAL_AUTH_TOKEN", raising=False)
        importlib.reload(reloaded)
