"""Tests for deprecated admin skill-applications endpoints.

Verifies that all old endpoints return 410 Gone with migration guidance.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.gateway.routers.admin_skill_applications import router


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.mark.asyncio
class TestDeprecatedSkillApplicationsEndpoints:
    """All old admin/skill-applications endpoints return 410 Gone."""

    async def test_list_returns_410(self, client: AsyncClient):
        resp = await client.get("/api/admin/skill-applications")
        assert resp.status_code == 410
        body = resp.json()
        assert body["detail"]["message"] == "This endpoint is deprecated."
        assert "visibility-applications" in body["detail"]["replacement"]

    async def test_get_by_id_returns_410(self, client: AsyncClient):
        resp = await client.get("/api/admin/skill-applications/some-id")
        assert resp.status_code == 410
        body = resp.json()
        assert body["detail"]["message"] == "This endpoint is deprecated."
        assert "visibility-applications" in body["detail"]["replacement"]

    async def test_put_returns_410(self, client: AsyncClient):
        resp = await client.put(
            "/api/admin/skill-applications/some-id",
            json={"action": "approved", "comment": ""},
        )
        assert resp.status_code == 410
        body = resp.json()
        assert body["detail"]["message"] == "This endpoint is deprecated."
        assert "visibility-applications" in body["detail"]["replacement"]

    async def test_list_with_query_params_returns_410(self, client: AsyncClient):
        resp = await client.get("/api/admin/skill-applications?status=pending")
        assert resp.status_code == 410
