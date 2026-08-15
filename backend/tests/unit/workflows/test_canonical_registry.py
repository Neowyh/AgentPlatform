"""Canonical Workflow registry excludes legacy agents and excess runner tools."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
import ideer.tools.tools
from app.workflow_worker import build_canonical_registry
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource, ResourceVersion, RunResourceSnapshot
from ideer.resources.canonical_sandbox import canonical_run_key
from ideer.resources.storage import ResourceStorage
from ideer.workflows.v2.adapters import ActionResolutionError


@pytest.mark.asyncio
async def test_canonical_registry_uses_uuid_and_frozen_runner_tool_groups(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'registry.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    storage = ResourceStorage(tmp_path)
    agent_id = "9b1edb10-cadc-45b4-85f1-0fb427a066ec"
    source = tmp_path / "agent"
    source.mkdir()
    (source / "config.yaml").write_text("name: writer\ntool_groups: [read, write]\nskills: []\n")
    published = storage.publish_staged(storage.stage_directory("agent", agent_id, source), version=1)
    async with factory() as session:
        session.add_all(
            [
                Resource(
                    id=agent_id,
                    type="agent",
                    slug="writer",
                    display_name="Writer",
                    owner_id="owner",
                    visibility="public",
                    scope_department_id=None,
                    lifecycle_status="active",
                    latest_version=1,
                    draft_revision=0,
                    storage_kind="filesystem",
                    storage_key=f"agents/{agent_id}",
                    system_owned=False,
                    authz_revision=1,
                ),
                ResourceVersion(
                    id="agent-version",
                    resource_id=agent_id,
                    version=1,
                    content_hash=published.content_hash,
                    storage_key=published.storage_key,
                    scan_result={},
                    created_by="owner",
                ),
                RunResourceSnapshot(
                    id="agent-snapshot",
                    run_id="run-1",
                    root_resource_id=agent_id,
                    resource_id=agent_id,
                    version=1,
                    content_hash=published.content_hash,
                    authz_revision=1,
                ),
            ]
        )
        await session.commit()

    tools = [SimpleNamespace(name="read_file", group="read"), SimpleNamespace(name="write_file", group="write")]
    monkeypatch.setattr(
        ideer.tools.tools,
        "get_available_tools",
        lambda groups=None, app_config=None: [tool for tool in tools if groups is None or tool.group in groups],
    )
    run = SimpleNamespace(
        run_id="run-1",
        created_by="runner",
        runner_tool_groups=["read"],
    )

    registry = await build_canonical_registry(run, SimpleNamespace(), factory, storage)

    assert registry.resolve("agent", agent_id).definition.resource_id == agent_id
    assert registry.resolve("tool", "read_file").tool.name == "read_file"
    with pytest.raises(ActionResolutionError):
        registry.resolve("agent", "writer")
    with pytest.raises(ActionResolutionError):
        registry.resolve("tool", "write_file")
    assert (tmp_path / "resources" / "run-skill-views" / canonical_run_key("run-1") / "custom").is_dir()
    await engine.dispose()
