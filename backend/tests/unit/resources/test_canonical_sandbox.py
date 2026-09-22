from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.agentplatform.resources.canonical_sandbox import (
    CANONICAL_SKILLS_CONTAINER_PATH,
    canonical_sandbox_scope,
    parse_canonical_sandbox_scope,
)
from app.agentplatform.resources.storage import ResourceStorage, StorageConflict
from deerflow.sandbox.local.local_sandbox_provider import LocalSandboxProvider
from deerflow.sandbox.tools import ensure_sandbox_initialized, validate_local_tool_path


def test_scope_round_trip_keeps_data_thread_separate_from_run_identity() -> None:
    run_id = str(uuid.uuid4())

    scope = canonical_sandbox_scope("thread-42", run_id)

    # The scope must fit DeerFlow's 64-character thread-id budget, so the
    # thread component is a per-(run, thread) digest; it stays stable across
    # retries and distinct across runs and threads.
    assert len(scope) <= 64
    key, parsed_run_id = parse_canonical_sandbox_scope(scope)
    assert parsed_run_id == run_id
    assert key != "thread-42"
    assert key == parse_canonical_sandbox_scope(canonical_sandbox_scope("thread-42", run_id))[0]
    other_run = str(uuid.uuid4())
    assert parse_canonical_sandbox_scope(canonical_sandbox_scope("thread-42", other_run))[0] != key
    assert parse_canonical_sandbox_scope(canonical_sandbox_scope("thread-43", run_id))[0] != key
    assert parse_canonical_sandbox_scope("thread-42") is None


def test_run_skill_view_contains_only_frozen_versions_and_is_read_only(tmp_path: Path) -> None:
    storage = ResourceStorage(tmp_path)
    first_id = str(uuid.uuid4())
    second_id = str(uuid.uuid4())
    first_source = tmp_path / "first"
    second_source = tmp_path / "second"
    first_source.mkdir()
    second_source.mkdir()
    (first_source / "SKILL.md").write_text("# First\n")
    (second_source / "SKILL.md").write_text("# Second\n")
    first = storage.publish_staged(storage.stage_directory("skill", first_id, first_source), version=1)
    second = storage.publish_staged(storage.stage_directory("skill", second_id, second_source), version=3)
    run_id = str(uuid.uuid4())

    view = storage.create_run_skill_view(
        run_id,
        [(first_id, 1, first.content_hash), (second_id, 3, second.content_hash)],
        aliases={first_id: "first", second_id: "second"},
    )

    assert (view / "custom" / first_id / "SKILL.md").read_text() == "# First\n"
    assert (view / "custom" / second_id / "SKILL.md").read_text() == "# Second\n"
    assert (view / "custom" / "first" / "SKILL.md").read_text() == "# First\n"
    assert (view / "custom" / "second" / "SKILL.md").read_text() == "# Second\n"
    assert (view / "first" / "SKILL.md").read_text() == "# First\n"
    assert (view / "second" / "SKILL.md").read_text() == "# Second\n"
    assert not (view / "custom" / first_id / "versions").exists()
    assert not (view / "custom" / first_id / "draft").exists()
    with pytest.raises(StorageConflict, match="hash mismatch"):
        storage.create_run_skill_view(
            run_id,
            [(first_id, 1, "0" * 64), (second_id, 3, second.content_hash)],
        )


def test_canonical_skill_path_is_read_only_at_the_tool_gate() -> None:
    thread_data = {"workspace_path": "/tmp/work", "uploads_path": "/tmp/uploads", "outputs_path": "/tmp/outputs"}
    path = f"{CANONICAL_SKILLS_CONTAINER_PATH}/custom/example/SKILL.md"

    validate_local_tool_path(path, thread_data, read_only=True)
    with pytest.raises(PermissionError, match="skills path"):
        validate_local_tool_path(path, thread_data, read_only=False)
    with pytest.raises(PermissionError, match="path traversal"):
        validate_local_tool_path(f"{CANONICAL_SKILLS_CONTAINER_PATH}/../secrets", thread_data, read_only=True)


def test_local_provider_scopes_mount_to_exact_run_view(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_id = str(uuid.uuid4())
    view = tmp_path / "resources" / "run-skill-views" / run_id
    (view / "custom").mkdir(parents=True)
    scope = canonical_sandbox_scope("thread-42", run_id)
    # get_paths() resolves through deerflow now; the deployment layer maps
    # the legacy IDEER_HOME to DEER_FLOW_HOME.
    monkeypatch.setenv("DEER_FLOW_HOME", str(tmp_path))
    from app.agentplatform.resources import canonical_sandbox
    from deerflow.sandbox.local import local_sandbox_provider

    # The gateway/worker install the enterprise resolver at startup; install
    # it here so the provider serves the frozen run view for the scoped id.
    monkeypatch.setattr(local_sandbox_provider, "RUN_SKILL_VIEW_RESOLVER", canonical_sandbox._resolve_run_skill_view)
    monkeypatch.setattr(LocalSandboxProvider, "_setup_path_mappings", lambda self: [])
    provider = LocalSandboxProvider()

    sandbox_id = provider.acquire(scope)
    sandbox = provider.get(sandbox_id)

    assert sandbox is not None
    mapping = next(value for value in sandbox.path_mappings if value.container_path == CANONICAL_SKILLS_CONTAINER_PATH)
    assert mapping.local_path == str(view)
    assert mapping.read_only is True
    # User-data directories key on the run workspace — the same
    # ``thread_dir(run_id)`` layout the workflow file-roots resolver and the
    # artifact gate verify against.
    user_data = next(value for value in sandbox.path_mappings if value.container_path == "/mnt/user-data")
    assert run_id in user_data.local_path


def test_local_provider_fails_closed_when_run_skill_view_is_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_id = str(uuid.uuid4())
    scope = canonical_sandbox_scope("thread-42", run_id)
    monkeypatch.setenv("DEER_FLOW_HOME", str(tmp_path))
    from app.agentplatform.resources import canonical_sandbox
    from deerflow.sandbox.local import local_sandbox_provider

    monkeypatch.setattr(local_sandbox_provider, "RUN_SKILL_VIEW_RESOLVER", canonical_sandbox._resolve_run_skill_view)
    monkeypatch.setattr(LocalSandboxProvider, "_setup_path_mappings", lambda self: [])
    provider = LocalSandboxProvider()

    with pytest.raises(RuntimeError, match="Canonical Run Skill view is missing"):
        provider.acquire(scope)


def test_lazy_tool_acquisition_uses_run_scoped_sandbox_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = str(uuid.uuid4())
    sandbox = MagicMock()
    provider = MagicMock()
    provider.acquire.return_value = "sandbox-id"
    provider.get.return_value = sandbox
    monkeypatch.setattr("deerflow.sandbox.tools.get_sandbox_provider", lambda: provider)
    # The executor bridge rewrites context["thread_id"] to the canonical
    # run scope before runtime tools see it (workflows/v2/executor_bridge.py),
    # so the upstream tool keys the sandbox on the already-scoped thread id.
    scoped = canonical_sandbox_scope("thread-42", run_id)
    runtime = SimpleNamespace(
        state={},
        context={"thread_id": scoped},
        config={},
    )

    assert ensure_sandbox_initialized(runtime) is sandbox
    assert provider.acquire.call_args.args[0] == scoped
