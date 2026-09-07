from __future__ import annotations

import pytest
from agentplatform_extension import install
from agentplatform_extension.evidence import (
    AuthorizationContext,
    EvidenceLifecycleContributor,
    ResourceSnapshotRef,
    RunEvidenceBinding,
    bind_run_evidence,
    build_run_evidence_envelope,
    current_run_evidence,
    record_subagent_verification,
    record_tool_receipt,
)
from agentplatform_extension.network_policy import NetworkPolicy
from deerflow_extension_api import ExtensionData, RunEvidenceEnvelope, TaskInfo, TaskOutcome

from deerflow.extensions.registry import ExtensionRegistry


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


def test_run_evidence_binding_exposes_only_caller_safe_metadata_projection() -> None:
    binding = RunEvidenceBinding(
        snapshots=[ResourceSnapshotRef("agent-1", 2, "a" * 64, "root")],
        authorization=AuthorizationContext("caller-1", "agent-1", "policy-2", memory_scope="caller-1"),
        runtime_assembly_fingerprint="b" * 64,
    )

    projection = binding.as_mapping()

    assert projection["resource_snapshots"] == [
        {
            "resource_id": "agent-1",
            "version": 2,
            "content_hash": "a" * 64,
            "selection_role": "root",
        }
    ]
    assert projection["authorization_context"]["memory_scope"] == "caller-1"
    assert "owner_credential" not in projection


def test_run_evidence_binding_collects_runtime_receipts() -> None:
    binding = RunEvidenceBinding(
        snapshots=[ResourceSnapshotRef("agent-1", 2, "a" * 64, "root")],
        authorization=AuthorizationContext("caller-1", "agent-1", "policy-2"),
    )

    with bind_run_evidence(binding):
        record_tool_receipt({"tool_name": "read_file", "status": "success"})
        record_subagent_verification({"task_id": "task-1", "verdict": "VERIFIED"})
        projection = current_run_evidence().as_mapping()

    assert projection["tool_receipts"] == [{"tool_name": "read_file", "status": "success"}]
    assert projection["subagent_verification"] == [{"task_id": "task-1", "verdict": "VERIFIED"}]


def test_network_policy_defaults_to_intranet_allowlist_and_public_deny() -> None:
    policy = NetworkPolicy(allowed_hosts=("vllm.internal",))

    assert policy.allows("https://vllm.internal/v1")
    assert not policy.allows("https://example.com")
    assert not policy.allows("http://127.0.0.1:8080")
    assert NetworkPolicy(allow_public=True).allows("https://example.com")


@pytest.mark.asyncio
async def test_evidence_lifecycle_contributor_binds_snapshot_and_terminal_outcome() -> None:
    contributor = EvidenceLifecycleContributor(
        snapshots=[ResourceSnapshotRef("agent-1", 2, "a" * 64)],
        authorization=AuthorizationContext("caller", "agent", "policy"),
        runtime_assembly_fingerprint="assembly-1",
    )
    store = ExtensionData("task-1")
    info = TaskInfo(task_id="task-1", run_id="run-1", thread_id="thread-1", kind="lead")

    await contributor.on_task_start(ExtensionData("app"), store, info)
    started = store.get(RunEvidenceEnvelope)
    assert started is not None
    assert started.resource_snapshots[0]["version"] == 2
    assert started.authorization_context["caller_user_id"] == "caller"

    await contributor.on_task_stop(ExtensionData("app"), store, info, TaskOutcome.COMPLETED)
    stopped = store.get(RunEvidenceEnvelope)
    assert stopped is not None and stopped.outcome is TaskOutcome.COMPLETED


