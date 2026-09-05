from __future__ import annotations

import pytest
from agentplatform_extension.evidence import AuthorizationContext, ResourceSnapshotRef, build_run_evidence_envelope
from agentplatform_extension.network_policy import NetworkPolicy


def test_run_evidence_envelope_freezes_resource_identity_and_caller_boundary() -> None:
    envelope = build_run_evidence_envelope(
        run_id="run-1",
        thread_id="thread-1",
        snapshots=[
            ResourceSnapshotRef("workflow-1", 3, "a" * 64, "root"),
            {"resource_id": "skill-1", "version": 2, "content_hash": "b" * 64},
        ],
        authorization=AuthorizationContext(
            caller_user_id="caller",
            effective_agent_id="agent-1",
            policy_revision="policy-7",
            allowed_tools=("read_file",),
        ),
        runtime_assembly_fingerprint="assembly-1",
    )

    assert envelope.resource_snapshots == (
        {"resource_id": "workflow-1", "version": 3, "content_hash": "a" * 64, "selection_role": "root"},
        {"resource_id": "skill-1", "version": 2, "content_hash": "b" * 64, "selection_role": "resolved"},
    )
    assert envelope.authorization_context == {
        "caller_user_id": "caller",
        "effective_agent_id": "agent-1",
        "policy_revision": "policy-7",
        "allowed_tools": ["read_file"],
        "memory_scope": "caller",
    }
    assert "credential" not in str(envelope.authorization_context).lower()


def test_evidence_rejects_duplicate_or_invalid_snapshot() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        build_run_evidence_envelope(
            run_id="run-1",
            thread_id="thread-1",
            snapshots=[
                ResourceSnapshotRef("agent-1", 1, "a" * 64),
                ResourceSnapshotRef("agent-1", 2, "b" * 64),
            ],
            authorization=AuthorizationContext("caller", "agent", "policy"),
        )

    with pytest.raises(ValueError, match="SHA-256"):
        ResourceSnapshotRef("agent-1", 1, "not-a-hash")


def test_shared_agent_memory_scope_cannot_be_owner_scoped() -> None:
    with pytest.raises(ValueError, match="caller-scoped"):
        AuthorizationContext("caller", "agent", "policy", memory_scope="owner")


def test_network_policy_defaults_to_intranet_allowlist_and_public_deny() -> None:
    policy = NetworkPolicy(allowed_hosts=("vllm.internal",))

    assert policy.allows("https://vllm.internal/v1")
    assert not policy.allows("https://example.com")
    assert not policy.allows("http://127.0.0.1:8080")
    assert NetworkPolicy(allow_public=True).allows("https://example.com")
