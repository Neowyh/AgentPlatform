from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from app.gateway import user_deletion
from ideer.config.paths import Paths
from ideer.persistence.models.user import UserModel, UserRole


def _stub_database_steps(monkeypatch):
    for name in (
        "_validate_preconditions",
        "_handle_canonical_resources",
        "_handle_resource_metadata",
        "_handle_visibility_applications",
        "_handle_historical_data",
        "_handle_audit_logs",
        "_record_user_deletion_audit",
        "_has_canonical_identity_references",
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


@pytest.mark.asyncio
async def test_report_user_state_anomalies_returns_empty_report_without_session_factory(tmp_path, monkeypatch):
    monkeypatch.setattr("ideer.persistence.engine.get_session_factory", lambda: None)

    assert await user_deletion.report_user_state_anomalies(Paths(tmp_path)) == {
        "unexpected_directories": [],
        "auth_only_users": [],
        "rbac_only_users": [],
    }


@pytest.mark.asyncio
async def test_report_user_state_anomalies_reports_disk_and_database_mismatches(tmp_path, monkeypatch):
    paths = Paths(tmp_path)
    for user_id in ("shared", "disk-only", "default"):
        paths.user_dir(user_id).mkdir(parents=True)

    class Result:
        def __init__(self, values):
            self.values = values

        def scalars(self):
            return self.values

    class Session:
        def __init__(self):
            self.results = iter((Result(["shared", "auth-only"]), Result(["shared", "rbac-only"])))

        async def execute(self, _statement):
            return next(self.results)

    class Factory:
        def __call__(self):
            session = Session()

            class Context:
                async def __aenter__(self):
                    return session

                async def __aexit__(self, *_args):
                    return False

            return Context()

    monkeypatch.setattr("ideer.persistence.engine.get_session_factory", lambda: Factory())

    assert await user_deletion.report_user_state_anomalies(paths) == {
        "unexpected_directories": ["disk-only"],
        "auth_only_users": ["auth-only"],
        "rbac_only_users": ["rbac-only"],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("strategy", "target_user_id", "current_user_id", "message"),
    [
        (
            "invalid",
            None,
            "admin",
            "Invalid resource_strategy: 'invalid'. Must be one of: transfer, delete, soft_delete",
        ),
        ("transfer", None, "admin", "target_user_id is required when resource_strategy is 'transfer'"),
        ("transfer", "deleted", "admin", "target_user_id cannot be the same as the user being deleted"),
        ("delete", None, "deleted", "Cannot delete your own account"),
    ],
)
async def test_validate_preconditions_rejects_invalid_request_before_database_lookup(strategy, target_user_id, current_user_id, message):
    with pytest.raises(ValueError) as exc_info:
        await user_deletion._validate_preconditions(AsyncMock(), "deleted", current_user_id, strategy, target_user_id)
    assert str(exc_info.value) == message


@pytest.mark.asyncio
async def test_validate_preconditions_rejects_missing_or_active_or_missing_transfer_target(monkeypatch):
    session = AsyncMock()
    monkeypatch.setattr(user_deletion, "_check_user_exists", AsyncMock(return_value=(None, None)))
    with pytest.raises(ValueError) as exc_info:
        await user_deletion._validate_preconditions(session, "deleted", "admin", "delete", None)
    assert str(exc_info.value) == "User not found"

    active = UserModel(id="deleted", username="deleted", role=UserRole.USER, disabled=False)
    monkeypatch.setattr(user_deletion, "_check_user_exists", AsyncMock(return_value=(active, SimpleNamespace(id="deleted"))))
    with pytest.raises(ValueError) as exc_info:
        await user_deletion._validate_preconditions(session, "deleted", "admin", "delete", None)
    assert str(exc_info.value) == "User must be disabled before deletion"

    disabled = UserModel(id="deleted", username="deleted", role=UserRole.USER, disabled=True)
    monkeypatch.setattr(user_deletion, "_check_user_exists", AsyncMock(return_value=(disabled, SimpleNamespace(id="deleted"))))
    monkeypatch.setattr(user_deletion, "_check_target_user_exists", AsyncMock(return_value=False))
    with pytest.raises(ValueError) as exc_info:
        await user_deletion._validate_preconditions(session, "deleted", "admin", "transfer", "target")
    assert str(exc_info.value) == "Target user 'target' not found"


@pytest.mark.asyncio
async def test_transfer_copies_agents_without_removing_source_and_rejects_name_conflicts(tmp_path):
    paths = Paths(tmp_path)
    source = paths.user_agent_dir("deleted", "research")
    source.mkdir(parents=True)
    (source / "SOUL.md").write_text("source", encoding="utf-8")

    await user_deletion._handle_resource_metadata(AsyncMock(), paths, "deleted", "transfer", "target")
    copied = paths.user_agent_dir("target", "research")
    assert copied.joinpath("SOUL.md").read_text(encoding="utf-8") == "source"
    assert source.exists()

    with pytest.raises(ValueError, match="already has agent 'research'"):
        user_deletion._copy_agent_directories(paths, "deleted", "target")
    assert source.exists()


@pytest.mark.asyncio
async def test_transfer_succeeds_when_source_agent_directory_is_absent(tmp_path):
    await user_deletion._handle_resource_metadata(AsyncMock(), Paths(tmp_path), "deleted", "transfer", "target")


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_user, rbac_user, expected_deletes", [(True, False, 1), (False, True, 1), (True, True, 2)])
async def test_delete_user_rows_deletes_only_records_that_exist(auth_user, rbac_user, expected_deletes):
    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    auth_record = SimpleNamespace(id="auth-deleted") if auth_user else None
    rbac_record = SimpleNamespace(id="rbac-deleted") if rbac_user else None
    session = AsyncMock()
    session.execute.side_effect = (Result(auth_record), Result(rbac_record))

    await user_deletion._delete_user_rows(session, "deleted")

    assert session.delete.await_count == expected_deletes
    assert session.delete.await_args_list == [call(record) for record in (auth_record, rbac_record) if record is not None]


@pytest.mark.asyncio
async def test_delete_user_rows_keeps_disabled_rbac_history_anchor() -> None:
    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    auth_record = SimpleNamespace(id="auth-deleted")
    rbac_record = SimpleNamespace(id="rbac-deleted", disabled=True, department_id="dept-a")
    session = AsyncMock()
    session.execute.side_effect = (Result(auth_record), Result(rbac_record))

    await user_deletion._delete_user_rows(session, "deleted", retain_rbac_identity=True)

    session.delete.assert_awaited_once_with(auth_record)
    assert rbac_record.disabled is True
    assert rbac_record.department_id is None
