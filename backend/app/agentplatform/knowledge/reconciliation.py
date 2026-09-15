"""Read-only reconciliation between published revisions and the provider (M4 ticket 05).

Reconciliation answers one question: does the provider still hold what each
published revision claims? Findings are recorded as immutable check history
and surfaced as revision integrity status; nothing here mutates provider
content, deletes orphans, rewrites manifests, or replaces run snapshots.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentplatform.knowledge.integrity import (
    INTEGRITY_DRIFTED,
    INTEGRITY_HEALTHY,
    INTEGRITY_MISSING_PROVIDER_DATASET,
    INTEGRITY_UNVERIFIED,
)
from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeRevision, KnowledgeRevisionCheck
from app.agentplatform.knowledge.provider import KnowledgeProvider, KnowledgeProviderError
from app.agentplatform.knowledge.revisions import PUBLISHED_DATASET_NAME_PREFIX
from app.agentplatform.knowledge.settings import config_value

_OUTCOME_TO_INTEGRITY = {
    "HEALTHY": INTEGRITY_HEALTHY,
    "UNVERIFIED": INTEGRITY_UNVERIFIED,
    "MISSING_PROVIDER_DATASET": INTEGRITY_MISSING_PROVIDER_DATASET,
    "MISSING_DOCUMENT": INTEGRITY_DRIFTED,
    "HASH_MISMATCH": INTEGRITY_DRIFTED,
    "ORPHAN_PROVIDER_RESOURCE": INTEGRITY_UNVERIFIED,
}


def configured_interval_seconds() -> int:
    """Read ``knowledge.reconciliation_interval_seconds`` (0 disables the loop)."""

    raw = config_value("reconciliation_interval_seconds")
    try:
        return max(0, int(raw)) if raw is not None else 0
    except (TypeError, ValueError):
        return 0


def _compare_provider_hash(provider_hash: object, expected: str | None) -> str:
    """Classify one provider-side content hash against the manifest hash.

    Only a 64-character hex digest can be the SHA-256 of the source bytes we
    hashed into the manifest. Anything else (absent, or a foreign digest such
    as RAGFlow's internal xxhash) can neither confirm nor contradict the
    manifest, so it is recorded as ``unverified`` — never a false HEALTHY and
    never a false HASH_MISMATCH.
    """

    text = str(provider_hash) if provider_hash is not None else ""
    if len(text) != 64 or any(character not in "0123456789abcdefABCDEF" for character in text):
        return "unverified"
    if expected is not None and text.lower() != expected.lower():
        return "hash_mismatch"
    return "verified"


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
        verdict = _compare_provider_hash(document.get("content_hash"), _expected_hash(revision, expected[document_id]))
        if verdict == "hash_mismatch":
            findings.append({**entry, "verdict": "hash_mismatch"})
        elif verdict == "unverified":
            findings.append({**entry, "verdict": "unverified", "reason": "provider exposes no verifiable sha-256 content hash"})
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
        if not name.startswith(PUBLISHED_DATASET_NAME_PREFIX):
            continue
        orphans.append(dataset_id)
    return sorted(orphans)


def _summary(revision_id: str | None, revision_no: int | None, kb_id: str | None, check: KnowledgeRevisionCheck, findings: list[dict]) -> dict[str, object]:
    return {
        "knowledge_base_id": kb_id,
        "revision_id": revision_id,
        "revision_no": revision_no,
        "outcome": check.outcome,
        "check_id": check.id,
        "findings": findings,
    }


def _record_check(
    session: AsyncSession,
    *,
    kb_id: str | None,
    revision_id: str | None,
    trigger: str,
    outcome: str,
    findings: list[dict],
    checked_by: str | None,
    started: float,
) -> KnowledgeRevisionCheck:
    check = KnowledgeRevisionCheck(
        id=str(uuid.uuid4()),
        knowledge_base_id=kb_id,
        revision_id=revision_id,
        trigger=trigger,
        outcome=outcome,
        findings_json=findings,
        checked_by=checked_by,
        checked_at=datetime.now(UTC),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    session.add(check)
    return check


async def run_reconciliation(
    session_factory: Callable[[], AsyncSession],
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
        rows = (await session.execute(select(KnowledgeRevision).where(KnowledgeRevision.status.in_(("published", "superseded"))).order_by(KnowledgeRevision.knowledge_base_id, KnowledgeRevision.revision_no))).scalars().all()
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
            check = _record_check(
                session,
                kb_id=revision.knowledge_base_id,
                revision_id=revision.id,
                trigger=trigger,
                outcome=outcome,
                findings=findings,
                checked_by=checked_by,
                started=started,
            )
            revision.integrity_status = _OUTCOME_TO_INTEGRITY.get(outcome, INTEGRITY_UNVERIFIED)
            revision.integrity_checked_at = check.checked_at
            kb_row = kb_rows.get(revision.knowledge_base_id)
            if outcome == "UNVERIFIED" and kb_row is not None:
                kb_row.sync_status = "unreachable"
            summaries.append(_summary(revision.id, revision.revision_no, revision.knowledge_base_id, check, findings))

        # Orphan scanning is workspace-level: it runs whenever the provider is
        # reachable, whether or not any published revision exists, and is
        # recorded once per run instead of once per KnowledgeBase.
        if reachable:
            orphans = await _find_orphans(session, provider)
            if orphans:
                findings = [{"kind": "orphan_dataset", "dataset_id": orphan} for orphan in orphans]
                check = _record_check(
                    session,
                    kb_id=None,
                    revision_id=None,
                    trigger=trigger,
                    outcome="ORPHAN_PROVIDER_RESOURCE",
                    findings=findings,
                    checked_by=checked_by,
                    started=time.perf_counter(),
                )
                for kb_row in kb_rows.values():
                    kb_row.sync_status = "orphaned"
                summaries.append(_summary(None, None, None, check, findings))
        else:
            for kb_row in kb_rows.values():
                kb_row.sync_status = "unreachable"
        await session.commit()
    return summaries
