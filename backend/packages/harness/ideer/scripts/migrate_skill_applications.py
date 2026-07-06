"""Migrate skill_applications records to visibility_applications table.

Reads all skill_applications rows, resolves current_visibility from
resource_metadata, and inserts into visibility_applications.

Usage:
    cd backend && python -m ideer.scripts.migrate_skill_applications [--dry-run]
"""

import argparse
import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String, Text, select

from ideer.persistence.base import Base
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.persistence.models.visibility_application import VisibilityApplication

logger = logging.getLogger(__name__)


# Inline model for the old skill_applications table (kept for migration purposes)
class SkillApplication(Base):
    __tablename__ = "skill_applications"

    id = Column(String, primary_key=True)
    skill_id = Column(String, nullable=False)
    skill_name = Column(String, nullable=False)
    applicant_id = Column(String, nullable=False)
    request_level = Column(String, nullable=False)
    department_id = Column(String, nullable=True)
    reason = Column(Text, default="")
    status = Column(String, nullable=False, default="pending")
    submitted_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, nullable=True)


def _resolve_current_visibility(skill_id: str, session) -> str:
    """Look up current visibility from resource_metadata for a skill.

    Falls back to 'private' if no resource_metadata record exists.
    """
    stmt = select(ResourceMetadata.visibility).where(
        ResourceMetadata.resource_type == "skill",
        ResourceMetadata.resource_id == skill_id,
    )
    result = session.execute(stmt).scalar_one_or_none()
    return result if result else "private"


def migrate_skill_applications(*, dry_run: bool = False) -> dict:
    """Migrate all skill_applications to visibility_applications.

    Args:
        dry_run: If True, only log what would happen without making changes.

    Returns:
        Migration report with counts of migrated, skipped, failed records.
    """
    sf = get_session_factory()
    if sf is None:
        logger.error("Database not initialized — cannot migrate")
        return {"migrated": 0, "skipped": 0, "failed": 0}

    migrated = 0
    skipped = 0
    failed = 0
    now = datetime.now(UTC)

    with sf() as session:
        # Load all skill_applications
        stmt = select(SkillApplication)
        result = session.execute(stmt)
        skill_apps = result.scalars().all()

        if not skill_apps:
            logger.info("No skill_applications found — nothing to migrate")
            return {"migrated": 0, "skipped": 0, "failed": 0}

        logger.info("Found %d skill_applications to migrate", len(skill_apps))

        for app in skill_apps:
            try:
                # Idempotency: skip if already migrated (same skill_id + applicant_id + pending)
                existing = session.execute(
                    select(VisibilityApplication).where(
                        VisibilityApplication.resource_type == "skill",
                        VisibilityApplication.resource_id == app.skill_id,
                        VisibilityApplication.applicant_id == app.applicant_id,
                        VisibilityApplication.status == "pending",
                    )
                ).scalar_one_or_none()

                if existing:
                    skipped += 1
                    continue

                current_visibility = _resolve_current_visibility(app.skill_id, session)

                vis_app = VisibilityApplication(
                    id=str(uuid.uuid4()),
                    resource_type="skill",
                    resource_id=app.skill_id,
                    applicant_id=app.applicant_id,
                    current_visibility=current_visibility,
                    target_visibility=app.request_level,
                    department_id=app.department_id,
                    reason=app.reason or "",
                    status=app.status,
                    submitted_at=app.submitted_at,
                    reviewed_by=app.reviewed_by,
                    reviewed_at=app.reviewed_at,
                    review_comment=app.review_comment or "",
                    version=1,
                    created_at=now,
                )

                if not dry_run:
                    session.add(vis_app)

                migrated += 1
                logger.info(
                    "Migrated skill application %s (skill=%s, applicant=%s, status=%s)",
                    app.id,
                    app.skill_id,
                    app.applicant_id,
                    app.status,
                )

            except Exception as e:
                failed += 1
                logger.error("Failed to migrate skill application %s: %s", app.id, e)

        if not dry_run and migrated > 0:
            session.commit()

    report = {"migrated": migrated, "skipped": skipped, "failed": failed}
    logger.info(
        "Migration complete: %d migrated, %d skipped, %d failed",
        migrated,
        skipped,
        failed,
    )

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate skill_applications to visibility_applications")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without making changes")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    report = migrate_skill_applications(dry_run=args.dry_run)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
