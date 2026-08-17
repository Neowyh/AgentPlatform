"""Stable, fail-closed provisioning for manifest-declared bundled resources."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml
from sqlalchemy import delete, select

from ideer.persistence.models.resource_catalog import (
    Resource,
    ResourceDependency,
    ResourceProvenance,
    ResourceVersion,
)
from ideer.resources.storage import ResourceStorage, StorageConflict
from ideer.workflows.v2.parser import parse_workflow_v2_file


@dataclass(frozen=True)
class BundledResource:
    id: str
    type: str
    slug: str
    visibility: str
    source: str
    system_owned: bool = False


@dataclass(frozen=True)
class BundledManifest:
    schema_version: int
    resources: tuple[BundledResource, ...]


@dataclass(frozen=True)
class BundledSeedReport:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0


def load_bundled_manifest(path: str | Path) -> BundledManifest:
    manifest_path = Path(path)
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Bundled resource manifest must use schema_version 1")
    values = raw.get("resources")
    if not isinstance(values, list):
        raise ValueError("Bundled resource manifest resources must be a list")
    resources: list[BundledResource] = []
    ids: set[str] = set()
    identities: set[tuple[str, str]] = set()
    for raw_item in values:
        if not isinstance(raw_item, dict):
            raise ValueError("Bundled resource entries must be objects")
        system_owned = raw_item.get("system_owned", False)
        if not isinstance(system_owned, bool):
            raise ValueError(f"Invalid bundled resource system_owned: {raw_item.get('slug', '')}")
        item = BundledResource(
            id=str(raw_item.get("id", "")),
            type=str(raw_item.get("type", "")),
            slug=str(raw_item.get("slug", "")),
            visibility=str(raw_item.get("visibility", "")),
            source=str(raw_item.get("source", "")),
            system_owned=system_owned,
        )
        try:
            canonical_id = str(uuid.UUID(item.id))
        except ValueError as exc:
            raise ValueError(f"Invalid bundled resource UUID: {item.id}") from exc
        if canonical_id != item.id:
            raise ValueError(f"Bundled resource UUID is not canonical: {item.id}")
        if item.type not in {"skill", "agent", "workflow"}:
            raise ValueError(f"Invalid bundled resource type: {item.type}")
        if item.visibility not in {"private", "public"}:
            raise ValueError(f"Invalid bundled resource visibility: {item.visibility}")
        if not item.slug or len(item.slug) > 128:
            raise ValueError("Bundled resource slug is empty or too long")
        relative = PurePosixPath(item.source)
        if relative.is_absolute() or ".." in relative.parts or "\\" in item.source:
            raise ValueError(f"Invalid bundled resource source: {item.source}")
        if item.id in ids or (item.type, item.slug) in identities:
            raise ValueError(f"Duplicate bundled resource identity: {item.type}/{item.slug}")
        ids.add(item.id)
        identities.add((item.type, item.slug))
        resources.append(item)
    return BundledManifest(schema_version=1, resources=tuple(resources))


def _database_hash(content: dict) -> str:
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _allows_dependency(source: BundledResource, target: BundledResource) -> bool:
    if source.visibility == "public":
        return target.visibility == "public"
    return True


def _resolve_reference(
    identity: str,
    *,
    expected_type: str,
    by_id: dict[str, BundledResource],
    by_identity: dict[tuple[str, str], BundledResource],
) -> BundledResource:
    target = by_id.get(identity) or by_identity.get((expected_type, identity))
    if target is None or target.type != expected_type:
        raise ValueError(f"Missing bundled {expected_type} dependency: {identity}")
    return target


def _prepare_agent(
    item: BundledResource,
    source: Path,
    *,
    by_id: dict[str, BundledResource],
    by_identity: dict[tuple[str, str], BundledResource],
) -> tuple[tempfile.TemporaryDirectory[str], Path, list[str]]:
    temporary = tempfile.TemporaryDirectory(prefix="bundled-agent-")
    target_root = Path(temporary.name)
    shutil.copytree(source, target_root, dirs_exist_ok=True, copy_function=shutil.copy2)
    config_path = target_root / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        temporary.cleanup()
        raise ValueError(f"Bundled Agent config must be a mapping: {item.slug}")
    dependencies: list[str] = []
    raw_skills = raw.get("skills") or []
    if not isinstance(raw_skills, list) or any(not isinstance(value, str) or not value for value in raw_skills):
        temporary.cleanup()
        raise ValueError(f"Bundled Agent skills must be a string list: {item.slug}")
    for identity in raw_skills:
        dependency = _resolve_reference(
            identity,
            expected_type="skill",
            by_id=by_id,
            by_identity=by_identity,
        )
        if not _allows_dependency(item, dependency):
            temporary.cleanup()
            raise ValueError(f"Bundled visibility closure rejects {item.slug} -> {dependency.slug}")
        dependencies.append(dependency.id)
    raw["name"] = item.slug
    if raw_skills:
        raw["skills"] = dependencies
    config_path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return temporary, target_root, dependencies


def _prepare_workflow(
    item: BundledResource,
    source: Path,
    *,
    by_id: dict[str, BundledResource],
    by_identity: dict[tuple[str, str], BundledResource],
) -> tuple[dict, list[str]]:
    workflow = parse_workflow_v2_file(source)
    dependencies: list[str] = []
    for node in workflow.nodes:
        if node.type != "action" or node.action is None or node.action.kind != "agent":
            continue
        dependency = _resolve_reference(
            node.action.name,
            expected_type="agent",
            by_id=by_id,
            by_identity=by_identity,
        )
        if not _allows_dependency(item, dependency):
            raise ValueError(f"Bundled visibility closure rejects {item.slug} -> {dependency.slug}")
        node.action.name = dependency.id
        dependencies.append(dependency.id)
    return workflow.model_dump(mode="json", by_alias=True), dependencies


def _assert_acyclic(edges: dict[str, list[str]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(resource_id: str) -> None:
        if resource_id in visiting:
            raise ValueError("Bundled resource dependency cycle detected")
        if resource_id in visited:
            return
        visiting.add(resource_id)
        for target_id in edges.get(resource_id, []):
            visit(target_id)
        visiting.remove(resource_id)
        visited.add(resource_id)

    for resource_id in edges:
        visit(resource_id)


async def seed_bundled_resources(
    session_factory,
    storage: ResourceStorage,
    *,
    manifest_path: str | Path,
    source_root: str | Path,
    owner_id: str,
    conflict_policy: str = "keep",
) -> BundledSeedReport:
    """Publish one immutable canonical version for every manifest entry.

    conflict_policy controls what happens when a bundled resource was
    modified after install (its latest version is no longer the bundled
    original): "keep" skips the bundled update, "override" publishes the
    bundled content as a new version.
    """

    if conflict_policy not in {"keep", "override"}:
        raise ValueError(f"Invalid bundled conflict policy: {conflict_policy}")

    manifest = load_bundled_manifest(manifest_path)
    root = Path(source_root).resolve()
    by_id = {item.id: item for item in manifest.resources}
    by_identity = {(item.type, item.slug): item for item in manifest.resources}
    prepared: dict[str, tuple[str, object, list[str], object | None]] = {}
    for item in manifest.resources:
        source = root.joinpath(*PurePosixPath(item.source).parts).resolve()
        if not source.is_relative_to(root) or not source.exists():
            raise ValueError(f"Bundled resource source is missing: {item.source}")
        if item.type == "workflow":
            content, dependencies = _prepare_workflow(
                item,
                source,
                by_id=by_id,
                by_identity=by_identity,
            )
            prepared[item.id] = (
                _database_hash(content),
                content,
                dependencies,
                None,
            )
            continue
        cleanup: object | None = None
        definition_source = source
        dependencies: list[str] = []
        if item.type == "agent":
            cleanup, definition_source, dependencies = _prepare_agent(
                item,
                source,
                by_id=by_id,
                by_identity=by_identity,
            )
        try:
            inspected = storage.inspect_directory(item.type, definition_source)
            prepared[item.id] = (
                inspected.content_hash,
                definition_source,
                dependencies,
                cleanup,
            )
        except BaseException:
            if cleanup is not None:
                cleanup.cleanup()
            raise
    _assert_acyclic({resource_id: value[2] for resource_id, value in prepared.items()})

    created = updated = unchanged = skipped = 0
    skipped_ids: set[str] = set()
    try:
        async with session_factory() as session:
            for item in manifest.resources:
                content_hash, content_or_source, _dependencies, _cleanup = prepared[item.id]
                resource = await session.get(Resource, item.id)
                if resource is None:
                    collision = await session.scalar(
                        select(Resource.id).where(
                            Resource.type == item.type,
                            Resource.owner_id == owner_id,
                            Resource.slug == item.slug,
                        )
                    )
                    if collision is not None:
                        raise StorageConflict(f"Bundled identity {item.type}/{item.slug} conflicts with {collision}")
                    directory = "workflows" if item.type == "workflow" else f"{item.type}s"
                    resource = Resource(
                        id=item.id,
                        type=item.type,
                        slug=item.slug,
                        display_name=item.slug,
                        owner_id=owner_id,
                        visibility=item.visibility,
                        lifecycle_status="active",
                        latest_version=0,
                        draft_revision=0,
                        storage_kind="database" if item.type == "workflow" else "filesystem",
                        storage_key=f"{directory}/{item.id}",
                        provenance=ResourceProvenance.BUNDLED.value,
                        system_owned=item.system_owned,
                        authz_revision=1,
                    )
                    session.add(resource)
                    await session.flush()
                    created += 1
                elif resource.type != item.type or resource.slug != item.slug or resource.provenance != ResourceProvenance.BUNDLED.value:
                    raise StorageConflict(f"Bundled UUID {item.id} is occupied by incompatible resource")
                if resource.system_owned != item.system_owned:
                    resource.system_owned = item.system_owned
                latest = None
                if resource.latest_version:
                    latest = await session.scalar(
                        select(ResourceVersion).where(
                            ResourceVersion.resource_id == item.id,
                            ResourceVersion.version == resource.latest_version,
                        )
                    )
                if latest is not None and latest.content_hash == content_hash:
                    unchanged += 1
                    continue
                if latest is not None and conflict_policy == "keep" and ((latest.scan_result or {}).get("status") != "trusted_bundled_manifest"):
                    skipped += 1
                    skipped_ids.add(item.id)
                    continue
                version_number = resource.latest_version + 1
                if item.type == "workflow":
                    storage_key = f"workflows/{item.id}/versions/{version_number}"
                    version_content = content_or_source
                else:
                    expected_path = storage.resources_root / f"{item.type}s" / item.id / "versions" / str(version_number)
                    if expected_path.exists():
                        inspected = storage.inspect_directory(item.type, expected_path)
                        if inspected.content_hash != content_hash:
                            raise StorageConflict(f"Bundled version path conflict: {item.id}@{version_number}")
                        storage_key = expected_path.relative_to(storage.resources_root).as_posix()
                    else:
                        staged = storage.stage_directory(
                            item.type,
                            item.id,
                            content_or_source,
                        )
                        published = storage.publish_staged(
                            staged,
                            version=version_number,
                        )
                        storage_key = published.storage_key
                    version_content = None
                session.add(
                    ResourceVersion(
                        id=str(uuid.uuid4()),
                        resource_id=item.id,
                        version=version_number,
                        content_hash=content_hash,
                        storage_key=storage_key,
                        scan_result={
                            "status": "trusted_bundled_manifest",
                            "manifest_schema": manifest.schema_version,
                        },
                        content=version_content,
                        created_by=owner_id,
                    )
                )
                resource.latest_version = version_number
                if version_number > 1:
                    updated += 1

            resource_ids = [resource_id for resource_id in prepared if resource_id not in skipped_ids]
            await session.execute(delete(ResourceDependency).where(ResourceDependency.source_resource_id.in_(resource_ids)))
            for source_id, (_hash, _content, target_ids, _cleanup) in prepared.items():
                if source_id in skipped_ids:
                    continue
                for target_id in dict.fromkeys(target_ids):
                    session.add(
                        ResourceDependency(
                            id=str(uuid.uuid4()),
                            source_resource_id=source_id,
                            target_resource_id=target_id,
                        )
                    )
            await session.commit()
    finally:
        for _hash, _content, _dependencies, cleanup in prepared.values():
            if cleanup is not None:
                cleanup.cleanup()
    return BundledSeedReport(created=created, updated=updated, unchanged=unchanged, skipped=skipped)
