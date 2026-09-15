"""Management retrieval tests against published Knowledge Revisions (M6 ticket 01).

An authorized user can probe a published (or superseded) Knowledge Revision
with a question and see the actual hits — without generating a chat answer.
This module reuses the official ``knowledge_search`` mechanics end to end:

- version mapping: the revision's own per-revision provider dataset plus the
  frozen per-revision document allowlist (``provider_doc_map_json``), exactly
  like run preparation freezes them;
- provider adaptation / parameter application: the ``knowledge_search`` tool
  settings (thresholds, candidate ``top_k``, timeout) feed the same retrieval
  call the tool makes; the test's ``top_k`` only bounds how many hits are
  requested and shown;
- projection: hits are projected through the same bounded, canonical-identity
  item projection as run retrieval receipts.

Everything is explicit: unsupported parameters are rejected, unknown
identifiers are indistinguishable from invisible ones, and every execution is
archived so it can be replayed later under the reader's *current* permission
without re-running the retrieval. No Agent Run, Tool Call, or chat citation is
fabricated.
"""

from __future__ import annotations

import inspect
import time
import uuid
from collections.abc import Callable
from typing import Any

from agentplatform_extension.knowledge.retrieval_receipts import project_retrieval_items
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentplatform.knowledge.integrity import UNUSABLE_INTEGRITY
from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeRetrievalTest, KnowledgeRevision
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceActor, ResourceConflict, ResourceNotFound, ResourceService

MAX_TEST_QUERY_CHARS = 500
MAX_TEST_TOP_K = 20
DEFAULT_TEST_TOP_K = 8
MAX_TEST_PAGE_SIZE = 50
RETRIEVABLE_REVISION_STATUSES = frozenset({"published", "superseded"})

_APPLIED_PARAMETER_KEYS = ("page_size", "similarity_threshold", "vector_similarity_weight", "top_k")


class RetrievalTestUnavailable(RuntimeError):
    """The retrieval tooling is not configured in this deployment."""


class KnowledgeRetrievalTestValidationError(ValueError):
    """Raised when a retrieval test request violates documented bounds."""


async def _official_retrieval_settings() -> Any | None:
    """Read the official knowledge_search tool settings (None if unconfigured)."""

    from deerflow.community.ragflow import tools as ragflow_tools

    settings, _error = ragflow_tools._settings_or_error()
    return settings


async def _ragflow_search(query: str, *, settings: Any, dataset_id: str, document_ids: list[str], applied: dict[str, Any]) -> dict[str, Any]:
    """Execute the retrieval through the official tool client and parameters."""

    from deerflow.community.ragflow import tools as ragflow_tools

    client = ragflow_tools._build_client(settings)
    return await client.retrieve(
        query,
        dataset_ids=[dataset_id],
        page_size=int(applied["page_size"]),
        similarity_threshold=float(applied["similarity_threshold"]),
        vector_similarity_weight=float(applied["vector_similarity_weight"]),
        top_k=int(applied["top_k"]),
        document_ids=document_ids,
    )


