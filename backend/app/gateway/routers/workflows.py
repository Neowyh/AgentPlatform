"""Workflow management APIs for iDeer software factory."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
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
from ideer.config import get_app_config
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.user import UserModel, UserRole
from ideer.persistence.models.workflow_legacy import LegacyWorkflowRunRow
from ideer.workflows.v2.file_roots import collect_artifacts, make_host_resolver, render_roots, validate_read_roots, validate_workflow_roots, workflow_record_path
from ideer.workflows.v2.parser import parse_workflow_v2 as parse_workflow_string
from ideer.workflows.v2.store import WorkflowV2Store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


def _friendly_validation_error(raw: str) -> str:
    """Translate common Pydantic workflow YAML errors into actionable messages."""
    if "nodes" in raw and "action.name" in raw and "string_too_short" in raw:
        return 'action node \'name\' cannot be empty. Provide a valid agent name (e.g., "my-agent") or tool name (e.g., "web_search").'
    if "nodes" in raw and "name" in raw and "string_too_short" in raw:
        return "workflow 'name' cannot be empty. Provide a name (1-60 characters)."
    return raw


_workflow_store = ResourceMetadataStore("workflow")


async def _save_v2_definition(workflow, yaml_content: str, created_by: str):
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(503, "Workflow persistence is unavailable")
    payload = workflow.model_dump(mode="json", by_alias=True)
    return await WorkflowV2Store(sf).save_definition(workflow.name, payload, hashlib.sha256(yaml_content.encode()).hexdigest(), created_by)


def _v2_store() -> WorkflowV2Store:
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(503, "Workflow persistence is unavailable")
    return WorkflowV2Store(sf)


def _definition_yaml(definition: dict) -> str:
    return yaml.safe_dump(definition, sort_keys=False)


def _can_access_run(current_user: UserModel, run) -> bool:
    """Runs stay private to their creator, except for platform audit access."""
    return current_user.role == UserRole.SUPER_ADMIN or str(current_user.id) == str(run.created_by)


def _run_write_roots(nodes: list[dict]) -> list[str]:
    """Collect every declared write root across a definition's nodes."""
    roots: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        action = node.get("action") or {}
        if not isinstance(action, dict):
            continue
        file_access = action.get("file_access") or {}
        if not isinstance(file_access, dict):
            continue
        roots.extend(file_access.get("write") or [])
    return roots


async def _run_artifacts(store: WorkflowV2Store, run) -> list[dict]:
    """List the files a run produced under its declared write roots.

    Roots are rendered against the persisted snapshot state so a run's
    artifacts can be browsed after completion; virtual paths are returned so
    host paths never leak to the client.
    """
    definition = await store.get_definition(run.workflow_name, run.definition_version)
    if definition is None:
        return []
    nodes = definition.definition.get("nodes", []) if isinstance(definition.definition, dict) else []
    write_roots = _run_write_roots(nodes)
    if not write_roots:
        return []
    snapshot = run.snapshot if isinstance(run.snapshot, dict) else {}
    state = {
        "inputs": run.inputs or {},
        "state": snapshot.get("state", {}),
        "outputs": snapshot.get("outputs", {}),
    }
    rendered = render_roots({"write": write_roots}, state)
    resolver = make_host_resolver(run.run_id, str(run.created_by))
    return collect_artifacts(rendered.get("write", []), resolver)


def _legacy_run_payload(run: LegacyWorkflowRunRow) -> dict:
    return {
        "run_id": run.run_id,
        "workflow": run.workflow_name,
        "status": run.status,
        "current_step": run.current_step,
        "error": run.error,
        "snapshot": {"steps": run.steps_state or {}, "loop_vars": run.loop_vars or {}},
        "migration_required": True,
    }


async def _get_legacy_run(workflow_name: str, run_id: str) -> LegacyWorkflowRunRow | None:
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(503, "Workflow persistence is unavailable")
    async with sf() as session:
        return (
            await session.execute(
                select(LegacyWorkflowRunRow).where(
                    LegacyWorkflowRunRow.workflow_name == workflow_name,
                    LegacyWorkflowRunRow.run_id == run_id,
                    ~LegacyWorkflowRunRow.run_id.like("def:%"),
                )
            )
        ).scalar_one_or_none()


