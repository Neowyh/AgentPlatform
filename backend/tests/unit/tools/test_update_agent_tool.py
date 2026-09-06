"""Tests for update_agent tool — partial updates, atomic writes, and validation.

Resolves issue #2616: a custom agent must be able to persist updates to its
own SOUL.md / config.yaml from inside a normal chat (not only from bootstrap).

The tool writes per-user (``{base_dir}/users/{user_id}/agents/{name}/``) so
that one user's update cannot mutate another user's agent.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

from deerflow.tools.builtins.update_agent_tool import update_agent

DEFAULT_USER = "test-user"


class _DummyRuntime(SimpleNamespace):
    context: dict
    tool_call_id: str


def _runtime(agent_name: str | None = "test-agent", tool_call_id: str = "call_1", user_id: str = DEFAULT_USER) -> _DummyRuntime:
    return _DummyRuntime(
        context={"agent_name": agent_name, "user_id": user_id} if agent_name is not None else {"user_id": user_id},
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


def _agent_dir(tmp_path: Path, name: str = "test-agent", user_id: str = DEFAULT_USER) -> Path:
    return tmp_path / "users" / user_id / "agents" / name


def _seed_agent(
    tmp_path: Path,
    name: str = "test-agent",
    *,
    description: str = "old desc",
    soul: str = "old soul",
    skills: list[str] | None = None,
    user_id: str = DEFAULT_USER,
) -> Path:
    """Create a baseline agent dir with config.yaml and SOUL.md for tests to mutate."""
    agent_dir = _agent_dir(tmp_path, name, user_id=user_id)
    agent_dir.mkdir(parents=True, exist_ok=True)
    cfg: dict = {"name": name, "description": description}
    if skills is not None:
        cfg["skills"] = skills
    (agent_dir / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    (agent_dir / "SOUL.md").write_text(soul, encoding="utf-8")
    return agent_dir


@pytest.fixture()
def patched_paths(tmp_path: Path):
    paths_mock = _make_paths_mock(tmp_path)
    with patch("deerflow.tools.builtins.update_agent_tool.get_paths", return_value=paths_mock):
        # load_agent_config and the file agent store also call get_paths(); patch
        # the module that binds it so every read/write sees the tmp layout.
        with patch("deerflow.config.agents_config.get_paths", return_value=paths_mock):
            yield paths_mock


@pytest.fixture()
def stub_app_config():
    """Stub get_app_config so model validation accepts only known names."""
    fake = MagicMock()
    fake.get_model_config.side_effect = lambda name: object() if name in {"gpt-known", "m1"} else None
    with patch("deerflow.tools.builtins.update_agent_tool.get_app_config", return_value=fake):
        yield fake


class TestUpdateAgentPartialUpdates:
    def test_updates_fields_via_store(
        self,
        tmp_path: Path,
        patched_paths: MagicMock,
    ) -> None:
        agent_dir = _seed_agent(tmp_path, "canonical-agent", soul="# First Soul", description="First description")

        result = update_agent.func(runtime=_runtime("canonical-agent"), soul="# Second Soul", description="Second description")

        content = result.update["messages"][0].content
        assert "soul" in content
        assert "description" in content
        assert (agent_dir / "SOUL.md").read_text(encoding="utf-8") == "# Second Soul"
        cfg = yaml.safe_load((agent_dir / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["description"] == "Second description"

    def test_omitted_fields_are_preserved(
        self,
        tmp_path: Path,
        patched_paths: MagicMock,
    ) -> None:
        agent_dir = _seed_agent(tmp_path, "canonical-agent", soul="# Keep Soul", description="Keep description")

        result = update_agent.func(runtime=_runtime("canonical-agent"), description="Changed description")

        content = result.update["messages"][0].content
        assert "description" in content
        assert "soul" not in content
        assert (agent_dir / "SOUL.md").read_text(encoding="utf-8") == "# Keep Soul"
        cfg = yaml.safe_load((agent_dir / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["description"] == "Changed description"

    def test_skills_persist_plain_names(
        self,
        tmp_path: Path,
        patched_paths: MagicMock,
    ) -> None:
        """Skill allowlists are stored as plain names and resolved at load time."""
        agent_dir = _seed_agent(tmp_path, "canonical-agent", soul="# Skillful", description="desc")

        result = update_agent.func(runtime=_runtime("canonical-agent"), skills=["research"])

        content = result.update["messages"][0].content
        assert "skills" in content
        cfg = yaml.safe_load((agent_dir / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["skills"] == ["research"]

    def test_skills_omitted_keeps_existing_allowlist(
        self,
        tmp_path: Path,
        patched_paths: MagicMock,
    ) -> None:
        agent_dir = _seed_agent(tmp_path, "canonical-agent", soul="# Skillful", description="desc", skills=["research"])

        update_agent.func(runtime=_runtime("canonical-agent"), description="bumped")

        cfg = yaml.safe_load((agent_dir / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["skills"] == ["research"], "omitting skills must preserve the existing allowlist"

    def test_no_op_when_values_match(
        self,
        tmp_path: Path,
        patched_paths: MagicMock,
    ) -> None:
        agent_dir = _seed_agent(tmp_path, "canonical-agent", soul="# Soul", description="Same description")

        result = update_agent.func(runtime=_runtime("canonical-agent"), description="Same description")

        assert "No changes applied" in result.update["messages"][0].content
        cfg = yaml.safe_load((agent_dir / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["description"] == "Same description"

    def test_unknown_agent_returns_error(
        self,
        tmp_path: Path,
        patched_paths: MagicMock,
    ) -> None:
        result = update_agent.func(runtime=_runtime("ghost-agent"), description="x")

        content = result.update["messages"][0].content
        assert "Error" in content
        assert "ghost-agent" in content

    def test_store_failure_returns_error(
        self,
        tmp_path: Path,
        patched_paths: MagicMock,
    ) -> None:
        _seed_agent(tmp_path, "canonical-agent", soul="# Soul", description="desc")

        failing_store = MagicMock()
        failing_store.update.side_effect = RuntimeError("disk full")
        with patch("deerflow.tools.builtins.update_agent_tool.get_agent_store", return_value=failing_store):
            result = update_agent.func(runtime=_runtime("canonical-agent"), description="changed")

        content = result.update["messages"][0].content
        assert "Error" in content
        assert "Failed to update agent" in content
