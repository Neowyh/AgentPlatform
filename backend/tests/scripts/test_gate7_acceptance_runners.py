import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.acceptance.run_gate7_agent_probe import _validate_probe_results
from scripts.acceptance.run_gate7_archive_failure import _validate_archive_failure
from scripts.acceptance.run_gate7_fault_recovery import _validate_outage, _validate_retry
from scripts.acceptance.run_gate7_matrix import (
    Gateway,
    _annotate_real_evidence,
    _has_workflow_citation,
    _resumable_row,
)
from scripts.acceptance.run_gate7_mixed_web import _validate_mixed_sources
from scripts.acceptance.run_gate7_streaming import _validate_stream_event_types
from scripts.acceptance.run_gate7_truncated import _validate_truncated_output


def test_empty_hit_rejects_an_access_denied_receipt() -> None:
    runs = [
        {
            "status": "success",
            "receipts": [
                {
                    "receipt_id": "rr-denied",
                    "result_status": "access_denied",
                    "archive_status": "archived",
                    "items": [],
                }
            ],
        }
    ]

    with pytest.raises(ValueError, match="empty_hit"):
        _validate_probe_results("empty_hit", runs)


def test_duplicate_requires_two_archived_successful_receipts() -> None:
    runs = [
        {
            "status": "success",
            "receipts": [
                {
                    "receipt_id": "rr-one",
                    "result_status": "access_denied",
                    "archive_status": "archived",
                    "items": [],
                }
            ],
        },
        {
            "status": "success",
            "receipts": [
                {
                    "receipt_id": "rr-two",
                    "result_status": "access_denied",
                    "archive_status": "archived",
                    "items": [],
                }
            ],
        },
    ]

    with pytest.raises(ValueError, match="duplicate"):
        _validate_probe_results("duplicate", runs)


def test_workflow_citation_accepts_numbered_source_reference() -> None:
    result = '"Gate 7 isolated matrix citation marker 8d7d6179. " Citation: **[1] ideer-kb-rev2 / gate7-matrix-marker.txt** (score 0.98)'

    assert _has_workflow_citation(result)


def test_workflow_citation_requires_the_marker_and_matching_source() -> None:
    result = "[1] unrelated.txt"

    assert not _has_workflow_citation(result)


def test_streaming_requires_intermediate_data_before_terminal_event() -> None:
    with pytest.raises(ValueError, match="intermediate"):
        _validate_stream_event_types(["metadata", "end"])

    _validate_stream_event_types(["metadata", "values", "end"])


def test_truncated_requires_the_real_tool_output_truncation_marker() -> None:
    with pytest.raises(ValueError, match="truncation"):
        _validate_truncated_output("complete untruncated text")

    _validate_truncated_output("[1] source.txt\ncontent… (response truncated)")


def test_provider_outage_requires_archived_error_on_frozen_revision() -> None:
    run = {"receipts": [{"result_status": "provider_error", "archive_status": "archived", "revision_id": "rev-2"}]}
    _validate_outage(run, "rev-2")
    with pytest.raises(ValueError, match="provider_error"):
        _validate_outage({"receipts": [{**run["receipts"][0], "result_status": "success"}]}, "rev-2")


def test_retry_requires_error_then_archived_success_on_same_revision() -> None:
    failed = {"receipts": [{"result_status": "provider_error", "archive_status": "archived", "revision_id": "rev-2"}]}
    recovered = {"status": "completed", "receipts": [{"result_status": "success", "archive_status": "archived", "revision_id": "rev-2"}]}
    _validate_retry(failed, recovered, "rev-2")
    with pytest.raises(ValueError, match="same revision"):
        _validate_retry(failed, {**recovered, "receipts": [{**recovered["receipts"][0], "revision_id": "rev-1"}]}, "rev-2")


def test_archive_failure_requires_failed_receipt_without_citation_items() -> None:
    _validate_archive_failure({"receipts": [{"receipt_id": "rr-failed", "archive_status": "failed", "items": [{"evidence_id": "rr-failed_i1"}], "cited_item_ids": []}], "assistant_text": "No verifiable citation is available."})
    with pytest.raises(ValueError, match="fail closed"):
        _validate_archive_failure({"receipts": [{"receipt_id": "rr-failed", "archive_status": "failed", "items": [], "cited_item_ids": []}], "assistant_text": "[source](evidence://rr-failed_i1)"})


