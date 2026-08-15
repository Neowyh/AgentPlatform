#!/usr/bin/env python3
"""Provision manifest-declared bundled resources into the canonical catalog."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Seed stable-UUID bundled Skill, Agent, and Workflow resources.",
    )
    parser.add_argument(
        "--manifest",
        default=str(root / "bundled-resources.json"),
    )
    parser.add_argument("--source-root", default=str(root))
    parser.add_argument(
        "--owner",
        required=True,
        help="Existing system/super-admin user id used as the immutable FK owner.",
    )
    return parser.parse_args(argv)


async def _seed(args: argparse.Namespace) -> int:
    from sqlalchemy import select

    from ideer.config import get_app_config, get_paths
    from ideer.persistence.engine import (
        close_engine,
        get_session_factory,
        init_engine_from_config,
    )
    from ideer.persistence.models.user import UserModel
    from ideer.resources.bundled import seed_bundled_resources
    from ideer.resources.storage import ResourceStorage

    manifest_path = Path(args.manifest).resolve()
    source_root = Path(args.source_root).resolve()
    if not manifest_path.is_file():
        print(f"Error: bundled resource manifest not found: {manifest_path}", file=sys.stderr)
        return 1
    config = get_app_config()
    await init_engine_from_config(config.database)
    try:
        factory = get_session_factory()
        if factory is None:
            print("Error: persistence engine is not initialized", file=sys.stderr)
            return 1
        async with factory() as session:
            owner_exists = await session.scalar(
                select(UserModel.id).where(UserModel.id == args.owner)
            )
        if owner_exists is None:
            print(f"Error: bundled resource owner does not exist: {args.owner}", file=sys.stderr)
            return 1
        report = await seed_bundled_resources(
            factory,
            ResourceStorage(
                get_paths().base_dir,
                allow_scanned_executables=True,
            ),
            manifest_path=manifest_path,
            source_root=source_root,
            owner_id=args.owner,
        )
    except Exception as exc:
        print(f"Error: bundled resource seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await close_engine()
    print(f"Bundled resources created: {report.created}")
    print(f"Bundled resources updated: {report.updated}")
    print(f"Bundled resources unchanged: {report.unchanged}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_seed(parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
