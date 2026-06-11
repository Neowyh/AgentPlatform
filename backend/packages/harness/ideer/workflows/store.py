"""Database-backed workflow storage.

Replaces in-memory dicts with SQLAlchemy persistence for:
- Workflow YAML definitions (stored in workflow_runs.workflow_yaml)
- Workflow run states (workflow_runs table)
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select, update

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
            logger.warning("load_workflow(%s): database not initialized, returning None", name)
            return None

        async with sf() as session:
            stmt = select(WorkflowRunRow).where(WorkflowRunRow.run_id == f"def:{name}")
            row = (await session.execute(stmt)).scalar_one_or_none()
            return row.workflow_yaml if row else None

    async def list_workflows(self, limit: int = 100, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        """List stored workflow definitions with pagination.

        Returns (items, total_count).
        """
        sf = get_session_factory()
        if sf is None:
            logger.warning("list_workflows: database not initialized, returning empty list")
            return [], 0

        async with sf() as session:
            # Get total count
            count_stmt = select(func.count()).select_from(WorkflowRunRow).where(WorkflowRunRow.run_id.startswith("def:"))
            total = (await session.execute(count_stmt)).scalar() or 0

            # Get page
            stmt = select(WorkflowRunRow).where(WorkflowRunRow.run_id.startswith("def:")).order_by(WorkflowRunRow.created_at.desc()).offset(offset).limit(limit)
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
        return results, total

    async def delete_workflow(self, name: str) -> bool:
        """Delete a workflow definition."""
        sf = get_session_factory()
        if sf is None:
            logger.warning("delete_workflow(%s): database not initialized, returning False", name)
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
                    loop_vars=state_data.get("loop_vars", {}),
                )
                session.add(row)
            else:
                row.status = state.status
                row.inputs = state.inputs
                row.steps_state = state_data["steps"]
                row.current_step = state.current_step
                row.error = state.error
                row.loop_vars = state_data.get("loop_vars", {})

            await session.commit()

    async def load_run_state(self, run_id: str) -> WorkflowState | None:
        """Load a workflow run state from the database."""
        sf = get_session_factory()
        if sf is None:
            logger.warning("load_run_state(%s): database not initialized, returning None", run_id)
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
        # Validate status against enum to prevent invalid values from being persisted
        valid_statuses = {s.value for s in RunStatus}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Valid: {valid_statuses}")

        sf = get_session_factory()
        if sf is None:
            logger.warning("update_run_status(%s): database not initialized, skipping", run_id)
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
        """Save a human review result for a waiting run (atomic UPDATE)."""
        sf = get_session_factory()
        if sf is None:
            logger.warning("save_review_result(%s): database not initialized, returning False", run_id)
            return False

        async with sf() as session:
            stmt = (
                update(WorkflowRunRow)
                .where(
                    WorkflowRunRow.run_id == run_id,
                    WorkflowRunRow.status == RunStatus.WAITING_HUMAN,
                )
                .values(review_result=result, status=RunStatus.RUNNING)
                .execution_options(synchronize_session="fetch")
            )
            result_proxy = await session.execute(stmt)
            if result_proxy.rowcount == 0:
                return False
            await session.commit()
        return True

    async def list_runs(
        self,
        workflow_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List run history, optionally filtered by workflow name. Returns (runs, total_count)."""
        sf = get_session_factory()
        if sf is None:
            logger.warning("list_runs: database not initialized, returning empty list")
            return [], 0

        # Clamp limit and offset
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        async with sf() as session:
            base_stmt = select(WorkflowRunRow).where(~WorkflowRunRow.run_id.like("def:%"))
            if workflow_name:
                base_stmt = base_stmt.where(WorkflowRunRow.workflow_name == workflow_name)

            # Get total count
            count_stmt = select(func.count()).select_from(base_stmt.subquery())
            total = (await session.execute(count_stmt)).scalar() or 0

            # Get paginated rows
            stmt = base_stmt.order_by(WorkflowRunRow.created_at.desc()).limit(limit).offset(offset)
            rows = (await session.execute(stmt)).scalars().all()

        runs = [
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
        return runs, total


# --- Serialization helpers ---


def _json_safe(obj: Any) -> Any:
    """Recursively ensure value is JSON-serializable, preserving dict/list structure."""
    import json

    # Fast path: already serializable
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        pass
    # Recursive sanitization for compound types
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    # Leaf fallback: convert to string representation
    return str(obj)


def _state_to_dict(state: WorkflowState) -> dict[str, Any]:
    """Serialize WorkflowState to a JSON-safe dict."""
    return {
        "workflow_name": state.workflow_name,
        "run_id": state.run_id,
        "inputs": state.inputs,
        "status": state.status,
        "current_step": state.current_step,
        "error": state.error,
        "review_result": _json_safe(state.review_result) if state.review_result is not None else None,
        "loop_vars": _json_safe(state.loop_vars) if state.loop_vars else {},
        "created_at": state.created_at,
        "steps": {
            sid: {
                "step_id": sr.step_id,
                "status": sr.status,
                "output": _json_safe(sr.output),
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
    try:
        status = RunStatus(row.status)
    except ValueError:
        logger.warning("Unknown run status '%s' for run %s, defaulting to FAILED", row.status, row.run_id)
        status = RunStatus.FAILED
    state = WorkflowState(
        workflow_name=row.workflow_name,
        run_id=row.run_id,
        inputs=row.inputs or {},
        status=status,
        current_step=row.current_step,
        error=row.error,
        review_result=getattr(row, "review_result", None),
    )
    # BUG-15: Restore loop_vars from DB
    state.loop_vars = getattr(row, "loop_vars", None) or {}
    # Restore original creation timestamp from DB (overrides field default)
    if row.created_at is not None:
        state.created_at = row.created_at.isoformat() if hasattr(row.created_at, "isoformat") else str(row.created_at)
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
