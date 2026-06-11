"""YAML workflow parser — converts YAML files/strings to WorkflowDef."""

from __future__ import annotations

from pathlib import Path

import yaml

from .schema import InputParam, StepDef, StepType, WorkflowDef


def parse_workflow_yaml(path: Path) -> WorkflowDef:
    """Parse a YAML file into a WorkflowDef."""
    if path.stat().st_size > 100_000:  # 100 KB
        raise ValueError(f"Workflow YAML too large: {path.stat().st_size} bytes (max 100,000)")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _parse_workflow(raw)


def parse_workflow_string(content: str) -> WorkflowDef:
    """Parse a YAML string into a WorkflowDef."""
    raw = yaml.safe_load(content)
    return _parse_workflow(raw)


def _parse_workflow(raw: dict) -> WorkflowDef:
    """Convert raw dict to WorkflowDef."""
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid workflow YAML: expected a mapping, got {type(raw).__name__}")
    if "name" not in raw:
        raise ValueError("Invalid workflow YAML: missing required 'name' field")
    inputs: dict[str, InputParam] = {}
    for name, spec in raw.get("inputs", {}).items():
        if isinstance(spec, str):
            inputs[name] = InputParam(type=spec)
        elif isinstance(spec, dict):
            inputs[name] = InputParam(**spec)

    raw_steps = raw.get("steps")
    if raw_steps is None:
        raw_steps = []
    elif not isinstance(raw_steps, list):
        raise ValueError(f"Invalid workflow YAML: 'steps' must be a list, got {type(raw_steps).__name__}")
    steps = [_parse_step(s) for s in raw_steps]

    # Validate step ID uniqueness across all nesting levels
    all_ids = _collect_step_ids(steps)
    seen: set[str] = set()
    dupes: set[str] = set()
    for sid in all_ids:
        if sid in seen:
            dupes.add(sid)
        seen.add(sid)
    if dupes:
        raise ValueError(f"Duplicate step IDs (including nested): {dupes}")

    # Validate that string then/else references point to existing step IDs
    _validate_step_references(steps, seen)

    return WorkflowDef(
        name=raw["name"],
        description=raw.get("description", ""),
        version=raw.get("version", "1.0"),
        inputs=inputs,
        steps=steps,
        triggers=raw.get("triggers"),
    )


def _parse_step(raw: dict, depth: int = 0, max_depth: int = 20) -> StepDef:
    """Recursively parse a step definition."""
    if depth > max_depth:
        raise ValueError(f"Step nesting exceeds maximum depth of {max_depth}")
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid step definition: expected a mapping, got {type(raw).__name__}")
    if "id" not in raw:
        raise ValueError("Invalid step definition: missing required 'id' field")
    if "type" not in raw:
        raise ValueError("Invalid step definition: missing required 'type' field for step '{}'".format(raw.get("id", "<unknown>")))

    step_type = raw["type"]

    # Validate step type is a valid StepType enum member
    valid_types = {t.value for t in StepType}
    if step_type not in valid_types:
        raise ValueError(f"Unknown step type '{step_type}'. Valid types: {sorted(valid_types)}")

    if step_type == "agent" and "agent" not in raw:
        raise ValueError("Invalid step definition: 'agent' step requires 'agent' field (step '{}')".format(raw.get("id", "<unknown>")))
    if step_type == "tool" and "tool" not in raw:
        raise ValueError("Invalid step definition: 'tool' step requires 'tool' field (step '{}')".format(raw.get("id", "<unknown>")))
    if step_type == "condition":
        if "expression" not in raw:
            raise ValueError("Invalid step definition: 'condition' step requires 'expression' field (step '{}')".format(raw.get("id", "<unknown>")))
        # then/else are optional — branchless conditions are valid as expression evaluators
    if step_type == "parallel" and "steps" not in raw:
        raise ValueError("Invalid step definition: 'parallel' step requires 'steps' field (step '{}')".format(raw.get("id", "<unknown>")))
    if step_type == "loop" and "items" not in raw:
        raise ValueError("Invalid step definition: 'loop' step requires 'items' field (step '{}')".format(raw.get("id", "<unknown>")))

    # BUG-01: Validate that human_review steps are not nested inside loop/parallel.
    # execute_step() does not dispatch HUMAN_REVIEW (only the executor's _dispatch
    # does, because it passes the store object). Nested human_review would crash.
    if depth > 0 and step_type == "human_review":
        raise ValueError("Invalid step definition: 'human_review' cannot be nested inside 'loop' or 'parallel' blocks (step '{}'). Place human_review at the top level or use a condition wrapper.".format(raw.get("id", "<unknown>")))

    raw_steps = raw.get("steps")
    if raw_steps is not None and not isinstance(raw_steps, list):
        raise ValueError("Invalid step definition: 'steps' must be a list for step '{}', got {}".format(raw.get("id", "<unknown>"), type(raw_steps).__name__))
    steps = [_parse_step(s, depth + 1, max_depth) for s in raw_steps] if raw_steps else None

    then = raw.get("then")
    if isinstance(then, dict):
        then = _parse_step(then, depth + 1, max_depth)

    else_ = raw.get("else")
    if isinstance(else_, dict):
        else_ = _parse_step(else_, depth + 1, max_depth)

    return StepDef(
        id=raw["id"],
        type=raw["type"],
        agent=raw.get("agent"),
        prompt=raw.get("prompt"),
        tool=raw.get("tool"),
        params=raw.get("params"),
        message=raw.get("message"),
        input_schema=raw.get("input_schema"),
        approvers=raw.get("approvers"),
        expression=raw.get("expression"),
        then=then,
        else_=else_,
        steps=steps,
        items=raw.get("items"),
        condition=raw.get("condition"),
        timeout=raw.get("timeout"),
        retry=raw.get("retry"),
        on_error=raw.get("on_error"),
        max_iterations=raw.get("max_iterations") if raw.get("max_iterations") is not None else 1000,
        fail_fast=raw.get("fail_fast", False),
    )


def _collect_step_ids(steps: list[StepDef] | None) -> list[str]:
    """Recursively collect all step IDs from a step list, including nested steps.

    Traverses ``steps``, ``then``, and ``else`` fields to find all IDs
    across parallel, loop, and condition nesting levels.
    """
    if not steps:
        return []
    ids: list[str] = []
    for step in steps:
        ids.append(step.id)
        ids.extend(_collect_step_ids(step.steps))
        if isinstance(step.then, StepDef):
            ids.extend(_collect_step_ids([step.then]))
        if isinstance(step.else_, StepDef):
            ids.extend(_collect_step_ids([step.else_]))
    return ids


def _validate_step_references(steps: list[StepDef], all_ids: set[str]) -> None:
    """Validate that string then/else references point to existing step IDs."""
    for step in steps:
        if isinstance(step.then, str) and step.then not in all_ids:
            raise ValueError(f"Step '{step.id}': 'then' references unknown step '{step.then}'")
        if isinstance(step.else_, str) and step.else_ not in all_ids:
            raise ValueError(f"Step '{step.id}': 'else' references unknown step '{step.else_}'")
        # Recurse into nested steps
        if step.steps:
            _validate_step_references(step.steps, all_ids)
        if isinstance(step.then, StepDef):
            _validate_step_references([step.then], all_ids)
        if isinstance(step.else_, StepDef):
            _validate_step_references([step.else_], all_ids)
