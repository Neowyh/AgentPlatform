"""Canonical-mode legacy-name Run resolution through the catalog alias resolver."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from app.gateway.services import _resolve_canonical_alias
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource
from ideer.persistence.models.user import UserModel


@pytest_asyncio.fixture
async def session_factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'alias-run.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _user(user_id: str, department_id: str | None = None) -> UserModel:
    return UserModel(
        id=user_id,
        username=f"{user_id}@test.com",
        role="user",
        department_id=department_id,
        disabled=False,
    )


def _resource(resource_id: str, slug: str, owner_id: str, visibility: str = "private") -> Resource:
    return Resource(
        id=resource_id,
        type="agent",
        slug=slug,
        display_name=slug,
        owner_id=owner_id,
        visibility=visibility,
        lifecycle_status="active",
        storage_kind="filesystem",
        storage_key=f"agents/{slug}",
    )


def _request(user_id: str | None = "user-1") -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(user=SimpleNamespace(id=user_id)))


@pytest.fixture()
def canonical_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")


def _no_db(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode() -> None:
        raise AssertionError("database must not be consulted")

    monkeypatch.setattr("ideer.persistence.engine.get_session_factory", explode)


class TestResolveCanonicalAlias:
    @pytest.mark.asyncio
    async def test_resolves_owner_agent_first(self, session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch, canonical_env: None) -> None:
        async with session_factory() as session:
            session.add_all(
                [
                    _user("user-1"),
                    _user("user-2"),
                    _resource("11111111-1111-1111-1111-111111111111", "writer", "user-2"),
                    _resource("22222222-2222-2222-2222-222222222222", "writer", "user-1"),
                ]
            )
            await session.commit()
        monkeypatch.setattr("ideer.persistence.engine.get_session_factory", lambda: session_factory)

        resolved = await _resolve_canonical_alias("writer", _request("user-1"))

        assert resolved == "22222222-2222-2222-2222-222222222222"

    @pytest.mark.asyncio
    async def test_resolves_unique_visible_shared_agent(self, session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch, canonical_env: None) -> None:
        async with session_factory() as session:
            session.add_all(
                [
                    _user("user-1"),
                    _user("user-2"),
                    _resource("33333333-3333-3333-3333-333333333333", "poet", "user-2", visibility="public"),
                ]
            )
            await session.commit()
        monkeypatch.setattr("ideer.persistence.engine.get_session_factory", lambda: session_factory)

        resolved = await _resolve_canonical_alias("poet", _request("user-1"))

        assert resolved == "33333333-3333-3333-3333-333333333333"

    @pytest.mark.asyncio
    async def test_ambiguous_visible_shared_agents_are_409(self, session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch, canonical_env: None) -> None:
        async with session_factory() as session:
            session.add_all(
                [
                    _user("user-1"),
                    _user("user-2"),
                    _user("user-3"),
                    _resource("44444444-4444-4444-4444-444444444444", "critic", "user-2", visibility="public"),
                    _resource("55555555-5555-5555-5555-555555555555", "critic", "user-3", visibility="public"),
                ]
            )
            await session.commit()
        monkeypatch.setattr("ideer.persistence.engine.get_session_factory", lambda: session_factory)

        with pytest.raises(HTTPException) as exc_info:
            await _resolve_canonical_alias("critic", _request("user-1"))

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_missing_alias_is_404(self, session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch, canonical_env: None) -> None:
        async with session_factory() as session:
            session.add(_user("user-1"))
            await session.commit()
        monkeypatch.setattr("ideer.persistence.engine.get_session_factory", lambda: session_factory)

        with pytest.raises(HTTPException) as exc_info:
            await _resolve_canonical_alias("ghost", _request("user-1"))

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_private_agent_of_other_user_is_404(self, session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch, canonical_env: None) -> None:
        async with session_factory() as session:
            session.add_all(
                [
                    _user("user-1"),
                    _user("user-2"),
                    _resource("66666666-6666-6666-6666-666666666666", "diarist", "user-2"),
                ]
            )
            await session.commit()
        monkeypatch.setattr("ideer.persistence.engine.get_session_factory", lambda: session_factory)

        with pytest.raises(HTTPException) as exc_info:
            await _resolve_canonical_alias("diarist", _request("user-1"))

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_default_assistant_returns_none_without_db(self, session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch, canonical_env: None) -> None:
        _no_db(monkeypatch)

        assert await _resolve_canonical_alias("lead_agent", _request("user-1")) is None

    @pytest.mark.asyncio
    async def test_non_canonical_mode_returns_none_without_db(self, session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "dual")
        _no_db(monkeypatch)

        assert await _resolve_canonical_alias("writer", _request("user-1")) is None

    @pytest.mark.asyncio
    async def test_missing_authenticated_user_is_401(self, session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch, canonical_env: None) -> None:
        _no_db(monkeypatch)

        with pytest.raises(HTTPException) as exc_info:
            await _resolve_canonical_alias("writer", _request(None))

        assert exc_info.value.status_code == 401


class TestStartRunCanonicalLegacyName:
    @pytest.fixture()
    def mock_deps(self):
        bridge = MagicMock()
        bridge.subscribe = MagicMock()

        run_mgr = MagicMock()
        run_mgr.create_or_reject = AsyncMock()
        run_mgr.cancel = AsyncMock()

        run_ctx = MagicMock()
        run_ctx.thread_store = MagicMock()
        run_ctx.thread_store.get = AsyncMock(return_value=None)
        run_ctx.thread_store.create = AsyncMock()
        run_ctx.thread_store.update_status = AsyncMock()

        request = MagicMock()
        request.state = SimpleNamespace(user=SimpleNamespace(id="user-1"))
        request.headers = {}

        return bridge, run_mgr, run_ctx, request

    @staticmethod
    def _body(assistant_id: str, context: dict | None = None) -> SimpleNamespace:
        return SimpleNamespace(
            assistant_id=assistant_id,
            on_disconnect="cancel",
            input={"messages": [{"role": "user", "content": "hi"}]},
            config=None,
            metadata=None,
            multitask_strategy="reject",
            stream_mode=None,
            stream_subgraphs=False,
            interrupt_before=None,
            interrupt_after=None,
            context=context,
        )

    @pytest.mark.asyncio
    async def test_canonical_mode_resolves_legacy_name_via_alias(self, mock_deps, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
        bridge, run_mgr, run_ctx, request = mock_deps
        resource_id = "22222222-2222-2222-2222-222222222222"
        record = MagicMock(run_id="canonical-run", task=None)
        run_mgr.create_or_reject.return_value = record

        with (
            patch("app.gateway.services.get_stream_bridge", return_value=bridge),
            patch("app.gateway.services.get_run_manager", return_value=run_mgr),
            patch("app.gateway.services.get_run_context", return_value=run_ctx),
            patch("app.gateway.services._resolve_canonical_alias", new_callable=AsyncMock, return_value=resource_id) as alias,
            patch("app.gateway.services._prepare_canonical_agent_run", new_callable=AsyncMock) as prepare,
            patch("app.gateway.services.run_agent", new_callable=AsyncMock),
            patch("app.gateway.services.get_app_config") as mock_app_config,
            patch("app.gateway.services.uuid.uuid4", return_value="canonical-run"),
        ):
            mock_app_config.return_value.get_model_config.return_value = None
            from app.gateway.services import start_run

            result = await start_run(self._body("writer"), "thread-1", request)

        assert result is record
        alias.assert_awaited_once_with("writer", request)
        prepare.assert_awaited_once_with(resource_id, request, "canonical-run")
        assert run_mgr.create_or_reject.call_args.kwargs["run_id"] == "canonical-run"

    @pytest.mark.asyncio
    async def test_canonical_mode_fails_closed_when_alias_missing(self, mock_deps, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
        bridge, run_mgr, run_ctx, request = mock_deps

        with (
            patch("app.gateway.services.get_stream_bridge", return_value=bridge),
            patch("app.gateway.services.get_run_manager", return_value=run_mgr),
            patch("app.gateway.services.get_run_context", return_value=run_ctx),
            patch(
                "app.gateway.services._resolve_canonical_alias",
                new_callable=AsyncMock,
                side_effect=HTTPException(status_code=404, detail="Agent 'ghost' not found"),
            ),
            patch("app.gateway.services.run_agent", new_callable=AsyncMock),
            patch("app.gateway.services.get_app_config") as mock_app_config,
        ):
            mock_app_config.return_value.get_model_config.return_value = None
            from app.gateway.services import start_run

            with pytest.raises(HTTPException) as exc_info:
                await start_run(self._body("ghost"), "thread-1", request)

        assert exc_info.value.status_code == 404
        run_mgr.create_or_reject.assert_not_called()

    @pytest.mark.asyncio
    async def test_canonical_mode_default_assistant_keeps_default_path(self, mock_deps, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
        bridge, run_mgr, run_ctx, request = mock_deps
        record = MagicMock(run_id="run-123", task=None)
        run_mgr.create_or_reject.return_value = record

        with (
            patch("app.gateway.services.get_stream_bridge", return_value=bridge),
            patch("app.gateway.services.get_run_manager", return_value=run_mgr),
            patch("app.gateway.services.get_run_context", return_value=run_ctx),
            patch("app.gateway.services._resolve_canonical_alias", new_callable=AsyncMock, return_value=None) as alias,
            patch("app.gateway.services.resolve_agent_factory") as mock_factory,
            patch("app.gateway.services.run_agent", new_callable=AsyncMock),
            patch("app.gateway.services.get_app_config") as mock_app_config,
        ):
            mock_factory.return_value = MagicMock()
            mock_app_config.return_value.get_model_config.return_value = None
            from app.gateway.services import start_run

            result = await start_run(self._body("lead_agent"), "thread-1", request)

        assert result is record
        alias.assert_awaited_once_with("lead_agent", request)
        run_mgr.create_or_reject.assert_called_once()

    @pytest.mark.asyncio
    async def test_canonical_mode_resolves_context_agent_name_uuid(self, mock_deps, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
        bridge, run_mgr, run_ctx, request = mock_deps
        resource_id = "11111111-1111-1111-1111-111111111111"
        record = MagicMock(run_id="canonical-run", task=None)
        run_mgr.create_or_reject.return_value = record

        with (
            patch("app.gateway.services.get_stream_bridge", return_value=bridge),
            patch("app.gateway.services.get_run_manager", return_value=run_mgr),
            patch("app.gateway.services.get_run_context", return_value=run_ctx),
            patch("app.gateway.services._resolve_canonical_alias", new_callable=AsyncMock) as alias,
            patch("app.gateway.services._prepare_canonical_agent_run", new_callable=AsyncMock) as prepare,
            patch("app.gateway.services.run_agent", new_callable=AsyncMock),
            patch("app.gateway.services.get_app_config") as mock_app_config,
            patch("app.gateway.services.uuid.uuid4", return_value="canonical-run"),
        ):
            mock_app_config.return_value.get_model_config.return_value = None
            from app.gateway.services import start_run

            result = await start_run(self._body("lead_agent", {"agent_name": resource_id}), "thread-1", request)

        assert result is record
        alias.assert_not_called()
        prepare.assert_awaited_once_with(resource_id, request, "canonical-run")
        assert run_mgr.create_or_reject.call_args.kwargs["run_id"] == "canonical-run"

    @pytest.mark.asyncio
    async def test_canonical_mode_resolves_context_agent_name_legacy_name(self, mock_deps, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
        bridge, run_mgr, run_ctx, request = mock_deps
        resource_id = "22222222-2222-2222-2222-222222222222"
        record = MagicMock(run_id="canonical-run", task=None)
        run_mgr.create_or_reject.return_value = record

        with (
            patch("app.gateway.services.get_stream_bridge", return_value=bridge),
            patch("app.gateway.services.get_run_manager", return_value=run_mgr),
            patch("app.gateway.services.get_run_context", return_value=run_ctx),
            patch("app.gateway.services._resolve_canonical_alias", new_callable=AsyncMock, return_value=resource_id) as alias,
            patch("app.gateway.services._prepare_canonical_agent_run", new_callable=AsyncMock) as prepare,
            patch("app.gateway.services.run_agent", new_callable=AsyncMock),
            patch("app.gateway.services.get_app_config") as mock_app_config,
            patch("app.gateway.services.uuid.uuid4", return_value="canonical-run"),
        ):
            mock_app_config.return_value.get_model_config.return_value = None
            from app.gateway.services import start_run

            result = await start_run(self._body("lead_agent", {"agent_name": "writer"}), "thread-1", request)

        assert result is record
        alias.assert_awaited_once_with("writer", request)
        prepare.assert_awaited_once_with(resource_id, request, "canonical-run")

    @pytest.mark.asyncio
    async def test_dual_mode_resolves_context_agent_name_uuid(self, mock_deps, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("IDEER_RESOURCE_CATALOG_MODE", raising=False)
        bridge, run_mgr, run_ctx, request = mock_deps
        resource_id = "11111111-1111-1111-1111-111111111111"
        record = MagicMock(run_id="canonical-run", task=None)
        run_mgr.create_or_reject.return_value = record

        with (
            patch("app.gateway.services.get_stream_bridge", return_value=bridge),
            patch("app.gateway.services.get_run_manager", return_value=run_mgr),
            patch("app.gateway.services.get_run_context", return_value=run_ctx),
            patch("app.gateway.services._resolve_canonical_alias", new_callable=AsyncMock) as alias,
            patch("app.gateway.services._prepare_canonical_agent_run", new_callable=AsyncMock) as prepare,
            patch("app.gateway.services.run_agent", new_callable=AsyncMock),
            patch("app.gateway.services.get_app_config") as mock_app_config,
            patch("app.gateway.services.uuid.uuid4", return_value="canonical-run"),
        ):
            mock_app_config.return_value.get_model_config.return_value = None
            from app.gateway.services import start_run

            result = await start_run(self._body("lead_agent", {"agent_name": resource_id}), "thread-1", request)

        assert result is record
        alias.assert_not_called()
        prepare.assert_awaited_once_with(resource_id, request, "canonical-run")
