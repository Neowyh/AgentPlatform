from agentplatform_extension.evidence import (
    AuthorizationContext,
    RunEvidenceBinding,
    RuntimeEvidenceHooks,
    bind_run_evidence,
    current_run_evidence,
)

from deerflow.tools.builtins.task_tool import _record_delegated_retrieval_evidence, _record_run_evidence_verification


def test_missing_subagent_receipts_are_recorded_as_unverified() -> None:
    binding = RunEvidenceBinding(
        snapshots=(),
        authorization=AuthorizationContext("caller", "agent", "policy"),
    )

    with bind_run_evidence(binding):
        _record_run_evidence_verification(evidence_hooks=RuntimeEvidenceHooks(), task_id="task-1", receipts=None, verdict=None)
        verification = current_run_evidence().subagent_verification[0]

    assert verification["status"] == "UNVERIFIED"
    assert verification["receipt_count"] == 0


def test_cited_subagent_receipts_are_recorded_as_verified() -> None:
    binding = RunEvidenceBinding(
        snapshots=(),
        authorization=AuthorizationContext("caller", "agent", "policy"),
    )

    with bind_run_evidence(binding):
        _record_run_evidence_verification(
            evidence_hooks=RuntimeEvidenceHooks(),
            task_id="task-2",
            receipts=[{"id": "r1", "tool_name": "write_file"}],
            verdict={"citation_resolved": True},
        )
        verification = current_run_evidence().subagent_verification[0]

    assert verification["status"] == "VERIFIED"
    assert verification["receipt_count"] == 1


def test_missing_delegated_retrieval_receipts_are_recorded_as_unavailable() -> None:
    binding = RunEvidenceBinding(
        snapshots=(),
        authorization=AuthorizationContext("caller", "agent", "policy"),
        run_id="run-1",
        knowledge_scope={"bindings": {"docs": "dataset-1"}},
    )

    with bind_run_evidence(binding):
        _record_delegated_retrieval_evidence(
            evidence_hooks=RuntimeEvidenceHooks(),
            parent_tool_call_id="task-call-1",
            child_task_id="child-1",
            agent_id="researcher",
            receipts=None,
        )
        status = current_run_evidence().subagent_verification[0]

    assert status["status"] == "UNAVAILABLE"
    assert status["reason"] == "delegated_retrieval_unavailable"
