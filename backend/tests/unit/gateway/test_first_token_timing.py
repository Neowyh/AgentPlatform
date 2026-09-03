"""First-token timing logs (T1): gateway stages emit one timing record each."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_auth_stage_emits_timing(caplog):
    """AuthMiddleware logs stage=auth timing on an authenticated request."""
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    from app.gateway.auth_middleware import AuthMiddleware
    from app.gateway.internal_auth import create_internal_auth_headers

    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.post("/api/threads/abc/runs/stream")
    async def stream():
        return {"ok": True}

    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger="app.gateway.auth_middleware"):
        res = client.post(
            "/api/threads/abc/runs/stream",
            headers=create_internal_auth_headers(),
        )
    assert res.status_code == 200
    assert any("first_token_timing" in message and "stage=auth" in message for message in caplog.messages)


@pytest.mark.asyncio
async def test_snapshot_stage_emits_timing(caplog):
    """prepare_run logs stage=snapshot timing around the canonical freeze."""
    from app.gateway import run_preparation as prep

    body = SimpleNamespace(
        assistant_id="11111111-1111-1111-1111-111111111111",
        context={"is_bootstrap": True},
        metadata=None,
    )
    request = MagicMock()
    with (
        patch.object(prep, "_prepare_canonical_agent_run", new=AsyncMock(return_value=MagicMock())),
        patch.object(prep, "_canonical_selection_metadata", new=AsyncMock(return_value={})),
        caplog.at_level(logging.INFO, logger="app.gateway.run_preparation"),
    ):
        prepared = await prep.prepare_run(body, "thread-1", request)
    assert prepared.canonical_run_id is not None
    assert any("first_token_timing" in message and "stage=snapshot" in message for message in caplog.messages)
