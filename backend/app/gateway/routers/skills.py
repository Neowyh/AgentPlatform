import json
import logging
import re
import threading

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.gateway.audit import record_audit
from app.gateway.authz import check_resource_access, check_resource_modify, get_current_rbac_user, get_optional_rbac_user, require_role
from app.gateway.deps import get_config
from app.gateway.path_utils import resolve_thread_virtual_path
from app.gateway.resource_catalog_mode import require_legacy_resource_facades
from app.gateway.utils import ResourceMetadataStore
from ideer.agents.lead_agent.prompt import refresh_skills_system_prompt_cache_async
from ideer.config.app_config import AppConfig
from ideer.config.extensions_config import ExtensionsConfig, SkillStateConfig, get_extensions_config, reload_extensions_config
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.user import ResourceVisibility, UserModel, UserRole
from ideer.skills import Skill
from ideer.skills.installer import SkillAlreadyExistsError
from ideer.skills.security_scanner import scan_skill_content
from ideer.skills.storage import get_or_new_skill_storage
from ideer.skills.types import SKILL_MD_FILE, SkillCategory

logger = logging.getLogger(__name__)

# BUG-21: Lock to serialize concurrent extensions_config.json writes
_extensions_config_lock = threading.Lock()

# Skill name validation pattern - prevents path traversal attacks
_SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")

_skill_store = ResourceMetadataStore("skill")


def _validate_skill_name(name: str) -> None:
    """Validate skill name against path traversal and special characters."""
    if not _SKILL_NAME_PATTERN.match(name):
        raise HTTPException(status_code=422, detail=f"Invalid skill name '{name}'. Only alphanumeric, underscore, and hyphen characters are allowed.")


router = APIRouter(
    prefix="/api/skills",
    tags=["skills"],
    dependencies=[Depends(require_legacy_resource_facades)],
)


async def _load_skill_meta(skill_name: str, config: AppConfig) -> dict:
    """Load skill RBAC metadata from resource_metadata table."""
    meta = await _skill_store.load_meta(skill_name)
    if meta:
        return meta
    return {}


async def _save_skill_meta(skill_name: str, config: AppConfig, meta: dict) -> None:
    """Persist skill RBAC metadata to resource_metadata table."""
    saved = await _skill_store.save_meta(skill_name, meta)
    if not saved:
        logger.error("Failed to save skill metadata for '%s' to database", skill_name)


class SkillResponse(BaseModel):
    """Response model for skill information."""

    name: str = Field(..., description="Name of the skill")
    description: str = Field(..., description="Description of what the skill does")
    license: str | None = Field(None, description="License information")
    category: SkillCategory = Field(..., description="Category of the skill (public or custom)")
    enabled: bool = Field(default=True, description="Whether this skill is enabled")
    visibility: str | None = Field(None, description="Current visibility level")
    owner_id: str | None = Field(None, description="Owner user ID (custom skills)")
    department_id: str | None = Field(None, description="Department ID (custom skills)")


class SkillsListResponse(BaseModel):
    """Response model for listing all skills."""

    skills: list[SkillResponse]


class SkillUpdateRequest(BaseModel):
    """Request model for updating a skill."""

    enabled: bool = Field(..., description="Whether to enable or disable the skill")


class SkillInstallRequest(BaseModel):
    """Request model for installing a skill from a .skill file."""

    thread_id: str = Field(..., description="The thread ID where the .skill file is located")
    path: str = Field(..., description="Virtual path to the .skill file (e.g., mnt/user-data/outputs/my-skill.skill)")


class SkillInstallResponse(BaseModel):
    """Response model for skill installation."""

    success: bool = Field(..., description="Whether the installation was successful")
    skill_name: str = Field(..., description="Name of the installed skill")
    message: str = Field(..., description="Installation result message")


class CustomSkillContentResponse(SkillResponse):
    content: str = Field(..., description="Raw SKILL.md content")


