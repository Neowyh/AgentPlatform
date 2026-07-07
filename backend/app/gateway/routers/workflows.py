"""Workflow management APIs for iDeer software factory."""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.gateway.audit import record_audit
from app.gateway.authz import (
    check_resource_access,
    check_resource_modify,
    get_current_rbac_user,
    get_optional_rbac_user,
    require_role,
)
from app.gateway.utils import ResourceMetadataStore
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.user import UserModel, UserRole
from ideer.workflows.executor import WorkflowExecutor
from ideer.workflows.parser import parse_workflow_string
from ideer.workflows.store import get_workflow_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

_workflow_store = ResourceMetadataStore("workflow")


# Keep strong references to background tasks to prevent GC before completion
_background_tasks: set[asyncio.Task] = set()


class WorkflowCreateRequest(BaseModel):
    name: str = ""  # Optional; derived from yaml_content if empty
    yaml_content: str


class WorkflowUpdateRequest(BaseModel):
    yaml_content: str
    version: int = Field(..., description="Current resource version for optimistic locking")


class WorkflowRunRequest(BaseModel):
    inputs: dict = Field(default_factory=dict)


class WorkflowExportResponse(BaseModel):
    """Response model for workflow export."""

    name: str
    yaml_content: str
    description: str = ""
    version: str = ""
    visibility: str = "private"
    owner_id: str | None = None
    department_id: str | None = None


class WorkflowImportRequest(BaseModel):
    """Request body for workflow import."""

    yaml_content: str = Field(..., description="Workflow YAML content")
    visibility: str = Field(default="private", description="Visibility: private, department, or public")


class HumanReviewRequest(BaseModel):
    approved: bool
    data: dict = Field(default_factory=dict)


# --- CRUD ---


