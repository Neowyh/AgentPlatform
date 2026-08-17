"""User deletion business logic.

Coordinates the multi-step process of permanently removing a user and all
associated data from the system.  Supports three resource-handling strategies:

* **transfer** — reassign agents/skills/workflows/tools to another user
* **delete** — hard-delete metadata + remove disk files
* **soft_delete** — hard-delete metadata only, keep disk files

Usage::

    from app.gateway.user_deletion import delete_user

    await delete_user(session, paths, user_id, current_user_id,
                      resource_strategy="transfer",
                      target_user_id="other-user-id")
"""

from __future__ import annotations

import logging
import shutil
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy import update as sql_update

from ideer.persistence.feedback.model import FeedbackRow
from ideer.persistence.models.audit_log import AuditLog
from ideer.persistence.models.resource_catalog import Resource, ResourceDraft, ResourceVersion
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.persistence.models.run_event import RunEventRow
from ideer.persistence.models.user import UserModel, UserRole
from ideer.persistence.models.visibility_application import VisibilityApplication
from ideer.persistence.run.model import RunRow
from ideer.persistence.thread_meta.model import ThreadMetaRow
from ideer.persistence.user.model import UserRow
from ideer.resources.service import ResourceAction, ResourceActor, ResourceService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ideer.config.paths import Paths

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def report_user_state_anomalies(paths: Paths) -> dict[str, list[str]]:
    """Report inconsistent user directories at startup without modifying them."""
    from ideer.persistence.engine import get_session_factory

    sf = get_session_factory()
    if sf is None:
        return {"unexpected_directories": [], "auth_only_users": [], "rbac_only_users": []}

    async with sf() as session:
        auth_ids = {str(value) for value in (await session.execute(select(UserRow.id))).scalars()}
        rbac_ids = {str(value) for value in (await session.execute(select(UserModel.id))).scalars()}

    users_root = paths.base_dir / "users"
    disk_ids = {path.name for path in users_root.iterdir() if path.is_dir()} if users_root.exists() else set()
    report = {
        "unexpected_directories": sorted(disk_ids - (auth_ids & rbac_ids) - {"default"}),
        "auth_only_users": sorted(auth_ids - rbac_ids),
        "rbac_only_users": sorted(rbac_ids - auth_ids),
    }
    if "default" in disk_ids:
        logger.info("Reserved system user-state directory present: default")
    if any(report.values()):
        logger.warning("User-state anomalies detected; run reconcile_user_state.py audit: %s", report)
    return report


async def delete_user(
    session: AsyncSession,
    paths: Paths,
    user_id: str,
    *,
    current_user_id: str,
    resource_strategy: str,
    target_user_id: str | None = None,
) -> dict[str, str]:
    """Permanently delete *user_id* and handle all owned resources.

    Raises:
        ValueError: If preconditions are not met.
    """
    await _validate_preconditions(
        session=session,
        user_id=user_id,
        current_user_id=current_user_id,
        strategy=resource_strategy,
        target_user_id=target_user_id,
    )

    await _handle_canonical_resources(
        session=session,
        user_id=user_id,
        current_user_id=current_user_id,
        strategy=resource_strategy,
        target_user_id=target_user_id,
    )
    await _handle_resource_metadata(
        session=session,
        paths=paths,
        user_id=user_id,
        strategy=resource_strategy,
        target_user_id=target_user_id,
    )
    await _handle_visibility_applications(session=session, user_id=user_id)
    await _handle_historical_data(session=session, paths=paths, user_id=user_id)
    await _handle_audit_logs(session=session, user_id=user_id)
    await _record_user_deletion_audit(session=session, user_id=user_id, current_user_id=current_user_id, strategy=resource_strategy)
    retain_rbac_identity = await _has_canonical_identity_references(session, user_id)
    await _delete_user_rows(
        session=session,
        user_id=user_id,
        retain_rbac_identity=retain_rbac_identity,
    )
    await session.commit()

    try:
        filesystem_cleanup = cleanup_user_state(paths, user_id)
    except OSError as exc:
        filesystem_cleanup = "failed"
        await _record_cleanup_failure_audit(
            user_id=user_id,
            current_user_id=current_user_id,
            error=str(exc),
        )

    logger.info(
        "User deleted: user_id=%s, strategy=%s, target=%s, by=%s",
        user_id,
        resource_strategy,
        target_user_id,
        current_user_id,
    )
    return {"filesystem_cleanup": filesystem_cleanup}


# ---------------------------------------------------------------------------
# Precondition checks
# ---------------------------------------------------------------------------


