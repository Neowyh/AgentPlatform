"""Tests for .meta.json to resource_metadata migration script."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def skills_path(base_dir: Path) -> Path:
    return base_dir / "skills"


@pytest.fixture
def agent_meta_path(base_dir: Path) -> Path:
    return base_dir / "users" / "u1" / "agents" / "test-agent"


@pytest.fixture
def legacy_agent_meta_path(base_dir: Path) -> Path:
    return base_dir / "agents" / "legacy-agent"


def _write_skill_meta(skills_path: Path, name: str, meta: dict) -> Path:
    skill_dir = skills_path / "custom" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    meta_file = skill_dir / ".meta.json"
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta_file


def _write_agent_meta(agent_dir: Path, meta: dict) -> Path:
    agent_dir.mkdir(parents=True, exist_ok=True)
    meta_file = agent_dir / ".meta.json"
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta_file


class TestScanSkillMetaFiles:
    def test_finds_custom_skill_meta_files(self, skills_path: Path):
        from ideer.scripts.migrate_meta_json import _scan_skill_meta_files

        _write_skill_meta(skills_path, "my-skill", {"name": "my-skill", "visibility": "public"})
        _write_skill_meta(skills_path, "other-skill", {"name": "other-skill", "visibility": "private"})

        results = _scan_skill_meta_files(skills_path)
        assert len(results) == 2
        names = {meta["name"] for _, meta in results}
        assert names == {"my-skill", "other-skill"}

    def test_skips_corrupted_json(self, skills_path: Path):
        from ideer.scripts.migrate_meta_json import _scan_skill_meta_files

        _write_skill_meta(skills_path, "good-skill", {"name": "good-skill"})
        bad_dir = skills_path / "custom" / "bad-skill"
        bad_dir.mkdir(parents=True)
        (bad_dir / ".meta.json").write_text("not json {{{")

        results = _scan_skill_meta_files(skills_path)
        assert len(results) == 1
        assert results[0][1]["name"] == "good-skill"

    def test_empty_when_no_custom_dir(self, tmp_path: Path):
        from ideer.scripts.migrate_meta_json import _scan_skill_meta_files

        results = _scan_skill_meta_files(tmp_path / "nonexistent")
        assert results == []

    def test_skips_non_directory_and_directory_without_meta(self, skills_path: Path):
        from ideer.scripts.migrate_meta_json import _scan_skill_meta_files

        custom_dir = skills_path / "custom"
        custom_dir.mkdir(parents=True)
        (custom_dir / "not-a-directory").write_text("ignored", encoding="utf-8")
        (custom_dir / "missing-meta").mkdir()
        _write_skill_meta(skills_path, "valid-skill", {"name": "valid-skill"})

        results = _scan_skill_meta_files(skills_path)

        assert len(results) == 1
        assert results[0][1]["name"] == "valid-skill"


class TestScanAgentMetaFiles:
    def test_finds_per_user_agent_meta_files(self, base_dir: Path):
        from ideer.scripts.migrate_meta_json import _scan_agent_meta_files

        _write_agent_meta(base_dir / "users" / "u1" / "agents" / "agent-a", {"name": "agent-a", "visibility": "private"})
        _write_agent_meta(base_dir / "users" / "u2" / "agents" / "agent-b", {"name": "agent-b", "visibility": "public"})

        results = _scan_agent_meta_files(base_dir)
        assert len(results) == 2
        names = {meta["name"] for _, meta in results}
        assert names == {"agent-a", "agent-b"}

    def test_finds_legacy_agent_meta_files(self, base_dir: Path):
        from ideer.scripts.migrate_meta_json import _scan_agent_meta_files

        _write_agent_meta(base_dir / "agents" / "legacy-agent", {"name": "legacy-agent"})

        results = _scan_agent_meta_files(base_dir)
        assert len(results) == 1
        assert results[0][1]["name"] == "legacy-agent"

    def test_skips_corrupted_json(self, base_dir: Path):
        from ideer.scripts.migrate_meta_json import _scan_agent_meta_files

        _write_agent_meta(base_dir / "users" / "u1" / "agents" / "good-agent", {"name": "good-agent"})
        bad_dir = base_dir / "users" / "u1" / "agents" / "bad-agent"
        bad_dir.mkdir(parents=True)
        (bad_dir / ".meta.json").write_text("not json {{{")

        results = _scan_agent_meta_files(base_dir)
        assert len(results) == 1

    def test_empty_when_no_dirs(self, tmp_path: Path):
        from ideer.scripts.migrate_meta_json import _scan_agent_meta_files

        results = _scan_agent_meta_files(tmp_path)
        assert results == []

    def test_skips_non_directory_and_missing_meta_in_user_and_legacy_dirs(self, base_dir: Path):
        from ideer.scripts.migrate_meta_json import _scan_agent_meta_files

        users_dir = base_dir / "users"
        users_dir.mkdir()
        (users_dir / "not-a-directory").write_text("ignored", encoding="utf-8")
        (users_dir / "u1" / "agents" / "missing-meta").mkdir(parents=True)
        (users_dir / "u1" / "agents" / "not-a-directory").write_text("ignored", encoding="utf-8")

        legacy_dir = base_dir / "agents"
        legacy_dir.mkdir()
        (legacy_dir / "not-a-directory").write_text("ignored", encoding="utf-8")
        (legacy_dir / "missing-meta").mkdir()
        _write_agent_meta(legacy_dir / "valid-agent", {"name": "valid-agent"})

        results = _scan_agent_meta_files(base_dir)

        assert len(results) == 1
        assert results[0][1]["name"] == "valid-agent"

    def test_skips_corrupted_legacy_agent_json(self, base_dir: Path):
        from ideer.scripts.migrate_meta_json import _scan_agent_meta_files

        _write_agent_meta(base_dir / "agents" / "good-agent", {"name": "good-agent"})
        bad_dir = base_dir / "agents" / "bad-agent"
        bad_dir.mkdir(parents=True)
        (bad_dir / ".meta.json").write_text("not json {{{", encoding="utf-8")

        results = _scan_agent_meta_files(base_dir)

        assert len(results) == 1
        assert results[0][1]["name"] == "good-agent"


class TestValidateOwnerExists:
    def test_valid_owner(self):
        from ideer.scripts.migrate_meta_json import _validate_owner_exists

        assert _validate_owner_exists("u1", {"u1", "u2"}) is True

    def test_invalid_owner(self):
        from ideer.scripts.migrate_meta_json import _validate_owner_exists

        assert _validate_owner_exists("unknown", {"u1", "u2"}) is False

    def test_empty_owner(self):
        from ideer.scripts.migrate_meta_json import _validate_owner_exists

        assert _validate_owner_exists("", {"u1"}) is False

    def test_none_owner(self):
        from ideer.scripts.migrate_meta_json import _validate_owner_exists

        assert _validate_owner_exists(None, {"u1"}) is False


def _make_mock_session(owner_rows=None, existing_record=None):
    """Create a mock async session with proper add/commit behavior."""
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    if owner_rows is None:
        owner_rows = []

    mock_owner_result = MagicMock()
    mock_owner_result.all.return_value = owner_rows

    mock_record_result = MagicMock()
    mock_record_result.scalar_one_or_none.return_value = existing_record

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_owner_result
        return mock_record_result

    mock_session.execute = mock_execute
    return mock_session


def _make_mock_sf(mock_session):
    """Create a mock session factory that yields the given session."""
    mock_sf = MagicMock()
    mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_sf


class _ScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Result:
    def __init__(self, *, scalar=None, scalar_one=None, scalar_rows=None, all_rows=None):
        self._scalar = scalar
        self._scalar_one = scalar_one
        self._scalar_rows = [] if scalar_rows is None else scalar_rows
        self._all_rows = [] if all_rows is None else all_rows

    def scalar(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar_one

    def scalars(self):
        return _ScalarRows(self._scalar_rows)

    def all(self):
        return self._all_rows


@pytest.mark.asyncio
class TestMigrateMetaJson:
    async def test_migrates_skill_meta_files(self, base_dir: Path, skills_path: Path):
        from ideer.scripts.migrate_meta_json import migrate_meta_json

        _write_skill_meta(
            skills_path,
            "my-skill",
            {
                "name": "my-skill",
                "owner_id": "u1",
                "visibility": "public",
                "department_id": "dept-1",
            },
        )

        mock_session = _make_mock_session(owner_rows=[("u1",), ("u2",)])
        mock_sf = _make_mock_sf(mock_session)

        with (
            patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=mock_sf),
            patch("ideer.scripts.migrate_meta_json.get_paths") as mock_get_paths,
            patch("ideer.scripts.migrate_meta_json.SkillsConfig") as mock_skills_config,
        ):
            mock_get_paths.return_value.base_dir = base_dir
            mock_skills_config.return_value.get_skills_path.return_value = skills_path

            report = await migrate_meta_json(dry_run=False)

        assert report["imported"] == 1
        assert report["skipped"] == 0
        assert report["failed"] == 0
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    async def test_skips_existing_records(self, base_dir: Path, skills_path: Path):
        from ideer.scripts.migrate_meta_json import migrate_meta_json

        _write_skill_meta(skills_path, "existing-skill", {"name": "existing-skill", "visibility": "private"})

        mock_session = _make_mock_session(existing_record=MagicMock())
        mock_sf = _make_mock_sf(mock_session)

        with (
            patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=mock_sf),
            patch("ideer.scripts.migrate_meta_json.get_paths") as mock_get_paths,
            patch("ideer.scripts.migrate_meta_json.SkillsConfig") as mock_skills_config,
        ):
            mock_get_paths.return_value.base_dir = base_dir
            mock_skills_config.return_value.get_skills_path.return_value = skills_path

            report = await migrate_meta_json(dry_run=False)

        assert report["imported"] == 0
        assert report["skipped"] == 1
        mock_session.add.assert_not_called()

    async def test_dry_run_does_not_commit(self, base_dir: Path, skills_path: Path):
        from ideer.scripts.migrate_meta_json import migrate_meta_json

        _write_skill_meta(skills_path, "dry-skill", {"name": "dry-skill", "owner_id": "u1", "visibility": "private"})

        mock_session = _make_mock_session(owner_rows=[("u1",)])
        mock_sf = _make_mock_sf(mock_session)

        with (
            patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=mock_sf),
            patch("ideer.scripts.migrate_meta_json.get_paths") as mock_get_paths,
            patch("ideer.scripts.migrate_meta_json.SkillsConfig") as mock_skills_config,
        ):
            mock_get_paths.return_value.base_dir = base_dir
            mock_skills_config.return_value.get_skills_path.return_value = skills_path

            report = await migrate_meta_json(dry_run=True)

        assert report["imported"] == 1
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    async def test_returns_error_when_db_not_initialized(self):
        from ideer.scripts.migrate_meta_json import migrate_meta_json

        with patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=None):
            report = await migrate_meta_json()

        assert report["imported"] == 0
        assert report["failed"] == 0

    async def test_skips_missing_owner_instead_of_defaulting_to_super_admin(self, base_dir: Path, skills_path: Path):
        from ideer.scripts.migrate_meta_json import migrate_meta_json

        _write_skill_meta(
            skills_path,
            "orphan-skill",
            {
                "name": "orphan-skill",
                "owner_id": "nonexistent-user",
                "visibility": "private",
            },
        )

        mock_session = _make_mock_session(owner_rows=[("u1",)])
        mock_sf = _make_mock_sf(mock_session)

        with (
            patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=mock_sf),
            patch("ideer.scripts.migrate_meta_json.get_paths") as mock_get_paths,
            patch("ideer.scripts.migrate_meta_json.SkillsConfig") as mock_skills_config,
        ):
            mock_get_paths.return_value.base_dir = base_dir
            mock_skills_config.return_value.get_skills_path.return_value = skills_path

            report = await migrate_meta_json(dry_run=False)

        assert report == {"imported": 0, "skipped": 1, "failed": 0}
        mock_session.add.assert_not_called()

    async def test_migrates_agent_meta_files(self, base_dir: Path, skills_path: Path):
        from ideer.scripts.migrate_meta_json import migrate_meta_json

        _write_agent_meta(
            base_dir / "users" / "u1" / "agents" / "my-agent",
            {
                "name": "my-agent",
                "owner_id": "u1",
                "visibility": "department",
                "department_id": "dept-1",
            },
        )

        mock_session = _make_mock_session(owner_rows=[("u1",)])
        mock_sf = _make_mock_sf(mock_session)

        with (
            patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=mock_sf),
            patch("ideer.scripts.migrate_meta_json.get_paths") as mock_get_paths,
            patch("ideer.scripts.migrate_meta_json.SkillsConfig") as mock_skills_config,
        ):
            mock_get_paths.return_value.base_dir = base_dir
            mock_skills_config.return_value.get_skills_path.return_value = skills_path

            report = await migrate_meta_json(dry_run=False)

        assert report["imported"] == 1
        added_resource = mock_session.add.call_args[0][0]
        assert added_resource.resource_type == "agent"
        assert added_resource.resource_id == "my-agent"
        assert added_resource.department_id == "dept-1"
        assert added_resource.visibility == "department"

    async def test_no_meta_files_returns_zero_counts(self, base_dir: Path, skills_path: Path):
        from ideer.scripts.migrate_meta_json import migrate_meta_json

        with (
            patch("ideer.scripts.migrate_meta_json.get_session_factory") as mock_sf,
            patch("ideer.scripts.migrate_meta_json.get_paths") as mock_get_paths,
            patch("ideer.scripts.migrate_meta_json.SkillsConfig") as mock_skills_config,
        ):
            mock_get_paths.return_value.base_dir = base_dir
            mock_skills_config.return_value.get_skills_path.return_value = skills_path

            report = await migrate_meta_json()

        assert report == {"imported": 0, "skipped": 0, "failed": 0}
        mock_sf.assert_not_called()

    async def test_imported_from_field_contains_file_path(self, base_dir: Path, skills_path: Path):
        from ideer.scripts.migrate_meta_json import migrate_meta_json

        meta_file = _write_skill_meta(skills_path, "trace-skill", {"name": "trace-skill", "owner_id": "u1", "visibility": "private"})

        mock_session = _make_mock_session(owner_rows=[("u1",)])
        mock_sf = _make_mock_sf(mock_session)

        with (
            patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=mock_sf),
            patch("ideer.scripts.migrate_meta_json.get_paths") as mock_get_paths,
            patch("ideer.scripts.migrate_meta_json.SkillsConfig") as mock_skills_config,
        ):
            mock_get_paths.return_value.base_dir = base_dir
            mock_skills_config.return_value.get_skills_path.return_value = skills_path

            await migrate_meta_json(dry_run=False)

        added_resource = mock_session.add.call_args[0][0]
        assert str(meta_file) in added_resource.imported_from

    async def test_counts_failed_records_when_idempotency_check_raises(self, base_dir: Path, skills_path: Path):
        from ideer.scripts.migrate_meta_json import migrate_meta_json

        _write_skill_meta(skills_path, "broken-skill", {"name": "broken-skill", "owner_id": "u1", "visibility": "private"})
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[_Result(all_rows=[("u1",)]), RuntimeError("database error")])

        with (
            patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=_make_mock_sf(mock_session)),
            patch("ideer.scripts.migrate_meta_json.get_paths") as mock_get_paths,
            patch("ideer.scripts.migrate_meta_json.SkillsConfig") as mock_skills_config,
        ):
            mock_get_paths.return_value.base_dir = base_dir
            mock_skills_config.return_value.get_skills_path.return_value = skills_path

            report = await migrate_meta_json()

        assert report == {"imported": 0, "skipped": 0, "failed": 1}
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()


@pytest.mark.asyncio
class TestOwnerLoadingAndSampleValidation:
    async def test_load_existing_owner_ids_returns_empty_when_db_unavailable(self):
        from ideer.scripts.migrate_meta_json import _load_existing_owner_ids

        with patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=None):
            assert await _load_existing_owner_ids() == set()

    async def test_load_existing_owner_ids_returns_empty_when_query_fails(self):
        from ideer.scripts.migrate_meta_json import _load_existing_owner_ids

        mock_session = MagicMock()

        async def raise_execute(_stmt):
            raise RuntimeError("boom")

        mock_session.execute = raise_execute

        with patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=_make_mock_sf(mock_session)):
            assert await _load_existing_owner_ids() == set()

    async def test_sample_validate_accepts_valid_rows_and_warns_invalid_rows(self):
        from ideer.persistence.models.resource_metadata import ResourceMetadata
        from ideer.scripts.migrate_meta_json import _sample_validate

        valid = ResourceMetadata(resource_type="skill", resource_id="ok", owner_id="u1", visibility="private", version=1)
        invalid = ResourceMetadata(resource_type="invalid", resource_id="bad", owner_id="", visibility="hidden", version=0)
        mock_session = MagicMock()
        mock_session.execute = AsyncMock(side_effect=[_Result(scalar=20), _Result(scalar_rows=[valid, invalid])])

        with patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=_make_mock_sf(mock_session)):
            await _sample_validate(imported=2, skipped=0)

        assert mock_session.execute.await_count == 2

    async def test_sample_validate_ignores_unavailable_database(self):
        from ideer.scripts.migrate_meta_json import _sample_validate

        with patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=None):
            await _sample_validate(imported=1, skipped=0)


@pytest.mark.asyncio
class TestBackfillTools:
    async def test_backfill_tools_handles_config_load_failure(self):
        from ideer.scripts.migrate_meta_json import backfill_tools

        with patch("ideer.scripts.migrate_meta_json.ExtensionsConfig.from_file", side_effect=ValueError("bad json")):
            assert await backfill_tools() == {"imported": 0, "skipped": 0, "failed": 0}

    async def test_backfill_tools_returns_zero_when_config_has_no_tools(self):
        from ideer.scripts.migrate_meta_json import backfill_tools

        config = MagicMock()
        config.mcp_servers = {}

        with patch("ideer.scripts.migrate_meta_json.ExtensionsConfig.from_file", return_value=config):
            assert await backfill_tools() == {"imported": 0, "skipped": 0, "failed": 0}

    async def test_backfill_tools_returns_zero_when_database_unavailable(self):
        from ideer.scripts.migrate_meta_json import backfill_tools

        config = MagicMock()
        config.mcp_servers = {"search": MagicMock()}

        with (
            patch("ideer.scripts.migrate_meta_json.ExtensionsConfig.from_file", return_value=config),
            patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=None),
        ):
            assert await backfill_tools() == {"imported": 0, "skipped": 0, "failed": 0}

    async def test_backfill_tools_imports_missing_tools_and_skips_existing(self):
        from ideer.scripts.migrate_meta_json import backfill_tools

        config = MagicMock()
        config.mcp_servers = {"search": MagicMock(), "existing": MagicMock()}
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[_Result(scalar_one=None), _Result(scalar_one=MagicMock())])

        with (
            patch("ideer.scripts.migrate_meta_json.ExtensionsConfig.from_file", return_value=config),
            patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=_make_mock_sf(mock_session)),
        ):
            report = await backfill_tools(default_owner="u1")

        assert report == {"imported": 1, "skipped": 1, "failed": 0}
        added_resource = mock_session.add.call_args[0][0]
        assert added_resource.resource_type == "tool"
        assert added_resource.resource_id == "search"
        assert added_resource.owner_id == "u1"
        assert added_resource.visibility == "public"
        mock_session.commit.assert_awaited_once()

    async def test_backfill_tools_dry_run_does_not_add_or_commit(self):
        from ideer.scripts.migrate_meta_json import backfill_tools

        config = MagicMock()
        config.mcp_servers = {"search": MagicMock()}
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock(return_value=_Result(scalar_one=None))

        with (
            patch("ideer.scripts.migrate_meta_json.ExtensionsConfig.from_file", return_value=config),
            patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=_make_mock_sf(mock_session)),
        ):
            report = await backfill_tools(dry_run=True, default_owner="u1")

        assert report == {"imported": 1, "skipped": 0, "failed": 0}
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    async def test_backfill_tools_counts_per_tool_failures(self):
        from ideer.scripts.migrate_meta_json import backfill_tools

        config = MagicMock()
        config.mcp_servers = {"broken": MagicMock()}
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=RuntimeError("database error"))

        with (
            patch("ideer.scripts.migrate_meta_json.ExtensionsConfig.from_file", return_value=config),
            patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=_make_mock_sf(mock_session)),
        ):
            report = await backfill_tools(default_owner="u1")

        assert report == {"imported": 0, "skipped": 0, "failed": 1}
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()


@pytest.mark.asyncio
class TestBackfillWorkflows:
    async def test_backfill_workflows_returns_zero_when_database_unavailable(self):
        from ideer.scripts.migrate_meta_json import backfill_workflows

        with patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=None):
            assert await backfill_workflows() == {"imported": 0, "skipped": 0, "failed": 0}

    async def test_backfill_workflows_returns_zero_when_no_definitions_exist(self):
        from ideer.scripts.migrate_meta_json import backfill_workflows

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(return_value=_Result(scalar_rows=[]))

        with patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=_make_mock_sf(mock_session)):
            assert await backfill_workflows() == {"imported": 0, "skipped": 0, "failed": 0}

    async def test_backfill_workflows_imports_missing_definitions_and_skips_existing(self):
        from ideer.scripts.migrate_meta_json import backfill_workflows

        created_at = datetime(2026, 1, 2, tzinfo=UTC)
        row_a = MagicMock(run_id="def:daily-report", created_at=created_at)
        row_b = MagicMock(run_id="def:existing-flow", created_at=created_at)
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=[
                _Result(scalar_rows=[row_a, row_b]),
                _Result(scalar_one=None),
                _Result(scalar_one=MagicMock()),
            ]
        )

        with patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=_make_mock_sf(mock_session)):
            report = await backfill_workflows(default_owner="u1")

        assert report == {"imported": 1, "skipped": 1, "failed": 0}
        added_resource = mock_session.add.call_args[0][0]
        assert added_resource.resource_type == "workflow"
        assert added_resource.resource_id == "daily-report"
        assert added_resource.owner_id == "u1"
        assert added_resource.visibility == "private"
        assert added_resource.created_at == created_at
        mock_session.commit.assert_awaited_once()

    async def test_backfill_workflows_counts_row_failures(self):
        from ideer.scripts.migrate_meta_json import backfill_workflows

        broken_row = MagicMock(run_id=None)
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[_Result(scalar_rows=[broken_row])])

        with patch("ideer.scripts.migrate_meta_json.get_session_factory", return_value=_make_mock_sf(mock_session)):
            report = await backfill_workflows(default_owner="u1")

        assert report == {"imported": 0, "skipped": 0, "failed": 1}
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()


class TestMain:
    def test_main_prints_combined_reports(self, capsys):
        from ideer.scripts import migrate_meta_json

        with (
            patch.object(sys, "argv", ["migrate_meta_json", "--dry-run"]),
            patch.object(migrate_meta_json, "migrate_meta_json", new=AsyncMock(return_value={"imported": 1})),
            patch.object(migrate_meta_json, "backfill_tools", new=AsyncMock(return_value={"skipped": 2})),
            patch.object(migrate_meta_json, "backfill_workflows", new=AsyncMock(return_value={"failed": 3})),
        ):
            migrate_meta_json.main()

        report = json.loads(capsys.readouterr().out)
        assert report == {
            "skill_agent": {"imported": 1},
            "tool_backfill": {"skipped": 2},
            "workflow_backfill": {"failed": 3},
        }