@router.get("")
async def list_workflows(
    limit: int = 100,
    offset: int = 0,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """List workflows visible to the current user."""
    store = get_workflow_store()
    workflows, total = await store.list_workflows(limit=min(limit, 500), offset=max(offset, 0))

    # Filter by visibility using resource_metadata
    filtered: list[dict] = []
    for wf in workflows:
        meta = await _workflow_store.load_meta(wf["name"])
        visibility = meta.get("visibility", "private")
        owner_id = meta.get("owner_id")
        dept_id = meta.get("department_id")

        if current_user is not None:
            if not check_resource_access(current_user, owner_id, dept_id, visibility):
                continue
        elif visibility != "public":
            continue

        wf["visibility"] = visibility
        wf["owner_id"] = owner_id
        wf["department_id"] = dept_id
        wf["is_favorited"] = meta.get("is_favorited", False)
        filtered.append(wf)

    return {"workflows": filtered, "total": len(filtered)}


@router.get("/{workflow_name}")
async def get_workflow(
    workflow_name: str,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """Get workflow details."""
    store = get_workflow_store()
    yaml_content = await store.load_workflow(workflow_name)
    if yaml_content is None:
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    # Check visibility
    meta = await _workflow_store.load_meta(workflow_name)
    visibility = meta.get("visibility", "private")
    owner_id = meta.get("owner_id")
    dept_id = meta.get("department_id")

    if current_user is not None:
        if not check_resource_access(current_user, owner_id, dept_id, visibility):
            raise HTTPException(404, f"Workflow '{workflow_name}' not found")
    elif visibility != "public":
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    try:
        wf = parse_workflow_string(yaml_content)
        result = {
            "name": wf.name,
            "description": wf.description,
            "version": wf.version,
            "inputs": {k: v.model_dump() for k, v in wf.inputs.items()},
            "steps": [s.model_dump(by_alias=True) for s in wf.steps],
            "visibility": visibility,
            "owner_id": owner_id,
        }
        # P2-API-05: Only expose raw YAML to admin users
        if current_user and current_user.role in (UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN):
            result["yaml_content"] = yaml_content
        return result
    except Exception as e:
        raise HTTPException(400, f"Invalid workflow YAML: {e}")


@router.get("/{workflow_name}/export")
async def export_workflow(
    workflow_name: str,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """Export a workflow's YAML content and metadata for sharing or backup."""
    store = get_workflow_store()
    yaml_content = await store.load_workflow(workflow_name)
    if yaml_content is None:
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    meta = await _workflow_store.load_meta(workflow_name)
    visibility = meta.get("visibility", "private")
    owner_id = meta.get("owner_id")
    dept_id = meta.get("department_id")

    if current_user is not None:
        if not check_resource_access(current_user, owner_id, dept_id, visibility):
            raise HTTPException(404, f"Workflow '{workflow_name}' not found")
    elif visibility != "public":
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    try:
        wf = parse_workflow_string(yaml_content)
        return {
            "name": wf.name,
            "yaml_content": yaml_content,
            "description": wf.description,
            "version": wf.version,
            "visibility": visibility,
            "owner_id": owner_id,
            "department_id": dept_id,
        }
    except Exception as e:
        raise HTTPException(400, f"Invalid workflow YAML: {e}")


@router.post(
    "/import",
    status_code=201,
)
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def import_workflow(
    body: WorkflowImportRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Import a workflow from exported YAML content."""
    # Validate YAML
    try:
        wf = parse_workflow_string(body.yaml_content)
    except Exception as e:
        raise HTTPException(400, f"Invalid workflow YAML: {e}")

    store = get_workflow_store()
    existing = await store.load_workflow(wf.name)
    if existing is not None:
        raise HTTPException(409, f"Workflow '{wf.name}' already exists")

    await store.save_workflow(wf.name, body.yaml_content)

    owner_id = current_user.id if current_user else "system"
    dept_id = current_user.department_id if current_user else None
    meta = {
        "visibility": body.visibility,
        "owner_id": owner_id,
        "department_id": dept_id,
    }
    if not await _workflow_store.save_meta(wf.name, meta):
        logger.error("Failed to save workflow metadata for '%s' to database", wf.name)

    return {
        "name": wf.name,
        "description": wf.description,
        "version": wf.version,
        "steps_count": len(wf.steps),
        "inputs": {k: v.model_dump() for k, v in wf.inputs.items()},
        "visibility": body.visibility,
        "owner_id": owner_id,
    }


@router.post("")
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def create_workflow(
    body: WorkflowCreateRequest,
    http_request: Request,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Create a new workflow from YAML content."""
    # Validate YAML
    try:
        wf = parse_workflow_string(body.yaml_content)
    except Exception as e:
        raise HTTPException(400, f"Invalid workflow YAML: {e}")

    store = get_workflow_store()
    existing = await store.load_workflow(wf.name)
    if existing is not None:
        raise HTTPException(409, f"Workflow '{wf.name}' already exists")

    await store.save_workflow(wf.name, body.yaml_content)

    # Persist RBAC metadata — default to private
    owner_id = current_user.id if current_user else "system"
    dept_id = current_user.department_id if current_user else None
    meta = {
        "visibility": "private",
        "owner_id": owner_id,
        "department_id": dept_id,
    }
    if not await _workflow_store.save_meta(wf.name, meta):
        logger.error("Failed to save workflow metadata for '%s' to database", wf.name)

    await record_audit(
        actor_id=current_user.id,
        action="create",
        resource_type="workflow",
        resource_id=wf.name,
        ip_address=http_request.client.host if http_request.client else None,
    )

    return {
        "name": wf.name,
        "description": wf.description,
        "version": wf.version,
        "steps_count": len(wf.steps),
        "inputs": {k: v.model_dump() for k, v in wf.inputs.items()},
        "visibility": "private",
        "owner_id": owner_id,
    }


@router.put("/{workflow_name}")
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def update_workflow(
    workflow_name: str,
    body: WorkflowUpdateRequest,
    http_request: Request,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Update an existing workflow."""
    store = get_workflow_store()
    existing = await store.load_workflow(workflow_name)
    if existing is None:
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    # RBAC: check ownership before allowing edit
    meta = await _workflow_store.load_meta(workflow_name)
    if not check_resource_modify(current_user, meta.get("owner_id"), meta.get("department_id")):
        raise HTTPException(403, "You do not have permission to modify this resource")

    # Optimistic locking: verify version matches
    from app.gateway.error_codes import ApiException

    current_version = meta.get("version")
    if current_version is not None and body.version != current_version:
        raise ApiException("VERSION_CONFLICT", "乐观锁冲突，需刷新重试")

    # Validate new YAML
    try:
        wf = parse_workflow_string(body.yaml_content)
    except Exception as e:
        raise HTTPException(400, f"Invalid workflow YAML: {e}")

    # Ensure YAML name matches the URL path to prevent ghost entries
    if wf.name != workflow_name:
        raise HTTPException(
            400,
            f"Workflow name in YAML ('{wf.name}') does not match URL path ('{workflow_name}'). Either rename the YAML to match, or create a new workflow.",
        )

    await store.save_workflow(workflow_name, body.yaml_content)

    # Increment version in resource_metadata
    if not await _workflow_store.save_meta(
        workflow_name,
        {
            "visibility": meta.get("visibility", "private"),
            "department_id": meta.get("department_id"),
            "owner_id": meta.get("owner_id"),
        },
    ):
        logger.error("Failed to save workflow metadata for '%s' — version not incremented", workflow_name)

    await record_audit(
        actor_id=current_user.id,
        action="update",
        resource_type="workflow",
        resource_id=workflow_name,
        ip_address=http_request.client.host if http_request.client else None,
    )

    return {
        "name": workflow_name,
        "description": wf.description,
        "version": wf.version,
        "steps_count": len(wf.steps),
        "inputs": {k: v.model_dump() for k, v in wf.inputs.items()},
    }


@router.delete("/{workflow_name}")
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def delete_workflow(
    workflow_name: str,
    http_request: Request,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Delete a workflow."""
    store = get_workflow_store()
    existing = await store.load_workflow(workflow_name)
    if existing is None:
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    # RBAC: check ownership before allowing delete
    meta = await _workflow_store.load_meta(workflow_name)
    if not check_resource_modify(current_user, meta.get("owner_id"), meta.get("department_id")):
        raise HTTPException(403, "You do not have permission to modify this resource")

    deleted = await store.delete_workflow(workflow_name)
    if not deleted:
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

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
                        VisibilityApplication.resource_type == "workflow",
                        VisibilityApplication.resource_id == workflow_name,
                        VisibilityApplication.status == "pending",
                    )
                    .values(status="rejected", review_comment="资源已删除，申请自动关闭")
                )
                await session.commit()
        except Exception:
            logger.warning("Failed to auto-reject pending applications for deleted workflow %s", workflow_name)

    # Soft delete resource_metadata
    if not await _workflow_store.soft_delete(workflow_name):
        logger.warning("Failed to soft delete metadata for workflow '%s'", workflow_name)

    await record_audit(
        actor_id=current_user.id,
        action="delete",
        resource_type="workflow",
        resource_id=workflow_name,
        ip_address=http_request.client.host if http_request.client else None,
    )

    return {"success": True}


# --- Execution ---


@router.post("/{workflow_name}/favorite")
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def toggle_workflow_favorite(
    workflow_name: str,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Toggle favorite status for a workflow."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(500, "Database not available")

    try:
        async with sf() as session:
            from ideer.persistence.models.resource_metadata import ResourceMetadata

            stmt = select(ResourceMetadata).where(
                ResourceMetadata.resource_type == "workflow",
                ResourceMetadata.resource_id == workflow_name,
                ResourceMetadata.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            resource = result.scalar_one_or_none()
            if resource:
                resource.is_favorited = not resource.is_favorited
                resource.version = ResourceMetadata.version + 1
            else:
                raise HTTPException(404, f"Workflow '{workflow_name}' not found")

            await session.commit()
            return {"success": True, "is_favorited": resource.is_favorited}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle favorite for workflow '{workflow_name}': {e}", exc_info=True)
        raise HTTPException(500, "Internal server error")


@router.post("/{workflow_name}/run")
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def run_workflow(
    workflow_name: str,
    body: WorkflowRunRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Start a workflow execution."""
    store = get_workflow_store()
    yaml_content = await store.load_workflow(workflow_name)
    if yaml_content is None:
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    # Check visibility
    meta = await _workflow_store.load_meta(workflow_name)
    visibility = meta.get("visibility", "private")
    owner_id = meta.get("owner_id")
    dept_id = meta.get("department_id")
    if not check_resource_access(current_user, owner_id, dept_id, visibility):
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    try:
        wf = parse_workflow_string(yaml_content)
    except Exception as e:
        raise HTTPException(400, f"Invalid workflow YAML: {e}")

    # Validate required inputs
    for name, param in wf.inputs.items():
        if param.required and name not in body.inputs and param.default is None:
            raise HTTPException(400, f"Missing required input: '{name}'")

    # Validate input types
    for name, value in body.inputs.items():
        if name in wf.inputs:
            expected_type = wf.inputs[name].type
            # Note: bool is a subclass of int in Python, so check bool BEFORE number
            if expected_type == "boolean" and not isinstance(value, bool):
                raise HTTPException(400, f"Input '{name}' expects boolean, got {type(value).__name__}")
            elif expected_type == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise HTTPException(400, f"Input '{name}' expects number, got {type(value).__name__}")
            elif expected_type == "string" and not isinstance(value, str):
                raise HTTPException(400, f"Input '{name}' expects string, got {type(value).__name__}")

    # Apply defaults
    inputs = dict(body.inputs)
    for name, param in wf.inputs.items():
        if name not in inputs and param.default is not None:
            inputs[name] = param.default

    run_id = str(uuid.uuid4())
    executor = WorkflowExecutor(wf, store)

    # Run in background with error logging
    # Note: WorkflowExecutor.run() already handles state updates on failure
    async def _run_workflow():
        try:
            await executor.run(inputs, run_id=run_id)
        except Exception:
            logger.exception("Workflow %s run %s failed", workflow_name, run_id)

    task = asyncio.create_task(_run_workflow())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"run_id": run_id, "status": "running", "workflow": workflow_name}


@router.get("/{workflow_name}/runs/{run_id}")
async def get_run_status(
    workflow_name: str,
    run_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Get workflow run status."""
    store = get_workflow_store()
    state = await store.load_run_state(run_id)
    if state is None or state.workflow_name != workflow_name:
        raise HTTPException(404, f"Run '{run_id}' not found for workflow '{workflow_name}'")

    meta = await _workflow_store.load_meta(workflow_name)
    if not meta or not check_resource_access(current_user, meta.get("owner_id"), meta.get("department_id"), meta.get("visibility")):
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    return {
        "run_id": state.run_id,
        "workflow": state.workflow_name,
        "status": state.status,
        "current_step": state.current_step,
        "error": state.error,
        "steps": {
            sid: {
                "status": sr.status,
                "output": sr.output,
                "error": sr.error,
                "retries": sr.retries,
                "started_at": sr.started_at,
                "finished_at": sr.finished_at,
            }
            for sid, sr in state.steps.items()
        },
    }


@router.get("/{workflow_name}/runs")
async def list_runs(
    workflow_name: str,
    limit: int = 50,
    offset: int = 0,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """List run history for a workflow."""
    meta = await _workflow_store.load_meta(workflow_name)
    if not meta or not check_resource_access(current_user, meta.get("owner_id"), meta.get("department_id"), meta.get("visibility")):
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    # Clamp limit and offset to match store behavior
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    store = get_workflow_store()
    runs, total = await store.list_runs(workflow_name, limit=limit, offset=offset)
    return {"runs": runs, "total": total, "limit": limit, "offset": offset}


@router.post("/{workflow_name}/runs/{run_id}/review")
async def submit_review(
    workflow_name: str,
    run_id: str,
    body: HumanReviewRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Submit a human review result to resume a paused workflow."""
    store = get_workflow_store()
    # Verify the run belongs to this workflow
    run_state = await store.load_run_state(run_id)
    if run_state is None or run_state.workflow_name != workflow_name:
        raise HTTPException(404, f"Run '{run_id}' not found for workflow '{workflow_name}'")

    # BUG-05: Validate approver permissions if the workflow defines approvers
    yaml_content = await store.load_workflow(workflow_name)
    if yaml_content:
        try:
            wf = parse_workflow_string(yaml_content)
            # Find the human_review step that is currently waiting
            for step in wf.steps:
                if step.type.value == "human_review" and step.approvers:
                    # Check if current user is in approvers list or is super_admin
                    user_identifiers = {current_user.id, current_user.username}
                    if not user_identifiers.intersection(set(step.approvers)) and current_user.role != UserRole.SUPER_ADMIN:
                        raise HTTPException(403, "You are not an approver for this workflow step")
                    break
        except HTTPException:
            raise
        except Exception:
            pass  # Don't block review if YAML parsing fails

    # Build review result — keep 'approved' at top level, merge extra data
    # but strip any 'approved' key from body.data to prevent overwrite.
    safe_data = {k: v for k, v in (body.data or {}).items() if k != "approved"}
    review_payload = {"approved": body.approved, **safe_data}
    ok = await store.save_review_result(run_id, review_payload)
    if not ok:
        # Re-check run status to provide a better error message
        current = await store.load_run_state(run_id)
        if current is None:
            raise HTTPException(404, f"Run '{run_id}' not found")
        raise HTTPException(409, f"Run '{run_id}' is in status '{current.status}', not waiting for review")
    return {"success": True, "run_id": run_id}
