"""T2: thread upsert leaves the pre-token path — start_run returns first."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_deps(release: asyncio.Event, get_side_effect=None):
    bridge = MagicMock()
    bridge.subscribe = MagicMock()

    run_mgr = MagicMock()
    run_mgr.create_or_reject = AsyncMock()
    run_mgr.cancel = AsyncMock()

    async def _blocked_get(thread_id):
        if get_side_effect is not None:
            raise get_side_effect
        await release.wait()
        return None

    run_ctx = MagicMock()
    run_ctx.thread_store = MagicMock()
    run_ctx.thread_store.get = AsyncMock(side_effect=_blocked_get)
    run_ctx.thread_store.create = AsyncMock()
    run_ctx.thread_store.update_status = AsyncMock()

    request = MagicMock()
    request.state = SimpleNamespace(user=SimpleNamespace(id="user-1"))
    request.headers = {}

    return bridge, run_mgr, run_ctx, request


def _body():
    return SimpleNamespace(
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


def _patches(bridge, run_mgr, run_ctx):
    return (
        patch("app.gateway.services.get_stream_bridge", return_value=bridge),
        patch("app.gateway.services.get_run_manager", return_value=run_mgr),
        patch("app.gateway.services.get_run_context", return_value=run_ctx),
        patch("app.gateway.services.resolve_agent_factory"),
        patch("app.gateway.services.run_agent", new_callable=AsyncMock),
        patch("app.gateway.run_preparation.get_app_config"),
    )


@pytest.mark.asyncio
async def test_start_run_returns_before_upsert_completes():
    release = asyncio.Event()
    bridge, run_mgr, run_ctx, request = _mock_deps(release)
    record = MagicMock()
    record.run_id = "run-123"
    record.task = None
    run_mgr.create_or_reject.return_value = record
    patches = _patches(bridge, run_mgr, run_ctx)

    from app.gateway.services import start_run

    with patches[0], patches[1], patches[2], patches[3] as mock_factory, patches[4], patches[5] as mock_app_config:
        mock_factory.return_value = MagicMock()
        mock_app_config.return_value.get_model_config.return_value = None
        task = asyncio.create_task(start_run(_body(), "thread-1", request))
        for _ in range(200):
            await asyncio.sleep(0.01)
            if task.done():
                break
        try:
            assert task.done(), "start_run must return while thread upsert is still blocked"
            assert task.result() is record
            run_ctx.thread_store.create.assert_not_called()
        finally:
            release.set()
        await asyncio.wait_for(task, timeout=5)
        for _ in range(200):
            await asyncio.sleep(0.01)
            if run_ctx.thread_store.create.called:
                break
        run_ctx.thread_store.create.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_failure_does_not_fail_start_run():
    release = asyncio.Event()
    bridge, run_mgr, run_ctx, request = _mock_deps(release, get_side_effect=RuntimeError("db down"))
    record = MagicMock()
    record.run_id = "run-123"
    record.task = None
    run_mgr.create_or_reject.return_value = record
    patches = _patches(bridge, run_mgr, run_ctx)

    from app.gateway.services import start_run

    with patches[0], patches[1], patches[2], patches[3] as mock_factory, patches[4], patches[5] as mock_app_config:
        mock_factory.return_value = MagicMock()
        mock_app_config.return_value.get_model_config.return_value = None
        result = await start_run(_body(), "thread-1", request)
        await asyncio.sleep(0.2)
    assert result is record
    run_ctx.thread_store.create.assert_not_called()
    run_ctx.thread_store.update_status.assert_not_called()
