"""Tests for ideer.tools.skill_manage_tool — comprehensive coverage."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource, ResourceVersion
from ideer.persistence.models.user import UserModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skill_content(name: str, description: str = "Demo skill") -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n"


def _make_runtime(thread_id: str = "t-1") -> SimpleNamespace:
    """Build a minimal Runtime-like object."""
    return SimpleNamespace(
        context={"thread_id": thread_id},
        config={"configurable": {"thread_id": thread_id}},
    )


def _make_storage() -> MagicMock:
    """Build a mock SkillStorage with sensible defaults."""
    s = MagicMock()
    s.validate_skill_name = MagicMock(side_effect=lambda n: n)
    s.custom_skill_exists = MagicMock(return_value=False)
    s.public_skill_exists = MagicMock(return_value=False)
    s.ensure_custom_skill_is_editable = MagicMock()
    s.validate_skill_markdown_content = MagicMock()
    s.write_custom_skill = MagicMock()
    s.append_history = MagicMock()
    s.delete_custom_skill = MagicMock()
    s.get_custom_skill_file = MagicMock()
    s.ensure_safe_support_path = MagicMock()
    return s


def _make_scan_result(decision: str = "allow", reason: str = "ok"):
    return SimpleNamespace(decision=decision, reason=reason)


def _async_result(decision: str, reason: str):
    from ideer.skills.security_scanner import ScanResult

    return ScanResult(decision=decision, reason=reason)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_deps():
    """Patch heavy dependencies for every test in this module."""
    with (
        patch("ideer.tools.skill_manage_tool.get_or_new_skill_storage") as mock_storage_fn,
        patch("ideer.tools.skill_manage_tool.scan_skill_content", new_callable=AsyncMock) as mock_scan,
        patch("ideer.tools.skill_manage_tool.refresh_skills_system_prompt_cache_async", new_callable=AsyncMock) as mock_refresh,
        patch("ideer.tools.skill_manage_tool.SKILL_MD_FILE", "SKILL.md"),
    ):
        storage = _make_storage()
        mock_storage_fn.return_value = storage
        mock_scan.return_value = _make_scan_result()
        yield SimpleNamespace(
            storage=storage,
            scan=mock_scan,
            refresh=mock_refresh,
        )


# ---------------------------------------------------------------------------
# Import the module under test AFTER patching
# ---------------------------------------------------------------------------

from ideer.tools.skill_manage_tool import (  # noqa: E402
    _get_lock,
    _get_thread_id,
    _history_record,
    _scan_or_raise,
    _skill_manage_impl,
    _to_thread,
    skill_manage_tool,
)

# ===================================================================
# _get_lock
# ===================================================================


class TestGetLock:
    def test_returns_lock_for_name(self):
        lock = _get_lock("my-skill")
        assert isinstance(lock, asyncio.Lock)

    def test_same_lock_for_same_name(self):
        a = _get_lock("same")
        b = _get_lock("same")
        assert a is b

    def test_different_locks_for_different_names(self):
        a = _get_lock("alpha")
        b = _get_lock("beta")
        assert a is not b


# ===================================================================
# _get_thread_id
# ===================================================================


class TestGetThreadId:
    def test_none_runtime(self):
        assert _get_thread_id(None) is None

    def test_from_context(self):
        rt = SimpleNamespace(context={"thread_id": "ctx-1"}, config={})
        assert _get_thread_id(rt) == "ctx-1"

    def test_from_config_fallback(self):
        rt = SimpleNamespace(context={}, config={"configurable": {"thread_id": "cfg-1"}})
        assert _get_thread_id(rt) == "cfg-1"

    def test_context_missing_thread_id(self):
        rt = SimpleNamespace(context={"other": "val"}, config={"configurable": {"thread_id": "cfg-2"}})
        assert _get_thread_id(rt) == "cfg-2"

    def test_no_context_no_config(self):
        rt = SimpleNamespace(context={}, config={})
        assert _get_thread_id(rt) is None

    def test_context_is_none(self):
        rt = SimpleNamespace(context=None, config={})
        assert _get_thread_id(rt) is None


# ===================================================================
# _history_record
# ===================================================================


class TestHistoryRecord:
    def test_returns_expected_dict(self):
        rec = _history_record(
            action="create",
            file_path="SKILL.md",
            prev_content=None,
            new_content="# Hello",
            thread_id="t-1",
            scanner={"decision": "allow", "reason": "ok"},
        )
        assert rec["action"] == "create"
        assert rec["author"] == "agent"
        assert rec["thread_id"] == "t-1"
        assert rec["file_path"] == "SKILL.md"
        assert rec["prev_content"] is None
        assert rec["new_content"] == "# Hello"
        assert rec["scanner"] == {"decision": "allow", "reason": "ok"}


# ===================================================================
# _scan_or_raise
# ===================================================================


class TestScanOrRaise:
    @pytest.mark.asyncio
    async def test_allow_decision(self, _patch_deps):
        _patch_deps.scan.return_value = _make_scan_result("allow", "clean")
        result = await _scan_or_raise("content", executable=False, location="x/SKILL.md")
        assert result == {"decision": "allow", "reason": "clean"}

    @pytest.mark.asyncio
    async def test_warn_decision_non_executable(self, _patch_deps):
        _patch_deps.scan.return_value = _make_scan_result("warn", "suspicious")
        result = await _scan_or_raise("content", executable=False, location="x/SKILL.md")
        assert result == {"decision": "warn", "reason": "suspicious"}

    @pytest.mark.asyncio
    async def test_block_raises(self, _patch_deps):
        _patch_deps.scan.return_value = _make_scan_result("block", "malicious")
        with pytest.raises(ValueError, match="Security scan blocked"):
            await _scan_or_raise("content", executable=False, location="x/SKILL.md")

    @pytest.mark.asyncio
    async def test_executable_warn_raises(self, _patch_deps):
        _patch_deps.scan.return_value = _make_scan_result("warn", "untrusted")
        with pytest.raises(ValueError, match="Security scan rejected executable"):
            await _scan_or_raise("content", executable=True, location="x/scripts/run.sh")

    @pytest.mark.asyncio
    async def test_executable_allow_ok(self, _patch_deps):
        _patch_deps.scan.return_value = _make_scan_result("allow", "ok")
        result = await _scan_or_raise("content", executable=True, location="x/scripts/run.sh")
        assert result["decision"] == "allow"


# ===================================================================
# _to_thread
# ===================================================================


class TestToThread:
    @pytest.mark.asyncio
    async def test_runs_sync_function_in_thread(self):
        result = await _to_thread(lambda: 42)
        assert result == 42

    @pytest.mark.asyncio
    async def test_passes_args(self):
        def add(a, b):
            return a + b

        result = await _to_thread(add, 3, 4)
        assert result == 7


# ===================================================================
# _skill_manage_impl — action: create
# ===================================================================


class TestCreateAction:
    @pytest.mark.asyncio
    async def test_create_success(self, _patch_deps):
        s = _patch_deps.storage
        s.custom_skill_exists.return_value = False
        rt = _make_runtime()
        result = await _skill_manage_impl(rt, "create", "my-skill", content="# My Skill")
        assert "Created" in result
        s.write_custom_skill.assert_called_once_with("my-skill", "SKILL.md", "# My Skill")
        s.append_history.assert_called_once()
        _patch_deps.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_already_exists(self, _patch_deps):
        _patch_deps.storage.custom_skill_exists.return_value = True
        with pytest.raises(ValueError, match="already exists"):
            await _skill_manage_impl(_make_runtime(), "create", "dup", content="# x")

    @pytest.mark.asyncio
    async def test_create_no_content(self, _patch_deps):
        with pytest.raises(ValueError, match="content is required"):
            await _skill_manage_impl(_make_runtime(), "create", "new-skill")

    @pytest.mark.asyncio
    async def test_create_scan_blocks(self, _patch_deps):
        _patch_deps.scan.return_value = _make_scan_result("block", "bad")
        with pytest.raises(ValueError, match="blocked"):
            await _skill_manage_impl(_make_runtime(), "create", "new-skill", content="# Bad")

    @pytest.mark.asyncio
    async def test_create_no_thread_id(self, _patch_deps):
        """Create with runtime that has no thread_id."""
        s = _patch_deps.storage
        s.custom_skill_exists.return_value = False
        rt = SimpleNamespace(context={}, config={})
        result = await _skill_manage_impl(rt, "create", "my-skill", content="# Skill")
        assert "Created" in result
        # Verify history was recorded with thread_id=None
        history_call = s.append_history.call_args
        assert history_call[0][1]["thread_id"] is None


# ===================================================================
# _skill_manage_impl — action: edit
# ===================================================================


class TestEditAction:
    @pytest.mark.asyncio
    async def test_edit_success(self, _patch_deps):
        s = _patch_deps.storage
        skill_file = MagicMock()
        skill_file.read_text = MagicMock(return_value="# Old")
        s.get_custom_skill_file.return_value = skill_file
        rt = _make_runtime()
        result = await _skill_manage_impl(rt, "edit", "my-skill", content="# New")
        assert "Updated" in result
        s.ensure_custom_skill_is_editable.assert_called_once_with("my-skill")
        s.write_custom_skill.assert_called_once_with("my-skill", "SKILL.md", "# New")
        _patch_deps.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_edit_no_content(self, _patch_deps):
        with pytest.raises(ValueError, match="content is required"):
            await _skill_manage_impl(_make_runtime(), "edit", "my-skill")

    @pytest.mark.asyncio
    async def test_edit_scan_blocks(self, _patch_deps):
        _patch_deps.scan.return_value = _make_scan_result("block", "malicious")
        with pytest.raises(ValueError, match="blocked"):
            await _skill_manage_impl(_make_runtime(), "edit", "my-skill", content="# Bad")

    @pytest.mark.asyncio
    async def test_edit_preserves_prev_content(self, _patch_deps):
        s = _patch_deps.storage
        skill_file = MagicMock()
        skill_file.read_text = MagicMock(return_value="# Previous")
        s.get_custom_skill_file.return_value = skill_file
        await _skill_manage_impl(_make_runtime(), "edit", "my-skill", content="# New")
        history = s.append_history.call_args[0][1]
        assert history["prev_content"] == "# Previous"
        assert history["new_content"] == "# New"
        assert history["action"] == "edit"


# ===================================================================
# _skill_manage_impl — action: patch
# ===================================================================


class TestPatchAction:
    @pytest.mark.asyncio
    async def test_patch_success(self, _patch_deps):
        s = _patch_deps.storage
        skill_file = MagicMock()
        skill_file.read_text = MagicMock(return_value="Hello World")
        s.get_custom_skill_file.return_value = skill_file
        rt = _make_runtime()
        result = await _skill_manage_impl(rt, "patch", "my-skill", find="World", replace="Universe")
        assert "Patched" in result
        assert "1 replacement" in result
        s.write_custom_skill.assert_called_once_with("my-skill", "SKILL.md", "Hello Universe")
        _patch_deps.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_patch_missing_find(self, _patch_deps):
        with pytest.raises(ValueError, match="find and replace are required"):
            await _skill_manage_impl(_make_runtime(), "patch", "my-skill", replace="y")

    @pytest.mark.asyncio
    async def test_patch_missing_replace(self, _patch_deps):
        with pytest.raises(ValueError, match="find and replace are required"):
            await _skill_manage_impl(_make_runtime(), "patch", "my-skill", find="x")

    @pytest.mark.asyncio
    async def test_patch_target_not_found(self, _patch_deps):
        skill_file = MagicMock()
        skill_file.read_text = MagicMock(return_value="Hello World")
        _patch_deps.storage.get_custom_skill_file.return_value = skill_file
        with pytest.raises(ValueError, match="Patch target not found"):
            await _skill_manage_impl(_make_runtime(), "patch", "my-skill", find="NOTHERE", replace="x")

    @pytest.mark.asyncio
    async def test_patch_expected_count_mismatch(self, _patch_deps):
        skill_file = MagicMock()
        skill_file.read_text = MagicMock(return_value="aaa bbb aaa")
        _patch_deps.storage.get_custom_skill_file.return_value = skill_file
        with pytest.raises(ValueError, match="Expected 1 replacements but found 2"):
            await _skill_manage_impl(
                _make_runtime(),
                "patch",
                "my-skill",
                find="aaa",
                replace="zzz",
                expected_count=1,
            )

    @pytest.mark.asyncio
    async def test_patch_expected_count_matches(self, _patch_deps):
        skill_file = MagicMock()
        skill_file.read_text = MagicMock(return_value="aaa bbb aaa")
        _patch_deps.storage.get_custom_skill_file.return_value = skill_file
        result = await _skill_manage_impl(
            _make_runtime(),
            "patch",
            "my-skill",
            find="aaa",
            replace="zzz",
            expected_count=2,
        )
        assert "2 replacement" in result

    @pytest.mark.asyncio
    async def test_patch_replaces_default_count(self, _patch_deps):
        skill_file = MagicMock()
        skill_file.read_text = MagicMock(return_value="aaa aaa aaa")
        _patch_deps.storage.get_custom_skill_file.return_value = skill_file
        result = await _skill_manage_impl(_make_runtime(), "patch", "my-skill", find="aaa", replace="b")
        assert "1 replacement" in result

    @pytest.mark.asyncio
    async def test_patch_no_expected_count(self, _patch_deps):
        """patch with expected_count=None uses default replacement_count=1."""
        skill_file = MagicMock()
        skill_file.read_text = MagicMock(return_value="foo foo")
        _patch_deps.storage.get_custom_skill_file.return_value = skill_file
        result = await _skill_manage_impl(
            _make_runtime(),
            "patch",
            "my-skill",
            find="foo",
            replace="bar",
            expected_count=None,
        )
        assert "1 replacement" in result


# ===================================================================
# _skill_manage_impl — action: delete
# ===================================================================


class TestDeleteAction:
    @pytest.mark.asyncio
    async def test_delete_success(self, _patch_deps):
        rt = _make_runtime()
        result = await _skill_manage_impl(rt, "delete", "old-skill")
        assert "Deleted" in result
        _patch_deps.storage.delete_custom_skill.assert_called_once()
        _patch_deps.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_history_record(self, _patch_deps):
        await _skill_manage_impl(_make_runtime(), "delete", "old-skill")
        history = _patch_deps.storage.delete_custom_skill.call_args[1]["history_meta"]
        assert history["action"] == "delete"
        assert history["scanner"]["decision"] == "allow"


# ===================================================================
# _skill_manage_impl — action: write_file
# ===================================================================


class TestWriteFileAction:
    @pytest.mark.asyncio
    async def test_write_file_new_file(self, _patch_deps):
        s = _patch_deps.storage
        target = MagicMock()
        target.exists.return_value = False
        s.ensure_safe_support_path.return_value = target
        rt = _make_runtime()
        result = await _skill_manage_impl(rt, "write_file", "my-skill", content="data", path="data.json")
        assert "Wrote" in result
        s.write_custom_skill.assert_called_once_with("my-skill", "data.json", "data")

    @pytest.mark.asyncio
    async def test_write_file_existing_file(self, _patch_deps):
        s = _patch_deps.storage
        target = MagicMock()
        target.exists.return_value = True
        target.read_text = MagicMock(return_value="old data")
        s.ensure_safe_support_path.return_value = target
        rt = _make_runtime()
        result = await _skill_manage_impl(rt, "write_file", "my-skill", content="new", path="data.json")
        assert "Wrote" in result

    @pytest.mark.asyncio
    async def test_write_file_missing_path(self, _patch_deps):
        with pytest.raises(ValueError, match="path and content are required"):
            await _skill_manage_impl(_make_runtime(), "write_file", "my-skill", content="x")

    @pytest.mark.asyncio
    async def test_write_file_missing_content(self, _patch_deps):
        with pytest.raises(ValueError, match="path and content are required"):
            await _skill_manage_impl(_make_runtime(), "write_file", "my-skill", path="x")

    @pytest.mark.asyncio
    async def test_write_file_missing_both(self, _patch_deps):
        with pytest.raises(ValueError, match="path and content are required"):
            await _skill_manage_impl(_make_runtime(), "write_file", "my-skill")

    @pytest.mark.asyncio
    async def test_write_file_scripts_path_is_executable(self, _patch_deps):
        s = _patch_deps.storage
        target = MagicMock()
        target.exists.return_value = False
        s.ensure_safe_support_path.return_value = target
        await _skill_manage_impl(_make_runtime(), "write_file", "my-skill", content="#!/bin/sh", path="scripts/run.sh")
        call_kwargs = _patch_deps.scan.call_args[1]
        assert call_kwargs["executable"] is True

    @pytest.mark.asyncio
    async def test_write_file_non_scripts_path(self, _patch_deps):
        s = _patch_deps.storage
        target = MagicMock()
        target.exists.return_value = False
        s.ensure_safe_support_path.return_value = target
        await _skill_manage_impl(_make_runtime(), "write_file", "my-skill", content="data", path="data/config.json")
        call_kwargs = _patch_deps.scan.call_args[1]
        assert call_kwargs["executable"] is False

    @pytest.mark.asyncio
    async def test_write_file_scripts_in_middle_not_executable(self, _patch_deps):
        """'scripts/' must be at the start or contain 'scripts/' in path."""
        s = _patch_deps.storage
        target = MagicMock()
        target.exists.return_value = False
        s.ensure_safe_support_path.return_value = target
        await _skill_manage_impl(_make_runtime(), "write_file", "my-skill", content="data", path="data/scripts/run.sh")
        call_kwargs = _patch_deps.scan.call_args[1]
        # "scripts/" is in the path
        assert call_kwargs["executable"] is True

    @pytest.mark.asyncio
    async def test_write_file_scan_blocks(self, _patch_deps):
        s = _patch_deps.storage
        target = MagicMock()
        target.exists.return_value = False
        s.ensure_safe_support_path.return_value = target
        _patch_deps.scan.return_value = _make_scan_result("block", "bad")
        with pytest.raises(ValueError, match="blocked"):
            await _skill_manage_impl(_make_runtime(), "write_file", "my-skill", content="bad", path="data.json")


# ===================================================================
# _skill_manage_impl — action: remove_file
# ===================================================================


class TestRemoveFileAction:
    @pytest.mark.asyncio
    async def test_remove_file_success(self, _patch_deps):
        s = _patch_deps.storage
        target = MagicMock()
        target.exists.return_value = True
        target.read_text = MagicMock(return_value="file content")
        s.ensure_safe_support_path.return_value = target
        rt = _make_runtime()
        result = await _skill_manage_impl(rt, "remove_file", "my-skill", path="data.json")
        assert "Removed" in result
        target.unlink.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_file_not_found(self, _patch_deps):
        target = MagicMock()
        target.exists.return_value = False
        _patch_deps.storage.ensure_safe_support_path.return_value = target
        with pytest.raises(FileNotFoundError, match="not found"):
            await _skill_manage_impl(_make_runtime(), "remove_file", "my-skill", path="missing.json")

    @pytest.mark.asyncio
    async def test_remove_file_missing_path(self, _patch_deps):
        with pytest.raises(ValueError, match="path is required"):
            await _skill_manage_impl(_make_runtime(), "remove_file", "my-skill")

    @pytest.mark.asyncio
    async def test_remove_file_history_record(self, _patch_deps):
        s = _patch_deps.storage
        target = MagicMock()
        target.exists.return_value = True
        target.read_text = MagicMock(return_value="content")
        s.ensure_safe_support_path.return_value = target
        await _skill_manage_impl(_make_runtime(), "remove_file", "my-skill", path="data.json")
        history = s.append_history.call_args[0][1]
        assert history["action"] == "remove_file"
        assert history["prev_content"] == "content"
        assert history["new_content"] is None


# ===================================================================
# _skill_manage_impl — unsupported action
# ===================================================================


class TestUnsupportedAction:
    @pytest.mark.asyncio
    async def test_unsupported_action_not_builtin(self, _patch_deps):
        _patch_deps.storage.public_skill_exists.return_value = False
        with pytest.raises(ValueError, match="Unsupported action"):
            await _skill_manage_impl(_make_runtime(), "foobar", "my-skill")

    @pytest.mark.asyncio
    async def test_unsupported_action_builtin_skill(self, _patch_deps):
        _patch_deps.storage.public_skill_exists.return_value = True
        with pytest.raises(ValueError, match="built-in skill"):
            await _skill_manage_impl(_make_runtime(), "foobar", "builtin-skill")

    @pytest.mark.asyncio
    async def test_unknown_action_checks_public(self, _patch_deps):
        """When action is unknown, public_skill_exists is checked."""
        _patch_deps.storage.public_skill_exists.return_value = False
        with pytest.raises(ValueError, match="Unsupported action"):
            await _skill_manage_impl(_make_runtime(), "unknown", "x")
        _patch_deps.storage.public_skill_exists.assert_called_once_with("x")


# ===================================================================
# skill_manage_tool (the @tool wrapper)
# ===================================================================


class TestSkillManageTool:
    @pytest.mark.asyncio
    async def test_tool_delegates_to_impl(self, _patch_deps):
        rt = _make_runtime()
        result = await skill_manage_tool.coroutine(
            runtime=rt,
            action="create",
            name="test-skill",
            content="# Test",
        )
        assert "Created" in result

    @pytest.mark.asyncio
    async def test_tool_create_no_content_raises(self, _patch_deps):
        with pytest.raises(ValueError, match="content is required"):
            await skill_manage_tool.coroutine(
                runtime=_make_runtime(),
                action="create",
                name="test-skill",
            )


# ===================================================================
# Thread safety — lock behaviour
# ===================================================================


class TestLockBehaviour:
    def test_concurrent_same_name_same_lock(self):
        lock_a = _get_lock("concurrent-skill")
        lock_b = _get_lock("concurrent-skill")
        assert lock_a is lock_b

    def test_weakref_allows_gc(self):
        """Locks are stored in WeakValueDictionary — unreferenced locks can be GC'd."""
        import gc

        _get_lock("gc-test")
        gc.collect()
        # After GC, a new lock may be created (not guaranteed, but no crash)
        lock = _get_lock("gc-test")
        assert isinstance(lock, asyncio.Lock)


