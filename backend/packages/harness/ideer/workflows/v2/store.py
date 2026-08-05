"""Persistence boundary for workflow v2 lifecycle data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy import delete as sql_delete

from ideer.persistence.models.workflow_v2 import (
    WorkflowCommandRow,
    WorkflowDefinitionVersionRow,
    WorkflowLeaseAuditRow,
    WorkflowTaskRow,
    WorkflowV2EventRow,
    WorkflowV2RunRow,
)


class WorkflowV2Store:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def save_definition(self, workflow_name: str, definition: dict, content_hash: str, created_by: str) -> WorkflowDefinitionVersionRow:
        async with self.session_factory() as session:
            result = await session.execute(select(func.coalesce(func.max(WorkflowDefinitionVersionRow.version), 0)).where(WorkflowDefinitionVersionRow.workflow_name == workflow_name))
            version = WorkflowDefinitionVersionRow(
                id=str(uuid4()),
                workflow_name=workflow_name,
                version=result.scalar_one() + 1,
                definition=definition,
                content_hash=content_hash,
                created_by=created_by,
            )
            session.add(version)
            await session.commit()
            return version

    async def get_definition(self, workflow_name: str, version: int) -> WorkflowDefinitionVersionRow | None:
        async with self.session_factory() as session:
            return (await session.execute(select(WorkflowDefinitionVersionRow).where(WorkflowDefinitionVersionRow.workflow_name == workflow_name, WorkflowDefinitionVersionRow.version == version))).scalar_one_or_none()

    async def get_latest_definition(self, workflow_name: str) -> WorkflowDefinitionVersionRow | None:
        async with self.session_factory() as session:
            result = await session.execute(select(WorkflowDefinitionVersionRow).where(WorkflowDefinitionVersionRow.workflow_name == workflow_name).order_by(WorkflowDefinitionVersionRow.version.desc()).limit(1))
            return result.scalar_one_or_none()

    async def list_latest_definitions(self, limit: int = 100, offset: int = 0) -> tuple[list[WorkflowDefinitionVersionRow], int]:
        async with self.session_factory() as session:
            result = await session.execute(select(WorkflowDefinitionVersionRow).order_by(WorkflowDefinitionVersionRow.workflow_name, WorkflowDefinitionVersionRow.version.desc()))
            latest: dict[str, WorkflowDefinitionVersionRow] = {}
            for row in result.scalars().all():
                latest.setdefault(row.workflow_name, row)
            values = list(latest.values())
            return values[offset : offset + limit], len(values)

    async def delete_definition(self, workflow_name: str) -> int:
        """Hard-delete every definition version of a workflow.

        Run rows referencing the workflow are intentionally retained so
        historical run data survives a deletion; only the definition versions
        are removed. Returns the number of rows deleted.
        """
        async with self.session_factory() as session:
            result = await session.execute(sql_delete(WorkflowDefinitionVersionRow).where(WorkflowDefinitionVersionRow.workflow_name == workflow_name))
            await session.commit()
            return result.rowcount or 0

    async def create_run(
        self,
        run_id: str,
        workflow_name: str,
        definition_version: int,
        inputs: dict,
        created_by: str,
        *,
        department_id: str | None = None,
        user_concurrency: int | None = None,
        department_concurrency: int | None = None,
    ) -> WorkflowV2RunRow:
        run = WorkflowV2RunRow(
            run_id=run_id,
            workflow_name=workflow_name,
            definition_version=definition_version,
            checkpoint_thread_id=f"wf-{run_id}",
            status="queued",
            inputs=inputs,
            snapshot={},
            created_by=created_by,
            department_id=department_id,
        )
        task = WorkflowTaskRow(task_id=str(uuid4()), run_id=run_id, status="queued", attempts=0, cancel_requested=False)
        async with self.session_factory() as session:
            active = ("queued", "running", "paused")
            if user_concurrency is not None:
                user_count = (
                    await session.execute(
                        select(func.count())
                        .select_from(WorkflowV2RunRow)
                        .where(
                            WorkflowV2RunRow.created_by == created_by,
                            WorkflowV2RunRow.status.in_(active),
                        )
                    )
                ).scalar_one()
                if user_count >= user_concurrency:
                    raise RuntimeError("workflow_user_concurrency_exceeded")
            if department_id is not None and department_concurrency is not None:
                department_count = (
                    await session.execute(
                        select(func.count())
                        .select_from(WorkflowV2RunRow)
                        .where(
                            WorkflowV2RunRow.department_id == department_id,
                            WorkflowV2RunRow.status.in_(active),
                        )
                    )
                ).scalar_one()
                if department_count >= department_concurrency:
                    raise RuntimeError("workflow_department_concurrency_exceeded")
            session.add(run)
            # Flush before inserting the task: with SQLite foreign keys enabled
            # (production engine), the task row must reference an already
            # persisted run row. Relying on flush ordering alone is fragile.
            await session.flush()
            session.add(task)
            await session.commit()
        return run

    async def append_event(
        self,
        run_id: str,
        event_type: str,
        payload: dict,
        *,
        worker_id: str | None = None,
        max_events: int | None = None,
    ) -> WorkflowV2EventRow | None:
        async with self.session_factory() as session:
            ownership = ()
            if worker_id is not None:
                ownership = (
                    select(WorkflowTaskRow.task_id)
                    .where(
                        WorkflowTaskRow.run_id == run_id,
                        WorkflowTaskRow.status == "running",
                        WorkflowTaskRow.lease_owner == worker_id,
                        WorkflowTaskRow.lease_expires_at > datetime.now(UTC),
                    )
                    .exists(),
                )
            limits = () if max_events is None else (WorkflowV2RunRow.event_seq < max_events,)
            result = await session.execute(update(WorkflowV2RunRow).where(WorkflowV2RunRow.run_id == run_id, *ownership, *limits).values(event_seq=WorkflowV2RunRow.event_seq + 1).returning(WorkflowV2RunRow.event_seq))
            sequence = result.scalar_one_or_none()
            if sequence is None:
                return None
            event = WorkflowV2EventRow(
                id=str(uuid4()),
                run_id=run_id,
                seq=sequence,
                event_type=event_type,
                payload=payload,
            )
            session.add(event)
            await session.commit()
            return event

    async def get_run(self, run_id: str) -> WorkflowV2RunRow | None:
        async with self.session_factory() as session:
            return (await session.execute(select(WorkflowV2RunRow).where(WorkflowV2RunRow.run_id == run_id))).scalar_one_or_none()

    async def list_runs(
        self,
        workflow_name: str,
        limit: int = 50,
        offset: int = 0,
        *,
        created_by: str | None = None,
    ) -> tuple[list[WorkflowV2RunRow], int]:
        async with self.session_factory() as session:
            query = select(WorkflowV2RunRow).where(WorkflowV2RunRow.workflow_name == workflow_name)
            if created_by is not None:
                query = query.where(WorkflowV2RunRow.created_by == created_by)
            query = query.order_by(WorkflowV2RunRow.created_at.desc())
            rows = list((await session.execute(query)).scalars().all())
            return rows[offset : offset + limit], len(rows)

    async def update_snapshot(self, run_id: str, snapshot: dict, *, worker_id: str) -> bool:
        """Persist recovery state only while the caller still owns its lease."""
        async with self.session_factory() as session:
            now = datetime.now(UTC)
            owned_task = select(WorkflowTaskRow.task_id).where(
                WorkflowTaskRow.run_id == run_id,
                WorkflowTaskRow.status == "running",
                WorkflowTaskRow.lease_owner == worker_id,
                WorkflowTaskRow.lease_expires_at > now,
            )
            result = await session.execute(update(WorkflowV2RunRow).where(WorkflowV2RunRow.run_id == run_id, owned_task.exists()).values(snapshot=snapshot))
            if result.rowcount != 1:
                return False
            await session.commit()
            return True

    async def consume_cancel_request(self, run_id: str) -> bool:
        async with self.session_factory() as session:
            task = (await session.execute(select(WorkflowTaskRow).where(WorkflowTaskRow.run_id == run_id))).scalar_one_or_none()
            if task is None or not task.cancel_requested:
                return False
            task.cancel_requested = False
            task.status = "cancelled"
            run = (await session.execute(select(WorkflowV2RunRow).where(WorkflowV2RunRow.run_id == run_id))).scalar_one_or_none()
            if run is not None:
                run.status = "cancelled"
            await session.commit()
            return True

    async def is_cancel_requested(self, run_id: str) -> bool:
        async with self.session_factory() as session:
            task = (await session.execute(select(WorkflowTaskRow).where(WorkflowTaskRow.run_id == run_id))).scalar_one_or_none()
            return bool(task is not None and task.cancel_requested)

    async def list_events(self, run_id: str, after_seq: int = 0) -> list[WorkflowV2EventRow]:
        async with self.session_factory() as session:
            result = await session.execute(select(WorkflowV2EventRow).where(WorkflowV2EventRow.run_id == run_id, WorkflowV2EventRow.seq > after_seq).order_by(WorkflowV2EventRow.seq))
            return list(result.scalars().all())

    async def submit_command(self, command_id: str, run_id: str, command_type: str, payload: dict, created_by: str) -> WorkflowCommandRow:
        async with self.session_factory() as session:
            existing = (await session.execute(select(WorkflowCommandRow).where(WorkflowCommandRow.command_id == command_id))).scalar_one_or_none()
            if existing is not None:
                if existing.run_id != run_id:
                    raise ValueError(f"command_id '{command_id}' already belongs to {existing.run_id}")
                return existing
            command = WorkflowCommandRow(command_id=command_id, run_id=run_id, command_type=command_type, payload=payload, created_by=created_by)
            session.add(command)
            task = (await session.execute(select(WorkflowTaskRow).where(WorkflowTaskRow.run_id == run_id))).scalar_one_or_none()
            run = (await session.execute(select(WorkflowV2RunRow).where(WorkflowV2RunRow.run_id == run_id))).scalar_one_or_none()
            if task is not None and run is not None:
                if command_type == "resume" and task.status in {"paused", "failed"}:
                    was_failed = task.status == "failed"
                    task.status = "queued"
                    task.resume_command_id = command.command_id
                    if was_failed:
                        # a failed run is revived from its last checkpoint: reset
                        # attempts (a max_attempts kill would otherwise re-trigger
                        # immediately) and clear the recorded error
                        task.attempts = 0
                    run.status = "queued"
                    run.error = None
                elif command_type == "cancel" and task.status in {"queued", "paused"}:
                    task.status = "cancelled"
                    run.status = "cancelled"
                elif command_type == "cancel" and task.status == "running":
                    task.cancel_requested = True
            await session.commit()
            return command

    async def latest_command(self, run_id: str, command_type: str) -> WorkflowCommandRow | None:
        async with self.session_factory() as session:
            result = await session.execute(select(WorkflowCommandRow).where(WorkflowCommandRow.run_id == run_id, WorkflowCommandRow.command_type == command_type).order_by(WorkflowCommandRow.created_at.desc()).limit(1))
            return result.scalar_one_or_none()

    async def get_command(self, command_id: str) -> WorkflowCommandRow | None:
        async with self.session_factory() as session:
            return (await session.execute(select(WorkflowCommandRow).where(WorkflowCommandRow.command_id == command_id))).scalar_one_or_none()

    async def claim_next_task(
        self,
        worker_id: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 30,
        max_attempts: int = 3,
    ) -> WorkflowTaskRow | None:
        now = now or datetime.now(UTC)
        async with self.session_factory() as session:
            task = (
                await session.execute(
                    select(WorkflowTaskRow)
                    .where(
                        or_(
                            WorkflowTaskRow.status == "queued",
                            and_(WorkflowTaskRow.status == "running", WorkflowTaskRow.lease_expires_at < now),
                        )
                    )
                    .order_by(WorkflowTaskRow.task_id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if task is None:
                return None
            if task.attempts >= max_attempts:
                task.status = "failed"
                task.lease_owner = None
                task.lease_expires_at = None
                run = (await session.execute(select(WorkflowV2RunRow).where(WorkflowV2RunRow.run_id == task.run_id))).scalar_one_or_none()
                if run is not None:
                    run.status = "failed"
                    run.error = "workflow_max_attempts_exceeded"
                    run.event_seq += 1
                    session.add(
                        WorkflowV2EventRow(
                            id=str(uuid4()),
                            run_id=run.run_id,
                            seq=run.event_seq,
                            event_type="run_failed",
                            payload={"error": "workflow_max_attempts_exceeded"},
                        )
                    )
                await session.commit()
                return None
            previous_owner = task.lease_owner
            task.status = "running"
            task.lease_owner = worker_id
            task.lease_expires_at = now + timedelta(seconds=lease_seconds)
            task.heartbeat_at = now
            task.attempts += 1
            run = (await session.execute(select(WorkflowV2RunRow).where(WorkflowV2RunRow.run_id == task.run_id))).scalar_one_or_none()
            if run is not None:
                run.status = "running"
            session.add(
                WorkflowLeaseAuditRow(
                    id=str(uuid4()),
                    run_id=task.run_id,
                    task_id=task.task_id,
                    event_type="taken_over" if previous_owner else "claimed",
                    worker_id=worker_id,
                    attempt=task.attempts,
                )
            )
            await session.commit()
            return task

    async def renew_lease(
        self,
        task_id: str,
        worker_id: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 30,
    ) -> bool:
        now = now or datetime.now(UTC)
        async with self.session_factory() as session:
            result = await session.execute(
                update(WorkflowTaskRow)
                .where(
                    WorkflowTaskRow.task_id == task_id,
                    WorkflowTaskRow.status == "running",
                    WorkflowTaskRow.lease_owner == worker_id,
                    WorkflowTaskRow.lease_expires_at > now,
                )
                .values(heartbeat_at=now, lease_expires_at=now + timedelta(seconds=lease_seconds))
            )
            if result.rowcount != 1:
                return False
            await session.commit()
            return True

    async def finish_task(self, task_id: str, status: str, error: str | None, worker_id: str) -> bool:
        """Atomically finalize only the task still leased to ``worker_id``."""
        async with self.session_factory() as session:
            now = datetime.now(UTC)
            task = (await session.execute(select(WorkflowTaskRow).where(WorkflowTaskRow.task_id == task_id))).scalar_one_or_none()
            if task is None:
                return False
            result = await session.execute(
                update(WorkflowTaskRow)
                .where(
                    WorkflowTaskRow.task_id == task_id,
                    WorkflowTaskRow.status == "running",
                    WorkflowTaskRow.lease_owner == worker_id,
                    WorkflowTaskRow.lease_expires_at > now,
                )
                .values(status=status, lease_owner=None, lease_expires_at=None)
                .returning(WorkflowTaskRow.run_id)
                .execution_options(synchronize_session=False)
            )
            run_id = result.scalar_one_or_none()
            if run_id is None:
                return False
            await session.execute(update(WorkflowV2RunRow).where(WorkflowV2RunRow.run_id == run_id).values(status=status, error=error))
            session.add(
                WorkflowLeaseAuditRow(
                    id=str(uuid4()),
                    run_id=run_id,
                    task_id=task_id,
                    event_type="released",
                    worker_id=worker_id,
                    attempt=task.attempts,
                )
            )
            await session.commit()
            return True
