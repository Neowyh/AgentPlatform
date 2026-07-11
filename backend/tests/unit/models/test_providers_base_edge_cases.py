"""Tests for app.gateway.auth.providers and repositories/base.

The abstract methods in these ABCs contain ``raise NotImplementedError``
in their bodies.  We cover those lines by defining concrete subclasses
that call ``super().method()`` to reach the ``raise``.
"""

from __future__ import annotations

import asyncio

import pytest


class TestAuthProviderAbstractMethods:
    """Lines 15, 20: abstract method bodies raise NotImplementedError."""

    def test_authenticate_raises(self):
        from app.gateway.auth.providers import AuthProvider

        class Impl(AuthProvider):
            async def authenticate(self, credentials):
                return await super().authenticate(credentials)

            async def get_user(self, user_id):
                return await super().get_user(user_id)

        provider = Impl()
        with pytest.raises(NotImplementedError):
            asyncio.run(provider.authenticate({}))

    def test_get_user_raises(self):
        from app.gateway.auth.providers import AuthProvider

        class Impl(AuthProvider):
            async def authenticate(self, credentials):
                return None

            async def get_user(self, user_id):
                return await super().get_user(user_id)

        provider = Impl()
        with pytest.raises(NotImplementedError):
            asyncio.run(provider.get_user("id"))


class TestUserRepositoryAbstractMethods:
    """Lines 38, 50, 62, 79, 84, 89, 102: abstract method bodies raise NotImplementedError."""

    def _make_repo(self):
        from app.gateway.auth.repositories.base import UserRepository

        class Impl(UserRepository):
            async def create_user(self, user):
                return await super().create_user(user)

            async def get_user_by_id(self, user_id):
                return await super().get_user_by_id(user_id)

            async def get_user_by_email(self, email):
                return await super().get_user_by_email(email)

            async def update_user(self, user):
                return await super().update_user(user)

            async def count_users(self):
                return await super().count_users()

            async def count_admin_users(self):
                return await super().count_admin_users()

            async def get_user_by_oauth(self, provider, oauth_id):
                return await super().get_user_by_oauth(provider, oauth_id)

        return Impl()

    def test_create_user_raises(self):
        with pytest.raises(NotImplementedError):
            asyncio.run(self._make_repo().create_user(None))

    def test_get_user_by_id_raises(self):
        with pytest.raises(NotImplementedError):
            asyncio.run(self._make_repo().get_user_by_id("id"))

    def test_get_user_by_email_raises(self):
        with pytest.raises(NotImplementedError):
            asyncio.run(self._make_repo().get_user_by_email("email"))

    def test_update_user_raises(self):
        with pytest.raises(NotImplementedError):
            asyncio.run(self._make_repo().update_user(None))

    def test_count_users_raises(self):
        with pytest.raises(NotImplementedError):
            asyncio.run(self._make_repo().count_users())

    def test_count_admin_users_raises(self):
        with pytest.raises(NotImplementedError):
            asyncio.run(self._make_repo().count_admin_users())

    def test_get_user_by_oauth_raises(self):
        with pytest.raises(NotImplementedError):
            asyncio.run(self._make_repo().get_user_by_oauth("gh", "id"))
