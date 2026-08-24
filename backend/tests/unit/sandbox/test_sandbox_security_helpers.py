"""Tests for sandbox security helpers.

Covers:
- uses_local_sandbox_provider: detecting LocalSandboxProvider in config
- is_host_bash_allowed: permission gating for host bash execution
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ideer.sandbox.security import (
    LOCAL_BASH_SUBAGENT_DISABLED_MESSAGE,
    LOCAL_HOST_BASH_DISABLED_MESSAGE,
    is_host_bash_allowed,
    uses_local_sandbox_provider,
)


def _make_config(sandbox_use: str = "", allow_host_bash: bool = False):
    """Build a minimal config object with sandbox settings."""
    sandbox = SimpleNamespace(use=sandbox_use, allow_host_bash=allow_host_bash)
    return SimpleNamespace(sandbox=sandbox)


def _make_config_no_sandbox():
    """Config with no sandbox attribute."""
    return SimpleNamespace()


# ── uses_local_sandbox_provider ─────────────────────────────────────


class TestUsesLocalSandboxProvider:
    """Tests for uses_local_sandbox_provider()."""

    def test_short_marker(self):
        config = _make_config("ideer.sandbox.local:LocalSandboxProvider")
        assert uses_local_sandbox_provider(config) is True

    def test_full_path_marker(self):
        config = _make_config("ideer.sandbox.local.local_sandbox_provider:LocalSandboxProvider")
        assert uses_local_sandbox_provider(config) is True

    def test_aio_sandbox_provider(self):
        config = _make_config("ideer.sandbox.aio:AioSandboxProvider")
        assert uses_local_sandbox_provider(config) is False

    def test_empty_use_string(self):
        config = _make_config("")
        assert uses_local_sandbox_provider(config) is False

    def test_custom_local_provider_suffix(self):
        """Any string ending with ':LocalSandboxProvider' and containing 'ideer.sandbox.local'."""
        config = _make_config("custom.ideer.sandbox.local.foo:LocalSandboxProvider")
        assert uses_local_sandbox_provider(config) is True

    def test_local_sandbox_provider_without_local_in_path(self):
        """':LocalSandboxProvider' without 'ideer.sandbox.local' should be False."""
        config = _make_config("other.module:LocalSandboxProvider")
        assert uses_local_sandbox_provider(config) is False

    def test_no_sandbox_attribute(self):
        config = _make_config_no_sandbox()
        assert uses_local_sandbox_provider(config) is False

    def test_sandbox_use_none_raises(self):
        """When sandbox.use is explicitly None, getattr returns None (not ''),
        and .endswith() raises AttributeError. This documents a known edge case."""
        config = SimpleNamespace(sandbox=SimpleNamespace(use=None, allow_host_bash=False))
        with pytest.raises(AttributeError):
            uses_local_sandbox_provider(config)


# ── is_host_bash_allowed ────────────────────────────────────────────


class TestIsHostBashAllowed:
    """Tests for is_host_bash_allowed()."""

    def test_allowed_when_not_local_provider(self):
        """Non-local providers always allow bash (no restriction)."""
        config = _make_config("ideer.sandbox.aio:AioSandboxProvider", allow_host_bash=False)
        assert is_host_bash_allowed(config) is True

    def test_disallowed_when_local_provider_and_flag_false(self):
        config = _make_config("ideer.sandbox.local:LocalSandboxProvider", allow_host_bash=False)
        assert is_host_bash_allowed(config) is False

    def test_allowed_when_local_provider_and_flag_true(self):
        config = _make_config("ideer.sandbox.local:LocalSandboxProvider", allow_host_bash=True)
        assert is_host_bash_allowed(config) is True

    def test_no_sandbox_attribute(self):
        config = _make_config_no_sandbox()
        assert is_host_bash_allowed(config) is False

    def test_no_sandbox_returns_false(self):
        """When config has no sandbox attribute at all."""
        config = SimpleNamespace()
        assert is_host_bash_allowed(config) is False


# ── Constants ────────────────────────────────────────────────────────


class TestConstants:
    """Verify the disabled messages are non-empty strings."""

    def test_local_host_bash_disabled_message(self):
        assert isinstance(LOCAL_HOST_BASH_DISABLED_MESSAGE, str)
        assert len(LOCAL_HOST_BASH_DISABLED_MESSAGE) > 0

    def test_local_bash_subagent_disabled_message(self):
        assert isinstance(LOCAL_BASH_SUBAGENT_DISABLED_MESSAGE, str)
        assert len(LOCAL_BASH_SUBAGENT_DISABLED_MESSAGE) > 0
