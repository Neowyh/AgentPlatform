"""Race test for concurrent password changes.

change_password() reads user, modifies password_hash + token_version,
then writes back — no row-level locking.  Two concurrent changes with
different passwords race on token_version: last write wins.
"""

import asyncio
from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.gateway.auth.local_provider import LocalAuthProvider
from app.gateway.auth.repositories.sqlite import SQLiteUserRepository
from app.gateway.routers.auth import ChangePasswordRequest, change_password
from ideer.persistence.base import Base


@pytest.mark.asyncio
async def test_concurrent_change_password_race():
    """2 concurrent change_password calls — token_version proves one was lost.

    Uses a REAL in-memory SQLite database.  Both calls read the same base
    user, modify their own copy, and the last write wins.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sf = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    repo = SQLiteUserRepository(sf)
    provider = LocalAuthProvider(repository=repo)

    base_user = await provider.create_user(
        email="race@test.com",
        password="old-password",
        system_role="user",
    )

    def get_user_side_effect(request):
        return deepcopy(base_user)

    def hash_side_effect(password: str) -> str:
        return f"$test_hash${password}"

    body_a = ChangePasswordRequest(current_password="old-password", new_password="newpass1")
    body_b = ChangePasswordRequest(current_password="old-password", new_password="newpass2")

    with (
        patch(
            "app.gateway.routers.auth.get_current_user_from_request",
            side_effect=get_user_side_effect,
        ),
        patch(
            "app.gateway.auth.password.verify_password_async",
            return_value=True,
        ),
        patch(
            "app.gateway.routers.auth.get_local_provider",
            return_value=provider,
        ),
        patch(
            "app.gateway.auth.password.hash_password_async",
            side_effect=hash_side_effect,
        ),
        patch(
            "app.gateway.routers.auth.create_access_token",
            return_value="mock-token",
        ),
        patch("app.gateway.routers.auth._set_session_cookie"),
    ):
        results = await asyncio.gather(
            change_password(MagicMock(), MagicMock(), body_a),
            change_password(MagicMock(), MagicMock(), body_b),
            return_exceptions=True,
        )

    for r in results:
        assert not isinstance(r, Exception), f"Unexpected exception: {r}"

    final_user = await repo.get_user_by_id(str(base_user.id))
    assert final_user is not None
    assert final_user.password_hash in ("$test_hash$newpass1", "$test_hash$newpass2")
    assert 1 <= final_user.token_version <= 2, f"token_version={final_user.token_version} — expected 1 (race) or 2 (serialized)"

    await engine.dispose()
