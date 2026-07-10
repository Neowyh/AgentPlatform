"""Shared utility helpers for the Gateway layer."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.resource_metadata import ResourceMetadata

logger = logging.getLogger(__name__)


def sanitize_log_param(value: str) -> str:
    """Strip control characters to prevent log injection."""
    return value.replace("\n", "").replace("\r", "").replace("\x00", "")


class ResourceMetadataStore:
    """Unified read/write for the resource_metadata table, parameterized by resource_type."""

    def __init__(self, resource_type: str) -> None:
        self.resource_type = resource_type

    async def load_meta(self, resource_id: str) -> dict:
        """Load RBAC metadata from the resource_metadata table."""
        sf = get_session_factory()
        if sf is not None:
            try:
                async with sf() as session:
                    stmt = select(ResourceMetadata).where(
                        ResourceMetadata.resource_type == self.resource_type,
                        ResourceMetadata.resource_id == resource_id,
                    )
                    result = await session.execute(stmt)
                    resource = result.scalar_one_or_none()
                    if resource:
                        return {
                            "visibility": resource.visibility,
                            "owner_id": resource.owner_id,
                            "department_id": resource.department_id,
                            "version": resource.version,
                            "is_favorited": resource.is_favorited,
                            "created_at": str(resource.created_at) if resource.created_at else None,
                        }
            except Exception as e:
                logger.warning("Failed to load meta: %s", e)
        return {}

    async def save_meta(self, resource_id: str, meta: dict) -> bool:
        """Persist RBAC metadata to the resource_metadata table.

        If a record already exists, updates visibility/department/version.
        Otherwise creates a new record.

        Returns True on success, False on failure.
        """
        sf = get_session_factory()
        if sf is None:
            return False
        try:
            async with sf() as session:
                stmt = select(ResourceMetadata).where(
                    ResourceMetadata.resource_type == self.resource_type,
                    ResourceMetadata.resource_id == resource_id,
                )
                result = await session.execute(stmt)
                resource = result.scalar_one_or_none()
                if resource:
                    resource.visibility = meta.get("visibility", "private")
                    resource.department_id = meta.get("department_id")
                    resource.version = resource.version + 1
                else:
                    resource = ResourceMetadata(
                        id=str(uuid.uuid4()),
                        resource_type=self.resource_type,
                        resource_id=resource_id,
                        owner_id=meta.get("owner_id", "system"),
                        department_id=meta.get("department_id"),
                        visibility=meta.get("visibility", "private"),
                    )
                    session.add(resource)
                await session.commit()
                return True
        except Exception as e:
            logger.warning("Failed to save meta: %s", e)
            return False

    async def delete(self, resource_id: str) -> bool:
        """Hard-delete a resource's metadata record.

        Returns True on success, False on failure.
        """
        from sqlalchemy import delete as sql_delete

        sf = get_session_factory()
        if sf is None:
            return False
        try:
            async with sf() as session:
                await session.execute(
                    sql_delete(ResourceMetadata).where(
                        ResourceMetadata.resource_type == self.resource_type,
                        ResourceMetadata.resource_id == resource_id,
                    )
                )
                await session.commit()
                return True
        except Exception as e:
            logger.warning("Failed to hard-delete meta: %s", e)
            return False
