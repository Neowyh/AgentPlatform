"""Cross-entry regression guards for the known fault-zeroing defects (ticket 07).

Each test pins one historically observed failure mode so it cannot return:

1. 最终修订绕过       — assessment_refine must carry a fault_tree schema gate.
2. 非法验证状态       — invalid verification statuses are rejected.
3. confidence 漂移    — schema enums and the contract share one definition.
4. 缺失报告章节       — a missing report section fails the contract.
5. 错误 Workflow 路径 — the acceptance harness points at the real YAML.
6. validator 未执行   — the acceptance report records a contract evaluation.
7. 文件存在即成功     — non-empty-but-broken artifacts never complete a run.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
PKG_DIR = REPO_ROOT / "backend" / "packages" / "harness" / "ideer" / "fault_zeroing"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def workflow_yaml() -> dict:
    import yaml

    return yaml.safe_load((REPO_ROOT / "resources" / "workflows" / "fault-zeroing.yaml").read_text(encoding="utf-8"))


def _node(workflow: dict, node_id: str) -> dict:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def test_final_revision_cannot_bypass_schema_gate(workflow_yaml: dict) -> None:
    """Regression 1: the last write of fault_tree.json is still schema-gated."""

    refine = _node(workflow_yaml, "assessment_refine")
    gates = refine.get("schemas") or []
    assert any("fault_tree.schema.json" in (gate.get("schema_file") or "") for gate in gates), "assessment_refine must gate fault_tree.json with fault_tree.schema.json"

    # The earlier gates must still be present as well.
    for node_id in ("integrate_tree", "evidence_assessment"):
        gates = _node(workflow_yaml, node_id).get("schemas") or []
        assert any("fault_tree" in (gate.get("schema_file") or "") for gate in gates), f"{node_id} lost its schema gate"


def test_invalid_verification_status_is_rejected_by_contract(tmp_path: Path) -> None:
    """Regression 2: only pending/in_progress/passed/failed/blocked pass."""

    contract = load_module("fz_contract_regr", PKG_DIR / "contract.py")
    fixtures = load_module(
        "fz_contract_fixtures_regr",
        REPO_ROOT / "backend" / "tests" / "unit" / "fault_zeroing" / "test_contract.py",
    )
    tree = fixtures.valid_fault_tree()
    tree["verification_plan"][0]["status"] = "to_verify"
    output_dir = fixtures.write_outputs(tmp_path, tree)

    verdict = contract.evaluate_result_contract(output_dir)

    assert not verdict.ok
    assert "verification_status_invalid" in {f.code for f in verdict.findings}


def test_confidence_drift_is_structurally_impossible(tmp_path: Path) -> None:
    """Regression 3: schema gate and contract accept the same confidence set."""

    contract = load_module("fz_contract_regr2", PKG_DIR / "contract.py")
    schema = json.loads((REPO_ROOT / "resources" / "skills" / "fault-zeroing" / "templates" / "fault_tree.schema.json").read_text(encoding="utf-8"))

    assert set(schema["$defs"]["confidence"]["enum"]) == contract.CONFIDENCE_VALUES

    # A Finding Confidence value that passes the schema gate also passes the
    # contract (historically the validator rejected it).
    fixtures = load_module(
        "fz_contract_fixtures_regr2",
        REPO_ROOT / "backend" / "tests" / "unit" / "fault_zeroing" / "test_contract.py",
    )
    tree = fixtures.valid_fault_tree()
    tree["bottom_events"][0]["confidence"] = "high_risk_candidate"
    output_dir = fixtures.write_outputs(tmp_path, tree)
    assert contract.evaluate_result_contract(output_dir).ok


def test_missing_report_section_fails(tmp_path: Path) -> None:
    """Regression 4: dropping a required section fails the contract."""

    contract = load_module("fz_contract_regr3", PKG_DIR / "contract.py")
    fixtures = load_module(
        "fz_contract_fixtures_regr3",
        REPO_ROOT / "backend" / "tests" / "unit" / "fault_zeroing" / "test_contract.py",
    )
    report = fixtures.valid_report().replace(
        "## 1. 问题概述\n\n- 顶事件：热流传感器 HF-07 测值超过试验允许上限\n- 主根因：HF-07 测量链路零点漂移\n",
        "",
    )
    output_dir = fixtures.write_outputs(tmp_path, report=report)

    verdict = contract.evaluate_result_contract(output_dir)

    assert not verdict.ok
    assert any(f.code == "report_section_missing" for f in verdict.findings)


def test_acceptance_harness_points_at_real_workflow_and_runs_contract() -> None:
    """Regressions 5+6: real YAML path; contract evaluation recorded."""

    source = (REPO_ROOT / "scripts" / "run_fault_zeroing_acceptance.py").read_text(encoding="utf-8")

    workflow_path = REPO_ROOT / "resources" / "workflows" / "fault-zeroing.yaml"
    assert workflow_path.is_file()
    assert 'REPO_ROOT / "resources" / "workflows" / "fault-zeroing.yaml"' in source
    assert 'REPO_ROOT / "workflows" / "fault-zeroing.yaml"' not in source

    assert '"validator_run": True' in source
    assert "evaluate_completion" in source
    assert "FaultZeroingKernel" in source


def test_file_existence_alone_never_completes_a_run(tmp_path: Path) -> None:
    """Regression 7: placeholder outputs fail the contract gate."""

    kernel_mod = load_module("fz_kernel_regr", PKG_DIR / "kernel.py")
    contract = load_module("fz_contract_regr4", PKG_DIR / "contract.py")
    load_module("fz_intake_regr", PKG_DIR / "intake.py")
    load_module("fz_policy_regr", PKG_DIR / "policy.py")

    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    for name in (
        "fault_tree.json",
        "fault_tree.svg",
        "bottom_event_assessment.md",
        "analysis_process.svg",
        "zeroing_report.md",
    ):
        (output_dir / name).write_text("占位\n", encoding="utf-8")

    verdict = contract.evaluate_result_contract(output_dir)
    assert not verdict.ok

    completion = kernel_mod.KernelCompletion(
        run_id="run-x",
        status=kernel_mod.COMPLETION_STATUS_FAILED,
        verdict=verdict,
    )
    assert completion.status == kernel_mod.COMPLETION_STATUS_FAILED
