from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ideer.workflows.v2.worker import WorkflowWorker


@pytest.mark.asyncio
async def test_worker_renews_lease_while_executing() -> None:
    store = MagicMock()
    task = MagicMock(task_id="task-1")
    store.claim_next_task = AsyncMock(return_value=task)
    store.renew_lease = AsyncMock(return_value=True)
    store.finish_task = AsyncMock(return_value=True)
    started = asyncio.Event()
    release = asyncio.Event()

    async def execute(_task) -> None:
        started.set()
        await release.wait()

    worker = WorkflowWorker(store, execute, worker_id="worker-1", heartbeat_seconds=0.01)
    running = asyncio.create_task(worker.run_once())
    await started.wait()
    await asyncio.sleep(0.02)
    release.set()
    assert await running is True

    store.renew_lease.assert_awaited_with("task-1", "worker-1", lease_seconds=30)
    store.finish_task.assert_awaited_with("task-1", "completed", None, "worker-1")


@pytest.mark.asyncio
async def test_worker_aborts_execution_when_lease_is_lost() -> None:
    store = MagicMock()
    task = MagicMock(task_id="task-1")
    store.claim_next_task = AsyncMock(return_value=task)
    store.renew_lease = AsyncMock(return_value=False)
    store.finish_task = AsyncMock(return_value=True)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def execute(_task) -> None:
        started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    worker = WorkflowWorker(store, execute, worker_id="worker-1", heartbeat_seconds=0.01)
    assert await worker.run_once() is True

    assert cancelled.is_set()
    store.finish_task.assert_not_awaited()
