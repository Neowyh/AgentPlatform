"""Database-backed workflow storage.

Replaces in-memory dicts with SQLAlchemy persistence for:
- Workflow YAML definitions (stored in workflow_runs.workflow_yaml)
- Workflow run states (workflow_runs table)
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.workflow import WorkflowRunRow

from .state import RunStatus, StepResult, WorkflowState

logger = logging.getLogger(__name__)


class WorkflowStore:
    """Persistent storage for workflow definitions and run states."""

    # --- Workflow YAML ---

    async def save_workflow(self, name: str, yaml_content: str) -> None:
        """Store a workflow YAML definition.

        Uses a dedicated run row with run_id=f"def:{name}" to store the
        definition alongside run data in the same table.
        """
        sf = get_session_factory()
        if sf is None:
            raise RuntimeError("Database not initialized")

        async with sf() as session:
            stmt = select(WorkflowRunRow).where(WorkflowRunRow.run_id == f"def:{name}")
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                row = WorkflowRunRow(
                    run_id=f"def:{name}",
                    workflow_name=name,
                    workflow_yaml=yaml_content,
                    status="definition",
                    inputs={},
                    steps_state={},
                )
                session.add(row)
            else:
                row.workflow_yaml = yaml_content
            await session.commit()

    async def load_workflow(self, name: str) -> str | None:
        """Load a workflow YAML definition."""
        sf = get_session_factory()
        if sf is None:
            return None

        async with sf() as session:
            stmt = select(WorkflowRunRow).where(WorkflowRunRow.run_id == f"def:{name}")
            row = (await session.execute(stmt)).scalar_one_or_none()
            return row.workflow_yaml if row else None

    async def list_workflows(self) -> list[dict[str, Any]]:
        """List all stored workflow definitions."""
        sf = get_session_factory()
        if sf is None:
            return []

        async with sf() as session:
            stmt = select(WorkflowRunRow).where(WorkflowRunRow.run_id.like("def:%"))
            rows = (await session.execute(stmt)).scalars().all()

        results = []
        for row in rows:
            try:
                from .parser import parse_workflow_string

                wf = parse_workflow_string(row.workflow_yaml)
                results.append(
                    {
                        "name": wf.name,
                        "description": wf.description,
                        "version": wf.version,
                        "steps_count": len(wf.steps),
                        "inputs": {k: v.model_dump() for k, v in wf.inputs.items()},
                    }
                )
            except Exception as e:
                results.append({"name": row.workflow_name, "error": str(e)})
        return results

    async def delete_workflow(self, name: str) -> bool:
        """Delete a workflow definition."""
        sf = get_session_factory()
        if sf is None:
            return False

        async with sf() as session:
            stmt = select(WorkflowRunRow).where(WorkflowRunRow.run_id == f"def:{name}")
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
        return True

    # --- Run State ---

    async def save_run_state(self, state: WorkflowState) -> None:
        """Persist a workflow run state (create or update)."""
        sf = get_session_factory()
        if sf is None:
            raise RuntimeError("Database not initialized")

        state_data = _state_to_dict(state)

        async with sf() as session:
            stmt = select(WorkflowRunRow).where(WorkflowRunRow.run_id == state.run_id)
            row = (await session.execute(stmt)).scalar_one_or_none()

            if row is None:
                row = WorkflowRunRow(
                    run_id=state.run_id,
                    workflow_name=state.workflow_name,
                    workflow_yaml="",  # filled by caller
                    status=state.status,
                    inputs=state.inputs,
                    steps_state=state_data["steps"],
                    current_step=state.current_step,
                    error=state.error,
                )
                session.add(row)
            else:
                row.status = state.status
                row.inputs = state.inputs
                row.steps_state = state_data["steps"]
                row.current_step = state.current_step
                row.error = state.error

            await session.commit()

    async def load_run_state(self, run_id: str) -> WorkflowState | None:
        """Load a workflow run state from the database."""
        sf = get_session_factory()
        if sf is None:
            return None

        async with sf() as session:
            stmt = select(WorkflowRunRow).where(WorkflowRunRow.run_id == run_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None
            return _row_to_state(row)

    async def update_run_status(
        self,
        run_id: str,
        status: str,
        current_step: str | None = None,
        error: str | None = None,
    ) -> None:
        """Update just the status fields of a run."""
        sf = get_session_factory()
        if sf is None:
            return

        async with sf() as session:
            stmt = select(WorkflowRunRow).where(WorkflowRunRow.run_id == run_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is not None:
                row.status = status
                if current_step is not None:
                    row.current_step = current_step
                if error is not None:
                    row.error = error
                await session.commit()

    async def save_review_result(self, run_id: str, result: dict[str, Any]) -> bool:
        """Save a human review result for a waiting run."""
        sf = get_session_factory()
        if sf is None:
            return False

        async with sf() as session:
            stmt = select(WorkflowRunRow).where(
                WorkflowRunRow.run_id == run_id,
                WorkflowRunRow.status == "waiting_human",
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return False
            row.review_result = result
            row.status = "running"
            await session.commit()
        return True

    async def list_runs(self, workflow_name: str | None = None) -> list[dict[str, Any]]:
        """List run history, optionally filtered by workflow name."""
        sf = get_session_factory()
        if sf is None:
            return []

        async with sf() as session:
            stmt = select(WorkflowRunRow).where(~WorkflowRunRow.run_id.like("def:%"))
            if workflow_name:
                stmt = stmt.where(WorkflowRunRow.workflow_name == workflow_name)
            stmt = stmt.order_by(WorkflowRunRow.created_at.desc()).limit(50)
            rows = (await session.execute(stmt)).scalars().all()

        return [
            {
                "run_id": row.run_id,
                "workflow": row.workflow_name,
                "status": row.status,
                "current_step": row.current_step,
                "error": row.error,
                "created_at": str(row.created_at) if row.created_at else None,
            }
            for row in rows
        ]


# --- Serialization helpers ---


def _state_to_dict(state: WorkflowState) -> dict[str, Any]:
    """Serialize WorkflowState to a JSON-safe dict."""
    return {
        "workflow_name": state.workflow_name,
        "run_id": state.run_id,
        "inputs": state.inputs,
        "status": state.status,
        "current_step": state.current_step,
        "error": state.error,
        "created_at": state.created_at,
        "steps": {
            sid: {
                "step_id": sr.step_id,
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


def _row_to_state(row: WorkflowRunRow) -> WorkflowState:
    """Deserialize a WorkflowRunRow back to WorkflowState."""
    state = WorkflowState(
        workflow_name=row.workflow_name,
        run_id=row.run_id,
        inputs=row.inputs or {},
        status=RunStatus(row.status),
        current_step=row.current_step,
        error=row.error,
    )
    for sid, sr_data in (row.steps_state or {}).items():
        state.steps[sid] = StepResult(
            step_id=sr_data.get("step_id", sid),
            status=sr_data.get("status", "pending"),
            output=sr_data.get("output"),
            error=sr_data.get("error"),
            retries=sr_data.get("retries", 0),
            started_at=sr_data.get("started_at"),
            finished_at=sr_data.get("finished_at"),
        )
    return state


# --- Singleton ---

_store: WorkflowStore | None = None


def get_workflow_store() -> WorkflowStore:
    """Return the global WorkflowStore singleton."""
    global _store
    if _store is None:
        _store = WorkflowStore()
    return _store
