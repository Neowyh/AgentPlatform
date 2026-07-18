"""Migrate .meta.json files to resource_metadata table.

Scans skill and agent directories for .meta.json files and inserts
corresponding rows into the resource_metadata table.

Usage:
    cd backend && python -m ideer.scripts.migrate_meta_json [--dry-run]
"""

import argparse
import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from ideer.config.extensions_config import ExtensionsConfig
from ideer.config.paths import get_paths
from ideer.config.skills_config import SkillsConfig
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.resource_metadata import ResourceMetadata

logger = logging.getLogger(__name__)


def _scan_skill_meta_files(skills_path: Path) -> list[tuple[Path, dict]]:
    """Scan skill directories for .meta.json files.

    Returns list of (meta_file_path, parsed_meta_dict) for each valid .meta.json found.
    """
    results = []
    custom_dir = skills_path / "custom"
    if not custom_dir.is_dir():
        return results

    for skill_dir in sorted(custom_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        meta_file = skill_dir / ".meta.json"
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            results.append((meta_file, meta))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read %s: %s", meta_file, e)
    return results


def _scan_agent_meta_files(base_dir: Path) -> list[tuple[Path, dict]]:
    """Scan agent directories for .meta.json files (per-user and legacy).

    Returns list of (meta_file_path, parsed_meta_dict) for each valid .meta.json found.
    """
    results = []
    users_dir = base_dir / "users"
    if users_dir.is_dir():
        for user_dir in sorted(users_dir.iterdir()):
            if not user_dir.is_dir():
                continue
            agents_dir = user_dir / "agents"
            if not agents_dir.is_dir():
                continue
            for agent_dir in sorted(agents_dir.iterdir()):
                if not agent_dir.is_dir():
                    continue
                meta_file = agent_dir / ".meta.json"
                if not meta_file.exists():
                    continue
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    results.append((meta_file, meta))
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("Failed to read %s: %s", meta_file, e)

    # Legacy agents dir (no user isolation)
    legacy_agents_dir = base_dir / "agents"
    if legacy_agents_dir.is_dir():
        for agent_dir in sorted(legacy_agents_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            meta_file = agent_dir / ".meta.json"
            if not meta_file.exists():
                continue
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                results.append((meta_file, meta))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read %s: %s", meta_file, e)

    return results


def _validate_owner_exists(owner_id: str, existing_owner_ids: set[str]) -> bool:
    """Check if owner_id is in the set of known valid user IDs."""
    if not owner_id:
        return False
    return owner_id in existing_owner_ids


async def _load_existing_owner_ids() -> set[str]:
    """Load all user IDs from users_ext table."""
    sf = get_session_factory()
    if sf is None:
        return set()

    try:
        from ideer.persistence.models.user import UserModel

        async with sf() as session:
            stmt = select(UserModel.id)
            result = await session.execute(stmt)
            return {row[0] for row in result.all()}
    except Exception as e:
        logger.warning("Failed to load user IDs: %s", e)
        return set()


async def migrate_meta_json(*, dry_run: bool = False) -> dict:
    """Migrate all .meta.json files to resource_metadata table.

    Args:
        dry_run: If True, only log what would happen without making changes.

    Returns:
        Migration report with counts of imported, skipped, and failed records.
    """
    paths = get_paths()
    skills_config = SkillsConfig()
    skills_path = skills_config.get_skills_path()

    # Collect all .meta.json files
    skill_metas = _scan_skill_meta_files(skills_path)
    agent_metas = _scan_agent_meta_files(paths.base_dir)

    all_metas: list[tuple[str, Path, dict]] = []
    for meta_file, meta in skill_metas:
        all_metas.append(("skill", meta_file, meta))
    for meta_file, meta in agent_metas:
        all_metas.append(("agent", meta_file, meta))

    if not all_metas:
        logger.info("No .meta.json files found — nothing to migrate")
        return {"imported": 0, "skipped": 0, "failed": 0}

    sf = get_session_factory()
    if sf is None:
        logger.error("Database not initialized — cannot migrate")
        return {"imported": 0, "skipped": 0, "failed": 0}

    logger.info("Found %d .meta.json files to migrate", len(all_metas))

    # Load existing owner IDs for validation
    existing_owner_ids = await _load_existing_owner_ids()
    logger.info("Found %d existing user IDs in users_ext", len(existing_owner_ids))

    imported = 0
    skipped = 0
    failed = 0
    now = datetime.now(UTC)

    async with sf() as session:
        for resource_type, meta_file, meta in all_metas:
            try:
                resource_id = meta.get("name", meta_file.parent.name)
                owner_id = meta.get("owner_id")
                department_id = meta.get("department_id")
                visibility = meta.get("visibility", "private")

                # Validate owner_id — skip if missing or invalid
                if not owner_id:
                    logger.error(
                        "Skipping %s '%s': no owner_id in meta file — add owner_id and re-run",
                        resource_type,
                        resource_id,
                    )
                    skipped += 1
                    continue
                if not _validate_owner_exists(owner_id, existing_owner_ids):
                    logger.error(
                        "Skipping %s '%s': owner_id '%s' not found in users_ext — fix the owner_id in %s and re-run",
                        resource_type,
                        resource_id,
                        owner_id,
                        meta_file,
                    )
                    skipped += 1
                    continue

                # Idempotency check
                stmt = select(ResourceMetadata).where(
                    ResourceMetadata.resource_type == resource_type,
                    ResourceMetadata.resource_id == resource_id,
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    skipped += 1
                    continue

                # Insert new record
                resource = ResourceMetadata(
                    id=str(uuid.uuid4()),
                    resource_type=resource_type,
                    resource_id=resource_id,
                    owner_id=owner_id,
                    department_id=department_id,
                    visibility=visibility,
                    imported_from=str(meta_file),
                    version=1,
                    created_at=now,
                    updated_at=now,
                )

                if not dry_run:
                    session.add(resource)

                imported += 1
                logger.info(
                    "Migrated %s '%s' (owner=%s, visibility=%s, source=%s)",
                    resource_type,
                    resource_id,
                    owner_id,
                    visibility,
                    meta_file,
                )

            except Exception as e:
                failed += 1
                logger.error("Failed to migrate %s: %s", meta_file, e)

        if not dry_run and imported > 0:
            await session.commit()

    report = {
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
    }
    logger.info(
        "Migration complete: %d imported, %d skipped, %d failed",
        imported,
        skipped,
        failed,
    )

    # Verification step: compare file count and table row count
    total_files = imported + skipped + failed
    total_db = imported + skipped
    if total_files != total_db:
        logger.warning(
            "Verification: file count (%d) != db count (%d) — %d failed",
            total_files,
            total_db,
            failed,
        )
    else:
        logger.info("Verification: file count (%d) == db count (%d) — OK", total_files, total_db)

    # Sample validation: check 10% of imported records
    if imported > 0:
        await _sample_validate(imported, skipped)

    return report


async def _sample_validate(imported: int, skipped: int) -> None:
    """Sample validate 10% of imported records to ensure field values are consistent."""
    sf = get_session_factory()
    if sf is None:
        return

    try:
        async with sf() as session:
            # Count total records
            from sqlalchemy import func

            count_stmt = select(func.count()).select_from(ResourceMetadata)
            total = (await session.execute(count_stmt)).scalar() or 0

            # Sample 10% of records (minimum 1)
            sample_size = max(1, total // 10)
            stmt = select(ResourceMetadata).order_by(func.random()).limit(sample_size)
            result = await session.execute(stmt)
            samples = result.scalars().all()

            # Validate each sample
            valid_count = 0
            for sample in samples:
                if sample.resource_type in ("tool", "skill", "workflow", "agent") and sample.visibility in ("private", "department", "public") and sample.version >= 1 and sample.owner_id:
                    valid_count += 1
                else:
                    logger.warning(
                        "Sample validation failed for %s/%s: type=%s, vis=%s, ver=%s, owner=%s",
                        sample.resource_type,
                        sample.resource_id,
                        sample.resource_type,
                        sample.visibility,
                        sample.version,
                        sample.owner_id,
                    )

            logger.info(
                "Sample validation: %d/%d records valid (%.1f%%)",
                valid_count,
                sample_size,
                (valid_count / sample_size * 100) if sample_size > 0 else 0,
            )
    except Exception as e:
        logger.warning("Sample validation failed: %s", e)


async def backfill_tools(*, dry_run: bool = False, default_owner: str | None = None) -> dict:
    """Backfill MCP server tool entries into resource_metadata table.

    Tools defined in MCP configuration (extensions_config.json) don't have
    .meta.json files, so they were never migrated to resource_metadata.
    This function reads all MCP server names and creates resource_metadata
    entries for them.

    Args:
        dry_run: If True, only log what would happen without making changes.

    Returns:
        Report with counts of imported, skipped, failed records.
    """
    try:
        config = ExtensionsConfig.from_file()
    except (ValueError, RuntimeError) as e:
        logger.error("Failed to load extensions config: %s", e)
        return {"imported": 0, "skipped": 0, "failed": 0}

    tool_names = list(config.mcp_servers.keys())

    if not tool_names:
        logger.info("No MCP tools found in configuration — nothing to backfill")
        return {"imported": 0, "skipped": 0, "failed": 0}

    if not default_owner:
        logger.error("Cannot backfill tools: --default-owner is required")
        return {"imported": 0, "skipped": 0, "failed": 0}

    sf = get_session_factory()
    if sf is None:
        logger.error("Database not initialized — cannot backfill")
        return {"imported": 0, "skipped": 0, "failed": 0}

    logger.info("Found %d MCP tools to backfill", len(tool_names))

    imported = 0
    skipped = 0
    failed = 0
    now = datetime.now(UTC)

    async with sf() as session:
        for tool_name in tool_names:
            try:
                # Idempotency check
                stmt = select(ResourceMetadata).where(
                    ResourceMetadata.resource_type == "tool",
                    ResourceMetadata.resource_id == tool_name,
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    skipped += 1
                    continue

                # Insert new record
                resource = ResourceMetadata(
                    id=str(uuid.uuid4()),
                    resource_type="tool",
                    resource_id=tool_name,
                    owner_id=default_owner,
                    department_id=None,
                    visibility="public",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )

                if not dry_run:
                    session.add(resource)

                imported += 1
                logger.info(
                    "Backfilled tool '%s' (owner=%s, visibility=public)",
                    tool_name,
                    default_owner,
                )

            except Exception as e:
                failed += 1
                logger.error("Failed to backfill tool '%s': %s", tool_name, e)

        if not dry_run and imported > 0:
            await session.commit()

    report = {
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
    }
    logger.info(
        "Tool backfill complete: %d imported, %d skipped, %d failed",
        imported,
        skipped,
        failed,
    )

    return report


def main() -> None:
    import uuid as uuid_validator

    parser = argparse.ArgumentParser(description="Migrate .meta.json files to resource_metadata table")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without making changes")
    parser.add_argument(
        "--default-owner",
        help="UUID of the default owner for backfilled tools and workflows (required for tool/workflow backfill)",
    )
    args = parser.parse_args()

    default_owner = args.default_owner
    if default_owner is not None:
        try:
            uuid_validator.UUID(default_owner)
        except ValueError:
            parser.error(f"--default-owner must be a valid UUID, got: {default_owner}")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    import asyncio

    skill_agent_report = asyncio.run(migrate_meta_json(dry_run=args.dry_run))
    tool_report = asyncio.run(backfill_tools(dry_run=args.dry_run, default_owner=default_owner))
    report = {
        "skill_agent": skill_agent_report,
        "tool_backfill": tool_report,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