@pytest.mark.asyncio
async def test_evidence_lifecycle_publishes_collected_receipts() -> None:
    contributor = EvidenceLifecycleContributor(
        snapshots=[ResourceSnapshotRef("agent-1", 2, "a" * 64)],
        authorization=AuthorizationContext("caller", "agent", "policy"),
    )
    store = ExtensionData("task-receipts")
    info = TaskInfo(task_id="task-receipts", run_id="run-1", thread_id="thread-1", kind="lead")
    binding = RunEvidenceBinding(
        snapshots=[ResourceSnapshotRef("agent-1", 2, "a" * 64)],
        authorization=AuthorizationContext("caller", "agent", "policy"),
    )

    with bind_run_evidence(binding):
        await contributor.on_task_start(ExtensionData("app"), store, info)
        record_tool_receipt({"tool_name": "write_file", "status": "success"})
        await contributor.on_task_stop(ExtensionData("app"), store, info, TaskOutcome.COMPLETED)

    envelope = store.get(RunEvidenceEnvelope)
    assert envelope is not None
    assert envelope.tool_receipts == ({"tool_name": "write_file", "status": "success"},)


def test_install_registers_boundary_only_with_explicit_authorization() -> None:
    empty = ExtensionRegistry()
    install(empty, {})
    assert not empty.build().has_task_lifecycle

    configured = ExtensionRegistry()
    with configured.attributed_to("agentplatform:install"):
        install(
            configured,
            {
                "authorization": {
                    "caller_user_id": "caller",
                    "effective_agent_id": "agent",
                    "policy_revision": "policy",
                },
                "resource_snapshots": [],
            },
        )
    loaded = configured.build()
    assert loaded.has_task_lifecycle


@pytest.mark.asyncio
async def test_shared_agent_install_projects_caller_permissions_without_owner_state() -> None:
    registry = ExtensionRegistry()
    with registry.attributed_to("agentplatform:install"):
        install(
            registry,
            {
                "authorization": {
                    "caller_user_id": "caller",
                    "effective_agent_id": "shared-agent",
                    "policy_revision": "policy-2",
                    "allowed_tools": ["read_file"],
                    "memory_scope": "caller",
                    "owner_user_id": "owner",
                    "owner_credential": "must-not-cross-runtime-boundary",
                    "owner_memory_scope": "owner",
                },
            },
        )

    contributor = registry.build().task_lifecycle[0][1]
    store = ExtensionData("task-1")
    info = TaskInfo(task_id="task-1", run_id="run-1", thread_id="thread-1", kind="lead")

    await contributor.on_task_start(ExtensionData("app"), store, info)
    envelope = store.get(RunEvidenceEnvelope)
    assert envelope is not None
    assert envelope.authorization_context == {
        "caller_user_id": "caller",
        "effective_agent_id": "shared-agent",
        "policy_revision": "policy-2",
        "allowed_tools": ["read_file"],
        "memory_scope": "caller",
    }
    assert "owner" not in str(envelope.authorization_context)
    assert "credential" not in str(envelope.authorization_context).lower()


@pytest.mark.asyncio
async def test_dynamic_install_uses_the_run_bound_snapshot_and_caller_context() -> None:
    registry = ExtensionRegistry()
    with registry.attributed_to("agentplatform:install"):
        install(registry, {"dynamic_context": True})

    contributor = registry.build().task_lifecycle[0][1]
    store = ExtensionData("task-1")
    info = TaskInfo(task_id="task-1", run_id="run-1", thread_id="thread-1", kind="lead")
    binding = RunEvidenceBinding(
        snapshots=[ResourceSnapshotRef("agent-1", 7, "a" * 64, "root")],
        authorization=AuthorizationContext(
            "caller",
            "agent-1",
            "resource-authz-3",
            allowed_tools=("read_file",),
        ),
        runtime_assembly_fingerprint="assembly-7",
    )

    with bind_run_evidence(binding):
        await contributor.on_task_start(ExtensionData("app"), store, info)

    envelope = store.get(RunEvidenceEnvelope)
    assert envelope is not None
    assert envelope.resource_snapshots[0]["version"] == 7
    assert envelope.authorization_context["caller_user_id"] == "caller"
    assert envelope.runtime_assembly_fingerprint == "assembly-7"
