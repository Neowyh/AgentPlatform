"""YAML workflow parser — converts YAML files/strings to WorkflowDef."""

from __future__ import annotations

from pathlib import Path

import yaml

from .schema import InputParam, StepDef, WorkflowDef


def parse_workflow_yaml(path: Path) -> WorkflowDef:
    """Parse a YAML file into a WorkflowDef."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _parse_workflow(raw)


def parse_workflow_string(content: str) -> WorkflowDef:
    """Parse a YAML string into a WorkflowDef."""
    raw = yaml.safe_load(content)
    return _parse_workflow(raw)


def _parse_workflow(raw: dict) -> WorkflowDef:
    """Convert raw dict to WorkflowDef."""
    inputs: dict[str, InputParam] = {}
    for name, spec in raw.get("inputs", {}).items():
        if isinstance(spec, str):
            inputs[name] = InputParam(type=spec)
        elif isinstance(spec, dict):
            inputs[name] = InputParam(**spec)

    steps = [_parse_step(s) for s in raw.get("steps", [])]

    return WorkflowDef(
        name=raw["name"],
        description=raw.get("description", ""),
        version=raw.get("version", "1.0"),
        inputs=inputs,
        steps=steps,
        triggers=raw.get("triggers"),
    )


def _parse_step(raw: dict) -> StepDef:
    """Recursively parse a step definition."""
    steps = [_parse_step(s) for s in raw["steps"]] if "steps" in raw else None

    then = raw.get("then")
    if isinstance(then, dict):
        then = _parse_step(then)

    else_ = raw.get("else")
    if isinstance(else_, dict):
        else_ = _parse_step(else_)

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
    )
