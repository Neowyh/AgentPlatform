"""Contracts for the UUID-first canonical resources facade."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.gateway.routers import resources
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import (
    Resource,
    ResourceVersion,
)
from ideer.persistence.models.user import UserModel, UserRole
from ideer.persistence.models.workflow_v2 import WorkflowV2RunRow
from ideer.resources.service import ResourceAction


def _user(role: UserRole, *, user_id: str = "user", department_id: str | None = "dept-a") -> UserModel:
    return UserModel(
        id=user_id,
        username=f"{user_id}@test.com",
        role=role,
        department_id=department_id,
        disabled=False,
    )


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


def test_router_exposes_uuid_first_workflow_lifecycle() -> None:
    routes = {(method, route.path) for route in resources.router.routes for method in route.methods}

    assert ("POST", "/api/resources") in routes
    assert ("GET", "/api/resources/notifications") in routes
    assert ("POST", "/api/resources/import/agent") in routes
    assert ("GET", "/api/resources/{resource_id}") in routes
    assert ("GET", "/api/resources/{resource_id}/published") in routes
    assert ("GET", "/api/resources/{resource_id}/export") in routes
    assert ("GET", "/api/resources/aliases/{resource_type}/{slug}") in routes
    assert ("PUT", "/api/resources/{resource_id}/workflow-draft") in routes
    assert ("PUT", "/api/resources/{resource_id}/agent-draft") in routes
    assert ("PUT", "/api/resources/{resource_id}/archive-draft") in routes
    assert ("POST", "/api/resources/{resource_id}/publish") in routes
    assert ("PUT", "/api/resources/{resource_id}/dependencies") in routes
    assert ("POST", "/api/resources/{resource_id}/fork") in routes
    assert ("POST", "/api/resources/{resource_id}/workflow-runs") in routes
    assert ("GET", "/api/resources/{resource_id}/workflow-runs") in routes
    assert ("GET", "/api/resources/{resource_id}/workflow-runs/{run_id}") in routes
    assert ("GET", "/api/resources/{resource_id}/workflow-runs/{run_id}/events") in routes
    assert ("GET", "/api/resources/{resource_id}/workflow-runs/{run_id}/artifacts") in routes
    assert ("GET", "/api/resources/{resource_id}/workflow-runs/{run_id}/artifacts/content") in routes
    assert ("POST", "/api/resources/{resource_id}/workflow-runs/{run_id}/commands") in routes
    assert ("GET", "/api/resources/admin/visibility-applications") in routes
    assert ("GET", "/api/resources/admin/retention-report") in routes
    assert ("POST", "/api/resources/admin/visibility-applications/{application_id}/review") in routes
    assert ("POST", "/api/resources/{resource_id}/suspend") in routes
    assert ("POST", "/api/resources/{resource_id}/transfer") in routes


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
async def test_legacy_catalog_mode_returns_no_canonical_list_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "legacy")

    payload = await resources.list_resources(
        resource_type=None,
        offset=0,
        limit=50,
        current_user=_user(UserRole.USER),
    )

    assert payload == {
        "items": [],
        "total": 0,
        "offset": 0,
        "limit": 50,
        "mode": "legacy",
    }


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
