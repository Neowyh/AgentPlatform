"""Initialized-database acceptance for the canonical Workflow Run snapshot.

The unit suite covers the run-evidence envelope merge with in-memory fakes;
this module freezes the snapshot against a real seeded catalog
(``ResourceService`` + SQLite) and asserts the adoption-matrix closure
behaviors on the persisted row:

- the dependency closure (workflow -> agent -> skill) freezes as
  UUID/version/hash at run creation,
- publishing a new dependency version mid-run does not move the frozen
  snapshot (upgrade regression §24-A),
- a worker recovery snapshot update preserves the immutable ``run_evidence``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from _resource_catalog import publish_resource
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agentplatform.resources.runtime import _json_hash
from app.agentplatform.resources.service import (
    ResourceAction,
    ResourceActor,
    ResourceService,
)
from app.agentplatform.workflows.v2.store import WorkflowV2Store
from deerflow.persistence.base import Base

MINIMAL_DEFINITION = {
    "schema_version": 2,
    "name": "snapshot-freeze",
    "description": "Minimal canonical workflow for snapshot acceptance",
    "inputs": {},
    "state": {},
    "entrypoint": "work",
    "nodes": [
        {
            "id": "work",
            "type": "action",
            "action": {"kind": "agent", "name": "snapshot-agent"},
        }
    ],
    "edges": [],
}


@pytest_asyncio.fixture
async def durable_store(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'workflow.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def seeded_catalog(durable_store):
    """Publish workflow -> agent -> skill, all at version 1, and wire edges."""
    actor = ResourceActor(
        user_id="owner-1",
        department_id=None,
        role="super_admin",
        permissions=frozenset({ResourceAction.READ, ResourceAction.WRITE, ResourceAction.USE}),
        tool_groups=None,
    )
    async with durable_store() as session:
        service = ResourceService(session, actor)
        skill, _ = await publish_resource(service, resource_type="skill", slug="snapshot-skill", storage_kind="filesystem", content={"name": "snapshot-skill", "description": "frozen skill"})
        agent, _ = await publish_resource(service, resource_type="agent", slug="snapshot-agent", storage_kind="filesystem", content={"name": "snapshot-agent", "description": "frozen agent"})
        workflow, _ = await publish_resource(service, resource_type="workflow", slug="snapshot-freeze", storage_kind="database", content=MINIMAL_DEFINITION)
        await service.replace_dependencies(agent.id, [skill.id])
        await service.replace_dependencies(workflow.id, [agent.id])
        await session.commit()
        return {"workflow": workflow.id, "agent": agent.id, "skill": skill.id}


async def _publish_new_version(durable_store, resource_id: str, content: dict) -> int:
    actor = ResourceActor(
        user_id="owner-1",
        department_id=None,
        role="super_admin",
        permissions=frozenset({ResourceAction.READ, ResourceAction.WRITE, ResourceAction.USE}),
        tool_groups=None,
    )
    async with durable_store() as session:
        service = ResourceService(session, actor)
        resource = await service.get_visible(resource_id)
        await service.save_draft(
            resource_id,
            expected_revision=resource.draft_revision,
            content_hash=_json_hash(content),
            storage_key=f"{resource.storage_key}/versions/{resource.latest_version + 1}",
            content=content,
        )
        version = await service.publish(resource_id, expected_draft_revision=resource.draft_revision, scan_result={})
        await session.commit()
        return version.version


def _owner_actor() -> ResourceActor:
    return ResourceActor(
        user_id="owner-1",
        department_id=None,
        role="super_admin",
        permissions=frozenset({ResourceAction.READ, ResourceAction.USE}),
        tool_groups=None,
    )


@pytest.mark.asyncio
async def test_canonical_run_freezes_dependency_closure_with_uuid_version_hash(
    durable_store,
    seeded_catalog: dict[str, str],
) -> None:
    store = WorkflowV2Store(durable_store)
    run_id = f"run-freeze-{uuid4().hex[:8]}"

    await store.create_canonical_run(run_id, seeded_catalog["workflow"], {}, _owner_actor())

    run = await store.get_run(run_id)
    assert run is not None and run.status == "queued"
    evidence = run.snapshot["run_evidence"]
    assert evidence["authorization_context"]["caller_user_id"] == "owner-1"
    assert evidence["authorization_context"]["memory_scope"] == "owner-1"
    assert evidence["authorization_context"]["effective_agent_id"] == seeded_catalog["workflow"]

    snapshots = {row["resource_id"]: row for row in evidence["resource_snapshots"]}
    assert set(snapshots) == set(seeded_catalog.values())
    assert snapshots[seeded_catalog["workflow"]]["selection_role"] == "root"
    assert snapshots[seeded_catalog["agent"]]["selection_role"] == "resolved"
    assert snapshots[seeded_catalog["skill"]]["selection_role"] == "resolved"
    for resource_id in seeded_catalog.values():
        assert snapshots[resource_id]["version"] == 1
        assert len(snapshots[resource_id]["content_hash"]) == 64
    assert evidence["policy_revision"] == "1"


@pytest.mark.asyncio
async def test_publishing_dependency_version_mid_run_does_not_move_frozen_snapshot(
    durable_store,
    seeded_catalog: dict[str, str],
) -> None:
    store = WorkflowV2Store(durable_store)
    run_id = f"run-freeze-{uuid4().hex[:8]}"
    await store.create_canonical_run(run_id, seeded_catalog["workflow"], {}, _owner_actor())
    before = (await store.get_run(run_id)).snapshot["run_evidence"]

    new_version = await _publish_new_version(
        durable_store,
        seeded_catalog["agent"],
        {"name": "snapshot-agent", "description": "agent v2 published mid-run"},
    )
    assert new_version == 2

    after = (await store.get_run(run_id)).snapshot["run_evidence"]
    assert before == after, "frozen run evidence must be immutable across mid-run publishes"


@pytest.mark.asyncio
async def test_worker_recovery_update_preserves_run_evidence_in_persisted_row(
    durable_store,
    seeded_catalog: dict[str, str],
) -> None:
    store = WorkflowV2Store(durable_store)
    run_id = f"run-freeze-{uuid4().hex[:8]}"
    await store.create_canonical_run(run_id, seeded_catalog["workflow"], {}, _owner_actor())

    task = await store.claim_next_task("worker-recovery")
    assert task is not None and task.run_id == run_id

    recovered = await store.update_snapshot(
        run_id,
        {"completed_nodes": ["work"], "checkpoint_state": {"messages": 3}},
        worker_id="worker-recovery",
    )
    assert recovered is True

    run = await store.get_run(run_id)
    assert run.snapshot["completed_nodes"] == ["work"]
    assert run.snapshot["checkpoint_state"] == {"messages": 3}
    # The mutable recovery merge must not drop the immutable evidence envelope.
    evidence = run.snapshot["run_evidence"]
    assert evidence is not None
    assert evidence["authorization_context"]["caller_user_id"] == "owner-1"
    assert len(evidence["resource_snapshots"]) == 3
