"""Regression tests for canonical run selection metadata."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.gateway.services import _canonical_selection_metadata


@pytest.mark.asyncio
async def test_selection_metadata_keeps_knowledge_revision_without_resource_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = SimpleNamespace(id="agent-1", type="agent", display_name="Agent", slug="agent")
    knowledge_base = SimpleNamespace(id="kb-1", type="knowledge_base", display_name="KB", slug="kb")
    agent_version = SimpleNamespace(version=1, content_hash="agent-hash")
    agent_snapshot = SimpleNamespace(
        resource_id="agent-1",
        version=1,
        content_hash="agent-hash",
        selection_role="root",
        knowledge_revision_id=None,
        knowledge_revision_no=None,
        manifest_hash=None,
        authz_revision=1,
    )
    knowledge_snapshot = SimpleNamespace(
        resource_id="kb-1",
        version=1,
        content_hash="manifest-hash",
        selection_role="resolved",
        knowledge_revision_id="revision-1",
        knowledge_revision_no=1,
        manifest_hash="manifest-hash",
        authz_revision=5,
    )

    class _Result:
        def all(self):
            return [
                (agent, agent_version, agent_snapshot),
                (knowledge_base, None, knowledge_snapshot),
            ]

    class _Session:
        async def execute(self, _query):
            return _Result()

    class _SessionContext:
        async def __aenter__(self):
            return _Session()

        async def __aexit__(self, *_exc):
            return False

    def _factory():
        return _SessionContext()

    monkeypatch.setattr("deerflow.persistence.engine.get_session_factory", lambda: _factory)

    result = await _canonical_selection_metadata("run-1", "agent-1", {})

    snapshots = result["selection_snapshot"]["resource_snapshots"]
    assert [item["resource_id"] for item in snapshots] == ["agent-1", "kb-1"]
    assert snapshots[1]["knowledge_revision_id"] == "revision-1"
    assert snapshots[1]["knowledge_manifest_hash"] == "manifest-hash"
