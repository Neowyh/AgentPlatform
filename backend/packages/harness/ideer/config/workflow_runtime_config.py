"""Operational limits for durable workflow-v2 execution."""

from pydantic import BaseModel, Field


class WorkflowRuntimeConfig(BaseModel):
    user_concurrency: int = Field(default=3, ge=1)
    department_concurrency: int = Field(default=10, ge=1)
    max_parallel_actions: int = Field(default=3, ge=1)
    node_timeout_seconds: int = Field(default=900, ge=1)
    max_events_per_run: int = Field(default=10_000, ge=1)
    lease_seconds: int = Field(default=30, ge=1)
    heartbeat_seconds: int = Field(default=10, ge=1)
    max_attempts: int = Field(default=3, ge=1)
