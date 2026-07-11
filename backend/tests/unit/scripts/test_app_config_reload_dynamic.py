"""Tests for dynamic config hot-reload edge cases.

Based on first-principles analysis of ``get_app_config()`` behavior:
- ``_get_config_mtime`` returns ``None`` on OSError (deleted file)
- ``resolve_config_path`` raises ``FileNotFoundError`` when file vanishes
- ``yaml.safe_load`` / ``model_validate`` raise on invalid content
- On any exception in ``_load_and_cache_app_config``, globals (``_app_config``,
  ``_app_config_path``, ``_app_config_mtime``) are never updated, so the old
  cached config survives and a subsequent successful call picks up the new file.
- ContextVar override and custom config (``set_app_config``) short-circuit file
  reload regardless of mtime changes.
- Symlink target replacement is transparent to mtime comparison because
  ``Path.stat()`` follows symlinks.
"""

from __future__ import annotations

import os

import pytest
import yaml
from pydantic import ValidationError

import ideer.config.app_config as app_config_module
from ideer.config.app_config import (
    get_app_config,
    pop_current_app_config,
    push_current_app_config,
    reload_app_config,
    reset_app_config,
    set_app_config,
)
from tests.helpers.app_config_helpers import (
    _reset_config_singletons,
    _write_config,
    _write_extensions_config,
)

pytestmark = pytest.mark.serial


def test_get_app_config_reloads_broken_yaml_preserves_old_config(tmp_path, monkeypatch):
    """Broken YAML → load raises → old config cached → fix file → reload picks new."""
    config_path = tmp_path / "config.yaml"
    extensions_path = tmp_path / "extensions_config.json"
    _write_extensions_config(extensions_path)
    _write_config(config_path, model_name="first-model", supports_thinking=False)

    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("IDEER_EXTENSIONS_CONFIG_PATH", str(extensions_path))
    reset_app_config()

    try:
        initial = get_app_config()
        assert initial.models[0].name == "first-model"

        config_path.write_text("broken: [invalid")
        next_mtime = config_path.stat().st_mtime + 5
        os.utime(config_path, (next_mtime, next_mtime))

        with pytest.raises(yaml.YAMLError):
            get_app_config()

        assert app_config_module._app_config is initial

        _write_config(config_path, model_name="second-model", supports_thinking=True)
        next_mtime = config_path.stat().st_mtime + 5
        os.utime(config_path, (next_mtime, next_mtime))

        reloaded = get_app_config()
        assert reloaded.models[0].name == "second-model"
        assert reloaded.models[0].supports_thinking is True
        assert reloaded is not initial
    finally:
        _reset_config_singletons()


def test_get_app_config_reloads_empty_file_preserves_old_config(tmp_path, monkeypatch):
    """Empty file → yaml.safe_load returns None → {} → ValidationError → old config unchanged."""
    config_path = tmp_path / "config.yaml"
    extensions_path = tmp_path / "extensions_config.json"
    _write_extensions_config(extensions_path)
    _write_config(config_path, model_name="first-model", supports_thinking=False)

    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("IDEER_EXTENSIONS_CONFIG_PATH", str(extensions_path))
    reset_app_config()

    try:
        initial = get_app_config()
        assert initial.models[0].name == "first-model"

        config_path.write_text("")
        next_mtime = config_path.stat().st_mtime + 5
        os.utime(config_path, (next_mtime, next_mtime))

        with pytest.raises(ValidationError):
            get_app_config()

        assert app_config_module._app_config is initial

        _write_config(config_path, model_name="second-model", supports_thinking=True)
        next_mtime = config_path.stat().st_mtime + 5
        os.utime(config_path, (next_mtime, next_mtime))

        reloaded = get_app_config()
        assert reloaded.models[0].name == "second-model"
        assert reloaded is not initial
    finally:
        _reset_config_singletons()


def test_get_app_config_reloads_deleted_file_keeps_cached_config(tmp_path, monkeypatch):
    """Deleted file → resolve_config_path raises FileNotFoundError → old config survives → recreate → reload."""
    config_path = tmp_path / "config.yaml"
    extensions_path = tmp_path / "extensions_config.json"
    _write_extensions_config(extensions_path)
    _write_config(config_path, model_name="first-model", supports_thinking=False)

    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("IDEER_EXTENSIONS_CONFIG_PATH", str(extensions_path))
    reset_app_config()

    try:
        initial = get_app_config()
        assert initial.models[0].name == "first-model"

        config_path.unlink()

        with pytest.raises(FileNotFoundError):
            get_app_config()

        assert app_config_module._app_config is initial

        _write_config(config_path, model_name="second-model", supports_thinking=True)
        next_mtime = config_path.stat().st_mtime + 5
        os.utime(config_path, (next_mtime, next_mtime))

        reloaded = get_app_config()
        assert reloaded.models[0].name == "second-model"
        assert reloaded is not initial
    finally:
        _reset_config_singletons()


def test_get_app_config_reloads_rapid_changes(tmp_path, monkeypatch):
    """Multiple rapid writes → mtime comparison triggers one reload reading current content (model-D)."""
    config_path = tmp_path / "config.yaml"
    extensions_path = tmp_path / "extensions_config.json"
    _write_extensions_config(extensions_path)

    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("IDEER_EXTENSIONS_CONFIG_PATH", str(extensions_path))
    reset_app_config()

    try:
        _write_config(config_path, model_name="model-A", supports_thinking=False)
        initial = get_app_config()
        assert initial.models[0].name == "model-A"

        _write_config(config_path, model_name="model-B", supports_thinking=True)
        _write_config(config_path, model_name="model-C", supports_thinking=False)
        _write_config(config_path, model_name="model-D", supports_thinking=True)
        next_mtime = config_path.stat().st_mtime + 5
        os.utime(config_path, (next_mtime, next_mtime))

        reloaded = get_app_config()
        assert reloaded.models[0].name == "model-D"
        assert reloaded.models[0].supports_thinking is True
        assert reloaded is not initial
    finally:
        _reset_config_singletons()


