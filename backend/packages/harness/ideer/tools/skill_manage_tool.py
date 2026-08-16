"""Tool for creating and evolving custom skills."""

from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from weakref import WeakValueDictionary

from langchain.tools import tool
from sqlalchemy import select

from ideer.agents.lead_agent.prompt import refresh_skills_system_prompt_cache_async
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.resource_catalog import Resource
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.resources.mode import ResourceCatalogMode, get_resource_catalog_mode
from ideer.runtime.user_context import resolve_runtime_user_id
from ideer.skills.security_scanner import scan_skill_content
from ideer.skills.storage import get_or_new_skill_storage
from ideer.skills.storage.skill_storage import SkillStorage
from ideer.skills.types import SKILL_MD_FILE
from ideer.tools.sync import make_sync_tool_wrapper
from ideer.tools.types import Runtime

logger = logging.getLogger(__name__)

_ALLOWED_SUPPORT_SUBDIRS = {"references", "templates", "scripts", "assets"}

_skill_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


def _get_lock(name: str) -> asyncio.Lock:
    lock = _skill_locks.get(name)
    if lock is None:
        lock = asyncio.Lock()
        _skill_locks[name] = lock
    return lock


def _get_thread_id(runtime: Runtime | None) -> str | None:
    if runtime is None:
        return None
    if runtime.context and runtime.context.get("thread_id"):
        return runtime.context.get("thread_id")
    return runtime.config.get("configurable", {}).get("thread_id")


def _history_record(*, action: str, file_path: str, prev_content: str | None, new_content: str | None, thread_id: str | None, scanner: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": action,
        "author": "agent",
        "thread_id": thread_id,
        "file_path": file_path,
        "prev_content": prev_content,
        "new_content": new_content,
        "scanner": scanner,
    }


async def _scan_or_raise(content: str, *, executable: bool, location: str) -> dict[str, str]:
    result = await scan_skill_content(content, executable=executable, location=location)
    if result.decision == "block":
        raise ValueError(f"Security scan blocked the write: {result.reason}")
    if executable and result.decision != "allow":
        raise ValueError(f"Security scan rejected executable content: {result.reason}")
    return {"decision": result.decision, "reason": result.reason}


