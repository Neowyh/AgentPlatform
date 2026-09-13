"""Knowledge reconciliation API for admin roles (M4 ticket 05)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.agentplatform.knowledge.models import KnowledgeRevision, KnowledgeRevisionCheck
from app.agentplatform.knowledge.ragflow import configured_ragflow_provider
from app.agentplatform.knowledge.reconciliation import run_reconciliation
from app.agentplatform.rbac_models import UserModel, UserRole
from app.gateway.authz import get_current_rbac_user, require_role
from deerflow.persistence.engine import get_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/knowledge", tags=["knowledge-admin"])


class ReconciliationRunRequest(BaseModel):
    knowledge_base_id: str | None = None


async def _latest_checks(session, kb_id: str, limit: int = 20) -> list[dict[str, Any]]:
    rows = (await session.execute(select(KnowledgeRevisionCheck).where(KnowledgeRevisionCheck.knowledge_base_id == kb_id).order_by(KnowledgeRevisionCheck.checked_at.desc()).limit(limit))).scalars()
    return [
        {
            "id": check.id,
            "revision_id": check.revision_id,
            "trigger": check.trigger,
            "outcome": check.outcome,
            "findings": check.findings_json,
            "checked_by": check.checked_by,
            "checked_at": check.checked_at.isoformat() if check.checked_at else None,
            "duration_ms": check.duration_ms,
        }
        for check in rows
    ]


async def _revision_states(session, kb_id: str) -> list[dict[str, Any]]:
    rows = (await session.execute(select(KnowledgeRevision).where(KnowledgeRevision.knowledge_base_id == kb_id, KnowledgeRevision.status == "published").order_by(KnowledgeRevision.revision_no))).scalars()
    return [
        {
            "revision_id": revision.id,
            "revision_no": revision.revision_no,
            "integrity_status": revision.integrity_status,
            "integrity_checked_at": revision.integrity_checked_at.isoformat() if revision.integrity_checked_at else None,
        }
        for revision in rows
    ]


@router.post("/reconciliation/run")
@require_role(UserRole.SUPER_ADMIN)
async def trigger_reconciliation(
    request: Request,
    body: ReconciliationRunRequest | None = None,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    """Run one read-only reconciliation pass; findings never auto-repair."""
    provider = configured_ragflow_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail="No knowledge provider is configured")
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    kb_id = body.knowledge_base_id if body is not None else None
    summaries = await run_reconciliation(
        session_factory,
        provider=provider,
        trigger="manual",
        checked_by=str(current_user.id),
        knowledge_base_id=kb_id,
    )
    return {"items": summaries, "total": len(summaries)}


@router.get("/knowledge-bases/{kb_id}/reconciliation")
@require_role(UserRole.SUPER_ADMIN)
async def get_reconciliation(
    kb_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    async with session_factory() as session:
        checks = await _latest_checks(session, kb_id)
        revisions = await _revision_states(session, kb_id)
        return {"knowledge_base_id": kb_id, "revisions": revisions, "checks": checks}
