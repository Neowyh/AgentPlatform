"""Parsing and static validation for workflow YAML v2."""

from __future__ import annotations

import ast
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import yaml

from .file_roots import path_within_root, workflow_state_root
from .schema import WorkflowV2

_PATH = re.compile(r"\$\.(?:inputs|state|outputs)(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
_TEMPLATE = re.compile(r"{{\s*((?:\$\.)?(?:inputs|state|state_files|outputs)(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\s*}}")


def parse_workflow_v2(content: str) -> WorkflowV2:
    raw = yaml.safe_load(content)
    if not isinstance(raw, dict):
        raise ValueError("Invalid workflow YAML: expected a mapping")
    if raw.get("schema_version") != 2:
        raise ValueError("schema_version must be 2")
    raw_nodes = raw.get("nodes")
    if isinstance(raw_nodes, list):
        seen: set[str] = set()
        for raw_node in raw_nodes:
            if isinstance(raw_node, dict) and raw_node.get("id") in seen:
                raise ValueError(f"duplicate node id '{raw_node['id']}'")
            if isinstance(raw_node, dict) and isinstance(raw_node.get("id"), str):
                seen.add(raw_node["id"])
    for field in ("inputs", "state"):
        values = raw.get(field, {})
        if isinstance(values, dict):
            raw[field] = {key: {"type": value} if isinstance(value, str) else value for key, value in values.items()}
    try:
        workflow = WorkflowV2.model_validate(raw)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    _validate_graph(workflow)
    return workflow


def parse_workflow_v2_file(path: Path) -> WorkflowV2:
    if path.stat().st_size > 100_000:
        raise ValueError("Workflow YAML exceeds 100,000 bytes")
    return parse_workflow_v2(path.read_text(encoding="utf-8"))


def _validate_graph(workflow: WorkflowV2) -> None:
    nodes = {node.id: node for node in workflow.nodes}
    if workflow.entrypoint not in nodes:
        raise ValueError(f"entrypoint '{workflow.entrypoint}' does not name a node")

    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in workflow.edges:
        if edge.from_ not in nodes:
            raise ValueError(f"edge source '{edge.from_}' does not name a node")
        if edge.to not in nodes:
            raise ValueError(f"edge target '{edge.to}' does not name a node")
        outgoing[edge.from_].append(edge.to)

    reachable: set[str] = set()
    pending = deque([workflow.entrypoint])
    while pending:
        current = pending.popleft()
        if current in reachable:
            continue
        reachable.add(current)
        pending.extend(outgoing[current])
    missing = sorted(set(nodes) - reachable)
    if missing:
        raise ValueError(f"unreachable node '{missing[0]}'")

    _validate_cycles(workflow, outgoing)
    _validate_routes(workflow, nodes)
    _validate_templates(workflow)
    _validate_forks(workflow, nodes, outgoing)
    _validate_writes(workflow)
    _validate_preconditions(workflow)
    _validate_write_schemas(workflow)


def _validate_cycles(workflow: WorkflowV2, outgoing: dict[str, list[str]]) -> None:
    index = 0
    stack: list[str] = []
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    on_stack: set[str] = set()
    components: list[set[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for child in outgoing[node]:
            if child not in indices:
                visit(child)
                lowlinks[node] = min(lowlinks[node], lowlinks[child])
            elif child in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[child])
        if lowlinks[node] == indices[node]:
            component: set[str] = set()
            while True:
                child = stack.pop()
                on_stack.remove(child)
                component.add(child)
                if child == node:
                    break
            if len(component) > 1 or node in outgoing[node]:
                components.append(component)

    for node in outgoing:
        if node not in indices:
            visit(node)
    for component in components:
        for edge in workflow.edges:
            if edge.from_ in component and edge.to in component:
                if edge.max_iterations is None:
                    raise ValueError(f"cycle edge {edge.from_} -> {edge.to} must declare max_iterations")
                break


def _validate_routes(workflow: WorkflowV2, nodes: dict[str, Any]) -> None:
    for node in workflow.nodes:
        if node.type != "route":
            continue
        if sum(edge.from_ == node.id for edge in workflow.edges) < 2:
            raise ValueError(f"route '{node.id}' requires at least two outgoing edges")
        _validate_expression(node.expression or "", workflow)
        for target in node.routes.values():
            if target not in nodes:
                raise ValueError(f"route '{node.id}' targets unknown node '{target}'")


def _validate_expression(expression: str, workflow: WorkflowV2) -> None:
    for path in _PATH.findall(expression):
        if any(part.startswith("__") for part in path.split(".")[-1:]):
            raise ValueError("route expression contains unsupported syntax")
        _validate_path(path, workflow, "expression")
    scrubbed = _PATH.sub("value", expression)
    try:
        tree = ast.parse(scrubbed, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"invalid route expression: {expression}") from exc
    allowed = (ast.Expression, ast.BoolOp, ast.Compare, ast.Name, ast.Load, ast.Constant, ast.And, ast.Or, ast.Not, ast.UnaryOp, ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq)
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        raise ValueError("route expression contains unsupported syntax")


def _validate_templates(workflow: WorkflowV2) -> None:
    declared = {f"$.inputs.{key}" for key in workflow.inputs} | {f"$.state.{key}" for key in workflow.state} | {f"$.state_files.{key}" for key in workflow.state}
    output_nodes = {node.id for node in workflow.nodes}
    declared |= {f"$.outputs.{key}" for key in output_nodes}
    for node in workflow.nodes:
        if node.action:
            templated_values: list[Any] = [node.action.params]
            if node.action.file_access is not None:
                templated_values.append(node.action.file_access.model_dump())
            for value in _walk_values(templated_values):
                if isinstance(value, str):
                    if ("{{" in value or "}}" in value) and (value.count("{{") != value.count("}}") or not _TEMPLATE.search(value)):
                        raise ValueError(f"invalid template syntax in action node '{node.id}'")
                    for path in _TEMPLATE.findall(value):
                        if not path.startswith("$."):
                            path = "$." + path
                        if path not in declared and not any(path.startswith(f"$.outputs.{key}.") for key in output_nodes):
                            raise ValueError(f"template references undeclared path '{path}'")


def _walk_values(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_values(item)
    else:
        yield value


def _validate_writes(workflow: WorkflowV2) -> None:
    declared = set(workflow.state)
    for node in workflow.nodes:
        for path in node.writes:
            parts = path.split(".")
            if len(parts) != 3 or parts[:2] != ["$", "state"] or parts[2] not in declared:
                raise ValueError(f"action node '{node.id}' writes undeclared state path '{path}'")


def _validate_preconditions(workflow: WorkflowV2) -> None:
    """Precondition files must be readable by their node.

    Static (non-templated) precondition files must sit under one of the node's
    static read roots or the shared state root; templated files are only
    resolvable at runtime and are validated there against the rendered roots.
    """
    for node in workflow.nodes:
        if node.type != "action" or not node.preconditions or node.action is None:
            continue
        read_roots = node.action.file_access.read if node.action.file_access is not None else []
        for precondition in node.preconditions:
            file = precondition.file
            if "{{" in file:
                continue  # resolved and validated at runtime
            if path_within_root(file, workflow_state_root()):
                continue
            if not any(path_within_root(file, root) for root in read_roots if "{{" not in root):
                raise ValueError(f"action node '{node.id}' precondition file '{file}' is not under its read roots")


def _validate_write_schemas(workflow: WorkflowV2) -> None:
    """Schema gates must point at a declared write root and a readable schema.

    Static (non-templated) paths are checked here; templated paths are only
    resolvable at runtime and are validated there against the rendered roots.
    """
    for node in workflow.nodes:
        if node.type != "action" or not node.schemas or node.action is None:
            continue
        read_roots = node.action.file_access.read if node.action.file_access is not None else []
        write_roots = node.action.file_access.write if node.action.file_access is not None else []
        for spec in node.schemas:
            if "{{" not in spec.file:
                if not any(path_within_root(spec.file, root) for root in write_roots if "{{" not in root):
                    raise ValueError(f"action node '{node.id}' schema target '{spec.file}' is not under its write roots")
            if "{{" not in spec.schema_file:
                if not any(path_within_root(spec.schema_file, root) for root in read_roots if "{{" not in root):
                    raise ValueError(f"action node '{node.id}' schema file '{spec.schema_file}' is not under its read roots")


def _validate_path(path: str, workflow: WorkflowV2, context: str) -> None:
    root, key = path.split(".")[1:3]
    if root == "inputs" and key not in workflow.inputs:
        raise ValueError(f"{context} references undeclared path '{path}'")
    if root == "state" and key not in workflow.state:
        raise ValueError(f"{context} references undeclared path '{path}'")
    if root == "outputs" and key not in {node.id for node in workflow.nodes}:
        raise ValueError(f"{context} references undeclared path '{path}'")


def _validate_forks(workflow: WorkflowV2, nodes: dict[str, Any], outgoing: dict[str, list[str]]) -> None:
    for node in workflow.nodes:
        if node.type == "fork":
            if sorted(node.branches) != sorted(outgoing[node.id]):
                raise ValueError(f"fork '{node.id}' branches must match its outgoing edges")
            if node.join not in nodes or nodes[node.join].type != "join" or nodes[node.join].fork != node.id:
                raise ValueError(f"fork '{node.id}' does not match its join")
            branch_writes: list[set[str]] = []
            for branch in node.branches:
                branch_writes.append(_writes_until_join(branch, node.join, nodes, outgoing))
            for left_index, left in enumerate(branch_writes):
                for right in branch_writes[left_index + 1 :]:
                    overlap = sorted(left & right)
                    if overlap:
                        raise ValueError(f"parallel branches write overlapping path '{overlap[0]}'")


def _writes_until_join(start: str, join: str, nodes: dict[str, Any], outgoing: dict[str, list[str]]) -> set[str]:
    writes: set[str] = set()
    pending = [start]
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == join or current in seen:
            continue
        seen.add(current)
        writes.update(nodes[current].writes)
        pending.extend(outgoing[current])
    return writes
