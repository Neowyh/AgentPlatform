#!/usr/bin/env python3
"""Seed the bundled fault-zeroing workflow into the workflow v2 definition store."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_workflow_path() -> Path:
    return repo_root() / "workflows" / "fault-zeroing.yaml"


def content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


def parse_bundled_workflow(path: Path) -> dict[str, Any]:
    """Parse and validate the bundled workflow YAML into a definition dict."""
    from ideer.workflows.v2.parser import parse_workflow_v2_file

    try:
        workflow = parse_workflow_v2_file(path)
    except Exception as exc:
        raise ValueError(f"Invalid workflow YAML at {path}: {exc}") from exc
    return workflow.model_dump(mode="json", by_alias=True)


async def _ensure_workflow_meta(
    session_factory, workflow_name: str, *, created_by: str
) -> None:
    """Create the resource_metadata row so workflow API endpoints resolve
    visibility/owner. An unknown owner (e.g. default 'system') fails the
    users_ext foreign key; the definition stays seeded and meta creation is
    skipped so the seed never hard-fails."""
    import uuid

    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from ideer.persistence.models.resource_metadata import ResourceMetadata

    async with session_factory() as session:
        stmt = select(ResourceMetadata).where(
            ResourceMetadata.resource_type == "workflow",
            ResourceMetadata.resource_id == workflow_name,
        )
        if (await session.execute(stmt)).scalar_one_or_none() is not None:
            return
        session.add(
            ResourceMetadata(
                id=str(uuid.uuid4()),
                resource_type="workflow",
                resource_id=workflow_name,
                owner_id=created_by,
                visibility="private",
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()


async def seed_workflow(
    store,
    workflow_path: Path,
    *,
    created_by: str = "system",
    session_factory=None,
) -> dict[str, Any]:
    """Idempotently seed the workflow definition, creating a new version on change."""
    definition = parse_bundled_workflow(workflow_path)
    name = definition["name"]
    digest = content_hash(workflow_path)

    latest = await store.get_latest_definition(name)
    if latest is not None and latest.content_hash == digest:
        if session_factory is not None:
            await _ensure_workflow_meta(session_factory, name, created_by=created_by)
        return {"status": "skipped", "workflow_name": name, "version": latest.version}

    row = await store.save_definition(name, definition, digest, created_by)
    if session_factory is not None:
        await _ensure_workflow_meta(session_factory, name, created_by=created_by)
    return {"status": "created", "workflow_name": name, "version": row.version}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the bundled fault-zeroing workflow into the iDeer workflow store."
    )
    parser.add_argument(
        "--workflow-path",
        default=str(default_workflow_path()),
        help="Path to the bundled fault-zeroing workflow YAML.",
    )
    parser.add_argument(
        "--created-by",
        default="system",
        help="Creator recorded on the definition version.",
    )
    return parser.parse_args(argv)


async def _seed(args: argparse.Namespace) -> int:
    from ideer.config import get_app_config
    from ideer.persistence.engine import (
        close_engine,
        get_session_factory,
        init_engine_from_config,
    )
    from ideer.workflows.v2.store import WorkflowV2Store

    workflow_path = Path(args.workflow_path).resolve()
    try:
        definition = parse_bundled_workflow(workflow_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    config = get_app_config()
    await init_engine_from_config(config.database)
    try:
        sf = get_session_factory()
        if sf is None:
            print(
                "Error: persistence engine not available (check config.database).",
                file=sys.stderr,
            )
            return 1
        result = await seed_workflow(
            WorkflowV2Store(sf),
            workflow_path,
            created_by=args.created_by,
            session_factory=sf,
        )
    finally:
        await close_engine()

    print(f"Workflow: {result['workflow_name']}")
    print(f"Status: {result['status']}")
    print(f"Version: {result['version']}")
    print(f"Definition id: {definition.get('id', '(none)')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    import asyncio

    return asyncio.run(_seed(parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
