"""KnowledgeBase management retrieval test endpoints (M6 ticket 01).

Lives outside ``resources.py`` so the eval-case and retrieval-test verticals
stay independent; it deliberately reuses the Resource Governance helpers so
visibility, error translation, and audit semantics cannot drift.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from app.agentplatform.knowledge.retrieval_test import KnowledgeRetrievalTestService, KnowledgeRetrievalTestValidationError, RetrievalTestUnavailable
from app.agentplatform.rbac_models import UserModel
from app.gateway.audit import record_audit
from app.gateway.authz import get_current_rbac_user
from app.gateway.routers.resources import _factory, _resource_actor, _translate_resource_errors

router = APIRouter(prefix="/api/resources", tags=["knowledge-tests"])


class RetrievalTestCreateRequest(BaseModel):
    """Only the parameters the shared retrieval path supports; anything else
    is an explicit 422 instead of a silently applied default."""

    model_config = ConfigDict(extra="forbid")

    revision_id: str = Field(min_length=1, max_length=36)
    profile_id: Literal["frozen", "configured"] = "frozen"
    query: str = Field(min_length=1, max_length=500)
    top_k: int | None = Field(default=None, ge=1, le=20)


@router.post("/{resource_id}/retrieval-tests", status_code=201)
@_translate_resource_errors
async def create_retrieval_test(
    resource_id: str,
    body: RetrievalTestCreateRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    """Run and archive a bounded retrieval test."""
    async with _factory()() as session:
        service = KnowledgeRetrievalTestService(session, _resource_actor(current_user))
        try:
            payload = await service.execute(resource_id, body.revision_id, query=body.query, top_k=body.top_k, profile_id=body.profile_id)
            await session.commit()
        except RetrievalTestUnavailable as exc:
            raise HTTPException(status_code=503, detail={"code": "retrieval_test_unavailable", "message": str(exc)}) from exc
        except KnowledgeRetrievalTestValidationError as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_retrieval_test", "message": str(exc)}) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": "retrieval_test_storage_unavailable", "message": "The retrieval test could not be archived; try again later."},
            ) from exc
    await record_audit(
        str(current_user.id),
        "knowledge_retrieval_test_executed",
        "knowledge_base",
        resource_id,
        {
            "resource_id": resource_id,
            "revision_id": payload["revision_id"],
            "test_id": payload["id"],
            "result_status": payload["result_status"],
        },
    )
    return payload


@router.get("/{resource_id}/retrieval-tests")
@_translate_resource_errors
async def list_retrieval_tests(
    resource_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    """List archived retrieval tests for a visible knowledge base."""
    async with _factory()() as session:
        return await KnowledgeRetrievalTestService(session, _resource_actor(current_user)).list_tests(resource_id, offset=offset, limit=limit)


@router.get("/{resource_id}/retrieval-tests/{test_id}")
@_translate_resource_errors
async def get_retrieval_test(
    resource_id: str,
    test_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    """Read one archived retrieval test after rechecking access."""
    async with _factory()() as session:
        return await KnowledgeRetrievalTestService(session, _resource_actor(current_user)).get_test(resource_id, test_id)
