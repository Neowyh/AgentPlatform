"""Workflow execution state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StepResult:
    """Result of a single step execution."""

    step_id: str
    status: str = "pending"
    output: Any = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    retries: int = 0


@dataclass
class WorkflowState:
    """Mutable state shared across all steps of a workflow run."""

    workflow_name: str
    run_id: str
    inputs: dict[str, Any] = field(default_factory=dict)
    steps: dict[str, StepResult] = field(default_factory=dict)
    status: RunStatus = RunStatus.PENDING
    current_step: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    error: str | None = None

    def get_context(self) -> dict[str, Any]:
        """Build the template rendering context.

        Returns ``{"inputs": {...}, "steps": {"id": {"output": …}, …}}``
        so Jinja-style ``{{inputs.xxx}}`` / ``{{steps.xxx.output}}`` work.
        """
        return {
            "inputs": self.inputs,
            "steps": {sid: {"output": sr.output, "status": sr.status} for sid, sr in self.steps.items()},
        }

    def set_step_result(self, step_id: str, **kwargs: Any) -> None:
        """Create or update a StepResult."""
        if step_id not in self.steps:
            self.steps[step_id] = StepResult(step_id=step_id)
        sr = self.steps[step_id]
        for k, v in kwargs.items():
            setattr(sr, k, v)
