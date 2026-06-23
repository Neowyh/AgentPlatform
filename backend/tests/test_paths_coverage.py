"""Extended coverage tests for ideer.config.paths module.

Targets the uncovered lines in host_base_dir, _host_base_dir_str,
_join_host_path (Windows paths), _validate_thread_id, _validate_user_id,
ensure_thread_dirs, delete_thread_dir, resolve_virtual_path,
get_paths singleton, and resolve_path.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ideer.config.paths import (
    Paths,
    _join_host_path,
    _validate_thread_id,
    _validate_user_id,
    get_paths,
    resolve_path,
)


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    return Paths(tmp_path)


# ---------------------------------------------------------------------------
# _validate_thread_id
# ---------------------------------------------------------------------------


class TestValidateThreadId:
    def test_valid_thread_ids(self):
        for tid in ["abc", "thread-1", "t_123", "A-B-C-123"]:
            assert _validate_thread_id(tid) == tid

    def test_invalid_thread_id_raises(self):
        with pytest.raises(ValueError, match="Invalid thread_id"):
            _validate_thread_id("../escape")
        with pytest.raises(ValueError, match="Invalid thread_id"):
            _validate_thread_id("a/b")
        with pytest.raises(ValueError, match="Invalid thread_id"):
            _validate_thread_id("")


# ---------------------------------------------------------------------------
# _validate_user_id
# ---------------------------------------------------------------------------


class TestValidateUserIdExtended:
    def test_valid_user_ids(self):
        for uid in ["alice", "user-123", "u_abc"]:
            assert _validate_user_id(uid) == uid

    def test_invalid_user_id_raises(self):
        with pytest.raises(ValueError, match="Invalid user_id"):
            _validate_user_id("../../../etc")
        with pytest.raises(ValueError, match="Invalid user_id"):
            _validate_user_id("user/name")
        with pytest.raises(ValueError, match="Invalid user_id"):
            _validate_user_id("")


# ---------------------------------------------------------------------------
# _join_host_path - Windows-style paths
# ---------------------------------------------------------------------------


class TestJoinHostPath:
    def test_posix_base(self):
        result = _join_host_path("/home/user", "threads", "t1")
        assert result == "/home/user/threads/t1"

    def test_windows_drive_letter(self):
        result = _join_host_path("C:\\Users\\me", "threads", "t1")
        assert "C:" in result
        assert "Users" in result
        assert "threads" in result
        assert "t1" in result

    def test_windows_unc_path(self):
        result = _join_host_path("\\\\server\\share", "dir", "file")
        assert "\\\\" in result or "server" in result

    def test_empty_parts_returns_base(self):
        result = _join_host_path("/some/base")
        assert result == "/some/base"

    def test_windows_backslash_in_base(self):
        result = _join_host_path("D:\\projects\\backend", "users", "u1", "threads", "t1")
        assert "D:" in result
        assert "users" in result
        assert "u1" in result
        assert "threads" in result
        assert "t1" in result


# ---------------------------------------------------------------------------
# host_base_dir and _host_base_dir_str
# ---------------------------------------------------------------------------


class TestHostBaseDir:
    def test_falls_back_to_base_dir(self, paths: Paths):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IDEER_HOST_BASE_DIR", None)
            assert paths.host_base_dir == paths.base_dir

    def test_uses_env_var(self, paths: Paths, monkeypatch):
        monkeypatch.setenv("IDEER_HOST_BASE_DIR", "/host/path")
        assert paths.host_base_dir == Path("/host/path")

    def test_host_base_dir_str_falls_back(self, paths: Paths):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IDEER_HOST_BASE_DIR", None)
            assert paths._host_base_dir_str() == str(paths.base_dir)

    def test_host_base_dir_str_uses_env(self, paths: Paths, monkeypatch):
        monkeypatch.setenv("IDEER_HOST_BASE_DIR", "/host/path")
        assert paths._host_base_dir_str() == "/host/path"


# ---------------------------------------------------------------------------
# Paths properties
# ---------------------------------------------------------------------------


class TestPathsProperties:
    def test_memory_file(self, paths: Paths):
        assert paths.memory_file == paths.base_dir / "memory.json"

    def test_user_md_file(self, paths: Paths):
        assert paths.user_md_file == paths.base_dir / "USER.md"

    def test_agents_dir(self, paths: Paths):
        assert paths.agents_dir == paths.base_dir / "agents"

    def test_agent_dir(self, paths: Paths):
        assert paths.agent_dir("my-agent") == paths.base_dir / "agents" / "my-agent"

    def test_agent_dir_lowercases(self, paths: Paths):
        assert paths.agent_dir("MyAgent") == paths.base_dir / "agents" / "myagent"

    def test_agent_memory_file(self, paths: Paths):
        assert paths.agent_memory_file("test") == paths.base_dir / "agent-memory" / "test" / "memory.json"

    def test_legacy_agent_memory_file(self, paths: Paths):
        assert paths.legacy_agent_memory_file("test") == paths.base_dir / "agents" / "test" / "memory.json"


# ---------------------------------------------------------------------------
# host_* path methods
# ---------------------------------------------------------------------------


class TestHostPathMethods:
    def test_host_thread_dir_legacy(self, paths: Paths):
        result = paths.host_thread_dir("t1")
        assert "threads" in result
        assert "t1" in result
        assert "users" not in result

    def test_host_thread_dir_with_user(self, paths: Paths):
        result = paths.host_thread_dir("t1", user_id="u1")
        assert "users" in result
        assert "u1" in result
        assert "threads" in result

    def test_host_sandbox_user_data_dir(self, paths: Paths):
        result = paths.host_sandbox_user_data_dir("t1")
        assert "user-data" in result

    def test_host_sandbox_work_dir(self, paths: Paths):
        result = paths.host_sandbox_work_dir("t1")
        assert "workspace" in result

    def test_host_sandbox_uploads_dir(self, paths: Paths):
        result = paths.host_sandbox_uploads_dir("t1")
        assert "uploads" in result

    def test_host_sandbox_outputs_dir(self, paths: Paths):
        result = paths.host_sandbox_outputs_dir("t1")
        assert "outputs" in result

    def test_host_acp_workspace_dir(self, paths: Paths):
        result = paths.host_acp_workspace_dir("t1")
        assert "acp-workspace" in result

    def test_host_sandbox_user_data_dir_with_user(self, paths: Paths):
        result = paths.host_sandbox_user_data_dir("t1", user_id="u1")
        assert "user-data" in result
        assert "users" in result

    def test_host_sandbox_work_dir_with_user(self, paths: Paths):
        result = paths.host_sandbox_work_dir("t1", user_id="u1")
        assert "workspace" in result

    def test_host_sandbox_uploads_dir_with_user(self, paths: Paths):
        result = paths.host_sandbox_uploads_dir("t1", user_id="u1")
        assert "uploads" in result

    def test_host_sandbox_outputs_dir_with_user(self, paths: Paths):
        result = paths.host_sandbox_outputs_dir("t1", user_id="u1")
        assert "outputs" in result

    def test_host_acp_workspace_dir_with_user(self, paths: Paths):
        result = paths.host_acp_workspace_dir("t1", user_id="u1")
        assert "acp-workspace" in result


# ---------------------------------------------------------------------------
# ensure_thread_dirs
# ---------------------------------------------------------------------------


class TestEnsureThreadDirs:
    def test_creates_all_dirs(self, paths: Paths):
        paths.ensure_thread_dirs("t1")
        assert paths.sandbox_work_dir("t1").is_dir()
        assert paths.sandbox_uploads_dir("t1").is_dir()
        assert paths.sandbox_outputs_dir("t1").is_dir()
        assert paths.acp_workspace_dir("t1").is_dir()

    def test_creates_user_scoped_dirs(self, paths: Paths):
        paths.ensure_thread_dirs("t1", user_id="u1")
        assert paths.sandbox_work_dir("t1", user_id="u1").is_dir()
        assert paths.sandbox_uploads_dir("t1", user_id="u1").is_dir()
        assert paths.sandbox_outputs_dir("t1", user_id="u1").is_dir()
        assert paths.acp_workspace_dir("t1", user_id="u1").is_dir()

    def test_idempotent(self, paths: Paths):
        paths.ensure_thread_dirs("t1")
        paths.ensure_thread_dirs("t1")  # should not raise
        assert paths.sandbox_work_dir("t1").is_dir()


# ---------------------------------------------------------------------------
# delete_thread_dir
# ---------------------------------------------------------------------------


class TestDeleteThreadDir:
    def test_deletes_existing_dir(self, paths: Paths):
        paths.ensure_thread_dirs("t1")
        assert paths.thread_dir("t1").exists()
        paths.delete_thread_dir("t1")
        assert not paths.thread_dir("t1").exists()

    def test_idempotent_for_missing(self, paths: Paths):
        paths.delete_thread_dir("nonexistent")  # should not raise

    def test_deletes_user_scoped(self, paths: Paths):
        paths.ensure_thread_dirs("t1", user_id="u1")
        assert paths.thread_dir("t1", user_id="u1").exists()
        paths.delete_thread_dir("t1", user_id="u1")
        assert not paths.thread_dir("t1", user_id="u1").exists()


# ---------------------------------------------------------------------------
# resolve_virtual_path
# ---------------------------------------------------------------------------


class TestResolveVirtualPath:
    def test_valid_path(self, paths: Paths):
        paths.ensure_thread_dirs("t1")
        result = paths.resolve_virtual_path("t1", "/mnt/user-data/workspace/file.txt")
        expected_base = paths.sandbox_user_data_dir("t1").resolve()
        assert str(result).startswith(str(expected_base))
        assert "file.txt" in str(result)

    def test_leading_slashes_stripped(self, paths: Paths):
        paths.ensure_thread_dirs("t1")
        result = paths.resolve_virtual_path("t1", "///mnt/user-data/workspace/file.txt")
        assert "file.txt" in str(result)

    def test_path_without_prefix_raises(self, paths: Paths):
        paths.ensure_thread_dirs("t1")
        with pytest.raises(ValueError, match="Path must start with"):
            paths.resolve_virtual_path("t1", "/tmp/evil.txt")

    def test_path_traversal_raises(self, paths: Paths):
        paths.ensure_thread_dirs("t1")
        with pytest.raises(ValueError, match="path traversal"):
            paths.resolve_virtual_path("t1", "/mnt/user-data/../../etc/passwd")

    def test_user_scoped(self, paths: Paths):
        paths.ensure_thread_dirs("t1", user_id="u1")
        result = paths.resolve_virtual_path("t1", "/mnt/user-data/workspace/file.txt", user_id="u1")
        expected_base = paths.sandbox_user_data_dir("t1", user_id="u1").resolve()
        assert str(result).startswith(str(expected_base))

    def test_prefix_without_segment_boundary_raises(self, paths: Paths):
        """Path like /mnt/user-dataX/ should not match /mnt/user-data/."""
        paths.ensure_thread_dirs("t1")
        with pytest.raises(ValueError, match="Path must start with"):
            paths.resolve_virtual_path("t1", "/mnt/user-dataX/evil.txt")


# ---------------------------------------------------------------------------
# get_paths singleton
# ---------------------------------------------------------------------------


class TestGetPathsSingleton:
    def test_returns_same_instance(self):
        p1 = get_paths()
        p2 = get_paths()
        assert p1 is p2


# ---------------------------------------------------------------------------
# resolve_path
# ---------------------------------------------------------------------------


class TestResolvePath:
    def test_absolute_path_passthrough(self, tmp_path):
        result = resolve_path(str(tmp_path / "file.txt"))
        assert result == (tmp_path / "file.txt").resolve()

    def test_relative_path_resolves_against_base(self):
        result = resolve_path("relative/path.txt")
        assert result.is_absolute()
        assert "relative" in str(result)
        assert "path.txt" in str(result)


# ---------------------------------------------------------------------------
# Paths constructor with explicit base_dir
# ---------------------------------------------------------------------------


class TestPathsConstructor:
    def test_explicit_base_dir(self, tmp_path):
        p = Paths(tmp_path)
        assert p.base_dir == tmp_path.resolve()

    def test_none_base_dir_uses_default(self):
        p = Paths(None)
        # base_dir should resolve to something (via runtime_home)
        assert p.base_dir is not None
        assert p.base_dir.is_absolute()
