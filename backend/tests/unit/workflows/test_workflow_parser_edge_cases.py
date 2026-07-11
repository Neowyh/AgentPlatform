"""Additional tests for packages.harness.ideer.workflows.parser — coverage gaps."""

from __future__ import annotations

import pytest

from packages.harness.ideer.workflows.parser import (
    _collect_step_ids,
    _parse_step,
    _validate_step_references,
    parse_workflow_string,
)
from packages.harness.ideer.workflows.schema import StepDef, StepType

# ---------------------------------------------------------------------------
# parse_workflow_string edge cases
# ---------------------------------------------------------------------------


class TestParseWorkflowStringEdgeCases:
    def test_non_dict_yaml_raises(self):
        with pytest.raises(ValueError, match="expected a mapping"):
            parse_workflow_string("- item1\n- item2")

    def test_missing_name_raises(self):
        with pytest.raises(ValueError, match="missing required 'name' field"):
            parse_workflow_string("steps:\n  - id: s1\n    type: agent\n")

    def test_steps_not_list_raises(self):
        with pytest.raises(ValueError, match="'steps' must be a list"):
            parse_workflow_string("name: bad\nsteps: not_a_list\n")

    def test_no_steps_field(self):
        wf = parse_workflow_string("name: no_steps\n")
        assert wf.steps == []

    def test_description_and_version(self):
        wf = parse_workflow_string('name: wf\nversion: "2.0"\ndescription: test desc\n')
        assert wf.version == "2.0"
        assert wf.description == "test desc"

    def test_triggers_parsed(self):
        yaml_content = "name: wf\ntriggers:\n  - type: schedule\n    cron: '0 * * * *'\n"
        wf = parse_workflow_string(yaml_content)
        assert wf.triggers == [{"type": "schedule", "cron": "0 * * * *"}]

    def test_inputs_shorthand_and_dict_mix(self):
        yaml_content = """
name: mixed
inputs:
  q: string
  c:
    type: integer
    required: true
    description: count
steps:
  - id: s1
    type: agent
    agent: a1
"""
        wf = parse_workflow_string(yaml_content)
        assert wf.inputs["q"].type == "string"
        assert wf.inputs["c"].required is True
        assert wf.inputs["c"].description == "count"

    def test_condition_no_then_no_else(self):
        """Branchless condition (expression evaluator) should parse fine."""
        yaml_content = """
name: branchless
steps:
  - id: check
    type: condition
    expression: "x > 0"
"""
        wf = parse_workflow_string(yaml_content)
        cond = wf.steps[0]
        assert cond.type == StepType.CONDITION
        assert cond.then is None
        assert cond.else_ is None

    def test_condition_string_then_else(self):
        """then/else as strings are kept as strings for reference validation."""
        yaml_content = """
name: ref_cond
steps:
  - id: s1
    type: agent
    agent: a1
  - id: check
    type: condition
    expression: "x > 0"
    then: s1
"""
        wf = parse_workflow_string(yaml_content)
        cond = wf.steps[1]
        assert cond.then == "s1"

    def test_condition_invalid_string_then_reference(self):
        """then referencing a nonexistent step ID should raise."""
        yaml_content = """
name: bad_ref
steps:
  - id: check
    type: condition
    expression: "x > 0"
    then: nonexistent_step
"""
        with pytest.raises(ValueError, match="references unknown step"):
            parse_workflow_string(yaml_content)

    def test_condition_invalid_string_else_reference(self):
        """else referencing a nonexistent step ID should raise."""
        yaml_content = """
name: bad_ref_else
steps:
  - id: check
    type: condition
    expression: "x > 0"
    else: nonexistent_step
"""
        with pytest.raises(ValueError, match="references unknown step"):
            parse_workflow_string(yaml_content)

    def test_duplicate_step_ids_raises(self):
        yaml_content = """
name: dupes
steps:
  - id: s1
    type: agent
    agent: a1
  - id: s1
    type: agent
    agent: a2
"""
        with pytest.raises(ValueError, match="Duplicate step IDs"):
            parse_workflow_string(yaml_content)

    def test_duplicate_nested_step_ids_raises(self):
        yaml_content = """
name: nested_dupes
steps:
  - id: s1
    type: parallel
    steps:
      - id: sub1
        type: agent
        agent: a1
  - id: sub1
    type: agent
    agent: a2
"""
        with pytest.raises(ValueError, match="Duplicate step IDs"):
            parse_workflow_string(yaml_content)

    def test_loop_step_requires_items(self):
        yaml_content = """
name: loop_no_items
steps:
  - id: l1
    type: loop
"""
        with pytest.raises(ValueError, match="requires 'items' field"):
            parse_workflow_string(yaml_content)

    def test_parallel_step_requires_steps(self):
        yaml_content = """
name: parallel_no_steps
steps:
  - id: p1
    type: parallel
"""
        with pytest.raises(ValueError, match="requires 'steps' field"):
            parse_workflow_string(yaml_content)