class CustomSkillUpdateRequest(BaseModel):
    content: str = Field(..., description="Replacement SKILL.md content")
    version: int = Field(..., description="Current resource version for optimistic locking")


class CustomSkillHistoryResponse(BaseModel):
    history: list[dict]


class SkillRollbackRequest(BaseModel):
    history_index: int = Field(default=-1, description="History entry index to restore from, defaulting to the latest change.")


class SkillExportResponse(BaseModel):
    """Response model for skill export."""

    name: str = Field(..., description="Skill name")
    content: str = Field(..., description="Raw SKILL.md content")
    meta: dict = Field(default_factory=dict, description="RBAC metadata")


class SkillImportRequest(BaseModel):
    """Request body for skill import."""

    name: str = Field(..., description="Skill name (hyphen-case, lowercase letters, digits, hyphens only)")
    content: str = Field(..., description="SKILL.md content")
    visibility: str = Field(default="private", description="Visibility: private, department, or public")


def _apply_skill_meta(skill: Skill, meta: dict) -> None:
    """Write ResourceMetadata values back onto the Skill object so responses reflect reality."""
    skill.visibility = ResourceVisibility(meta.get("visibility", "private"))
    skill.owner_id = meta.get("owner_id")
    skill.department_id = meta.get("department_id")


def _skill_to_response(skill: Skill) -> SkillResponse:
    """Convert a Skill object to a SkillResponse."""
    return SkillResponse(
        name=skill.name,
        description=skill.description,
        license=skill.license,
        category=skill.category,
        enabled=skill.enabled,
        visibility=getattr(skill, "visibility", None),
        owner_id=getattr(skill, "owner_id", None),
        department_id=getattr(skill, "department_id", None),
    )


