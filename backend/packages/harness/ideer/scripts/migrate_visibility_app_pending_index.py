"""Rebuild the visibility_applications pending unique index to be per-applicant.

The original partial unique index ``uq_visibility_app_pending`` keyed on
(resource_type, resource_id) only, which blocked same-named resources owned
by different users from having independent application flows. This script
drops and recreates it keyed on (resource_type, resource_id, applicant_id).

Idempotent: safe to run multiple times.

Usage:
    cd backend && python -m ideer.scripts.migrate_visibility_app_pending_index [--dry-run]
"""

import argparse
import asyncio
import json
import logging

from sqlalchemy import text

from ideer.config.app_config import get_app_config
from ideer.persistence.engine import close_engine, get_session_factory, init_engine_from_config

logger = logging.getLogger(__name__)

OLD_INDEX_SQL = "DROP INDEX IF EXISTS uq_visibility_app_pending"
NEW_INDEX_SQL = "CREATE UNIQUE INDEX IF NOT EXISTS uq_visibility_app_pending ON visibility_applications(resource_type, resource_id, applicant_id) WHERE status = 'pending'"


async def migrate_visibility_app_pending_index(*, dry_run: bool = False) -> dict:
    """Drop and recreate the pending unique index keyed per applicant.

    Args:
        dry_run: If True, only log what would happen without making changes.

    Returns:
        Migration report with the action taken.
    """
    sf = get_session_factory()
    if sf is None:
        logger.error("Database not initialized — cannot migrate")
        return {"action": "skipped", "reason": "database not initialized"}

    async with sf() as session:
        if not dry_run:
            await session.execute(text(OLD_INDEX_SQL))
            await session.execute(text(NEW_INDEX_SQL))
            await session.commit()

    logger.info("Recreated index uq_visibility_app_pending keyed per applicant (dry_run=%s)", dry_run)
    return {"action": "dry-run" if dry_run else "recreated"}


async def _run(dry_run: bool) -> dict:
    """Bootstrap the engine (if needed), run the migration, then close it."""
    owned_engine = get_session_factory() is None
    if owned_engine:
        await init_engine_from_config(get_app_config().database)
    try:
        return await migrate_visibility_app_pending_index(dry_run=dry_run)
    finally:
        if owned_engine:
            await close_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild visibility_applications pending unique index per applicant")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without making changes")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    report = asyncio.run(_run(args.dry_run))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
