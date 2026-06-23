"""Test data factories for authentication-related models."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4


class UserDictFactory:
    """Factory for creating test user data as SimpleNamespace objects.

    Usage::

        from tests.factories import UserDictFactory

        user = UserDictFactory.build(role="admin")
        user = UserDictFactory.build(department_id="dept-123")
    """

    @staticmethod
    def build(**kwargs) -> SimpleNamespace:
        """Build a test user with sensible defaults.

        Args:
            **kwargs: Override any default field value.

        Returns:
            SimpleNamespace with user fields.
        """
        defaults = {
            "id": str(uuid4()),
            "email": f"user-{uuid4().hex[:8]}@test.com",
            "password_hash": "$2b$12$test_hash_value",
            "system_role": "user",
            "oauth_provider": None,
            "oauth_id": None,
            "needs_setup": False,
            "token_version": 0,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    @staticmethod
    def build_admin(**kwargs) -> SimpleNamespace:
        """Build a test admin user."""
        return UserDictFactory.build(system_role="admin", **kwargs)

    @staticmethod
    def build_batch(count: int, **kwargs) -> list[SimpleNamespace]:
        """Build multiple test users.

        Args:
            count: Number of users to create.
            **kwargs: Override any default field value.

        Returns:
            List of SimpleNamespace objects.
        """
        return [UserDictFactory.build(**kwargs) for _ in range(count)]
