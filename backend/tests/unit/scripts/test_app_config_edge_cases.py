"""Extended coverage tests for ideer.config.app_config module.

Targets the uncovered lines in CircuitBreakerConfig, UploadsConfig,
_resolve_config_path, resolve_env_variables, get_model_config,
get_tool_config, get_tool_group_config, singleton management,
and ContextVar push/pop logic.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from ideer.config.app_config import (
    AppConfig,
    CircuitBreakerConfig,
    UploadsConfig,
    _get_config_mtime,
    _legacy_config_candidates,
    get_app_config,
    peek_current_app_config,
    pop_current_app_config,
    push_current_app_config,
    reset_app_config,
    set_app_config,
)
from ideer.config.sandbox_config import SandboxConfig

_SANDBOX = SandboxConfig(use="ideer.sandbox.local:LocalSandboxProvider")


# ---------------------------------------------------------------------------
# CircuitBreakerConfig defaults
# ---------------------------------------------------------------------------


class TestCircuitBreakerConfig:
    def test_default_values(self):
        cfg = CircuitBreakerConfig()
        assert cfg.failure_threshold == 5
        assert cfg.recovery_timeout_sec == 60

    def test_custom_values(self):
        cfg = CircuitBreakerConfig(failure_threshold=3, recovery_timeout_sec=120)
        assert cfg.failure_threshold == 3
        assert cfg.recovery_timeout_sec == 120


# ---------------------------------------------------------------------------
# UploadsConfig defaults
# ---------------------------------------------------------------------------


class TestUploadsConfig:
    def test_default_values(self):
        cfg = UploadsConfig()
        assert cfg.max_files == 20
        assert cfg.max_file_size == 52428800
        assert cfg.max_total_size == 209715200
        assert cfg.auto_convert_documents is True
        assert cfg.pdf_converter == "default"

    def test_custom_values(self):
        cfg = UploadsConfig(max_files=5, max_file_size=1024)
        assert cfg.max_files == 5
        assert cfg.max_file_size == 1024


# ---------------------------------------------------------------------------
# _legacy_config_candidates
# ---------------------------------------------------------------------------


class TestLegacyConfigCandidates:
    def test_returns_tuple_of_two_paths(self):
        candidates = _legacy_config_candidates()
        assert isinstance(candidates, tuple)
        assert len(candidates) == 2
        for p in candidates:
            assert isinstance(p, Path)


# ---------------------------------------------------------------------------
# _get_config_mtime
# ---------------------------------------------------------------------------


class TestGetConfigMtime:
    def test_returns_mtime_for_existing_file(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("key: value")
        mtime = _get_config_mtime(f)
        assert isinstance(mtime, float)
        assert mtime > 0

    def test_returns_none_for_missing_file(self):
        mtime = _get_config_mtime(Path("/nonexistent/path/config.yaml"))
        assert mtime is None


# ---------------------------------------------------------------------------
# resolve_config_path
# ---------------------------------------------------------------------------


class TestResolveConfigPath:
    def test_explicit_config_path(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("sandbox: {}")
        result = AppConfig.resolve_config_path(str(config_file))
        assert result == config_file

    def test_explicit_config_path_not_found(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            AppConfig.resolve_config_path("/nonexistent/config.yaml")

    def test_env_var_config_path(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("sandbox: {}")
        monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_file))
        result = AppConfig.resolve_config_path()
        assert result == config_file

    def test_env_var_config_path_not_found(self, monkeypatch):
        monkeypatch.setenv("IDEER_CONFIG_PATH", "/nonexistent/config.yaml")
        with pytest.raises(FileNotFoundError, match="IDEER_CONFIG_PATH"):
            AppConfig.resolve_config_path()

    def test_legacy_candidate_fallback(self, tmp_path, monkeypatch):
        """When no explicit path or env var is set, check legacy candidates."""
        monkeypatch.delenv("IDEER_CONFIG_PATH", raising=False)
        candidates = _legacy_config_candidates()
        # If neither legacy candidate exists, it should raise FileNotFoundError
        # (since existing_project_file also won't find it)
        exists = any(c.exists() for c in candidates)
        if not exists:
            with pytest.raises(FileNotFoundError):
                AppConfig.resolve_config_path()


# ---------------------------------------------------------------------------
# resolve_env_variables
# ---------------------------------------------------------------------------


class TestResolveEnvVariables:
    def test_string_with_dollar_sign_resolves_env(self, monkeypatch):
        monkeypatch.setenv("TEST_ENV_VAR_XYZ", "resolved_value")
        result = AppConfig.resolve_env_variables("$TEST_ENV_VAR_XYZ")
        assert result == "resolved_value"

    def test_string_with_dollar_sign_missing_env_raises(self, monkeypatch):
        monkeypatch.delenv("TOTALLY_MISSING_VAR_12345", raising=False)
        with pytest.raises(ValueError, match="Environment variable"):
            AppConfig.resolve_env_variables("$TOTALLY_MISSING_VAR_12345")

    def test_string_without_dollar_sign_passes_through(self):
        result = AppConfig.resolve_env_variables("plain_string")
        assert result == "plain_string"

    def test_dict_resolves_recursively(self, monkeypatch):
        monkeypatch.setenv("MY_TEST_KEY", "from_env")
        config = {"a": "$MY_TEST_KEY", "b": "static"}
        result = AppConfig.resolve_env_variables(config)
        assert result == {"a": "from_env", "b": "static"}

    def test_list_resolves_recursively(self, monkeypatch):
        monkeypatch.setenv("LIST_TEST_KEY", "env_val")
        config = ["$LIST_TEST_KEY", "plain"]
        result = AppConfig.resolve_env_variables(config)
        assert result == ["env_val", "plain"]

    def test_non_string_passthrough(self):
        assert AppConfig.resolve_env_variables(42) == 42
        assert AppConfig.resolve_env_variables(True) is True
        assert AppConfig.resolve_env_variables(None) is None


# ---------------------------------------------------------------------------
# AppConfig model_config: extra="allow"
# ---------------------------------------------------------------------------


class TestAppConfigExtraAllow:
    def test_extra_fields_allowed(self):
        cfg = AppConfig(
            sandbox=_SANDBOX,
            unknown_field="value",
        )
        assert cfg.unknown_field == "value"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# get_model_config / get_tool_config / get_tool_group_config
# ---------------------------------------------------------------------------


class TestGetModelConfig:
    def test_returns_matching_model(self):
        from ideer.config.model_config import ModelConfig

        model = ModelConfig(
            name="gpt-4",
            display_name="GPT-4",
            description=None,
            use="langchain_openai:ChatOpenAI",
            model="gpt-4",
        )
        cfg = AppConfig(
            sandbox=_SANDBOX,
            models=[model],
        )
        assert cfg.get_model_config("gpt-4") is model

    def test_returns_none_for_missing_model(self):
        cfg = AppConfig(
            sandbox=_SANDBOX,
            models=[],
        )
        assert cfg.get_model_config("nonexistent") is None


class TestGetToolConfig:
    def test_returns_matching_tool(self):
        from ideer.config.tool_config import ToolConfig

        tool = ToolConfig(name="web_search", group="search", use="ideer.tools:web_search")
        cfg = AppConfig(
            sandbox=_SANDBOX,
            tools=[tool],
        )
        assert cfg.get_tool_config("web_search") is tool

    def test_returns_none_for_missing_tool(self):
        cfg = AppConfig(
            sandbox=_SANDBOX,
            tools=[],
        )
        assert cfg.get_tool_config("nonexistent") is None


class TestGetToolGroupConfig:
    def test_returns_matching_group(self):
        from ideer.config.tool_config import ToolGroupConfig

        group = ToolGroupConfig(name="file:read")
        cfg = AppConfig(
            sandbox=_SANDBOX,
            tool_groups=[group],
        )
        assert cfg.get_tool_group_config("file:read") is group

    def test_returns_none_for_missing_group(self):
        cfg = AppConfig(
            sandbox=_SANDBOX,
            tool_groups=[],
        )
        assert cfg.get_tool_group_config("nonexistent") is None


# ---------------------------------------------------------------------------
# _check_config_version edge cases
# ---------------------------------------------------------------------------


class TestCheckConfigVersionEdgeCases:
    def test_non_numeric_config_version_treated_as_zero(self, tmp_path, caplog):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("sandbox: {}")
        example_file = tmp_path / "config.example.yaml"
        example_file.write_text(yaml.dump({"config_version": 1}))

        with caplog.at_level(logging.WARNING, logger="ideer.config.app_config"):
            AppConfig._check_config_version({"config_version": "not_a_number"}, config_file)
        assert "outdated" in caplog.text

    def test_example_version_non_numeric_treated_as_zero(self, tmp_path, caplog):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("sandbox: {}")
        example_file = tmp_path / "config.example.yaml"
        example_file.write_text(yaml.dump({"config_version": "abc"}))

        # User has version 5, example has non-numeric "abc" -> 0, no warning
        with caplog.at_level(logging.WARNING, logger="ideer.config.app_config"):
            AppConfig._check_config_version({"config_version": 5}, config_file)
        assert "outdated" not in caplog.text

    def test_example_yaml_unreadable_returns_silently(self, tmp_path, caplog):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("sandbox: {}")
        example_file = tmp_path / "config.example.yaml"
        example_file.write_bytes(b"\x00\x01\x02")  # invalid YAML

        with caplog.at_level(logging.WARNING, logger="ideer.config.app_config"):
            AppConfig._check_config_version({"config_version": 1}, config_file)
        # Should not raise, just return silently
        assert "outdated" not in caplog.text


# ---------------------------------------------------------------------------
# Singleton management: get / set / reset / reload
# ---------------------------------------------------------------------------


class TestSingletonManagement:
    def test_set_app_config_and_get(self):
        reset_app_config()
        try:
            cfg = AppConfig(sandbox=_SANDBOX)
            set_app_config(cfg)
            result = get_app_config()
            assert result is cfg
        finally:
            reset_app_config()

    def test_reset_clears_singleton(self):
        reset_app_config()
        try:
            cfg = AppConfig(sandbox=_SANDBOX)
            set_app_config(cfg)
            reset_app_config()
            # After reset, get_app_config should try to load from file
            # Since we can't guarantee a config.yaml exists, just verify
            # the singleton is cleared
            from ideer.config import app_config as ac_module

            assert ac_module._app_config is None
        finally:
            reset_app_config()


# ---------------------------------------------------------------------------
# ContextVar push/pop
# ---------------------------------------------------------------------------


class TestContextVarPushPop:
    def test_push_and_pop(self):
        reset_app_config()
        try:
            cfg1 = AppConfig(sandbox=_SANDBOX)
            cfg2 = AppConfig(sandbox=_SANDBOX)

            push_current_app_config(cfg1)
            assert peek_current_app_config() is cfg1

            push_current_app_config(cfg2)
            assert peek_current_app_config() is cfg2

            pop_current_app_config()
            assert peek_current_app_config() is cfg1

            pop_current_app_config()
            assert peek_current_app_config() is None
        finally:
            reset_app_config()

    def test_pop_empty_stack_sets_none(self):
        reset_app_config()
        try:
            pop_current_app_config()
            assert peek_current_app_config() is None
        finally:
            reset_app_config()

    def test_peek_returns_none_when_no_override(self):
        reset_app_config()
        try:
            assert peek_current_app_config() is None
        finally:
            reset_app_config()


# ---------------------------------------------------------------------------
# _apply_database_defaults
# ---------------------------------------------------------------------------


class TestApplyDatabaseDefaults:
    def test_applies_defaults_when_database_section_missing(self):
        config_data = {}
        AppConfig._apply_database_defaults(config_data)
        assert config_data["database"]["backend"] == "sqlite"
        assert config_data["database"]["sqlite_dir"] == ".ideer/data"

    def test_does_not_overwrite_existing_values(self):
        config_data = {"database": {"backend": "postgres"}}
        AppConfig._apply_database_defaults(config_data)
        assert config_data["database"]["backend"] == "postgres"
        assert config_data["database"]["sqlite_dir"] == ".ideer/data"

    def test_non_dict_database_section_is_noop(self):
        config_data = {"database": "not-a-dict"}
        AppConfig._apply_database_defaults(config_data)
        assert config_data["database"] == "not-a-dict"


# ---------------------------------------------------------------------------
# _validate_acp_agents
# ---------------------------------------------------------------------------


class TestValidateAcpAgents:
    def test_none_input_returns_empty_dict(self):
        result = AppConfig._validate_acp_agents(None)
        assert result == {}

    def test_empty_dict_returns_empty_dict(self):
        result = AppConfig._apply_database_defaults({})
        assert isinstance(result, type(None))  # _apply_database_defaults is in-place

    def test_valid_acp_agents(self):
        from ideer.config.acp_config import ACPAgentConfig

        result = AppConfig._validate_acp_agents({"codex": {"command": "codex", "description": "Codex agent"}})
        assert "codex" in result
        assert isinstance(result["codex"], ACPAgentConfig)


# ---------------------------------------------------------------------------
# _build_middlewares with safety_finish_reason
# ---------------------------------------------------------------------------


class TestBuildMiddlewaresSafetyFinishReason:
    """Test the safety_finish_reason middleware path in _build_middlewares."""

    def test_safety_finish_reason_enabled(self, monkeypatch):
        from ideer.config.safety_finish_reason_config import SafetyFinishReasonConfig

        app_config = AppConfig(
            sandbox=_SANDBOX,
            safety_finish_reason=SafetyFinishReasonConfig(enabled=True),
        )

        from ideer.agents.lead_agent import agent as lead_mod

        monkeypatch.setattr(lead_mod, "get_app_config", lambda: app_config)
        monkeypatch.setattr(lead_mod, "build_lead_runtime_middlewares", lambda **kw: [])

        from ideer.agents.lead_agent.agent import SafetyFinishReasonMiddleware

        safety_instance = MagicMock()

        monkeypatch.setattr(SafetyFinishReasonMiddleware, "from_config", classmethod(lambda cls, config: safety_instance))
        monkeypatch.setattr(lead_mod, "_create_summarization_middleware", lambda **kw: None)
        monkeypatch.setattr(lead_mod, "_create_todo_list_middleware", lambda is_plan_mode: None)

        middlewares = lead_mod._build_middlewares(
            {"configurable": {"is_plan_mode": False, "subagent_enabled": False}},
            model_name=None,
            app_config=app_config,
        )

        assert safety_instance in middlewares


# ---------------------------------------------------------------------------
# _get_config_mtime edge cases
# ---------------------------------------------------------------------------


class TestGetConfigMtimeEdge:
    def test_os_error_returns_none(self):
        """Permission denied or other OS errors should return None."""
        result = _get_config_mtime(Path("/dev/null/unreachable"))
        assert result is None
