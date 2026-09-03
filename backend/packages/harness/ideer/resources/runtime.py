"""Fail-closed loading of immutable canonical resources for a frozen Run."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ideer.config.agents_config import AgentConfig
from ideer.persistence.models.resource_catalog import Resource, ResourceDependency, ResourceVersion, RunResourceSnapshot
from ideer.persistence.models.user import ResourceVisibility
from ideer.resources.storage import ResourceStorage, StorageValidationError
from ideer.skills.types import Skill, SkillCategory

_CREDENTIAL_KEYS = {"api_key", "credential", "credentials", "password", "secret", "token"}


class ResourceRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class CanonicalAgentDefinition:
    resource_id: str
    version: int
    content_hash: str
    path: Path
    config: AgentConfig
    soul: str


@dataclass(frozen=True)
class CanonicalWorkflowDefinition:
    resource_id: str
    version: int
    content_hash: str
    content: dict


@dataclass(frozen=True)
class CanonicalSkillDefinition:
    resource_id: str
    version: int
    content_hash: str
    skill: Skill


def intersect_tool_groups(
    declared_groups: list[str] | None,
    runner_allowed_groups: frozenset[str] | None,
) -> list[str] | None:
    if declared_groups is None:
        return sorted(runner_allowed_groups) if runner_allowed_groups is not None else None
    if runner_allowed_groups is None:
        return list(dict.fromkeys(declared_groups))
    return list(dict.fromkeys(group for group in declared_groups if group in runner_allowed_groups))


def resource_memory_key(runner_id: str, agent_resource_id: str) -> tuple[str, str]:
    return runner_id, agent_resource_id


def _contains_credentials(value: object) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in _CREDENTIAL_KEYS or _contains_credentials(child):
                return True
    elif isinstance(value, list):
        return any(_contains_credentials(child) for child in value)
    return False


def _json_hash(content: dict) -> str:
    canonical = json.dumps(content, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


def load_validated_agent_definition(path: Path, *, fallback_name: str) -> tuple[AgentConfig, str]:
    try:
        raw = yaml.safe_load((path / "config.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ResourceRuntimeError(f"Agent config is invalid: {exc}") from exc
    if not isinstance(raw, dict):
        raise ResourceRuntimeError("Agent config must be a mapping")
    if _contains_credentials(raw):
        raise ResourceRuntimeError("Agent definition contains credential fields")
    raw["name"] = raw.get("name") or fallback_name
    known_fields = set(AgentConfig.model_fields)
    config = AgentConfig(**{key: value for key, value in raw.items() if key in known_fields})
    soul_path = path / "SOUL.md"
    soul = soul_path.read_text(encoding="utf-8").strip() if soul_path.is_file() else ""
    return config, soul


class CanonicalResourceLoader:
    def __init__(self, session: AsyncSession, storage: ResourceStorage) -> None:
        self.session = session
        self.storage = storage

    async def _frozen_version(
        self,
        run_id: str,
        resource_id: str,
        *,
        expected_type: str,
    ) -> tuple[Resource, ResourceVersion, RunResourceSnapshot]:
        snapshot = (
            await self.session.execute(
                select(RunResourceSnapshot).where(
                    RunResourceSnapshot.run_id == run_id,
                    RunResourceSnapshot.resource_id == resource_id,
                )
            )
        ).scalar_one_or_none()
        if snapshot is None:
            raise ResourceRuntimeError(f"Run {run_id} has no snapshot for resource {resource_id}")
        resource = await self.session.get(Resource, resource_id)
        if resource is None or resource.type != expected_type:
            raise ResourceRuntimeError(f"Snapshot resource {resource_id} is not a {expected_type}")
        if resource.lifecycle_status == "suspended":
            raise ResourceRuntimeError(f"Resource {resource_id} is suspended")
        version = (
            await self.session.execute(
                select(ResourceVersion).where(
                    ResourceVersion.resource_id == resource.id,
                    ResourceVersion.version == snapshot.version,
                )
            )
        ).scalar_one_or_none()
        if version is None:
            raise ResourceRuntimeError(f"Frozen resource version {resource.id}@{snapshot.version} is missing")
        if version.content_hash != snapshot.content_hash:
            raise ResourceRuntimeError(f"Frozen resource hash differs from snapshot for {resource.id}")
        return resource, version, snapshot

    async def load_agent(self, run_id: str, resource_id: str) -> CanonicalAgentDefinition:
        resource, version, _snapshot = await self._frozen_version(run_id, resource_id, expected_type="agent")
        expected_key = f"agents/{resource.id}/versions/{version.version}"
        if version.storage_key != expected_key:
            raise ResourceRuntimeError(f"Agent version has invalid storage key: {version.storage_key}")
        path = self.storage.resources_root / expected_key
        try:
            inspected = self.storage.inspect_directory("agent", path)
        except (OSError, StorageValidationError) as exc:
            raise ResourceRuntimeError(f"Agent version content is invalid: {exc}") from exc
        if inspected.content_hash != version.content_hash:
            raise ResourceRuntimeError(f"Agent version hash mismatch for {resource.id}@{version.version}")
        config, soul = load_validated_agent_definition(path, fallback_name=resource.slug)
        return CanonicalAgentDefinition(
            resource_id=resource.id,
            version=version.version,
            content_hash=version.content_hash,
            path=path,
            config=config,
            soul=soul,
        )

    async def load_workflow(self, run_id: str, resource_id: str) -> CanonicalWorkflowDefinition:
        resource, version, _snapshot = await self._frozen_version(run_id, resource_id, expected_type="workflow")
        if version.content is None or _json_hash(version.content) != version.content_hash:
            raise ResourceRuntimeError(f"Workflow version hash mismatch for {resource.id}@{version.version}")
        return CanonicalWorkflowDefinition(
            resource_id=resource.id,
            version=version.version,
            content_hash=version.content_hash,
            content=version.content,
        )

    async def load_skill(self, run_id: str, resource_id: str) -> CanonicalSkillDefinition:
        resource, version, _snapshot = await self._frozen_version(run_id, resource_id, expected_type="skill")
        expected_key = f"skills/{resource.id}/versions/{version.version}"
        if version.storage_key != expected_key:
            raise ResourceRuntimeError(f"Skill version has invalid storage key: {version.storage_key}")
        path = self.storage.resources_root / expected_key
        try:
            inspected = self.storage.inspect_directory("skill", path)
        except (OSError, StorageValidationError) as exc:
            raise ResourceRuntimeError(f"Skill version content is invalid: {exc}") from exc
        if inspected.content_hash != version.content_hash:
            raise ResourceRuntimeError(f"Skill version hash mismatch for {resource.id}@{version.version}")
        from ideer.skills.parser import parse_skill_file

        skill = parse_skill_file(path / "SKILL.md", category=SkillCategory.CUSTOM, relative_path=Path(resource.id))
        if skill is None:
            raise ResourceRuntimeError(f"Skill definition is invalid for {resource.id}@{version.version}")
        skill.enabled = True
        skill.visibility = ResourceVisibility(resource.visibility)
        skill.owner_id = resource.owner_id
        skill.department_id = resource.scope_department_id
        return CanonicalSkillDefinition(
            resource_id=resource.id,
            version=version.version,
            content_hash=version.content_hash,
            skill=skill,
        )

    async def load_agent_skill_definitions(
        self,
        run_id: str,
        agent_resource_id: str,
        *,
        definition: CanonicalAgentDefinition | None = None,
    ) -> list[CanonicalSkillDefinition]:
        # T3: callers that already loaded the Agent pass it in so the
        # definition (inspect + hash + parse) happens exactly once per Run.
        if definition is None:
            definition = await self.load_agent(run_id, agent_resource_id)
        targets = list(
            (
                await self.session.execute(
                    select(Resource)
                    .join(ResourceDependency, ResourceDependency.target_resource_id == Resource.id)
                    .where(
                        ResourceDependency.source_resource_id == agent_resource_id,
                        Resource.type == "skill",
                    )
                    .order_by(Resource.slug, Resource.id)
                )
            ).scalars()
        )
        by_slug = {target.slug: target for target in targets}
        by_id = {target.id: target for target in targets}

        def _match(name: str) -> Resource | None:
            return by_id.get(name) or by_slug.get(name)

        requested = definition.config.skills
        selected = targets if requested is None else [target for name in requested if (target := _match(name)) is not None]
        missing = [] if requested is None else [name for name in requested if _match(name) is None]
        if missing:
            raise ResourceRuntimeError(f"Agent {agent_resource_id} has unresolved Skill dependencies: {', '.join(missing)}")
        return [await self.load_skill(run_id, target.id) for target in selected]

    async def load_agent_skills(self, run_id: str, agent_resource_id: str) -> list[Skill]:
        definitions = await self.load_agent_skill_definitions(run_id, agent_resource_id)
        return [definition.skill for definition in definitions]