@router.get(
    "",
    response_model=SkillsListResponse,
    summary="List All Skills",
    description="Retrieve a list of all available skills from both public and custom directories.",
)
async def list_skills(
    config: AppConfig = Depends(get_config),
    current_user: UserModel | None = Depends(get_optional_rbac_user),
) -> SkillsListResponse:
    """List all skills, filtered by visibility when auth is active."""
    try:
        skills = get_or_new_skill_storage(app_config=config).load_skills(enabled_only=False)

        filtered: list[Skill] = []
        for skill in skills:
            if skill.category == SkillCategory.PUBLIC:
                filtered.append(skill)
                continue

            meta = await _load_skill_meta(skill.name, config)

            # Lazy registration: auto-create ResourceMetadata for custom skills
            # found on disk but missing from DB.
            if not meta and current_user is not None:
                meta = {
                    "visibility": "private",
                    "owner_id": str(current_user.id),
                    "department_id": str(current_user.department_id) if current_user.department_id else None,
                }
                await _save_skill_meta(skill.name, config, meta)

            visibility = meta.get("visibility", "private")
            owner_id = meta.get("owner_id")
            dept_id = meta.get("department_id")

            _apply_skill_meta(skill, meta)

            if current_user is not None:
                if check_resource_access(current_user, owner_id, dept_id, visibility):
                    filtered.append(skill)
            elif visibility == "public":
                filtered.append(skill)

        return SkillsListResponse(skills=[_skill_to_response(skill) for skill in filtered])
    except Exception as e:
        logger.error(f"Failed to load skills: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/install",
    response_model=SkillInstallResponse,
    summary="Install Skill",
    description="Install a skill from a .skill file (ZIP archive) located in the thread's user-data directory. Requires admin or department_admin role.",
)
@require_role(UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def install_skill(
    request: SkillInstallRequest,
    config: AppConfig = Depends(get_config),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> SkillInstallResponse:
    """Install a skill from an archive.

    RBAC: Only admin and department_admin roles can install new skills.
    """

    try:
        skill_file_path = resolve_thread_virtual_path(request.thread_id, request.path)
        result = await get_or_new_skill_storage(app_config=config).ainstall_skill_from_archive(skill_file_path)
        # Persist RBAC metadata to resource_metadata table
        meta = {
            "owner_id": str(current_user.id),
            "department_id": str(current_user.department_id) if current_user.department_id else None,
            "visibility": "private",
        }
        await _save_skill_meta(result["skill_name"], config, meta)
        await refresh_skills_system_prompt_cache_async()
        return SkillInstallResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SkillAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to install skill: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/custom", response_model=SkillsListResponse, summary="List Custom Skills")
async def list_custom_skills(
    config: AppConfig = Depends(get_config),
    current_user: UserModel | None = Depends(get_optional_rbac_user),
) -> SkillsListResponse:
    """List custom skills, filtered by visibility when auth is active."""
    try:
        skills = [skill for skill in get_or_new_skill_storage(app_config=config).load_skills(enabled_only=False) if skill.category == SkillCategory.CUSTOM]

        filtered: list[Skill] = []
        for skill in skills:
            meta = await _load_skill_meta(skill.name, config)

            # Lazy registration: auto-create ResourceMetadata for custom skills
            # found on disk but missing from DB.
            if not meta and current_user is not None:
                meta = {
                    "visibility": "private",
                    "owner_id": str(current_user.id),
                    "department_id": str(current_user.department_id) if current_user.department_id else None,
                }
                await _save_skill_meta(skill.name, config, meta)

            visibility = meta.get("visibility", "private")
            owner_id = meta.get("owner_id")
            dept_id = meta.get("department_id")

            _apply_skill_meta(skill, meta)

            if current_user is not None:
                if check_resource_access(current_user, owner_id, dept_id, visibility):
                    filtered.append(skill)
            elif visibility == "public":
                filtered.append(skill)

        return SkillsListResponse(skills=[_skill_to_response(skill) for skill in filtered])
    except Exception as e:
        logger.error("Failed to list custom skills: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/custom/{skill_name}", response_model=CustomSkillContentResponse, summary="Get Custom Skill Content")
async def get_custom_skill(
    skill_name: str,
    config: AppConfig = Depends(get_config),
    current_user: UserModel | None = Depends(get_optional_rbac_user),
) -> CustomSkillContentResponse:
    try:
        _validate_skill_name(skill_name)
        skill_name = skill_name.replace("\r\n", "").replace("\n", "")
        skills = get_or_new_skill_storage(app_config=config).load_skills(enabled_only=False)
        skill = next((s for s in skills if s.name == skill_name and s.category == SkillCategory.CUSTOM), None)
        if skill is None:
            raise HTTPException(status_code=404, detail=f"Custom skill '{skill_name}' not found")

        # Check visibility: unauthenticated users can only see public skills
        meta = await _load_skill_meta(skill.name, config)
        # Default to 'public' when no metadata exists (pre-RBAC skills)
        visibility = meta.get("visibility", "private")
        owner_id = meta.get("owner_id")
        dept_id = meta.get("department_id")
        _apply_skill_meta(skill, meta)
        if current_user is not None:
            if not check_resource_access(current_user, owner_id, dept_id, visibility):
                raise HTTPException(status_code=404, detail=f"Custom skill '{skill_name}' not found")
        elif visibility != "public":
            raise HTTPException(status_code=404, detail=f"Custom skill '{skill_name}' not found")

        return CustomSkillContentResponse(**_skill_to_response(skill).model_dump(), content=get_or_new_skill_storage(app_config=config).read_custom_skill(skill_name))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get custom skill %s: %s", skill_name, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/custom/{skill_name}", response_model=CustomSkillContentResponse, summary="Edit Custom Skill")
async def update_custom_skill(
    skill_name: str,
    request: CustomSkillUpdateRequest,
    config: AppConfig = Depends(get_config),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> CustomSkillContentResponse:
    """Update a custom skill's content. Requires authentication."""

    try:
        _validate_skill_name(skill_name)
        skill_name = skill_name.replace("\r\n", "").replace("\n", "")

        # RBAC: check ownership before allowing edit
        meta = await _load_skill_meta(skill_name, config)
        if not check_resource_modify(current_user, meta.get("owner_id"), meta.get("department_id")):
            raise HTTPException(status_code=403, detail="You do not have permission to modify this resource")

        # Optimistic locking: verify version matches
        from app.gateway.error_codes import ApiException

        current_version = meta.get("version")
        if current_version is not None and request.version != current_version:
            raise ApiException("VERSION_CONFLICT", "乐观锁冲突，需刷新重试")
        storage = get_or_new_skill_storage(app_config=config)
        storage.ensure_custom_skill_is_editable(skill_name)
        storage.validate_skill_markdown_content(skill_name, request.content)
        # Security scan deferred to phase 2 per design doc
        prev_content = storage.read_custom_skill(skill_name)
        storage.write_custom_skill(skill_name, SKILL_MD_FILE, request.content)
        storage.append_history(
            skill_name,
            {
                "action": "human_edit",
                "author": "human",
                "thread_id": None,
                "file_path": SKILL_MD_FILE,
                "prev_content": prev_content,
                "new_content": request.content,
            },
        )
        # Increment version in resource_metadata on successful edit
        await _save_skill_meta(
            skill_name,
            config,
            {
                "owner_id": str(current_user.id),
                "department_id": str(current_user.department_id) if current_user.department_id else None,
                "visibility": meta.get("visibility", "private"),
            },
        )
        await refresh_skills_system_prompt_cache_async()
        return await get_custom_skill(skill_name, config, current_user)
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to update custom skill %s: %s", skill_name, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/custom/{skill_name}", summary="Delete Custom Skill")
async def delete_custom_skill(
    skill_name: str,
    http_request: Request,
    config: AppConfig = Depends(get_config),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, bool]:
    """Delete a custom skill. Requires authentication."""

    try:
        _validate_skill_name(skill_name)
        skill_name = skill_name.replace("\r\n", "").replace("\n", "")

        # RBAC: check ownership before allowing delete
        meta = await _load_skill_meta(skill_name, config)
        if not check_resource_modify(current_user, meta.get("owner_id"), meta.get("department_id")):
            raise HTTPException(status_code=403, detail="You do not have permission to modify this resource")

        storage = get_or_new_skill_storage(app_config=config)
        storage.delete_custom_skill(
            skill_name,
            history_meta={
                "action": "human_delete",
                "author": "human",
                "thread_id": None,
                "file_path": SKILL_MD_FILE,
                "prev_content": None,
                "new_content": None,
                "scanner": {"decision": "allow", "reason": "Deletion requested."},
            },
        )

        # Auto-reject pending visibility applications for this resource
        sf = get_session_factory()
        if sf is not None:
            try:
                async with sf() as session:
                    from sqlalchemy import update as sql_update

                    from ideer.persistence.models.visibility_application import VisibilityApplication

                    await session.execute(
                        sql_update(VisibilityApplication)
                        .where(
                            VisibilityApplication.resource_type == "skill",
                            VisibilityApplication.resource_id == skill_name,
                            VisibilityApplication.applicant_id == str(current_user.id),
                            VisibilityApplication.status == "pending",
                        )
                        .values(status="rejected", review_comment="资源已删除，申请自动关闭")
                    )
                    # Hard-delete resource_metadata via store
                    if not await _skill_store.delete(skill_name):
                        logger.warning("Failed to delete metadata for skill '%s'", skill_name)
                    await session.commit()
            except Exception:
                logger.warning("Failed to auto-reject pending applications for deleted skill %s", skill_name)
        await refresh_skills_system_prompt_cache_async()
        await record_audit(
            actor_id=current_user.id,
            action="delete",
            resource_type="skill",
            resource_id=skill_name,
            detail=meta if meta else None,
            ip_address=http_request.client.host if http_request.client else None,
        )
        return {"success": True}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete custom skill %s: %s", skill_name, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/custom/{skill_name}/history", response_model=CustomSkillHistoryResponse, summary="Get Custom Skill History")
