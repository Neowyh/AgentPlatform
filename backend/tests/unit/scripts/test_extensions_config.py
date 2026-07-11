"""Tests for ideer.config.extensions_config — MCP and skill extension config."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from ideer.config.extensions_config import (
    ExtensionsConfig,
    McpOAuthConfig,
    McpServerConfig,
    SkillStateConfig,
    get_extensions_config,
    reload_extensions_config,
    reset_extensions_config,
    set_extensions_config,
)

# ---------------------------------------------------------------------------
# McpOAuthConfig
# ---------------------------------------------------------------------------


class TestMcpOAuthConfig:
    def test_defaults(self):
        cfg = McpOAuthConfig(token_url="https://auth.example.com/token")
        assert cfg.enabled is True
        assert cfg.grant_type == "client_credentials"
        assert cfg.client_id is None
        assert cfg.client_secret is None
        assert cfg.token_field == "access_token"
        assert cfg.default_token_type == "Bearer"
        assert cfg.refresh_skew_seconds == 60

    def test_custom_values(self):
        cfg = McpOAuthConfig(
            token_url="https://auth.example.com/token",
            grant_type="refresh_token",
            client_id="cid",
            client_secret="csecret",
            refresh_token="rtok",
            scope="read write",
            audience="api",
        )
        assert cfg.grant_type == "refresh_token"
        assert cfg.client_id == "cid"
        assert cfg.refresh_token == "rtok"
        assert cfg.scope == "read write"
        assert cfg.audience == "api"

    def test_extra_fields_allowed(self):
        cfg = McpOAuthConfig(token_url="https://x.com", custom_field="custom")
        assert cfg.custom_field == "custom"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# McpServerConfig
# ---------------------------------------------------------------------------


class TestMcpServerConfig:
    def test_defaults(self):
        cfg = McpServerConfig()
        assert cfg.enabled is True
        assert cfg.type == "stdio"
        assert cfg.command is None
        assert cfg.args == []
        assert cfg.env == {}
        assert cfg.url is None
        assert cfg.headers == {}
        assert cfg.oauth is None
        assert cfg.description == ""

    def test_http_type_with_oauth(self):
        oauth = McpOAuthConfig(token_url="https://auth.example.com/token")
        cfg = McpServerConfig(type="http", url="https://mcp.example.com", oauth=oauth)
        assert cfg.type == "http"
        assert cfg.url == "https://mcp.example.com"
        assert cfg.oauth is oauth


# ---------------------------------------------------------------------------
# SkillStateConfig
# ---------------------------------------------------------------------------


class TestSkillStateConfig:
    def test_default_enabled(self):
        cfg = SkillStateConfig()
        assert cfg.enabled is True

    def test_disabled(self):
        cfg = SkillStateConfig(enabled=False)
        assert cfg.enabled is False


# ---------------------------------------------------------------------------
# ExtensionsConfig — resolve_env_variables
# ---------------------------------------------------------------------------


class TestResolveEnvVariables:
    def test_non_string_passthrough(self):
        assert ExtensionsConfig.resolve_env_variables(42) == 42
        assert ExtensionsConfig.resolve_env_variables(True) is True
        assert ExtensionsConfig.resolve_env_variables(None) is None

    def test_string_without_dollar(self):
        assert ExtensionsConfig.resolve_env_variables("hello") == "hello"

    def test_env_var_resolved(self):
        with patch.dict(os.environ, {"TEST_SECRET_KEY": "secret123"}):
            assert ExtensionsConfig.resolve_env_variables("$TEST_SECRET_KEY") == "secret123"

    def test_env_var_missing_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Required environment variable 'MISSING_VAR' is not set"):
                ExtensionsConfig.resolve_env_variables("$MISSING_VAR")

    def test_dict_recursion(self):
        with patch.dict(os.environ, {"KEY1": "val1", "KEY2": "val2"}):
            result = ExtensionsConfig.resolve_env_variables({"a": "$KEY1", "b": "$KEY2"})
            assert result == {"a": "val1", "b": "val2"}

    def test_list_recursion(self):
        with patch.dict(os.environ, {"K": "v"}):
            assert ExtensionsConfig.resolve_env_variables(["$K", "plain"]) == ["v", "plain"]

    def test_tuple_recursion(self):
        with patch.dict(os.environ, {"K": "v"}):
            assert ExtensionsConfig.resolve_env_variables(("$K",)) == ("v",)

    def test_nested_structure(self):
        with patch.dict(os.environ, {"DB_PASS": "p@ss"}):
            data = {"db": {"password": "$DB_PASS"}, "items": ["$DB_PASS", 5]}
            result = ExtensionsConfig.resolve_env_variables(data)
            assert result["db"]["password"] == "p@ss"
            assert result["items"][0] == "p@ss"
            assert result["items"][1] == 5


# ---------------------------------------------------------------------------
# ExtensionsConfig — resolve_config_path
# ---------------------------------------------------------------------------


class TestResolveConfigPath:
    def test_explicit_path(self, tmp_path):
        p = tmp_path / "ext.json"
        p.write_text("{}")
        assert ExtensionsConfig.resolve_config_path(str(p)) == p

    def test_explicit_path_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="not found"):
            ExtensionsConfig.resolve_config_path(str(tmp_path / "nope.json"))

    def test_env_variable(self, tmp_path):
        p = tmp_path / "env_ext.json"
        p.write_text("{}")
        with patch.dict(os.environ, {"IDEER_EXTENSIONS_CONFIG_PATH": str(p)}):
            assert ExtensionsConfig.resolve_config_path() == p

    def test_env_variable_not_found(self, tmp_path):
        with patch.dict(os.environ, {"IDEER_EXTENSIONS_CONFIG_PATH": str(tmp_path / "nope.json")}):
            with pytest.raises(FileNotFoundError, match="environment variable"):
                ExtensionsConfig.resolve_config_path()

    def test_no_config_returns_none(self, tmp_path):
        with patch.dict(os.environ, {}, clear=True):
            with patch("ideer.config.extensions_config.existing_project_file", return_value=None):
                with patch("ideer.config.extensions_config.Path.exists", return_value=False):
                    result = ExtensionsConfig.resolve_config_path()
                    assert result is None


# ---------------------------------------------------------------------------
# ExtensionsConfig — from_file
# ---------------------------------------------------------------------------


class TestFromFile:
    def test_no_file_returns_empty(self):
        with patch.object(ExtensionsConfig, "resolve_config_path", return_value=None):
            cfg = ExtensionsConfig.from_file()
            assert cfg.mcp_servers == {}
            assert cfg.skills == {}

    def test_load_valid_json(self, tmp_path):
        data = {
            "mcpServers": {"myserver": {"type": "http", "url": "https://x.com"}},
            "skills": {"myskill": {"enabled": False}},
        }
        p = tmp_path / "ext.json"
        p.write_text(json.dumps(data))

        with patch.object(ExtensionsConfig, "resolve_config_path", return_value=p):
            cfg = ExtensionsConfig.from_file()
            assert "myserver" in cfg.mcp_servers
            assert cfg.mcp_servers["myserver"].type == "http"
            assert "myskill" in cfg.skills
            assert cfg.skills["myskill"].enabled is False

    def test_invalid_json_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json{{{")
        with patch.object(ExtensionsConfig, "resolve_config_path", return_value=p):
            with pytest.raises(ValueError, match="not valid JSON"):
                ExtensionsConfig.from_file()

    def test_env_variable_resolution(self, tmp_path):
        data = {"mcpServers": {"s": {"url": "$MY_URL"}}}
        p = tmp_path / "ext.json"
        p.write_text(json.dumps(data))
        with patch.dict(os.environ, {"MY_URL": "https://resolved.com"}):
            with patch.object(ExtensionsConfig, "resolve_config_path", return_value=p):
                cfg = ExtensionsConfig.from_file()
                assert cfg.mcp_servers["s"].url == "https://resolved.com"


# ---------------------------------------------------------------------------
# ExtensionsConfig — get_enabled_mcp_servers / is_skill_enabled
# ---------------------------------------------------------------------------


class TestExtensionsConfigMethods:
    def test_get_enabled_mcp_servers(self):
        cfg = ExtensionsConfig(
            mcp_servers={
                "a": McpServerConfig(enabled=True),
                "b": McpServerConfig(enabled=False),
                "c": McpServerConfig(enabled=True),
            }
        )
        enabled = cfg.get_enabled_mcp_servers()
        assert set(enabled.keys()) == {"a", "c"}

    def test_is_skill_enabled_explicit(self):
        cfg = ExtensionsConfig(skills={"s1": SkillStateConfig(enabled=False)})
        assert cfg.is_skill_enabled("s1", "public") is False

    def test_is_skill_enabled_default_public(self):
        cfg = ExtensionsConfig(skills={})
        assert cfg.is_skill_enabled("unknown", "public") is True

    def test_is_skill_enabled_default_custom(self):
        cfg = ExtensionsConfig(skills={})
        assert cfg.is_skill_enabled("unknown", "custom") is True

    def test_is_skill_enabled_default_other_category(self):
        cfg = ExtensionsConfig(skills={})
        assert cfg.is_skill_enabled("unknown", "private") is False


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------


class TestSingleton:
    def setup_method(self):
        reset_extensions_config()

    def teardown_method(self):
        reset_extensions_config()

    def test_set_and_get(self):
        custom = ExtensionsConfig(mcp_servers={}, skills={"x": SkillStateConfig()})
        set_extensions_config(custom)
        assert get_extensions_config() is custom

    def test_get_loads_from_file(self):
        with patch.object(ExtensionsConfig, "from_file") as mock_from:
            mock_from.return_value = ExtensionsConfig(mcp_servers={}, skills={})
            cfg = get_extensions_config()
            mock_from.assert_called_once()
            assert isinstance(cfg, ExtensionsConfig)

    def test_reload(self):
        with patch.object(ExtensionsConfig, "from_file") as mock_from:
            mock_from.return_value = ExtensionsConfig(mcp_servers={}, skills={})
            reload_extensions_config("/some/path")
            mock_from.assert_called_with("/some/path")

    def test_reset_clears_cache(self):
        set_extensions_config(ExtensionsConfig(mcp_servers={}, skills={}))
        reset_extensions_config()
        # Next get should call from_file
        with patch.object(ExtensionsConfig, "from_file") as mock_from:
            mock_from.return_value = ExtensionsConfig(mcp_servers={}, skills={})
            get_extensions_config()
            mock_from.assert_called_once()
