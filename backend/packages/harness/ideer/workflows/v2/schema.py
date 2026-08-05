"""Governed, declarative workflow v2 schema."""

from __future__ import annotations

import re
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


class FileAccessSpec(BaseModel):
    read: list[str] = Field(default_factory=list)
    write: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_roots(self) -> FileAccessSpec:
        for root in [*self.read, *self.write]:
            if "\\" in root or ".." in root.split("/"):
                raise ValueError(f"unsafe file_access root '{root}'")
            if root.startswith("/"):
                continue
            if not re.fullmatch(r"{{\s*(?:\$\.)?(?:inputs|state|outputs)(?:\.[A-Za-z_][A-Za-z0-9_]*)+\s*}}(?:/[^{}]*)?", root):
                raise ValueError(f"file_access root must be absolute or a templated absolute root: '{root}'")
        return self


class ActionSpec(BaseModel):
    kind: Literal["agent", "tool"]
    name: str = Field(min_length=1)
    file_access: FileAccessSpec | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_file_access(self) -> ActionSpec:
        if self.file_access is not None and self.kind != "agent":
            raise ValueError("file_access is only valid for agent actions")
        return self


class PreconditionSpec(BaseModel):
    """Runtime gate on a node's inputs; an unsatisfied precondition fails the node.

    A precondition asserts something about the content of a file the node reads
    (existence, non-emptiness, or a JSON value match).  Node failures caused by
    unsatisfied preconditions carry a specific reason instead of the generic
    "the agent claimed success but produced nothing".
    """

    file: str = Field(min_length=1)
    json_path: str | None = None
    some_equals: Any = None
    none_equals: Any = None
    non_empty: bool = False

    @model_validator(mode="after")
    def validate_shape(self) -> PreconditionSpec:
        if "\\" in self.file or ".." in self.file.split("/"):
            raise ValueError(f"unsafe precondition file '{self.file}'")
        if self.json_path is not None and self.some_equals is None and self.none_equals is None:
            raise ValueError("precondition 'json_path' requires some_equals or none_equals")
        if self.some_equals is not None and self.none_equals is not None:
            raise ValueError("precondition cannot set both some_equals and none_equals")
        if self.json_path is None and self.some_equals is None and self.none_equals is None and not self.non_empty:
            raise ValueError("precondition requires json_path, some_equals, none_equals or non_empty")
        return self


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
    preconditions: list[PreconditionSpec] = Field(default_factory=list)
    on_missing_artifact: Literal["fail", "pause"] = "fail"
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
        if self.type != "action" and self.preconditions:
            raise ValueError(f"only action nodes may declare preconditions ('{self.id}')")
        if self.type != "action" and self.on_missing_artifact != "fail":
            raise ValueError(f"on_missing_artifact is only valid on action nodes ('{self.id}')")
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
