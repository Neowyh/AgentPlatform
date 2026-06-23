"""Tests for app.gateway.auth.local_provider covering uncovered lines."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLocalAuthProviderAuthenticate:
    """Cover the authenticate() branches."""

    @pytest.mark.asyncio
    async def test_missing_email_returns_none(self):
        """Line 37: not email returns None."""
        from app.gateway.auth.local_provider import LocalAuthProvider

        repo = MagicMock()
        provider = LocalAuthProvider(repo)
        result = await provider.authenticate({"password": "pass"})
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_password_returns_none(self):
        """Line 37: not password returns None."""
        from app.gateway.auth.local_provider import LocalAuthProvider

        repo = MagicMock()
        provider = LocalAuthProvider(repo)
        result = await provider.authenticate({"email": "test@test.com"})
        assert result is None

    @pytest.mark.asyncio
    async def test_user_not_found_returns_none(self):
        """Line 39-40: user is None returns None."""
        from app.gateway.auth.local_provider import LocalAuthProvider

        repo = MagicMock()
        repo.get_user_by_email = AsyncMock(return_value=None)
        provider = LocalAuthProvider(repo)
        result = await provider.authenticate({"email": "test@test.com", "password": "pass"})
        assert result is None

    @pytest.mark.asyncio
    async def test_no_password_hash_returns_none(self):
        """Line 45: OAuth user without password_hash returns None."""
        from app.gateway.auth.local_provider import LocalAuthProvider

        user = MagicMock()
        user.password_hash = None
        repo = MagicMock()
        repo.get_user_by_email = AsyncMock(return_value=user)
        provider = LocalAuthProvider(repo)
        result = await provider.authenticate({"email": "test@test.com", "password": "pass"})
        assert result is None

    @pytest.mark.asyncio
    async def test_password_mismatch_returns_none(self):
        """Line 48: password verification fails returns None."""
        from app.gateway.auth.local_provider import LocalAuthProvider

        user = MagicMock()
        user.password_hash = "hashed"
        repo = MagicMock()
        repo.get_user_by_email = AsyncMock(return_value=user)
        provider = LocalAuthProvider(repo)
        with patch("app.gateway.auth.local_provider.verify_password_async", new_callable=AsyncMock, return_value=False):
            result = await provider.authenticate({"email": "test@test.com", "password": "wrong"})
        assert result is None

    @pytest.mark.asyncio
    async def test_rehash_failure_still_returns_user(self, caplog):
        """Lines 54-57: rehash failure is logged but user is still returned."""
        from app.gateway.auth.local_provider import LocalAuthProvider

        user = MagicMock()
        user.password_hash = "hashed"
        user.email = "test@test.com"
        repo = MagicMock()
        repo.get_user_by_email = AsyncMock(return_value=user)
        repo.update_user = AsyncMock(side_effect=RuntimeError("db error"))
        provider = LocalAuthProvider(repo)
        with (
            patch("app.gateway.auth.local_provider.verify_password_async", new_callable=AsyncMock, return_value=True),
            patch("app.gateway.auth.local_provider.needs_rehash", return_value=True),
            patch("app.gateway.auth.local_provider.hash_password_async", new_callable=AsyncMock, return_value="new_hash"),
        ):
            result = await provider.authenticate({"email": "test@test.com", "password": "correct"})
        assert result is user
        assert "Failed to rehash" in caplog.text


class TestLocalAuthProviderDelegates:
    """Cover delegation methods: get_user_by_oauth, count_users, update_user, get_user_by_email."""

    @pytest.mark.asyncio
    async def test_get_user_by_oauth(self):
        """Line 88: delegates to repo."""
        from app.gateway.auth.local_provider import LocalAuthProvider

        repo = MagicMock()
        repo.get_user_by_oauth = AsyncMock(return_value="user")
        provider = LocalAuthProvider(repo)
        result = await provider.get_user_by_oauth("github", "123")
        assert result == "user"
        repo.get_user_by_oauth.assert_called_once_with("github", "123")

    @pytest.mark.asyncio
    async def test_count_users(self):
        """Line 92: delegates to repo."""
        from app.gateway.auth.local_provider import LocalAuthProvider

        repo = MagicMock()
        repo.count_users = AsyncMock(return_value=5)
        provider = LocalAuthProvider(repo)
        result = await provider.count_users()
        assert result == 5

    @pytest.mark.asyncio
    async def test_update_user(self):
        """Line 100: delegates to repo."""
        from app.gateway.auth.local_provider import LocalAuthProvider

        user = MagicMock()
        repo = MagicMock()
        repo.update_user = AsyncMock(return_value=user)
        provider = LocalAuthProvider(repo)
        result = await provider.update_user(user)
        assert result is user

    @pytest.mark.asyncio
    async def test_get_user_by_email(self):
        """Line 104: delegates to repo."""
        from app.gateway.auth.local_provider import LocalAuthProvider

        repo = MagicMock()
        repo.get_user_by_email = AsyncMock(return_value="user")
        provider = LocalAuthProvider(repo)
        result = await provider.get_user_by_email("test@test.com")
        assert result == "user"
