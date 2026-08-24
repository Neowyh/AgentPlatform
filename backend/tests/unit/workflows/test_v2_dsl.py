from __future__ import annotations

from pathlib import Path

import pytest

from ideer.workflows.v2.parser import parse_workflow_v2, parse_workflow_v2_file

REPO_ROOT = Path(__file__).resolve().parents[4]


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
    nodes = [
        {"id": "prepare", "type": "action", "action": {"kind": "tool", "name": "prepare", "params": {"prompt": "处理：{{inputs.request}}"}}, "writes": ["$.state.attempt"]},
        {"id": "review", "type": "interrupt", "roles": ["department_admin"]},
    ]
    workflow = parse_workflow_v2(_workflow(nodes=nodes))

    assert workflow.schema_version == 2
    assert workflow.entrypoint == "prepare"
    assert workflow.nodes[0].action.name == "prepare"


def test_v2_parser_accepts_file_access_only_for_agent_actions() -> None:
    nodes = [
        {
            "id": "prepare",
            "type": "action",
            "action": {
                "kind": "agent",
                "name": "fault-zeroing",
                "file_access": {
                    "read": ["{{inputs.request}}"],
                    "write": ["/outputs/evidence"],
                },
                "params": {"prompt": "collect"},
            },
        },
        {"id": "review", "type": "interrupt", "roles": ["department_admin"]},
    ]

    workflow = parse_workflow_v2(_workflow(nodes=nodes))

    assert workflow.nodes[0].action.file_access.read == ["{{inputs.request}}"]
    assert workflow.nodes[0].action.file_access.write == ["/outputs/evidence"]

    nodes[0]["action"]["kind"] = "tool"
    with pytest.raises(ValueError, match="file_access is only valid for agent actions"):
        parse_workflow_v2(_workflow(nodes=nodes))


@pytest.mark.parametrize(
    "root",
    ["relative/path", "/safe/../secret", "/safe\\..\\secret"],
)
def test_v2_parser_rejects_unsafe_file_access_roots(root: str) -> None:
    nodes = [
        {
            "id": "prepare",
            "type": "action",
            "action": {
                "kind": "agent",
                "name": "fault-zeroing",
                "file_access": {"read": [root]},
            },
        },
        {"id": "review", "type": "interrupt", "roles": ["department_admin"]},
    ]

    with pytest.raises(ValueError, match="file_access root"):
        parse_workflow_v2(_workflow(nodes=nodes))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"schema_version": 1}, "schema_version must be 2"),
        ({"entrypoint": "missing"}, "entrypoint 'missing' does not name a node"),
        ({"edges": [{"from": "prepare", "to": "missing"}]}, "edge target 'missing' does not name a node"),
        ({"nodes": [{"id": "prepare", "type": "action", "action": {"kind": "tool", "name": "prepare"}}, {"id": "prepare", "type": "interrupt", "roles": ["admin"]}]}, "duplicate node id 'prepare'"),
        (
            {
                "nodes": [
                    {"id": "prepare", "type": "action", "action": {"kind": "tool", "name": "prepare", "params": {"text": "{{broken"}}},
                    {"id": "review", "type": "interrupt", "roles": ["admin"]},
                ]
            },
            "invalid template syntax in action node 'prepare'",
        ),
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


@pytest.mark.parametrize("template", ["{{ $.inputs.unknown }}", "{{inputs.unknown}}"])
def test_v2_parser_rejects_undeclared_template_path(template: str) -> None:
    nodes = [
        {"id": "prepare", "type": "action", "action": {"kind": "tool", "name": "prepare", "params": {"text": template}}},
        {"id": "review", "type": "interrupt", "roles": ["admin"]},
    ]
    with pytest.raises(ValueError, match=r"template references undeclared path"):
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


