"""Validation helpers for artifacts produced by the Gate 7 real harness."""

from __future__ import annotations

from collections.abc import Mapping

_MATRIX_SCENARIOS = (
    "agent",
    "workflow_subagent",
    "two_users_two_kbs",
    "revoked_access",
    "revision_freeze_provider_outage",
    "empty_hit",
    "truncated",
    "retry",
    "duplicate",
    "archive_failure",
    "forged_citation",
    "history_without_receipt",
    "mixed_web",
    "streaming",
    "loading_error_restricted",
    "keyboard",
)


def validate_gate7_source_chain(artifact: Mapping[str, object], *, expected_run_id: str) -> None:
    """Assert that a real-run artifact contains the complete source chain."""
    _equal(artifact.get("run_id"), expected_run_id, "run")
    tool_calls = artifact.get("tool_calls")
    assert isinstance(tool_calls, list) and tool_calls, "missing tool call"
    tool_call_id = _required_mapping_value(tool_calls[0], "id", "tool call")
    assert _required_mapping_value(tool_calls[0], "name", "tool call") == "knowledge_search"
    knowledge_base = _required_mapping(artifact, "knowledge_base")
    revision = _required_mapping(artifact, "revision")
    document = _required_mapping(artifact, "document")
    chunk = _required_mapping(artifact, "chunk")
    receipt = _required_mapping(artifact, "receipt")
    for value, label in ((knowledge_base, "knowledge base"), (revision, "revision"), (document, "document"), (chunk, "chunk")):
        _required_mapping_value(value, "id", label)
    _required_mapping_value(revision, "number", "revision")
    _required_mapping_value(chunk, "content", "chunk")

    _equal(receipt.get("run_id"), expected_run_id, "receipt run")
    _equal(receipt.get("tool_call_id"), tool_call_id, "receipt tool call")
    _equal(receipt.get("chunk_id"), _required_mapping_value(artifact["chunk"], "id", "chunk"), "receipt chunk")


def validate_gate7_matrix(matrix: Mapping[str, object]) -> None:
    """Require a passing, attributable artifact for every Gate 7 scenario."""
    for scenario in _MATRIX_SCENARIOS:
        entry = matrix.get(scenario)
        assert isinstance(entry, Mapping), f"missing {scenario}"
        assert entry.get("result") == "passed", f"{scenario} is not passed"
        assert entry.get("evidence"), f"{scenario} has no evidence artifact"
        for field in ("provider", "model", "browser"):
            assert entry.get(field), f"{scenario} has no {field} record"


def _required_mapping_value(value: object, key: str, label: str) -> object:
    assert isinstance(value, Mapping) and value.get(key), f"missing {label} {key}"
    return value[key]


def _required_mapping(artifact: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = artifact.get(key)
    assert isinstance(value, Mapping), f"missing {key}"
    return value


def _equal(actual: object, expected: object, label: str) -> None:
    assert actual == expected, f"{label} does not match expected value"
