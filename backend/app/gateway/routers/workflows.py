"""Workflow management APIs for iDeer software factory."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user, require_role
from ideer.persistence.models.user import UserModel, UserRole
from ideer.workflows.executor import WorkflowExecutor, get_active_run
from ideer.workflows.parser import parse_workflow_string
from ideer.workflows.steps.human_step import get_pending_review, resume_review

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

# In-memory workflow storage (YAML content keyed by name)
_workflow_store: dict[str, str] = {}

# Workflow file directory
_WORKFLOW_DIR = Path("workflows")


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


def _get_workflow_dir() -> Path:
    """Get or create the workflow directory."""
    _WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
    return _WORKFLOW_DIR


def _load_workflows_from_disk() -> None:
    """Load all YAML files from the workflow directory into memory."""
    wf_dir = _get_workflow_dir()
    for f in wf_dir.glob("*.yaml"):
        name = f.stem
        if name not in _workflow_store:
            _workflow_store[name] = f.read_text(encoding="utf-8")


# --- CRUD ---


@router.get("")
async def list_workflows(
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """List all workflows."""
    _load_workflows_from_disk()

    workflows = []
    for name, yaml_content in sorted(_workflow_store.items()):
        try:
            wf = parse_workflow_string(yaml_content)
            workflows.append(
                {
                    "name": wf.name,
                    "description": wf.description,
                    "version": wf.version,
                    "steps_count": len(wf.steps),
                    "inputs": {k: v.model_dump() for k, v in wf.inputs.items()},
                }
            )
        except Exception as e:
            workflows.append({"name": name, "error": str(e)})

    return {"workflows": workflows, "total": len(workflows)}


@router.get("/{workflow_name}")
async def get_workflow(
    workflow_name: str,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """Get workflow details."""
    _load_workflows_from_disk()

    yaml_content = _workflow_store.get(workflow_name)
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

    if wf.name in _workflow_store:
        raise HTTPException(409, f"Workflow '{wf.name}' already exists")

    # Store in memory and on disk
    _workflow_store[wf.name] = body.yaml_content
    wf_dir = _get_workflow_dir()
    (wf_dir / f"{wf.name}.yaml").write_text(body.yaml_content, encoding="utf-8")

    return {"name": wf.name, "description": wf.description, "version": wf.version}


@router.put("/{workflow_name}")
@require_role(UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def update_workflow(
    workflow_name: str,
    body: WorkflowUpdateRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Update an existing workflow."""
    if workflow_name not in _workflow_store:
        # Try loading from disk
        _load_workflows_from_disk()
        if workflow_name not in _workflow_store:
            raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    # Validate new YAML
    try:
        wf = parse_workflow_string(body.yaml_content)
    except Exception as e:
        raise HTTPException(400, f"Invalid workflow YAML: {e}")

    _workflow_store[workflow_name] = body.yaml_content
    wf_dir = _get_workflow_dir()
    (wf_dir / f"{workflow_name}.yaml").write_text(body.yaml_content, encoding="utf-8")

    return {"name": wf.name, "description": wf.description, "version": wf.version}


@router.delete("/{workflow_name}")
@require_role(UserRole.SUPER_ADMIN)
async def delete_workflow(
    workflow_name: str,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Delete a workflow."""
    _load_workflows_from_disk()

    if workflow_name not in _workflow_store:
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")

    del _workflow_store[workflow_name]
    wf_file = _get_workflow_dir() / f"{workflow_name}.yaml"
    if wf_file.exists():
        wf_file.unlink()

    return {"success": True}


# --- Execution ---


@router.post("/{workflow_name}/run")
async def run_workflow(
    workflow_name: str,
    body: WorkflowRunRequest,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """Start a workflow execution."""
    _load_workflows_from_disk()

    yaml_content = _workflow_store.get(workflow_name)
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
    executor = WorkflowExecutor(wf)

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
    state = get_active_run(run_id)
    if state is None:
        raise HTTPException(404, "Run not found or already completed")

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


@router.post("/{workflow_name}/runs/{run_id}/review")
async def submit_review(
    workflow_name: str,
    run_id: str,
    body: HumanReviewRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Submit a human review result to resume a paused workflow."""
    if not get_pending_review(run_id):
        raise HTTPException(404, "No pending review for this run")

    ok = await resume_review(run_id, {"approved": body.approved, **body.data})
    if not ok:
        raise HTTPException(400, "Failed to resume review")

    return {"success": True, "run_id": run_id}
