"""Contracts for the UUID-first canonical resources facade."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.gateway.routers import resources
from app.gateway.routers.resources import WorkflowRunRequest
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import (
    Resource,
    ResourceVersion,
)
from ideer.persistence.models.user import UserModel, UserRole
from ideer.persistence.models.workflow_v2 import WorkflowV2RunRow
from ideer.resources.service import ResourceAction
from ideer.resources.storage import ResourceStorage


def _user(role: UserRole, *, user_id: str = "user", department_id: str | None = "dept-a") -> UserModel:
    return UserModel(
        id=user_id,
        username=f"{user_id}@test.com",
        role=role,
        department_id=department_id,
        disabled=False,
    )


def _skill_resource(resource_id: str) -> Resource:
    return Resource(
        id=resource_id,
        type="skill",
        slug="demo",
        display_name="Demo",
        owner_id="owner",
        visibility="private",
        lifecycle_status="active",
        latest_version=1,
        draft_revision=0,
        storage_kind="filesystem",
        storage_key=f"skills/{resource_id}",
        system_owned=False,
        authz_revision=0,
    )


def _write_skill_md(
    storage: ResourceStorage,
    resource_id: str,
    frontmatter: str,
    body: str = "",
) -> None:
    source = storage.resources_root / f"skills/{resource_id}/versions/1"
    source.mkdir(parents=True, exist_ok=True)
    (source / "SKILL.md").write_text(f"---\n{frontmatter.rstrip()}\n---\n{body}", encoding="utf-8")


def test_skill_description_prefers_description_zh(tmp_path: Path) -> None:
    storage = ResourceStorage(tmp_path / "runtime")
    _write_skill_md(
        storage,
        "skill-zh",
        "name: demo\ndescription: English description\ndescription_zh: 中文说明\n",
    )

    assert resources._skill_description(_skill_resource("skill-zh"), storage) == "中文说明"


def test_skill_localized_description_is_empty_when_description_zh_is_missing(tmp_path: Path) -> None:
    storage = ResourceStorage(tmp_path / "runtime")
    _write_skill_md(storage, "skill-en", "name: demo\ndescription: English description\n")

    assert resources._skill_description_zh(_skill_resource("skill-en"), storage) is None


def test_skill_description_falls_back_to_english(tmp_path: Path) -> None:
    storage = ResourceStorage(tmp_path / "runtime")
    _write_skill_md(
        storage,
        "skill-en",
        "name: demo\ndescription: English description\n",
    )

    assert resources._skill_description(_skill_resource("skill-en"), storage) == "English description"


def test_skill_description_falls_back_to_skill_body(tmp_path: Path) -> None:
    storage = ResourceStorage(tmp_path / "runtime")
    _write_skill_md(
        storage,
        "skill-body",
        "name: demo\n",
        "# Demo\n\nSummarize documents into concise findings.\n",
    )

    assert resources._skill_description(_skill_resource("skill-body"), storage) == "Summarize documents into concise findings."


def test_skill_description_is_none_for_missing_or_invalid_content(tmp_path: Path) -> None:
    storage = ResourceStorage(tmp_path / "runtime")
    assert resources._skill_description(_skill_resource("skill-missing"), storage) is None
    _write_skill_md(storage, "skill-bad", "not: yaml: [")
    assert resources._skill_description(_skill_resource("skill-bad"), storage) is None
    workflow = _skill_resource("skill-other")
    workflow.type = "workflow"
    assert resources._skill_description(workflow, storage) is None


def test_agent_description_uses_config_then_soul(tmp_path: Path) -> None:
    storage = ResourceStorage(tmp_path / "runtime")
    agent = _skill_resource("expert")
    agent.type = "agent"
    source = storage.resources_root / "agents/expert/versions/1"
    source.mkdir(parents=True)
    (source / "config.yaml").write_text("description: Config summary\n", encoding="utf-8")
    (source / "SOUL.md").write_text("Soul summary\n", encoding="utf-8")
    assert resources._skill_description(agent, storage) == "Config summary"


def test_actor_mapping_separates_read_use_write_and_admin_governance() -> None:
    viewer = resources._resource_actor(_user(UserRole.VIEWER))
    user = resources._resource_actor(_user(UserRole.USER))
    department_admin = resources._resource_actor(_user(UserRole.DEPARTMENT_ADMIN))
    super_admin = resources._resource_actor(_user(UserRole.SUPER_ADMIN))

    assert viewer.permissions == frozenset({ResourceAction.READ})
    assert user.permissions == frozenset({ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE})
    assert ResourceAction.APPROVE in department_admin.permissions
    assert ResourceAction.SUSPEND not in department_admin.permissions
    assert super_admin.permissions == frozenset(ResourceAction)


def test_workflow_run_request_accepts_optional_model_name() -> None:
    request = WorkflowRunRequest(inputs={"topic": "test"}, model_name="model-b")

    assert request.model_name == "model-b"


def test_router_exposes_uuid_first_workflow_lifecycle() -> None:
    routes = {(method, route.path) for route in resources.router.routes for method in route.methods}

    assert ("POST", "/api/resources") in routes
    assert ("GET", "/api/resources/notifications") in routes
    assert ("POST", "/api/resources/import/agent") in routes
    assert ("POST", "/api/resources/import/skill") in routes
    assert ("GET", "/api/resources/{resource_id}") in routes
    assert ("GET", "/api/resources/{resource_id}/published") in routes
    assert ("GET", "/api/resources/{resource_id}/export") in routes
    assert ("GET", "/api/resources/aliases/{resource_type}/{slug}") in routes
    assert ("PUT", "/api/resources/{resource_id}/workflow-draft") in routes
    assert ("PUT", "/api/resources/{resource_id}/agent-draft") in routes
    assert ("PUT", "/api/resources/{resource_id}/skill-draft") in routes
    assert ("PUT", "/api/resources/{resource_id}/archive-draft") in routes
    assert ("POST", "/api/resources/{resource_id}/publish") in routes
    assert ("PUT", "/api/resources/{resource_id}/dependencies") in routes
    assert ("POST", "/api/resources/{resource_id}/fork") in routes
    assert ("POST", "/api/resources/{resource_id}/workflow-runs") in routes
    assert ("POST", "/api/resources/{resource_id}/workflow-runs/with-files") in routes
    assert ("GET", "/api/resources/{resource_id}/workflow-runs") in routes
    assert ("GET", "/api/resources/{resource_id}/workflow-runs/{run_id}") in routes
    assert ("GET", "/api/resources/{resource_id}/workflow-runs/{run_id}/events") in routes
    assert ("GET", "/api/resources/{resource_id}/workflow-runs/{run_id}/artifacts") in routes
    assert ("GET", "/api/resources/{resource_id}/workflow-runs/{run_id}/artifacts/content") in routes
    assert ("GET", "/api/resources/{resource_id}/workflow-runs/{run_id}/record") in routes
    assert ("POST", "/api/resources/{resource_id}/workflow-runs/{run_id}/commands") in routes
    assert ("GET", "/api/resources/admin/visibility-applications") in routes
    assert ("GET", "/api/resources/admin/retention-report") in routes
    assert ("POST", "/api/resources/admin/visibility-applications/{application_id}/review") in routes
    assert ("POST", "/api/resources/{resource_id}/suspend") in routes
    assert ("POST", "/api/resources/{resource_id}/transfer") in routes
    assert ("GET", "/api/resources/{resource_id}/visibility-impact") in routes
    assert ("PUT", "/api/resources/notifications/{notification_id}/read") in routes
    assert ("PUT", "/api/resources/notifications/read-all") in routes


def test_workflow_draft_request_accepts_raw_yaml_for_editor_round_trip() -> None:
    body = resources.WorkflowDraftRequest(
        content="schema_version: 2\nname: review\nnodes:\n  - id: start\n",
        expected_revision=0,
    )

    assert isinstance(body.content, str)


def test_resource_payload_only_marks_active_non_system_owner_as_modifiable() -> None:
    resource = Resource(
        id="resource-id",
        type="workflow",
        slug="review",
        display_name="Review",
        owner_id="owner",
        visibility="private",
        lifecycle_status="active",
        latest_version=1,
        draft_revision=0,
        storage_kind="database",
        storage_key="workflow/resource-id",
        system_owned=False,
        authz_revision=0,
    )

    assert (
        resources._resource_payload(
            resource,
            current_user=_user(UserRole.USER, user_id="owner"),
        )["can_modify"]
        is True
    )
    assert (
        resources._resource_payload(
            resource,
            current_user=_user(UserRole.SUPER_ADMIN, user_id="admin"),
        )["can_modify"]
        is False
    )


@pytest.mark.asyncio
def test_canonical_resume_roles_are_read_from_the_frozen_interrupt_node() -> None:
    run = WorkflowV2RunRow(
        run_id="run-id",
        workflow_name="review",
        workflow_resource_id="resource-id",
        definition_version=2,
        checkpoint_thread_id="thread-id",
        status="paused",
        inputs={},
        snapshot={"interrupt": [{"node_id": "approval"}]},
        created_by="user",
    )
    definition = {"nodes": [{"id": "approval", "type": "interrupt", "roles": ["department_admin"]}]}

    assert resources._required_canonical_resume_roles(run, definition) == {"department_admin"}


@pytest.mark.asyncio
async def test_published_workflow_response_includes_real_yaml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'published.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            UserModel(
                id="owner",
                username="owner@test.com",
                role=UserRole.SUPER_ADMIN,
                disabled=False,
            )
        )
        session.add(
            Resource(
                id="workflow-id",
                type="workflow",
                slug="review",
                display_name="Review",
                owner_id="owner",
                visibility="private",
                lifecycle_status="active",
                latest_version=1,
                draft_revision=0,
                storage_kind="database",
                storage_key="workflows/workflow-id",
                system_owned=False,
                authz_revision=1,
            )
        )
        session.add(
            ResourceVersion(
                id="version-id",
                resource_id="workflow-id",
                version=1,
                content_hash="a" * 64,
                storage_key="workflows/workflow-id/versions/1",
                scan_result={},
                content={"name": "review", "nodes": [{"id": "start"}]},
                created_by="owner",
            )
        )
        await session.commit()

    monkeypatch.setattr(resources, "_factory", lambda: factory)
    monkeypatch.setattr(
        "app.gateway.routers.resources.get_paths",
        lambda: SimpleNamespace(base_dir=tmp_path / "runtime"),
    )

    payload = await resources.get_published_resource(
        "workflow-id",
        version=None,
        current_user=UserModel(
            id="owner",
            username="owner@test.com",
            role=UserRole.SUPER_ADMIN,
            disabled=False,
        ),
    )

    assert payload["resource"]["slug"] == "review"
    assert payload["content"] == {"name": "review", "nodes": [{"id": "start"}]}
    assert yaml.safe_load(payload["yaml_content"]) == payload["content"]
    await engine.dispose()


# --- Canonical run record download ---


def _record_host(tmp_path: Path, run_id: str, created_by: str, ext: str) -> Path:
    from ideer.workflows.v2.file_roots import make_host_resolver, workflow_record_path

    host = make_host_resolver(run_id, created_by)(workflow_record_path(ext))
    assert host is not None, "record virtual path must resolve under the workspace"
    path = Path(host)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class TestCanonicalRunRecordDownload:
    @pytest.fixture
    def client(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.gateway.authz import get_current_rbac_user
        from app.gateway.routers.resources import router as resources_router

        app = FastAPI()
        app.include_router(resources_router)

        async def _stub_user():
            return SimpleNamespace(id="user-1", role="user", department_id=None, username="u@test.com")

        app.dependency_overrides[get_current_rbac_user] = _stub_user

        from ideer.config.paths import Paths

        async def _stub_run(_resource_id: str, _run_id: str, _user) -> SimpleNamespace:
            return SimpleNamespace(run_id="run-1", workflow_resource_id="workflow-id", created_by="user-1", status="completed")

        monkeypatch.setattr(resources, "_get_canonical_run", _stub_run)
        monkeypatch.setattr(
            "ideer.workflows.v2.file_roots.get_paths",
            lambda: Paths(str(tmp_path / "runtime")),
        )
        monkeypatch.setattr("ideer.workflows.v2.file_roots._get_custom_mounts", lambda: [])

        with TestClient(app) as test_client:
            yield test_client

    def test_record_download_rejects_unknown_format(self, client) -> None:
        response = client.get("/api/resources/workflow-id/workflow-runs/run-1/record?format=pdf")
        assert response.status_code == 400

    def test_record_download_is_404_when_not_persisted(self, client, tmp_path: Path) -> None:
        response = client.get("/api/resources/workflow-id/workflow-runs/run-1/record?format=jsonl")
        assert response.status_code == 404

    def test_record_download_jsonl_returns_ndjson(self, client, tmp_path: Path) -> None:
        record = _record_host(tmp_path, "run-1", "user-1", "jsonl")
        record.write_text('{"event": "started"}\n', encoding="utf-8")

        response = client.get("/api/resources/workflow-id/workflow-runs/run-1/record?format=jsonl")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-ndjson"
        assert response.headers["content-disposition"].endswith('filename="run_run-1.jsonl"')
        assert response.text == '{"event": "started"}\n'

    def test_record_download_md_returns_markdown(self, client, tmp_path: Path) -> None:
        record = _record_host(tmp_path, "run-1", "user-1", "md")
        record.write_text("# 运行记录 `run-1`\n", encoding="utf-8")

        response = client.get("/api/resources/workflow-id/workflow-runs/run-1/record?format=md")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        assert response.headers["content-disposition"].endswith('filename="run_run-1.md"')
        assert response.text == "# 运行记录 `run-1`\n"
