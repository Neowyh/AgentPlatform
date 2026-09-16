"""Durable single-profile retrieval evaluation for a published revision."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from agentplatform_extension.knowledge.retrieval_receipts import project_retrieval_items
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentplatform.knowledge.eval_gate import load_eval_policy, policy_payload
from app.agentplatform.knowledge.integrity import UNUSABLE_INTEGRITY
from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeEvalCase, KnowledgeEvalComparison, KnowledgeEvalResult, KnowledgeEvalRun, KnowledgeRevision
from app.agentplatform.knowledge.retrieval_test import (
    DEFAULT_TEST_TOP_K,
    MAX_TEST_TOP_K,
    KnowledgeRetrievalTestService,
    _maybe_await,
    _provider_error_code,
    _ragflow_search,
)
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceAction, ResourceActor, ResourceConflict, ResourceNotFound, ResourcePermissionDenied, ResourceService

MAX_EVAL_CASES = 1000
MAX_EVAL_PAGE_SIZE = 100
EVAL_METRICS_VERSION = "retrieval-metrics-v1"
EVAL_LEASE_SECONDS = 60
EVAL_MAX_CONCURRENT_CASES = 4
EVAL_TOTAL_TIMEOUT_SECONDS = 900
EVAL_MAX_STORED_CHUNKS = 200


class KnowledgeEvaluationValidationError(ValueError):
    """Raised for an invalid evaluation request or frozen input."""


def require_evaluation_execution_access(actor: ResourceActor) -> None:
    """Require the same current maintenance permissions as evaluation start."""
    if not actor.can(ResourceAction.USE) or not actor.can(ResourceAction.WRITE):
        raise ResourcePermissionDenied("Evaluation execution permission has been revoked")


def calculate_retrieval_metrics(ranked_document_ids: list[str], expected_document_ids: list[str]) -> dict[str, float | bool]:
    """Calculate the frozen top-K facts from the actual de-duplicated ranking."""
    expected = set(expected_document_ids)
    hits = [rank for rank, document_id in enumerate(ranked_document_ids, 1) if document_id in expected]
    return {
        "expected_hit": bool(hits),
        "recall_at_k": len(set(ranked_document_ids) & expected) / len(expected) if expected else 0.0,
        "mrr_at_k": 1 / hits[0] if hits else 0.0,
    }


def compare_evaluation_runs(left: dict[str, object], right: dict[str, object], left_results: list[KnowledgeEvalResult], right_results: list[KnowledgeEvalResult]) -> dict[str, object]:
    """Compare two complete runs without treating failed cases as zeroes."""
    left_aggregate = left.get("aggregate") if isinstance(left.get("aggregate"), dict) else {}
    right_aggregate = right.get("aggregate") if isinstance(right.get("aggregate"), dict) else {}
    complete = left.get("status") == right.get("status") == "completed"
    same_protocol = (left.get("top_k"), left.get("metrics_version")) == (right.get("top_k"), right.get("metrics_version"))
    left_by_case = {result.case_id: result for result in left_results}
    right_by_case = {result.case_id: result for result in right_results}
    cases: list[dict[str, object]] = []
    for case_id in sorted(set(left_by_case) | set(right_by_case)):
        left_result, right_result = left_by_case.get(case_id), right_by_case.get(case_id)
        valid = left_result is not None and right_result is not None and left_result.recall_at_k is not None and right_result.recall_at_k is not None
        if not valid:
            outcome = "incomplete"
        else:
            left_score = (float(left_result.recall_at_k or 0), float(left_result.mrr_at_k or 0), bool(left_result.expected_hit))
            right_score = (float(right_result.recall_at_k or 0), float(right_result.mrr_at_k or 0), bool(right_result.expected_hit))
            outcome = "improved" if right_score > left_score else "regressed" if right_score < left_score else "unchanged"
        cases.append({"case_id": case_id, "outcome": outcome, "left": _result_payload(left_result) if left_result else None, "right": _result_payload(right_result) if right_result else None})
    eligible = complete and same_protocol and bool(cases) and all(item["outcome"] != "incomplete" for item in cases)
    delta = {key: (float(right_aggregate[key]) - float(left_aggregate[key])) if eligible and right_aggregate.get(key) is not None and left_aggregate.get(key) is not None else None for key in ("expected_hit_rate", "recall_at_k", "mrr_at_k")}
    return {"eligible": eligible, "reason": None if eligible else "Both runs must complete with the same K, metrics version, and case set", "delta": delta, "cases": cases}


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _run_payload(run: KnowledgeEvalRun) -> dict[str, object]:
    return {
        "id": run.id,
        "retry_of_run_id": run.retry_of_run_id,
        "resource_id": run.knowledge_base_id,
        "revision_id": run.revision_id,
        "revision_no": run.revision_no,
        "manifest_hash": run.manifest_hash,
        "profile_id": run.profile_id,
        "profile_hash": run.profile_hash,
        "policy_version": run.policy_version,
        "policy": dict(run.policy_json or {}) if run.policy_json else None,
        "qualification_status": run.qualification_status,
        "qualification_reason": run.qualification_reason,
        "profile": dict(run.profile_json or {}),
        "top_k": run.top_k,
        "metrics_version": run.metrics_version,
        "status": run.status,
        "total_cases": run.total_cases,
        "completed_cases": run.completed_cases,
        "failed_cases": run.failed_cases,
        "case_ids": list(run.case_ids_json or []),
        "aggregate": dict(run.aggregate_json or {}),
        "error_code": run.error_code,
        "created_by": run.created_by,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def _result_payload(result: KnowledgeEvalResult) -> dict[str, object]:
    return {
        "id": result.id,
        "run_id": result.run_id,
        "case_id": result.case_id,
        "case_version_no": result.case_version_no,
        "case_content_hash": result.case_content_hash,
        "query": result.query,
        "expected_document_ids": list(result.expected_document_ids_json or []),
        "status": result.status,
        "error_code": result.error_code,
        "ranked_items": [dict(item) for item in result.ranked_items_json or []],
        "expected_hit": result.expected_hit,
        "recall_at_k": result.recall_at_k,
        "mrr_at_k": result.mrr_at_k,
        "created_at": result.created_at.isoformat() if result.created_at else None,
    }


class KnowledgeEvaluationService:
    def __init__(self, session: AsyncSession, actor: ResourceActor, *, search: Callable[..., Any] | None = None, settings_factory: Callable[[], Any] | None = None) -> None:
        self.session = session
        self.resource_service = ResourceService(session, actor)
        self._search = search or _ragflow_search
        self._settings_factory = settings_factory

    async def _kb(self, resource_id: str, *, use: bool = False) -> Resource:
        resource = await self.resource_service.get_visible(resource_id)
        if resource.type != "knowledge_base":
            raise ResourceNotFound(f"KnowledgeBase {resource_id} not found")
        if use and not self.resource_service.actor.can(ResourceAction.USE):
            raise ResourcePermissionDenied(f"Permission denied: {ResourceAction.USE.value}")
        return resource

    async def _revision(self, resource_id: str, revision_id: str) -> KnowledgeRevision:
        revision = await self.session.get(KnowledgeRevision, revision_id)
        if revision is None or revision.knowledge_base_id != resource_id:
            raise ResourceNotFound(f"Knowledge revision {revision_id} not found")
        if revision.status not in {"published", "superseded", "ready"} or revision.integrity_status in UNUSABLE_INTEGRITY or not revision.provider_dataset_id:
            raise ResourceConflict(f"Revision {revision_id} is not an eligible published or verified candidate revision")
        return revision

    async def _profile(self, revision: KnowledgeRevision, profile_id: str) -> dict[str, object]:
        if profile_id not in {"frozen", "configured"}:
            raise KnowledgeEvaluationValidationError("unsupported retrieval profile")
        kb = await self.session.get(KnowledgeBase, revision.knowledge_base_id)
        if profile_id == "configured":
            return dict(kb.retrieval_profile_json or {}) if kb and isinstance(kb.retrieval_profile_json, dict) else {}
        profiles = next((entry.get("knowledge_profiles") for entry in revision.manifest_json or [] if isinstance(entry, dict) and isinstance(entry.get("knowledge_profiles"), dict)), None)
        retrieval = profiles.get("retrieval") if isinstance(profiles, dict) else None
        if isinstance(retrieval, dict):
            return dict(retrieval)
        return dict(kb.retrieval_profile_json or {}) if kb and isinstance(kb.retrieval_profile_json, dict) else {}

    async def start(self, resource_id: str, revision_id: str, *, profile_id: str = "frozen", top_k: int = DEFAULT_TEST_TOP_K, case_ids: list[str] | None = None) -> dict[str, object]:
        resource = await self._kb(resource_id, use=True)
        self.resource_service.assert_modify(resource)
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= MAX_TEST_TOP_K:
            raise KnowledgeEvaluationValidationError(f"top_k must be between 1 and {MAX_TEST_TOP_K}")
        revision = await self._revision(resource_id, revision_id)
        cases_query = select(KnowledgeEvalCase).where(KnowledgeEvalCase.knowledge_base_id == resource_id).order_by(KnowledgeEvalCase.created_at, KnowledgeEvalCase.id)
        if case_ids is not None:
            if not case_ids or len(case_ids) > MAX_EVAL_CASES or len(set(case_ids)) != len(case_ids):
                raise KnowledgeEvaluationValidationError("case_ids must be a non-empty list without duplicates")
            cases_query = cases_query.where(KnowledgeEvalCase.id.in_(case_ids))
        cases = list((await self.session.execute(cases_query)).scalars())
        if not cases:
            raise KnowledgeEvaluationValidationError("evaluation case set must not be empty")
        if case_ids is not None and {case.id for case in cases} != set(case_ids):
            raise KnowledgeEvaluationValidationError("one or more evaluation cases were not found")
        manifest_ids = {str(entry.get("document_id")) for entry in revision.manifest_json or [] if isinstance(entry, dict)}
        snapshot = []
        for case in cases:
            expected = list(case.expected_document_ids_json or [])
            missing = [doc_id for doc_id in expected if doc_id not in manifest_ids]
            if missing:
                raise KnowledgeEvaluationValidationError(f"case {case.id} has expected documents not present in revision: {', '.join(missing)}")
            snapshot.append({"case_id": case.id, "version_no": case.version_no, "content_hash": case.content_hash, "question": case.question, "expected_document_ids": expected, "tags": list(case.tags_json or [])})
        profile = await self._profile(revision, profile_id)
        unsupported = set(profile) - {"similarity_threshold", "vector_similarity_weight", "top_k"}
        if unsupported:
            raise KnowledgeEvaluationValidationError(f"unsupported retrieval profile parameters: {', '.join(sorted(unsupported))}")
        policy = await load_eval_policy(self.session, resource_id)
        frozen_policy = policy_payload(policy)
        if frozen_policy is not None and (profile_id != policy.profile_id or top_k != policy.top_k or [item["case_id"] for item in snapshot] != list(policy.case_ids_json or [])):
            # Evaluation remains allowed for exploration, but it cannot be
            # mistaken for publish evidence for a different contract.
            frozen_policy = None
        run = KnowledgeEvalRun(
            id=str(uuid.uuid4()),
            knowledge_base_id=resource_id,
            revision_id=revision.id,
            revision_no=revision.revision_no,
            manifest_hash=revision.manifest_hash,
            profile_id=profile_id,
            profile_hash=_hash(profile),
            policy_version=policy.version if frozen_policy is not None else None,
            policy_json=frozen_policy,
            profile_json=profile,
            case_ids_json=[item["case_id"] for item in snapshot],
            case_snapshot_json=snapshot,
            top_k=top_k,
            metrics_version=EVAL_METRICS_VERSION,
            status="queued",
            total_cases=len(snapshot),
            created_by=self.resource_service.actor.user_id,
        )
        self.session.add(run)
        await self.session.flush()
        return _run_payload(run)

    async def process_run(self, run_id: str, *, owner: str = "knowledge-eval-worker") -> dict[str, object] | None:
        run = await self.session.get(KnowledgeEvalRun, run_id)
        if run is None or run.status in {"completed", "partial", "failed"}:
            return _run_payload(run) if run else None
        now = datetime.now(UTC)
        claimed = await self.session.execute(
            update(KnowledgeEvalRun)
            .where(KnowledgeEvalRun.id == run_id, KnowledgeEvalRun.status.in_(["queued", "running"]), (KnowledgeEvalRun.lease_until.is_(None)) | (KnowledgeEvalRun.lease_until < now))
            .values(status="running", lease_owner=owner, lease_until=now + timedelta(seconds=EVAL_LEASE_SECONDS), started_at=run.started_at or now)
        )
        if claimed.rowcount != 1:
            return _run_payload(run)
        await self.session.commit()
        await self.session.refresh(run)
        try:
            resource = await self._kb(run.knowledge_base_id, use=True)
            self.resource_service.assert_modify(resource)
            require_evaluation_execution_access(self.resource_service.actor)
        except ResourcePermissionDenied:
            run.status = "failed"
            run.error_code = "evaluation_authorization_revoked"
            run.finished_at = datetime.now(UTC)
            run.lease_owner = run.lease_until = None
            await self.session.commit()
            return _run_payload(run)
        revision = await self.session.get(KnowledgeRevision, run.revision_id)
        if revision is None:
            run.status = "failed"
            run.error_code = "revision_missing"
            run.finished_at = datetime.now(UTC)
            await self.session.commit()
            return _run_payload(run)
        settings_factory = self._settings_factory
        if settings_factory is None:
            from app.agentplatform.knowledge.retrieval_test import _official_retrieval_settings

            settings_factory = _official_retrieval_settings
        try:
            settings = await _maybe_await(settings_factory())
        except ImportError:
            settings = None
        if settings is None:
            run.status, run.error_code, run.finished_at = "failed", "retrieval_unavailable", datetime.now(UTC)
            run.lease_owner = run.lease_until = None
            await self.session.commit()
            return _run_payload(run)
        retrieval = KnowledgeRetrievalTestService(self.session, self.resource_service.actor, search=self._search, settings_factory=lambda: settings)
        metadata = retrieval.revision_metadata(revision)
        provider_ids = [str(value) for value in (revision.provider_doc_map_json or {}).values()]
        deadline = asyncio.get_running_loop().time() + EVAL_TOTAL_TIMEOUT_SECONDS
        timed_out = False
        for case in run.case_snapshot_json or []:
            if asyncio.get_running_loop().time() >= deadline:
                timed_out = True
                break
            exists = await self.session.scalar(select(KnowledgeEvalResult.id).where(KnowledgeEvalResult.run_id == run.id, KnowledgeEvalResult.case_id == case["case_id"]))
            if exists:
                continue
            status, error_code, items = "success", None, []
            try:
                applied = retrieval.applied_parameters(settings, run.profile_json or {}, run.top_k)
                raw = await asyncio.wait_for(_maybe_await(self._search(case["question"], settings=settings, dataset_id=revision.provider_dataset_id, document_ids=provider_ids, applied=applied)), timeout=float(settings.timeout))
                chunks = raw.get("chunks") if isinstance(raw, dict) and isinstance(raw.get("chunks"), list) else []
                projected = project_retrieval_items(
                    {"chunks": [chunk for chunk in chunks[:EVAL_MAX_STORED_CHUNKS] if isinstance(chunk, dict)]},
                    metadata,
                )
                seen: set[str] = set()
                raw_items: list[dict[str, object]] = []
                for item in projected:
                    document_id = str(item.get("document_id") or "")
                    if not document_id:
                        continue
                    item = dict(item)
                    item["chunk_rank"] = len(raw_items) + 1
                    if document_id not in seen:
                        seen.add(document_id)
                        item["rank"] = len(items) + 1
                        items.append(item)
                    else:
                        item["rank"] = next(entry["rank"] for entry in items if entry.get("document_id") == document_id)
                    raw_items.append(item)
                    if len(items) >= run.top_k:
                        break
                if not items:
                    status = "empty_hit"
            except Exception as exc:
                status, error_code = "provider_error", _provider_error_code(exc)
            ranked_ids = [str(item.get("document_id")) for item in items]
            metrics = calculate_retrieval_metrics(ranked_ids, case["expected_document_ids"])
            result = KnowledgeEvalResult(
                id=str(uuid.uuid4()),
                run_id=run.id,
                case_id=case["case_id"],
                case_version_no=case["version_no"],
                case_content_hash=case["content_hash"],
                query=case["question"],
                expected_document_ids_json=case["expected_document_ids"],
                status=status,
                error_code=error_code,
                ranked_items_json=raw_items if status in {"success", "empty_hit"} else [],
                expected_hit=bool(metrics["expected_hit"]),
                recall_at_k=float(metrics["recall_at_k"]) if status in {"success", "empty_hit"} else None,
                mrr_at_k=float(metrics["mrr_at_k"]) if status in {"success", "empty_hit"} else None,
            )
            self.session.add(result)
            await self.session.flush()
            run.completed_cases += 1
            if status == "provider_error":
                run.failed_cases += 1
        results = list((await self.session.execute(select(KnowledgeEvalResult).where(KnowledgeEvalResult.run_id == run.id))).scalars())
        if timed_out:
            run.status = "partial"
            run.error_code = "evaluation_total_timeout"
            run.finished_at = datetime.now(UTC)
            run.lease_owner = run.lease_until = None
        elif len(results) >= run.total_cases:
            valid = [item for item in results if item.recall_at_k is not None]
            run.status = "completed" if not run.failed_cases else "partial"
            run.aggregate_json = {
                "denominator": len(valid),
                "expected_hit_rate": (sum(item.expected_hit for item in valid) / len(valid)) if valid else None,
                "recall_at_k": (sum(item.recall_at_k or 0 for item in valid) / len(valid)) if valid else None,
                "mrr_at_k": (sum(item.mrr_at_k or 0 for item in valid) / len(valid)) if valid else None,
                "top_k": run.top_k,
                "metrics_version": run.metrics_version,
            }
            policy = run.policy_json or {}
            metrics = run.aggregate_json
            qualified = (
                (
                    run.failed_cases == 0
                    and metrics["denominator"] == run.total_cases
                    and all(metrics.get(key) is not None for key in ("expected_hit_rate", "recall_at_k", "mrr_at_k"))
                    and all(float(metrics[key]) >= float(policy[key]) for key in ("min_expected_hit_rate", "min_recall_at_k", "min_mrr_at_k"))
                )
                if policy
                else False
            )
            run.qualification_status = "passed" if qualified else "rejected"
            run.qualification_reason = None if qualified else ("evaluation did not meet the versioned publish thresholds" if policy else "run was not created for the current publish policy")
            run.finished_at = datetime.now(UTC)
            run.lease_owner = run.lease_until = None
        else:
            run.lease_owner = run.lease_until = None
        await self.session.commit()
        return _run_payload(run)

    async def list_runs(self, resource_id: str, *, offset: int = 0, limit: int = 20) -> dict[str, object]:
        await self._kb(resource_id)
        if offset < 0 or not 1 <= limit <= MAX_EVAL_PAGE_SIZE:
            raise KnowledgeEvaluationValidationError("pagination is out of bounds")
        query = select(KnowledgeEvalRun).where(KnowledgeEvalRun.knowledge_base_id == resource_id).order_by(KnowledgeEvalRun.created_at.desc(), KnowledgeEvalRun.id.desc())
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        rows = list((await self.session.execute(query.offset(offset).limit(limit))).scalars())
        return {"items": [_run_payload(row) for row in rows], "total": int(total or 0), "offset": offset, "limit": limit}

    async def get_run(self, resource_id: str, run_id: str, *, result_offset: int = 0, result_limit: int = 20) -> dict[str, object]:
        await self._kb(resource_id)
        run = await self.session.get(KnowledgeEvalRun, run_id)
        if run is None or run.knowledge_base_id != resource_id:
            raise ResourceNotFound(f"Evaluation {run_id} not found")
        if result_offset < 0 or not 1 <= result_limit <= MAX_EVAL_PAGE_SIZE:
            raise KnowledgeEvaluationValidationError("pagination is out of bounds")
        query = select(KnowledgeEvalResult).where(KnowledgeEvalResult.run_id == run.id).order_by(KnowledgeEvalResult.created_at, KnowledgeEvalResult.id)
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        rows = list((await self.session.execute(query.offset(result_offset).limit(result_limit))).scalars())
        payload = _run_payload(run)
        payload["results"] = [_result_payload(row) for row in rows]
        payload["results_total"] = int(total or 0)
        payload["results_offset"] = result_offset
        payload["results_limit"] = result_limit
        return payload

    async def retry(self, resource_id: str, run_id: str) -> dict[str, object]:
        run = await self.session.get(KnowledgeEvalRun, run_id)
        if run is None or run.knowledge_base_id != resource_id:
            raise ResourceNotFound(f"Evaluation {run_id} not found")
        await self._kb(resource_id, use=True)
        resource = await self._kb(resource_id)
        self.resource_service.assert_modify(resource)
        if run.status not in {"failed", "partial"}:
            raise ResourceConflict("only failed or partial evaluations can be retried")
        revision = await self._revision(resource_id, run.revision_id)
        clone = KnowledgeEvalRun(
            id=str(uuid.uuid4()),
            retry_of_run_id=run.id,
            knowledge_base_id=resource_id,
            revision_id=revision.id,
            revision_no=run.revision_no,
            manifest_hash=run.manifest_hash,
            profile_id=run.profile_id,
            profile_hash=run.profile_hash,
            profile_json=dict(run.profile_json or {}),
            case_ids_json=list(run.case_ids_json or []),
            case_snapshot_json=list(run.case_snapshot_json or []),
            top_k=run.top_k,
            metrics_version=run.metrics_version,
            policy_version=run.policy_version,
            policy_json=dict(run.policy_json or {}) if run.policy_json else None,
            status="queued",
            total_cases=run.total_cases,
            created_by=self.resource_service.actor.user_id,
        )
        self.session.add(clone)
        await self.session.flush()
        return _run_payload(clone)

    async def start_comparison(self, resource_id: str, *, left_revision_id: str, left_profile_id: str, right_revision_id: str, right_profile_id: str, top_k: int = DEFAULT_TEST_TOP_K, case_ids: list[str] | None = None) -> dict[str, object]:
        """Enqueue two ordinary frozen evaluations under one comparison identity."""
        left = await self.start(resource_id, left_revision_id, profile_id=left_profile_id, top_k=top_k, case_ids=case_ids)
        right = await self.start(resource_id, right_revision_id, profile_id=right_profile_id, top_k=top_k, case_ids=list(left["case_ids"]))
        comparison = KnowledgeEvalComparison(
            id=str(uuid.uuid4()),
            knowledge_base_id=resource_id,
            left_run_id=str(left["id"]),
            right_run_id=str(right["id"]),
            top_k=top_k,
            metrics_version=EVAL_METRICS_VERSION,
            status="queued",
            created_by=self.resource_service.actor.user_id,
        )
        self.session.add(comparison)
        await self.session.flush()
        return await self.get_comparison(resource_id, comparison.id)

    async def get_comparison(self, resource_id: str, comparison_id: str) -> dict[str, object]:
        await self._kb(resource_id)
        comparison = await self.session.get(KnowledgeEvalComparison, comparison_id)
        if comparison is None or comparison.knowledge_base_id != resource_id:
            raise ResourceNotFound(f"Evaluation comparison {comparison_id} not found")
        left = await self.session.get(KnowledgeEvalRun, comparison.left_run_id)
        right = await self.session.get(KnowledgeEvalRun, comparison.right_run_id)
        if left is None or right is None:
            raise ResourceConflict("comparison runs are unavailable")
        left_payload, right_payload = _run_payload(left), _run_payload(right)
        left_rows = list((await self.session.execute(select(KnowledgeEvalResult).where(KnowledgeEvalResult.run_id == left.id))).scalars())
        right_rows = list((await self.session.execute(select(KnowledgeEvalResult).where(KnowledgeEvalResult.run_id == right.id))).scalars())
        result = compare_evaluation_runs(left_payload, right_payload, left_rows, right_rows)
        comparison_status = "queued" if left.status in {"queued", "running"} or right.status in {"queued", "running"} else "completed" if result["eligible"] else "incomplete"
        return {
            "id": comparison.id,
            "resource_id": resource_id,
            "status": comparison_status,
            "top_k": comparison.top_k,
            "metrics_version": comparison.metrics_version,
            "left": left_payload,
            "right": right_payload,
            "comparison": result,
            "created_by": comparison.created_by,
            "created_at": comparison.created_at.isoformat() if comparison.created_at else None,
        }