async def _to_thread(func, /, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


async def _skill_manage_impl(
    runtime: Runtime,
    action: str,
    name: str,
    content: str | None = None,
    path: str | None = None,
    find: str | None = None,
    replace: str | None = None,
    expected_count: int | None = None,
) -> str:
    """Manage custom skills under skills/custom/.

    Args:
        action: One of create, patch, edit, delete, write_file, remove_file.
        name: Skill name in hyphen-case.
        content: New file content for create, edit, or write_file.
        path: Supporting file path for write_file or remove_file.
        find: Existing text to replace for patch.
        replace: Replacement text for patch.
        expected_count: Optional expected number of replacements for patch.
    """
    name = SkillStorage.validate_skill_name(name)
    lock = _get_lock(name)
    thread_id = _get_thread_id(runtime)
    skill_storage = get_or_new_skill_storage()

    async with lock:
        if action == "create":
            if await _to_thread(skill_storage.custom_skill_exists, name):
                raise ValueError(f"Custom skill '{name}' already exists.")
            if content is None:
                raise ValueError("content is required for create.")
            await _to_thread(skill_storage.validate_skill_markdown_content, name, content)
            scan = await _scan_or_raise(content, executable=False, location=f"{name}/{SKILL_MD_FILE}")
            await _to_thread(skill_storage.write_custom_skill, name, SKILL_MD_FILE, content)
            await _to_thread(
                skill_storage.append_history,
                name,
                _history_record(action="create", file_path=SKILL_MD_FILE, prev_content=None, new_content=content, thread_id=thread_id, scanner=scan),
            )
            # Persist RBAC metadata to resource_metadata table
            try:
                sf = get_session_factory()
                if sf is not None:
                    async with sf() as session:
                        existing = await session.execute(
                            select(ResourceMetadata).where(
                                ResourceMetadata.resource_type == "skill",
                                ResourceMetadata.resource_id == name,
                            )
                        )
                        if not existing.scalar_one_or_none():
                            owner_id = resolve_runtime_user_id(runtime)
                            session.add(
                                ResourceMetadata(
                                    id=str(uuid.uuid4()),
                                    resource_type="skill",
                                    resource_id=name,
                                    owner_id=owner_id,
                                    visibility="private",
                                )
                            )
                            await session.commit()
            except Exception:
                logger.warning("Failed to save resource metadata for skill '%s'", name)
            await refresh_skills_system_prompt_cache_async()
            return f"Created custom skill '{name}'."

        if action == "edit":
            await _to_thread(skill_storage.ensure_custom_skill_is_editable, name)
            if content is None:
                raise ValueError("content is required for edit.")
            await _to_thread(skill_storage.validate_skill_markdown_content, name, content)
            scan = await _scan_or_raise(content, executable=False, location=f"{name}/{SKILL_MD_FILE}")
            skill_file = skill_storage.get_custom_skill_file(name)
            prev_content = await _to_thread(skill_file.read_text, encoding="utf-8")
            await _to_thread(skill_storage.write_custom_skill, name, SKILL_MD_FILE, content)
            await _to_thread(
                skill_storage.append_history,
                name,
                _history_record(action="edit", file_path=SKILL_MD_FILE, prev_content=prev_content, new_content=content, thread_id=thread_id, scanner=scan),
            )
            await refresh_skills_system_prompt_cache_async()
            return f"Updated custom skill '{name}'."

        if action == "patch":
            await _to_thread(skill_storage.ensure_custom_skill_is_editable, name)
            if find is None or replace is None:
                raise ValueError("find and replace are required for patch.")
            skill_file = skill_storage.get_custom_skill_file(name)
            prev_content = await _to_thread(skill_file.read_text, encoding="utf-8")
            occurrences = prev_content.count(find)
            if occurrences == 0:
                raise ValueError("Patch target not found in SKILL.md.")
            if expected_count is not None and occurrences != expected_count:
                raise ValueError(f"Expected {expected_count} replacements but found {occurrences}.")
            replacement_count = expected_count if expected_count is not None else 1
            new_content = prev_content.replace(find, replace, replacement_count)
            await _to_thread(skill_storage.validate_skill_markdown_content, name, new_content)
            scan = await _scan_or_raise(new_content, executable=False, location=f"{name}/{SKILL_MD_FILE}")
            await _to_thread(skill_storage.write_custom_skill, name, SKILL_MD_FILE, new_content)
            await _to_thread(
                skill_storage.append_history,
                name,
                _history_record(action="patch", file_path=SKILL_MD_FILE, prev_content=prev_content, new_content=new_content, thread_id=thread_id, scanner=scan),
            )
            await refresh_skills_system_prompt_cache_async()
            return f"Patched custom skill '{name}' ({replacement_count} replacement(s) applied, {occurrences} match(es) found)."

        if action == "delete":
            await _to_thread(
                skill_storage.delete_custom_skill,
                name,
                history_meta=_history_record(
                    action="delete",
                    file_path=SKILL_MD_FILE,
                    prev_content=None,
                    new_content=None,
                    thread_id=thread_id,
                    scanner={"decision": "allow", "reason": "Deletion requested."},
                ),
            )
            await refresh_skills_system_prompt_cache_async()
            return f"Deleted custom skill '{name}'."

        if action == "write_file":
            await _to_thread(skill_storage.ensure_custom_skill_is_editable, name)
            if path is None or content is None:
                raise ValueError("path and content are required for write_file.")
            target = await _to_thread(skill_storage.ensure_safe_support_path, name, path)
            exists = await _to_thread(target.exists)
            prev_content = await _to_thread(target.read_text, encoding="utf-8") if exists else None
            executable = "scripts/" in path or path.startswith("scripts/")
            scan = await _scan_or_raise(content, executable=executable, location=f"{name}/{path}")
            await _to_thread(skill_storage.write_custom_skill, name, path, content)
            await _to_thread(
                skill_storage.append_history,
                name,
                _history_record(action="write_file", file_path=path, prev_content=prev_content, new_content=content, thread_id=thread_id, scanner=scan),
            )
            return f"Wrote '{path}' for custom skill '{name}'."

        if action == "remove_file":
            await _to_thread(skill_storage.ensure_custom_skill_is_editable, name)
            if path is None:
                raise ValueError("path is required for remove_file.")
            target = await _to_thread(skill_storage.ensure_safe_support_path, name, path)
            if not await _to_thread(target.exists):
                raise FileNotFoundError(f"Supporting file '{path}' not found for skill '{name}'.")
            prev_content = await _to_thread(target.read_text, encoding="utf-8")
            await _to_thread(target.unlink)
            await _to_thread(
                skill_storage.append_history,
                name,
                _history_record(action="remove_file", file_path=path, prev_content=prev_content, new_content=None, thread_id=thread_id, scanner={"decision": "allow", "reason": "Deletion requested."}),
            )
            return f"Removed '{path}' from custom skill '{name}'."

        if await _to_thread(skill_storage.public_skill_exists, name):
            raise ValueError(f"'{name}' is a built-in skill. To customise it, create a new skill with the same name under skills/custom/.")
        raise ValueError(f"Unsupported action '{action}'.")


async def _skill_manage_canonical_impl(
    runtime: Runtime,
    action: str,
    name: str,
    content: str | None = None,
    path: str | None = None,
    find: str | None = None,
    replace: str | None = None,
    expected_count: int | None = None,
) -> str:
    """Manage catalog skills through draft + publish in canonical mode.

    Mirrors the legacy actions (create/edit/patch/delete/write_file/remove_file)
    but routes every write through ResourceService + ResourcePublisher so the
    catalog row, filesystem draft, and published version stay consistent.
    """
    from ideer.config.paths import get_paths
    from ideer.persistence.models.user import UserModel, UserRole
    from ideer.resources.publisher import ResourcePublisher
    from ideer.resources.service import ResourceAction, ResourceActor, ResourceNotFound, ResourceService
    from ideer.resources.storage import ResourceStorage

    name = SkillStorage.validate_skill_name(name)
    lock = _get_lock(name)
    skill_storage = get_or_new_skill_storage()

    sf = get_session_factory()
    if sf is None:
        raise RuntimeError("Resource catalog persistence is unavailable")

    def _validate_support_path(relative_path: str) -> Path:
        if not relative_path or relative_path.endswith("/"):
            raise ValueError("Supporting file path must include a filename.")
        relative = Path(relative_path)
        if relative.is_absolute():
            raise ValueError("Supporting file path must be relative.")
        if any(part in {"..", ""} for part in relative.parts):
            raise ValueError("Supporting file path must not contain parent-directory traversal.")
        top_level = relative.parts[0] if relative.parts else ""
        if top_level not in _ALLOWED_SUPPORT_SUBDIRS:
            raise ValueError(f"Supporting files must live under one of: {', '.join(sorted(_ALLOWED_SUPPORT_SUBDIRS))}.")
        return relative

    async with lock:
        async with sf() as session:
            user = (await session.execute(select(UserModel).where(UserModel.id == resolve_runtime_user_id(runtime), UserModel.disabled.is_not(True)))).scalar_one_or_none()
            if user is None:
                raise RuntimeError("Active user is required to manage catalog skills")
            permissions = {ResourceAction.READ, ResourceAction.USE}
            if user.role in {UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN}:
                permissions.add(ResourceAction.WRITE)
            actor = ResourceActor(
                user_id=str(user.id),
                department_id=str(user.department_id) if user.department_id is not None else None,
                role=str(user.role),
                permissions=frozenset(permissions),
                tool_groups=None,
            )
            service = ResourceService(session, actor)
            storage = ResourceStorage(get_paths().base_dir, allow_scanned_executables=True)

            async def _resolve() -> Resource:
                try:
                    return await service.resolve_legacy_alias("skill", name)
                except ResourceNotFound as exc:
                    raise ValueError(f"Custom skill '{name}' does not exist. Use create to add it first.") from exc

            async def _published_root(resource: Resource) -> Path:
                published = await service.get_published_content(resource.id)
                return storage.resources_root / published.storage_key

            async def _publish(resource: Resource, source: Path) -> None:
                publisher = ResourcePublisher(service, storage)
                draft = await publisher.save_filesystem_draft(
                    resource.id,
                    source_dir=source,
                    expected_revision=resource.draft_revision,
                )
                await publisher.publish_filesystem(
                    resource.id,
                    expected_draft_revision=draft.revision,
                    scan_result={},
                )

            async def _materialize(source: Path, root: Path) -> None:
                for entry in root.rglob("*"):
                    if not entry.is_file():
                        continue
                    relative = entry.relative_to(root)
                    target = source / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    await asyncio.to_thread(shutil.copyfile, entry, target)

            if action == "create":
                try:
                    await service.resolve_legacy_alias("skill", name)
                    raise ValueError(f"Custom skill '{name}' already exists.")
                except ResourceNotFound:
                    pass
                if await _to_thread(skill_storage.public_skill_exists, name):
                    raise ValueError(f"'{name}' is a built-in skill. To customise it, create a new skill with a different name.")
                if content is None:
                    raise ValueError("content is required for create.")
                await _to_thread(skill_storage.validate_skill_markdown_content, name, content)
                await _scan_or_raise(content, executable=False, location=f"{name}/{SKILL_MD_FILE}")
                resource = await service.create_resource(
                    resource_type="skill",
                    slug=name,
                    display_name=name,
                    storage_kind="filesystem",
                )
                with TemporaryDirectory(prefix="ideer-skill-create-") as temporary:
                    source = Path(temporary)
                    (source / SKILL_MD_FILE).write_text(content, encoding="utf-8")
                    await _publish(resource, source)
                await refresh_skills_system_prompt_cache_async()
                return f"Created custom skill '{name}'."

            resource = await _resolve()

            if action == "delete":
                await service.archive(resource.id)
                await session.commit()
                await refresh_skills_system_prompt_cache_async()
                return f"Deleted custom skill '{name}'."

            with TemporaryDirectory(prefix="ideer-skill-edit-") as temporary:
                source = Path(temporary)
                await _materialize(source, await _published_root(resource))

                if action == "edit":
                    if content is None:
                        raise ValueError("content is required for edit.")
                    await _to_thread(skill_storage.validate_skill_markdown_content, name, content)
                    await _scan_or_raise(content, executable=False, location=f"{name}/{SKILL_MD_FILE}")
                    (source / SKILL_MD_FILE).write_text(content, encoding="utf-8")
                    await _publish(resource, source)
                    await refresh_skills_system_prompt_cache_async()
                    return f"Updated custom skill '{name}'."

                if action == "patch":
                    if find is None or replace is None:
                        raise ValueError("find and replace are required for patch.")
                    skill_file = source / SKILL_MD_FILE
                    prev_content = skill_file.read_text(encoding="utf-8")
                    occurrences = prev_content.count(find)
                    if occurrences == 0:
                        raise ValueError("Patch target not found in SKILL.md.")
                    if expected_count is not None and occurrences != expected_count:
                        raise ValueError(f"Expected {expected_count} replacements but found {occurrences}.")
                    replacement_count = expected_count if expected_count is not None else 1
                    new_content = prev_content.replace(find, replace, replacement_count)
                    await _to_thread(skill_storage.validate_skill_markdown_content, name, new_content)
                    await _scan_or_raise(new_content, executable=False, location=f"{name}/{SKILL_MD_FILE}")
                    skill_file.write_text(new_content, encoding="utf-8")
                    await _publish(resource, source)
                    await refresh_skills_system_prompt_cache_async()
                    return f"Patched custom skill '{name}' ({replacement_count} replacement(s) applied, {occurrences} match(es) found)."

                if action == "write_file":
                    if path is None or content is None:
                        raise ValueError("path and content are required for write_file.")
                    relative = _validate_support_path(path)
                    target = source / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    executable = "scripts/" in path or path.startswith("scripts/")
                    await _scan_or_raise(content, executable=executable, location=f"{name}/{path}")
                    target.write_text(content, encoding="utf-8")
                    await _publish(resource, source)
                    return f"Wrote '{path}' for custom skill '{name}'."

                if action == "remove_file":
                    if path is None:
                        raise ValueError("path is required for remove_file.")
                    relative = _validate_support_path(path)
                    target = source / relative
                    if not target.exists():
                        raise FileNotFoundError(f"Supporting file '{path}' not found for skill '{name}'.")
                    target.unlink()
                    await _publish(resource, source)
                    return f"Removed '{path}' from custom skill '{name}'."

            raise ValueError(f"Unsupported action '{action}'.")


async def _skill_manage_dispatch(
    runtime: Runtime,
    action: str,
    name: str,
    content: str | None = None,
    path: str | None = None,
    find: str | None = None,
    replace: str | None = None,
    expected_count: int | None = None,
) -> str:
    if get_resource_catalog_mode() is ResourceCatalogMode.CANONICAL:
        return await _skill_manage_canonical_impl(
            runtime=runtime,
            action=action,
            name=name,
            content=content,
            path=path,
            find=find,
            replace=replace,
            expected_count=expected_count,
        )
    return await _skill_manage_impl(
        runtime=runtime,
        action=action,
        name=name,
        content=content,
        path=path,
        find=find,
        replace=replace,
        expected_count=expected_count,
    )


@tool("skill_manage", parse_docstring=True)
async def skill_manage_tool(
    runtime: Runtime,
    action: str,
    name: str,
    content: str | None = None,
    path: str | None = None,
    find: str | None = None,
    replace: str | None = None,
    expected_count: int | None = None,
) -> str:
    """Manage custom skills under skills/custom/.

    Args:
        action: One of create, patch, edit, delete, write_file, remove_file.
        name: Skill name in hyphen-case.
        content: New file content for create, edit, or write_file.
        path: Supporting file path for write_file or remove_file.
        find: Existing text to replace for patch.
        replace: Replacement text for patch.
        expected_count: Optional expected number of replacements for patch.
    """
    return await _skill_manage_dispatch(
        runtime=runtime,
        action=action,
        name=name,
        content=content,
        path=path,
        find=find,
        replace=replace,
        expected_count=expected_count,
    )


skill_manage_tool.func = make_sync_tool_wrapper(_skill_manage_dispatch, "skill_manage")
