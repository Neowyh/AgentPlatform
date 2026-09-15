from __future__ import annotations

import pytest

from tests.gate7_acceptance import validate_gate7_matrix, validate_gate7_source_chain


def test_gate7_source_chain_requires_every_persisted_hop() -> None:
    artifact = {
        "run_id": "run-1",
        "tool_calls": [{"id": "call-1", "name": "knowledge_search"}],
        "knowledge_base": {"id": "kb-1"},
        "revision": {"id": "rev-1", "number": 1},
        "document": {"id": "doc-1"},
        "chunk": {"id": "chunk-1", "content": "known source"},
        "receipt": {"run_id": "run-1", "tool_call_id": "call-1", "chunk_id": "chunk-1"},
    }

    validate_gate7_source_chain(artifact, expected_run_id="run-1")


def test_gate7_source_chain_rejects_a_receipt_without_tool_call() -> None:
    artifact = {"run_id": "run-1", "receipt": {"run_id": "run-1", "chunk_id": "chunk-1"}}

    with pytest.raises(AssertionError, match="tool call"):
        validate_gate7_source_chain(artifact, expected_run_id="run-1")


def test_gate7_matrix_requires_real_evidence_for_each_scenario() -> None:
    matrix = {
        "agent": {"result": "passed", "evidence": "agent.json", "provider": "ragflow", "model": "model", "browser": "chromium"},
        "workflow_subagent": {"result": "passed", "evidence": "workflow.json", "provider": "ragflow", "model": "model", "browser": "chromium"},
    }

    with pytest.raises(AssertionError, match="two_users_two_kbs"):
        validate_gate7_matrix(matrix)
