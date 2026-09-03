"""T2: RBAC identity cached on request.state — duplicate UserModel SELECTs gone."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from app.gateway.authz import _authenticate, _cached_rbac_identity


def _make_request() -> MagicMock:
    return MagicMock()


def _mock_session_factory(rbac_row):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = rbac_row
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_sf = MagicMock(return_value=mock_session)
    return mock_sf, mock_session


@pytest.mark.asyncio
async def test_authenticate_stashes_identity_on_request_state():
    user = SimpleNamespace(id="u-1", email="u@test.com")
    rbac_row = SimpleNamespace(id="u-1", username="u@test.com", role="user", department_id="dept-1", disabled=False)
    mock_sf, _ = _mock_session_factory(rbac_row)
    request = _make_request()
    with (
        patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=user),
        patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
    ):
        await _authenticate(request)
    assert request.state._ideer_rbac_user == {
        "user_id": "u-1",
        "department_id": "dept-1",
        "role": "user",
    }


@pytest.mark.asyncio
async def test_anonymous_request_stashes_nothing():
    request = SimpleNamespace(state=SimpleNamespace())
    with patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=None):
        await _authenticate(request)
    assert getattr(request.state, "_ideer_rbac_user", None) is None


@pytest.mark.asyncio
async def test_alias_resolve_uses_cache_without_user_select():
    from app.gateway.services import _resolve_canonical_alias

    request = _make_request()
    request.state.user = SimpleNamespace(id="u-1")
    request.state._ideer_rbac_user = {
        "user_id": "u-1",
        "department_id": "dept-1",
        "role": "user",
    }
    _, mock_session = _mock_session_factory(None)
    mock_sf = MagicMock(return_value=_mock_session_factory(None)[0].return_value)
    with (
        patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        patch(
            "ideer.resources.service.ResourceService.resolve_legacy_alias",
            new=AsyncMock(return_value=SimpleNamespace(id="res-9")),
        ),
    ):
        resolved = await _resolve_canonical_alias("some-legacy-name", request)
    assert resolved == "res-9"
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_alias_resolve_falls_back_to_query_without_cache():
    from app.gateway.services import _resolve_canonical_alias

    rbac_row = SimpleNamespace(id="u-1", username="u@test.com", role="user", department_id=None, disabled=False)
    mock_sf, mock_session = _mock_session_factory(rbac_row)
    request = _make_request()
    request.state.user = SimpleNamespace(id="u-1")
    with (
        patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        patch(
            "ideer.resources.service.ResourceService.resolve_legacy_alias",
            new=AsyncMock(return_value=SimpleNamespace(id="res-9")),
        ),
    ):
        resolved = await _resolve_canonical_alias("some-legacy-name", request)
    assert resolved == "res-9"
    mock_session.execute.assert_called_once()


def test_cached_identity_helpers():
    request = _make_request()
    assert _cached_rbac_identity(request, "u-1") is None
    request.state._ideer_rbac_user = {"user_id": "u-1", "department_id": None, "role": "user"}
    assert _cached_rbac_identity(request, "u-1")["role"] == "user"
    assert _cached_rbac_identity(request, "other-user") is None
    assert _cached_rbac_identity(MagicMock(spec=Request), "u-1") is None
