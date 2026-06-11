"""Tests for workflow schema models and YAML parser."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.harness.ideer.workflows.parser import parse_workflow_string
from packages.harness.ideer.workflows.schema import (
    InputParam,
    RetryPolicy,
    StepDef,
    StepType,
    WorkflowDef,
)

# ── StepType enum ──────────────────────────────────────────────────


def test_step_type_enum_values():
    assert StepType.AGENT == "agent"
    assert StepType.TOOL == "tool"
    assert StepType.HUMAN_REVIEW == "human_review"
    assert StepType.CONDITION == "condition"
    assert StepType.PARALLEL == "parallel"
    assert StepType.LOOP == "loop"
    assert StepType.RETRY == "retry"


def test_step_type_has_exactly_seven_members():
    assert len(StepType) == 7


# ── WorkflowDef ────────────────────────────────────────────────────


def test_workflow_def_defaults():
    wf = WorkflowDef(name="my-workflow")
    assert wf.name == "my-workflow"
    assert wf.description == ""
    assert wf.version == "1.0"
    assert wf.inputs == {}
    assert wf.steps == []
    assert wf.triggers is None


def test_workflow_def_full_data():
    step = StepDef(id="s1", type=StepType.AGENT, agent="researcher")
    param = InputParam(type="string", required=True, description="query")
    wf = WorkflowDef(
        name="full",
        description="A full workflow",
        version="2.0",
        inputs={"query": param},
        steps=[step],
        triggers=[{"type": "schedule", "cron": "0 * * * *"}],
    )
    assert wf.name == "full"
    assert wf.description == "A full workflow"
    assert wf.version == "2.0"
    assert wf.inputs["query"].required is True
    assert len(wf.steps) == 1
    assert wf.triggers[0]["type"] == "schedule"


def test_workflow_def_requires_name():
    with pytest.raises(ValidationError):
        WorkflowDef()


# ── StepDef ────────────────────────────────────────────────────────


def test_step_def_minimal():
    s = StepDef(id="s1", type=StepType.TOOL)
    assert s.id == "s1"
    assert s.type == StepType.TOOL
    assert s.agent is None
    assert s.prompt is None
    assert s.tool is None
    assert s.params is None
    assert s.message is None
    assert s.input_schema is None
    assert s.approvers is None
    assert s.expression is None
    assert s.then is None
    assert s.else_ is None
    assert s.steps is None
    assert s.items is None
    assert s.condition is None
    assert s.timeout is None
    assert s.retry is None
    assert s.on_error is None


def test_step_def_all_fields():
    retry = RetryPolicy(max=5, backoff=10.0, on_errors=["TimeoutError"])
    s = StepDef(
        id="s-full",
        type=StepType.AGENT,
        agent="writer",
        prompt="Write something",
        tool="search",
        params={"q": "test"},
        message="Please review",
        input_schema={"type": "object"},
        approvers=["alice", "bob"],
        expression="len(result) > 0",
        then="next-step",
        else_="fallback-step",
        steps=[],
        items="items_list",
        condition="x > 0",
        timeout=120,
        retry=retry,
        on_error="skip",
    )
    assert s.id == "s-full"
    assert s.type == StepType.AGENT
    assert s.agent == "writer"
    assert s.prompt == "Write something"
    assert s.tool == "search"
    assert s.params == {"q": "test"}
    assert s.message == "Please review"
    assert s.input_schema == {"type": "object"}
    assert s.approvers == ["alice", "bob"]
    assert s.expression == "len(result) > 0"
    assert s.then == "next-step"
    assert s.else_ == "fallback-step"
    assert s.steps == []
    assert s.items == "items_list"
    assert s.condition == "x > 0"
    assert s.timeout == 120
    assert s.retry.max == 5
    assert s.retry.backoff == 10.0
    assert s.retry.on_errors == ["TimeoutError"]
    assert s.on_error == "skip"


def test_step_def_else_alias_populate_by_name():
    """The 'else' alias maps to else_ when using populate_by_name."""
    s = StepDef(id="s1", type=StepType.CONDITION, **{"else": "fb"})
    assert s.else_ == "fb"


def test_step_def_requires_id():
    with pytest.raises(ValidationError):
        StepDef(type=StepType.TOOL)


def test_step_def_requires_type():
    with pytest.raises(ValidationError):
        StepDef(id="s1")


# ── RetryPolicy ────────────────────────────────────────────────────


def test_retry_policy_defaults():
    rp = RetryPolicy()
    assert rp.max == 3
    assert rp.backoff == 5.0
    assert rp.on_errors == ["*"]


def test_retry_policy_custom():
    rp = RetryPolicy(max=10, backoff=2.5, on_errors=["IOError", "TimeoutError"])
    assert rp.max == 10
    assert rp.backoff == 2.5
    assert rp.on_errors == ["IOError", "TimeoutError"]


# ── InputParam ─────────────────────────────────────────────────────


def test_input_param_defaults():
    ip = InputParam()
    assert ip.type == "string"
    assert ip.required is False
    assert ip.default is None
    assert ip.description == ""


def test_input_param_custom():
    ip = InputParam(
        type="integer",
        required=True,
        default=42,
        description="max retries",
    )
    assert ip.type == "integer"
    assert ip.required is True
    assert ip.default == 42
    assert ip.description == "max retries"


# ── Parser: parse_workflow_string ──────────────────────────────────


def test_parse_workflow_string_basic():
    yaml_content = """