async def _validate_preconditions(
    session: AsyncSession,
    user_id: str,
    current_user_id: str,
    strategy: str,
    target_user_id: str | None,
) -> None:
    """Validate preconditions before deletion."""
    if strategy not in ("transfer", "delete", "soft_delete"):
        raise ValueError(f"Invalid resource_strategy: '{strategy}'. Must be one of: transfer, delete, soft_delete")

    if strategy == "transfer" and not target_user_id:
        raise ValueError("target_user_id is required when resource_strategy is 'transfer'")

    if strategy == "transfer" and target_user_id == user_id:
        raise ValueError("target_user_id cannot be the same as the user being deleted")

    if current_user_id == user_id:
        raise ValueError("Cannot delete your own account")

    rbac_user, auth_user = await _check_user_exists(session, user_id)
    if rbac_user is None and auth_user is None:
        raise ValueError("User not found")

    if rbac_user is not None and not rbac_user.disabled:
        raise ValueError("User must be disabled before deletion")

    if rbac_user is not None and rbac_user.role == UserRole.SUPER_ADMIN and not rbac_user.disabled:
        if await _check_last_super_admin(session):
            raise ValueError("Cannot delete the last active super_admin")

    if strategy == "transfer" and target_user_id:
        if not await _check_target_user_exists(session, target_user_id):
            raise ValueError(f"Target user '{target_user_id}' not found")


# ---------------------------------------------------------------------------
# Internal query helpers
# ---------------------------------------------------------------------------


async def _check_user_exists(session: AsyncSession, user_id: str) -> tuple[UserModel | None, UserRow | None]:
    """Load both RBAC and auth user records."""
    rbac_result = await session.execute(select(UserModel).where(UserModel.id == user_id))
    auth_result = await session.execute(select(UserRow).where(UserRow.id == user_id))
    return rbac_result.scalar_one_or_none(), auth_result.scalar_one_or_none()


async def _check_last_super_admin(session: AsyncSession) -> bool:
    """Return True if there is at most one active super_admin left."""
    count = (
        await session.execute(
            select(func.count())
            .select_from(UserModel)
            .where(
                UserModel.role == UserRole.SUPER_ADMIN,
                UserModel.disabled.is_not(True),
            )
        )
    ).scalar() or 0
    return count <= 1


async def _check_target_user_exists(session: AsyncSession, target_user_id: str) -> bool:
    """Return True if the target RBAC user exists."""
    result = await session.execute(select(UserModel).where(UserModel.id == target_user_id))
    return result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Resource metadata handling (strategy-based)
# ---------------------------------------------------------------------------


async def _handle_canonical_resources(
    session: AsyncSession,
    user_id: str,
    current_user_id: str,
    strategy: str,
    target_user_id: str | None,
) -> None:
    """Govern canonical resources while retaining immutable history."""

    actor = ResourceActor(
        user_id=current_user_id,
        department_id=None,
        role="super_admin",
        permissions=frozenset(ResourceAction),
    )
    canonical_strategy = "transfer" if strategy == "transfer" else "archive"
    await ResourceService(session, actor).govern_owner_deletion(
        user_id,
        strategy=canonical_strategy,
        target_owner_id=target_user_id,
    )


async def _has_canonical_identity_references(session: AsyncSession, user_id: str) -> bool:
    """Return whether immutable catalog history still requires the RBAC identity row."""

    statements = (
        select(Resource.id).where(Resource.owner_id == user_id).limit(1),
        select(ResourceVersion.id).where(ResourceVersion.created_by == user_id).limit(1),
        select(ResourceDraft.resource_id).where(ResourceDraft.modified_by == user_id).limit(1),
        select(VisibilityApplication.id).where((VisibilityApplication.applicant_id == user_id) | (VisibilityApplication.reviewed_by == user_id)).limit(1),
    )
    for statement in statements:
        if (await session.execute(statement)).scalar_one_or_none() is not None:
            return True
    return False


async def _handle_resource_metadata(
    session: AsyncSession,
    paths: Paths,
    user_id: str,
    strategy: str,
    target_user_id: str | None = None,
) -> None:
    """Process resource_metadata rows according to *strategy*."""
    now = datetime.now(UTC)

    if strategy == "transfer":
        if not target_user_id:
            raise ValueError("target_user_id required for transfer strategy")
        await _bulk_transfer_resources(session, user_id, target_user_id, now)

    elif strategy == "delete":
        await _bulk_hard_delete_resources(session, user_id)

    else:
        await _bulk_hard_delete_resources(session, user_id)


async def _bulk_transfer_resources(session: AsyncSession, user_id: str, target_user_id: str, now: datetime) -> None:
    """Reassign all non-deleted resources to *target_user_id*."""
    await session.execute(sql_update(ResourceMetadata).where(ResourceMetadata.owner_id == user_id).values(owner_id=target_user_id, updated_at=now))


