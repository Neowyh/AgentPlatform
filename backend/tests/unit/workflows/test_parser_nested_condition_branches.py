"""Workflow parser support for nested condition branches."""

from __future__ import annotations

import pytest

from packages.harness.ideer.workflows.parser import (
    _validate_step_references,
    parse_workflow_string,
)
from packages.harness.ideer.workflows.schema import StepDef, StepType

# ---------------------------------------------------------------------------
# then/else dictionaries are parsed into nested StepDef instances
# ---------------------------------------------------------------------------


class TestConditionThenElseAsDict:
    def test_condition_with_dict_then(self):
        """Condition step with then as a dict should be recursively parsed into StepDef."""
        yaml_content = """
name: dict_then
steps:
  - id: check
    type: condition
    expression: "x > 0"
    then:
      id: do_thing
      type: agent
      agent: my_agent
"""
        wf = parse_workflow_string(yaml_content)
        cond = wf.steps[0]
        assert isinstance(cond.then, StepDef)
        assert cond.then.id == "do_thing"
        assert cond.then.type == StepType.AGENT
        assert cond.then.agent == "my_agent"

    def test_condition_with_dict_else(self):
        """Condition step with else_ as a dict should be recursively parsed into StepDef."""
        yaml_content = """
name: dict_else
steps:
  - id: check
    type: condition
    expression: "x > 0"
    else:
      id: fallback
      type: tool
      tool: my_tool
"""
        wf = parse_workflow_string(yaml_content)
        cond = wf.steps[0]
        assert isinstance(cond.else_, StepDef)
        assert cond.else_.id == "fallback"
        assert cond.else_.type == StepType.TOOL
        assert cond.else_.tool == "my_tool"

    def test_condition_with_both_dict_then_else(self):
        """Condition step with both then and else as dicts."""
        yaml_content = """
name: both_dict
steps:
  - id: check
    type: condition
    expression: "x > 0"
    then:
      id: positive
      type: agent
      agent: a1
    else:
      id: negative
      type: agent
      agent: a2
"""
        wf = parse_workflow_string(yaml_content)
        cond = wf.steps[0]
        assert isinstance(cond.then, StepDef)
        assert isinstance(cond.else_, StepDef)
        assert cond.then.id == "positive"
        assert cond.else_.id == "negative"


# ---------------------------------------------------------------------------
# Step reference validation recurses into nested branches
# ---------------------------------------------------------------------------


class TestValidateStepReferencesElseStepDef:
    def test_valid_else_stepdef_reference(self):
        """Valid string reference inside nested else_ StepDef should pass."""
        inner_then = StepDef(id="ok_then", type=StepType.AGENT, agent="a")
        inner_else = StepDef(id="ok_else", type=StepType.CONDITION, expression="y", then=inner_then)
        outer = StepDef(id="outer", type=StepType.CONDITION, expression="x", else_=inner_else)
        _validate_step_references([outer], {"outer", "ok_else", "ok_then"})

    def test_invalid_reference_in_nested_else_stepdef(self):
        """Invalid string reference inside nested else_ StepDef should raise."""
        inner_else = StepDef(id="inner_else", type=StepType.CONDITION, expression="y", then="ghost")
        outer = StepDef(id="outer", type=StepType.CONDITION, expression="x", else_=inner_else)
        with pytest.raises(ValueError, match="references unknown step 'ghost'"):
            _validate_step_references([outer], {"outer", "inner_else"})

    def test_valid_then_stepdef_reference(self):
        """Valid string reference inside nested then StepDef should pass."""
        inner_then = StepDef(id="inner_then", type=StepType.CONDITION, expression="y", else_="ok_target")
        outer = StepDef(id="outer", type=StepType.CONDITION, expression="x", then=inner_then)
        _validate_step_references([outer], {"outer", "inner_then", "ok_target"})

    def test_invalid_reference_in_nested_then_stepdef(self):
        """Invalid string reference inside nested then StepDef should raise."""
        inner_then = StepDef(id="inner_then", type=StepType.CONDITION, expression="y", else_="missing")
        outer = StepDef(id="outer", type=StepType.CONDITION, expression="x", then=inner_then)
        with pytest.raises(ValueError, match="references unknown step 'missing'"):
            _validate_step_references([outer], {"outer", "inner_then"})


# ---------------------------------------------------------------------------
# Full workflow with dict then/else
# ---------------------------------------------------------------------------


class TestFullWorkflowWithDictBranches:
    def test_complex_workflow_with_dict_branches(self):
        """Full workflow with dict then/else and nested steps."""
        yaml_content = """
name: complex
steps:
  - id: evaluate
    type: condition
    expression: "score > 80"
    then:
      id: high_score
      type: agent
      agent: praise_agent
      prompt: "Great job!"
    else:
      id: low_score
      type: tool
      tool: send_reminder
      params:
        message: "Try harder"
"""
        wf = parse_workflow_string(yaml_content)
        assert len(wf.steps) == 1
        cond = wf.steps[0]
        assert cond.id == "evaluate"
        assert isinstance(cond.then, StepDef)
        assert isinstance(cond.else_, StepDef)
        assert cond.then.agent == "praise_agent"
        assert cond.else_.tool == "send_reminder"