name: simple
steps:
  - id: s1
    type: agent
    agent: researcher
    prompt: "find info"
"""
    wf = parse_workflow_string(yaml_content)
    assert wf.name == "simple"
    assert wf.version == "1.0"
    assert len(wf.steps) == 1
    assert wf.steps[0].id == "s1"
    assert wf.steps[0].type == StepType.AGENT
    assert wf.steps[0].agent == "researcher"
    assert wf.steps[0].prompt == "find info"


def test_parse_workflow_string_inputs_shorthand():
    """Shorthand 'string' becomes InputParam(type='string')."""
    yaml_content = """
name: with-inputs
inputs:
  query: string
  count:
    type: integer
    required: true
steps:
  - id: s1
    type: tool
    tool: my_tool
"""
    wf = parse_workflow_string(yaml_content)
    assert wf.inputs["query"].type == "string"
    assert wf.inputs["query"].required is False
    assert wf.inputs["count"].type == "integer"
    assert wf.inputs["count"].required is True


def test_parse_workflow_string_nested_parallel_steps():
    yaml_content = """
name: parallel
steps:
  - id: p1
    type: parallel
    steps:
      - id: sub1
        type: agent
        agent: a1
      - id: sub2
        type: agent
        agent: a2
"""
    wf = parse_workflow_string(yaml_content)
    assert len(wf.steps) == 1
    parallel = wf.steps[0]
    assert parallel.type == StepType.PARALLEL
    assert parallel.steps is not None
    assert len(parallel.steps) == 2
    assert parallel.steps[0].id == "sub1"
    assert parallel.steps[0].agent == "a1"
    assert parallel.steps[1].id == "sub2"
    assert parallel.steps[1].agent == "a2"


def test_parse_workflow_string_condition_then_else_dict():
    """then/else as dicts are recursively parsed into StepDef."""
    yaml_content = """
name: conditional
steps:
  - id: check
    type: condition
    expression: "x > 0"
    then:
      id: positive
      type: agent
      agent: responder
    else:
      id: negative
      type: tool
      tool: fallback
"""
    wf = parse_workflow_string(yaml_content)
    cond = wf.steps[0]
    assert cond.type == StepType.CONDITION
    assert isinstance(cond.then, StepDef)
    assert cond.then.id == "positive"
    assert cond.then.agent == "responder"
    assert isinstance(cond.else_, StepDef)
    assert cond.else_.id == "negative"
    assert cond.else_.tool == "fallback"


def test_parse_workflow_string_missing_name_raises():
    yaml_content = """
steps:
  - id: s1
    type: agent
"""
    with pytest.raises((KeyError, ValueError)):
        parse_workflow_string(yaml_content)


def test_parse_workflow_string_missing_step_id_raises():
    yaml_content = """
name: bad
steps:
  - type: agent
"""
    with pytest.raises(ValueError, match="missing required 'id' field"):
        parse_workflow_string(yaml_content)


def test_parse_workflow_string_empty_steps():
    yaml_content = """
name: empty
steps: []
"""
    wf = parse_workflow_string(yaml_content)
    assert wf.name == "empty"
    assert wf.steps == []
