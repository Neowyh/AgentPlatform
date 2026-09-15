"""Published Revision reconciliation and drift visibility (M4 ticket 05)."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.agentplatform.audit_model  # noqa: F401 - register audit_logs
import app.agentplatform.rbac_models  # noqa: F401 - register users_ext
import app.agentplatform.resource_models  # noqa: F401 - register resource tables
import app.agentplatform.visibility_models  # noqa: F401 - register visibility tables
from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeRevision
from app.agentplatform.knowledge.provider import KnowledgeProviderError
from app.agentplatform.knowledge.reconciliation import run_reconciliation
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceAction, ResourceActor, ResourceConflict, ResourceService
from deerflow.persistence.base import Base


class FakeReconciliationProvider:
    """Controllable provider whose reads never mutate anything."""

    def __init__(
        self,
        *,
        datasets: dict[str, list[dict]] | None = None,
        missing_datasets: set[str] | None = None,
        extra_datasets: list[str] | None = None,
        fail_reads_for: set[str] | None = None,
    ) -> None:
        self.datasets = datasets or {}
        self.missing_datasets = missing_datasets or set()
        self.extra_datasets = extra_datasets or []
        self.fail_reads_for = fail_reads_for or set()
        self.read_calls: list[str] = []
        self.mutations: list[str] = []

    async def list_datasets(self, *, dataset_id: str | None = None) -> list[dict]:
        self.read_calls.append(f"list_datasets:{dataset_id or 'all'}")
        if dataset_id is not None:
            if dataset_id in self.missing_datasets:
                return []
            if dataset_id in self.fail_reads_for:
                raise KnowledgeProviderError("unavailable")
            return [{"id": dataset_id, "name": f"dataset-{dataset_id}"}]
        known = [{"id": key, "name": f"dataset-{key}"} for key in self.datasets if key not in self.missing_datasets]
        orphans = [{"id": value, "name": value} for value in self.extra_datasets]
        return known + orphans

    async def list_dataset_documents(self, *, dataset_id: str) -> list[dict]:
        self.read_calls.append(f"list_dataset_documents:{dataset_id}")
        if dataset_id in self.fail_reads_for:
            raise KnowledgeProviderError("unavailable")
        return list(self.datasets.get(dataset_id, []))

    async def create_dataset(self, *, name: str) -> str:
        self.mutations.append(f"create_dataset:{name}")
        raise AssertionError("reconciliation must never create datasets")

    async def ingest(self, **kwargs) -> None:
        self.mutations.append(f"ingest:{kwargs}")

    async def delete_document(self, **kwargs) -> None:
        self.mutations.append(f"delete_document:{kwargs}")


@pytest_asyncio.fixture
async def store(tmp_path) -> AsyncIterator[tuple[AsyncSession, async_sessionmaker]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reconcile.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session, factory
    await engine.dispose()


def _actor(user_id: str = "admin") -> ResourceActor:
    return ResourceActor(
        user_id=user_id,
        department_id=None,
        role="super_admin",
        permissions=frozenset(ResourceAction),
    )


async def _seed_kb(session: AsyncSession, slug: str = "reconcile") -> Resource:
    kb = await ResourceService(session, _actor("owner")).create_resource(
        resource_type="knowledge_base",
        slug=slug,
        display_name=slug,
        storage_kind="database",
    )
    kb.latest_version = 1
    kb.draft_revision = 1
    from app.agentplatform.resource_models import ResourceVersion

    session.add(
        ResourceVersion(
            id=str(uuid.uuid4()),
            resource_id=kb.id,
            version=1,
            content_hash=hashlib.sha256(slug.encode()).hexdigest(),
            storage_key=f"knowledge_bases/{kb.id}",
            scan_result={},
            content={},
            created_by=kb.owner_id,
        )
    )
    await session.commit()
    return kb


def _published_revision(session: AsyncSession, kb: Resource, *, revision_no: int = 1, dataset_id: str | None = None) -> KnowledgeRevision:
    row = KnowledgeRevision(
        id=f"{kb.slug}-rev-{revision_no}",
        knowledge_base_id=kb.id,
        revision_no=revision_no,
        status="published",
        manifest_hash="a" * 64,
        manifest_json=[{"document_id": "doc-1", "filename": "guide.txt", "content_hash": "a" * 64}],
        provider_doc_map_json={"doc-1": f"provider-doc-{kb.slug}-{revision_no}"},
        document_count=1,
        provider_dataset_id=dataset_id or f"{kb.slug}-dataset-{revision_no}",
        publish_attempt=1,
        created_by=kb.owner_id,
        published_at=datetime.now(UTC),
    )
    session.add(row)
    return row


async def _activate(session: AsyncSession, kb: Resource, revision: KnowledgeRevision) -> None:
    kb_row = (await session.execute(select(KnowledgeBase).where(KnowledgeBase.resource_id == kb.id))).scalar_one()
    kb_row.active_revision_id = revision.id
    await session.commit()


async def _integrity(session: AsyncSession, revision_id: str) -> KnowledgeRevision:
    fresh = (await session.execute(select(KnowledgeRevision).where(KnowledgeRevision.id == revision_id))).scalar_one()
    return fresh


@pytest.mark.asyncio
async def test_healthy_revision_reports_no_drift(store) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = _published_revision(session, kb, dataset_id="healthy-dataset")
    await _activate(session, kb, revision)

    provider = FakeReconciliationProvider(datasets={"healthy-dataset": [{"id": "provider-doc-reconcile-1", "name": "guide.txt", "content_hash": "a" * 64}]})
    checks = await run_reconciliation(factory, provider=provider, trigger="manual", checked_by="admin")
    await session.commit()

    assert len(checks) == 1
    assert checks[0]["outcome"] == "HEALTHY"
    fresh = await _integrity(session, revision.id)
    assert fresh.integrity_status == "healthy"
    kb_row = (await session.execute(select(KnowledgeBase).where(KnowledgeBase.resource_id == kb.id))).scalar_one()
    assert kb_row.sync_status == "ok"
    assert provider.mutations == []


@pytest.mark.asyncio
async def test_missing_provider_dataset_is_reported(store) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = _published_revision(session, kb, dataset_id="vanished-dataset")
    await _activate(session, kb, revision)

    provider = FakeReconciliationProvider(missing_datasets={"vanished-dataset"})
    checks = await run_reconciliation(factory, provider=provider, trigger="manual", checked_by="admin")
    await session.commit()

    assert checks[0]["outcome"] == "MISSING_PROVIDER_DATASET"
    fresh = await _integrity(session, revision.id)
    assert fresh.integrity_status == "missing_provider_dataset"
    assert provider.mutations == []


@pytest.mark.asyncio
async def test_missing_document_is_drift(store) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = _published_revision(session, kb, dataset_id="partial-dataset")
    await _activate(session, kb, revision)

    provider = FakeReconciliationProvider(datasets={"partial-dataset": []})
    checks = await run_reconciliation(factory, provider=provider, trigger="manual", checked_by="admin")
    await session.commit()

    assert checks[0]["outcome"] == "MISSING_DOCUMENT"
    fresh = await _integrity(session, revision.id)
    assert fresh.integrity_status == "drifted"


@pytest.mark.asyncio
async def test_hash_verifiable_mismatch_is_reported_without_false_health(store) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = _published_revision(session, kb, dataset_id="tampered-dataset")
    await _activate(session, kb, revision)

    provider = FakeReconciliationProvider(datasets={"tampered-dataset": [{"id": "provider-doc-reconcile-1", "name": "guide.txt", "content_hash": "b" * 64}]})
    checks = await run_reconciliation(factory, provider=provider, trigger="manual", checked_by="admin")
    await session.commit()

    assert checks[0]["outcome"] == "HASH_MISMATCH"
    fresh = await _integrity(session, revision.id)
    assert fresh.integrity_status == "drifted"

    # Without a verifiable hash the same shape stays UNVERIFIED, never HEALTHY.
    revision_two = _published_revision(session, kb, revision_no=2, dataset_id="nohash-dataset")
    kb_row = (await session.execute(select(KnowledgeBase).where(KnowledgeBase.resource_id == kb.id))).scalar_one()
    kb_row.active_revision_id = revision_two.id
    await session.commit()
    provider.datasets["nohash-dataset"] = [{"id": "provider-doc-reconcile-2", "name": "guide-2.txt"}]
    checks = await run_reconciliation(factory, provider=provider, trigger="scheduled", checked_by=None)
    summary = next(item for item in checks if item["revision_id"] == revision_two.id)
    assert summary["outcome"] == "UNVERIFIED"
    fresh = await _integrity(session, revision_two.id)
    assert fresh.integrity_status == "unverified"


@pytest.mark.asyncio
async def test_unreachable_provider_is_never_reported_healthy_or_missing(store) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = _published_revision(session, kb, dataset_id="dark-dataset")
    await _activate(session, kb, revision)

    provider = FakeReconciliationProvider(fail_reads_for={"dark-dataset"})
    checks = await run_reconciliation(factory, provider=provider, trigger="manual", checked_by="admin")
    await session.commit()

    assert checks[0]["outcome"] == "UNVERIFIED"
    fresh = await _integrity(session, revision.id)
    assert fresh.integrity_status == "unverified"
    kb_row = (await session.execute(select(KnowledgeBase).where(KnowledgeBase.resource_id == kb.id))).scalar_one()
    assert kb_row.sync_status == "unreachable"


@pytest.mark.asyncio
async def test_orphan_provider_datasets_are_visible_but_untouched(store) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = _published_revision(session, kb, dataset_id="bound-dataset")
    await _activate(session, kb, revision)

    provider = FakeReconciliationProvider(
        datasets={"bound-dataset": [{"id": "provider-doc-reconcile-1", "name": "guide.txt", "content_hash": "a" * 64}]},
        extra_datasets=["ideer-kb-stray"],
    )
    checks = await run_reconciliation(factory, provider=provider, trigger="manual", checked_by="admin")
    await session.commit()

    outcomes = [check["outcome"] for check in checks]
    assert "ORPHAN_PROVIDER_RESOURCE" in outcomes
    assert "HEALTHY" in outcomes
    assert provider.mutations == []


@pytest.mark.asyncio
async def test_drifted_revision_cannot_anchor_pinned_or_live_runs(store) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = _published_revision(session, kb, dataset_id="drifted-dataset")
    await _activate(session, kb, revision)

    provider = FakeReconciliationProvider(datasets={"drifted-dataset": []})
    await run_reconciliation(factory, provider=provider, trigger="manual", checked_by="admin")
    await session.commit()

    fresh = await _integrity(session, revision.id)
    assert fresh.integrity_status == "drifted"

    agent = await ResourceService(session, _actor("owner")).create_resource(
        resource_type="agent",
        slug="pinned-drift",
        display_name="pinned-drift",
        storage_kind="filesystem",
    )
    agent.latest_version = 1
    agent.draft_revision = 1
    from app.agentplatform.resource_models import ResourceVersion

    session.add(
        ResourceVersion(
            id=str(uuid.uuid4()),
            resource_id=agent.id,
            version=1,
            content_hash="c" * 64,
            storage_key=f"agents/{agent.id}",
            scan_result={},
            content={},
            created_by=agent.owner_id,
        )
    )
    await session.commit()
    service = ResourceService(session, _actor("owner"))

    # Saving a pinned declaration against a drifted revision is rejected…
    with pytest.raises(ResourceConflict, match="not usable"):
        await service.replace_dependencies(
            agent.id,
            [{"resource_id": kb.id, "dependency_mode": "pinned", "revision_id": revision.id}],
        )

    # …and a LIVE dependency against the drifted active revision is rejected too.
    from app.agentplatform.resource_models import ResourceDependency

    session.add(ResourceDependency(id=str(uuid.uuid4()), source_resource_id=agent.id, target_resource_id=kb.id, dependency_mode="live"))
    await session.commit()
    with pytest.raises(ResourceConflict, match="drifted"):
        await service.resolve_dependency_closure(agent.id)


@pytest.mark.asyncio
async def test_non_sha256_provider_hash_is_unverified_not_a_mismatch(store) -> None:
    """RAGFlow exposes non-SHA-256 digests (e.g. xxhash128); those can never
    confirm or contradict our manifest, so the document stays UNVERIFIED."""
    session, factory = store
    kb = await _seed_kb(session)
    revision = _published_revision(session, kb, dataset_id="xxhash-dataset")
    await _activate(session, kb, revision)

    provider = FakeReconciliationProvider(datasets={"xxhash-dataset": [{"id": "provider-doc-reconcile-1", "name": "guide.txt", "content_hash": "deadbeef" * 4}]})
    checks = await run_reconciliation(factory, provider=provider, trigger="manual", checked_by="admin")
    await session.commit()

    assert checks[0]["outcome"] == "UNVERIFIED"
    fresh = await _integrity(session, revision.id)
    assert fresh.integrity_status == "unverified"


@pytest.mark.asyncio
async def test_matching_sha256_provider_hash_is_healthy(store) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = _published_revision(session, kb, dataset_id="matching-dataset")
    await _activate(session, kb, revision)

    provider = FakeReconciliationProvider(datasets={"matching-dataset": [{"id": "provider-doc-reconcile-1", "name": "guide.txt", "content_hash": "a" * 64}]})
    checks = await run_reconciliation(factory, provider=provider, trigger="manual", checked_by="admin")
    assert checks[0]["outcome"] == "HEALTHY"


@pytest.mark.asyncio
async def test_orphans_are_visible_without_published_revisions(store) -> None:
    """Orphan scanning must not be gated on published revisions existing."""
    session, factory = store
    await _seed_kb(session)  # no revision at all

    provider = FakeReconciliationProvider(extra_datasets=["ideer-kb-stray"])
    checks = await run_reconciliation(factory, provider=provider, trigger="manual", checked_by="admin")
    await session.commit()

    orphan_checks = [check for check in checks if check["outcome"] == "ORPHAN_PROVIDER_RESOURCE"]
    assert len(orphan_checks) == 1


@pytest.mark.asyncio
async def test_orphan_findings_are_recorded_once_per_run(store) -> None:
    """The same orphan dataset is one finding, not one per KnowledgeBase."""
    session, factory = store
    first = await _seed_kb(session, slug="kb-a")
    second = await _seed_kb(session, slug="kb-b")
    revision_a = _published_revision(session, first, dataset_id="dataset-a")
    revision_b = _published_revision(session, second, dataset_id="dataset-b")
    await _activate(session, first, revision_a)
    await _activate(session, second, revision_b)

    provider = FakeReconciliationProvider(
        datasets={
            "dataset-a": [{"id": "provider-doc-kb-a-1", "name": "guide.txt", "content_hash": "a" * 64}],
            "dataset-b": [{"id": "provider-doc-kb-b-1", "name": "guide.txt", "content_hash": "a" * 64}],
        },
        extra_datasets=["ideer-kb-stray"],
    )
    checks = await run_reconciliation(factory, provider=provider, trigger="manual", checked_by="admin")
    await session.commit()

    orphan_checks = [check for check in checks if check["outcome"] == "ORPHAN_PROVIDER_RESOURCE"]
    assert len(orphan_checks) == 1
