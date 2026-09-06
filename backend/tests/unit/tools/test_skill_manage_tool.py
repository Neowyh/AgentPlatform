"""Tests for deerflow.tools.skill_manage_tool — comprehensive coverage."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skill_content(name: str, description: str = "Demo skill") -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n"


def _make_runtime(thread_id: str = "t-1", user_id: str = "test-user") -> SimpleNamespace:
    """Build a minimal Runtime-like object."""
    return SimpleNamespace(
        context={"thread_id": thread_id, "user_id": user_id},
        config={"configurable": {"thread_id": thread_id}},
    )


def _make_scan_result(decision: str = "allow", reason: str = "ok"):
    return SimpleNamespace(decision=decision, reason=reason)


def _user_custom_root(tmp_path: Path) -> Path:
    """Custom-skill root for the test user inside the isolated base dir."""
    return tmp_path / "users" / "test-user" / "skills" / "custom"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_deps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolate config paths and patch the async/model dependencies.

    The storage itself stays real (UserScopedSkillStorage over tmp_path) so the
    tool's filesystem behaviour is exercised end to end; only the LLM security
    scan and the prompt-cache refresh are mocked.
    """
    from deerflow.config.paths import Paths
    from deerflow.skills.storage.user_scoped_skill_storage import UserScopedSkillStorage

    paths = Paths(base_dir=tmp_path)
    monkeypatch.setattr("deerflow.config.paths.get_paths", lambda: paths)
    storage = UserScopedSkillStorage("test-user", host_path=str(tmp_path))

    with (
        patch("deerflow.tools.skill_manage_tool.get_or_new_user_skill_storage", return_value=storage),
        patch("deerflow.tools.skill_manage_tool.scan_skill_content", new_callable=AsyncMock) as mock_scan,
        patch("deerflow.tools.skill_manage_tool.refresh_user_skills_system_prompt_cache_async", new_callable=AsyncMock) as mock_refresh,
    ):
        mock_scan.return_value = _make_scan_result()
        yield SimpleNamespace(
            storage=storage,
            scan=mock_scan,
            refresh=mock_refresh,
        )


# ---------------------------------------------------------------------------
# Import the module under test AFTER patching
# ---------------------------------------------------------------------------

from deerflow.tools.skill_manage_tool import (  # noqa: E402
    _get_lock,
    _get_thread_id,
    _history_record,
    _scan_or_raise,
    _to_thread,
    skill_manage_tool,
)

# ===================================================================
# _get_lock
# ===================================================================


class TestGetLock:
    def test_returns_lock_for_name(self):
        lock = _get_lock("test-user", "my-skill")
        assert isinstance(lock, asyncio.Lock)

    def test_same_lock_for_same_name(self):
        a = _get_lock("test-user", "same")
        b = _get_lock("test-user", "same")
        assert a is b

    def test_different_locks_for_different_names(self):
        a = _get_lock("test-user", "alpha")
        b = _get_lock("test-user", "beta")
        assert a is not b

    def test_different_locks_for_different_users(self):
        """Lock granularity is (user_id, skill_name) to avoid cross-user blocking."""
        a = _get_lock("user-1", "shared")
        b = _get_lock("user-2", "shared")
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

    def test_concurrent_same_name_same_lock(self):
        lock_a = _get_lock("test-user", "concurrent-skill")
        lock_b = _get_lock("test-user", "concurrent-skill")
        assert lock_a is lock_b

    def test_weakref_allows_gc(self):
        """Locks are stored in WeakValueDictionary — unreferenced locks can be GC'd."""
        import gc

        _get_lock("test-user", "gc-test")
        gc.collect()
        # After GC, a new lock may be created (not guaranteed, but no crash)
        lock = _get_lock("test-user", "gc-test")
        assert isinstance(lock, asyncio.Lock)


# ===================================================================
# skill_manage_tool — filesystem behaviour via a real user-scoped storage
# ===================================================================


