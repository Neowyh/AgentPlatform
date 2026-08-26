"""Canonical Workflow Run creation freezes resources before queueing."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource, ResourceDependency, ResourceVersion, RunResourceSnapshot
from ideer.persistence.models.workflow_v2 import WorkflowTaskRow, WorkflowV2RunRow
from ideer.resources.service import ResourceAction, ResourceActor
from ideer.workflows.v2.store import WorkflowV2Store


def _resource(resource_id: str, resource_type: str, *, latest_version: int = 1) -> Resource:
    return Resource(
        id=resource_id,
        type=resource_type,
        slug=f"slug-{resource_id}",
        display_name=resource_id,
        owner_id="owner",
        visibility="public",
        scope_department_id=None,
        lifecycle_status="active",
        latest_version=latest_version,
        draft_revision=0,
        storage_kind="database" if resource_type == "workflow" else "filesystem",
        storage_key=f"{resource_type}s/{resource_id}",
        system_owned=False,
        authz_revision=1,
    )


@pytest.mark.asyncio
async def test_create_canonical_run_persists_snapshot_run_and_task_in_one_contract(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'canonical-run.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    workflow = _resource("workflow-id", "workflow")
    agent = _resource("agent-id", "agent")
    async with factory() as session:
        session.add_all(
            [
                workflow,
                agent,
                ResourceVersion(
                    id="workflow-version",
                    resource_id=workflow.id,
                    version=1,
                    content_hash="w" * 64,
                    storage_key=f"workflows/{workflow.id}/versions/1",
                    scan_result={},
                    content={
                        "schema_version": 2,
                        "name": workflow.slug,
                        "inputs": {
                            "request": {"type": "string", "required": True},
                            "count": {"type": "integer", "default": 2},
                        },
                        "state": {},
                        "entrypoint": "start",
                        "nodes": [
                            {
                                "id": "start",
                                "type": "action",
                                "action": {"kind": "agent", "name": agent.id},
                            }
                        ],
                        "edges": [],
                    },
                    created_by="owner",
                ),
                ResourceVersion(
                    id="agent-version",
                    resource_id=agent.id,
                    version=1,
                    content_hash="a" * 64,
                    storage_key=f"agents/{agent.id}/versions/1",
                    scan_result={},
                    created_by="owner",
                ),
                ResourceDependency(id="edge", source_resource_id=workflow.id, target_resource_id=agent.id),
            ]
        )
        await session.commit()

    actor = ResourceActor(
        user_id="runner",
        department_id="dept-a",
        role="user",
        permissions=frozenset({ResourceAction.READ, ResourceAction.USE}),
    )
    store = WorkflowV2Store(factory)

    run = await store.create_canonical_run("run-uuid", workflow.id, {"request": "x"}, actor)

    assert run.workflow_resource_id == workflow.id
    assert run.workflow_name == workflow.slug
    assert run.definition_version == 1
    assert run.inputs == {"request": "x", "count": 2}
    assert run.runner_tool_groups is None
    async with factory() as session:
        snapshots = list((await session.execute(select(RunResourceSnapshot).where(RunResourceSnapshot.run_id == run.run_id))).scalars())
        task = (await session.execute(select(WorkflowTaskRow).where(WorkflowTaskRow.run_id == run.run_id))).scalar_one()
        persisted = await session.get(WorkflowV2RunRow, run.run_id)
        assert {row.resource_id for row in snapshots} == {workflow.id, agent.id}
        assert task.status == "queued"
        assert persisted is not None and persisted.status == "queued"
        assert persisted.model_name is None

    modelled_run = await store.create_canonical_run(
        "run-uuid-model",
        workflow.id,
        {"request": "x"},
        actor,
        model_name="gpt-test",
    )
    assert modelled_run.model_name == "gpt-test"
    async with factory() as session:
        persisted_modelled = await session.get(WorkflowV2RunRow, "run-uuid-model")
        assert persisted_modelled is not None
        assert persisted_modelled.model_name == "gpt-test"

    with pytest.raises(ValueError, match="Input 'count' expects integer"):
        await store.create_canonical_run(
            "invalid-run",
            workflow.id,
            {"request": "x", "count": "two"},
            actor,
        )
    async with factory() as session:
        assert await session.get(WorkflowV2RunRow, "invalid-run") is None
        invalid_snapshots = list((await session.execute(select(RunResourceSnapshot).where(RunResourceSnapshot.run_id == "invalid-run"))).scalars())
        assert invalid_snapshots == []
    await engine.dispose()
