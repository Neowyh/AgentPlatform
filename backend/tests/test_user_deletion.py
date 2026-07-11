from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.gateway import user_deletion
from ideer.config.paths import Paths


def _stub_database_steps(monkeypatch):
    for name in (
        "_validate_preconditions",
        "_handle_resource_metadata",
        "_handle_visibility_applications",
        "_handle_historical_data",
        "_handle_audit_logs",
        "_record_user_deletion_audit",
        "_delete_user_rows",
    ):
        monkeypatch.setattr(user_deletion, name, AsyncMock())


@pytest.mark.asyncio
async def test_database_commit_failure_does_not_delete_user_directory(tmp_path, monkeypatch):
    _stub_database_steps(monkeypatch)
    paths = Paths(tmp_path)
    user_dir = paths.user_dir("deleted-user")
    user_dir.mkdir(parents=True)
    (user_dir / "state.txt").write_text("keep", encoding="utf-8")
    session = AsyncMock()
    session.commit.side_effect = RuntimeError("commit failed")

    with pytest.raises(RuntimeError, match="commit failed"):
        await user_deletion.delete_user(
            session,
            paths,
            "deleted-user",
            current_user_id="admin-user",
            resource_strategy="delete",
        )

    assert user_dir.exists()


@pytest.mark.asyncio
async def test_cleanup_failure_happens_after_commit_and_is_retryable(tmp_path, monkeypatch):
    _stub_database_steps(monkeypatch)
    paths = Paths(tmp_path)
    user_dir = paths.user_dir("deleted-user")
    user_dir.mkdir(parents=True)
    session = AsyncMock()
    audit = AsyncMock()
    monkeypatch.setattr(user_deletion, "_record_cleanup_failure_audit", audit)
    real_rmtree = user_deletion.shutil.rmtree

    def fail_once(path):
        monkeypatch.setattr(user_deletion.shutil, "rmtree", real_rmtree)
        raise OSError("busy")

    monkeypatch.setattr(user_deletion.shutil, "rmtree", fail_once)

    result = await user_deletion.delete_user(
        session,
        paths,
        "deleted-user",
        current_user_id="admin-user",
        resource_strategy="delete",
    )

    session.commit.assert_awaited_once()
    assert result["filesystem_cleanup"] == "failed"
    audit.assert_awaited_once()
    assert user_deletion.cleanup_user_state(paths, "deleted-user") == "deleted"
    assert user_deletion.cleanup_user_state(paths, "deleted-user") == "already_absent"