async def workflow_event_stream(
    store: WorkflowV2Store,
    run_id: str,
    after_seq: int,
    *,
    poll_seconds: float = 0.25,
) -> AsyncIterator[str]:
    """Replay and then tail the durable, run-local event sequence."""
    cursor = after_seq
    terminal = {"completed", "failed", "cancelled"}
    while True:
        events = await store.list_events(run_id, cursor)
        for event in events:
            cursor = event.seq
            yield f"id: {event.seq}\nevent: {event.event_type}\ndata: {json.dumps(event.payload, ensure_ascii=False)}\n\n"
        run = await store.get_run(run_id)
        if run is None or run.status in terminal:
            return
        await asyncio.sleep(poll_seconds)


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


class WorkflowCommandRequest(BaseModel):
    command_id: str = Field(min_length=1, max_length=64)
    type: str = Field(pattern="^(resume|cancel)$")
    payload: dict = Field(default_factory=dict)


# --- CRUD ---


@router.get("/{workflow_name}/legacy-runs/{run_id}")
async def get_legacy_run(
    workflow_name: str,
    run_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    meta = await _workflow_store.load_meta(workflow_name)
    if not meta or not check_resource_access(current_user, meta.get("owner_id"), meta.get("department_id"), meta.get("visibility")):
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")
    run = await _get_legacy_run(workflow_name, run_id)
    if run is None:
        raise HTTPException(404, f"Legacy run '{run_id}' not found for workflow '{workflow_name}'")
    return _legacy_run_payload(run)


@router.get("/{workflow_name}/legacy-runs")
async def list_legacy_runs(
    workflow_name: str,
    limit: int = 50,
    offset: int = 0,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    meta = await _workflow_store.load_meta(workflow_name)
    if not meta or not check_resource_access(current_user, meta.get("owner_id"), meta.get("department_id"), meta.get("visibility")):
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(503, "Workflow persistence is unavailable")
    async with sf() as session:
        rows = list(
            (
                await session.execute(
                    select(LegacyWorkflowRunRow)
                    .where(LegacyWorkflowRunRow.workflow_name == workflow_name, ~LegacyWorkflowRunRow.run_id.like("def:%"))
                    .order_by(LegacyWorkflowRunRow.created_at.desc())
                    .offset(max(offset, 0))
                    .limit(min(max(limit, 1), 200))
                )
            )
            .scalars()
            .all()
        )
    return {"runs": [_legacy_run_payload(run) for run in rows], "total": len(rows), "migration_required": True}


@router.get("")
async def list_workflows(
    limit: int = 100,
    offset: int = 0,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """List workflows visible to the current user."""
    definitions, total = await _v2_store().list_latest_definitions(limit=min(limit, 500), offset=max(offset, 0))

    # Filter by visibility using resource_metadata
    filtered: list[dict] = []
    for definition in definitions:
        meta = await _workflow_store.load_meta(definition.workflow_name)
        visibility = meta.get("visibility", "private")
        owner_id = meta.get("owner_id")
        dept_id = meta.get("department_id")

        if current_user is not None:
            if not check_resource_access(current_user, owner_id, dept_id, visibility):
                continue
        elif visibility != "public":
            continue

        filtered.append(
            {
                "name": definition.workflow_name,
                "description": definition.definition.get("description", ""),
                "version": str(definition.version),
                "steps_count": len(definition.definition.get("nodes", [])),
                "inputs": definition.definition.get("inputs", {}),
                "visibility": visibility,
                "owner_id": owner_id,
                "department_id": dept_id,
                "is_favorited": meta.get("is_favorited", False),
            }
        )

    return {"workflows": filtered, "total": total}


@router.get("/{workflow_name}")
async def get_workflow(
    workflow_name: str,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """Get workflow details."""
    definition = await _v2_store().get_latest_definition(workflow_name)
    if definition is None:
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
        wf = parse_workflow_string(_definition_yaml(definition.definition))
        result = {
            "name": wf.name,
            "description": wf.description,
            "version": str(definition.version),
            "inputs": {k: v.model_dump() for k, v in wf.inputs.items()},
            "state": {k: v.model_dump() for k, v in wf.state.items()},
            "entrypoint": wf.entrypoint,
            "nodes": [s.model_dump(by_alias=True) for s in wf.nodes],
            "edges": [e.model_dump(by_alias=True) for e in wf.edges],
            "steps": [s.model_dump(by_alias=True) for s in wf.nodes],
            "visibility": visibility,
            "owner_id": owner_id,
        }
        # P2-API-05: Only expose raw YAML to admin users
        if current_user and current_user.role in (UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN):
            result["yaml_content"] = _definition_yaml(definition.definition)
        return result
    except Exception as e:
        raise HTTPException(400, f"Invalid workflow YAML: {e}")


@router.get("/{workflow_name}/export")
async def export_workflow(
    workflow_name: str,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """Export a workflow's YAML content and metadata for sharing or backup."""
    definition = await _v2_store().get_latest_definition(workflow_name)
    if definition is None:
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
        yaml_content = _definition_yaml(definition.definition)
        wf = parse_workflow_string(yaml_content)
        return {
            "name": wf.name,
            "yaml_content": yaml_content,
            "description": wf.description,
            "version": str(definition.version),
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

    store = _v2_store()
    existing = await store.get_latest_definition(wf.name)
    if existing is not None:
        raise HTTPException(409, f"Workflow '{wf.name}' already exists")

    version = await _save_v2_definition(wf, body.yaml_content, str(current_user.id))

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
        "version": str(version.version),
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
        raise HTTPException(400, f"Invalid workflow YAML: {_friendly_validation_error(str(e))}")

    store = _v2_store()
    existing = await store.get_latest_definition(wf.name)
    if existing is not None:
        raise HTTPException(409, f"Workflow '{wf.name}' already exists")

    version = await _save_v2_definition(wf, body.yaml_content, str(current_user.id))

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
        "version": str(version.version),
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
    store = _v2_store()
    existing = await store.get_latest_definition(workflow_name)
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

    version = await _save_v2_definition(wf, body.yaml_content, str(current_user.id))

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
        "version": str(version.version),
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
    store = _v2_store()
    existing = await store.get_latest_definition(workflow_name)
    if existing is None:
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    # RBAC: check ownership before allowing delete
    meta = await _workflow_store.load_meta(workflow_name)
    if not check_resource_modify(current_user, meta.get("owner_id"), meta.get("department_id")):
        raise HTTPException(403, "You do not have permission to modify this resource")

    deleted = await _workflow_store.delete(workflow_name)
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

    # Hard-delete resource_metadata
    await record_audit(
        actor_id=current_user.id,
        action="delete",
        resource_type="workflow",
        resource_id=workflow_name,
        detail=meta if meta else None,
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
            from sqlalchemy import select

            from ideer.persistence.models.resource_metadata import ResourceMetadata

            stmt = select(ResourceMetadata).where(
                ResourceMetadata.resource_type == "workflow",
                ResourceMetadata.resource_id == workflow_name,
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
    store = _v2_store()
    definition = await store.get_latest_definition(workflow_name)
    if definition is None:
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    # Check visibility
    meta = await _workflow_store.load_meta(workflow_name)
    visibility = meta.get("visibility", "private")
    owner_id = meta.get("owner_id")
    dept_id = meta.get("department_id")
    if not check_resource_access(current_user, owner_id, dept_id, visibility):
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    try:
        wf = parse_workflow_string(_definition_yaml(definition.definition))
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

    # Reject host paths before a run is created: the sandbox only allows
    # virtual paths (/mnt/user-data, /mnt/skills, /mnt/acp-workspace and
    # configured mount container paths), so an invalid root would otherwise
    # surface only later as a soft-failed node.
    invalid_roots = validate_workflow_roots(wf.nodes, inputs)
    if invalid_roots:
        raise HTTPException(
            400,
            "Invalid file_access paths: " + "; ".join(invalid_roots) + ". Use virtual paths under /mnt/user-data, /mnt/skills, /mnt/acp-workspace, or a configured mount path.",
        )

    run_id = str(uuid.uuid4())
    # Fail fast when user-provided input roots are missing or empty: the run
    # would otherwise consume the whole pipeline and produce garbage.
    missing_read_roots = validate_read_roots(wf.nodes, inputs, make_host_resolver(run_id, str(current_user.id)))
    if missing_read_roots:
        raise HTTPException(400, "Missing input roots: " + "; ".join(missing_read_roots))

    runtime = get_app_config().workflow_runtime
    try:
        await store.create_run(
            run_id,
            workflow_name,
            definition.version,
            inputs,
            str(current_user.id),
            department_id=current_user.department_id,
            user_concurrency=runtime.user_concurrency,
            department_concurrency=runtime.department_concurrency,
        )
    except RuntimeError as exc:
        if str(exc) in {"workflow_user_concurrency_exceeded", "workflow_department_concurrency_exceeded"}:
            await record_audit(
                str(current_user.id),
                "workflow_run_rejected",
                "workflow_run",
                None,
                {
                    "workflow": workflow_name,
                    "department_id": current_user.department_id,
                    "reason": str(exc),
                },
            )
            raise HTTPException(429, str(exc)) from exc
        raise
    await record_audit(str(current_user.id), "workflow_run_created", "workflow_run", run_id, {"workflow": workflow_name, "department_id": current_user.department_id})
    return {"run_id": run_id, "status": "queued", "workflow": workflow_name}


@router.get("/{workflow_name}/runs/{run_id}")
async def get_run_status(
    workflow_name: str,
    run_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Get workflow run status."""
    store = _v2_store()
    state = await store.get_run(run_id)
    if state is None or state.workflow_name != workflow_name:
        raise HTTPException(404, f"Run '{run_id}' not found for workflow '{workflow_name}'")
    if not _can_access_run(current_user, state):
        raise HTTPException(404, f"Run '{run_id}' not found for workflow '{workflow_name}'")

    meta = await _workflow_store.load_meta(workflow_name)
    if not meta or not check_resource_access(current_user, meta.get("owner_id"), meta.get("department_id"), meta.get("visibility")):
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    return {"run_id": state.run_id, "workflow": state.workflow_name, "status": state.status, "definition_version": state.definition_version, "snapshot": state.snapshot, "error": state.error}


@router.get("/{workflow_name}/runs/{run_id}/artifacts")
async def list_run_artifacts(
    workflow_name: str,
    run_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """List the files a run produced under its declared write roots."""
    store = _v2_store()
    run = await store.get_run(run_id)
    if run is None or run.workflow_name != workflow_name:
        raise HTTPException(404, f"Run '{run_id}' not found for workflow '{workflow_name}'")
    if not _can_access_run(current_user, run):
        raise HTTPException(404, f"Run '{run_id}' not found for workflow '{workflow_name}'")
    meta = await _workflow_store.load_meta(workflow_name)
    if not meta or not check_resource_access(current_user, meta.get("owner_id"), meta.get("department_id"), meta.get("visibility")):
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")
    artifacts = await _run_artifacts(store, run)
    return {"run_id": run_id, "workflow": workflow_name, "artifacts": artifacts}


@router.get("/{workflow_name}/runs/{run_id}/artifacts/content")
async def get_run_artifact_content(
    workflow_name: str,
    run_id: str,
    path: str,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Return one artifact's file content, addressed by its virtual path."""
    store = _v2_store()
    run = await store.get_run(run_id)
    if run is None or run.workflow_name != workflow_name:
        raise HTTPException(404, f"Run '{run_id}' not found for workflow '{workflow_name}'")
    if not _can_access_run(current_user, run):
        raise HTTPException(404, f"Run '{run_id}' not found for workflow '{workflow_name}'")
    meta = await _workflow_store.load_meta(workflow_name)
    if not meta or not check_resource_access(current_user, meta.get("owner_id"), meta.get("department_id"), meta.get("visibility")):
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")
    artifacts = await _run_artifacts(store, run)
    if not any(item["path"] == path for item in artifacts):
        raise HTTPException(404, f"Artifact '{path}' not found for run '{run_id}'")
    host = make_host_resolver(run.run_id, str(run.created_by))(path)
    if host is None or not Path(host).is_file():
        raise HTTPException(404, f"Artifact '{path}' not found for run '{run_id}'")
    return FileResponse(host, media_type="application/octet-stream", filename=Path(host).name)


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

    owner_id = None if current_user.role == UserRole.SUPER_ADMIN else str(current_user.id)
    runs, total = await _v2_store().list_runs(workflow_name, limit=limit, offset=offset, created_by=owner_id)
    return {
        "runs": [{"run_id": run.run_id, "workflow": run.workflow_name, "status": run.status, "definition_version": run.definition_version, "snapshot": run.snapshot, "error": run.error} for run in runs],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{workflow_name}/runs/{run_id}/events")
async def stream_workflow_events(
    workflow_name: str,
    run_id: str,
    after_seq: int = 0,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Replay durable lifecycle events after ``after_seq`` as SSE."""
    store = _v2_store()
    run_state = await store.get_run(run_id)
    if run_state is None or run_state.workflow_name != workflow_name:
        raise HTTPException(404, f"Run '{run_id}' not found for workflow '{workflow_name}'")
    if not _can_access_run(current_user, run_state):
        raise HTTPException(404, f"Run '{run_id}' not found for workflow '{workflow_name}'")

    meta = await _workflow_store.load_meta(workflow_name)
    if not meta or not check_resource_access(current_user, meta.get("owner_id"), meta.get("department_id"), meta.get("visibility")):
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")
    return StreamingResponse(
        workflow_event_stream(store, run_id, max(0, after_seq)),
        media_type="text/event-stream",
    )


@router.get("/{workflow_name}/runs/{run_id}/record")
async def download_run_record(
    workflow_name: str,
    run_id: str,
    format: str = "md",
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Download the persisted run record (jsonl event log or markdown summary)."""
    if format not in {"jsonl", "md"}:
        raise HTTPException(400, "format must be 'jsonl' or 'md'")
    store = _v2_store()
    run = await store.get_run(run_id)
    if run is None or run.workflow_name != workflow_name:
        raise HTTPException(404, f"Run '{run_id}' not found for workflow '{workflow_name}'")
    if not _can_access_run(current_user, run):
        raise HTTPException(404, f"Run '{run_id}' not found for workflow '{workflow_name}'")
    meta = await _workflow_store.load_meta(workflow_name)
    if not meta or not check_resource_access(current_user, meta.get("owner_id"), meta.get("department_id"), meta.get("visibility")):
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")
    virtual = workflow_record_path(format)
    host = make_host_resolver(run.run_id, str(run.created_by))(virtual)
    if host is None or not Path(host).is_file():
        raise HTTPException(404, f"Run record for run '{run_id}' is not available")
    media_types = {"jsonl": "application/x-ndjson", "md": "text/markdown"}
    return FileResponse(host, media_type=media_types[format], filename=f"run_{run.run_id}.{format}")


@router.post("/{workflow_name}/runs/{run_id}/commands")
async def submit_workflow_command(
    workflow_name: str,
    run_id: str,
    body: WorkflowCommandRequest,
    request: Request,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    store = _v2_store()
    run = await store.get_run(run_id)
    if run is None or run.workflow_name != workflow_name:
        raise HTTPException(404, f"Run '{run_id}' not found for workflow '{workflow_name}'")
    if not _can_access_run(current_user, run):
        raise HTTPException(404, f"Run '{run_id}' not found for workflow '{workflow_name}'")
    meta = await _workflow_store.load_meta(workflow_name)
    if not meta or not check_resource_access(current_user, meta.get("owner_id"), meta.get("department_id"), meta.get("visibility")):
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")
    if body.type == "resume":
        if run.status == "failed":
            # a failed run can only be revived from a durable checkpoint; without
            # one LangGraph would silently restart the workflow from scratch
            checkpointer = getattr(request.app.state, "checkpointer", None)
            if checkpointer is not None:
                ckpt = await checkpointer.aget_tuple({"configurable": {"thread_id": run.checkpoint_thread_id}})
                if ckpt is None:
                    raise HTTPException(409, "Run has no checkpoint to resume from")
        elif current_user.role != UserRole.SUPER_ADMIN:
            definition = await store.get_definition(workflow_name, run.definition_version)
            interrupt_node = run.snapshot.get("interrupt", {}).get("node_id") if isinstance(run.snapshot, dict) else None
            required_roles = {role for node in (definition.definition.get("nodes", []) if definition else []) if node.get("id") == interrupt_node for role in node.get("roles", [])}
            if required_roles and current_user.role.value not in required_roles:
                raise HTTPException(403, "You do not have permission to resume this workflow")
    command = await store.submit_command(body.command_id, run_id, body.type, body.payload, str(current_user.id))
    await record_audit(
        str(current_user.id),
        f"workflow_run_{body.type}",
        "workflow_run",
        run_id,
        {"command_id": command.command_id, "workflow": workflow_name},
    )
    return {"command_id": command.command_id, "run_id": command.run_id, "type": command.command_type, "accepted": True}
