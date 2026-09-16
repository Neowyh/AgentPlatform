"""Small durable knowledge reconciliation loop owned by Gateway lifespan."""

from __future__ import annotations

import asyncio
import logging
import socket
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update

from app.agentplatform.knowledge.documents import KnowledgeDocumentService
from app.agentplatform.knowledge.evaluation import KnowledgeEvaluationService
from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeDocument, KnowledgeEvalRun
from app.agentplatform.knowledge.ragflow import configured_ragflow_provider
from app.agentplatform.rbac_models import UserModel, UserRole
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceAction, ResourceActor
from deerflow.persistence.engine import get_session_factory

logger = logging.getLogger(__name__)


class KnowledgeWorker:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._owner = f"{socket.gethostname()}:{uuid.uuid4()}"
        self._lease_seconds = 30

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="knowledge-worker")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception:
                logger.exception("Knowledge worker tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=2)
            except TimeoutError:
                pass

    async def _tick(self) -> None:
        factory = get_session_factory()
        provider = configured_ragflow_provider()
        if factory is None:
            return
        async with factory() as session:
            evaluation = (await session.execute(select(KnowledgeEvalRun.id).where(KnowledgeEvalRun.status.in_(["queued", "running"])).order_by(KnowledgeEvalRun.created_at).limit(1))).scalar_one_or_none()
            if evaluation:
                run = await session.get(KnowledgeEvalRun, evaluation)
                if run is not None:
                    resource = await session.get(Resource, run.knowledge_base_id)
                    if resource is not None:
                        user = await session.get(UserModel, str(run.created_by))
                        permissions = {ResourceAction.READ}
                        if user and not user.disabled and user.role in {UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN}:
                            permissions.update({ResourceAction.USE, ResourceAction.WRITE})
                        if user and not user.disabled and user.role == UserRole.SUPER_ADMIN:
                            permissions.update(ResourceAction)
                        actor = ResourceActor(
                            user_id=str(run.created_by),
                            department_id=str(user.department_id) if user and user.department_id else None,
                            role=str(user.role) if user else "unknown",
                            permissions=frozenset(permissions),
                        )
                        await KnowledgeEvaluationService(session, actor).process_run(run.id, owner=self._owner)
                        return
            if provider is None:
                rows = list((await session.execute(select(KnowledgeBase).where(KnowledgeBase.initialization_status == "initializing"))).scalars())
                for binding in rows:
                    binding.initialization_status = "failed"
                    binding.initialization_error = "Knowledge provider configuration is missing."
                if rows:
                    await session.commit()
                return
            now = datetime.now(UTC)
            rows = list(
                (
                    await session.execute(
                        select(KnowledgeBase).where(
                            KnowledgeBase.initialization_status == "initializing",
                            or_(KnowledgeBase.initialization_next_attempt_at.is_(None), KnowledgeBase.initialization_next_attempt_at <= now),
                            or_(KnowledgeBase.initialization_lease_until.is_(None), KnowledgeBase.initialization_lease_until < now),
                        )
                    )
                ).scalars()
            )
            for binding in rows:
                claimed = await session.execute(
                    update(KnowledgeBase)
                    .where(
                        KnowledgeBase.resource_id == binding.resource_id,
                        KnowledgeBase.initialization_status == "initializing",
                        or_(KnowledgeBase.initialization_lease_until.is_(None), KnowledgeBase.initialization_lease_until < now),
                    )
                    .values(
                        initialization_lease_owner=self._owner,
                        initialization_lease_until=now + timedelta(seconds=self._lease_seconds),
                        initialization_step="creating_dataset",
                    )
                )
                if claimed.rowcount != 1:
                    continue
                # Release the claim transaction before making a network call.
                await session.commit()
                await session.refresh(binding)
                binding.initialization_attempt += 1
                await session.commit()
                try:
                    dataset_id = await provider.create_dataset(name=f"deerflow-{binding.resource_id}")
                    binding.provider_dataset_id = dataset_id
                    binding.initialization_status = "ready"
                    binding.initialization_error = None
                    binding.initialization_step = "complete"
                    binding.initialization_lease_owner = None
                    binding.initialization_lease_until = None
                except Exception:
                    binding.initialization_status = "failed"
                    binding.initialization_error = "The knowledge provider is temporarily unavailable."
                    binding.initialization_step = "failed"
                    binding.initialization_next_attempt_at = now + timedelta(seconds=min(300, 2 ** min(binding.initialization_attempt, 8)))
                    binding.initialization_lease_owner = None
                    binding.initialization_lease_until = None
                await session.commit()
            docs = list(
                (
                    await session.execute(
                        select(KnowledgeDocument).where(
                            KnowledgeDocument.status.in_(["uploaded", "processing", "rebuild_requested", "deleting"]),
                            or_(KnowledgeDocument.next_attempt_at.is_(None), KnowledgeDocument.next_attempt_at <= now),
                            or_(KnowledgeDocument.lease_until.is_(None), KnowledgeDocument.lease_until < now),
                        )
                    )
                ).scalars()
            )
            for document in docs:
                claimed = await session.execute(
                    update(KnowledgeDocument)
                    .where(
                        KnowledgeDocument.id == document.id,
                        KnowledgeDocument.status.in_(["uploaded", "processing", "rebuild_requested", "deleting"]),
                        or_(KnowledgeDocument.lease_until.is_(None), KnowledgeDocument.lease_until < now),
                    )
                    .values(
                        lease_owner=self._owner,
                        lease_until=now + timedelta(seconds=self._lease_seconds),
                        processing_step=("deleting" if document.status == "deleting" else "syncing" if document.status == "processing" else "ingesting"),
                    )
                )
                if claimed.rowcount != 1:
                    continue
                # Provider I/O must not hold an open database transaction.
                await session.commit()
                await session.refresh(document)
                document_id = document.id
                claimed_status = document.status
                resource = await session.get(Resource, document.resource_id)
                if resource is None:
                    await session.execute(
                        update(KnowledgeDocument)
                        .where(KnowledgeDocument.id == document_id, KnowledgeDocument.lease_owner == self._owner)
                        .values(
                            status="failed",
                            failure_code="resource_missing",
                            failure_message="The KnowledgeBase for this document no longer exists.",
                            lease_owner=None,
                            lease_until=None,
                            processing_step="failed",
                        )
                    )
                    await session.commit()
                    continue
                actor = ResourceActor(user_id=str(resource.owner_id), department_id=None, role="user", permissions=frozenset({ResourceAction.READ, ResourceAction.WRITE}))
                service = KnowledgeDocumentService(session, actor, provider)
                try:
                    if claimed_status == "deleting":
                        await service.delete(document_id, resource_id=resource.id)
                    elif claimed_status == "processing":
                        await service.sync_status(document_id, resource_id=resource.id)
                    else:
                        await service.process(
                            document_id,
                            resource_id=resource.id,
                            rebuild=claimed_status == "rebuild_requested",
                        )
                except Exception:
                    # Keep the row recoverable when an unexpected service or
                    # storage failure escapes the provider boundary.
                    logger.exception("Knowledge document reconciliation failed for %s", document_id)
                    await session.rollback()
                    await session.execute(
                        update(KnowledgeDocument)
                        .where(KnowledgeDocument.id == document_id, KnowledgeDocument.lease_owner == self._owner)
                        .values(
                            status="failed",
                            failure_code="worker_error",
                            failure_message="Document processing failed. Please try again later.",
                            lease_owner=None,
                            lease_until=None,
                            processing_step="failed",
                        )
                    )
                    await session.commit()
                    continue
                await session.refresh(document)
                await session.execute(
                    update(KnowledgeDocument)
                    .where(KnowledgeDocument.id == document_id, KnowledgeDocument.lease_owner == self._owner)
                    .values(
                        lease_owner=None,
                        lease_until=None,
                        processing_step="complete" if document.status == "ready" else document.status,
                    )
                )
                await session.commit()
