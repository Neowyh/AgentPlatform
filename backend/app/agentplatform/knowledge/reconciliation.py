"""Read-only reconciliation between published revisions and the provider (M4 ticket 05).

Reconciliation answers one question: does the provider still hold what each
published revision claims? Findings are recorded as immutable check history
and surfaced as revision integrity status; nothing here mutates provider
content, deletes orphans, rewrites manifests, or replaces run snapshots.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeRevision, KnowledgeRevisionCheck
from app.agentplatform.knowledge.provider import KnowledgeProvider, KnowledgeProviderError

# Revision integrity statuses (ticket 05 taxonomy; UNVERIFIED is deliberately
# distinct so an unreachable or unverifiable provider is never reported as
# HEALTHY nor as a confirmed failure).
INTEGRITY_HEALTHY = "healthy"
INTEGRITY_UNVERIFIED = "unverified"
INTEGRITY_MISSING_PROVIDER_DATASET = "missing_provider_dataset"
INTEGRITY_DRIFTED = "drifted"

_OUTCOME_TO_INTEGRITY = {
    "HEALTHY": INTEGRITY_HEALTHY,
    "UNVERIFIED": INTEGRITY_UNVERIFIED,
    "MISSING_PROVIDER_DATASET": INTEGRITY_MISSING_PROVIDER_DATASET,
    "MISSING_DOCUMENT": INTEGRITY_DRIFTED,
    "HASH_MISMATCH": INTEGRITY_DRIFTED,
    "ORPHAN_PROVIDER_RESOURCE": INTEGRITY_UNVERIFIED,
}

# Platform-created published datasets follow the publish naming scheme; a
# provider dataset carrying that prefix but bound to nothing is an orphan.
_ORPHAN_NAME_PREFIX = "ideer-kb-"


def configured_interval_seconds() -> int:
    """Read ``knowledge.reconciliation_interval_seconds`` (0 disables the loop)."""

    from deerflow.config.app_config import get_app_config

    knowledge = getattr(get_app_config(), "knowledge", None)
    raw = knowledge.get("reconciliation_interval_seconds") if isinstance(knowledge, dict) else getattr(knowledge, "reconciliation_interval_seconds", None)
    try:
        return max(0, int(raw)) if raw is not None else 0
    except (TypeError, ValueError):
        return 0


async def _check_revision(provider: KnowledgeProvider, revision: KnowledgeRevision) -> tuple[str, list[dict]]:
    dataset_id = revision.provider_dataset_id
    if not dataset_id:
        return "MISSING_PROVIDER_DATASET", [{"kind": "missing_dataset"}]
    exists = await provider.list_datasets(dataset_id=dataset_id)
    if not exists:
        return "MISSING_PROVIDER_DATASET", [{"kind": "missing_dataset", "dataset_id": dataset_id}]
    documents = await provider.list_dataset_documents(dataset_id=dataset_id)
    expected = {str(value): key for key, value in (revision.provider_doc_map_json or {}).items()}
    findings: list[dict] = []
    actual_ids: set[str] = set()
    for document in documents:
        document_id = str(document.get("id"))
        actual_ids.add(document_id)
        entry: dict[str, object] = {"kind": "document", "provider_document_id": document_id}
        if document_id not in expected:
            findings.append({**entry, "verdict": "unexpected"})
            continue
        provider_hash = document.get("content_hash")
        if provider_hash is None:
            findings.append({**entry, "verdict": "unverified", "reason": "provider exposes no verifiable content hash"})
        elif _expected_hash(revision, expected[document_id]) != str(provider_hash):
            findings.append({**entry, "verdict": "hash_mismatch"})
    for document_id in sorted(set(expected) - actual_ids):
        findings.append({"kind": "document", "provider_document_id": document_id, "verdict": "missing"})
    missing = any(item.get("verdict") == "missing" for item in findings)
    unexpected = any(item.get("verdict") == "unexpected" for item in findings)
    mismatched = any(item.get("verdict") == "hash_mismatch" for item in findings)
    if missing or unexpected:
        return "MISSING_DOCUMENT", findings
    if mismatched:
        return "HASH_MISMATCH", findings
    if findings:
        return "UNVERIFIED", findings
    return "HEALTHY", []


def _expected_hash(revision: KnowledgeRevision, document_id: str) -> str | None:
    for entry in revision.manifest_json or []:
        if str(entry.get("document_id")) == document_id:
            return str(entry.get("content_hash"))
    return None


async def _bound_dataset_ids(session: AsyncSession) -> set[str]:
    bound: set[str] = set()
    revision_ids = (await session.execute(select(KnowledgeRevision.provider_dataset_id))).scalars()
    bound.update(str(value) for value in revision_ids if value)
    kb_ids = (await session.execute(select(KnowledgeBase.provider_dataset_id))).scalars()
    bound.update(str(value) for value in kb_ids if value)
    return bound


async def _find_orphans(session: AsyncSession, provider: KnowledgeProvider) -> list[str]:
    """Provider datasets that no revision or KB binding claims."""

    try:
        datasets = await provider.list_datasets()
    except KnowledgeProviderError:
        return []
    bound = await _bound_dataset_ids(session)
    orphans = []
    for dataset in datasets:
        dataset_id = str(dataset.get("id"))
        name = str(dataset.get("name") or "")
        if dataset_id in bound:
            continue
        if not name.startswith(_ORPHAN_NAME_PREFIX):
            continue
        orphans.append(dataset_id)
    return sorted(orphans)


async def run_reconciliation(
    session_factory,
    *,
    provider: KnowledgeProvider,
    trigger: str = "manual",
    checked_by: str | None = None,
    knowledge_base_id: str | None = None,
) -> list[dict[str, object]]:
    """Reconcile published revisions against the provider; read-only, no repair.

    The latest check outcome decides a revision's integrity status, so a
    healthy re-check after an operator repaired the provider is the explicit
    path back to ``healthy`` — reconciliation itself never repairs anything.
    """

    summaries: list[dict[str, object]] = []
    async with session_factory() as session:
        rows = (await session.execute(select(KnowledgeRevision).where(KnowledgeRevision.status == "published").order_by(KnowledgeRevision.knowledge_base_id, KnowledgeRevision.revision_no))).scalars().all()
        if knowledge_base_id is not None:
            rows = [revision for revision in rows if revision.knowledge_base_id == knowledge_base_id]
        kb_ids = sorted({revision.knowledge_base_id for revision in rows})
        kb_rows: dict[str, KnowledgeBase] = {}
        if kb_ids:
            for row in (await session.execute(select(KnowledgeBase).where(KnowledgeBase.resource_id.in_(kb_ids)))).scalars():
                kb_rows[row.resource_id] = row

        reachable = True
        for revision in rows:
            started = time.perf_counter()
            try:
                outcome, findings = await _check_revision(provider, revision)
            except KnowledgeProviderError:
                reachable = False
                outcome = "UNVERIFIED"
                findings = [{"kind": "provider_unreachable"}]
            check = KnowledgeRevisionCheck(
                id=str(uuid.uuid4()),
                knowledge_base_id=revision.knowledge_base_id,
                revision_id=revision.id,
                trigger=trigger,
                outcome=outcome,
                findings_json=findings,
                checked_by=checked_by,
                checked_at=datetime.now(UTC),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            session.add(check)
            revision.integrity_status = _OUTCOME_TO_INTEGRITY.get(outcome, INTEGRITY_UNVERIFIED)
            revision.integrity_checked_at = check.checked_at
            kb_row = kb_rows.get(revision.knowledge_base_id)
            if outcome == "UNVERIFIED" and kb_row is not None:
                kb_row.sync_status = "unreachable"
            summaries.append(
                {
                    "knowledge_base_id": revision.knowledge_base_id,
                    "revision_id": revision.id,
                    "revision_no": revision.revision_no,
                    "outcome": outcome,
                    "check_id": check.id,
                    "findings": findings,
                }
            )

        if reachable and rows:
            orphans = await _find_orphans(session, provider)
            if orphans:
                for kb_id in kb_ids:
                    findings = [{"kind": "orphan_dataset", "dataset_id": orphan} for orphan in orphans]
                    check = KnowledgeRevisionCheck(
                        id=str(uuid.uuid4()),
                        knowledge_base_id=kb_id,
                        revision_id=None,
                        trigger=trigger,
                        outcome="ORPHAN_PROVIDER_RESOURCE",
                        findings_json=findings,
                        checked_by=checked_by,
                        checked_at=datetime.now(UTC),
                        duration_ms=None,
                    )
                    session.add(check)
                    kb_row = kb_rows.get(kb_id)
                    if kb_row is not None:
                        kb_row.sync_status = "orphaned"
                    summaries.append(
                        {
                            "knowledge_base_id": kb_id,
                            "revision_id": None,
                            "revision_no": None,
                            "outcome": "ORPHAN_PROVIDER_RESOURCE",
                            "check_id": check.id,
                            "findings": findings,
                        }
                    )
            else:
                for kb_row in kb_rows.values():
                    if kb_row.sync_status == "ok":
                        continue
                    if kb_row.sync_status == "unreachable":
                        continue
                    kb_row.sync_status = "ok"
        elif not reachable:
            for kb_row in kb_rows.values():
                kb_row.sync_status = "unreachable"
        await session.commit()
    return summaries
