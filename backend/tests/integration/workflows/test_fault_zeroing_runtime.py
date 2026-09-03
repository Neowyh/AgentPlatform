"""Full-chain integration coverage for the fault-zeroing workflow v2 graph.

Uses the real ``resources/workflows/fault-zeroing.yaml`` definition through the real
parser and compiler, with stub adapters standing in for the LLM agent nodes.
The stubs write realistic artifacts to disk so the acceptance boundary is the
production graph wiring, not any one node's content.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import MemorySaver

from ideer.workflows.v2.adapters import ActionAdapterRegistry
from ideer.workflows.v2.compiler import WorkflowGraphCompiler
from ideer.workflows.v2.parser import parse_workflow_v2_file

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_PATH = REPO_ROOT / "resources" / "workflows" / "fault-zeroing.yaml"

TOP_EVENT = "热流传感器 HF-07 测值超过试验允许上限"


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _structure() -> dict:
    return {
        "top_event": TOP_EVENT,
        "intermediate_events": [
            {
                "id": "IE-01",
                "name": "测量链路异常",
                "description": "传感器、接线和采集链路需要排查",
                "parent_ids": ["TOP"],
                "logic": "OR",
            }
        ],
        "bottom_events": [
            {
                "id": "BE-01",
                "name": "HF-07 零点漂移",
                "description": "关车后零位偏差超过试验前校准范围",
                "parent_ids": ["IE-01"],
                "evidence_ids": [],
                "probability": None,
                "probability_basis": None,
                "confidence": None,
                "status": None,
                "verification_suggestion": "复测 HF-07 零位",
            }
        ],
        "logic": [{"source": "TOP", "target": "IE-01", "type": "OR"}],
    }


def _assessed_tree() -> dict:
    tree = _structure()
    tree["bottom_events"][0].update(
        {
            "evidence_ids": ["EV-01"],
            "probability": "high",
            "probability_basis": "本次零点复测复现",
            "confidence": "high",
            "status": "confirmed",
        }
    )
    tree["evidence"] = [
        {
            "id": "EV-01",
            "source": "03_test_records.md#L12-L18",
            "grade": "A",
            "type": "test_record",
            "summary": "HF-07 关车后零位复测偏差超出校准范围。",
            "supports": ["BE-01"],
            "contradicts": [],
        }
    ]
    tree["root_causes"] = [
        {
            "id": "RC-01",
            "name": "HF-07 测量链路零点漂移",
            "description": "零点复测和历史复核共同支持测量链路异常。",
            "evidence_ids": ["EV-01"],
            "status": "confirmed",
            "confidence": "high",
        }
    ]
    tree["verification_plan"] = [
        {
            "id": "VP-01",
            "target_id": "BE-01",
            "item": "零点复测复核",
            "method": "复查相邻测点和重复试验数据",
            "expected_result": "确认零漂是否复现",
            # Must satisfy VERIFICATION_STATUS_VALUES (pending/in_progress/
            # passed/failed/blocked); "to_verify" is a conclusion status and
            # would now be caught by the schema gate once an
            # artifact_resolver is wired in.
            "status": "pending",
        }
    ]
    return tree


def _corrective_actions() -> dict:
    return {
        "corrective_actions": [
            {
                "id": "CA-001",
                "name": "更换传感器",
                "description": "对批次传感器更换",
                "target_root_cause_id": "RC-01",
                "owner": "工艺部门",
                "completion_criteria": "更换后通过48小时试车",
                "priority": "high",
                "status": "planned",
            }
        ]
    }


class NodeStub:
    """Stands in for the LLM agent on every node of the workflow."""

    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    async def run(self, context, params):
        node_id = context.node_id
        self.calls.append(node_id)
        base = Path(context.inputs["output_base_dir"])
        if node_id == "evidence_collection":
            _write(
                base / "artifacts/evidence/evidence_table.json",
                {"evidence": []},
            )
            (base / "artifacts/evidence/coverage_matrix.md").parent.mkdir(parents=True, exist_ok=True)
            (base / "artifacts/evidence/coverage_matrix.md").write_text("# 覆盖矩阵\n", encoding="utf-8")
            return {"total": 0, "grade_distribution": {}, "coverage_status": "incomplete"}
        if node_id == "deductive_tree":
            _write(base / "artifacts/tree/fault_tree_structure.json", _structure())
            return {"top_event": TOP_EVENT, "depth": 2, "node_count": 3}
        if node_id == "review_and_crosscheck":
            return {"structure_issues": [], "evidence_gaps": []}
        if node_id == "integrate_tree":
            _write(base / "artifacts/tree/fault_tree_structure.json", _structure())
            return {"top_event": TOP_EVENT, "depth": 2, "node_count": 3}
        if node_id == "evidence_assessment":
            _write(base / "fault_tree.json", _assessed_tree())
            return {"root_causes": 1, "to_verify": 1}
        if node_id == "assessment_review":
            return {"issues": []}
        if node_id == "assessment_refine":
            _write(base / "fault_tree.json", _assessed_tree())
            return {"root_causes": 1, "to_verify": 1}
        if node_id == "corrective_actions":
            _write(base / "artifacts/corrective_actions.json", _corrective_actions())
            return {"actions": 1}
        if node_id == "generate_outputs":
            for name in ("fault_tree.svg", "analysis_process.svg"):
                (base / name).write_text("<svg><rect/><text>x</text></svg>", encoding="utf-8")
            (base / "bottom_event_assessment.md").write_text("| 底事件 | 状态 |\n| --- | --- |\n", encoding="utf-8")
            (base / "zeroing_report.md").write_text("# 归零报告\n", encoding="utf-8")
            return {"files": 4}
        raise AssertionError(f"unexpected node {node_id}")


def _compile_workflow(adapter: NodeStub):
    definition = parse_workflow_v2_file(WORKFLOW_PATH)
    registry = ActionAdapterRegistry({("agent", "fault-zeroing"): adapter})
    return WorkflowGraphCompiler(definition, registry).compile(checkpointer=MemorySaver())


@pytest.mark.asyncio
async def test_fault_zeroing_full_workflow_produces_artifacts_and_state(tmp_path: Path) -> None:
    calls: list[str] = []
    graph = _compile_workflow(NodeStub(calls))
    inputs = {
        "upload_dir": str(tmp_path / "uploads"),
        "problem_description": TOP_EVENT,
        "output_base_dir": str(tmp_path / "outputs"),
    }
    result = await graph.ainvoke(
        {"run_id": "run-1", "inputs": inputs, "state": {}, "outputs": {}},
        config={"configurable": {"thread_id": "wf:run-1"}},
    )

    assert set(calls[:2]) == {"evidence_collection", "deductive_tree"}
    assert calls[2:] == [
        "review_and_crosscheck",
        "integrate_tree",
        "evidence_assessment",
        "assessment_review",
        "assessment_refine",
        "corrective_actions",
        "generate_outputs",
    ]

    state = result["state"]
    for key in (
        "evidence_summary",
        "tree_structure",
        "all_findings",
        "assessment_summary",
        "assessment_review",
        "corrective_actions_summary",
    ):
        assert state[key], f"state.{key} missing"

    base = tmp_path / "outputs"
    for path in (
        "artifacts/evidence/evidence_table.json",
        "artifacts/evidence/coverage_matrix.md",
        "artifacts/tree/fault_tree_structure.json",
        "artifacts/corrective_actions.json",
        "fault_tree.json",
        "fault_tree.svg",
        "bottom_event_assessment.md",
        "analysis_process.svg",
        "zeroing_report.md",
    ):
        assert (base / path).is_file(), f"missing artifact {path}"
    assert json.loads((base / "fault_tree.json").read_text(encoding="utf-8"))["top_event"] == TOP_EVENT


@pytest.mark.asyncio
async def test_fault_zeroing_evidence_assessment_retries_on_transient_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("ideer.workflows.v2.compiler.asyncio.sleep", no_sleep)

    delegate = NodeStub([])
    attempts = 0

    class Flaky(NodeStub):
        async def run(self, context, params):
            nonlocal attempts
            if context.node_id == "evidence_assessment":
                attempts += 1
                if attempts == 1:
                    raise RuntimeError("transient LLM failure")
            return await delegate.run(context, params)

    graph = _compile_workflow(Flaky([]))
    inputs = {
        "upload_dir": str(tmp_path / "uploads"),
        "problem_description": TOP_EVENT,
        "output_base_dir": str(tmp_path / "outputs"),
    }
    result = await graph.ainvoke(
        {"run_id": "run-2", "inputs": inputs, "state": {}, "outputs": {}},
        config={"configurable": {"thread_id": "wf:run-2"}},
    )

    assert attempts == 2
    assert result["state"]["assessment_summary"] == {"root_causes": 1, "to_verify": 1}
    assert (tmp_path / "outputs" / "fault_tree.json").is_file()
