from types import SimpleNamespace

from agentplatform_extension.evidence import current_run_evidence, record_tool_receipt

from app.agentplatform.workflows.v2.store import _canonical_run_evidence, _merge_recovery_snapshot
from app.workflow_worker import _workflow_run_evidence_context


def test_canonical_workflow_evidence_is_caller_scoped_and_immutable() -> None:
    snapshots = [
        SimpleNamespace(
            resource_id="workflow-1",
            version=3,
            content_hash="a" * 64,
            selection_role="root",
            authz_revision=7,
            knowledge_revision_id=None,
        ),
        SimpleNamespace(
            resource_id="agent-1",
            version=2,
            content_hash="b" * 64,
            selection_role="resolved",
            authz_revision=8,
            knowledge_revision_id="revision-9",
            knowledge_revision_no=9,
            manifest_hash="c" * 64,
        ),
    ]
    actor = SimpleNamespace(user_id="caller", tool_groups=frozenset({"read", "write"}))

    evidence = _canonical_run_evidence(snapshots, actor, "workflow-1")

    assert [item["resource_id"] for item in evidence["resource_snapshots"]] == ["workflow-1", "agent-1"]
    assert evidence["authorization_context"] == {
        "caller_user_id": "caller",
        "effective_agent_id": "workflow-1",
        "policy_revision": "8",
        "allowed_tools": ["read", "write"],
        "memory_scope": "caller",
    }
    assert len(evidence["runtime_assembly_fingerprint"]) == 64
    assert "credential" not in repr(evidence).lower()


def test_recovery_snapshot_update_preserves_run_evidence() -> None:
    evidence = {"resource_snapshots": [{"resource_id": "workflow-1", "version": 1}]}

    merged = _merge_recovery_snapshot({"run_evidence": evidence}, {"state": {"step": "done"}})

    assert merged == {"state": {"step": "done"}, "run_evidence": evidence}


def test_workflow_worker_binds_persisted_evidence_for_runtime_execution() -> None:
    run = SimpleNamespace(
        created_by="caller",
        workflow_name="workflow-slug",
        workflow_resource_id="workflow-1",
        snapshot={
            "run_evidence": {
                "resource_snapshots": [
                    {
                        "resource_id": "workflow-1",
                        "version": 1,
                        "content_hash": "a" * 64,
                        "selection_role": "root",
                    }
                ],
                "authorization_context": {
                    "caller_user_id": "caller",
                    "effective_agent_id": "workflow-1",
                    "policy_revision": "1",
                    "allowed_tools": ["read"],
                    "memory_scope": "caller",
                },
                "policy_revision": "1",
            }
        },
    )

    assert current_run_evidence() is None
    with _workflow_run_evidence_context(run):
        record_tool_receipt({"tool_name": "read_file", "status": "success"})
        binding = current_run_evidence()
        assert binding is not None
        assert binding.authorization.caller_user_id == "caller"
        assert binding.snapshots[0]["resource_id"] == "workflow-1"
        assert binding.tool_receipts == ({"tool_name": "read_file", "status": "success"},)
    assert current_run_evidence() is None
