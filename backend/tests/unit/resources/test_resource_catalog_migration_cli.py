"""Command-line contracts for resource catalog migration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource, ResourceDependency
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.persistence.models.workflow_v2 import WorkflowDefinitionVersionRow
from ideer.scripts.resource_catalog_v2 import build_parser, run


def _legacy_layout(tmp_path: Path) -> tuple[Path, Path]:
    runtime = tmp_path / "runtime"
    agent = runtime / "users" / "owner" / "agents" / "writer"
    agent.mkdir(parents=True, exist_ok=True)
    (agent / "config.yaml").write_text("name: writer\nskills: [research]\n")
    (agent / "SOUL.md").write_text("Careful.\n")
    (agent / "memory.json").write_text('{"secret": true}')
    skills = tmp_path / "skills"
    skill = skills / "custom" / "research"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text("# Research\n")
    return runtime, skills


async def _make_database(tmp_path: Path, *, seed: bool = True) -> Path:
    database = tmp_path / "cli.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        existing = (await session.execute(select(ResourceMetadata.id).limit(1))).scalar_one_or_none()
        if seed and existing is None:
            session.add_all(
                [
                    ResourceMetadata(
                        id="legacy-skill",
                        resource_type="skill",
                        resource_id="research",
                        owner_id="owner",
                        department_id=None,
                        visibility="private",
                        version=3,
                    ),
                    ResourceMetadata(
                        id="legacy-agent",
                        resource_type="agent",
                        resource_id="writer",
                        owner_id="owner",
                        department_id=None,
                        visibility="private",
                        version=2,
                    ),
                    ResourceMetadata(
                        id="legacy-workflow",
                        resource_type="workflow",
                        resource_id="review-flow",
                        owner_id="owner",
                        department_id=None,
                        visibility="private",
                        version=4,
                    ),
                    WorkflowDefinitionVersionRow(
                        id="workflow-definition",
                        workflow_name="review-flow",
                        version=7,
                        definition={
                            "nodes": [
                                {
                                    "id": "draft",
                                    "type": "action",
                                    "action": {"kind": "agent", "name": "writer"},
                                }
                            ],
                            "edges": [],
                        },
                        content_hash="legacy-hash",
                        created_by="owner",
                    ),
                ]
            )
        await session.commit()
    await engine.dispose()
    return database


async def _run_cli(capsys: pytest.CaptureFixture[str], tmp_path: Path, *extra_args: str) -> tuple[int, dict]:
    runtime, skills = _legacy_layout(tmp_path)
    database = await _make_database(tmp_path)
    args = build_parser().parse_args(
        [
            *extra_args,
            "--database-url",
            f"sqlite+aiosqlite:///{database}",
            "--legacy-base-dir",
            str(runtime),
            "--skills-root",
            str(skills),
        ]
    )
    exit_code = await run(args)
    payload = json.loads(capsys.readouterr().out)
    return exit_code, payload


@pytest.mark.asyncio
async def test_rollback_cli_requires_explicit_backup_before_opening_database(tmp_path) -> None:
    args = build_parser().parse_args(
        [
            "rollback",
            "--legacy-base-dir",
            str(tmp_path / "runtime"),
            "--skills-root",
            str(tmp_path / "skills"),
        ]
    )

    with pytest.raises(ValueError, match="--backup-dir"):
        await run(args)


@pytest.mark.asyncio
async def test_audit_cli_is_read_only_and_emits_json(capsys, tmp_path) -> None:
    exit_code, payload = await _run_cli(capsys, tmp_path, "audit")

    assert exit_code == 0
    assert payload["command"] == "audit"
    assert payload["created"] == 0
    assert payload["errors"] == []
    assert [item["resource_type"] for item in payload["items"]] == ["agent", "skill", "workflow"]
    assert not (tmp_path / "runtime" / "resources").exists()


@pytest.mark.asyncio
async def test_migrate_cli_is_idempotent_and_emits_json(capsys, tmp_path) -> None:
    first_code, first = await _run_cli(capsys, tmp_path, "migrate")
    second_code, second = await _run_cli(capsys, tmp_path, "migrate")

    assert first_code == 0
    assert first["command"] == "migrate"
    assert first["created"] == 3
    assert first["errors"] == []
    assert all(item["content_hash"] for item in first["items"])
    assert second_code == 0
    assert second["created"] == 0
    assert second["unchanged"] == 3


@pytest.mark.asyncio
async def test_verify_cli_succeeds_after_migrate(capsys, tmp_path) -> None:
    migrate_code, _ = await _run_cli(capsys, tmp_path, "migrate")
    verify_code, payload = await _run_cli(capsys, tmp_path, "verify")

    assert migrate_code == 0
    assert verify_code == 0
    assert payload["command"] == "verify"
    assert payload["errors"] == []


@pytest.mark.asyncio
async def test_verify_cli_fails_when_canonical_content_is_tampered(capsys, tmp_path) -> None:
    migrate_code, migrate_payload = await _run_cli(capsys, tmp_path, "migrate")
    assert migrate_code == 0

    agent_item = next(item for item in migrate_payload["items"] if item["resource_type"] == "agent")
    version_dir = tmp_path / "runtime" / "resources" / "agents" / agent_item["resource_id"] / "versions" / "1"
    soul = version_dir / "SOUL.md"
    soul.chmod(0o644)
    soul.write_text("Tampered.\n")

    verify_code, payload = await _run_cli(capsys, tmp_path, "verify")

    assert verify_code == 1
    assert any("mismatched" in error for error in payload["errors"])


@pytest.mark.asyncio
async def test_verify_cli_fails_when_resource_is_missing(capsys, tmp_path) -> None:
    migrate_code, _ = await _run_cli(capsys, tmp_path, "migrate")
    assert migrate_code == 0
    (tmp_path / "runtime" / "resources").rename(tmp_path / "runtime" / "resources-moved")

    verify_code, payload = await _run_cli(capsys, tmp_path, "verify")

    assert verify_code == 1
    assert payload["errors"]


@pytest.mark.asyncio
async def test_rollback_cli_moves_files_to_backup_and_emits_json(capsys, tmp_path) -> None:
    migrate_code, migrate_payload = await _run_cli(capsys, tmp_path, "migrate")
    assert migrate_code == 0

    runtime, _ = _legacy_layout(tmp_path)
    backup = tmp_path / "rollback-backup"
    args = build_parser().parse_args(
        [
            "rollback",
            "--backup-dir",
            str(backup),
            "--database-url",
            f"sqlite+aiosqlite:///{tmp_path / 'cli.db'}",
            "--legacy-base-dir",
            str(runtime),
            "--skills-root",
            str(tmp_path / "skills"),
        ]
    )
    exit_code = await run(args)
    payload = json.loads(capsys.readouterr().out)

    agent_item = next(item for item in migrate_payload["items"] if item["resource_type"] == "agent")
    assert exit_code == 0
    assert payload["command"] == "rollback"
    assert payload["removed"] == 3
    assert (backup / "resources" / "agents" / agent_item["resource_id"]).is_dir()
    assert not (runtime / "resources" / "agents" / agent_item["resource_id"]).exists()
    assert (runtime / "users" / "owner" / "agents" / "writer" / "config.yaml").exists()


@pytest.mark.asyncio
async def test_compare_cli_requires_dual_mode(capsys, tmp_path, monkeypatch) -> None:
    runtime, skills = _legacy_layout(tmp_path)
    database = await _make_database(tmp_path)
    monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
    args = build_parser().parse_args(
        [
            "compare",
            "--database-url",
            f"sqlite+aiosqlite:///{database}",
            "--legacy-base-dir",
            str(runtime),
            "--skills-root",
            str(skills),
        ]
    )

    with pytest.raises(ValueError, match="dual mode"):
        await run(args)


@pytest.mark.asyncio
async def test_compare_cli_succeeds_after_migrate_and_emits_json(capsys, tmp_path) -> None:
    migrate_code, _ = await _run_cli(capsys, tmp_path, "migrate")
    compare_code, payload = await _run_cli(capsys, tmp_path, "compare")

    assert migrate_code == 0
    assert compare_code == 0
    assert payload["command"] == "compare"
    assert payload["ok"] == 3
    assert payload["errors"] == []
    assert payload["diverged"] == []
    assert payload["extras"] == []
    assert {item["status"] for item in payload["items"]} == {"ok"}


@pytest.mark.asyncio
async def test_compare_cli_fails_on_structural_mismatch(capsys, tmp_path) -> None:
    migrate_code, _ = await _run_cli(capsys, tmp_path, "migrate")
    assert migrate_code == 0
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'cli.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        agent = (await session.execute(select(Resource).where(Resource.type == "agent"))).scalar_one()
        await session.execute(delete(ResourceDependency).where(ResourceDependency.source_resource_id == agent.id))
        await session.commit()
    await engine.dispose()

    compare_code, payload = await _run_cli(capsys, tmp_path, "compare")

    assert compare_code == 1
    assert any("dependencies" in error for error in payload["errors"])


@pytest.mark.asyncio
async def test_cli_rejects_unknown_command(tmp_path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["unsupported"])
    assert excinfo.value.code == 2
