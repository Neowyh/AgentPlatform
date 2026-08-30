"""Transaction boundary for filesystem-backed resource drafts and versions."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from pathlib import Path

import yaml

from ideer.persistence.models.resource_catalog import Resource, ResourceDraft, ResourceVersion
from ideer.resources.runtime import load_validated_agent_definition
from ideer.resources.service import ResourceConflict, ResourceService
from ideer.resources.storage import ResourceStorage, StorageError, StorageValidationError
from ideer.skills.publish_policy import SkillPublishPolicy
from ideer.workflows.v2.parser import parse_workflow_v2

logger = logging.getLogger(__name__)


def write_agent_draft_source(
    source: Path,
    *,
    slug: str,
    config: dict,
    soul: str,
) -> None:
    """Materialize an agent draft directory from a config mapping and SOUL."""
    definition = {key: value for key, value in config.items() if key not in {"name", "owner_id", "department_id", "visibility"}}
    definition["name"] = slug
    (source / "config.yaml").write_text(
        yaml.safe_dump(definition, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    (source / "SOUL.md").write_text(soul, encoding="utf-8")


class ResourcePublisher:
    """Order filesystem publication before committing its database pointer."""

    def __init__(self, service: ResourceService, storage: ResourceStorage) -> None:
        self.service = service
        self.storage = storage
        self.skill_publish_policy = SkillPublishPolicy()

    def _assert_publishable(self, resource: Resource, scan_result: dict) -> None:
        if resource.type == "skill":
            self.skill_publish_policy.assert_publishable(scan_result)

    async def save_filesystem_draft(
        self,
        resource_id: str,
        *,
        source_dir: str | Path,
        expected_revision: int,
    ) -> ResourceDraft:
        resource = await self.service.get_visible(resource_id)
        self.service.assert_modify(resource)
        previous = await self.service.session.get(ResourceDraft, resource.id)
        previous_revision = previous.revision if previous is not None else None
        staged = self.storage.stage_directory(resource.type, resource.id, source_dir)
        stored = self.storage.store_draft(staged, revision=expected_revision + 1)
        try:
            draft = await self.service.save_draft(
                resource.id,
                expected_revision=expected_revision,
                content_hash=stored.content_hash,
                storage_key=stored.storage_key,
            )
            await self.service.session.commit()
        except BaseException:
            await self.service.session.rollback()
            raise
        if previous_revision is not None and previous_revision != draft.revision:
            try:
                self.storage.discard_draft(resource.type, resource.id, revision=previous_revision)
            except (OSError, StorageError):
                logger.warning("Failed to remove replaced resource draft %s@%s", resource.id, previous_revision, exc_info=True)
        return draft

    async def save_archive_draft(
        self,
        resource_id: str,
        *,
        archive_path: str | Path,
        expected_revision: int,
    ) -> ResourceDraft:
        resource = await self.service.get_visible(resource_id)
        self.service.assert_modify(resource)
        staged = self.storage.stage_archive(resource.type, resource.id, archive_path)
        stored = self.storage.store_draft(staged, revision=expected_revision + 1)
        try:
            draft = await self.service.save_draft(
                resource.id,
                expected_revision=expected_revision,
                content_hash=stored.content_hash,
                storage_key=stored.storage_key,
            )
            await self.service.session.commit()
        except BaseException:
            await self.service.session.rollback()
            raise
        return draft

    async def fork(
        self,
        source_resource_id: str,
        *,
        slug: str,
        display_name: str,
    ) -> Resource:
        source = await self.service.resolve_for_use(source_resource_id)
        source_version = await self.service.get_published_content(source.id)
        target_resource_id = str(uuid.uuid4())
        if source.storage_kind == "filesystem":
            copied = self.storage.copy_published_version(
                source.type,
                source.id,
                source_version.version,
                target_resource_id,
                1,
            )
            storage_key = copied.storage_key
        else:
            storage_key = f"workflows/{target_resource_id}/versions/1"
        try:
            resource = await self.service.fork(
                source.id,
                slug=slug,
                display_name=display_name,
                copied_storage_key=storage_key,
                target_resource_id=target_resource_id,
            )
            await self.service.session.commit()
        except BaseException:
            await self.service.session.rollback()
            raise
        return resource

    async def publish_filesystem(
        self,
        resource_id: str,
        *,
        expected_draft_revision: int,
        scan_result: dict,
    ) -> ResourceVersion:
        resource = await self.service.get_visible(resource_id)
        self.service.assert_modify(resource)
        self._assert_publishable(resource, scan_result)
        draft = await self.service.session.get(ResourceDraft, resource.id)
        if draft is None or draft.revision != expected_draft_revision:
            raise ResourceConflict("Draft revision changed before filesystem publication")

        staged = self.storage.stage_draft(resource.type, resource.id, revision=draft.revision)
        if staged.content_hash != draft.content_hash:
            self.storage.discard_staged(staged)
            raise StorageValidationError("Resource draft hash does not match the catalog")
        if resource.type == "agent":
            try:
                load_validated_agent_definition(staged.path, fallback_name=resource.slug)
            except BaseException:
                self.storage.discard_staged(staged)
                raise
        published = self.storage.publish_staged(staged, version=resource.latest_version + 1)
        draft.storage_key = published.storage_key
        draft.content_hash = published.content_hash
        try:
            version = await self.service.publish(
                resource.id,
                expected_draft_revision=expected_draft_revision,
                scan_result=scan_result,
            )
            await self.service.session.commit()
        except BaseException:
            await self.service.session.rollback()
            raise
        try:
            self.storage.discard_draft(resource.type, resource.id, revision=expected_draft_revision)
        except (OSError, StorageError):
            logger.warning("Failed to remove published resource draft %s@%s", resource.id, expected_draft_revision, exc_info=True)
        return version

    @staticmethod
    def _database_hash(content: dict) -> str:
        canonical = json.dumps(content, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        return hashlib.sha256(canonical).hexdigest()

    async def save_database_draft(
        self,
        resource_id: str,
        *,
        content: dict,
        expected_revision: int,
    ) -> ResourceDraft:
        resource = await self.service.get_visible(resource_id)
        self.service.assert_modify(resource)
        if resource.type != "workflow" or resource.storage_kind != "database":
            raise ResourceConflict("Only database-backed Workflow resources accept database drafts")
        revision = expected_revision + 1
        try:
            draft = await self.service.save_draft(
                resource.id,
                expected_revision=expected_revision,
                content_hash=self._database_hash(content),
                storage_key=f"workflows/{resource.id}/draft/{revision}",
                content=content,
            )
            await self.service.session.commit()
        except BaseException:
            await self.service.session.rollback()
            raise
        return draft

    async def publish_database(
        self,
        resource_id: str,
        *,
        expected_draft_revision: int,
        scan_result: dict,
    ) -> ResourceVersion:
        resource = await self.service.get_visible(resource_id)
        self.service.assert_modify(resource)
        self._assert_publishable(resource, scan_result)
        if resource.type != "workflow" or resource.storage_kind != "database":
            raise ResourceConflict("Only database-backed Workflow resources accept database publication")
        draft = await self.service.session.get(ResourceDraft, resource.id)
        if draft is None or draft.revision != expected_draft_revision or draft.content is None:
            raise ResourceConflict("Workflow draft revision changed before publication")
        if self._database_hash(draft.content) != draft.content_hash:
            raise ResourceConflict("Workflow draft hash does not match its content")
        parse_workflow_v2(yaml.safe_dump(draft.content, sort_keys=False, allow_unicode=True))
        draft.storage_key = f"workflows/{resource.id}/versions/{resource.latest_version + 1}"
        try:
            version = await self.service.publish(
                resource.id,
                expected_draft_revision=expected_draft_revision,
                scan_result=scan_result,
            )
            await self.service.session.commit()
        except BaseException:
            await self.service.session.rollback()
            raise
        return version

    async def rollback_filesystem(self, resource_id: str, *, source_version: int) -> ResourceVersion:
        resource = await self.service.get_visible(resource_id)
        self.service.assert_modify(resource)
        if resource.type == "workflow" or resource.storage_kind != "filesystem":
            raise ResourceConflict("Only filesystem-backed Skill and Agent resources use filesystem rollback")
        source = await self.service.get_published_content(resource.id, version=source_version)
        copied = self.storage.copy_published_version(
            resource.type,
            resource.id,
            source.version,
            resource.id,
            resource.latest_version + 1,
        )
        try:
            version = await self.service.rollback(
                resource.id,
                source_version=source.version,
                copied_storage_key=copied.storage_key,
            )
            await self.service.session.commit()
        except BaseException:
            await self.service.session.rollback()
            raise
        return version

    async def rollback_database(self, resource_id: str, *, source_version: int) -> ResourceVersion:
        resource = await self.service.get_visible(resource_id)
        self.service.assert_modify(resource)
        if resource.type != "workflow" or resource.storage_kind != "database":
            raise ResourceConflict("Only database-backed Workflow resources use database rollback")
        storage_key = f"workflows/{resource.id}/versions/{resource.latest_version + 1}"
        try:
            version = await self.service.rollback(
                resource.id,
                source_version=source_version,
                copied_storage_key=storage_key,
            )
            await self.service.session.commit()
        except BaseException:
            await self.service.session.rollback()
            raise
        return version