async def get_custom_skill_history(skill_name: str, config: AppConfig = Depends(get_config), current_user: UserModel | None = Depends(get_optional_rbac_user)) -> CustomSkillHistoryResponse:
    try:
        _validate_skill_name(skill_name)
        skill_name = skill_name.replace("\r\n", "").replace("\n", "")
        storage = get_or_new_skill_storage(app_config=config)
        if not storage.custom_skill_exists(skill_name) and not storage.get_skill_history_file(skill_name).exists():
            raise HTTPException(status_code=404, detail=f"Custom skill '{skill_name}' not found")

        # Check visibility
        meta = await _load_skill_meta(skill_name, config)
        visibility = meta.get("visibility", "private")
        owner_id = meta.get("owner_id")
        dept_id = meta.get("department_id")
        if current_user is not None:
            if not check_resource_access(current_user, owner_id, dept_id, visibility):
                raise HTTPException(status_code=404, detail=f"Custom skill '{skill_name}' not found")
        elif visibility != "public":
            raise HTTPException(status_code=404, detail=f"Custom skill '{skill_name}' not found")

        return CustomSkillHistoryResponse(history=storage.read_history(skill_name))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to read history for %s: %s", skill_name, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/custom/{skill_name}/rollback", response_model=CustomSkillContentResponse, summary="Rollback Custom Skill")
