from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from ideer.persistence.models.workflow_v2 import WorkflowCommandRow, WorkflowDefinitionVersionRow, WorkflowV2RunRow
from ideer.workflows.v2.store import WorkflowV2Store


class _Context:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_append_event_uses_run_local_monotonic_sequence() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = 3
    session.execute.return_value = result
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    event = await store.append_event("run-1", "node_started", {"node_id": "a"})

    assert event.seq == 4
    assert event.event_type == "node_started"
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_run_starts_queued_and_never_embeds_yaml() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    run = await store.create_run("run-1", "approval", 2, {"request": "x"}, "user-1")

    assert isinstance(run, WorkflowV2RunRow)
    assert run.status == "queued"
    assert run.definition_version == 2
    assert not hasattr(run, "workflow_yaml")
    session.add.assert_called()


@pytest.mark.asyncio
async def test_save_definition_creates_an_immutable_version() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = 2
    session.execute.return_value = result
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    version = await store.save_definition("approval", {"schema_version": 2}, "hash", "user-1")

    assert isinstance(version, WorkflowDefinitionVersionRow)
    assert version.version == 3
    assert version.definition == {"schema_version": 2}


@pytest.mark.asyncio
async def test_worker_claim_ignores_terminal_tasks() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    assert await store.claim_next_task("worker-1") is None


@pytest.mark.asyncio
async def test_command_id_cannot_be_reused_for_another_run() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    existing = WorkflowCommandRow(command_id="cmd-1", run_id="run-other", command_type="cancel", payload={}, created_by="u")
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    session.execute.return_value = result
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    with pytest.raises(ValueError, match="already belongs to run-other"):
        await store.submit_command("cmd-1", "run-1", "resume", {}, "u")


@pytest.mark.asyncio
async def test_reusing_command_id_for_same_run_is_idempotent() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    existing = WorkflowCommandRow(command_id="cmd-1", run_id="run-1", command_type="resume", payload={"approved": True}, created_by="u")
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    session.execute.return_value = result
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    returned = await store.submit_command("cmd-1", "run-1", "resume", {"approved": False}, "other-user")

    assert returned is existing
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_finish_task_transitions_run_and_releases_lease() -> None:
    session = AsyncMock()
    task = MagicMock(task_id="task-1", run_id="run-1", status="running", lease_owner="worker-1")
    run = MagicMock(run_id="run-1", status="running", error=None)
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = task
    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run
    session.execute.side_effect = [task_result, run_result]
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    await store.finish_task("task-1", "failed", "adapter failed")

    assert task.status == "failed"
    assert task.lease_owner is None
    assert run.status == "failed"
    assert run.error == "adapter failed"
    session.commit.assert_awaited_once()


def test_workflow_tasks_include_an_expiring_lease() -> None:
    from ideer.persistence.models.workflow_v2 import WorkflowTaskRow

    assert "lease_expires_at" in WorkflowTaskRow.__table__.columns


@pytest.mark.asyncio
async def test_renew_lease_rejects_an_expired_or_foreign_holder() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 0
    session.execute.return_value = result
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    renewed = await store.renew_lease(
        "task-1",
        "worker-1",
        now=datetime.now(UTC),
        lease_seconds=30,
    )

    assert renewed is False
    session.commit.assert_not_awaited()