def test_get_app_config_reloads_handles_missing_file(tmp_path):
    """reload_app_config with nonexistent path → FileNotFoundError."""
    non_existent = tmp_path / "nonexistent.yaml"

    with pytest.raises(FileNotFoundError):
        reload_app_config(str(non_existent))

    reset_app_config()


def test_get_app_config_reloads_ignores_file_when_contextvar_active(tmp_path, monkeypatch):
    """ContextVar override → file changes → get_app_config returns ContextVar config."""
    config_path = tmp_path / "config.yaml"
    extensions_path = tmp_path / "extensions_config.json"
    _write_extensions_config(extensions_path)
    _write_config(config_path, model_name="first-model", supports_thinking=False)

    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("IDEER_EXTENSIONS_CONFIG_PATH", str(extensions_path))
    reset_app_config()

    try:
        initial = get_app_config()
        assert initial.models[0].name == "first-model"

        push_current_app_config(initial)

        _write_config(config_path, model_name="second-model", supports_thinking=True)
        next_mtime = config_path.stat().st_mtime + 5
        os.utime(config_path, (next_mtime, next_mtime))

        result = get_app_config()
        assert result is initial
        assert result.models[0].name == "first-model"
    finally:
        pop_current_app_config()
        _reset_config_singletons()


def test_get_app_config_reloads_ignores_file_when_custom_config_set(tmp_path, monkeypatch):
    """set_app_config custom config → file changes → get_app_config returns custom config."""
    config_path = tmp_path / "config.yaml"
    extensions_path = tmp_path / "extensions_config.json"
    _write_extensions_config(extensions_path)
    _write_config(config_path, model_name="first-model", supports_thinking=False)

    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("IDEER_EXTENSIONS_CONFIG_PATH", str(extensions_path))
    reset_app_config()

    try:
        initial = get_app_config()
        assert initial.models[0].name == "first-model"

        set_app_config(initial)

        _write_config(config_path, model_name="second-model", supports_thinking=True)
        next_mtime = config_path.stat().st_mtime + 5
        os.utime(config_path, (next_mtime, next_mtime))

        result = get_app_config()
        assert result is initial
        assert result.models[0].name == "first-model"
    finally:
        _reset_config_singletons()


def test_get_app_config_reloads_invalid_yaml_raises(tmp_path):
    """reload_app_config with syntactically-invalid YAML → yaml.YAMLError."""
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text("{broken: [yaml", encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        reload_app_config(str(config_path))


def test_get_app_config_reloads_from_symlink_update(tmp_path, monkeypatch):
    """Symlink target replacement → mtime change → reload picks up new target content."""
    config_a = tmp_path / "real_config_a.yaml"
    config_b = tmp_path / "real_config_b.yaml"
    link_path = tmp_path / "link_config.yaml"
    extensions_path = tmp_path / "extensions_config.json"

    _write_extensions_config(extensions_path)
    _write_config(config_a, model_name="model-a", supports_thinking=False)
    _write_config(config_b, model_name="model-b", supports_thinking=True)

    link_path.symlink_to(config_a)

    monkeypatch.setenv("IDEER_CONFIG_PATH", str(link_path))
    monkeypatch.setenv("IDEER_EXTENSIONS_CONFIG_PATH", str(extensions_path))
    reset_app_config()

    try:
        initial = get_app_config()
        assert initial.models[0].name == "model-a"

        link_path.unlink()
        link_path.symlink_to(config_b)
        next_mtime = config_b.stat().st_mtime + 5
        os.utime(config_b, (next_mtime, next_mtime))

        reloaded = get_app_config()
        assert reloaded.models[0].name == "model-b"
        assert reloaded is not initial
    finally:
        _reset_config_singletons()


def test_get_app_config_reloads_file_permission_change(tmp_path, monkeypatch):
    """File becomes unreadable → PermissionError → old config survives → restore → reload."""
    config_path = tmp_path / "config.yaml"
    extensions_path = tmp_path / "extensions_config.json"
    _write_extensions_config(extensions_path)
    _write_config(config_path, model_name="first-model", supports_thinking=False)

    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("IDEER_EXTENSIONS_CONFIG_PATH", str(extensions_path))
    reset_app_config()

    try:
        initial = get_app_config()
        assert initial.models[0].name == "first-model"

        next_mtime = config_path.stat().st_mtime + 5
        os.utime(config_path, (next_mtime, next_mtime))
        config_path.chmod(0o000)

        with pytest.raises(PermissionError):
            get_app_config()

        assert app_config_module._app_config is initial

        config_path.chmod(0o644)
        _write_config(config_path, model_name="second-model", supports_thinking=True)
        next_mtime = config_path.stat().st_mtime + 5
        os.utime(config_path, (next_mtime, next_mtime))

        reloaded = get_app_config()
        assert reloaded.models[0].name == "second-model"
    finally:
        try:
            config_path.chmod(0o644)
        except OSError:
            pass
        _reset_config_singletons()
