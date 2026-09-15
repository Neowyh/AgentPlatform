"""Regression eval case management for KnowledgeBases (M6 ticket 03).

An eval case pairs a question with one or more expected documents (canonical
platform identities, never provider ids) plus tags. Every content change
appends an immutable version row whose deterministic ``content_hash`` lets a
later Eval run freeze exactly the case content it evaluated. Expected
documents that are absent from a target revision are reported explicitly —
stale annotations are never silently dropped and never counted as misses.
"""

from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentplatform.knowledge.models import KnowledgeDocument, KnowledgeEvalCase, KnowledgeEvalCaseVersion, KnowledgeRevision
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceActor, ResourceNotFound, ResourceService

MAX_QUESTION_LENGTH = 4000
MAX_EXPECTED_DOCUMENTS = 20
MAX_TAGS = 20
MAX_TAG_LENGTH = 64


class KnowledgeEvalCaseValidationError(ValueError):
    """Raised when eval case content violates the documented boundaries."""


def eval_case_content_hash(question: str, expected_document_ids: list[str], tags: list[str]) -> str:
    """Deterministically hash the case content (order-independent)."""

    payload = {
        "question": question,
        "expected_document_ids": sorted(expected_document_ids),
        "tags": sorted(tags),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalized_question(question: object) -> str:
    if not isinstance(question, str):
        raise KnowledgeEvalCaseValidationError("question must be a string")
    value = question.strip()
    if not value:
        raise KnowledgeEvalCaseValidationError("question must not be empty")
    if len(value) > MAX_QUESTION_LENGTH:
        raise KnowledgeEvalCaseValidationError(f"question must be at most {MAX_QUESTION_LENGTH} characters")
    return value


def _normalized_tags(tags: object) -> list[str]:
    if tags is None:
        return []
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise KnowledgeEvalCaseValidationError("tags must be a list of strings")
    normalized = [tag.strip() for tag in tags]
    if any(not tag for tag in normalized):
        raise KnowledgeEvalCaseValidationError("tags must not contain empty entries")
    if len(normalized) > MAX_TAGS:
        raise KnowledgeEvalCaseValidationError(f"a case carries at most {MAX_TAGS} tags")
    if any(len(tag) > MAX_TAG_LENGTH for tag in normalized):
        raise KnowledgeEvalCaseValidationError(f"a tag is at most {MAX_TAG_LENGTH} characters")
    if len(set(normalized)) != len(normalized):
        raise KnowledgeEvalCaseValidationError("tags must not contain duplicates")
    return normalized


def _normalized_expected_ids(expected_document_ids: object) -> list[str]:
    if not isinstance(expected_document_ids, list) or any(not isinstance(value, str) for value in expected_document_ids):
        raise KnowledgeEvalCaseValidationError("expected_document_ids must be a list of document ids")
    normalized = [value.strip() for value in expected_document_ids]
    if not normalized:
        raise KnowledgeEvalCaseValidationError("a case requires at least one expected document")
    if len(set(normalized)) != len(normalized):
        raise KnowledgeEvalCaseValidationError("expected documents must not contain duplicates")
    if len(normalized) > MAX_EXPECTED_DOCUMENTS:
        raise KnowledgeEvalCaseValidationError(f"a case expects at most {MAX_EXPECTED_DOCUMENTS} documents")
    return normalized


def _case_payload(case: KnowledgeEvalCase) -> dict[str, object]:
    return {
        "id": case.id,
        "resource_id": case.knowledge_base_id,
        "question": case.question,
        "expected_document_ids": list(case.expected_document_ids_json or []),
        "tags": list(case.tags_json or []),
        "content_hash": case.content_hash,
        "version_no": case.version_no,
        "created_by": case.created_by,
        "updated_by": case.updated_by,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }


def _version_payload(version: KnowledgeEvalCaseVersion) -> dict[str, object]:
    return {
        "version_no": version.version_no,
        "question": version.question,
        "expected_document_ids": list(version.expected_document_ids_json or []),
        "tags": list(version.tags_json or []),
        "content_hash": version.content_hash,
        "change_type": version.change_type,
        "changed_by": version.changed_by,
        "changed_at": version.changed_at.isoformat() if version.changed_at else None,
    }


class KnowledgeEvalCaseService:
    def __init__(self, session: AsyncSession, actor: ResourceActor) -> None:
        self.session = session
        self.resource_service = ResourceService(session, actor)

    async def _knowledge_base(self, resource_id: str, *, modify: bool = False) -> Resource:
        resource = await self.resource_service.get_visible(resource_id)
        if resource.type != "knowledge_base":
            raise ResourceNotFound(f"KnowledgeBase {resource_id} not found")
        if modify:
            self.resource_service.assert_modify(resource)
        return resource

    async def _owned_case(self, resource_id: str, case_id: str) -> KnowledgeEvalCase:
        case = await self.session.get(KnowledgeEvalCase, case_id)
        if case is None or case.knowledge_base_id != resource_id:
            raise ResourceNotFound(f"Eval case {case_id} not found")
        return case

    async def _validated_document_ids(self, resource_id: str, expected_document_ids: list[str]) -> list[str]:
        normalized = _normalized_expected_ids(expected_document_ids)
        rows = await self.session.execute(
            select(KnowledgeDocument.id).where(
                KnowledgeDocument.id.in_(normalized),
                KnowledgeDocument.resource_id == resource_id,
                KnowledgeDocument.status != "deleted",
            )
        )
        known = set(rows.scalars())
        unknown = [value for value in normalized if value not in known]
        if unknown:
            raise KnowledgeEvalCaseValidationError(f"unknown expected documents for this KnowledgeBase: {', '.join(unknown)}")
        return normalized

    async def create_case(
        self,
        resource_id: str,
        *,
        question: str,
        expected_document_ids: list[str],
        tags: list[str] | None = None,
    ) -> dict[str, object]:
        await self._knowledge_base(resource_id, modify=True)
        normalized_question = _normalized_question(question)
        normalized_tags = _normalized_tags(tags)
        document_ids = await self._validated_document_ids(resource_id, expected_document_ids)
        user_id = self.resource_service.actor.user_id
        case = KnowledgeEvalCase(
            id=str(uuid.uuid4()),
            knowledge_base_id=resource_id,
            question=normalized_question,
            expected_document_ids_json=document_ids,
            tags_json=normalized_tags,
            content_hash=eval_case_content_hash(normalized_question, document_ids, normalized_tags),
            version_no=1,
            created_by=user_id,
        )
        self.session.add(case)
        self.session.add(
            KnowledgeEvalCaseVersion(
                id=str(uuid.uuid4()),
                case_id=case.id,
                version_no=1,
                question=normalized_question,
                expected_document_ids_json=document_ids,
                tags_json=normalized_tags,
                content_hash=case.content_hash,
                change_type="created",
                changed_by=user_id,
            )
        )
        await self.session.flush()
        return _case_payload(case)

    async def list_cases(self, resource_id: str) -> list[dict[str, object]]:
        await self._knowledge_base(resource_id)
        rows = await self.session.execute(select(KnowledgeEvalCase).where(KnowledgeEvalCase.knowledge_base_id == resource_id).order_by(KnowledgeEvalCase.created_at, KnowledgeEvalCase.id))
        return [_case_payload(case) for case in rows.scalars()]

    async def get_case(self, resource_id: str, case_id: str) -> dict[str, object]:
        await self._knowledge_base(resource_id)
        case = await self._owned_case(resource_id, case_id)
        payload = _case_payload(case)
        rows = await self.session.execute(select(KnowledgeEvalCaseVersion).where(KnowledgeEvalCaseVersion.case_id == case.id).order_by(KnowledgeEvalCaseVersion.version_no))
        payload["versions"] = [_version_payload(version) for version in rows.scalars()]
        return payload

    async def update_case(
        self,
        resource_id: str,
        case_id: str,
        *,
        question: str | None = None,
        expected_document_ids: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, object]:
        await self._knowledge_base(resource_id, modify=True)
        case = await self._owned_case(resource_id, case_id)
        normalized_question = _normalized_question(case.question if question is None else question)
        normalized_tags = _normalized_tags(case.tags_json if tags is None else tags)
        current_documents = list(case.expected_document_ids_json or [])
        document_ids = current_documents if expected_document_ids is None else await self._validated_document_ids(resource_id, expected_document_ids)
        content_hash = eval_case_content_hash(normalized_question, document_ids, normalized_tags)
        if content_hash == case.content_hash:
            return _case_payload(case)

        user_id = self.resource_service.actor.user_id
        case.question = normalized_question
        case.expected_document_ids_json = document_ids
        case.tags_json = normalized_tags
        case.content_hash = content_hash
        case.version_no += 1
        case.updated_by = user_id
        self.session.add(
            KnowledgeEvalCaseVersion(
                id=str(uuid.uuid4()),
                case_id=case.id,
                version_no=case.version_no,
                question=normalized_question,
                expected_document_ids_json=document_ids,
                tags_json=normalized_tags,
                content_hash=content_hash,
                change_type="updated",
                changed_by=user_id,
            )
        )
        await self.session.flush()
        return _case_payload(case)

    async def delete_case(self, resource_id: str, case_id: str) -> None:
        await self._knowledge_base(resource_id, modify=True)
        case = await self._owned_case(resource_id, case_id)
        await self.session.execute(KnowledgeEvalCaseVersion.__table__.delete().where(KnowledgeEvalCaseVersion.case_id == case.id))
        await self.session.delete(case)
        await self.session.flush()

    async def revision_applicability(self, resource_id: str, revision_id: str) -> dict[str, object]:
        """Report, per case, which expected documents the revision does not contain.

        Cases are never rewritten here: stale annotations stay on the case and
        are surfaced as ``missing_document_ids`` instead of counting as misses.
        """

        await self._knowledge_base(resource_id)
        revision = await self.session.get(KnowledgeRevision, revision_id)
        if revision is None or revision.knowledge_base_id != resource_id:
            raise ResourceNotFound(f"Knowledge revision {revision_id} not found")
        manifest_ids = {str(entry.get("document_id")) for entry in revision.manifest_json or [] if isinstance(entry, dict)}
        rows = await self.session.execute(select(KnowledgeEvalCase).where(KnowledgeEvalCase.knowledge_base_id == resource_id).order_by(KnowledgeEvalCase.created_at, KnowledgeEvalCase.id))
        items = []
        for case in rows.scalars():
            missing = [value for value in case.expected_document_ids_json or [] if value not in manifest_ids]
            items.append(
                {
                    "case_id": case.id,
                    "question": case.question,
                    "content_hash": case.content_hash,
                    "version_no": case.version_no,
                    "expected_document_count": len(case.expected_document_ids_json or []),
                    "missing_document_ids": missing,
                    "applicable": not missing,
                }
            )
        return {
            "revision_id": revision.id,
            "revision_no": revision.revision_no,
            "status": revision.status,
            "manifest_hash": revision.manifest_hash,
            "items": items,
            "total": len(items),
        }