# ---------------------------------------------------------------------------
# _parse_step edge cases
# ---------------------------------------------------------------------------


class TestParseStepEdgeCases:
    def test_missing_type_raises(self):
        with pytest.raises(ValueError, match="missing required 'type' field"):
            _parse_step({"id": "s1"})

    def test_missing_id_raises(self):
        with pytest.raises(ValueError, match="missing required 'id' field"):
            _parse_step({"type": "agent"})

    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="expected a mapping"):
            _parse_step("not_a_dict")

    def test_invalid_step_type_raises(self):
        with pytest.raises(ValueError, match="Unknown step type"):
            _parse_step({"id": "s1", "type": "invalid_type"})

    def test_agent_step_requires_agent_field(self):
        with pytest.raises(ValueError, match="requires 'agent' field"):
            _parse_step({"id": "s1", "type": "agent"})

    def test_tool_step_requires_tool_field(self):
        with pytest.raises(ValueError, match="requires 'tool' field"):
            _parse_step({"id": "s1", "type": "tool"})

    def test_condition_step_requires_expression(self):
        with pytest.raises(ValueError, match="requires 'expression' field"):
            _parse_step({"id": "s1", "type": "condition"})

    def test_nesting_depth_exceeded(self):
        deep = {"id": "s1", "type": "agent", "agent": "a"}
        for i in range(21):
            deep = {"id": f"level_{i}", "type": "loop", "items": "x", "steps": [deep]}
        with pytest.raises(ValueError, match="exceeds maximum depth"):
            _parse_step(deep)

    def test_human_review_nested_raises(self):
        yaml_content = """
name: nested_hr
steps:
  - id: loop1
    type: loop
    items: x
    steps:
      - id: hr1
        type: human_review
        message: approve?
"""
        with pytest.raises(ValueError, match="human_review.*cannot be nested"):
            parse_workflow_string(yaml_content)

    def test_human_review_in_parallel_raises(self):
        yaml_content = """
name: nested_hr_parallel
steps:
  - id: p1
    type: parallel
    steps:
      - id: hr1
        type: human_review
        message: approve?
"""
        with pytest.raises(ValueError, match="human_review.*cannot be nested"):
            parse_workflow_string(yaml_content)

    def test_steps_field_not_list_raises(self):
        yaml_content = """
name: bad_steps
steps:
  - id: p1
    type: parallel
    steps: not_a_list
"""
        with pytest.raises(ValueError, match="'steps' must be a list"):
            parse_workflow_string(yaml_content)

    def test_agent_step_optional_fields(self):
        step = _parse_step(
            {
                "id": "s1",
                "type": "agent",
                "agent": "a1",
                "prompt": "do something",
                "params": {"key": "val"},
                "timeout": 30,
                "retry": {"max": 3},
                "on_error": "skip",
                "max_iterations": 500,
                "fail_fast": True,
            }
        )
        assert step.prompt == "do something"
        assert step.params == {"key": "val"}
        assert step.timeout == 30
        assert step.retry.max == 3
        assert step.on_error == "skip"
        assert step.max_iterations == 500
        assert step.fail_fast is True

    def test_max_iterations_none_default(self):
        """max_iterations=None should default to 1000."""
        step = _parse_step(
            {
                "id": "s1",
                "type": "loop",
                "items": "x",
                "max_iterations": None,
            }
        )
        assert step.max_iterations == 1000

    def test_loop_step_optional_fields(self):
        step = _parse_step(
            {
                "id": "l1",
                "type": "loop",
                "items": "x",
                "condition": "len(x) > 0",
                "max_iterations": 50,
                "fail_fast": True,
            }
        )
        assert step.items == "x"
        assert step.condition == "len(x) > 0"
        assert step.max_iterations == 50
        assert step.fail_fast is True

    def test_human_review_step(self):
        step = _parse_step(
            {
                "id": "hr1",
                "type": "human_review",
                "message": "Please review",
                "approvers": ["alice"],
                "input_schema": {"type": "object"},
            }
        )
        assert step.type == StepType.HUMAN_REVIEW
        assert step.message == "Please review"
        assert step.approvers == ["alice"]
        assert step.input_schema == {"type": "object"}


