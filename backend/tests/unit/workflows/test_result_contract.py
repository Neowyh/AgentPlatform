"""Engine-side declared result contract enforcement (unified-kernel ticket 01)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.agentplatform.workflows.v2.file_roots import make_host_resolver
from app.agentplatform.workflows.v2.parser import parse_workflow_v2
from app.agentplatform.workflows.v2.result_contract import enforce_result_contract

REPO_ROOT = Path(__file__).resolve().parents[4]

VALIDATOR = "tests.support.result_contract_validators"


def _workflow(nodes: list[dict], validator: str | None = None) -> object:
    definition: dict = {
        "schema_version": 2,
        "name": "gated",
        "inputs": {"output_base_dir": {"type": "string", "default": "/mnt/user-data/outputs"}},
        "state": {},
        "entrypoint": "write",
        "nodes": nodes,
        "edges": [],
    }
    if validator is not None:
        definition["result_contract"] = {"validator": validator}
    return parse_workflow_v2(yaml.safe_dump(definition))


def _write_node() -> dict:
    return {
        "id": "write",
        "type": "action",
        "action": {
            "kind": "agent",
            "name": "writer",
            "file_access": {
                "write": [
                    "{{inputs.output_base_dir}}/fault_tree.json",
                    "{{inputs.output_base_dir}}/artifacts/corrective_actions.json",
                ]
            },
        },
    }


def test_workflow_without_declaration_is_not_gated() -> None:
    workflow = _workflow([_write_node()])

    assert enforce_result_contract(workflow, run_inputs={}, run_snapshot={}, resolver=lambda path: "/host") is None


def test_passing_validator_returns_no_error() -> None:
    workflow = _workflow([_write_node()], validator=f"{VALIDATOR}:accepting_validator")

    violation = enforce_result_contract(workflow, run_inputs={}, run_snapshot={}, resolver=lambda path: "/host")

    assert violation is None


def test_violating_validator_returns_structured_violation() -> None:
    workflow = _workflow([_write_node()], validator=f"{VALIDATOR}:rejecting_validator")

    violation = enforce_result_contract(workflow, run_inputs={}, run_snapshot={}, resolver=lambda path: "/host")

    assert violation is not None
    assert violation.code == "result_contract_failed"
    assert "2 项违规" in violation.summary
    assert [item["message"] for item in violation.violations] == ["报告缺少章节 X", "证据引用悬空"]
    assert violation.payload()["violations"] == [{"message": "报告缺少章节 X"}, {"message": "证据引用悬空"}]


def test_validator_execution_failure_fails_closed() -> None:
    workflow = _workflow([_write_node()], validator=f"{VALIDATOR}:exploding_validator")

    violation = enforce_result_contract(workflow, run_inputs={}, run_snapshot={}, resolver=lambda path: "/host")

    assert violation is not None
    assert violation.code == "result_contract_validator_error"
    assert "exploding_validator" in violation.summary


def test_unloadable_validator_fails_closed() -> None:
    """A validator that stops being importable after publication fails closed.

    The parser rejects unimportable validators at parse time, so the runtime
    case is simulated by building the model directly (definition drift).
    """
    definition = {
        "schema_version": 2,
        "name": "gated",
        "inputs": {},
        "state": {},
        "entrypoint": "write",
        "nodes": [{"id": "write", "type": "action", "action": {"kind": "tool", "name": "prepare"}}],
        "edges": [],
        "result_contract": {"validator": "app.nonexistent_gate_module:validate"},
    }
    from app.agentplatform.workflows.v2.schema import WorkflowV2

    workflow = WorkflowV2.model_validate(definition)

    violation = enforce_result_contract(workflow, run_inputs={}, run_snapshot={}, resolver=lambda path: "/host")

    assert violation is not None
    assert violation.code == "result_contract_validator_error"


def test_malformed_validator_result_fails_closed() -> None:
    workflow = _workflow([_write_node()], validator=f"{VALIDATOR}:non_list_validator")

    violation = enforce_result_contract(workflow, run_inputs={}, run_snapshot={}, resolver=lambda path: "/host")

    assert violation is not None
    assert violation.code == "result_contract_validator_error"


def test_validator_receives_common_artifact_root_and_run_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate derives the artifact root from the run's declared write roots."""

    from app.agentplatform.workflows.v2 import file_roots
    from deerflow.config.paths import Paths

    monkeypatch.setattr(file_roots, "get_paths", lambda: Paths(str(tmp_path / "base")))
    workflow = _workflow([_write_node()], validator=f"{VALIDATOR}:recording_validator")
    resolver = make_host_resolver("run-gate-root", "user-1")
    run_inputs = {"output_base_dir": "/mnt/user-data/outputs"}

    from tests.support import result_contract_validators as stubs

    stubs.RECORDED_OUTPUTS_DIR.clear()
    stubs.RECORDED_SNAPSHOTS.clear()
    enforce_result_contract(workflow, run_inputs=run_inputs, run_snapshot={"state": {"k": 1}}, resolver=resolver)

    expected_root = str(tmp_path / "base" / "users" / "user-1" / "threads" / "run-gate-root" / "user-data" / "outputs")
    assert stubs.RECORDED_OUTPUTS_DIR == [expected_root]
    assert stubs.RECORDED_SNAPSHOTS == [{"state": {"k": 1}}]
