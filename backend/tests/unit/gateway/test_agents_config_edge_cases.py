"""Extended coverage tests for ideer.config.agents_config module.

Targets the uncovered lines in validate_agent_name, resolve_agent_dir,
load_agent_config (YAML error, legacy fallback), load_agent_soul (legacy),
and list_custom_agents (legacy paths, error handling).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from ideer.config.agents_config import (
    list_custom_agents,
    load_agent_config,
    load_agent_soul,
    resolve_agent_dir,
    validate_agent_name,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_paths(base_dir: Path):
    from ideer.config.paths import Paths

    return Paths(base_dir=base_dir)


def _write_user_agent(base_dir: Path, user_id: str, name: str, config: dict, soul: str = "Soul.") -> None:
    agent_dir = base_dir / "users" / user_id / "agents" / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    config_copy = dict(config)
    if "name" not in config_copy:
        config_copy["name"] = name
    with open(agent_dir / "config.yaml", "w") as f:
        yaml.dump(config_copy, f)
    (agent_dir / "SOUL.md").write_text(soul, encoding="utf-8")


def _write_legacy_agent(base_dir: Path, name: str, config: dict, soul: str = "Legacy soul.") -> None:
    agent_dir = base_dir / "agents" / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    config_copy = dict(config)
    if "name" not in config_copy:
        config_copy["name"] = name
    with open(agent_dir / "config.yaml", "w") as f:
        yaml.dump(config_copy, f)
    (agent_dir / "SOUL.md").write_text(soul, encoding="utf-8")


# ---------------------------------------------------------------------------
# validate_agent_name
# ---------------------------------------------------------------------------


class TestValidateAgentName:
    def test_none_returns_none(self):
        assert validate_agent_name(None) is None

    def test_non_string_raises(self):
        with pytest.raises(ValueError, match="Expected a string or None"):
            validate_agent_name(123)  # type: ignore[arg-type]

    def test_valid_names(self):
        for name in ["agent", "my-agent", "agent123", "A", "abc-123-xyz"]:
            assert validate_agent_name(name) == name

    def test_invalid_names(self):
        for name in ["my_agent", "agent name", "agent.name", "../evil"]:
            with pytest.raises(ValueError, match="Invalid agent name"):
                validate_agent_name(name)


# ---------------------------------------------------------------------------
# resolve_agent_dir
# ---------------------------------------------------------------------------


class TestResolveAgentDir:
    def test_prefers_per_user_path_when_exists(self, tmp_path):
        _write_user_agent(tmp_path, "u1", "my-agent", {"name": "my-agent"})
        with patch("ideer.config.agents_config.get_paths", return_value=_make_paths(tmp_path)):
            with patch("ideer.config.agents_config.get_effective_user_id", return_value="u1"):
                result = resolve_agent_dir("my-agent")
        assert "users" in str(result)
        assert "u1" in str(result)

    def test_falls_back_to_legacy_when_no_user_dir(self, tmp_path):
        _write_legacy_agent(tmp_path, "legacy-agent", {"name": "legacy-agent"})
        with patch("ideer.config.agents_config.get_paths", return_value=_make_paths(tmp_path)):
            with patch("ideer.config.agents_config.get_effective_user_id", return_value="u1"):
                result = resolve_agent_dir("legacy-agent")
        assert "agents" in str(result)
        assert "legacy-agent" in str(result)
        assert "users" not in str(result)

    def test_returns_user_path_when_neither_exists(self, tmp_path):
        with patch("ideer.config.agents_config.get_paths", return_value=_make_paths(tmp_path)):
            with patch("ideer.config.agents_config.get_effective_user_id", return_value="u1"):
                result = resolve_agent_dir("nonexistent")
        assert "users" in str(result)
        assert "u1" in str(result)

    def test_explicit_user_id_overrides_context(self, tmp_path):
        _write_user_agent(tmp_path, "explicit-user", "my-agent", {"name": "my-agent"})
        with patch("ideer.config.agents_config.get_paths", return_value=_make_paths(tmp_path)):
            result = resolve_agent_dir("my-agent", user_id="explicit-user")
        assert "explicit-user" in str(result)


# ---------------------------------------------------------------------------
# load_agent_config - YAML error handling
# ---------------------------------------------------------------------------


class TestLoadAgentConfigYamlError:
    def test_invalid_yaml_raises_value_error(self, tmp_path):
        agent_dir = tmp_path / "agents" / "bad-yaml"
        agent_dir.mkdir(parents=True)
        (agent_dir / "config.yaml").write_text("{{invalid yaml: [", encoding="utf-8")

        with patch("ideer.config.agents_config.get_paths", return_value=_make_paths(tmp_path)):
            with pytest.raises(ValueError, match="Failed to parse"):
                load_agent_config("bad-yaml")

    def test_returns_none_when_name_is_none(self):
        assert load_agent_config(None) is None


# ---------------------------------------------------------------------------
# load_agent_soul - legacy paths
# ---------------------------------------------------------------------------


class TestLoadAgentSoulLegacy:
    def test_reads_from_legacy_path_when_user_path_missing(self, tmp_path):
        """When no user dir exists but legacy agent dir does, read SOUL.md from legacy."""
        _write_legacy_agent(tmp_path, "legacy-soul-agent", {"name": "legacy-soul-agent"}, soul="Legacy soul content")

        with patch("ideer.config.agents_config.get_paths", return_value=_make_paths(tmp_path)):
            with patch("ideer.config.agents_config.get_effective_user_id", return_value="u1"):
                soul = load_agent_soul("legacy-soul-agent")

        assert soul == "Legacy soul content"

    def test_returns_none_when_agent_name_is_none(self, tmp_path):
        """When agent_name is None, load_agent_soul returns None."""
        with patch("ideer.config.agents_config.get_paths", return_value=_make_paths(tmp_path)):
            soul = load_agent_soul(None)
        assert soul is None


# ---------------------------------------------------------------------------
# list_custom_agents - legacy paths and error handling
# ---------------------------------------------------------------------------


class TestListCustomAgentsLegacy:
    def test_discovers_agents_from_legacy_path(self, tmp_path):
        """Agents from the legacy shared path should be found."""
        _write_legacy_agent(tmp_path, "legacy-one", {"name": "legacy-one"})
        _write_legacy_agent(tmp_path, "legacy-two", {"name": "legacy-two", "description": "Two"})

        with patch("ideer.config.agents_config.get_paths", return_value=_make_paths(tmp_path)):
            with patch("ideer.config.agents_config.get_effective_user_id", return_value="u1"):
                agents = list_custom_agents()

        names = [a.name for a in agents]
        assert "legacy-one" in names
        assert "legacy-two" in names

    def test_user_agents_shadow_legacy(self, tmp_path):
        """User agents should shadow legacy agents with the same name."""
        _write_legacy_agent(tmp_path, "shared-name", {"name": "shared-name"}, soul="Legacy soul")
        _write_user_agent(tmp_path, "u1", "shared-name", {"name": "shared-name"}, soul="User soul")

        with patch("ideer.config.agents_config.get_paths", return_value=_make_paths(tmp_path)):
            with patch("ideer.config.agents_config.get_effective_user_id", return_value="u1"):
                agents = list_custom_agents()

        matching = [a for a in agents if a.name == "shared-name"]
        assert len(matching) == 1

    def test_skips_dirs_with_invalid_config(self, tmp_path):
        """Directories with invalid config files should be logged and skipped."""
        # Create a directory with an unreadable config.yaml
        broken_dir = tmp_path / "users" / "u1" / "agents" / "broken"
        broken_dir.mkdir(parents=True)
        (broken_dir / "config.yaml").write_text("{{{{invalid", encoding="utf-8")
        # Also need a valid agent to ensure the function runs
        _write_user_agent(tmp_path, "u1", "valid-agent", {"name": "valid-agent"})

        with patch("ideer.config.agents_config.get_paths", return_value=_make_paths(tmp_path)):
            with patch("ideer.config.agents_config.get_effective_user_id", return_value="u1"):
                agents = list_custom_agents()

        names = [a.name for a in agents]
        assert "valid-agent" in names
        assert "broken" not in names

    def test_legacy_agents_dir_does_not_exist(self, tmp_path):
        """When legacy agents dir doesn't exist, only user agents are returned."""
        _write_user_agent(tmp_path, "u1", "user-agent", {"name": "user-agent"})
        # No legacy agents dir created

        with patch("ideer.config.agents_config.get_paths", return_value=_make_paths(tmp_path)):
            with patch("ideer.config.agents_config.get_effective_user_id", return_value="u1"):
                agents = list_custom_agents()

        assert len(agents) == 1
        assert agents[0].name == "user-agent"

    def test_user_agents_dir_does_not_exist(self, tmp_path):
        """When user agents dir doesn't exist, only legacy agents are returned."""
        _write_legacy_agent(tmp_path, "legacy-agent", {"name": "legacy-agent"})

        with patch("ideer.config.agents_config.get_paths", return_value=_make_paths(tmp_path)):
            with patch("ideer.config.agents_config.get_effective_user_id", return_value="u1"):
                agents = list_custom_agents()

        assert len(agents) == 1
        assert agents[0].name == "legacy-agent"

    def test_explicit_user_id(self, tmp_path):
        """Explicit user_id should be used instead of the context."""
        _write_user_agent(tmp_path, "specific-user", "target-agent", {"name": "target-agent"})

        with patch("ideer.config.agents_config.get_paths", return_value=_make_paths(tmp_path)):
            agents = list_custom_agents(user_id="specific-user")

        assert any(a.name == "target-agent" for a in agents)
