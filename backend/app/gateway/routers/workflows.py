"""Workflow management APIs for iDeer software factory."""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user, require_role
from ideer.persistence.models.user import UserModel, UserRole
from ideer.workflows.executor import WorkflowExecutor
from ideer.workflows.parser import parse_workflow_string
from ideer.workflows.store import get_workflow_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class WorkflowCreateRequest(BaseModel):
    name: str
    yaml_content: str


class WorkflowUpdateRequest(BaseModel):
    yaml_content: str


class WorkflowRunRequest(BaseModel):
    inputs: dict = {}


class HumanReviewRequest(BaseModel):
    approved: bool
    data: dict = {}


# --- CRUD ---


@router.get("")
async def list_workflows(
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """List all workflows."""
    store = get_workflow_store()
    workflows = await store.list_workflows()
    return {"workflows": workflows, "total": len(workflows)}


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

    try:
        wf = parse_workflow_string(yaml_content)
        return {
            "name": wf.name,
            "description": wf.description,
            "version": wf.version,
            "inputs": {k: v.model_dump() for k, v in wf.inputs.items()},
            "steps": [s.model_dump(by_alias=True) for s in wf.steps],
            "yaml_content": yaml_content,
        }
    except Exception as e:
        raise HTTPException(400, f"Invalid workflow YAML: {e}")


@router.post("")
@require_role(UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def create_workflow(
    body: WorkflowCreateRequest,
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
    return {"name": wf.name, "description": wf.description, "version": wf.version}


@router.put("/{workflow_name}")
@require_role(UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def update_workflow(
    workflow_name: str,
    body: WorkflowUpdateRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Update an existing workflow."""
    store = get_workflow_store()
    existing = await store.load_workflow(workflow_name)
    if existing is None:
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    # Validate new YAML
    try:
        wf = parse_workflow_string(body.yaml_content)
    except Exception as e:
        raise HTTPException(400, f"Invalid workflow YAML: {e}")

    await store.save_workflow(workflow_name, body.yaml_content)
    return {"name": wf.name, "description": wf.description, "version": wf.version}


@router.delete("/{workflow_name}")
@require_role(UserRole.SUPER_ADMIN)
async def delete_workflow(
    workflow_name: str,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Delete a workflow."""
    store = get_workflow_store()
    deleted = await store.delete_workflow(workflow_name)
    if not deleted:
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")
    return {"success": True}


# --- Execution ---


@router.post("/{workflow_name}/run")
async def run_workflow(
    workflow_name: str,
    body: WorkflowRunRequest,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """Start a workflow execution."""
    store = get_workflow_store()
    yaml_content = await store.load_workflow(workflow_name)
    if yaml_content is None:
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    try:
        wf = parse_workflow_string(yaml_content)
    except Exception as e:
        raise HTTPException(400, f"Invalid workflow YAML: {e}")

    # Validate required inputs
    for name, param in wf.inputs.items():
        if param.required and name not in body.inputs and param.default is None:
            raise HTTPException(400, f"Missing required input: '{name}'")

    # Apply defaults
    inputs = dict(body.inputs)
    for name, param in wf.inputs.items():
        if name not in inputs and param.default is not None:
            inputs[name] = param.default

    run_id = str(uuid.uuid4())
    executor = WorkflowExecutor(wf, store)

    # Run in background
    asyncio.create_task(executor.run(inputs, run_id=run_id))

    return {"run_id": run_id, "status": "running", "workflow": workflow_name}


@router.get("/{workflow_name}/runs/{run_id}")
async def get_run_status(
    workflow_name: str,
    run_id: str,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """Get workflow run status."""
    store = get_workflow_store()
    state = await store.load_run_state(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")

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
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """List run history for a workflow."""
    store = get_workflow_store()
    runs = await store.list_runs(workflow_name)
    return {"runs": runs, "total": len(runs)}


@router.post("/{workflow_name}/runs/{run_id}/review")
async def submit_review(
    workflow_name: str,
    run_id: str,
    body: HumanReviewRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Submit a human review result to resume a paused workflow."""
    store = get_workflow_store()
    ok = await store.save_review_result(run_id, {"approved": body.approved, **body.data})
    if not ok:
        raise HTTPException(404, "No pending review for this run")
    return {"success": True, "run_id": run_id}