async def _bulk_hard_delete_resources(session: AsyncSession, user_id: str) -> None:
    """Hard-delete all resource metadata owned by *user_id*."""
    await session.execute(sql_delete(ResourceMetadata).where(ResourceMetadata.owner_id == user_id))


# ---------------------------------------------------------------------------
# Visibility applications
# ---------------------------------------------------------------------------


async def _handle_visibility_applications(session: AsyncSession, user_id: str) -> None:
    """Withdraw pending applications and clear reviewer references."""
    await _bulk_withdraw_applications(session, user_id)
    await _clear_reviewer_refs(session, user_id)


async def _bulk_withdraw_applications(session: AsyncSession, user_id: str) -> None:
    """Withdraw all pending applications where *user_id* is the applicant."""
    await session.execute(
        sql_update(VisibilityApplication)
        .where(
            VisibilityApplication.applicant_id == user_id,
            VisibilityApplication.status == "pending",
        )
        .values(status="withdrawn")
    )


async def _clear_reviewer_refs(session: AsyncSession, user_id: str) -> None:
    """Clear reviewer references where *user_id* is the reviewer."""
    await session.execute(sql_update(VisibilityApplication).where(VisibilityApplication.reviewed_by == user_id).values(reviewed_by=None))


# ---------------------------------------------------------------------------
# Historical data (threads / runs / events / feedback)
# ---------------------------------------------------------------------------


async def _handle_historical_data(session: AsyncSession, paths: Paths, user_id: str) -> None:
    """Hard-delete threads, runs, run_events, and feedback for this user."""
    await _delete_threads(session, paths, user_id)
    await _delete_rows(session, RunRow, RunRow.user_id, user_id)
    await _delete_rows(session, RunEventRow, RunEventRow.user_id, user_id)
    await _delete_rows(session, FeedbackRow, FeedbackRow.user_id, user_id)


async def _delete_threads(session: AsyncSession, paths: Paths, user_id: str) -> None:
    """Delete thread rows; the user directory is removed after commit."""
    await session.execute(sql_delete(ThreadMetaRow).where(ThreadMetaRow.user_id == user_id))


async def _delete_rows(session: AsyncSession, model, column, user_id: str) -> None:
    """Hard-delete all rows in *model* where *column* == *user_id*."""
    await session.execute(sql_delete(model).where(column == user_id))


# ---------------------------------------------------------------------------
# Disk cleanup
# ---------------------------------------------------------------------------


def cleanup_user_state(paths: Paths, user_id: str) -> str:
    """Idempotently remove a deleted user's state directory."""
    user_dir = paths.user_dir(user_id)
    if not user_dir.exists():
        return "already_absent"
    shutil.rmtree(user_dir)
    return "deleted"


# ---------------------------------------------------------------------------
# Audit logs
# ---------------------------------------------------------------------------


async def _record_user_deletion_audit(session: AsyncSession, user_id: str, current_user_id: str, strategy: str) -> None:
    """Record an audit event for user deletion."""
    from app.gateway.audit import record_audit

    await record_audit(
        actor_id=current_user_id,
        action="delete",
        resource_type="user",
        resource_id=user_id,
        detail={"strategy": strategy},
    )


async def _record_cleanup_failure_audit(user_id: str, current_user_id: str, error: str) -> None:
    """Record post-commit filesystem cleanup failure for operator retry."""
    from app.gateway.audit import record_audit

    await record_audit(
        actor_id=current_user_id,
        action="user_state_cleanup_failed",
        resource_type="user",
        resource_id=user_id,
        detail={"error": error},
    )


async def _handle_audit_logs(session: AsyncSession, user_id: str) -> None:
    """Set actor_id to NULL on audit logs referencing this user.

    The FK already has ``ondelete="SET NULL"``, but we make it explicit
    here so the cleanup is visible regardless of how the user row is removed.
    """
    await session.execute(sql_update(AuditLog).where(AuditLog.actor_id == user_id).values(actor_id=None))


# ---------------------------------------------------------------------------
# Delete user rows
# ---------------------------------------------------------------------------


async def _delete_user_rows(
    session: AsyncSession,
    user_id: str,
    *,
    retain_rbac_identity: bool = False,
) -> None:
    """Delete login identity and retain a disabled RBAC history anchor when required."""
    auth_stmt = select(UserRow).where(UserRow.id == user_id)
    auth_result = await session.execute(auth_stmt)
    auth_user = auth_result.scalar_one_or_none()
    if auth_user:
        await session.delete(auth_user)

    rbac_stmt = select(UserModel).where(UserModel.id == user_id)
    rbac_result = await session.execute(rbac_stmt)
    rbac_user = rbac_result.scalar_one_or_none()
    if rbac_user and retain_rbac_identity:
        rbac_user.disabled = True
        rbac_user.department_id = None
    elif rbac_user:
        await session.delete(rbac_user)
