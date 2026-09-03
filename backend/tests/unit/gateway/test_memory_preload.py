"""T5: prepare_run preloads Memory into the storage cache off the token path."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _canonical_body():
    return SimpleNamespace(
        assistant_id="11111111-1111-1111-1111-111111111111",
        context={"is_bootstrap": True},
        metadata=None,
    )


def _authed_request(user_id: str = "user-1") -> MagicMock:
    request = MagicMock()
    request.state.user = SimpleNamespace(id=user_id)
    return request


@pytest.mark.asyncio
async def test_prepare_spawns_memory_preload_for_canonical_key():
    from app.gateway import run_preparation as prep

    seen: dict = {}

    def fake_get_memory_data(agent_name, *, user_id=None):
        seen["agent_name"] = agent_name
        seen["user_id"] = user_id
        return {}

    app_config = MagicMock()
    app_config.memory.enabled = True
    app_config.memory.injection_enabled = True
    with (
        patch.object(prep, "_prepare_canonical_agent_run", new=AsyncMock(return_value=MagicMock())),
        patch.object(prep, "_canonical_selection_metadata", new=AsyncMock(return_value={})),
        patch.object(prep, "get_app_config", return_value=app_config),
        patch.object(prep, "get_memory_data", side_effect=fake_get_memory_data),
    ):
        prepared = await prep.prepare_run(_canonical_body(), "thread-1", _authed_request())
        assert prepared.memory_preload_task is not None
        await asyncio.wait_for(prepared.memory_preload_task, timeout=5)
    assert seen == {"agent_name": "11111111-1111-1111-1111-111111111111", "user_id": "user-1"}


@pytest.mark.asyncio
async def test_preload_skipped_when_injection_disabled():
    from app.gateway import run_preparation as prep

    app_config = MagicMock()
    app_config.memory.enabled = True
    app_config.memory.injection_enabled = False
    with (
        patch.object(prep, "_prepare_canonical_agent_run", new=AsyncMock(return_value=MagicMock())),
        patch.object(prep, "_canonical_selection_metadata", new=AsyncMock(return_value={})),
        patch.object(prep, "get_app_config", return_value=app_config),
        patch.object(prep, "get_memory_data") as mock_warm,
    ):
        prepared = await prep.prepare_run(_canonical_body(), "thread-1", _authed_request())
    assert prepared.memory_preload_task is None
    mock_warm.assert_not_called()


@pytest.mark.asyncio
async def test_preload_failure_does_not_fail_start_run():
    from app.gateway.services import start_run

    bridge = MagicMock()
    bridge.subscribe = MagicMock()
    run_mgr = MagicMock()
    run_mgr.create_or_reject = AsyncMock()
    run_ctx = MagicMock()
    run_ctx.thread_store = MagicMock()
    run_ctx.thread_store.get = AsyncMock(return_value=None)
    run_ctx.thread_store.create = AsyncMock()
    run_ctx.thread_store.update_status = AsyncMock()
    request = MagicMock()
    request.state = SimpleNamespace(user=SimpleNamespace(id="user-1"))
    request.headers = {}
    record = MagicMock()
    record.run_id = "run-123"
    record.task = None
    run_mgr.create_or_reject.return_value = record
    body = SimpleNamespace(
        assistant_id="lead_agent",
        on_disconnect="cancel",
        input={"messages": [{"role": "user", "content": "hi"}]},
        config=None,
        metadata=None,
        multitask_strategy="reject",
        stream_mode=None,
        stream_subgraphs=False,
        interrupt_before=None,
        interrupt_after=None,
        context=None,
    )

    async def _boom():
        raise RuntimeError("disk on fire")

    warmer = asyncio.ensure_future(_boom())
    prepared = SimpleNamespace(
        body_context={},
        canonical_run_id=None,
        canonical_factory=None,
        model_name=None,
        run_metadata={},
        memory_preload_task=warmer,
    )
    with (
        patch("app.gateway.services.get_stream_bridge", return_value=bridge),
        patch("app.gateway.services.get_run_manager", return_value=run_mgr),
        patch("app.gateway.services.get_run_context", return_value=run_ctx),
        patch("app.gateway.services.resolve_agent_factory") as mock_factory,
        patch("app.gateway.services.run_agent", new_callable=AsyncMock),
        patch("app.gateway.run_preparation.prepare_run", new=AsyncMock(return_value=prepared)),
        patch("app.gateway.run_preparation.get_app_config") as mock_app_config,
    ):
        mock_factory.return_value = MagicMock()
        mock_app_config.return_value.get_model_config.return_value = None
        result = await start_run(body, "thread-1", request)
        await asyncio.sleep(0.2)
    assert result is record
