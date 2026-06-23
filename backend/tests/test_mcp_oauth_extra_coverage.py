"""Extra coverage tests for mcp/oauth.py missed lines.

Targets: 50, 60, 81, 83, 87, 90-99, 108, 115-116, 126, 131, 144
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideer.config.extensions_config import McpOAuthConfig
from ideer.mcp.oauth import (
    OAuthTokenManager,
    _OAuthToken,
    build_oauth_tool_interceptor,
    get_initial_oauth_headers,
)


def _make_oauth_config(**overrides):
    defaults = {
        "enabled": True,
        "token_url": "https://auth.example.com/token",
        "grant_type": "client_credentials",
        "client_id": "cid",
        "client_secret": "csecret",
    }
    defaults.update(overrides)
    return McpOAuthConfig(**defaults)


# --- Line 50: has_oauth_servers / oauth_server_names ---


def test_has_oauth_servers_and_names():
    """Lines 41-45: has_oauth_servers and oauth_server_names work correctly."""
    config = {"s1": _make_oauth_config(), "s2": _make_oauth_config()}
    manager = OAuthTokenManager(config)
    assert manager.has_oauth_servers() is True
    assert set(manager.oauth_server_names()) == {"s1", "s2"}


def test_has_oauth_servers_empty():
    """Returns False when no OAuth servers configured."""
    manager = OAuthTokenManager({})
    assert manager.has_oauth_servers() is False
    assert manager.oauth_server_names() == []


# --- Line 60: get_authorization_header lock path ---


def test_get_authorization_header_refreshes_under_lock():
    """Line 60: Acquires lock and fetches fresh token when cached one is expiring."""
    from datetime import UTC, datetime, timedelta

    oauth_config = _make_oauth_config(refresh_skew_seconds=300)
    manager = OAuthTokenManager({"s1": oauth_config})

    # Set an expiring token
    manager._tokens["s1"] = _OAuthToken(
        access_token="old-token",
        token_type="Bearer",
        expires_at=datetime.now(UTC) + timedelta(seconds=10),  # within skew
    )

    fresh_token = _OAuthToken(
        access_token="new-token",
        token_type="Bearer",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    async def run():
        with patch.object(manager, "_fetch_token", new_callable=AsyncMock, return_value=fresh_token):
            header = await manager.get_authorization_header("s1")
        return header

    result = asyncio.run(run())
    assert result == "Bearer new-token"


# --- Line 81, 83: _fetch_token with scope and audience ---


def test_fetch_token_includes_scope_and_audience():
    """Lines 81-83: scope and audience are added to token request data."""
    post_calls = []

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": "tok", "token_type": "Bearer", "expires_in": 3600}

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, data):
            post_calls.append(data)
            return MockResponse()

    with patch("httpx.AsyncClient", return_value=MockClient()):
        manager = OAuthTokenManager({})
        oauth = _make_oauth_config(scope="read write", audience="https://api.example.com")

        async def run():
            return await manager._fetch_token(oauth)

        asyncio.run(run())

    assert post_calls[0]["scope"] == "read write"
    assert post_calls[0]["audience"] == "https://api.example.com"


# --- Line 87: client_credentials without client_id/secret ---


def test_fetch_token_client_credentials_requires_credentials():
    """Line 87: Raises ValueError when client_credentials lacks credentials."""
    manager = OAuthTokenManager({})
    oauth = _make_oauth_config(client_id="", client_secret="")

    async def run():
        with pytest.raises(ValueError, match="client_id and client_secret"):
            await manager._fetch_token(oauth)

    asyncio.run(run())


# --- Lines 90-99: refresh_token grant type ---


def test_fetch_token_refresh_token_grant():
    """Lines 90-99: refresh_token grant sends refresh_token in request."""
    post_calls = []

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": "new-tok", "token_type": "Bearer", "expires_in": 3600}

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, data):
            post_calls.append(data)
            return MockResponse()

    with patch("httpx.AsyncClient", return_value=MockClient()):
        manager = OAuthTokenManager({})
        oauth = _make_oauth_config(
            grant_type="refresh_token",
            refresh_token="rt-123",
            client_id="cid",
            client_secret="csecret",
        )

        async def run():
            return await manager._fetch_token(oauth)

        asyncio.run(run())

    assert post_calls[0]["grant_type"] == "refresh_token"
    assert post_calls[0]["refresh_token"] == "rt-123"
    assert post_calls[0]["client_id"] == "cid"
    assert post_calls[0]["client_secret"] == "csecret"


def test_fetch_token_refresh_token_requires_token():
    """Line 92: Raises ValueError when refresh_token grant lacks refresh_token."""
    manager = OAuthTokenManager({})
    oauth = _make_oauth_config(grant_type="refresh_token", refresh_token="")

    async def run():
        with pytest.raises(ValueError, match="refresh_token"):
            await manager._fetch_token(oauth)

    asyncio.run(run())


def test_fetch_token_unsupported_grant_type():
    """Line 99: Raises ValueError for unsupported grant type."""
    manager = OAuthTokenManager({})
    # Create a mock config that bypasses pydantic validation
    oauth = MagicMock()
    oauth.grant_type = "authorization_code"
    oauth.extra_token_params = {}
    oauth.scope = None
    oauth.audience = None
    oauth.client_id = ""
    oauth.client_secret = ""
    oauth.refresh_token = ""

    async def run():
        with pytest.raises(ValueError, match="Unsupported OAuth grant type"):
            await manager._fetch_token(oauth)

    asyncio.run(run())


# --- Line 108: missing token field ---


def test_fetch_token_raises_when_token_missing():
    """Line 108: Raises ValueError when token response lacks token field."""

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"token_type": "Bearer", "expires_in": 3600}  # no access_token

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, data):
            return MockResponse()

    with patch("httpx.AsyncClient", return_value=MockClient()):
        manager = OAuthTokenManager({})
        oauth = _make_oauth_config()

        async def run():
            with pytest.raises(ValueError, match="missing"):
                await manager._fetch_token(oauth)

        asyncio.run(run())


# --- Lines 115-116: expires_in parse fallback ---


def test_fetch_token_handles_invalid_expires_in():
    """Lines 115-116: Falls back to 3600 when expires_in is not parseable."""

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": "tok", "token_type": "Bearer", "expires_in": "not_a_number"}

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, data):
            return MockResponse()

    with patch("httpx.AsyncClient", return_value=MockClient()):
        manager = OAuthTokenManager({})
        oauth = _make_oauth_config()

        async def run():
            token = await manager._fetch_token(oauth)
            return token

        result = asyncio.run(run())
    assert result.access_token == "tok"


# --- Line 126: build_oauth_tool_interceptor with no servers ---


def test_build_oauth_tool_interceptor_returns_none_when_no_servers():
    """Line 126: Returns None when no OAuth servers configured."""
    config = MagicMock()
    config.get_enabled_mcp_servers.return_value = {}

    result = build_oauth_tool_interceptor(config)
    assert result is None


# --- Line 131: oauth_interceptor when no header ---


def test_oauth_interceptor_passes_through_when_no_header():
    """Line 131: Calls handler directly when no header is available."""
    config = MagicMock()
    server_config = MagicMock()
    server_config.oauth = _make_oauth_config()
    config.get_enabled_mcp_servers.return_value = {"s1": server_config}

    interceptor = build_oauth_tool_interceptor(config)
    assert interceptor is not None

    # Mock token manager to return None header
    class Request:
        def __init__(self):
            self.server_name = "unknown-server"
            self.headers = {}

    async def handler(req):
        return "passed-through"

    result = asyncio.run(interceptor(Request(), handler))
    assert result == "passed-through"


# --- Line 144: get_initial_oauth_headers with no servers ---


def test_get_initial_oauth_headers_returns_empty_when_no_servers():
    """Line 144: Returns empty dict when no OAuth servers."""
    config = MagicMock()
    config.get_enabled_mcp_servers.return_value = {}

    result = asyncio.run(get_initial_oauth_headers(config))
    assert result == {}


# --- Extra: get_authorization_header returns None for unknown server ---


def test_get_authorization_header_returns_none_for_unknown():
    """Returns None for server not in oauth config."""
    manager = OAuthTokenManager({"s1": _make_oauth_config()})

    async def run():
        return await manager.get_authorization_header("unknown")

    result = asyncio.run(run())
    assert result is None


# --- Extra: _is_expiring edge cases ---


def test_is_expiring_with_zero_refresh_skew():
    """_is_expiring with zero skew checks exact expiry."""
    from datetime import UTC, datetime, timedelta

    oauth = _make_oauth_config(refresh_skew_seconds=0)
    token = _OAuthToken(
        access_token="tok",
        token_type="Bearer",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    assert OAuthTokenManager._is_expiring(token, oauth) is True
