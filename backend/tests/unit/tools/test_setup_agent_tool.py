"""Tests for setup_agent tool — validates agent name security and store semantics.

The upstream tool persists custom agents through the per-user agent store
(``{base_dir}/users/{user_id}/agents/{name}/``). The legacy enterprise
resource-catalog mode (Resource/ResourceVersion publishing) was removed in the
upstream runtime merge, so these tests exercise the on-disk store contract.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

import deerflow.tools.builtins.setup_agent_tool as setup_agent_tool_module

DEFAULT_USER = "test-user-autouse"

# --- Helpers ---


@pytest.fixture(autouse=True)
def _stock_setup_agent_tool():
    """Pin the upstream stock tool for every test in this file.

    Tests that import the gateway (e.g. test_mcp_config_secrets) trigger
    ``app.agentplatform.agent_bootstrap.install()`` at collection time, which
    rebinds ``setup_agent_tool.setup_agent`` to the enterprise resource-catalog
    wrapper. These tests exercise the upstream per-user store contract, so
    reload the tool module to restore the stock implementation, and restore
    the previous attribute afterwards to keep the process state unchanged.
    """
    previous = setup_agent_tool_module.setup_agent
    importlib.reload(setup_agent_tool_module)
    yield
    setup_agent_tool_module.setup_agent = previous


def _call_setup_agent(*args, **kwargs):
    return setup_agent_tool_module.setup_agent.func(*args, **kwargs)


class _DummyRuntime(SimpleNamespace):
    context: dict
    tool_call_id: str


def _make_runtime(agent_name: str | None = "test-agent", user_id: str = DEFAULT_USER) -> _DummyRuntime:
    return _DummyRuntime(
        context={"agent_name": agent_name, "user_id": user_id} if agent_name is not None else {"user_id": user_id},
        tool_call_id="call_1",
    )


def _make_paths_mock(tmp_path: Path) -> MagicMock:
    paths = MagicMock()
    paths.base_dir = tmp_path
    paths.agent_dir = lambda name: tmp_path / "agents" / name
    paths.user_agent_dir = lambda user_id, name: tmp_path / "users" / user_id / "agents" / name
    return paths


def _agent_dir(tmp_path: Path, name: str, user_id: str = DEFAULT_USER) -> Path:
    return tmp_path / "users" / user_id / "agents" / name


def _read_config(agent_dir: Path) -> dict:
    return yaml.safe_load((agent_dir / "config.yaml").read_text(encoding="utf-8"))


@pytest.fixture()
def patched_paths(tmp_path: Path):
    paths_mock = _make_paths_mock(tmp_path)
    # The tool resolves the default-agent layout via its own get_paths binding;
    # the file agent store reads paths through deerflow.config.agents_config.
    with (
        patch("deerflow.tools.builtins.setup_agent_tool.get_paths", return_value=paths_mock),
        patch("deerflow.config.agents_config.get_paths", return_value=paths_mock),
    ):
        yield paths_mock


# --- Agent name validation tests ---


def test_setup_agent_rejects_invalid_agent_name_before_writing(tmp_path: Path, patched_paths: MagicMock) -> None:
    outside_dir = tmp_path.parent / "outside-target"
    traversal_agent = f"../../../{outside_dir.name}/evil"
    runtime = _DummyRuntime(context={"agent_name": traversal_agent}, tool_call_id="tool-1")

    result = _call_setup_agent(soul="test soul", description="desc", runtime=runtime)

    messages = result.update["messages"]
    assert len(messages) == 1
    assert "Invalid agent name" in messages[0].content
    assert not (tmp_path / "users" / DEFAULT_USER / "agents").exists()
    assert not (outside_dir / "evil" / "SOUL.md").exists()


def test_setup_agent_rejects_absolute_agent_name_before_writing(tmp_path: Path, patched_paths: MagicMock) -> None:
    absolute_agent = str(tmp_path / "outside-agent")
    runtime = _DummyRuntime(context={"agent_name": absolute_agent}, tool_call_id="tool-2")

    result = _call_setup_agent(soul="test soul", description="desc", runtime=runtime)

    messages = result.update["messages"]
    assert len(messages) == 1
    assert "Invalid agent name" in messages[0].content
    assert not (tmp_path / "users" / DEFAULT_USER / "agents").exists()
    assert not (Path(absolute_agent) / "SOUL.md").exists()


# --- Per-user agent store tests ---


class TestSetupAgentUserStore:
    def test_setup_creates_agent_in_user_store(self, tmp_path: Path, patched_paths: MagicMock) -> None:
        result = _call_setup_agent(
            soul="# Canonical Agent",
            description="A canonical agent",
            runtime=_make_runtime("canonical-agent"),
        )

        assert result.update["created_agent_name"] == "canonical-agent"
        agent_dir = _agent_dir(tmp_path, "canonical-agent")
        config = _read_config(agent_dir)
        assert config["name"] == "canonical-agent"
        assert config["description"] == "A canonical agent"
        assert (agent_dir / "SOUL.md").read_text(encoding="utf-8") == "# Canonical Agent"
        # Custom agents never use the legacy shared layout.
        assert not (tmp_path / "agents" / "canonical-agent").exists()

    def test_setup_is_an_idempotent_upsert(self, tmp_path: Path, patched_paths: MagicMock) -> None:
        first = _call_setup_agent(
            soul="# First Soul",
            description="First description",
            runtime=_make_runtime("canonical-agent"),
        )
        second = _call_setup_agent(
            soul="# Second Soul",
            description="Second description",
            runtime=_make_runtime("canonical-agent"),
        )

        assert first.update["created_agent_name"] == "canonical-agent"
        assert second.update["created_agent_name"] == "canonical-agent"
        agent_dir = _agent_dir(tmp_path, "canonical-agent")
        assert (agent_dir / "SOUL.md").read_text(encoding="utf-8") == "# Second Soul"
        assert _read_config(agent_dir)["description"] == "Second description"

    def test_setup_persists_skill_list_in_config(self, tmp_path: Path, patched_paths: MagicMock) -> None:
        result = _call_setup_agent(
            soul="# Skillful Agent",
            description="Uses skills",
            runtime=_make_runtime("skillful-agent"),
            skills=["research", "ghost-skill"],
        )

        assert result.update["created_agent_name"] == "skillful-agent"
        config = _read_config(_agent_dir(tmp_path, "skillful-agent"))
        assert config["skills"] == ["research", "ghost-skill"]

    def test_setup_without_skills_omits_skills_key(self, tmp_path: Path, patched_paths: MagicMock) -> None:
        result = _call_setup_agent(
            soul="# Plain Agent",
            description="desc",
            runtime=_make_runtime("plain-agent"),
        )

        assert result.update["created_agent_name"] == "plain-agent"
        config = _read_config(_agent_dir(tmp_path, "plain-agent"))
        assert "skills" not in config

    def test_setup_empty_soul_returns_error_without_writing(self, tmp_path: Path, patched_paths: MagicMock) -> None:
        # Issue #3549: an empty soul must fail loud instead of persisting an
        # empty SOUL.md and reporting success.
        result = _call_setup_agent(
            soul="   ",
            description="desc",
            runtime=_make_runtime("empty-soul-agent"),
        )

        messages = result.update["messages"]
        assert len(messages) == 1
        assert messages[0].content.startswith("Error: soul content is empty")
        assert "created_agent_name" not in result.update
        assert not _agent_dir(tmp_path, "empty-soul-agent").exists()
