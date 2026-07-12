"""Race test for admin role toggle with with_for_update silently skipped on SQLite.

update_user_role() wraps SELECT in with_for_update() but silently skips
it on SQLite.  Concurrent toggles read the same current value, both
compute a new value, last write wins — one toggle is lost.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.gateway.routers.admin import UpdateRoleRequest, update_user_role
from ideer.persistence.base import Base
from ideer.persistence.models.user import UserModel, UserRole


@pytest.mark.asyncio
async def test_concurrent_toggle_user_disabled_race():
    """3 concurrent toggles race on with_for_update skip — one toggle is lost.

    Uses a REAL in-memory SQLite database so we test actual DB behavior,
    not mock-to-mock communication.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sf = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with sf() as session:
        target_user = UserModel(id="target-1", username="target", role=UserRole.USER, disabled=False)
        session.add(target_user)
        await session.commit()

    current_user = MagicMock()
    current_user.role = UserRole.SUPER_ADMIN
    current_user.id = "admin-1"
    current_user.department_id = None

    body = UpdateRoleRequest(role=UserRole.USER)

    with patch("app.gateway.routers.admin.get_session_factory", return_value=sf):
        results = await asyncio.gather(
            update_user_role(
                user_id="target-1",
                body=body,
                http_request=MagicMock(),
                current_user=current_user,
            ),
            update_user_role(
                user_id="target-1",
                body=body,
                http_request=MagicMock(),
                current_user=current_user,
            ),
            update_user_role(
                user_id="target-1",
                body=body,
                http_request=MagicMock(),
                current_user=current_user,
            ),
            return_exceptions=True,
        )

    for r in results:
        assert not isinstance(r, Exception), f"Unexpected exception: {r}"

    async with sf() as session:
        result = await session.execute(select(UserModel).where(UserModel.id == "target-1"))
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.disabled is False
        assert user.role == UserRole.USER

    await engine.dispose()
