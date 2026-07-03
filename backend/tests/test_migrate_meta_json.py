"""Tests for .meta.json to resource_metadata migration script."""

import json
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

        _write_skill_meta(skills_path, "dry-skill", {"name": "dry-skill", "visibility": "private"})

        mock_session = _make_mock_session()
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

    async def test_defaults_owner_to_super_admin_when_not_found(self, base_dir: Path, skills_path: Path):
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

        assert report["imported"] == 1
        assert report["owner_warned"] == 1
        added_resource = mock_session.add.call_args[0][0]
        assert added_resource.owner_id == "super_admin"

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

        assert report == {"imported": 0, "skipped": 0, "failed": 0, "owner_warned": 0}
        mock_sf.assert_not_called()

    async def test_imported_from_field_contains_file_path(self, base_dir: Path, skills_path: Path):
        from ideer.scripts.migrate_meta_json import migrate_meta_json

        meta_file = _write_skill_meta(skills_path, "trace-skill", {"name": "trace-skill", "visibility": "private"})

        mock_session = _make_mock_session()
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