def _provider_error_code(exc: Exception) -> str:
    from deerflow.community.ragflow.client import RAGFlowAPIError, RAGFlowConnectionError, RAGFlowProtocolError

    if isinstance(exc, RAGFlowConnectionError):
        return "connection_error"
    if isinstance(exc, RAGFlowProtocolError):
        return "protocol_error"
    if isinstance(exc, RAGFlowAPIError):
        return "provider_api_error"
    return "unexpected_error"


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class KnowledgeRetrievalTestService:
    def __init__(
        self,
        session: AsyncSession,
        actor: ResourceActor,
        *,
        search: Callable[..., Any] | None = None,
        settings_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.session = session
        self.resource_service = ResourceService(session, actor)
        self._search = search or _ragflow_search
        self._settings_factory = settings_factory or _official_retrieval_settings

    async def _knowledge_base(self, resource_id: str) -> Resource:
        resource = await self.resource_service.get_visible(resource_id)
        if resource.type != "knowledge_base":
            raise ResourceNotFound(f"KnowledgeBase {resource_id} not found")
        return resource

    async def _resolved_profile(self, revision: KnowledgeRevision) -> dict[str, object]:
        """Selected retrieval profile: frozen manifest value when present —
        otherwise the KnowledgeBase row, for revisions created before profile
        freezing. Same resolution order as the run freeze."""

        profiles = next(
            (entry.get("knowledge_profiles") for entry in revision.manifest_json or [] if isinstance(entry, dict) and isinstance(entry.get("knowledge_profiles"), dict)),
            None,
        )
        if profiles:
            retrieval = profiles.get("retrieval") if isinstance(profiles, dict) else None
            return dict(retrieval) if isinstance(retrieval, dict) else {}
        kb_row = await self.session.get(KnowledgeBase, revision.knowledge_base_id)
        if kb_row is not None and isinstance(kb_row.retrieval_profile_json, dict):
            return dict(kb_row.retrieval_profile_json)
        return {}

    async def _retrievable_revision(self, resource_id: str, revision_id: str) -> KnowledgeRevision:
        revision = await self.session.get(KnowledgeRevision, revision_id)
        if revision is None or revision.knowledge_base_id != resource_id:
            raise ResourceNotFound(f"Knowledge revision {revision_id} not found")
        if revision.status not in RETRIEVABLE_REVISION_STATUSES:
            raise ResourceConflict(f"Revision {revision_id} is not retrievable (status={revision.status})")
        if revision.integrity_status in UNUSABLE_INTEGRITY:
            raise ResourceConflict(f"Revision {revision_id} failed reconciliation and is not retrievable")
        if not revision.provider_dataset_id:
            raise ResourceConflict(f"Revision {revision_id} has no published dataset")
        return revision

    @staticmethod
    def _revision_metadata(revision: KnowledgeRevision) -> dict[str, object]:
        manifest_by_id = {str(entry.get("document_id")): entry for entry in revision.manifest_json or [] if isinstance(entry, dict)}
        documents = {
            str(provider_document_id): {
                "logical_document_id": logical_document_id,
                "display_name": manifest_by_id.get(logical_document_id, {}).get("filename"),
                "content_hash": manifest_by_id.get(logical_document_id, {}).get("content_hash"),
            }
            for logical_document_id, provider_document_id in (revision.provider_doc_map_json or {}).items()
        }
        return {"documents": documents}

    @staticmethod
    def _applied_parameters(settings: Any, top_k: int) -> dict[str, Any]:
        return {
            "page_size": top_k,
            "similarity_threshold": settings.similarity_threshold,
            "vector_similarity_weight": settings.vector_similarity_weight,
            "top_k": settings.top_k,
        }

    async def execute(
        self,
        resource_id: str,
        revision_id: str,
        *,
        query: str,
        top_k: int | None = None,
    ) -> dict[str, object]:
        resource = await self._knowledge_base(resource_id)
        revision = await self._retrievable_revision(resource_id, revision_id)

        normalized_query = (query or "").strip()
        if not normalized_query:
            raise KnowledgeRetrievalTestValidationError("query must not be empty")
        if len(normalized_query) > MAX_TEST_QUERY_CHARS:
            raise KnowledgeRetrievalTestValidationError(f"query must be at most {MAX_TEST_QUERY_CHARS} characters")
        requested_top_k = DEFAULT_TEST_TOP_K if top_k is None else top_k
        if not isinstance(requested_top_k, int) or isinstance(requested_top_k, bool) or not 1 <= requested_top_k <= MAX_TEST_TOP_K:
            raise KnowledgeRetrievalTestValidationError(f"top_k must be between 1 and {MAX_TEST_TOP_K}")

        settings = await _maybe_await(self._settings_factory())
        if settings is None:
            raise RetrievalTestUnavailable("knowledge retrieval is not configured in this deployment")
        applied = self._applied_parameters(settings, requested_top_k)
        profile = await self._resolved_profile(revision)

        document_ids = [str(provider_document_id) for provider_document_id in (revision.provider_doc_map_json or {}).values()]
        started = time.monotonic()
        error_code: str | None = None
        try:
            result = await _maybe_await(self._search(normalized_query, settings=settings, dataset_id=revision.provider_dataset_id, document_ids=document_ids, applied=applied))
        except Exception as exc:
            result = {"chunks": []}
            error_code = _provider_error_code(exc)
        duration_ms = int((time.monotonic() - started) * 1000)

        chunks = result.get("chunks") if isinstance(result, dict) and isinstance(result.get("chunks"), list) else []
        items = [] if error_code else project_retrieval_items(result, self._revision_metadata(revision))[:requested_top_k]
        for rank, item in enumerate(items, start=1):
            item["rank"] = rank
            item["rerank_score"] = _rerank_score(result, rank - 1)
        result_status = "provider_error" if error_code else ("empty_hit" if not items else "success")
        truncated = not error_code and len(chunks) > len(items)

        record = KnowledgeRetrievalTest(
            id=str(uuid.uuid4()),
            knowledge_base_id=resource_id,
            revision_id=revision.id,
            revision_no=revision.revision_no,
            manifest_hash=revision.manifest_hash,
            query=normalized_query,
            requested_top_k=requested_top_k,
            retrieval_profile_json=profile,
            applied_parameters_json={key: applied[key] for key in _APPLIED_PARAMETER_KEYS},
            result_status=result_status,
            error_code=error_code,
            results_json=items,
            returned_count=len(items),
            truncated=truncated,
            duration_ms=duration_ms,
            created_by=self.resource_service.actor.user_id,
        )
        self.session.add(record)
        await self.session.flush()
        payload = _test_payload(record, include_items=True)
        payload["resource_slug"] = resource.slug
        return payload

    async def list_tests(self, resource_id: str, *, offset: int = 0, limit: int = 20) -> dict[str, object]:
        await self._knowledge_base(resource_id)
        if limit < 1 or limit > MAX_TEST_PAGE_SIZE or offset < 0:
            raise KnowledgeRetrievalTestValidationError("pagination is out of bounds")
        total = await self.session.scalar(select(func.count()).select_from(KnowledgeRetrievalTest).where(KnowledgeRetrievalTest.knowledge_base_id == resource_id))
        rows = await self.session.execute(
            select(KnowledgeRetrievalTest).where(KnowledgeRetrievalTest.knowledge_base_id == resource_id).order_by(KnowledgeRetrievalTest.created_at.desc(), KnowledgeRetrievalTest.id.desc()).offset(offset).limit(limit)
        )
        return {"items": [_test_payload(record, include_items=False) for record in rows.scalars()], "total": int(total or 0), "offset": offset, "limit": limit}

    async def get_test(self, resource_id: str, test_id: str) -> dict[str, object]:
        await self._knowledge_base(resource_id)
        record = await self.session.get(KnowledgeRetrievalTest, test_id)
        if record is None or record.knowledge_base_id != resource_id:
            raise ResourceNotFound(f"Retrieval test {test_id} not found")
        return _test_payload(record, include_items=True)


def _rerank_score(result: object, index: int) -> float | None:
    """Surface a provider rerank score when one exists; never synthesize one."""

    if not isinstance(result, dict) or not isinstance(result.get("chunks"), list):
        return None
    chunks = result["chunks"]
    if index >= len(chunks) or not isinstance(chunks[index], dict):
        return None
    for key in ("rerank_similarity", "rerank_score"):
        value = chunks[index].get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _test_payload(record: KnowledgeRetrievalTest, *, include_items: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": record.id,
        "resource_id": record.knowledge_base_id,
        "revision_id": record.revision_id,
        "revision_no": record.revision_no,
        "manifest_hash": record.manifest_hash,
        "query": record.query,
        "requested_top_k": record.requested_top_k,
        "retrieval_profile": dict(record.retrieval_profile_json or {}),
        "result_status": record.result_status,
        "error_code": record.error_code,
        "returned_count": record.returned_count,
        "truncated": record.truncated,
        "duration_ms": record.duration_ms,
        "created_by": record.created_by,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
    if include_items:
        payload["items"] = [dict(item) for item in record.results_json or []]
        payload["applied_parameters"] = dict(record.applied_parameters_json or {})
    return payload
