"""Tests for startup reconciliation of missing resource_metadata records."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


class _Result:
    def __init__(self, row=None):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


def _session_factory(session):
    sf = MagicMock()
    sf.return_value.__aenter__ = AsyncMock(return_value=session)
    sf.return_value.__aexit__ = AsyncMock(return_value=False)
    return sf


def _user(user_id: str, department_id: str | None = None):
    return MagicMock(id=user_id, username=f"{user_id}@test.com", department_id=department_id)


@pytest.mark.asyncio
class TestResolveResourceOwner:
    async def test_resolves_by_user_id(self):
        from app.gateway.app import _resolve_resource_owner

        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result(_user("u1", "dept-1")))

        owner_id, dept_id = await _resolve_resource_owner(_session_factory(session), "u1")

        assert owner_id == "u1"
        assert dept_id == "dept-1"

    async def test_resolves_by_username_email(self):
        from app.gateway.app import _resolve_resource_owner

        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result(_user("u1")))

        owner_id, dept_id = await _resolve_resource_owner(_session_factory(session), "u1@test.com")

        assert owner_id == "u1"
        assert dept_id is None

    async def test_system_and_empty_return_none(self):
        from app.gateway.app import _resolve_resource_owner

        sf = _session_factory(MagicMock())

        assert await _resolve_resource_owner(sf, "system") == (None, None)
        assert await _resolve_resource_owner(sf, None) == (None, None)
        assert await _resolve_resource_owner(sf, "") == (None, None)

    async def test_unknown_owner_returns_none(self):
        from app.gateway.app import _resolve_resource_owner

        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result(None))

        owner_id, dept_id = await _resolve_resource_owner(_session_factory(session), "ghost")

        assert owner_id is None
        assert dept_id is None


@pytest.mark.asyncio
class TestReconcileWorkflowMetadata:
    def _definition(self, name, created_by):
        return MagicMock(workflow_name=name, created_by=created_by)

    async def test_creates_meta_for_workflow_missing_one(self):
        from app.gateway.app import _reconcile_workflow_metadata

        sf = _session_factory(MagicMock())
        store = MagicMock()
        store.load_meta = AsyncMock(return_value={})
        store.save_meta = AsyncMock(return_value=True)

        with patch("ideer.workflows.v2.store.WorkflowV2Store") as store_cls:
            store_cls.return_value.list_latest_definitions = AsyncMock(return_value=([self._definition("orphan-wf", "u1")], 1))
            with patch("app.gateway.utils.ResourceMetadataStore", return_value=store):
                with patch("app.gateway.app._resolve_resource_owner", return_value=("u1", "dept-1")):
                    await _reconcile_workflow_metadata(sf, "admin-1")

        store.save_meta.assert_awaited_once_with("orphan-wf", {"owner_id": "u1", "department_id": "dept-1", "visibility": "private"})

    async def test_skips_workflows_that_already_have_meta(self):
        from app.gateway.app import _reconcile_workflow_metadata

        sf = _session_factory(MagicMock())
        store = MagicMock()
        store.load_meta = AsyncMock(return_value={"owner_id": "u1"})
        store.save_meta = AsyncMock(return_value=True)

        with patch("ideer.workflows.v2.store.WorkflowV2Store") as store_cls:
            store_cls.return_value.list_latest_definitions = AsyncMock(return_value=([self._definition("known-wf", "u1")], 1))
            with patch("app.gateway.utils.ResourceMetadataStore", return_value=store):
                await _reconcile_workflow_metadata(sf, "admin-1")

        store.save_meta.assert_not_awaited()

    async def test_falls_back_to_admin_when_creator_unresolved(self):
        from app.gateway.app import _reconcile_workflow_metadata

        sf = _session_factory(MagicMock())
        store = MagicMock()
        store.load_meta = AsyncMock(return_value={})
        store.save_meta = AsyncMock(return_value=True)

        with patch("ideer.workflows.v2.store.WorkflowV2Store") as store_cls:
            store_cls.return_value.list_latest_definitions = AsyncMock(return_value=([self._definition("system-wf", "system")], 1))
            with patch("app.gateway.utils.ResourceMetadataStore", return_value=store):
                with patch("app.gateway.app._resolve_resource_owner", return_value=(None, None)):
                    await _reconcile_workflow_metadata(sf, "admin-1")

        store.save_meta.assert_awaited_once_with("system-wf", {"owner_id": "admin-1", "department_id": None, "visibility": "private"})

    async def test_handles_store_enumeration_failure(self):
        from app.gateway.app import _reconcile_workflow_metadata

        sf = _session_factory(MagicMock())
        store = MagicMock()
        store.save_meta = AsyncMock(return_value=True)

        with patch("ideer.workflows.v2.store.WorkflowV2Store") as store_cls:
            store_cls.return_value.list_latest_definitions = AsyncMock(side_effect=RuntimeError("boom"))
            with patch("app.gateway.utils.ResourceMetadataStore", return_value=store):
                await _reconcile_workflow_metadata(sf, "admin-1")

        store.save_meta.assert_not_awaited()


class TestScanAgentDirs:
    def test_returns_per_user_and_legacy_agents(self, tmp_path):
        from app.gateway.app import _scan_agent_dirs

        per_user = tmp_path / "users" / "u1" / "agents" / "helper"
        per_user.mkdir(parents=True)
        legacy = tmp_path / "agents" / "legacy-agent"
        legacy.mkdir(parents=True)
        (tmp_path / "agents" / "not-a-dir.txt").write_text("x", encoding="utf-8")

        dirs = _scan_agent_dirs(tmp_path)

        assert [d.name for d in dirs] == ["helper", "legacy-agent"]

    def test_per_user_shadows_legacy(self, tmp_path):
        from app.gateway.app import _scan_agent_dirs

        per_user = tmp_path / "users" / "u1" / "agents" / "dup"
        per_user.mkdir(parents=True)
        legacy = tmp_path / "agents" / "dup"
        legacy.mkdir(parents=True)

        dirs = _scan_agent_dirs(tmp_path)

        assert len(dirs) == 1
        assert dirs[0] == per_user

    def test_missing_dirs_yield_empty(self, tmp_path):
        from app.gateway.app import _scan_agent_dirs

        assert _scan_agent_dirs(tmp_path / "nonexistent") == []


@pytest.mark.asyncio
class TestReconcileAgentMetadata:
    async def test_creates_meta_for_agents_on_disk(self, tmp_path):
        from app.gateway.app import _reconcile_agent_metadata

        per_user = tmp_path / "users" / "u1" / "agents" / "helper"
        per_user.mkdir(parents=True)
        (per_user / "config.yaml").write_text("owner_id: u1\n", encoding="utf-8")
        legacy = tmp_path / "agents" / "legacy-agent"
        legacy.mkdir(parents=True)
        (legacy / "config.yaml").write_text("", encoding="utf-8")

        store = MagicMock()
        store.load_meta = AsyncMock(return_value={})
        store.save_meta = AsyncMock(return_value=True)

        with patch("ideer.config.paths.get_paths") as paths:
            paths.return_value.base_dir = tmp_path
            with patch("app.gateway.utils.ResourceMetadataStore", return_value=store):
                with patch("app.gateway.app._resolve_resource_owner", side_effect=[("u1", "dept-1")]):
                    await _reconcile_agent_metadata(_session_factory(MagicMock()), "admin-1")

        store.save_meta.assert_has_awaits(
            [
                call("helper", {"owner_id": "u1", "department_id": "dept-1", "visibility": "private"}),
                call("legacy-agent", {"owner_id": "admin-1", "department_id": None, "visibility": "private"}),
            ]
        )

    async def test_respects_config_visibility_and_skips_existing(self, tmp_path):
        from app.gateway.app import _reconcile_agent_metadata

        existing_dir = tmp_path / "agents" / "known"
        existing_dir.mkdir(parents=True)
        (existing_dir / "config.yaml").write_text("owner_id: other\n", encoding="utf-8")
        new_dir = tmp_path / "agents" / "shared"
        new_dir.mkdir(parents=True)
        (new_dir / "config.yaml").write_text("owner_id: u1\nvisibility: public\n", encoding="utf-8")

        store = MagicMock()
        store.load_meta = AsyncMock(side_effect=[{"owner_id": "other"}, {}])
        store.save_meta = AsyncMock(return_value=True)

        with patch("ideer.config.paths.get_paths") as paths:
            paths.return_value.base_dir = tmp_path
            with patch("app.gateway.utils.ResourceMetadataStore", return_value=store):
                with patch("app.gateway.app._resolve_resource_owner", return_value=("u1", None)):
                    await _reconcile_agent_metadata(_session_factory(MagicMock()), "admin-1")

        store.save_meta.assert_awaited_once_with("shared", {"owner_id": "u1", "department_id": None, "visibility": "public"})


@pytest.mark.asyncio
class TestReconcileResourceMetadata:
    async def test_invokes_workflow_and_agent_reconciliation(self, tmp_path):
        from app.gateway.app import _reconcile_resource_metadata

        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result(_user("admin-1")))
        sf = _session_factory(session)
        startup_config = MagicMock()
        startup_config.skills.get_skills_path.return_value = tmp_path

        with patch("ideer.persistence.engine.get_session_factory", return_value=sf):
            with patch("app.gateway.app._reconcile_workflow_metadata") as wf:
                with patch("app.gateway.app._reconcile_agent_metadata") as ag:
                    await _reconcile_resource_metadata(startup_config)

        wf.assert_awaited_once()
        ag.assert_awaited_once()

    async def test_skips_when_no_active_super_admin(self, tmp_path):
        from app.gateway.app import _reconcile_resource_metadata

        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result(None))
        sf = _session_factory(session)
        startup_config = MagicMock()
        startup_config.skills.get_skills_path.return_value = tmp_path

        with patch("ideer.persistence.engine.get_session_factory", return_value=sf):
            with patch("app.gateway.app._reconcile_workflow_metadata") as wf:
                with patch("app.gateway.app._reconcile_agent_metadata") as ag:
                    await _reconcile_resource_metadata(startup_config)

        wf.assert_not_awaited()
        ag.assert_not_awaited()

    async def test_skips_when_database_unavailable(self):
        from app.gateway.app import _reconcile_resource_metadata

        with patch("ideer.persistence.engine.get_session_factory", return_value=None):
            await _reconcile_resource_metadata(MagicMock())
