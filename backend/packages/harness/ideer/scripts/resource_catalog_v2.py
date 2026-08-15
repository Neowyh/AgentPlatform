"""Audit, migrate, verify, roll back, or compare the canonical resource catalog."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ideer.resources.compare import ComparisonReport, DualModeComparator
from ideer.resources.migration import CatalogMigrationReport, LegacyResourceMigrator
from ideer.resources.mode import ResourceCatalogMode, get_resource_catalog_mode
from ideer.resources.storage import ResourceStorage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit", "migrate", "verify", "rollback", "compare"))
    parser.add_argument("--database-url", help="SQLAlchemy async URL; defaults to <legacy-base-dir>/data/ideer.db")
    parser.add_argument(
        "--legacy-base-dir",
        type=Path,
        default=Path(os.environ.get("IDEER_HOME", ".ideer")),
        help="Existing IDEER_HOME containing users/ and agents/",
    )
    parser.add_argument("--skills-root", type=Path, default=Path("../skills"), help="Existing skills root containing custom/")
    parser.add_argument("--backup-dir", type=Path, help="Required, new backup directory for rollback")
    return parser


def _payload(command: str, report: CatalogMigrationReport) -> dict:
    return {
        "command": command,
        "created": report.created,
        "unchanged": report.unchanged,
        "removed": report.removed,
        "errors": report.errors,
        "items": [
            {
                "resource_type": item.resource_type,
                "slug": item.slug,
                "owner_id": item.owner_id,
                "resource_id": item.resource_id,
                "content_hash": item.content_hash,
                "error": item.error,
            }
            for item in report.items
        ],
    }


def _compare_payload(report: ComparisonReport) -> dict:
    return {
        "command": "compare",
        "total": len(report.items),
        "ok": report.ok_count,
        "diverged": report.diverged,
        "errors": report.errors,
        "extras": report.extras,
        "items": [
            {
                "resource_type": item.resource_type,
                "slug": item.slug,
                "owner_id": item.owner_id,
                "resource_id": item.resource_id,
                "status": item.status,
                "error": item.error,
            }
            for item in report.items
        ],
    }


async def run(args: argparse.Namespace) -> int:
    legacy_base_dir = args.legacy_base_dir.resolve()
    database_url = args.database_url or f"sqlite+aiosqlite:///{legacy_base_dir / 'data' / 'ideer.db'}"
    if args.command == "rollback" and args.backup_dir is None:
        raise ValueError("--backup-dir is required for rollback")
    if args.command == "compare" and get_resource_catalog_mode() is not ResourceCatalogMode.DUAL:
        raise ValueError("compare requires dual mode (IDEER_RESOURCE_CATALOG_MODE=dual)")

    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            storage = ResourceStorage(legacy_base_dir)
            migrator = LegacyResourceMigrator(
                session,
                storage,
                legacy_base_dir=legacy_base_dir,
                skills_root=args.skills_root.resolve(),
            )
            if args.command == "audit":
                report = await migrator.audit()
            elif args.command == "migrate":
                report = await migrator.migrate()
            elif args.command == "verify":
                report = await migrator.verify()
            elif args.command == "compare":
                comparator = DualModeComparator(
                    session,
                    storage,
                    legacy_base_dir=legacy_base_dir,
                    skills_root=args.skills_root.resolve(),
                )
                comparison = await comparator.compare()
                print(json.dumps(_compare_payload(comparison), ensure_ascii=False, indent=2))
                return 1 if comparison.errors else 0
            else:
                report = await migrator.rollback(backup_dir=args.backup_dir)
    finally:
        await engine.dispose()

    print(json.dumps(_payload(args.command, report), ensure_ascii=False, indent=2))
    return 1 if report.errors else 0


def main() -> int:
    return asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
