"""Canonical run skill projection acceptance over the real gateway app.

Upgrade regression §24-D: an Agent whose catalog dependency closure contains
a Skill must get a run-scoped, frozen, read-only skill view at the managed
``/mnt/skills`` mount (PATCH-012 resolver), built from the snapshot's
UUID/version/hash — not from the mutable skill directory.
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

OWNER_EMAIL = "skill-agent-owner@example.com"
CALLER_EMAIL = "skill-agent-caller@example.com"
AGENT_SLUG = "skill-projection-agent"
SKILL_SLUG = "projection-skill"
AGENT_SOUL = "You use the projection skill to answer."

SKILL_FILES = {
    "SKILL.md": "---\nname: projection-skill\ndescription: Frozen projection skill\n---\n\n# Projection skill\n",
    "references/notes.md": "Frozen reference notes for the run.\n",
}


def _seed_shared_agent_with_skill(home: Path, owner_id: str) -> tuple[str, str]:
    """Publish an Agent plus a Skill dependency and make both public."""
    import asyncio

    agent_source = home / "staging" / AGENT_SLUG
    agent_source.mkdir(parents=True, exist_ok=True)
    (agent_source / "SOUL.md").write_text(AGENT_SOUL, encoding="utf-8")
    (agent_source / "config.yaml").write_text("model: fake-test-model\n", encoding="utf-8")

    skill_source = home / "staging" / SKILL_SLUG
    for name, content in SKILL_FILES.items():
        path = skill_source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    from app.agentplatform.resources.publisher import ResourcePublisher
    from app.agentplatform.resources.service import (
        ResourceAction,
        ResourceActor,
        ResourceService,
    )
    from app.agentplatform.resources.storage import ResourceStorage
    from deerflow.config.paths import get_paths
    from deerflow.persistence.engine import get_session_factory

    async def _seed() -> tuple[str, str]:
        actor = ResourceActor(
            user_id=owner_id,
            department_id=None,
            role="user",
            permissions=frozenset({ResourceAction.READ, ResourceAction.WRITE, ResourceAction.USE}),
            tool_groups=None,
        )
        storage = ResourceStorage(str(get_paths().base_dir))
        session_factory = get_session_factory()
        async with session_factory() as session:
            service = ResourceService(session, actor)
            publisher = ResourcePublisher(service, storage)

            skill = await service.create_resource(
                resource_type="skill",
                slug=SKILL_SLUG,
                display_name="Projection Skill",
                storage_kind="filesystem",
            )
            await publisher.save_filesystem_draft(skill.id, source_dir=skill_source, expected_revision=0)
            await publisher.publish_filesystem(skill.id, expected_draft_revision=1, scan_result={})

            agent = await service.create_resource(
                resource_type="agent",
                slug=AGENT_SLUG,
                display_name="Skill Projection Agent",
                storage_kind="filesystem",
            )
            await publisher.save_filesystem_draft(agent.id, source_dir=agent_source, expected_revision=0)
            await publisher.publish_filesystem(agent.id, expected_draft_revision=1, scan_result={})
            await service.replace_dependencies(agent.id, [skill.id])

            # Test shortcut mirroring tests/unit/gateway/test_canonical_agent_run.py:
            # visibility expansion normally requires an approval workflow.
            skill.visibility = "public"
            agent.visibility = "public"
            await session.commit()
            return agent.id, skill.id

    return asyncio.run(_seed())


def _drain(response) -> str:
    chunks: list[str] = []
    for chunk in response.iter_text():
        chunks.append(chunk)
        if "event: end" in chunk:
            break
    return "".join(chunks)


def _parse_sse(transcript: str) -> list[dict]:
    events: list[dict] = []
    for block in transcript.split("\n\n"):
        lines = [line for line in block.splitlines() if line.startswith("data: ")]
        name = next((line for line in block.splitlines() if line.startswith("event: ")), None)
        if name and lines:
            events.append(
                {
                    "event": name.removeprefix("event: ").strip(),
                    "data": json.loads(lines[0].removeprefix("data: ")),
                }
            )
    return events


def test_canonical_run_projects_frozen_skill_view_only(
    isolated_app,
    isolated_deer_flow_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_model = FakeToolCallingModel(responses=[AIMessage(content="projection run done")])

    with (
        patch("deerflow.agents.lead_agent.agent.create_chat_model", new=lambda *args, **kwargs: fake_model),
        TestClient(isolated_app) as client,
    ):
        register_user(client, email=OWNER_EMAIL)
        owner_id = auth_user_id(client)
        agent_id, skill_id = _seed_shared_agent_with_skill(isolated_deer_flow_home, owner_id)

        caller_csrf = register_user(client, email=CALLER_EMAIL)
        thread_id = create_thread(client, caller_csrf)

        with client.stream(
            "POST",
            f"/api/threads/{thread_id}/runs/stream",
            json={
                "input": {"messages": [{"role": "user", "content": "Use the skill."}]},
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
        run_id = next(event["data"]["run_id"] for event in events if event["event"] == "metadata")

        run = client.get(
            f"/api/threads/{thread_id}/runs/{run_id}",
            headers={"X-CSRF-Token": caller_csrf},
        )
        assert run.status_code == 200, run.text
        assert run.json()["status"] == "success", run.text

        # The run-scoped skill view exists and mirrors the frozen skill copy.
        view_root = isolated_deer_flow_home / "resources" / "run-skill-views" / run_id
        assert view_root.is_dir(), f"missing run skill view at {view_root}"
        skill_dirs = list((view_root / "custom").iterdir()) if (view_root / "custom").is_dir() else []
        assert [path.name for path in skill_dirs] == [skill_id], "the view must contain exactly the frozen dependency skill"
        projected = {str(path.relative_to(view_root / "custom" / skill_id)): path.read_text(encoding="utf-8") for path in (view_root / "custom" / skill_id).rglob("*") if path.is_file()}
        assert projected.get("SKILL.md") == SKILL_FILES["SKILL.md"]
        assert projected.get("references/notes.md") == SKILL_FILES["references/notes.md"]
        del agent_id
