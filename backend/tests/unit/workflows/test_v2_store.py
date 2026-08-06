from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from ideer.persistence.models.workflow_v2 import WorkflowCommandRow, WorkflowDefinitionVersionRow, WorkflowTaskRow, WorkflowV2RunRow
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
    result.scalar_one_or_none.return_value = 4
    session.execute.return_value = result
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    event = await store.append_event("run-1", "node_started", {"node_id": "a"})

    assert event.seq == 4
    assert event.event_type == "node_started"
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_append_event_reserves_its_sequence_in_the_database() -> None:
    """Concurrent workers must not derive the next sequence from a stale read."""
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = 1
    session.execute.return_value = result
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    await store.append_event("run-1", "node_started", {"node_id": "a"})

    statement = session.execute.await_args_list[0].args[0]
    assert "UPDATE workflow_v2_runs" in str(statement)


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
async def test_create_run_rejects_user_concurrency_limit() -> None:
    session = AsyncMock()
    count = MagicMock()
    count.scalar_one.return_value = 3
    session.execute.return_value = count
    session.add = MagicMock()
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    with pytest.raises(RuntimeError, match="workflow_user_concurrency_exceeded"):
        await store.create_run(
            "run-1",
            "approval",
            2,
            {},
            "user-1",
            department_id="dept-1",
            user_concurrency=3,
            department_concurrency=10,
        )


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
async def test_delete_definition_targets_the_workflow_name() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 3
    session.execute.return_value = result
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    deleted = await store.delete_definition("approval")

    assert deleted == 3
    statement = session.execute.await_args_list[0].args[0]
    assert "DELETE FROM workflow_definition_versions" in str(statement)
    assert "workflow_name" in str(statement)
    assert "approval" in list(statement.compile().params.values())
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_definition_returns_zero_for_unmatched_rows() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 0
    session.execute.return_value = result
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    assert await store.delete_definition("missing") == 0
    session.commit.assert_awaited_once()


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
    session.add = MagicMock()
    leased_task = MagicMock(attempts=2)
    leased_task_result = MagicMock()
    leased_task_result.scalar_one_or_none.return_value = leased_task
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = "run-1"
    session.execute.side_effect = [leased_task_result, task_result, MagicMock()]
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    assert await store.finish_task("task-1", "failed", "adapter failed", "worker-1") is True

    assert session.execute.await_count == 3
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_resume_command_revives_failed_task() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    task = MagicMock(spec=WorkflowTaskRow, status="failed", attempts=3, run_id="run-1", cancel_requested=False)
    run = MagicMock(spec=WorkflowV2RunRow, run_id="run-1", status="failed", error="workflow_max_attempts_exceeded")
    command_result = MagicMock()
    command_result.scalar_one_or_none.return_value = None
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = task
    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run
    session.execute.side_effect = [command_result, task_result, run_result]
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    await store.submit_command("cmd-1", "run-1", "resume", {}, "u")

    assert task.status == "queued"
    assert task.attempts == 0
    assert task.resume_command_id == "cmd-1"
    assert run.status == "queued"
    assert run.error is None
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_resume_command_does_not_reset_attempts_for_paused_task() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    task = MagicMock(spec=WorkflowTaskRow, status="paused", attempts=1, run_id="run-1", cancel_requested=False)
    run = MagicMock(spec=WorkflowV2RunRow, run_id="run-1", status="paused", error=None)
    command_result = MagicMock()
    command_result.scalar_one_or_none.return_value = None
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = task
    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run
    session.execute.side_effect = [command_result, task_result, run_result]
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    await store.submit_command("cmd-1", "run-1", "resume", {}, "u")

    assert task.status == "queued"
    assert task.attempts == 1
    assert run.status == "queued"
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


@pytest.mark.asyncio
async def test_stale_worker_cannot_persist_snapshot_after_lease_takeover() -> None:
    """A worker that no longer owns the lease must not overwrite recovery state."""
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 0
    session.execute.return_value = result
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    persisted = await store.update_snapshot(
        "run-1",
        {"outputs": {"old": "value"}},
        worker_id="worker-1",
    )

    assert persisted is False
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_finish_task_uses_compare_and_set_lease_ownership() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    leased_task = MagicMock(attempts=1)
    leased_task_result = MagicMock()
    leased_task_result.scalar_one_or_none.return_value = leased_task
    result = MagicMock()
    result.scalar_one_or_none.return_value = "run-1"
    session.execute.side_effect = [leased_task_result, result, MagicMock()]
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    await store.finish_task("task-1", "completed", None, "worker-1")

    statement = session.execute.await_args_list[1].args[0]
    assert "UPDATE workflow_tasks" in str(statement)


