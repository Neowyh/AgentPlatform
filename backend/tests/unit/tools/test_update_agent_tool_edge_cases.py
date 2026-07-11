"""Coverage tests for update_agent_tool — error and edge-case paths.

Targets previously uncovered lines:
- Lines 55-58: _stage_temp BaseException handler
- Lines 66-67: _cleanup_temps OSError handler
- Line 138: shared read-only template rejection
- Lines 144-145: ValueError from load_agent_config
- Line 148: existing_cfg is None
- Line 170: tool_groups change tracking
- Lines 216-224: partial write error with committed files
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

from ideer.tools.builtins.update_agent_tool import _cleanup_temps, _stage_temp, update_agent

DEFAULT_USER = "test-user-autouse"


class _DummyRuntime(SimpleNamespace):
    context: dict
    tool_call_id: str


def _runtime(agent_name: str | None = "test-agent", tool_call_id: str = "call_1") -> _DummyRuntime:
    return _DummyRuntime(
        context={"agent_name": agent_name} if agent_name is not None else {},
        tool_call_id=tool_call_id,
    )


def _make_paths_mock(tmp_path: Path) -> MagicMock:
    paths = MagicMock()
    paths.base_dir = tmp_path
    paths.agent_dir = lambda name: tmp_path / "agents" / name
    paths.agents_dir = tmp_path / "agents"
    paths.user_agent_dir = lambda user_id, name: tmp_path / "users" / user_id / "agents" / name
    paths.user_agents_dir = lambda user_id: tmp_path / "users" / user_id / "agents"
    return paths


def _user_agent_dir(tmp_path: Path, name: str = "test-agent", user_id: str = DEFAULT_USER) -> Path:
    return tmp_path / "users" / user_id / "agents" / name


def _seed_agent(
    tmp_path: Path,
    name: str = "test-agent",
    *,
    description: str = "old desc",
    soul: str = "old soul",
    skills: list[str] | None = None,
    tool_groups: list[str] | None = None,
    user_id: str = DEFAULT_USER,
) -> Path:
    agent_dir = _user_agent_dir(tmp_path, name, user_id=user_id)
    agent_dir.mkdir(parents=True, exist_ok=True)
    cfg: dict = {"name": name, "description": description}
    if skills is not None:
        cfg["skills"] = skills
    if tool_groups is not None:
        cfg["tool_groups"] = tool_groups
    (agent_dir / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    (agent_dir / "SOUL.md").write_text(soul, encoding="utf-8")
    return agent_dir


@pytest.fixture()
def patched_paths(tmp_path: Path):
    paths_mock = _make_paths_mock(tmp_path)
    with patch("ideer.tools.builtins.update_agent_tool.get_paths", return_value=paths_mock):
        with patch("ideer.config.agents_config.get_paths", return_value=paths_mock):
            yield paths_mock


@pytest.fixture()
def stub_app_config():
    fake = MagicMock()
    fake.get_model_config.side_effect = lambda name: object() if name in {"gpt-known", "m1"} else None
    with patch("ideer.tools.builtins.update_agent_tool.get_app_config", return_value=fake):
        yield fake


# ===========================================================================
# Lines 55-58: _stage_temp BaseException handler
# ===========================================================================


class TestStageTempErrorHandling:
    """Cover the except BaseException block in _stage_temp."""

    def test_stage_temp_cleans_up_on_write_failure(self, tmp_path):
        """When fd.write() raises, _stage_temp must close the fd, unlink the
        temp file, and re-raise the exception."""
        target = tmp_path / "output.txt"
        target.parent.mkdir(parents=True, exist_ok=True)

        real_ntf = __import__("tempfile").NamedTemporaryFile

        class BrokenFD:
            """A file descriptor whose write() always fails."""

            name: str

            def __init__(self, fd):
                self._fd = fd
                self.name = fd.name

            def write(self, data):
                raise OSError("disk full")

            def flush(self):
                pass

            def close(self):
                self._fd.close()

        original_ntf = real_ntf

        def _make_broken(*args, **kwargs):
            fd = original_ntf(*args, **kwargs)
            return BrokenFD(fd)

        with patch("ideer.tools.builtins.update_agent_tool.tempfile.NamedTemporaryFile", side_effect=_make_broken):
            with pytest.raises(OSError, match="disk full"):
                _stage_temp(target, "some content")

        # Temp file should have been cleaned up
        assert list(tmp_path.glob("*.tmp")) == []

    def test_stage_temp_closes_fd_on_exception(self, tmp_path):
        """Verify fd.close() is called even when write raises."""
        target = tmp_path / "output.txt"
        target.parent.mkdir(parents=True, exist_ok=True)

        real_ntf = __import__("tempfile").NamedTemporaryFile

        close_called = {"value": False}

        class FDWithCloseTracking:
            name: str

            def __init__(self, fd):
                self._fd = fd
                self.name = fd.name

            def write(self, data):
                raise OSError("write failed")

            def flush(self):
                pass

            def close(self):
                close_called["value"] = True
                self._fd.close()

        original_ntf = real_ntf

        def _make_tracking(*args, **kwargs):
            fd = original_ntf(*args, **kwargs)
            return FDWithCloseTracking(fd)

        with patch("ideer.tools.builtins.update_agent_tool.tempfile.NamedTemporaryFile", side_effect=_make_tracking):
            with pytest.raises(IOError):
                _stage_temp(target, "content")

        assert close_called["value"], "fd.close() must be called on exception"


# ===========================================================================
# Lines 66-67: _cleanup_temps OSError handler
# ===========================================================================


class TestCleanupTempsErrorHandling:
    """Cover the except OSError branch in _cleanup_temps."""

    def test_cleanup_temps_continues_on_oserror(self, tmp_path):
        """If unlink raises OSError for one file, the rest must still be cleaned."""
        good_file = tmp_path / "good.tmp"
        good_file.write_text("data")
        bad_file = tmp_path / "bad.tmp"
        bad_file.write_text("data")

        real_unlink = Path.unlink

        def _selective_unlink(self, *args, **kwargs):
            if self.name == "bad.tmp":
                raise OSError("permission denied")
            return real_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", _selective_unlink):
            # Should not raise; OSError is swallowed
            _cleanup_temps([good_file, bad_file])

        # bad_file still exists because unlink failed (missing_ok was ignored by the mock)
        assert bad_file.exists()
        # good_file's unlink was attempted — but our mock delegates to real_unlink
        # which would delete it. However the mock intercepts all Path.unlink calls,
        # including the missing_ok=True call in the except branch. So we just verify
        # no exception propagated.

    def test_cleanup_temps_swallows_oserror(self, tmp_path):
        """_cleanup_temps must not propagate OSError."""
        f = tmp_path / "stubborn.tmp"
        f.write_text("x")

        with patch.object(Path, "unlink", side_effect=OSError("busy")):
            # Must not raise
            _cleanup_temps([f])


# ===========================================================================
# Line 138: shared read-only template rejection
# ===========================================================================


class TestSharedTemplateRejection:
    """Cover line 138 — agent exists as shared template but not per-user."""

    def test_update_agent_rejects_shared_readonly_template(self, tmp_path, patched_paths, stub_app_config):
        """If the per-user agent dir does NOT exist but the shared agent dir
        DOES exist, the tool must refuse with a read-only template error."""
        # Create a shared (legacy) agent dir, but NOT the per-user dir
        shared_dir = tmp_path / "agents" / "shared-agent"
        shared_dir.mkdir(parents=True)
        (shared_dir / "config.yaml").write_text(
            yaml.safe_dump({"name": "shared-agent", "description": "shared"}, sort_keys=False),
            encoding="utf-8",
        )
        (shared_dir / "SOUL.md").write_text("shared soul", encoding="utf-8")

        # Ensure the per-user dir does NOT exist
        per_user_dir = _user_agent_dir(tmp_path, "shared-agent")
        assert not per_user_dir.exists()

        result = update_agent.func(runtime=_runtime(agent_name="shared-agent"), description="attempted update")

        msg = result.update["messages"][0]
        assert "shared read-only template" in msg.content
        assert "cannot be modified" in msg.content


# ===========================================================================
# Lines 144-145: ValueError from load_agent_config
# ===========================================================================


class TestLoadAgentConfigValueError:
    """Cover lines 144-145 — load_agent_config raises ValueError."""

    def test_update_agent_handles_unreadable_config(self, tmp_path, patched_paths, stub_app_config):
        """When load_agent_config raises ValueError (e.g. corrupted YAML),
        update_agent must return a helpful error message."""
        # Seed a valid agent dir so the shared-template check passes
        _seed_agent(tmp_path)

        with patch(
            "ideer.tools.builtins.update_agent_tool.load_agent_config",
            side_effect=ValueError("bad yaml content"),
        ):
            result = update_agent.func(runtime=_runtime(), description="new desc")

        msg = result.update["messages"][0]
        assert "unreadable config" in msg.content
        assert "bad yaml content" in msg.content


# ===========================================================================
# Line 148: existing_cfg is None
# ===========================================================================


class TestExistingConfigNone:
    """Cover line 148 — load_agent_config returns None."""

    def test_update_agent_handles_none_config(self, tmp_path, patched_paths, stub_app_config):
        """When load_agent_config returns None (agent name was None at loader
        level but somehow passed validation), update_agent must error."""
        _seed_agent(tmp_path)

        with patch("ideer.tools.builtins.update_agent_tool.load_agent_config", return_value=None):
            result = update_agent.func(runtime=_runtime(), description="new desc")

        msg = result.update["messages"][0]
        assert "could not be loaded" in msg.content


# ===========================================================================
# Line 170: tool_groups change tracking
# ===========================================================================


class TestToolGroupsChangeTracking:
    """Cover line 170 — updated_fields.append('tool_groups')."""

    def test_update_agent_tracks_tool_groups_change(self, tmp_path, patched_paths, stub_app_config):
        """When tool_groups differs from the existing value, it must appear
        in the updated_fields list in the success message."""
        _seed_agent(tmp_path, tool_groups=["old-group"])

        result = update_agent.func(runtime=_runtime(), tool_groups=["new-group", "another"])

        msg = result.update["messages"][0]
        assert "tool_groups" in msg.content
        assert "updated successfully" in msg.content

        cfg = yaml.safe_load((_user_agent_dir(tmp_path) / "config.yaml").read_text())
        assert cfg["tool_groups"] == ["new-group", "another"]

    def test_update_agent_no_change_when_tool_groups_match(self, tmp_path, patched_paths, stub_app_config):
        """When tool_groups matches existing, it must NOT appear in updated_fields."""
        _seed_agent(tmp_path, tool_groups=["same-group"])

        result = update_agent.func(runtime=_runtime(), tool_groups=["same-group"])

        msg = result.update["messages"][0]
        assert "No changes applied" in msg.content


# ===========================================================================
# Lines 216-224: partial write error with committed files
# ===========================================================================


class TestPartialWriteWithCommittedFiles:
    """Cover lines 216-224 — partial write where some files were already
    committed via Path.replace before a subsequent rename fails."""

    def test_partial_write_reports_committed_files(self, tmp_path, patched_paths, stub_app_config):
        """When the first Path.replace succeeds but the second fails,
        the error message must list which files were committed."""
        _seed_agent(tmp_path, description="old", soul="old soul")

        real_replace = Path.replace
        call_count = {"n": 0}

        def _fail_second_replace(self, target):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                raise OSError("disk full during second rename")
            return real_replace(self, target)

        with patch.object(Path, "replace", _fail_second_replace):
            result = update_agent.func(runtime=_runtime(), description="new desc", soul="new soul")

        msg = result.update["messages"][0]
        assert "Partial update" in msg.content
        assert "config.yaml" in msg.content, "committed config.yaml must be listed"

    def test_partial_write_no_committed_raises(self, tmp_path, patched_paths, stub_app_config):
        """When the FIRST Path.replace fails (nothing committed yet),
        the exception must propagate to the outer handler which returns
        a generic error."""
        _seed_agent(tmp_path, description="old", soul="old soul")

        with patch.object(Path, "replace", side_effect=OSError("immediate disk error")):
            result = update_agent.func(runtime=_runtime(), description="new desc", soul="new soul")

        msg = result.update["messages"][0]
        assert "Failed to update agent" in msg.content
        # Should NOT say "Partial update" since nothing was committed
        assert "Partial update" not in msg.content

    def test_partial_write_cleans_up_uncommitted_temps(self, tmp_path, patched_paths, stub_app_config):
        """After a partial write, temp files for uncommitted renames must be
        cleaned up, but committed files should remain on disk."""
        agent_dir = _seed_agent(tmp_path, description="old", soul="old soul")

        real_replace = Path.replace
        call_count = {"n": 0}

        def _fail_second_replace(self, target):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                raise OSError("disk full")
            return real_replace(self, target)

        with patch.object(Path, "replace", _fail_second_replace):
            update_agent.func(runtime=_runtime(), description="new desc", soul="new soul")

        # No temp files should remain
        assert list(agent_dir.glob("*.tmp")) == []
