from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.gateway.routers.workflows import _legacy_run_payload
from ideer.persistence.models.workflow_legacy import LegacyWorkflowRunRow


def test_legacy_model_keeps_historical_workflow_runs_read_only() -> None:
    assert LegacyWorkflowRunRow.__tablename__ == "workflow_runs"
    assert "workflow_yaml" in LegacyWorkflowRunRow.__table__.columns
    assert "loop_vars" in LegacyWorkflowRunRow.__table__.columns


def test_legacy_run_payload_requires_migration_and_never_advertises_resume() -> None:
    row = LegacyWorkflowRunRow(
        run_id="legacy-1",
        workflow_name="approval",
        workflow_yaml="name: approval",
        status="failed",
        inputs={},
        steps_state={},
        error="workflow_runtime_replaced",
        loop_vars={},
    )

    payload = _legacy_run_payload(row)

    assert payload["migration_required"] is True
    assert payload["error"] == "workflow_runtime_replaced"
    assert "resume" not in payload


@pytest.mark.asyncio
async def test_workflow_event_stream_replays_then_waits_for_new_events() -> None:
    from app.gateway.routers.workflows import workflow_event_stream

    class Store:
        calls = 0

        async def list_events(self, run_id: str, after_seq: int):
            self.calls += 1
            return [SimpleNamespace(seq=after_seq + 1, event_type="node_progress", payload={"node_id": "a"})] if self.calls == 1 else []

        async def get_run(self, run_id: str):
            return SimpleNamespace(status="running")

    stream = workflow_event_stream(Store(), "run-1", 0, poll_seconds=0)
    assert "id: 1" in await anext(stream)
    pending = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    assert not pending.done()
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
