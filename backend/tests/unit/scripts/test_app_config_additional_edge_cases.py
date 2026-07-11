"""Extra coverage tests for app_config.py missed lines.

Targets: 72-73, 86-91, 147, 152, 247->256, 379, 388->396, 412
"""

import logging
from unittest.mock import patch

import pytest

from ideer.config.app_config import (
    AppConfig,
    apply_logging_level,
    get_app_config,
    logging_level_from_config,
    pop_current_app_config,
    push_current_app_config,
    reload_app_config,
    reset_app_config,
    set_app_config,
)
from ideer.config.sandbox_config import SandboxConfig

_SANDBOX = SandboxConfig(use="ideer.sandbox.local:LocalSandboxProvider")


# --- Lines 72-73: logging_level_from_config ---


def test_logging_level_from_config_default():
    """Line 72-73: Returns INFO for None or empty string."""
    assert logging_level_from_config(None) == logging.INFO
    assert logging_level_from_config("") == logging.INFO


def test_logging_level_from_config_debug():
    """Line 72-73: Maps debug string to DEBUG level."""
    assert logging_level_from_config("debug") == logging.DEBUG


def test_logging_level_from_config_unknown():
    """Line 72-73: Falls back to INFO for unknown level."""
    assert logging_level_from_config("verbose") == logging.INFO


# --- Lines 86-91: apply_logging_level ---


def test_apply_logging_level_sets_logger_levels():
    """Lines 86-91: Sets ideer and app logger levels."""
    apply_logging_level("debug")
    assert logging.getLogger("ideer").level == logging.DEBUG
    assert logging.getLogger("app").level == logging.DEBUG
    # Restore
    apply_logging_level("info")


def test_apply_logging_level_lowers_handler_levels():
    """Lines 89-91: Lowers handler levels when config level is lower."""
    handler = logging.StreamHandler()
    handler.setLevel(logging.WARNING)
    logging.root.addHandler(handler)
    try:
        apply_logging_level("debug")
        # Handler level should be lowered to DEBUG
        assert handler.level <= logging.DEBUG
    finally:
        logging.root.removeHandler(handler)
        apply_logging_level("info")


# --- Line 147: resolve_config_path with project config ---


def test_resolve_config_path_finds_project_config(tmp_path, monkeypatch):
    """Line 147: Falls back to existing_project_file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("sandbox: {}")
    monkeypatch.delenv("IDEER_CONFIG_PATH", raising=False)

    with patch("ideer.config.app_config.existing_project_file", return_value=config_file):
        result = AppConfig.resolve_config_path()
    assert result == config_file


# --- Line 152: resolve_config_path legacy fallback ---


def test_resolve_config_path_finds_legacy_config(tmp_path, monkeypatch):
    """Line 152: Falls back to legacy candidates."""
    monkeypatch.delenv("IDEER_CONFIG_PATH", raising=False)

    legacy = tmp_path / "config.yaml"
    legacy.write_text("sandbox: {}")

    with (
        patch("ideer.config.app_config.existing_project_file", return_value=None),
        patch("ideer.config.app_config._legacy_config_candidates", return_value=(legacy,)),
    ):
        result = AppConfig.resolve_config_path()
    assert result == legacy


def test_resolve_config_path_raises_when_nothing_found(monkeypatch):
    """Line 152: Raises FileNotFoundError when no config found."""
    monkeypatch.delenv("IDEER_CONFIG_PATH", raising=False)

    with (
        patch("ideer.config.app_config.existing_project_file", return_value=None),
        patch("ideer.config.app_config._legacy_config_candidates", return_value=()),
    ):
        with pytest.raises(FileNotFoundError, match="config.yaml"):
            AppConfig.resolve_config_path()


# --- Line 379: get_app_config with runtime override ---


def test_get_app_config_returns_runtime_override():
    """Line 379: Returns runtime ContextVar override when set."""
    reset_app_config()
    try:
        cfg = AppConfig(sandbox=_SANDBOX)
        push_current_app_config(cfg)
        result = get_app_config()
        assert result is cfg
    finally:
        pop_current_app_config()
        reset_app_config()


# --- Lines 388-396: get_app_config with custom config ---


def test_get_app_config_returns_custom_config():
    """Lines 388-396: Returns custom config set via set_app_config."""
    reset_app_config()
    try:
        cfg = AppConfig(sandbox=_SANDBOX)
        set_app_config(cfg)
        result = get_app_config()
        assert result is cfg
    finally:
        reset_app_config()


# --- Line 412: reload_app_config ---


def test_reload_app_config(tmp_path):
    """Line 412: reload_app_config loads config from file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("sandbox:\n  use: ideer.sandbox.local:LocalSandboxProvider\n")

    reset_app_config()
    try:
        result = reload_app_config(str(config_file))
        assert isinstance(result, AppConfig)
        assert result.sandbox.use == "ideer.sandbox.local:LocalSandboxProvider"
    finally:
        reset_app_config()


# --- get_app_config with mtime change ---


def test_get_app_config_reloads_on_mtime_change(tmp_path):
    """get_app_config reloads when file mtime changes."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("sandbox:\n  use: ideer.sandbox.local:LocalSandboxProvider\nlog_level: info\n")

    reset_app_config()
    try:
        # First load
        with patch("ideer.config.app_config.AppConfig.resolve_config_path", return_value=config_file):
            cfg1 = get_app_config()
        assert cfg1.log_level == "info"

        # Modify file
        import time

        time.sleep(0.1)
        config_file.write_text("sandbox:\n  use: ideer.sandbox.local:LocalSandboxProvider\nlog_level: debug\n")

        # Second load should pick up changes
        with patch("ideer.config.app_config.AppConfig.resolve_config_path", return_value=config_file):
            cfg2 = get_app_config()
        assert cfg2.log_level == "debug"
    finally:
        reset_app_config()
