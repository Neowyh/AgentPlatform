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
        "case_ids": list(policy.case_ids_json or []),
        "min_expected_hit_rate": policy.min_expected_hit_rate,
        "min_recall_at_k": policy.min_recall_at_k,
        "min_mrr_at_k": policy.min_mrr_at_k,
    }


async def load_eval_policy(session: AsyncSession, knowledge_base_id: str) -> KnowledgeEvaluationPolicy | None:
    return await session.get(KnowledgeEvaluationPolicy, knowledge_base_id)


def _profile_hash(profile: object) -> str:
    return hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


async def load_eval_evidence(session: AsyncSession, knowledge_base_id: str, manifest_hash: str, *, revision_id: str, policy: KnowledgeEvaluationPolicy) -> dict | None:
    """Return only a completed run matching every current publish identity."""
    revision = await session.get(KnowledgeRevision, revision_id)
    knowledge_base = await session.get(KnowledgeBase, knowledge_base_id)
    if revision is None or knowledge_base is None or revision.knowledge_base_id != knowledge_base_id:
        return None
    if policy.profile_id == "configured":
        profile = knowledge_base.retrieval_profile_json or {}
    else:
        profiles = next(
            (entry.get("knowledge_profiles") for entry in revision.manifest_json or [] if isinstance(entry, dict) and isinstance(entry.get("knowledge_profiles"), dict)),
            None,
        )
        profile = profiles.get("retrieval") if isinstance(profiles, dict) else knowledge_base.retrieval_profile_json or {}
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
        if run.policy_json != policy_payload(policy) or list(run.case_ids_json or []) != list(policy.case_ids_json or []):
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
