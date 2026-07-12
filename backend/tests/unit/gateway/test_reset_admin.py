"""Tests for app.gateway.auth.reset_admin module."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateway.auth.models import User


def _make_user(**overrides) -> User:
    """Create a User instance with sensible defaults for testing."""
    defaults = {
        "email": "admin@example.com",
        "password_hash": "$dfv2$oldhash",
        "system_role": "admin",
        "needs_setup": False,
        "token_version": 0,
    }
    defaults.update(overrides)
    return User(**defaults)


def _make_session_factory(admin_row=None):
    """Build a mock async session factory that returns an RBAC row from execute()."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = admin_row
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=mock_session)


def _close_coro_and_return(value):
    def _side_effect(coro):
        coro.close()
        return value

    return _side_effect


class TestRunFunction:
    """Test the async _run() helper that powers the CLI."""

    @pytest.mark.asyncio
    async def test_reset_by_email_success(self, tmp_path: Path) -> None:
        """When --email is given and user exists, password is reset."""
        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.get_user_by_email = AsyncMock(return_value=user)
        mock_repo.update_user = AsyncMock(return_value=user)

        mock_sf = _make_session_factory(admin_row=SimpleNamespace(id=str(user.id)))
        cred_path = tmp_path / "admin_initial_credentials.txt"

        with (
            patch("ideer.config.get_app_config"),
            patch("ideer.persistence.engine.init_engine_from_config", new_callable=AsyncMock),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
            patch("ideer.persistence.engine.close_engine", new_callable=AsyncMock),
            patch("app.gateway.auth.reset_admin.SQLiteUserRepository", return_value=mock_repo),
            patch("app.gateway.auth.reset_admin.hash_password", return_value="$dfv2$newhash"),
            patch("app.gateway.auth.reset_admin.write_initial_credentials", return_value=cred_path),
        ):
            from app.gateway.auth.reset_admin import _run

            exit_code = await _run("admin@example.com")

        assert exit_code == 0
        mock_repo.get_user_by_email.assert_awaited_once_with("admin@example.com")
        mock_repo.update_user.assert_awaited_once()
        # Verify user fields were mutated
        updated_user = mock_repo.update_user.call_args[0][0]
        assert updated_user.password_hash == "$dfv2$newhash"
        assert updated_user.needs_setup is True
        assert updated_user.token_version == 1

    @pytest.mark.asyncio
    async def test_reset_by_email_user_not_found(self) -> None:
        """When --email is given but user does not exist, returns 1."""
        mock_repo = MagicMock()
        mock_repo.get_user_by_email = AsyncMock(return_value=None)

        mock_sf = _make_session_factory(admin_row=None)

        with (
            patch("ideer.config.get_app_config"),
            patch("ideer.persistence.engine.init_engine_from_config", new_callable=AsyncMock),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
            patch("ideer.persistence.engine.close_engine", new_callable=AsyncMock),
            patch("app.gateway.auth.reset_admin.SQLiteUserRepository", return_value=mock_repo),
        ):
            from app.gateway.auth.reset_admin import _run

            exit_code = await _run("missing@example.com")

        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_reset_find_first_admin_success(self, tmp_path: Path) -> None:
        """When no --email, finds the first admin user via direct SELECT."""
        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.get_user_by_id = AsyncMock(return_value=user)
        mock_repo.update_user = AsyncMock(return_value=user)

        # Mock the session execute for the direct SELECT
        mock_row = SimpleNamespace(id=str(user.id))
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_row
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)
        cred_path = tmp_path / "admin_initial_credentials.txt"

        with (
            patch("ideer.config.get_app_config"),
            patch("ideer.persistence.engine.init_engine_from_config", new_callable=AsyncMock),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
            patch("ideer.persistence.engine.close_engine", new_callable=AsyncMock),
            patch("app.gateway.auth.reset_admin.SQLiteUserRepository", return_value=mock_repo),
            patch("app.gateway.auth.reset_admin.hash_password", return_value="$dfv2$gen"),
            patch("app.gateway.auth.reset_admin.write_initial_credentials", return_value=cred_path),
        ):
            from app.gateway.auth.reset_admin import _run

            exit_code = await _run(None)

        assert exit_code == 0
        mock_repo.get_user_by_id.assert_awaited_once_with(str(user.id))

    @pytest.mark.asyncio
    async def test_reset_no_admin_user_found(self) -> None:
        """When no --email and no admin exists in the DB, returns 1."""
        mock_repo = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)

        with (
            patch("ideer.config.get_app_config"),
            patch("ideer.persistence.engine.init_engine_from_config", new_callable=AsyncMock),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
            patch("ideer.persistence.engine.close_engine", new_callable=AsyncMock),
            patch("app.gateway.auth.reset_admin.SQLiteUserRepository", return_value=mock_repo),
        ):
            from app.gateway.auth.reset_admin import _run

            exit_code = await _run(None)

        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_session_factory_none_returns_1(self) -> None:
        """When get_session_factory returns None, _run returns 1."""
        with (
            patch("ideer.config.get_app_config"),
            patch("ideer.persistence.engine.init_engine_from_config", new_callable=AsyncMock),
            patch("ideer.persistence.engine.get_session_factory", return_value=None),
            patch("ideer.persistence.engine.close_engine", new_callable=AsyncMock),
        ):
            from app.gateway.auth.reset_admin import _run

            exit_code = await _run("admin@example.com")

        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_close_engine_called_in_finally(self, tmp_path: Path) -> None:
        """close_engine() is always called, even on success."""
        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.get_user_by_email = AsyncMock(return_value=user)
        mock_repo.update_user = AsyncMock(return_value=user)

        mock_sf = _make_session_factory(admin_row=SimpleNamespace(id=str(user.id)))
        cred_path = tmp_path / "creds.txt"

        with (
            patch("ideer.config.get_app_config"),
            patch("ideer.persistence.engine.init_engine_from_config", new_callable=AsyncMock),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
            patch("ideer.persistence.engine.close_engine", new_callable=AsyncMock) as mock_close,
            patch("app.gateway.auth.reset_admin.SQLiteUserRepository", return_value=mock_repo),
            patch("app.gateway.auth.reset_admin.hash_password", return_value="h"),
            patch("app.gateway.auth.reset_admin.write_initial_credentials", return_value=cred_path),
        ):
            from app.gateway.auth.reset_admin import _run

            await _run("admin@example.com")

        mock_close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_engine_called_on_failure(self) -> None:
        """close_engine() is called even when the function returns 1."""
        with (
            patch("ideer.config.get_app_config"),
            patch("ideer.persistence.engine.init_engine_from_config", new_callable=AsyncMock),
            patch("ideer.persistence.engine.get_session_factory", return_value=None),
            patch("ideer.persistence.engine.close_engine", new_callable=AsyncMock) as mock_close,
        ):
            from app.gateway.auth.reset_admin import _run

            await _run("admin@example.com")

        mock_close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_token_version_incremented(self, tmp_path: Path) -> None:
        """token_version should be incremented by 1 on each reset."""
        user = _make_user(token_version=5)
        mock_repo = MagicMock()
        mock_repo.get_user_by_email = AsyncMock(return_value=user)
        mock_repo.update_user = AsyncMock(return_value=user)

        mock_sf = _make_session_factory(admin_row=SimpleNamespace(id=str(user.id)))
        cred_path = tmp_path / "creds.txt"

        with (
            patch("ideer.config.get_app_config"),
            patch("ideer.persistence.engine.init_engine_from_config", new_callable=AsyncMock),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
            patch("ideer.persistence.engine.close_engine", new_callable=AsyncMock),
            patch("app.gateway.auth.reset_admin.SQLiteUserRepository", return_value=mock_repo),
            patch("app.gateway.auth.reset_admin.hash_password", return_value="h"),
            patch("app.gateway.auth.reset_admin.write_initial_credentials", return_value=cred_path),
        ):
            from app.gateway.auth.reset_admin import _run

            await _run("admin@example.com")

        updated_user = mock_repo.update_user.call_args[0][0]
        assert updated_user.token_version == 6

    @pytest.mark.asyncio
    async def test_credential_file_called_with_reset_label(self, tmp_path: Path) -> None:
        """write_initial_credentials is called with label='reset'."""
        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.get_user_by_email = AsyncMock(return_value=user)
        mock_repo.update_user = AsyncMock(return_value=user)

        mock_sf = _make_session_factory(admin_row=SimpleNamespace(id=str(user.id)))
        cred_path = tmp_path / "creds.txt"

        with (
            patch("ideer.config.get_app_config"),
            patch("ideer.persistence.engine.init_engine_from_config", new_callable=AsyncMock),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
            patch("ideer.persistence.engine.close_engine", new_callable=AsyncMock),
            patch("app.gateway.auth.reset_admin.SQLiteUserRepository", return_value=mock_repo),
            patch("app.gateway.auth.reset_admin.hash_password", return_value="h"),
            patch("app.gateway.auth.reset_admin.write_initial_credentials", return_value=cred_path) as mock_write,
        ):
            from app.gateway.auth.reset_admin import _run

            await _run("admin@example.com")

        mock_write.assert_called_once_with(user.email, mock_write.call_args[0][1], label="reset")