def test_v2_parser_accepts_fault_zeroing_workflow() -> None:
    workflow = parse_workflow_v2_file(REPO_ROOT / "resources" / "workflows" / "fault-zeroing.yaml")

    assert workflow.schema_version == 2
    assert workflow.name == "fault-zeroing"
    assert workflow.entrypoint == "fork_start"
    assert {node.id for node in workflow.nodes} == {
        "fork_start",
        "evidence_collection",
        "deductive_tree",
        "join_review",
        "review_and_crosscheck",
        "integrate_tree",
        "evidence_assessment",
        "assessment_review",
        "assessment_refine",
        "corrective_actions",
        "generate_outputs",
    }

    fork = next(node for node in workflow.nodes if node.id == "fork_start")
    assert fork.type == "fork"
    assert sorted(fork.branches) == ["deductive_tree", "evidence_collection"]
    assert fork.join == "join_review"

    written = {node.id: node.writes for node in workflow.nodes if node.writes}
    assert written == {
        "evidence_collection": ["$.state.evidence_summary"],
        "deductive_tree": ["$.state.tree_structure"],
        "review_and_crosscheck": ["$.state.all_findings"],
        "integrate_tree": ["$.state.tree_structure"],
        "evidence_assessment": ["$.state.assessment_summary"],
        "assessment_review": ["$.state.assessment_review"],
        "assessment_refine": ["$.state.assessment_summary"],
        "corrective_actions": ["$.state.corrective_actions_summary"],
    }

    policies = {node.id: node.action.file_access.model_dump() for node in workflow.nodes if node.action is not None}
    assert set(policies) == {
        "evidence_collection",
        "deductive_tree",
        "review_and_crosscheck",
        "integrate_tree",
        "evidence_assessment",
        "assessment_review",
        "assessment_refine",
        "corrective_actions",
        "generate_outputs",
    }
    assert policies["deductive_tree"] == {
        "read": [
            "/mnt/skills/fault-zeroing",
            "/mnt/skills/fault-zeroing/templates",
        ],
        "write": ["{{inputs.output_base_dir}}/artifacts/tree/fault_tree_structure.json"],
    }
    assert all("artifacts/evidence" not in root for root in policies["deductive_tree"]["read"])

    integrate_tree = next(node for node in workflow.nodes if node.id == "integrate_tree")
    assert integrate_tree.action.file_access.model_dump()["read"] == [
        "/mnt/skills/fault-zeroing",
        "{{inputs.output_base_dir}}/artifacts/tree/",
        "{{inputs.output_base_dir}}/artifacts/evidence/",
    ]
    assert integrate_tree.action.params.get("max_turns") == 150

    expected_max_turns = {
        "evidence_collection": 150,
        "deductive_tree": 150,
        "review_and_crosscheck": 150,
        "integrate_tree": 150,
        "evidence_assessment": 150,
        "assessment_review": 150,
        "assessment_refine": 150,
        "corrective_actions": 150,
        "generate_outputs": 200,
    }
    agent_nodes = {node.id: node.action.params.get("max_turns") for node in workflow.nodes if node.action is not None}
    assert agent_nodes == expected_max_turns

    prompts = {node.id: (node.action.params.get("prompt") or "") + (node.action.params.get("system_prompt") or "") for node in workflow.nodes if node.action is not None}
    assert "read_document" in prompts["evidence_collection"]
    assert "page_range" in prompts["evidence_collection"]
    assert "read_document" in prompts["assessment_review"]

    # Reliability hardening: every agent (action) node retries once with
    # backoff so a single max-turns exhaustion does not fail the whole run.
    # fork/join control nodes carry no retry policy by design.
    retry_by_node = {node.id: (node.retry.max_attempts, node.retry.backoff_seconds) for node in workflow.nodes if node.type == "action"}
    assert set(retry_by_node) == {
        "evidence_collection",
        "deductive_tree",
        "review_and_crosscheck",
        "integrate_tree",
        "evidence_assessment",
        "assessment_review",
        "assessment_refine",
        "corrective_actions",
        "generate_outputs",
    }
    assert all(value == (2, 30) for value in retry_by_node.values())

    # Write-schema gates: the intermediate tree is validated after both
    # deductive construction and post-review integration.
    schemas_by_node = {node.id: [(spec.file, spec.schema_file) for spec in node.schemas] for node in workflow.nodes if node.schemas}
    assert schemas_by_node == {
        "deductive_tree": [
            (
                "{{inputs.output_base_dir}}/artifacts/tree/fault_tree_structure.json",
                "/mnt/skills/fault-zeroing/templates/fault_tree_structure.schema.json",
            )
        ],
        "integrate_tree": [
            (
                "{{inputs.output_base_dir}}/artifacts/tree/fault_tree_structure.json",
                "/mnt/skills/fault-zeroing/templates/fault_tree_structure.schema.json",
            )
        ],
        "evidence_assessment": [
            (
                "{{inputs.output_base_dir}}/fault_tree.json",
                "/mnt/skills/fault-zeroing/templates/fault_tree.schema.json",
            )
        ],
        "corrective_actions": [
            (
                "{{inputs.output_base_dir}}/artifacts/corrective_actions.json",
                "/mnt/skills/fault-zeroing/templates/corrective_actions.schema.json",
            )
        ],
    }

    # Input preconditions: downstream nodes fail fast on missing/empty
    # upstream artifacts instead of letting the agent improvise.
    preconditions_by_node = {node.id: [(pre.file, pre.non_empty, pre.json_path, pre.some_equals) for pre in node.preconditions] for node in workflow.nodes if node.preconditions}
    assert preconditions_by_node == {
        "review_and_crosscheck": [
            ("{{inputs.output_base_dir}}/artifacts/tree/fault_tree_structure.json", True, None, None),
            ("{{inputs.output_base_dir}}/artifacts/evidence/evidence_table.json", True, None, None),
        ],
        "integrate_tree": [("{{inputs.output_base_dir}}/artifacts/tree/fault_tree_structure.json", True, None, None)],
        "evidence_assessment": [
            ("{{inputs.output_base_dir}}/artifacts/tree/fault_tree_structure.json", True, None, None),
            ("{{inputs.output_base_dir}}/artifacts/evidence/evidence_table.json", True, None, None),
            ("{{inputs.output_base_dir}}/artifacts/evidence/coverage_matrix.md", True, None, None),
        ],
        "assessment_refine": [("{{inputs.output_base_dir}}/fault_tree.json", True, None, None)],
        "corrective_actions": [
            (
                "{{inputs.output_base_dir}}/fault_tree.json",
                True,
                "$.root_causes[*].status",
                "confirmed",
            )
        ],
        "generate_outputs": [
            ("{{inputs.output_base_dir}}/fault_tree.json", True, None, None),
            ("{{inputs.output_base_dir}}/artifacts/evidence/evidence_table.json", True, None, None),
        ],
    }