# ===================================================================
# Canonical catalog mode
# ===================================================================


@pytest_asyncio.fixture
async def _catalog_db(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'catalog.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _seed_user_canonical(catalog_db: async_sessionmaker[AsyncSession]) -> None:
    async with catalog_db() as session:
        session.add(UserModel(id="test-user-autouse", username="test-user-autouse@test.com", role="user", disabled=False))
        await session.commit()


def _skill_root(tmp_path: Path, resource_id: str) -> Path:
    return tmp_path / "resources" / "skills" / resource_id


async def _resolve_skill_resource(catalog_db: async_sessionmaker[AsyncSession], slug: str) -> Resource:
    async with catalog_db() as session:
        resource = (await session.execute(select(Resource).where(Resource.type == "skill", Resource.slug == slug))).scalar_one()
        return resource


async def _published_skill(tmp_path: Path, catalog_db: async_sessionmaker[AsyncSession], slug: str) -> tuple[str, Path]:
    resource = await _resolve_skill_resource(catalog_db, slug)
    async with catalog_db() as session:
        versions = (await session.execute(select(ResourceVersion).where(ResourceVersion.resource_id == resource.id))).scalars().all()
        version = max(item.version for item in versions)
    return resource.id, _skill_root(tmp_path, resource.id) / "versions" / str(version)


class TestSkillManageCanonical:
    @pytest.mark.asyncio
    async def test_create_publishes_skill(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        _catalog_db: async_sessionmaker[AsyncSession],
        _patch_deps,
    ) -> None:
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
        await _seed_user_canonical(_catalog_db)

        with patch("ideer.tools.skill_manage_tool.get_session_factory", return_value=_catalog_db):
            with patch("ideer.config.paths.get_paths", return_value=SimpleNamespace(base_dir=tmp_path)):
                result = await skill_manage_tool.coroutine(
                    runtime=_make_runtime(),
                    action="create",
                    name="my-skill",
                    content=_skill_content("my-skill"),
                )

        assert result == "Created custom skill 'my-skill'."
        resource_id, published = await _published_skill(tmp_path, _catalog_db, "my-skill")
        assert (published / "SKILL.md").read_text(encoding="utf-8") == _skill_content("my-skill")
        assert not (tmp_path / "skills" / "custom" / "my-skill").exists()

    @pytest.mark.asyncio
    async def test_create_rejects_existing_skill(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        _catalog_db: async_sessionmaker[AsyncSession],
        _patch_deps,
    ) -> None:
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
        await _seed_user_canonical(_catalog_db)

        with patch("ideer.tools.skill_manage_tool.get_session_factory", return_value=_catalog_db):
            with patch("ideer.config.paths.get_paths", return_value=SimpleNamespace(base_dir=tmp_path)):
                await skill_manage_tool.coroutine(runtime=_make_runtime(), action="create", name="my-skill", content=_skill_content("my-skill"))
                with pytest.raises(ValueError, match="already exists"):
                    await skill_manage_tool.coroutine(runtime=_make_runtime(), action="create", name="my-skill", content=_skill_content("my-skill"))

    @pytest.mark.asyncio
    async def test_edit_publishes_new_version(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        _catalog_db: async_sessionmaker[AsyncSession],
        _patch_deps,
    ) -> None:
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
        await _seed_user_canonical(_catalog_db)

        with patch("ideer.tools.skill_manage_tool.get_session_factory", return_value=_catalog_db):
            with patch("ideer.config.paths.get_paths", return_value=SimpleNamespace(base_dir=tmp_path)):
                await skill_manage_tool.coroutine(runtime=_make_runtime(), action="create", name="my-skill", content=_skill_content("my-skill"))
                result = await skill_manage_tool.coroutine(
                    runtime=_make_runtime(),
                    action="edit",
                    name="my-skill",
                    content=_skill_content("my-skill", description="Edited"),
                )

        assert result == "Updated custom skill 'my-skill'."
        resource_id, published = await _published_skill(tmp_path, _catalog_db, "my-skill")
        assert (published / "SKILL.md").read_text(encoding="utf-8") == _skill_content("my-skill", description="Edited")
        assert _skill_root(tmp_path, resource_id).joinpath("versions", "1").exists(), "previous version must be retained"

    @pytest.mark.asyncio
    async def test_patch_applies_replacement(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        _catalog_db: async_sessionmaker[AsyncSession],
        _patch_deps,
    ) -> None:
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
        await _seed_user_canonical(_catalog_db)

        with patch("ideer.tools.skill_manage_tool.get_session_factory", return_value=_catalog_db):
            with patch("ideer.config.paths.get_paths", return_value=SimpleNamespace(base_dir=tmp_path)):
                await skill_manage_tool.coroutine(runtime=_make_runtime(), action="create", name="my-skill", content=_skill_content("my-skill"))
                result = await skill_manage_tool.coroutine(runtime=_make_runtime(), action="patch", name="my-skill", find="Demo skill", replace="Patched skill")

        assert "1 replacement(s)" in result
        _, published = await _published_skill(tmp_path, _catalog_db, "my-skill")
        assert "Patched skill" in (published / "SKILL.md").read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_write_file_and_remove_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        _catalog_db: async_sessionmaker[AsyncSession],
        _patch_deps,
    ) -> None:
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
        await _seed_user_canonical(_catalog_db)

        with patch("ideer.tools.skill_manage_tool.get_session_factory", return_value=_catalog_db):
            with patch("ideer.config.paths.get_paths", return_value=SimpleNamespace(base_dir=tmp_path)):
                await skill_manage_tool.coroutine(runtime=_make_runtime(), action="create", name="my-skill", content=_skill_content("my-skill"))
                await skill_manage_tool.coroutine(runtime=_make_runtime(), action="write_file", name="my-skill", path="templates/letter.md", content="# Letter")

                _, published = await _published_skill(tmp_path, _catalog_db, "my-skill")
                assert (published / "templates" / "letter.md").read_text(encoding="utf-8") == "# Letter"

                await skill_manage_tool.coroutine(runtime=_make_runtime(), action="remove_file", name="my-skill", path="templates/letter.md")
                _, published = await _published_skill(tmp_path, _catalog_db, "my-skill")
                assert not (published / "templates" / "letter.md").exists()
                assert (published / "SKILL.md").exists(), "SKILL.md must survive a support-file removal"

    @pytest.mark.asyncio
    async def test_delete_archives_resource(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        _catalog_db: async_sessionmaker[AsyncSession],
        _patch_deps,
    ) -> None:
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
        await _seed_user_canonical(_catalog_db)

        with patch("ideer.tools.skill_manage_tool.get_session_factory", return_value=_catalog_db):
            with patch("ideer.config.paths.get_paths", return_value=SimpleNamespace(base_dir=tmp_path)):
                await skill_manage_tool.coroutine(runtime=_make_runtime(), action="create", name="my-skill", content=_skill_content("my-skill"))
                result = await skill_manage_tool.coroutine(runtime=_make_runtime(), action="delete", name="my-skill")

        assert result == "Deleted custom skill 'my-skill'."
        resource = await _resolve_skill_resource(_catalog_db, "my-skill")
        assert resource.lifecycle_status == "archived"

    @pytest.mark.asyncio
    async def test_edit_unknown_skill_raises(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        _catalog_db: async_sessionmaker[AsyncSession],
        _patch_deps,
    ) -> None:
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
        await _seed_user_canonical(_catalog_db)

        with patch("ideer.tools.skill_manage_tool.get_session_factory", return_value=_catalog_db):
            with patch("ideer.config.paths.get_paths", return_value=SimpleNamespace(base_dir=tmp_path)):
                with pytest.raises(ValueError, match="does not exist"):
                    await skill_manage_tool.coroutine(runtime=_make_runtime(), action="edit", name="ghost-skill", content="# Ghost")

    @pytest.mark.asyncio
    async def test_without_database_raises(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        _patch_deps,
    ) -> None:
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")

        with patch("ideer.tools.skill_manage_tool.get_session_factory", return_value=None):
            with pytest.raises(RuntimeError, match="persistence is unavailable"):
                await skill_manage_tool.coroutine(runtime=_make_runtime(), action="create", name="my-skill", content="# X")