# ---------------------------------------------------------------------------
# _collect_step_ids
# ---------------------------------------------------------------------------


class TestCollectStepIds:
    def test_empty_list(self):
        assert _collect_step_ids([]) == []

    def test_none(self):
        assert _collect_step_ids(None) == []

    def test_nested_steps(self):
        inner = StepDef(id="inner", type=StepType.AGENT, agent="a")
        outer = StepDef(id="outer", type=StepType.PARALLEL, steps=[inner])
        assert _collect_step_ids([outer]) == ["outer", "inner"]

    def test_then_else_steps(self):
        then_s = StepDef(id="then_s", type=StepType.AGENT, agent="a")
        else_s = StepDef(id="else_s", type=StepType.AGENT, agent="b")
        cond = StepDef(id="cond", type=StepType.CONDITION, expression="x", then=then_s, else_=else_s)
        ids = _collect_step_ids([cond])
        assert set(ids) == {"cond", "then_s", "else_s"}


# ---------------------------------------------------------------------------
# _validate_step_references
# ---------------------------------------------------------------------------


class TestValidateStepReferences:
    def test_valid_reference(self):
        StepDef(id="s1", type=StepType.AGENT, agent="a")
        s2 = StepDef(id="s2", type=StepType.CONDITION, expression="x", then="s1")
        _validate_step_references([s2], {"s1", "s2"})

    def test_invalid_then_reference(self):
        s2 = StepDef(id="s2", type=StepType.CONDITION, expression="x", then="missing")
        with pytest.raises(ValueError, match="references unknown step 'missing'"):
            _validate_step_references([s2], {"s2"})

    def test_invalid_else_reference(self):
        s2 = StepDef(id="s2", type=StepType.CONDITION, expression="x", else_="missing")
        with pytest.raises(ValueError, match="references unknown step 'missing'"):
            _validate_step_references([s2], {"s2"})

    def test_nested_references(self):
        inner_then = StepDef(id="inner_then", type=StepType.AGENT, agent="a")
        inner = StepDef(id="inner", type=StepType.CONDITION, expression="y", then=inner_then)
        outer = StepDef(id="outer", type=StepType.PARALLEL, steps=[inner])
        _validate_step_references([outer], {"outer", "inner", "inner_then"})

    def test_nested_invalid_reference(self):
        inner = StepDef(id="inner", type=StepType.CONDITION, expression="y", then="ghost")
        outer = StepDef(id="outer", type=StepType.PARALLEL, steps=[inner])
        with pytest.raises(ValueError, match="references unknown step 'ghost'"):
            _validate_step_references([outer], {"outer", "inner"})

    def test_string_then_in_nested(self):
        """String references in nested steps are also validated."""
        inner = StepDef(id="inner", type=StepType.CONDITION, expression="y", else_="nonexistent")
        outer = StepDef(id="outer", type=StepType.LOOP, items="x", steps=[inner])
        with pytest.raises(ValueError, match="references unknown step 'nonexistent'"):
            _validate_step_references([outer], {"outer", "inner"})

    def test_valid_nested_references(self):
        inner_then = StepDef(id="ok_then", type=StepType.AGENT, agent="a")
        inner = StepDef(id="inner", type=StepType.CONDITION, expression="y", then=inner_then)
        outer = StepDef(id="outer", type=StepType.LOOP, items="x", steps=[inner])
        _validate_step_references([outer], {"outer", "inner", "ok_then"})


# ---------------------------------------------------------------------------
# parse_workflow_yaml (file-based)
# ---------------------------------------------------------------------------


class TestParseWorkflowYaml:
    def test_parse_from_file(self, tmp_path):
        wf_file = tmp_path / "workflow.yaml"
        wf_file.write_text("name: from_file\nsteps:\n  - id: s1\n    type: agent\n    agent: a1\n")
        from packages.harness.ideer.workflows.parser import parse_workflow_yaml

        wf = parse_workflow_yaml(wf_file)
        assert wf.name == "from_file"

    def test_file_too_large(self, tmp_path):
        wf_file = tmp_path / "huge.yaml"
        wf_file.write_text("name: huge\n" + " " * 100_001)
        from packages.harness.ideer.workflows.parser import parse_workflow_yaml

        with pytest.raises(ValueError, match="too large"):
            parse_workflow_yaml(wf_file)
