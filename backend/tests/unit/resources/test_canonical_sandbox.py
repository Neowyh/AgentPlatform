from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ideer.resources.canonical_sandbox import (
    CANONICAL_SKILLS_CONTAINER_PATH,
    canonical_sandbox_scope,
    parse_canonical_sandbox_scope,
)
from ideer.resources.storage import ResourceStorage, StorageConflict
from ideer.sandbox.local.local_sandbox_provider import LocalSandboxProvider
from ideer.sandbox.tools import ensure_sandbox_initialized, validate_local_tool_path


def test_scope_round_trip_keeps_data_thread_separate_from_run_identity() -> None:
    run_id = str(uuid.uuid4())

    scope = canonical_sandbox_scope("thread-42", run_id)

    assert parse_canonical_sandbox_scope(scope) == ("thread-42", run_id)
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
    )

    assert (view / "custom" / first_id / "SKILL.md").read_text() == "# First\n"
    assert (view / "custom" / second_id / "SKILL.md").read_text() == "# Second\n"
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
    with pytest.raises(PermissionError, match="canonical Run skills"):
        validate_local_tool_path(path, thread_data, read_only=False)
    with pytest.raises(PermissionError, match="path traversal"):
        validate_local_tool_path(f"{CANONICAL_SKILLS_CONTAINER_PATH}/../secrets", thread_data, read_only=True)


def test_local_provider_scopes_mount_to_exact_run_view(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_id = str(uuid.uuid4())
    view = tmp_path / "resources" / "run-skill-views" / run_id
    (view / "custom").mkdir(parents=True)
    scope = canonical_sandbox_scope("thread-42", run_id)
    monkeypatch.setenv("IDEER_HOME", str(tmp_path))
    monkeypatch.setattr(LocalSandboxProvider, "_setup_path_mappings", lambda self: [])
    monkeypatch.setattr(LocalSandboxProvider, "_build_thread_path_mappings", lambda self, thread_id: [])
    provider = LocalSandboxProvider()

    sandbox_id = provider.acquire(scope)
    sandbox = provider.get(sandbox_id)

    assert sandbox is not None
    mapping = next(value for value in sandbox.path_mappings if value.container_path == CANONICAL_SKILLS_CONTAINER_PATH)
    assert mapping.local_path == str(view)
    assert mapping.read_only is True


def test_lazy_tool_acquisition_uses_run_scoped_sandbox_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = str(uuid.uuid4())
    sandbox = MagicMock()
    provider = MagicMock()
    provider.acquire.return_value = "sandbox-id"
    provider.get.return_value = sandbox
    monkeypatch.setattr("ideer.sandbox.tools.get_sandbox_provider", lambda: provider)
    runtime = SimpleNamespace(
        state={},
        context={"thread_id": "thread-42", "canonical_run_id": run_id},
        config={},
    )

    assert ensure_sandbox_initialized(runtime) is sandbox
    provider.acquire.assert_called_once_with(canonical_sandbox_scope("thread-42", run_id))
