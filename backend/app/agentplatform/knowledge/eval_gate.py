"""Exact, versioned evaluation evidence for the revision publish gate."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeEvalRun, KnowledgeEvaluationPolicy, KnowledgeRevision
from app.agentplatform.knowledge.settings import config_value
from app.agentplatform.resources.service import ResourceConflict


def eval_required() -> bool:
    return bool(config_value("publish_eval_required"))


def policy_payload(policy: KnowledgeEvaluationPolicy | None) -> dict | None:
    if policy is None:
        return None
    return {
        "version": policy.version,
        "profile_id": policy.profile_id,
        "top_k": policy.top_k,
        "case_ids": normalize_case_ids(policy.case_ids_json or []),
        "min_expected_hit_rate": policy.min_expected_hit_rate,
        "min_recall_at_k": policy.min_recall_at_k,
        "min_mrr_at_k": policy.min_mrr_at_k,
    }


async def load_eval_policy(session: AsyncSession, knowledge_base_id: str) -> KnowledgeEvaluationPolicy | None:
    result = await session.execute(select(KnowledgeEvaluationPolicy).where(KnowledgeEvaluationPolicy.knowledge_base_id == knowledge_base_id).execution_options(populate_existing=True))
    return result.scalar_one_or_none()


def normalize_case_ids(case_ids: list[str]) -> list[str]:
    """Treat a policy's case set as an order-independent, stable identity."""
    return sorted(set(case_ids))


def retrieval_profile_for_revision(retrieval_profile: dict | None, manifest_json: list | None, profile_id: str) -> dict:
    if profile_id == "configured":
        return dict(retrieval_profile or {})
    profiles = next(
        (entry.get("knowledge_profiles") for entry in manifest_json or [] if isinstance(entry, dict) and isinstance(entry.get("knowledge_profiles"), dict)),
        None,
    )
    retrieval = profiles.get("retrieval") if isinstance(profiles, dict) else None
    return dict(retrieval) if isinstance(retrieval, dict) else dict(retrieval_profile or {})


def _profile_hash(profile: object) -> str:
    return hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


async def load_eval_evidence(session: AsyncSession, knowledge_base_id: str, manifest_hash: str, *, revision_id: str, policy: KnowledgeEvaluationPolicy) -> dict | None:
    """Return only a completed run matching every current publish identity."""
    revision = (await session.execute(select(KnowledgeRevision).where(KnowledgeRevision.id == revision_id).execution_options(populate_existing=True))).scalar_one_or_none()
    knowledge_base = (await session.execute(select(KnowledgeBase).where(KnowledgeBase.resource_id == knowledge_base_id).execution_options(populate_existing=True))).scalar_one_or_none()
    if revision is None or knowledge_base is None or revision.knowledge_base_id != knowledge_base_id:
        return None
    profile = retrieval_profile_for_revision(knowledge_base.retrieval_profile_json, revision.manifest_json, policy.profile_id)
    expected_profile_hash = _profile_hash(profile)
    result = await session.execute(
        select(KnowledgeEvalRun)
        .where(
            KnowledgeEvalRun.knowledge_base_id == knowledge_base_id,
            KnowledgeEvalRun.revision_id == revision_id,
            KnowledgeEvalRun.manifest_hash == manifest_hash,
            KnowledgeEvalRun.profile_id == policy.profile_id,
            KnowledgeEvalRun.profile_hash == expected_profile_hash,
            KnowledgeEvalRun.policy_version == policy.version,
            KnowledgeEvalRun.status == "completed",
            KnowledgeEvalRun.qualification_status == "passed",
        )
        .order_by(KnowledgeEvalRun.finished_at.desc(), KnowledgeEvalRun.id.desc())
    )
    for run in result.scalars():
        if run.policy_json != policy_payload(policy) or normalize_case_ids(run.case_ids_json or []) != normalize_case_ids(policy.case_ids_json or []):
            continue
        return {"run_id": run.id, "policy_version": policy.version, "profile_id": run.profile_id}
    return None


async def require_publish_evidence(session: AsyncSession, knowledge_base_id: str, revision_id: str, manifest_hash: str) -> dict | None:
    policy = await load_eval_policy(session, knowledge_base_id)
    if policy is None:
        raise ResourceConflict("Publishing requires an evaluation policy with explicit thresholds")
    evidence = await load_eval_evidence(session, knowledge_base_id, manifest_hash, revision_id=revision_id, policy=policy)
    if evidence is None:
        raise ResourceConflict("Publishing requires completed, passing evaluation evidence matching this revision, profile, case set, and policy")
    return evidence
