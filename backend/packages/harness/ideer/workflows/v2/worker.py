"""Single-instance durable workflow worker loop."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from ideer.persistence.models.workflow_v2 import WorkflowTaskRow

from .store import WorkflowV2Store

logger = logging.getLogger(__name__)


class WorkflowPaused(Exception):
    """Raised by graph execution after a durable interrupt checkpoint."""


def workflow_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    """Keep the persisted run snapshot JSON-safe across LangGraph versions."""
    snapshot = {key: value for key, value in result.items() if key in {"inputs", "state", "outputs"}}
    interrupts = result.get("__interrupt__")
    if interrupts:
        snapshot["interrupt"] = [getattr(item, "value", item) for item in interrupts]
    return snapshot


class WorkflowWorker:
    def __init__(
        self,
        store: WorkflowV2Store,
        execute: Callable[[WorkflowTaskRow], Awaitable[None]],
        worker_id: str = "workflow-worker",
        *,
        lease_seconds: int = 30,
        heartbeat_seconds: float = 10,
        max_attempts: int = 3,
    ) -> None:
        self.store = store
        self.execute = execute
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.max_attempts = max_attempts

    async def run_once(self) -> bool:
        task = await self.store.claim_next_task(
            self.worker_id,
            lease_seconds=self.lease_seconds,
            max_attempts=self.max_attempts,
        )
        if task is None:
            return False
        lease_lost = asyncio.Event()

        async def heartbeat() -> None:
            while True:
                await asyncio.sleep(self.heartbeat_seconds)
                if not await self.store.renew_lease(
                    task.task_id,
                    self.worker_id,
                    lease_seconds=self.lease_seconds,
                ):
                    lease_lost.set()
                    return

        heartbeat_task = asyncio.create_task(heartbeat())
        try:
            await self.execute(task)
        except WorkflowPaused:
            if not lease_lost.is_set():
                await self.store.finish_task(task.task_id, "paused", None, self.worker_id)
        except Exception as exc:
            logger.exception("workflow task %s failed", task.task_id)
            if not lease_lost.is_set():
                await self.store.finish_task(task.task_id, "failed", str(exc), self.worker_id)
        else:
            if not lease_lost.is_set():
                await self.store.finish_task(task.task_id, "completed", None, self.worker_id)
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        return True

    async def run_forever(self, poll_seconds: float = 1.0) -> None:
        while True:
            if not await self.run_once():
                await asyncio.sleep(poll_seconds)
