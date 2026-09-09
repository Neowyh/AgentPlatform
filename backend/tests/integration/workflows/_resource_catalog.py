"""Shared ResourceService publish helper for workflow integration tests."""

from __future__ import annotations

from app.agentplatform.resources.runtime import _json_hash
from app.agentplatform.resources.service import ResourceService


async def publish_resource(service: ResourceService, *, resource_type: str, slug: str, storage_kind: str, content: dict):
    """Create, draft, and publish one catalog resource; returns (resource, version)."""
    resource = await service.create_resource(
        resource_type=resource_type,
        slug=slug,
        display_name=slug,
        storage_kind=storage_kind,
    )
    await service.save_draft(
        resource.id,
        expected_revision=resource.draft_revision,
        content_hash=_json_hash(content),
        storage_key=f"{resource.storage_key}/versions/1",
        content=content,
    )
    # save_draft bumps draft_revision in-session; publish must observe it.
    version = await service.publish(resource.id, expected_draft_revision=resource.draft_revision, scan_result={})
    return resource, version
