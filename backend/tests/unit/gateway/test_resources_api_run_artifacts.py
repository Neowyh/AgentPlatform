"""Run artifact resolution: canonical runs read the frozen resource snapshot,
legacy runs fall back to the definition store."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from app.gateway.routers import resources
from ideer.config.paths import Paths
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource, ResourceVersion, RunResourceSnapshot
from ideer.persistence.models.user import UserModel, UserRole
from ideer.workflows.v2 import file_roots
from ideer.workflows.v2.store import WorkflowV2Store

WRITE_ROOT = "/mnt/user-data/outputs"


def _definition() -> dict:
    return {
        "schema_version": 2,
        "name": "fault-zeroing",
        "entrypoint": "gen",
        "nodes": [
            {
                "id": "gen",
                "type": "action",
                "action": {
                    "kind": "tool",
                    "name": "write_file",
                    "file_access": {"write": [WRITE_ROOT]},
                },
            }
        ],
        "edges": [],
    }


def _run(*, workflow_resource_id: str | None, definition_version: int = 3) -> SimpleNamespace:
    return SimpleNamespace(
        run_id="run-1",
        created_by="user-1",
        workflow_name="fault-zeroing",
        workflow_resource_id=workflow_resource_id,
        definition_version=definition_version,
        inputs={},
        snapshot={},
    )


def _seed_canonical_rows(session, resource_id: str, *, with_version: bool = True) -> None:
    session.add(
        Resource(
            id=resource_id,
            type="workflow",
            slug="fault-zeroing",
            display_name="fault-zeroing",
            owner_id="user-1",
            visibility="public",
            lifecycle_status="active",
            latest_version=3 if with_version else 0,
            draft_revision=0,
            storage_kind="database",
            storage_key=f"workflows/{resource_id}",
            provenance="bundled",
            system_owned=True,
            authz_revision=1,
        )
    )
    if with_version:
        session.add(
            ResourceVersion(
                id=str(uuid.uuid4()),
                resource_id=resource_id,
                version=3,
                content_hash="hash-v3",
                storage_key=f"workflows/{resource_id}/versions/3",
                scan_result={},
                content=_definition(),
                created_by="user-1",
            )
        )
    session.add(
        RunResourceSnapshot(
            id=str(uuid.uuid4()),
            run_id="run-1",
            root_resource_id=resource_id,
            resource_id=resource_id,
            version=3,
            content_hash="hash-v3",
            authz_revision=1,
        )
    )


async def _make_store(tmp_path: Path) -> tuple[WorkflowV2Store, async_sessionmaker, Paths]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'artifacts.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            UserModel(
                id="user-1",
                username="user-1@test.com",
                role=UserRole.USER,
                department_id=None,
                disabled=False,
            )
        )
        await session.commit()
    base = Paths(str(tmp_path / "base"))
    return WorkflowV2Store(factory), factory, base


async def _write_artifact(base: Paths) -> None:
    host = base.sandbox_outputs_dir("run-1", user_id="user-1")
    host.mkdir(parents=True, exist_ok=True)
    (host / "report.md").write_text("done", encoding="utf-8")


@pytest.mark.asyncio
async def test_canonical_run_artifacts_resolve_from_frozen_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, factory, base = await _make_store(tmp_path)
    monkeypatch.setattr(file_roots, "get_paths", lambda: base)
    async with factory() as session:
        _seed_canonical_rows(session, "wf-1")
        await session.commit()
    await _write_artifact(base)

    artifacts = await resources._run_artifacts(store, _run(workflow_resource_id="wf-1"))

    assert len(artifacts) == 1
    assert artifacts[0]["path"] == f"{WRITE_ROOT}/report.md"
    assert artifacts[0]["size"] == 4


@pytest.mark.asyncio
async def test_canonical_run_missing_version_falls_back_to_definition_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, factory, base = await _make_store(tmp_path)
    monkeypatch.setattr(file_roots, "get_paths", lambda: base)
    async with factory() as session:
        _seed_canonical_rows(session, "wf-1", with_version=False)
        await session.commit()
    await store.save_definition("fault-zeroing", _definition(), "hash-v1", "user-1")
    await _write_artifact(base)

    artifacts = await resources._run_artifacts(store, _run(workflow_resource_id="wf-1"))

    assert len(artifacts) == 1
    assert artifacts[0]["path"] == f"{WRITE_ROOT}/report.md"


@pytest.mark.asyncio
async def test_legacy_run_uses_latest_definition_when_exact_version_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _factory, base = await _make_store(tmp_path)
    monkeypatch.setattr(file_roots, "get_paths", lambda: base)
    await store.save_definition("fault-zeroing", _definition(), "hash-v1", "user-1")
    await _write_artifact(base)

    run = _run(workflow_resource_id=None, definition_version=5)
    artifacts = await resources._run_artifacts(store, run)

    assert len(artifacts) == 1
    assert artifacts[0]["path"] == f"{WRITE_ROOT}/report.md"


@pytest.mark.asyncio
async def test_run_without_any_definition_returns_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, factory, base = await _make_store(tmp_path)
    monkeypatch.setattr(file_roots, "get_paths", lambda: base)
    async with factory() as session:
        _seed_canonical_rows(session, "wf-1", with_version=False)
        await session.commit()

    artifacts = await resources._run_artifacts(store, _run(workflow_resource_id="wf-1"))

    assert artifacts == []
