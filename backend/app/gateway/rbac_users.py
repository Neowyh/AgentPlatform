"""Helpers for creating auth users with RBAC profiles."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.agentplatform.rbac_models import UserModel, UserRole
from app.gateway.auth.models import User
from app.gateway.auth.password import hash_password_async
from deerflow.persistence.user.model import UserRow


async def create_auth_user_with_rbac(
    session,
    *,
    email: str,
    password: str | None,
    username: str,
    role: UserRole,
    department_id: str | None = None,
    needs_setup: bool = False,
    oauth_provider: str | None = None,
    oauth_id: str | None = None,
) -> User:
    """Create matching rows in ``users`` and ``users_ext`` in one transaction."""
    password_hash = await hash_password_async(password)
    user = User(
        email=email,
        password_hash=password_hash,
        system_role="user",
        oauth_provider=oauth_provider,
        oauth_id=oauth_id,
        needs_setup=needs_setup,
    )
    session.add(
        UserRow(
            id=str(user.id),
            email=user.email,
            password_hash=user.password_hash,
            system_role="user",
            created_at=user.created_at,
            oauth_provider=oauth_provider,
            oauth_id=oauth_id,
            needs_setup=user.needs_setup,
            token_version=user.token_version,
        )
    )
    session.add(
        UserModel(
            id=str(user.id),
            username=username,
            role=role.value,
            department_id=department_id,
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError("User already exists") from exc
    return user
