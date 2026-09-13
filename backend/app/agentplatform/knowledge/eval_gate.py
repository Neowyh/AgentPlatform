"""Revision publish gate contract for evaluation evidence (M4).

The gate is a seam only: M6 will introduce the Eval engine that records
evidence against a candidate manifest hash. Until then no evidence can ever
match, so enabling ``publish_eval_required`` rejects every publish.
"""

from __future__ import annotations

from deerflow.config.app_config import get_app_config


def eval_required() -> bool:
    """Read the optional ``knowledge.publish_eval_required`` config flag."""

    knowledge = getattr(get_app_config(), "knowledge", None)
    raw = knowledge.get("publish_eval_required") if isinstance(knowledge, dict) else getattr(knowledge, "publish_eval_required", None)
    return bool(raw)


def load_eval_evidence(knowledge_base_id: str, manifest_hash: str) -> dict | None:
    """Return accepted evaluation evidence matching this exact candidate.

    Returns ``None`` while no evaluation engine exists (M4). A publish that
    requires evidence therefore stays rejected with a conflict, never silently
    approved.
    """

    return None
