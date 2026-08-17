from __future__ import annotations

from ideer.workflows.v2.errors import (
    UNKNOWN,
    WorkflowInvalidRootsError,
    WorkflowMissingInputRootsError,
    node_failure_payload,
    run_error_summary,
    run_failure_payload,
)


def test_invalid_roots_error_carries_summary_and_violations() -> None:
    violations = [
        {"node_id": "evidence_collection", "access": "read", "path": "/mnt/eval-cases/case_01"},
        {"node_id": "evidence_collection", "access": "write", "path": "/mnt/fault-zeroing-outputs/out"},
    ]
    exc = WorkflowInvalidRootsError(violations)

    assert exc.code == "invalid_file_roots"
    assert exc.summary == "无法启动工作流：2 个文件访问路径不在允许的挂载范围内（涉及 1 个节点）"
    assert exc.violations == violations
    assert exc.payload()["code"] == "invalid_file_roots"
    assert exc.payload()["summary"] == exc.summary
    assert exc.payload()["error"] == "node 'evidence_collection': read:/mnt/eval-cases/case_01; node 'evidence_collection': write:/mnt/fault-zeroing-outputs/out"
    assert exc.api_detail() == {"code": "invalid_file_roots", "message": exc.summary, "violations": violations}


def test_missing_input_roots_error_summary() -> None:
    exc = WorkflowMissingInputRootsError([{"node_id": "collect", "access": "read", "path": "/mnt/eval-cases/gone"}])
    assert exc.code == "missing_input_roots"
    assert exc.summary == "无法启动工作流：1 个输入路径缺失或为空（涉及 1 个节点）"


def test_node_failure_payload_maps_schema_violations() -> None:
    from ideer.workflows.v2.compiler import WorkflowSchemaViolation

    payload = node_failure_payload("deduce", WorkflowSchemaViolation("deduce", ["$.status: wrong enum", "$.grade: missing"]))

    assert payload["node_id"] == "deduce"
    assert payload["code"] == "schema_violation"
    assert "未通过 schema 校验" in payload["summary"]
    assert payload["error"] == "$.status: wrong enum\n$.grade: missing"


def test_node_failure_payload_maps_precondition_failures() -> None:
    from ideer.workflows.v2.compiler import WorkflowPreconditionFailed

    payload = node_failure_payload("gate", WorkflowPreconditionFailed("gate", ["file fault_tree.json some_equals: confirmed"]))

    assert payload["code"] == "precondition_failed"
    assert "前置条件不满足" in payload["summary"]
    assert payload["error"] == "file fault_tree.json some_equals: confirmed"


def test_node_failure_payload_maps_iteration_limit_and_unknown() -> None:
    from ideer.workflows.v2.compiler import WorkflowIterationLimit

    limited = node_failure_payload("second", WorkflowIterationLimit("workflow_iteration_limit_exceeded"))
    assert limited["code"] == "iteration_limit"
    assert limited["summary"] == "节点「second」循环次数达到上限"
    assert limited["error"] == "workflow_iteration_limit_exceeded"

    unknown = node_failure_payload("boom", RuntimeError("something exploded"))
    assert unknown["code"] == UNKNOWN
    assert unknown["error"] == "something exploded"


def test_run_level_helpers_collapse_node_failures_to_short_summaries() -> None:
    from ideer.workflows.v2.compiler import WorkflowNodeFailed

    exc = WorkflowNodeFailed("node 'draft' reported failure: FAILED: 输入数据互相矛盾")
    summary = run_error_summary(exc)
    assert "执行失败" in summary
    assert len(summary) <= 120

    payload = run_failure_payload(exc)
    assert payload["code"] == "agent_failed"
    assert payload["summary"].startswith("工作流失败：")
    assert "输入数据互相矛盾" in payload["error"]


def test_run_failure_payload_passes_structured_errors_through() -> None:
    exc = WorkflowInvalidRootsError([{"node_id": "a", "access": "write", "path": "/etc/x"}])
    assert run_failure_payload(exc) == exc.payload()
    assert run_error_summary(exc) == exc.summary


def test_long_details_are_capped() -> None:
    from ideer.workflows.v2.compiler import WorkflowNodeFailed

    long_message = "FAILED: " + "x" * 10000
    payload = node_failure_payload("draft", WorkflowNodeFailed(f"node 'draft' reported failure: {long_message}"))

    assert len(payload["error"]) == 4001  # 4000 chars + "…"
    assert payload["error"].endswith("…")
