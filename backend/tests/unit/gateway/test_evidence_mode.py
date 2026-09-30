"""Gateway evidence input contract after the glossary alignment (ticket 02).

The evidence mode is a derived system result: the gateway no longer accepts
an ``evidence_mode`` user input on any run-creation surface, and the
workflow launch route injects the mode derived by the shared intake.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.gateway.routers import resources
from app.gateway.routers.thread_runs import RunCreateRequest
from app.gateway.services import validate_evidence_selection

# ---------------------------------------------------------------------------
# S3 input contract: evidence_mode is not a user input anymore.
# ---------------------------------------------------------------------------


def test_run_create_request_rejects_evidence_mode_user_input():
    """The declared run contract treats evidence_mode as an unknown field."""

    with pytest.raises(ValidationError):
        RunCreateRequest(
            assistant_id="agent-1",
            input={"messages": []},
            evidence_mode="hybrid",
        )


def test_validate_evidence_selection_has_no_mode_parameter():
    import inspect

    params = inspect.signature(validate_evidence_selection).parameters
    assert list(params) == ["code_package_id"]


def test_validate_evidence_selection_normalizes_optional_package():
    assert validate_evidence_selection(None) is None
    assert validate_evidence_selection("package-1") == "package-1"


# ---------------------------------------------------------------------------
# Workflow launch route: derived mode injected, user value never honored.
# ---------------------------------------------------------------------------


def _user():
    from app.agentplatform.rbac_models import UserModel, UserRole

    return UserModel(
        id="user-1",
        username="user@test.com",
        role=UserRole.USER,
        department_id="dept-a",
        disabled=False,
    )


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, _query):
        # Latest-version lookup of _resolve_launch_workflow: a plain (no
        # result_contract) definition keeps these tests on the plain path.
        return SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(content={"name": "plain"}))


def _run_with_files_route(inputs: dict, files: list, stored_manifest) -> tuple[dict, list[dict]]:
    """Drive the with-files route with its collaborators stubbed.

    Returns the route response and the inputs each created canonical run
    received (in call order).
    """

    created_inputs: list[dict] = []

    class _FakeStore:
        def __init__(self, session_factory):
            pass

        async def create_canonical_run(self, run_id, resource_id, inputs, actor, **kwargs):
            created_inputs.append(dict(inputs))
            return SimpleNamespace(
                run_id=run_id,
                status="queued",
                workflow_resource_id=resource_id,
                model_name=kwargs.get("model_name"),
            )

    async def _fake_store_files(*, run_id, user_id, files):
        return stored_manifest, [f.filename or "" for f in files]

    async def _resolve_for_use(resource_id):
        return SimpleNamespace(type="workflow", id=resource_id, slug="plain", latest_version=1)

    resource_service = patch.object(resources, "ResourceService")
    with (
        patch.object(resources, "_store_workflow_run_files", _fake_store_files),
        patch.object(resources, "_factory", lambda: lambda: _FakeSession()),
        resource_service as service,
        patch.object(resources, "WorkflowV2Store", _FakeStore),
        patch.object(resources, "_cleanup_run_user_data"),
    ):
        service.return_value.resolve_for_use = _resolve_for_use

        response = asyncio.run(
            resources.create_workflow_run_with_files(
                resource_id="wf-resource",
                inputs=json.dumps(inputs),
                model_name=None,
                files=files,
                current_user=_user(),
            )
        )
    return response, created_inputs


def _upload_file(name: str):
    return SimpleNamespace(filename=name)


def test_with_files_route_injects_derived_hybrid_mode():
    stored = SimpleNamespace(
        source_virtual_path="/mnt/user-data/code-evidence/run-1/source",
        as_dict=lambda: {"package_id": "run-1"},
    )
    _, created = _run_with_files_route(
        inputs={"problem_description": "主轴电机过热报警", "evidence_mode": "document"},
        files=[_upload_file("source.zip")],
        stored_manifest=stored,
    )

    # The user-supplied mode never reaches the run inputs; the gateway
    # injects the mode derived by the shared intake instead.
    assert created[0]["evidence_mode"] == "hybrid"
    assert created[0]["code_package_source"] == "/mnt/user-data/code-evidence/run-1/source"
    assert created[0]["upload_dir"] == "/mnt/user-data/uploads"


def test_with_files_route_derived_mode_is_always_hybrid():
    """Attachments + code ZIP is the full evidence case: mode stays hybrid."""

    stored = SimpleNamespace(
        source_virtual_path="/mnt/user-data/code-evidence/run-1/source",
        as_dict=lambda: {"package_id": "run-1"},
    )
    _, created = _run_with_files_route(
        inputs={},
        files=[_upload_file("source.zip"), _upload_file("evidence.log")],
        stored_manifest=stored,
    )

    assert created[0]["evidence_mode"] == "hybrid"


def test_with_files_route_rejects_user_supplied_server_paths():
    with pytest.raises(HTTPException) as excinfo:
        _run_with_files_route(
            inputs={"upload_dir": "/mnt/user-data/uploads"},
            files=[_upload_file("evidence.log")],
            stored_manifest=None,
        )
    assert excinfo.value.status_code == 400


def test_workflow_run_route_never_honors_user_supplied_evidence_mode():
    """The JSON launch route strips evidence_mode: the definition's derived
    default applies, so no user value can select a document-only run."""

    created_inputs: list[dict] = []

    class _FakeStore:
        def __init__(self, session_factory):
            pass

        async def create_canonical_run(self, run_id, resource_id, inputs, actor, **kwargs):
            created_inputs.append(dict(inputs))
            return SimpleNamespace(run_id=run_id, status="queued", workflow_resource_id=resource_id, model_name=None)

    async def _resolve_for_use(resource_id):
        return SimpleNamespace(type="workflow", id=resource_id, slug="plain", latest_version=1)

    with (
        patch.object(resources, "_factory", lambda: lambda: _FakeSession()),
        patch.object(resources, "ResourceService") as service,
        patch.object(resources, "WorkflowV2Store", _FakeStore),
    ):
        service.return_value.resolve_for_use = _resolve_for_use
        asyncio.run(
            resources.create_workflow_run(
                resource_id="wf-resource",
                body=resources.WorkflowRunRequest(
                    inputs={"problem_description": "主轴电机过热", "evidence_mode": "document"},
                ),
                current_user=_user(),
            )
        )

    assert "evidence_mode" not in created_inputs[0]
