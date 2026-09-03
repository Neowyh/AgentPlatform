"""Contract tests for global gateway exception handlers.

Verifies that every error path returns the unified response envelope and
that unhandled exceptions never leak internal details (stack traces, model
paths, payloads) to the client.
"""

from __future__ import annotations

import logging

import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.gateway.app import register_exception_handlers
from app.gateway.error_codes import ApiException


class _Body(BaseModel):
    name: str


@pytest.fixture()
def probe_app() -> FastAPI:
    """Minimal app with the real handler chain and a few probe endpoints."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> dict:
        raise RuntimeError("SECRET_INTERNAL_STATE=classified / model_path=/srv/llm/weights")

    @app.get("/teapot")
    async def teapot() -> dict:
        raise HTTPException(status_code=418, detail="short and stout")

    @app.post("/validate")
    async def validate(body: _Body) -> dict:
        return {"ok": True}

    @app.get("/api-error")
    async def api_error() -> dict:
        raise ApiException("RESOURCE_NOT_FOUND", "resource missing")

    return app


@pytest_asyncio.fixture()
async def client(probe_app: FastAPI):
    # raise_app_exceptions=False: Starlette's ServerErrorMiddleware re-raises
    # the exception AFTER sending the handler's response (by design, so the
    # server logs see it). We want the response the handler produced.
    transport = ASGITransport(app=probe_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestUnhandledExceptions:
    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_generic_envelope(self, client: AsyncClient, caplog) -> None:
        with caplog.at_level(logging.ERROR, logger="app.gateway.app"):
            resp = await client.get("/boom")

        assert resp.status_code == 500
        payload = resp.json()
        assert payload["success"] is False
        assert payload["data"] is None
        assert payload["error"]["code"] == "INTERNAL_ERROR"
        assert payload["error"]["message"] == "服务器内部错误"

    @pytest.mark.asyncio
    async def test_unhandled_exception_does_not_leak_details(self, client: AsyncClient) -> None:
        resp = await client.get("/boom")
        text = resp.text
        assert "SECRET_INTERNAL_STATE" not in text
        assert "classified" not in text
        assert "/srv/llm/weights" not in text
        assert "RuntimeError" not in text

    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_correlation_id(self, client: AsyncClient) -> None:
        resp = await client.get("/boom")
        request_id = resp.headers.get("X-Request-ID")
        assert request_id
        assert resp.json()["error"]["request_id"] == request_id

    @pytest.mark.asyncio
    async def test_unhandled_exception_logs_full_traceback(self, client: AsyncClient, caplog) -> None:
        with caplog.at_level(logging.ERROR, logger="app.gateway.app"):
            await client.get("/boom")

        assert any("Unhandled exception" in record.message and "request_id=" in record.message for record in caplog.records)


class TestKnownErrorPaths:
    @pytest.mark.asyncio
    async def test_http_exception_keeps_envelope(self, client: AsyncClient) -> None:
        resp = await client.get("/teapot")
        assert resp.status_code == 418
        payload = resp.json()
        assert payload["success"] is False
        assert payload["error"]["message"] == "short and stout"

    @pytest.mark.asyncio
    async def test_api_exception_keeps_envelope(self, client: AsyncClient) -> None:
        resp = await client.get("/api-error")
        assert resp.status_code == 404
        payload = resp.json()
        assert payload["error"]["code"] == "RESOURCE_NOT_FOUND"
        assert payload["error"]["message"] == "resource missing"

    @pytest.mark.asyncio
    async def test_validation_error_is_sanitized(self, client: AsyncClient) -> None:
        resp = await client.post("/validate", json={"name": 123, "extra_field": {"nested": "payload"}})
        assert resp.status_code == 400
        payload = resp.json()
        assert payload["error"]["code"] == "INVALID_REQUEST_BODY"
        # Only the sanitized projection (loc/msg/type) is exposed.
        for issue in payload["error"]["issues"]:
            assert set(issue.keys()) == {"loc", "msg", "type"}
        # The raw pydantic repr (full input payload echo) must not leak.
        assert "extra_field" not in resp.text
        assert "nested" not in resp.text
