"""Shared-resource run acceptance over the real gateway app.

Upgrade regression §24-C: a caller must be able to run an owner's published
shared Agent end to end, and every durable evidence projection must bind to
the *caller* — caller principal, caller memory scope — never the owner's
identity or private state. The focused suites cover the projection seams;
this module drives the full HTTP run path.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from _agent_e2e_helpers import FakeToolCallingModel
from _gateway_e2e_env import (
    auth_user_id,
    create_thread,
    register_user,
)
from langchain_core.messages import AIMessage
from starlette.testclient import TestClient

OWNER_EMAIL = "agent-owner@example.com"
CALLER_EMAIL = "agent-caller@example.com"
AGENT_SLUG = "shared-poet-agent"
AGENT_SOUL = "You are a published poet agent shared with the company."


def _seed_shared_agent(home: Path, owner_id: str) -> str:
    """Publish one filesystem Agent owned by *owner_id* and make it public."""
    import asyncio

    source_dir = home / "staging" / AGENT_SLUG
    (source_dir / "skill").mkdir(parents=True, exist_ok=True)
    (source_dir / "SOUL.md").write_text(AGENT_SOUL, encoding="utf-8")
    (source_dir / "config.yaml").write_text(
        "model: fake-test-model\n",
        encoding="utf-8",
    )

    from app.agentplatform.resources.publisher import ResourcePublisher
    from app.agentplatform.resources.service import (
        ResourceAction,
        ResourceActor,
        ResourceService,
    )
    from app.agentplatform.resources.storage import ResourceStorage
    from deerflow.config.paths import get_paths
    from deerflow.persistence.engine import get_session_factory

    async def _seed() -> str:
        actor = ResourceActor(
            user_id=owner_id,
            department_id=None,
            role="user",
            permissions=frozenset({ResourceAction.READ, ResourceAction.WRITE, ResourceAction.USE}),
            tool_groups=None,
        )
        session_factory = get_session_factory()
        async with session_factory() as session:
            service = ResourceService(session, actor)
            publisher = ResourcePublisher(service, ResourceStorage(str(get_paths().base_dir)))
            resource = await service.create_resource(
                resource_type="agent",
                slug=AGENT_SLUG,
                display_name="Shared Poet Agent",
                storage_kind="filesystem",
            )
            await publisher.save_filesystem_draft(
                resource.id,
                source_dir=source_dir,
                expected_revision=0,
            )
            await publisher.publish_filesystem(
                resource.id,
                expected_draft_revision=1,
                scan_result={},
            )
            # Test shortcut mirroring tests/unit/gateway/test_canonical_agent_run.py:
            # visibility expansion normally requires an approval workflow.
            resource.visibility = "public"
            await session.commit()
            return resource.id

    return asyncio.run(_seed())


def _drain(response, *, timeout: float = 20.0) -> str:
    chunks: list[str] = []
    for chunk in response.iter_text():
        chunks.append(chunk)
        if "\r\n\r\n" in chunk and "event: end" in chunk:
            break
    del timeout
    return "".join(chunks)


def _parse_sse(transcript: str) -> list[dict]:
    events: list[dict] = []
    for block in transcript.split("\n\n"):
        lines = [line for line in block.splitlines() if line.startswith("data: ")]
        name = next((line for line in block.splitlines() if line.startswith("event: ")), None)
        if name and lines:
            events.append({
                "event": name.removeprefix("event: ").strip(),
                "data": json.loads(lines[0].removeprefix("data: ")),
            })
    return events


def test_caller_runs_owner_shared_agent_with_caller_scoped_evidence(
    isolated_app,
    isolated_deer_flow_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_model = FakeToolCallingModel(responses=[AIMessage(content="shared run done")])

    with (
        patch("deerflow.agents.lead_agent.agent.create_chat_model", new=lambda *args, **kwargs: fake_model),
        TestClient(isolated_app) as client,
    ):
        register_user(client, email=OWNER_EMAIL)
        owner_id = auth_user_id(client)
        agent_id = _seed_shared_agent(isolated_deer_flow_home, owner_id)

        caller_csrf = register_user(client, email=CALLER_EMAIL)
        caller_id = auth_user_id(client)
        assert caller_id != owner_id
        thread_id = create_thread(client, caller_csrf)

        with client.stream(
            "POST",
            f"/api/threads/{thread_id}/runs/stream",
            json={
                "input": {"messages": [{"role": "user", "content": "Write a haiku."}]},
                "context": {
                    "agent_name": AGENT_SLUG,
                    "thinking_enabled": False,
                    "is_plan_mode": False,
                    "subagent_enabled": False,
                },
            },
            headers={"X-CSRF-Token": caller_csrf},
        ) as stream:
            assert stream.status_code == 200, stream.read().decode()
            transcript = _drain(stream)

        events = _parse_sse(transcript)
        event_names = [event["event"] for event in events]
        assert "metadata" in event_names
        assert "error" not in event_names, transcript
        assert event_names[-1] == "end"

        metadata_event = next(event["data"] for event in events if event["event"] == "metadata")
        run_id = metadata_event["run_id"]

        run = client.get(
            f"/api/threads/{thread_id}/runs/{run_id}",
            headers={"X-CSRF-Token": caller_csrf},
        )
        assert run.status_code == 200, run.text
        assert run.json()["status"] == "success", run.text

        # The run metadata carries the caller-safe evidence projection.
        evidence = (run.json().get("metadata") or {}).get("run_evidence") or {}
        authorization = evidence.get("authorization_context") or {}
        assert authorization.get("caller_user_id") == caller_id, authorization
        assert authorization.get("memory_scope") == caller_id, authorization
        assert authorization.get("effective_agent_id") == agent_id, authorization
        assert owner_id not in json.dumps(authorization), (
            "owner identity must not leak into the caller's evidence envelope"
        )
        snapshot_refs = evidence.get("resource_snapshots") or []
        assert [ref.get("resource_id") for ref in snapshot_refs] == [agent_id]