class TestMainFunction:
    """Test the CLI main() entry point."""

    def test_main_with_email_arg(self) -> None:
        """main() parses --email and calls _run."""
        with (
            patch("sys.argv", ["reset_admin", "--email", "admin@test.com"]),
            patch("app.gateway.auth.reset_admin.asyncio") as mock_asyncio,
        ):
            mock_asyncio.run.side_effect = _close_coro_and_return(0)
            from app.gateway.auth.reset_admin import main

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0
            mock_asyncio.run.assert_called_once()

    def test_main_without_email_arg(self) -> None:
        """main() passes None for email when --email is not given."""
        with (
            patch("sys.argv", ["reset_admin"]),
            patch("app.gateway.auth.reset_admin.asyncio") as mock_asyncio,
        ):
            mock_asyncio.run.side_effect = _close_coro_and_return(1)
            from app.gateway.auth.reset_admin import main

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1

    def test_main_exits_with_run_return_code(self) -> None:
        """main() sys.exit()s with the return code from _run."""
        with (
            patch("sys.argv", ["reset_admin", "--email", "x@y.com"]),
            patch("app.gateway.auth.reset_admin.asyncio") as mock_asyncio,
        ):
            mock_asyncio.run.side_effect = _close_coro_and_return(42)
            from app.gateway.auth.reset_admin import main

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 42
