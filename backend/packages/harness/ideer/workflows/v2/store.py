"""Persistence boundary for workflow v2 lifecycle data."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy import delete as sql_delete
from sqlalchemy.exc import OperationalError

from ideer.persistence.models.workflow_v2 import (
    WorkflowCommandRow,
    WorkflowDefinitionVersionRow,
    WorkflowLeaseAuditRow,
    WorkflowTaskRow,
    WorkflowV2EventRow,
    WorkflowV2RunRow,
)

logger = logging.getLogger(__name__)


def _validated_canonical_inputs(definition: dict, submitted: dict, run_id: str, user_id: str) -> dict:
    """Validate one frozen Workflow definition before its Run becomes claimable."""

    from ideer.workflows.v2.errors import WorkflowInvalidRootsError, WorkflowMissingInputRootsError
    from ideer.workflows.v2.file_roots import (
        make_host_resolver,
        validate_read_roots,
        validate_workflow_roots,
    )
    from ideer.workflows.v2.schema import WorkflowV2

    workflow = WorkflowV2.model_validate(definition)
    inputs = dict(submitted)
    expected_types = {
        "string": lambda value: isinstance(value, str),
        "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": lambda value: isinstance(value, bool),
        "object": lambda value: isinstance(value, dict),
        "array": lambda value: isinstance(value, list),
    }
    for name, parameter in workflow.inputs.items():
        if name not in inputs:
            if parameter.default is not None:
                inputs[name] = parameter.default
            elif parameter.required:
                raise ValueError(f"Missing required input: '{name}'")
            continue
        if not expected_types[parameter.type](inputs[name]):
            raise ValueError(f"Input '{name}' expects {parameter.type}, got {type(inputs[name]).__name__}")

    invalid_roots = validate_workflow_roots(workflow.nodes, inputs)
    if invalid_roots:
        raise WorkflowInvalidRootsError(invalid_roots)
    missing_roots = validate_read_roots(
        workflow.nodes,
        inputs,
        make_host_resolver(run_id, user_id),
    )
    if missing_roots:
        raise WorkflowMissingInputRootsError(missing_roots)
    return inputs


class WorkflowV2Store:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        # Serializes event appends: parallel fork branches emit concurrently,
        # and a cancelled branch must never leave an open write transaction
        # behind (SQLite would then block every later writer until the busy
        # timeout).  One lock per store instance is enough — a worker runs one
        # run at a time, so only intra-run fork branches contend.
        self._event_append_lock = asyncio.Lock()
        # Optional sink invoked after every persisted event (including the
        # max_attempts exhaustion event written inside claim_next_task), so the
        # worker can stream a run record to disk. Sink failures are logged and
        # never fail the run itself.
        self.event_sink: Callable[[WorkflowV2RunRow, WorkflowV2EventRow], Awaitable[None]] | None = None

    async def _notify_sink(self, run_id: str, event: WorkflowV2EventRow | None = None) -> None:
        if self.event_sink is None:
            return
        try:
            run = await self.get_run(run_id)
            if run is not None:
                await self.event_sink(run, event)
        except Exception:
            logger.exception("workflow event sink failed for run %s", run_id)

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

    async def create_canonical_run(
        self,
        run_id: str,
        workflow_resource_id: str,
        inputs: dict,
        actor,
        *,
        model_name: str | None = None,
        user_concurrency: int | None = None,
        department_concurrency: int | None = None,
    ) -> WorkflowV2RunRow:
        """Freeze a canonical dependency closure before making the Run claimable."""

        from ideer.persistence.models.resource_catalog import Resource, ResourceVersion
        from ideer.resources.service import ResourceConflict, ResourceService

        async with self.session_factory() as session:
            service = ResourceService(session, actor)
            snapshots = await service.create_run_snapshot(run_id, workflow_resource_id)
            resource = await session.get(Resource, workflow_resource_id)
            if resource is None or resource.type != "workflow":
                raise ResourceConflict(f"Resource {workflow_resource_id} is not a Workflow")
            root_snapshot = next(
                (snapshot for snapshot in snapshots if snapshot.resource_id == workflow_resource_id),
                None,
            )
            if root_snapshot is None:
                raise ResourceConflict("Canonical Workflow snapshot is missing its root")
            version = (
                await session.execute(
                    select(ResourceVersion).where(
                        ResourceVersion.resource_id == workflow_resource_id,
                        ResourceVersion.version == root_snapshot.version,
                    )
                )
            ).scalar_one()
            if not isinstance(version.content, dict):
                raise ResourceConflict("Canonical Workflow version has no definition content")
            inputs = _validated_canonical_inputs(
                version.content,
                inputs,
                run_id,
                actor.user_id,
            )

            active = ("queued", "running", "paused")
            if user_concurrency is not None:
                user_count = (
                    await session.execute(
                        select(func.count())
                        .select_from(WorkflowV2RunRow)
                        .where(
                            WorkflowV2RunRow.created_by == actor.user_id,
                            WorkflowV2RunRow.status.in_(active),
                        )
                    )
                ).scalar_one()
                if user_count >= user_concurrency:
                    raise RuntimeError("workflow_user_concurrency_exceeded")
            if actor.department_id is not None and department_concurrency is not None:
                department_count = (
                    await session.execute(
                        select(func.count())
                        .select_from(WorkflowV2RunRow)
                        .where(
                            WorkflowV2RunRow.department_id == actor.department_id,
                            WorkflowV2RunRow.status.in_(active),
                        )
                    )
                ).scalar_one()
                if department_count >= department_concurrency:
                    raise RuntimeError("workflow_department_concurrency_exceeded")

            run = WorkflowV2RunRow(
                run_id=run_id,
                workflow_name=resource.slug,
                workflow_resource_id=resource.id,
                definition_version=root_snapshot.version,
                checkpoint_thread_id=f"wf-{run_id}",
                status="queued",
                inputs=inputs,
                model_name=model_name,
                snapshot={},
                runner_tool_groups=sorted(actor.tool_groups) if actor.tool_groups is not None else None,
                created_by=actor.user_id,
                department_id=actor.department_id,
            )
            session.add(run)
            await session.flush()
            session.add(
                WorkflowTaskRow(
                    task_id=str(uuid4()),
                    run_id=run_id,
                    status="queued",
                    attempts=0,
                    cancel_requested=False,
                )
            )
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
        async with self._event_append_lock:
            # The write must survive branch cancellation: langgraph cancels the
            # sibling of a failed fork branch mid-await, and an append killed
            # inside ``session.execute`` would leave an open write transaction
            # on the pooled connection — blocking every later writer for the
            # SQLite busy timeout. Shielding lets the write finish cleanly.
            event = await asyncio.shield(self._append_event_once(run_id, event_type, payload, worker_id=worker_id, max_events=max_events))
            if event is not None:
                await self._notify_sink(run_id, event)
            return event

    async def _append_event_once(
        self,
        run_id: str,
        event_type: str,
        payload: dict,
        *,
        worker_id: str | None,
        max_events: int | None,
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
            await self._notify_sink(run_id)
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

    async def clear_resume_command(self, task_id: str) -> None:
        """Consume a resume command once the worker has built its invocation.

        The attempt-budget exemption in ``claim_next_task`` only applies to the
        immediate resume execution; clearing the intent here means a later
        lease take-over after a crash counts as a fresh attempt again.
        """
        async with self.session_factory() as session:
            await session.execute(update(WorkflowTaskRow).where(WorkflowTaskRow.task_id == task_id).values(resume_command_id=None))
            await session.commit()

    async def claim_next_task(
        self,
        worker_id: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 30,
        max_attempts: int = 3,
    ) -> WorkflowTaskRow | None:
        now = now or datetime.now(UTC)
        claim_scope = or_(
            WorkflowTaskRow.status == "queued",
            and_(WorkflowTaskRow.status == "running", WorkflowTaskRow.lease_expires_at < now),
        )
        # The claim itself is a single UPDATE ... RETURNING statement, so two
        # workers can never claim the same task: SQLite serializes writers, and
        # the candidate subquery is re-evaluated when the loser retries. The
        # SELECT below only labels the lease-audit row (taken_over vs claimed)
        # and never influences the claim decision.
        #
        # WAL mode does not invoke the busy handler for snapshot conflicts
        # (SQLITE_BUSY_SNAPSHOT), so a concurrent commit can abort the whole
        # statement with "database is locked"; retrying re-runs the subquery
        # against fresh state.
        for attempt in range(3):
            try:
                async with self.session_factory() as session:
                    probe = (await session.execute(select(WorkflowTaskRow.task_id, WorkflowTaskRow.lease_owner).where(claim_scope).order_by(WorkflowTaskRow.task_id).limit(1))).first()
                    claimed = await session.execute(
                        update(WorkflowTaskRow)
                        .where(WorkflowTaskRow.task_id.in_(select(WorkflowTaskRow.task_id).where(claim_scope).order_by(WorkflowTaskRow.task_id).limit(1)))
                        .values(
                            status="running",
                            lease_owner=worker_id,
                            lease_expires_at=now + timedelta(seconds=lease_seconds),
                            heartbeat_at=now,
                        )
                        .returning(WorkflowTaskRow)
                    )
                    task = claimed.scalar_one_or_none()
                    if task is None:
                        return None
                    # The immediate execution of an operator resume is free:
                    # paused and failed runs may be resumed without consuming
                    # the attempt budget. Only fresh claims (and lease
                    # take-overs after a worker crash) increment attempts, so
                    # max_attempts still kills crash loops. The row is ours
                    # (fresh lease) while we settle attempts, so this is race-free.
                    if task.resume_command_id is None:
                        task.attempts += 1
                        if task.attempts > max_attempts:
                            task.status = "failed"
                            task.lease_owner = None
                            task.lease_expires_at = None
                            run = (await session.execute(select(WorkflowV2RunRow).where(WorkflowV2RunRow.run_id == task.run_id))).scalar_one_or_none()
                            if run is not None:
                                run.status = "failed"
                                run.error = "工作流执行失败：重试次数已达上限"
                                run.event_seq += 1
                                event = WorkflowV2EventRow(
                                    id=str(uuid4()),
                                    run_id=run.run_id,
                                    seq=run.event_seq,
                                    event_type="run_failed",
                                    payload={"code": "max_attempts", "summary": "工作流执行失败：重试次数已达上限", "error": "workflow_max_attempts_exceeded"},
                                )
                                session.add(event)
                            await session.commit()
                            if run is not None:
                                await self._notify_sink(run.run_id, event)
                            return None
                    run = (await session.execute(select(WorkflowV2RunRow).where(WorkflowV2RunRow.run_id == task.run_id))).scalar_one_or_none()
                    if run is not None:
                        run.status = "running"
                    previous_owner = probe.lease_owner if probe is not None and probe.task_id == task.task_id else None
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
            except OperationalError as exc:
                message = str(exc.orig).lower()
                if "busy" not in message and "locked" not in message and "snapshot" not in message:
                    raise
                logger.warning("claim_next_task hit a transient SQLite lock, retrying: %s", exc)
                await asyncio.sleep(0.05 * (attempt + 1))
        logger.error("claim_next_task exhausted retries for worker %s", worker_id)
        return None

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
            # notify the sink after the status flip so terminal records finalize
            await self._notify_sink(run_id)
            return True