@pytest.mark.asyncio
async def test_fresh_claim_increments_attempts() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    task = MagicMock(
        spec=WorkflowTaskRow,
        task_id="task-1",
        run_id="run-1",
        status="queued",
        attempts=2,
        lease_owner=None,
        resume_command_id=None,
        cancel_requested=False,
    )
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = task
    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = MagicMock(spec=WorkflowV2RunRow, run_id="run-1", status="queued")

    def execute_stub(statement, *args, **kwargs):
        if "workflow_v2_runs" in str(statement):
            return run_result
        return task_result

    session.execute.side_effect = execute_stub
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    claimed = await store.claim_next_task("worker-1", max_attempts=3)

    assert claimed is task
    assert task.attempts == 3
    task_result.delete.assert_not_called()


@pytest.mark.asyncio
async def test_resumed_task_claim_does_not_increment_attempts() -> None:
    """The immediate execution of an operator resume is free: it never consumes
    the attempt budget, so pausing again cannot exhaust max_attempts."""
    session = AsyncMock()
    session.add = MagicMock()
    task = MagicMock(
        spec=WorkflowTaskRow,
        task_id="task-1",
        run_id="run-1",
        status="queued",
        attempts=3,
        lease_owner=None,
        resume_command_id="cmd-1",
        cancel_requested=False,
    )
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = task
    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = MagicMock(spec=WorkflowV2RunRow, run_id="run-1", status="queued")

    def execute_stub(statement, *args, **kwargs):
        if "workflow_v2_runs" in str(statement):
            return run_result
        return task_result

    session.execute.side_effect = execute_stub
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    claimed = await store.claim_next_task("worker-1", max_attempts=3)

    assert claimed is task
    assert task.attempts == 3
    assert task.resume_command_id == "cmd-1"


@pytest.mark.asyncio
async def test_resume_exemption_is_bounded_to_the_pending_resume_command() -> None:
    """The attempt exemption only lasts as long as the resume command is
    pending. After the worker consumes it (clear_resume_command), the next
    claim must count an attempt again, so a second pause cannot burn the
    budget for free."""
    session = AsyncMock()
    session.add = MagicMock()
    task = MagicMock(
        spec=WorkflowTaskRow,
        task_id="task-1",
        run_id="run-1",
        status="queued",
        attempts=3,
        lease_owner=None,
        resume_command_id="cmd-1",
        cancel_requested=False,
    )
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = task
    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = MagicMock(spec=WorkflowV2RunRow, run_id="run-1", status="queued")

    def execute_stub(statement, *args, **kwargs):
        if "workflow_v2_runs" in str(statement):
            return run_result
        return task_result

    session.execute.side_effect = execute_stub
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    claimed = await store.claim_next_task("worker-1", max_attempts=5)
    assert claimed is task
    assert task.attempts == 3, "the pending resume command must exempt the claim"

    # The production worker consumes the command right after the resume
    # execution starts (workflow_process.py clears resume_command_id).
    task.resume_command_id = None
    session.execute.side_effect = execute_stub

    claimed_again = await store.claim_next_task("worker-1", max_attempts=5)
    assert claimed_again is task
    assert task.attempts == 4, "after the command is consumed the budget resumes"


@pytest.mark.asyncio
async def test_max_attempts_kill_persists_failure_and_notifies_sink() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    task = MagicMock(
        spec=WorkflowTaskRow,
        task_id="task-1",
        run_id="run-1",
        status="queued",
        attempts=3,
        lease_owner=None,
        resume_command_id=None,
        cancel_requested=False,
    )
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = task
    run = MagicMock(spec=WorkflowV2RunRow, run_id="run-1", status="queued", event_seq=4)
    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run

    def execute_stub(statement, *args, **kwargs):
        if "workflow_v2_runs" in str(statement):
            return run_result
        return task_result

    session.execute.side_effect = execute_stub
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))
    notified: list[tuple[str, str]] = []

    async def sink(run_row, event_row):
        notified.append((run_row.run_id, event_row.event_type))

    store.event_sink = sink

    assert await store.claim_next_task("worker-1", max_attempts=3) is None

    assert task.status == "failed"
    assert run.status == "failed"
    assert run.error == "workflow_max_attempts_exceeded"
    assert notified == [("run-1", "run_failed")]
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_clear_resume_command_consumes_the_intent() -> None:
    session = AsyncMock()
    session.execute.return_value = MagicMock()
    store = WorkflowV2Store(MagicMock(return_value=_Context(session)))

    await store.clear_resume_command("task-1")

    statement = session.execute.await_args.args[0]
    assert "UPDATE workflow_tasks" in str(statement)
    session.commit.assert_awaited_once()
