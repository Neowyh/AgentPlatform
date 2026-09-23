"""Direct LangGraph Run preparation for UUID-addressed canonical Agents."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.agentplatform.audit_model  # noqa: F401 - register audit_logs
import app.agentplatform.rbac_models  # noqa: F401 - register users_ext for audit FK
import deerflow.persistence.models  # noqa: F401
from app.agentplatform.audit_model import AuditLog
from app.agentplatform.rbac_models import UserModel
from app.agentplatform.resource_models import Resource, RunResourceSnapshot
from app.agentplatform.resources.publisher import ResourcePublisher
from app.agentplatform.resources.runtime import CanonicalResourceLoader, ResourceRuntimeError
from app.agentplatform.resources.service import ResourceAction, ResourceActor, ResourceService
from app.agentplatform.resources.storage import ResourceStorage
from app.gateway.canonical_agent_run_preparation import prepare_canonical_agent_run
from app.gateway.routers.assistants_compat import _list_canonical_assistants
from deerflow.persistence.base import Base


@pytest_asyncio.fixture
async def session_factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'canonical-run.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _actor(user_id: str) -> ResourceActor:
    return ResourceActor(
        user_id=user_id,
        department_id="dept-a",
        role="user",
        permissions=frozenset({ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE}),
    )


@pytest.mark.asyncio
async def test_prepare_canonical_agent_run_freezes_visible_version_and_hides_private_resource(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visible_run_id = str(uuid.uuid4())
    hidden_run_id = str(uuid.uuid4())
    source = tmp_path / "agent-source"
    source.mkdir()
    (source / "config.yaml").write_text("name: canonical-agent\n")
    (source / "SOUL.md").write_text("frozen soul\n")
    async with session_factory() as session:
        session.add_all(
            [
                UserModel(id="owner", username="owner@test.com", role="user", department_id=None, disabled=False),
                UserModel(id="runner", username="runner@test.com", role="user", department_id=None, disabled=False),
            ]
        )
        await session.commit()
        service = ResourceService(session, _actor("owner"))
        resource = await service.create_resource(
            resource_type="agent",
            slug="canonical-agent",
            display_name="Canonical Agent",
            storage_kind="filesystem",
        )
        await session.commit()
        publisher = ResourcePublisher(service, ResourceStorage(tmp_path))
        draft = await publisher.save_filesystem_draft(resource.id, source_dir=source, expected_revision=0)
        await publisher.publish_filesystem(resource.id, expected_draft_revision=draft.revision, scan_result={})
        resource.visibility = "public"
        await session.commit()
        resource_id = resource.id

    monkeypatch.setattr("deerflow.persistence.engine.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("app.gateway.audit.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("deerflow.config.paths.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    request = SimpleNamespace(state=SimpleNamespace(user=SimpleNamespace(id="runner")))

    factory = await prepare_canonical_agent_run(resource_id, request, visible_run_id)

    assert callable(factory)
    assistants = await _list_canonical_assistants(request)
    assert [(item.assistant_id, item.name) for item in assistants] == [(resource_id, "Canonical Agent")]
    async with session_factory() as session:
        snapshots = list((await session.execute(select(RunResourceSnapshot).where(RunResourceSnapshot.run_id == visible_run_id))).scalars())
        assert [(item.resource_id, item.version) for item in snapshots] == [(resource_id, 1)]

    rejected_run_id = str(uuid.uuid4())
    with pytest.raises(HTTPException) as rejected_info:
        await prepare_canonical_agent_run(
            resource_id,
            request,
            rejected_run_id,
            preferred_skill="academic-paper-review",
            diagnostic_context={
                "task_id": "academic-paper-review",
                "context_source": "scenario_binding",
            },
            thread_id="thread-123",
        )
    assert rejected_info.value.status_code == 409
    assert rejected_info.value.detail == {
        "code": "skill_outside_agent_closure",
        "message": "The selected Skill is not available to the current Expert.",
        "agent": {"resource_id": resource_id, "slug": "canonical-agent"},
        "requested_skill": "academic-paper-review",
        "available_skills": [],
        "context_source": "scenario_binding",
    }
    async with session_factory() as session:
        audit = (await session.execute(select(AuditLog).where(AuditLog.action == "run_preparation_rejected"))).scalar_one()
        assert audit.detail is not None
        assert '"thread_id": "thread-123"' in audit.detail
        assert '"run_attempt_id": "' in audit.detail
        assert '"task_id": "academic-paper-review"' in audit.detail
        assert "message" not in audit.detail

    original_skill_loader = CanonicalResourceLoader.load_agent_skill_definitions

    async def fail_skill_loading(*_args: object, **_kwargs: object) -> list[object]:
        raise ResourceRuntimeError("skill view preparation failed")

    monkeypatch.setattr(CanonicalResourceLoader, "load_agent_skill_definitions", fail_skill_loading)
    with pytest.raises(HTTPException) as failed_info:
        await prepare_canonical_agent_run(resource_id, request, hidden_run_id)
    assert failed_info.value.status_code == 409
    async with session_factory() as session:
        failed = list((await session.execute(select(RunResourceSnapshot).where(RunResourceSnapshot.run_id == hidden_run_id))).scalars())
        assert failed == []
    monkeypatch.setattr(
        CanonicalResourceLoader,
        "load_agent_skill_definitions",
        original_skill_loader,
    )

    async with session_factory() as session:
        resource = await session.get(Resource, resource_id)
        assert resource is not None
        resource.visibility = "private"
        await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await prepare_canonical_agent_run(resource_id, request, hidden_run_id)
    assert exc_info.value.status_code == 404
    async with session_factory() as session:
        hidden = list((await session.execute(select(RunResourceSnapshot).where(RunResourceSnapshot.run_id == hidden_run_id))).scalars())
        assert hidden == []


@pytest.mark.asyncio
async def test_canonical_mcp_dispatch_nests_tool_arguments_for_local_runtime(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agentplatform_extension.evidence import (
        AuthorizationContext,
        RunEvidenceBinding,
        bind_run_evidence,
        bind_tool_call_evidence,
        current_run_evidence,
    )

    from app.device_control.broker import TaskStatus

    run_id = str(uuid.uuid4())
    source = tmp_path / "mcp-agent-source"
    source.mkdir()
    (source / "config.yaml").write_text("name: canonical-mcp-agent\n")
    (source / "SOUL.md").write_text("read the requested local file\n")
    async with session_factory() as session:
        session.add(
            UserModel(
                id="runner",
                username="runner@test.com",
                role="user",
                department_id=None,
                disabled=False,
            )
        )
        await session.commit()
        service = ResourceService(session, _actor("runner"))
        resource = await service.create_resource(
            resource_type="agent",
            slug="canonical-mcp-agent",
            display_name="Canonical MCP Agent",
            storage_kind="filesystem",
        )
        await session.commit()
        publisher = ResourcePublisher(service, ResourceStorage(tmp_path))
        draft = await publisher.save_filesystem_draft(resource.id, source_dir=source, expected_revision=0)
        await publisher.publish_filesystem(resource.id, expected_draft_revision=draft.revision, scan_result={})
        resource_id = resource.id

    monkeypatch.setattr("deerflow.persistence.engine.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("deerflow.config.paths.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))

    sent = []
    device_receipt = {
        "capability": "local.mcp.fs.read_file",
        "status": "completed",
        "request_hash": "a" * 64,
        "result_hash": "b" * 64,
        "policy_version": "runtime-default",
        "consent_decision": "allow",
        "run_id": run_id,
        "task_id": "task-1",
        "runtime_version": "test",
    }

    class FakeBroker:
        async def send_task(self, **kwargs):
            sent.append(kwargs)
            return SimpleNamespace(
                status=TaskStatus.COMPLETED,
                result={"status": "completed"},
                receipt=device_receipt,
                tool_call_id="call-1",
            )

        def get_task(self, _task_id):
            raise AssertionError("completed task should not be polled")

    monkeypatch.setattr("app.device_control.broker.get_device_broker", lambda: FakeBroker())
    prepared = {}

    def capture_factory(*_args, **kwargs):
        prepared.update(kwargs)
        return lambda *_factory_args, **_factory_kwargs: object()

    monkeypatch.setattr("app.agentplatform.runtime_adapter.build_canonical_agent_factory", capture_factory)
    request = SimpleNamespace(state=SimpleNamespace(user=SimpleNamespace(id="runner")))
    capability = "local.mcp.fs.read_file"
    await prepare_canonical_agent_run(
        resource_id,
        request,
        run_id,
        diagnostic_context={
            "local_device_id": "device-1",
            "local_authorization": {
                key: [capability]
                for key in (
                    "agent_capabilities",
                    "caller_capabilities",
                    "device_capabilities",
                    "local_policy_capabilities",
                    "workflow_capabilities",
                    "platform_capabilities",
                )
            },
        },
    )

    executor = prepared["local_tool_executor"]
    binding = RunEvidenceBinding(
        snapshots=(),
        authorization=AuthorizationContext(
            caller_user_id="runner",
            effective_agent_id=resource_id,
            policy_revision="runtime-default",
        ),
        run_id=run_id,
    )
    with bind_run_evidence(binding), bind_tool_call_evidence("call-1"):
        await executor.sender("device-1", capability, {"path": "marker.txt"})
        evidence = current_run_evidence()

    assert sent[0]["payload_extra"]["arguments"] == {"path": "marker.txt"}
    assert sent[0]["tool_call_id"] == "call-1"
    assert evidence is not None
    local_receipts = [item.get("local_execution_receipt") for item in evidence.tool_receipts if item.get("receipt_kind") == "tool"]
    assert any(item and item.get("capability") == capability and item.get("status") == "completed" and item.get("task_id") == "task-1" for item in local_receipts)
