"""Pydantic models for workflow YAML DSL."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class StepType(StrEnum):
    """Supported workflow step types."""

    AGENT = "agent"
    TOOL = "tool"
    HUMAN_REVIEW = "human_review"
    CONDITION = "condition"
    PARALLEL = "parallel"
    LOOP = "loop"
    RETRY = "retry"


class RetryPolicy(BaseModel):
    """Retry configuration for a step."""

    max: int = Field(3, ge=0)
    backoff: float = Field(5.0, ge=0)
    on_errors: list[str] = Field(default_factory=lambda: ["*"])


class InputParam(BaseModel):
    """Definition of a workflow input parameter."""

    type: str = "string"
    required: bool = False
    default: Any = None
    description: str = ""


class StepDef(BaseModel):
    """Definition of a single workflow step."""

    id: str
    type: StepType

    # agent step
    agent: str | None = None
    prompt: str | None = None

    # tool step
    tool: str | None = None
    params: dict[str, Any] | None = None

    # human_review step
    message: str | None = None
    input_schema: dict[str, Any] | None = None
    approvers: list[str] | None = None

    # condition step
    expression: str | None = None
    then: str | StepDef | None = None
    else_: str | StepDef | None = Field(None, alias="else")

    # parallel / loop
    steps: list[StepDef] | None = None
    items: str | None = None
    max_iterations: int = Field(1000, ge=0)
    fail_fast: bool = False  # BUG-12: Stop loop on first sub-step failure

    # common
    condition: str | None = None
    timeout: int | None = None
    retry: RetryPolicy | None = None
    on_error: str | None = None

    model_config = {"populate_by_name": True}


class WorkflowDef(BaseModel):
    """Top-level workflow definition parsed from YAML."""

    name: str = Field(..., max_length=60)
    description: str = ""
    version: str = "1.0"
    inputs: dict[str, InputParam] = Field(default_factory=dict)
    steps: list[StepDef] = Field(default_factory=list)
    triggers: list[dict[str, Any]] | None = None
