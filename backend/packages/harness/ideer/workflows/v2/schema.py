"""Governed, declarative workflow v2 schema."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

ScalarType = Literal["string", "integer", "number", "boolean", "object", "array"]


class ValueSpec(BaseModel):
    type: ScalarType
    required: bool = False
    default: Any = None
    description: str = ""


class RetrySpec(BaseModel):
    max_attempts: int = Field(1, ge=1)
    backoff_seconds: float = Field(0, ge=0)


class ActionSpec(BaseModel):
    kind: Literal["agent", "tool"]
    name: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class NodeV2(BaseModel):
    id: str = Field(min_length=1)
    type: Literal["action", "route", "fork", "join", "interrupt"]
    action: ActionSpec | None = None
    expression: str | None = None
    routes: dict[str, str] = Field(default_factory=dict)
    branches: list[str] = Field(default_factory=list)
    join: str | None = None
    fork: str | None = None
    roles: list[str] = Field(default_factory=list)
    writes: list[str] = Field(default_factory=list)
    retry: RetrySpec = Field(default_factory=RetrySpec)

    @model_validator(mode="after")
    def validate_shape(self) -> NodeV2:
        if self.type == "action" and self.action is None:
            raise ValueError(f"action node '{self.id}' requires action")
        if self.type == "route" and not self.expression:
            raise ValueError(f"route node '{self.id}' requires expression")
        if self.type == "fork" and (not self.branches or not self.join):
            raise ValueError(f"fork node '{self.id}' requires branches and join")
        if self.type == "join" and not self.fork:
            raise ValueError(f"join node '{self.id}' requires fork")
        if self.type == "interrupt" and not self.roles:
            raise ValueError(f"interrupt node '{self.id}' requires roles")
        if self.type != "action" and self.writes:
            raise ValueError(f"only action nodes may declare writes ('{self.id}')")
        return self


class EdgeV2(BaseModel):
    from_: str = Field(alias="from", min_length=1)
    to: str = Field(min_length=1)
    max_iterations: int | None = Field(default=None, ge=1)

    model_config = {"populate_by_name": True}


class WorkflowV2(BaseModel):
    schema_version: Literal[2]
    name: str = Field(min_length=1, max_length=60)
    description: str = ""
    inputs: dict[str, ValueSpec] = Field(default_factory=dict)
    state: dict[str, ValueSpec] = Field(default_factory=dict)
    entrypoint: str
    nodes: list[NodeV2] = Field(min_length=1)
    edges: list[EdgeV2] = Field(default_factory=list)

    @property
    def version(self) -> str:
        return "2"

    @property
    def steps(self) -> list[NodeV2]:
        """Read-only presentation alias used by the legacy list response."""
        return self.nodes
