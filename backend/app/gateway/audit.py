"""Audit logging utility for recording key operations."""

from __future__ import annotations

import json
import logging
import uuid

from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def record_audit(
    actor_id: str,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Record an audit log entry.

    This is the unified entry point for all critical operation audit logging.
    All endpoints should call this function after performing key operations.

    Args:
        actor_id: The user ID who performed the action.
        action: The action type (e.g. 'update', 'delete', 'create', 'visibility_change', 'role_change').
        resource_type: The type of resource affected (e.g. 'skill', 'workflow', 'agent', 'tool', 'user').
        resource_id: The identifier of the affected resource.
        detail: Optional JSON-serializable dict with additional context (e.g. old/new values).
        ip_address: The client IP address for the request.
    """
    sf = get_session_factory()
    if sf is None:
        return

    try:
        async with sf() as session:
            entry = AuditLog(
                id=uuid.uuid4().hex,
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=json.dumps(detail, ensure_ascii=False) if detail else None,
                ip_address=ip_address,
            )
            session.add(entry)
            await session.commit()
    except Exception:
        logger.exception("Failed to record audit log")
