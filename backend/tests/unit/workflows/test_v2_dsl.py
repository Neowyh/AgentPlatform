from __future__ import annotations

import pytest

from ideer.workflows.v2.parser import parse_workflow_v2


def _workflow(**overrides: object) -> str:
    values = {
        "schema_version": 2,
        "name": "approval",
        "inputs": {"request": {"type": "string", "required": True}},
        "state": {"attempt": {"type": "integer", "default": 0}},
        "entrypoint": "prepare",
        "nodes": [
            {
                "id": "prepare",
                "type": "action",
                "action": {"kind": "tool", "name": "prepare"},
                "writes": ["$.state.attempt"],
            },
            {
                "id": "review",
                "type": "interrupt",
                "roles": ["department_admin"],
            },
        ],
        "edges": [{"from": "prepare", "to": "review"}],
    }
    values.update(overrides)
    import yaml

    return yaml.safe_dump(values)


def test_v2_parser_accepts_declared_graph() -> None:
    workflow = parse_workflow_v2(_workflow())

    assert workflow.schema_version == 2
    assert workflow.entrypoint == "prepare"
    assert workflow.nodes[0].action.name == "prepare"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"schema_version": 1}, "schema_version must be 2"),
        ({"entrypoint": "missing"}, "entrypoint 'missing' does not name a node"),
        ({"edges": [{"from": "prepare", "to": "missing"}]}, "edge target 'missing' does not name a node"),
        ({"nodes": [{"id": "prepare", "type": "action", "action": {"kind": "tool", "name": "prepare"}}, {"id": "prepare", "type": "interrupt", "roles": ["admin"]}]}, "duplicate node id 'prepare'"),
    ],
)
def test_v2_parser_rejects_invalid_graph(change: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_workflow_v2(_workflow(**change))


def test_v2_parser_rejects_unbounded_cycle() -> None:
    nodes = [
        {"id": "a", "type": "action", "action": {"kind": "tool", "name": "a"}},
        {"id": "b", "type": "action", "action": {"kind": "tool", "name": "b"}},
    ]
    with pytest.raises(ValueError, match="cycle edge a -> b must declare max_iterations"):
        parse_workflow_v2(_workflow(entrypoint="a", nodes=nodes, edges=[{"from": "a", "to": "b"}, {"from": "b", "to": "a"}]))


def test_v2_parser_rejects_undeclared_template_path() -> None:
    nodes = [
        {"id": "prepare", "type": "action", "action": {"kind": "tool", "name": "prepare", "params": {"text": "{{ $.inputs.unknown }}"}}},
        {"id": "review", "type": "interrupt", "roles": ["admin"]},
    ]
    with pytest.raises(ValueError, match=r"template references undeclared path '\$\.inputs\.unknown'"):
        parse_workflow_v2(_workflow(nodes=nodes))


def test_v2_parser_rejects_overlapping_parallel_writes() -> None:
    nodes = [
        {"id": "fork", "type": "fork", "branches": ["left", "right"], "join": "join"},
        {"id": "left", "type": "action", "action": {"kind": "tool", "name": "left"}, "writes": ["$.state.value"]},
        {"id": "right", "type": "action", "action": {"kind": "tool", "name": "right"}, "writes": ["$.state.value"]},
        {"id": "join", "type": "join", "fork": "fork"},
    ]
    edges = [{"from": "fork", "to": "left"}, {"from": "fork", "to": "right"}, {"from": "left", "to": "join"}, {"from": "right", "to": "join"}]
    with pytest.raises(ValueError, match=r"parallel branches write overlapping path '\$\.state\.value'"):
        parse_workflow_v2(_workflow(entrypoint="fork", nodes=nodes, edges=edges))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            {
                "nodes": [
                    {"id": "prepare", "type": "action", "action": {"kind": "tool", "name": "prepare"}},
                    {"id": "review", "type": "interrupt", "roles": ["admin"]},
                    {"id": "orphan", "type": "interrupt", "roles": ["admin"]},
                ]
            },
            "unreachable node 'orphan'",
        ),
        (
            {
                "nodes": [
                    {"id": "prepare", "type": "action", "action": {"kind": "tool", "name": "prepare"}},
                    {"id": "review", "type": "interrupt", "roles": ["admin"], "writes": ["$.state.attempt"]},
                ]
            },
            "only action nodes may declare writes",
        ),
    ],
)
def test_v2_parser_rejects_unreachable_nodes_and_non_action_writes(change: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_workflow_v2(_workflow(**change))


def test_v2_parser_rejects_route_with_unknown_target() -> None:
    nodes = [
        {"id": "route", "type": "route", "expression": "$.state.attempt > 0", "routes": {"positive": "missing"}},
        {"id": "review", "type": "interrupt", "roles": ["admin"]},
    ]
    edges = [{"from": "route", "to": "review"}, {"from": "route", "to": "review"}]

    with pytest.raises(ValueError, match="route 'route' targets unknown node 'missing'"):
        parse_workflow_v2(_workflow(entrypoint="route", nodes=nodes, edges=edges))


def test_v2_parser_rejects_fork_join_mismatch() -> None:
    nodes = [
        {"id": "fork", "type": "fork", "branches": ["left"], "join": "join"},
        {"id": "left", "type": "interrupt", "roles": ["admin"]},
        {"id": "join", "type": "join", "fork": "other"},
    ]
    edges = [{"from": "fork", "to": "left"}, {"from": "left", "to": "join"}]

    with pytest.raises(ValueError, match="fork 'fork' does not match its join"):
        parse_workflow_v2(_workflow(entrypoint="fork", nodes=nodes, edges=edges))