def test_mixed_web_requires_both_tools_archived_kb_and_web_url() -> None:
    run = {"tool_names": ["knowledge_search", "web_search"], "retrieval_receipts": [{"archive_status": "archived", "items": [{"evidence_id": "rr_i1"}]}], "assistant_text": "KB [1]; Web https://docs.python.org/"}
    _validate_mixed_sources(run)
    with pytest.raises(ValueError, match="knowledge_search and web_search"):
        _validate_mixed_sources({**run, "tool_names": ["knowledge_search"]})


def test_matrix_direct_rows_include_strictly_attributable_evidence_metadata() -> None:
    evidence = _annotate_real_evidence({}, "candidate-sha", "agent", ["observed a real run"])
    assert evidence == {
        "candidate_commit": "candidate-sha",
        "scenario": "agent",
        "real_execution": True,
        "result": "passed",
        "observed_steps": ["observed a real run"],
    }


def test_matrix_resume_reuses_only_current_candidate_real_passed_evidence(tmp_path: Path) -> None:
    evidence_path = tmp_path / "agent.json"
    evidence_path.write_text(
        '{"candidate_commit":"candidate-sha","scenario":"agent","real_execution":true,"result":"passed","observed_steps":["run"]}',
        encoding="utf-8",
    )
    row = {"result": "passed", "evidence": "agent.json"}
    assert _resumable_row(row, evidence_path, "agent", "candidate-sha")
    assert not _resumable_row(row, evidence_path, "agent", "other-candidate")


def test_workflow_probe_pins_a_published_agent_to_the_frozen_revision() -> None:
    class FakeGateway(Gateway):
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict]] = []
            self.resources = iter(("agent-resource", "workflow-resource"))

        def request(self, method: str, path: str, **kwargs: object) -> dict:
            self.calls.append((method, path, kwargs))
            if path.endswith("/knowledge-revisions"):
                return {
                    "items": [
                        {"id": "rev-1", "revision_no": 1, "status": "superseded"},
                        {"id": "rev-2", "revision_no": 2, "status": "published"},
                    ]
                }
            if path == "/api/resources":
                return {"id": next(self.resources)}
            if path.endswith("/publish"):
                return {}
            if path.endswith("/agent-draft") or path.endswith("/workflow-draft"):
                return {}
            if path.endswith("/workflow-runs"):
                return {"run_id": "run-1"}
            if path.endswith("/workflow-runs/run-1"):
                return {
                    "status": "completed",
                    "snapshot": {
                        "run_evidence": {
                            "knowledge_scope": {
                                "logical_selectors": ["kb-1"],
                                "revisions": {
                                    "kb-1": {
                                        "revision_id": "rev-2",
                                        "manifest_hash": "a" * 64,
                                    }
                                },
                            }
                        }
                    },
                }
            raise AssertionError(f"unexpected Gateway request: {method} {path}")

        def request_text(self, method: str, path: str, **kwargs: object) -> str:
            self.calls.append((method, path, kwargs))
            return 'event: action_progress\ndata: {"message":"knowledge_search"}\n\nevent: node_completed\ndata: {"result":"Gate 7 isolated matrix citation marker 8d7d6179. gate7-matrix-marker.txt [citation: x]"}\n\n'

    gateway = FakeGateway()
    result = gateway.run_workflow("kb-1", "dataset-1", "model-1")

    agent_draft = next(kwargs["json"] for method, path, kwargs in gateway.calls if method == "PUT" and path.endswith("/agent-draft"))
    assert agent_draft["knowledge_dependencies"][0]["revision_id"] == "rev-2"
    agent_slug = agent_draft["config"]["name"]
    workflow_draft = next(kwargs["json"]["content"] for method, path, kwargs in gateway.calls if method == "PUT" and path.endswith("/workflow-draft"))
    assert workflow_draft["nodes"][0]["action"]["name"] == agent_slug
    action = workflow_draft["nodes"][0]["action"]
    assert action["params"]["max_turns"] == 10
    assert "list_uploaded_files" in action["params"]["prompt"]
    assert result["frozen_knowledge_revision"]["revision_id"] == "rev-2"
    assert result["knowledge_tool_event_count"] == 1
