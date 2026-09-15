"""Workflow v2 runs consume revision-frozen knowledge scopes (M4 ticket 03)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.agentplatform.resource_models import RunResourceSnapshot
from app.agentplatform.resources.service import ResourceAction, ResourceActor
from app.agentplatform.workflows.v2.store import _canonical_run_evidence, _frozen_knowledge_scope
from deerflow.persistence.models.workflow_v2 import WorkflowV2RunRow


def _actor() -> ResourceActor:
    return ResourceActor(
        user_id="caller",
        department_id=None,
        role="user",
        permissions=frozenset({ResourceAction.READ, ResourceAction.USE}),
    )


def _kb_snapshot(run_id: str, resource_id: str, *, revision_no: int, dataset_id: str) -> RunResourceSnapshot:
    return RunResourceSnapshot(
        id=f"{run_id}-{resource_id}",
        run_id=run_id,
        root_resource_id="workflow-1",
        resource_id=resource_id,
        version=1,
        content_hash="a" * 64,
        authz_revision=1,
        selection_role="resolved",
        knowledge_revision_id=f"revision-{revision_no}",
        knowledge_revision_no=revision_no,
        manifest_hash=f"{revision_no}" * 64,
        provider_type="ragflow",
        provider_dataset_id=dataset_id,
        retrieval_profile_json={"top_k": 6},
        embedding_profile_json={"model": "bge-m3"},
    )


def _agent_snapshot(run_id: str) -> RunResourceSnapshot:
    return RunResourceSnapshot(
        id=f"{run_id}-workflow-1",
        run_id=run_id,
        root_resource_id="workflow-1",
        resource_id="workflow-1",
        version=1,
        content_hash="b" * 64,
        authz_revision=1,
        selection_role="root",
    )


@pytest.mark.asyncio
async def test_frozen_scope_binds_logical_kb_to_revision_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshots = [
        _agent_snapshot("run-1"),
        _kb_snapshot("run-1", "kb-1", revision_no=1, dataset_id="published-dataset-1"),
    ]

    monkeypatch.setattr(
        "deerflow.config.get_app_config",
        lambda: SimpleNamespace(get_tool_config=lambda _name: SimpleNamespace(datasets=None)),
    )
    scope = await _frozen_knowledge_scope(MagicMock(), snapshots, _actor())

    assert scope == {"kb-1": "published-dataset-1"}


@pytest.mark.asyncio
async def test_frozen_scope_ignores_snapshots_without_revisions() -> None:
    snapshots = [_agent_snapshot("run-1")]

    scope = await _frozen_knowledge_scope(MagicMock(), snapshots, _actor())

    assert scope == {}


def test_run_evidence_records_revision_identities() -> None:
    snapshots = [
        _agent_snapshot("run-1"),
        _kb_snapshot("run-1", "kb-1", revision_no=2, dataset_id="published-dataset-2"),
    ]

    evidence = _canonical_run_evidence(snapshots, _actor(), "workflow-1", {"kb-1": "published-dataset-2"})

    knowledge_scope = evidence["knowledge_scope"]
    assert knowledge_scope["bindings"] == {"kb-1": "published-dataset-2"}
    assert knowledge_scope["revisions"] == {
        "kb-1": {
            "revision_id": "revision-2",
            "revision_no": 2,
            "manifest_hash": "2" * 64,
            "retrieval_profile": {"top_k": 6},
            "embedding_profile": {"model": "bge-m3"},
        }
    }


def test_run_payload_hides_provider_bindings_but_keeps_revision_identities() -> None:
    from app.gateway.routers.resources import _run_payload

    run = WorkflowV2RunRow(
        run_id="run-1",
        workflow_name="flow",
        workflow_resource_id="workflow-1",
        definition_version=1,
        checkpoint_thread_id="wf-run-1",
        status="queued",
        snapshot={
            "run_evidence": {
                "knowledge_scope": {
                    "bindings": {"kb-1": "published-dataset-2"},
                    "logical_selectors": ["kb-1"],
                    "revisions": {"kb-1": {"revision_id": "revision-2", "revision_no": 2, "manifest_hash": "2" * 64}},
                }
            }
        },
    )

    payload = _run_payload(run, "flow")
    scope = payload["snapshot"]["run_evidence"]["knowledge_scope"]
    assert "bindings" not in scope
    assert scope["logical_selectors"] == ["kb-1"]
    assert scope["revisions"]["kb-1"]["revision_no"] == 2