async def rollback_custom_skill(skill_name: str, request: SkillRollbackRequest, config: AppConfig = Depends(get_config), current_user: UserModel = Depends(get_current_rbac_user)) -> CustomSkillContentResponse:
    try:
        _validate_skill_name(skill_name)
        skill_name = skill_name.replace("\r\n", "").replace("\n", "")
        storage = get_or_new_skill_storage(app_config=config)
        if not storage.custom_skill_exists(skill_name) and not storage.get_skill_history_file(skill_name).exists():
            raise HTTPException(status_code=404, detail=f"Custom skill '{skill_name}' not found")

        # RBAC: check ownership before allowing rollback
        meta = await _load_skill_meta(skill_name, config)
        if not check_resource_modify(current_user, meta.get("owner_id"), meta.get("department_id")):
            raise HTTPException(status_code=403, detail="You do not have permission to modify this resource")
        history = storage.read_history(skill_name)
        if not history:
            raise HTTPException(status_code=400, detail=f"Custom skill '{skill_name}' has no history")
        record = history[request.history_index]
        target_content = record.get("prev_content")
        if target_content is None:
            raise HTTPException(status_code=400, detail="Selected history entry has no previous content to roll back to")
        storage.validate_skill_markdown_content(skill_name, target_content)
        scan = await scan_skill_content(target_content, executable=False, location=f"{skill_name}/{SKILL_MD_FILE}", app_config=config)
        skill_file = storage.get_custom_skill_file(skill_name)
        current_content = skill_file.read_text(encoding="utf-8") if skill_file.exists() else None
        history_entry = {
            "action": "rollback",
            "author": "human",
            "thread_id": None,
            "file_path": SKILL_MD_FILE,
            "prev_content": current_content,
            "new_content": target_content,
            "rollback_from_ts": record.get("ts"),
            "scanner": {"decision": scan.decision, "reason": scan.reason},
        }
        if scan.decision == "block":
            storage.append_history(skill_name, history_entry)
            raise HTTPException(status_code=400, detail=f"Rollback blocked by security scanner: {scan.reason}")
        storage.write_custom_skill(skill_name, SKILL_MD_FILE, target_content)
        storage.append_history(skill_name, history_entry)
        await refresh_skills_system_prompt_cache_async()
        return await get_custom_skill(skill_name, config, current_user)
    except HTTPException:
        raise
    except IndexError:
        raise HTTPException(status_code=400, detail="history_index is out of range")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to roll back custom skill %s: %s", skill_name, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/custom/{skill_name}/export",
    response_model=SkillExportResponse,
    summary="Export Custom Skill",
    description="Export a custom skill's SKILL.md content and metadata as a JSON bundle for sharing or backup.",
)
async def export_skill(
    skill_name: str,
    config: AppConfig = Depends(get_config),
    current_user: UserModel | None = Depends(get_optional_rbac_user),
) -> SkillExportResponse:
    """Export a custom skill for sharing or backup.

    RBAC: filtered by visibility — unauthenticated users can only export public skills.
    """
    try:
        _validate_skill_name(skill_name)
        skill_name = skill_name.replace("\r\n", "").replace("\n", "")
        storage = get_or_new_skill_storage(app_config=config)
        if not storage.custom_skill_exists(skill_name):
            raise HTTPException(status_code=404, detail=f"Custom skill '{skill_name}' not found")

        meta = await _load_skill_meta(skill_name, config)
        visibility = meta.get("visibility", "private")
        owner_id = meta.get("owner_id")
        dept_id = meta.get("department_id")

        if current_user is not None:
            if not check_resource_access(current_user, owner_id, dept_id, visibility):
                raise HTTPException(status_code=404, detail=f"Custom skill '{skill_name}' not found")
        elif visibility != "public":
            raise HTTPException(status_code=404, detail=f"Custom skill '{skill_name}' not found")

        content = storage.read_custom_skill(skill_name)
        return SkillExportResponse(name=skill_name, content=content, meta=meta)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to export custom skill %s: %s", skill_name, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/custom/import",
    response_model=SkillResponse,
    status_code=201,
    summary="Import Custom Skill",
    description="Import a custom skill from an exported JSON bundle.",
)
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def import_skill(
    request: SkillImportRequest,
    config: AppConfig = Depends(get_config),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> SkillResponse:
    """Import a custom skill from an export bundle.

    RBAC: all writable roles (user, department_admin, super_admin) can import.
    """
    try:
        _validate_skill_name(request.name)
        skill_name = request.name.replace("\r\n", "").replace("\n", "")
        storage = get_or_new_skill_storage(app_config=config)

        if storage.custom_skill_exists(skill_name):
            raise HTTPException(status_code=409, detail=f"Custom skill '{skill_name}' already exists")

        storage.validate_skill_markdown_content(skill_name, request.content)
        scan = await scan_skill_content(request.content, executable=False, location=f"{skill_name}/{SKILL_MD_FILE}", app_config=config)
        if scan.decision == "block":
            raise HTTPException(status_code=400, detail=f"Skill content blocked by security scanner: {scan.reason}")

        storage.write_custom_skill(skill_name, SKILL_MD_FILE, request.content)
        storage.append_history(
            skill_name,
            {
                "action": "import",
                "author": "human",
                "thread_id": None,
                "file_path": SKILL_MD_FILE,
                "prev_content": None,
                "new_content": request.content,
                "scanner": {"decision": scan.decision, "reason": scan.reason},
            },
        )

        meta = {
            "owner_id": str(current_user.id),
            "department_id": str(current_user.department_id) if current_user.department_id else None,
            "visibility": request.visibility,
        }
        await _save_skill_meta(skill_name, config, meta)
        await refresh_skills_system_prompt_cache_async()

        skill = next((s for s in storage.load_skills(enabled_only=False) if s.name == skill_name), None)
        return (
            _skill_to_response(skill)
            if skill
            else SkillResponse(
                name=skill_name,
                description=request.content.split("\n")[0] if request.content else skill_name,
                category=SkillCategory.CUSTOM,
            )
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to import skill '%s': %s", request.name, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{skill_name}",
    response_model=SkillResponse,
    summary="Get Skill Details",
    description="Retrieve detailed information about a specific skill by its name.",
)
async def get_skill(skill_name: str, config: AppConfig = Depends(get_config), current_user: UserModel | None = Depends(get_optional_rbac_user)) -> SkillResponse:
    try:
        _validate_skill_name(skill_name)
        skill_name = skill_name.replace("\r\n", "").replace("\n", "")
        skills = get_or_new_skill_storage(app_config=config).load_skills(enabled_only=False)
        skill = next((s for s in skills if s.name == skill_name), None)

        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        # Check visibility for custom skills (built-in skills are always public)
        if skill.category == SkillCategory.CUSTOM:
            meta = await _load_skill_meta(skill.name, config)
            visibility = meta.get("visibility", "private")
            owner_id = meta.get("owner_id")
            dept_id = meta.get("department_id")
            _apply_skill_meta(skill, meta)
            if current_user is not None:
                if not check_resource_access(current_user, owner_id, dept_id, visibility):
                    raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
            elif visibility != "public":
                raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        return _skill_to_response(skill)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get skill {skill_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put(
    "/{skill_name}",
    response_model=SkillResponse,
    summary="Update Skill",
    description="Update a skill's enabled status by modifying the extensions_config.json file.",
)
@require_role(UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def update_skill(skill_name: str, request: SkillUpdateRequest, http_request: Request, config: AppConfig = Depends(get_config), current_user: UserModel = Depends(get_current_rbac_user)) -> SkillResponse:
    try:
        _validate_skill_name(skill_name)
        skill_name = skill_name.replace("\r\n", "").replace("\n", "")
        skills = get_or_new_skill_storage(app_config=config).load_skills(enabled_only=False)
        skill = next((s for s in skills if s.name == skill_name), None)

        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        config_path = ExtensionsConfig.resolve_config_path()
        if config_path is None:
            raise HTTPException(status_code=500, detail="Extensions config path not configured")

        # BUG-21: Serialize read-modify-write to prevent concurrent overwrite
        with _extensions_config_lock:
            extensions_config = get_extensions_config()
            extensions_config.skills[skill_name] = SkillStateConfig(enabled=request.enabled)

            config_data = {
                "mcpServers": {name: server.model_dump() for name, server in extensions_config.mcp_servers.items()},
                "skills": {name: {"enabled": skill_config.enabled} for name, skill_config in extensions_config.skills.items()},
            }

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)

        logger.info(f"Skills configuration updated and saved to: {config_path}")
        reload_extensions_config()
        await refresh_skills_system_prompt_cache_async()

        skills = get_or_new_skill_storage(app_config=config).load_skills(enabled_only=False)
        updated_skill = next((s for s in skills if s.name == skill_name), None)

        if updated_skill is None:
            raise HTTPException(status_code=500, detail=f"Failed to reload skill '{skill_name}' after update")

        logger.info(f"Skill '{skill_name}' enabled status updated to {request.enabled}")
        await record_audit(
            actor_id=current_user.id,
            action="update",
            resource_type="skill",
            resource_id=skill_name,
            ip_address=http_request.client.host if http_request.client else None,
        )
        return _skill_to_response(updated_skill)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update skill {skill_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Skill Application routes (DEPRECATED)
# ---------------------------------------------------------------------------


@router.post("/{skill_name}/apply")
async def submit_application(skill_name: str) -> None:
    """DEPRECATED — Use POST /api/visibility-applications instead."""
    raise HTTPException(
        status_code=410,
        detail={
            "message": "This endpoint is deprecated.",
            "replacement": "POST /api/visibility-applications",
        },
    )


@router.get("/{skill_name}/application")
async def get_application(skill_name: str) -> None:
    """DEPRECATED — Use GET /api/visibility-applications instead."""
    raise HTTPException(
        status_code=410,
        detail={
            "message": "This endpoint is deprecated.",
            "replacement": "GET /api/visibility-applications",
        },
    )


@router.delete("/{skill_name}/application")
async def withdraw_application(skill_name: str) -> None:
    """DEPRECATED — Use PUT /api/visibility-applications/{id}/withdraw instead."""
    raise HTTPException(
        status_code=410,
        detail={
            "message": "This endpoint is deprecated.",
            "replacement": "PUT /api/visibility-applications/{id}/withdraw",
        },
    )