class TestSkillManageFilesystem:
    @pytest.mark.asyncio
    async def test_create_publishes_skill(self, tmp_path: Path) -> None:
        result = await skill_manage_tool.coroutine(
            runtime=_make_runtime(),
            action="create",
            name="my-skill",
            content=_skill_content("my-skill"),
        )

        assert result == "Created custom skill 'my-skill'."
        published = _user_custom_root(tmp_path) / "my-skill" / "SKILL.md"
        assert published.read_text(encoding="utf-8") == _skill_content("my-skill")

    @pytest.mark.asyncio
    async def test_create_rejects_existing_skill(self) -> None:
        await skill_manage_tool.coroutine(runtime=_make_runtime(), action="create", name="my-skill", content=_skill_content("my-skill"))
        with pytest.raises(ValueError, match="already exists"):
            await skill_manage_tool.coroutine(runtime=_make_runtime(), action="create", name="my-skill", content=_skill_content("my-skill"))

    @pytest.mark.asyncio
    async def test_edit_updates_skill_and_records_history(self, _patch_deps) -> None:
        await skill_manage_tool.coroutine(runtime=_make_runtime(), action="create", name="my-skill", content=_skill_content("my-skill"))
        result = await skill_manage_tool.coroutine(
            runtime=_make_runtime(),
            action="edit",
            name="my-skill",
            content=_skill_content("my-skill", description="Edited"),
        )

        assert result == "Updated custom skill 'my-skill'."
        history = _patch_deps.storage.read_history("my-skill")
        assert [record["action"] for record in history] == ["create", "edit"], "previous version must be retained in history"
        assert history[-1]["prev_content"] == _skill_content("my-skill")

    @pytest.mark.asyncio
    async def test_patch_applies_replacement(self, tmp_path: Path) -> None:
        await skill_manage_tool.coroutine(runtime=_make_runtime(), action="create", name="my-skill", content=_skill_content("my-skill"))
        result = await skill_manage_tool.coroutine(runtime=_make_runtime(), action="patch", name="my-skill", find="Demo skill", replace="Patched skill")

        assert "1 replacement(s)" in result
        published = _user_custom_root(tmp_path) / "my-skill" / "SKILL.md"
        assert "Patched skill" in published.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_write_file_and_remove_file(self, tmp_path: Path) -> None:
        await skill_manage_tool.coroutine(runtime=_make_runtime(), action="create", name="my-skill", content=_skill_content("my-skill"))
        await skill_manage_tool.coroutine(runtime=_make_runtime(), action="write_file", name="my-skill", path="templates/letter.md", content="# Letter")

        skill_dir = _user_custom_root(tmp_path) / "my-skill"
        assert (skill_dir / "templates" / "letter.md").read_text(encoding="utf-8") == "# Letter"

        await skill_manage_tool.coroutine(runtime=_make_runtime(), action="remove_file", name="my-skill", path="templates/letter.md")
        assert not (skill_dir / "templates" / "letter.md").exists()
        assert (skill_dir / "SKILL.md").exists(), "SKILL.md must survive a support-file removal"

    @pytest.mark.asyncio
    async def test_delete_removes_custom_skill(self, tmp_path: Path) -> None:
        await skill_manage_tool.coroutine(runtime=_make_runtime(), action="create", name="my-skill", content=_skill_content("my-skill"))
        result = await skill_manage_tool.coroutine(runtime=_make_runtime(), action="delete", name="my-skill")

        assert result == "Deleted custom skill 'my-skill'."
        assert not (_user_custom_root(tmp_path) / "my-skill").exists()

    @pytest.mark.asyncio
    async def test_edit_unknown_skill_raises(self) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            await skill_manage_tool.coroutine(runtime=_make_runtime(), action="edit", name="ghost-skill", content="# Ghost")

    @pytest.mark.asyncio
    async def test_unsupported_action_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported action"):
            await skill_manage_tool.coroutine(runtime=_make_runtime(), action="frobnicate", name="my-skill")
