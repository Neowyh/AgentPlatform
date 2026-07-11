"""Tests for app.gateway.auth.repositories.sqlite — SQLiteUserRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Helper to build a mock session factory
# ---------------------------------------------------------------------------


def _make_repo():
    from app.gateway.auth.repositories.sqlite import SQLiteUserRepository

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_sf = MagicMock()
    mock_sf.return_value = mock_session

    repo = SQLiteUserRepository(mock_sf)
    return repo, mock_session


def _make_user_row(**overrides):
    from ideer.persistence.user.model import UserRow

    defaults = {
        "id": str(uuid4()),
        "email": "test@example.com",
        "password_hash": "hashed_pw",
        "system_role": "user",
        "created_at": datetime.now(UTC),
        "oauth_provider": None,
        "oauth_id": None,
        "needs_setup": False,
        "token_version": 0,
    }
    defaults.update(overrides)
    return UserRow(**defaults)


def _make_user(**overrides):
    from app.gateway.auth.models import User

    defaults = {
        "id": uuid4(),
        "email": "test@example.com",
        "password_hash": "hashed_pw",
        "system_role": "user",
        "created_at": datetime.now(UTC),
        "oauth_provider": None,
        "oauth_id": None,
        "needs_setup": False,
        "token_version": 0,
    }
    defaults.update(overrides)
    return User(**defaults)


# ---------------------------------------------------------------------------
# _row_to_user
# ---------------------------------------------------------------------------


class TestRowToUser:
    def test_basic_conversion(self):
        from app.gateway.auth.repositories.sqlite import SQLiteUserRepository

        row = _make_user_row(email="a@b.com", system_role="admin")
        user = SQLiteUserRepository._row_to_user(row)
        assert user.email == "a@b.com"
        assert user.system_role == "admin"

    def test_naive_datetime_gets_utc(self):
        from app.gateway.auth.repositories.sqlite import SQLiteUserRepository

        naive_dt = datetime(2024, 1, 1, 12, 0, 0)
        row = _make_user_row(created_at=naive_dt)
        user = SQLiteUserRepository._row_to_user(row)
        assert user.created_at.tzinfo is UTC

    def test_aware_datetime_preserved(self):
        from app.gateway.auth.repositories.sqlite import SQLiteUserRepository

        aware_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        row = _make_user_row(created_at=aware_dt)
        user = SQLiteUserRepository._row_to_user(row)
        assert user.created_at.tzinfo is UTC


# ---------------------------------------------------------------------------
# _user_to_row
# ---------------------------------------------------------------------------


class TestUserToRow:
    def test_basic_conversion(self):
        from app.gateway.auth.repositories.sqlite import SQLiteUserRepository

        user = _make_user(email="x@y.com")
        row = SQLiteUserRepository._user_to_row(user)
        assert row.email == "x@y.com"
        assert row.id == str(user.id)


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_success(self):
        repo, mock_session = _make_repo()
        user = _make_user()

        result = await repo.create_user(user)
        assert result is user
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_email_raises(self):
        from sqlalchemy.exc import IntegrityError

        repo, mock_session = _make_repo()
        user = _make_user(email="dup@test.com")
        mock_session.commit = AsyncMock(side_effect=IntegrityError("dup", {}, Exception()))

        with pytest.raises(ValueError, match="Email already registered"):
            await repo.create_user(user)


# ---------------------------------------------------------------------------
# get_user_by_id
# ---------------------------------------------------------------------------


class TestGetUserById:
    @pytest.mark.asyncio
    async def test_found(self):
        repo, mock_session = _make_repo()
        row = _make_user_row(email="found@test.com")
        mock_session.get = AsyncMock(return_value=row)

        result = await repo.get_user_by_id(row.id)
        assert result is not None
        assert result.email == "found@test.com"

    @pytest.mark.asyncio
    async def test_not_found(self):
        repo, mock_session = _make_repo()
        mock_session.get = AsyncMock(return_value=None)

        result = await repo.get_user_by_id("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# get_user_by_email
# ---------------------------------------------------------------------------


class TestGetUserByEmail:
    @pytest.mark.asyncio
    async def test_found(self):
        repo, mock_session = _make_repo()
        row = _make_user_row(email="search@test.com")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = row
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_user_by_email("search@test.com")
        assert result is not None
        assert result.email == "search@test.com"

    @pytest.mark.asyncio
    async def test_not_found(self):
        repo, mock_session = _make_repo()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_user_by_email("missing@test.com")
        assert result is None


# ---------------------------------------------------------------------------
# update_user
# ---------------------------------------------------------------------------


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_success(self):
        repo, mock_session = _make_repo()
        row = _make_user_row()
        mock_session.get = AsyncMock(return_value=row)

        user = _make_user(id=uuid4())
        user.email = "updated@test.com"
        result = await repo.update_user(user)
        assert result is user
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_not_found_raises(self):
        from app.gateway.auth.repositories.base import UserNotFoundError

        repo, mock_session = _make_repo()
        mock_session.get = AsyncMock(return_value=None)

        user = _make_user()
        with pytest.raises(UserNotFoundError, match="no longer exists"):
            await repo.update_user(user)


# ---------------------------------------------------------------------------
# count_users / count_admin_users
# ---------------------------------------------------------------------------


class TestCountUsers:
    @pytest.mark.asyncio
    async def test_count_users(self):
        repo, mock_session = _make_repo()
        mock_session.scalar = AsyncMock(return_value=5)

        result = await repo.count_users()
        assert result == 5

    @pytest.mark.asyncio
    async def test_count_users_zero(self):
        repo, mock_session = _make_repo()
        mock_session.scalar = AsyncMock(return_value=None)

        result = await repo.count_users()
        assert result == 0

    @pytest.mark.asyncio
    async def test_count_admin_users(self):
        repo, mock_session = _make_repo()
        mock_session.scalar = AsyncMock(return_value=2)

        result = await repo.count_admin_users()
        assert result == 2


# ---------------------------------------------------------------------------
# get_user_by_oauth
# ---------------------------------------------------------------------------


class TestGetUserByOauth:
    @pytest.mark.asyncio
    async def test_found(self):
        repo, mock_session = _make_repo()
        row = _make_user_row(oauth_provider="google", oauth_id="g123")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = row
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_user_by_oauth("google", "g123")
        assert result is not None
        assert result.oauth_provider == "google"

    @pytest.mark.asyncio
    async def test_not_found(self):
        repo, mock_session = _make_repo()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_user_by_oauth("github", "gh456")
        assert result is None
