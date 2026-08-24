"""Tests for network mode detection (online/offline).

Covers:
- Environment variable parsing (IDEER_NETWORK_MODE)
- Default behavior (online)
- Unrecognized values (warn + default to online)
- is_offline convenience function
"""

from __future__ import annotations

import os
from unittest.mock import patch

from ideer.config.network_mode import NetworkMode, get_network_mode, is_offline


class TestNetworkModeEnum:
    """Tests for the NetworkMode enum."""

    def test_online_value(self):
        assert NetworkMode.ONLINE == "online"

    def test_offline_value(self):
        assert NetworkMode.OFFLINE == "offline"

    def test_has_two_members(self):
        assert len(NetworkMode) == 2


class TestGetNetworkMode:
    """Tests for get_network_mode()."""

    def test_default_is_online(self):
        """When IDEER_NETWORK_MODE is not set, defaults to online."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IDEER_NETWORK_MODE", None)
            assert get_network_mode() == NetworkMode.ONLINE

    def test_explicit_online(self):
        with patch.dict(os.environ, {"IDEER_NETWORK_MODE": "online"}):
            assert get_network_mode() == NetworkMode.ONLINE

    def test_explicit_offline(self):
        with patch.dict(os.environ, {"IDEER_NETWORK_MODE": "offline"}):
            assert get_network_mode() == NetworkMode.OFFLINE

    def test_case_insensitive(self):
        with patch.dict(os.environ, {"IDEER_NETWORK_MODE": "OFFLINE"}):
            assert get_network_mode() == NetworkMode.OFFLINE

    def test_mixed_case(self):
        with patch.dict(os.environ, {"IDEER_NETWORK_MODE": "Online"}):
            assert get_network_mode() == NetworkMode.ONLINE

    def test_unrecognized_value_defaults_to_online(self):
        """Unrecognized values warn and default to online."""
        with patch.dict(os.environ, {"IDEER_NETWORK_MODE": "vpn"}):
            assert get_network_mode() == NetworkMode.ONLINE

    def test_empty_string_defaults_to_online(self):
        with patch.dict(os.environ, {"IDEER_NETWORK_MODE": ""}):
            assert get_network_mode() == NetworkMode.ONLINE


class TestIsOffline:
    """Tests for the is_offline() convenience function."""

    def test_returns_false_when_online(self):
        with patch.dict(os.environ, {"IDEER_NETWORK_MODE": "online"}):
            assert is_offline() is False

    def test_returns_true_when_offline(self):
        with patch.dict(os.environ, {"IDEER_NETWORK_MODE": "offline"}):
            assert is_offline() is True

    def test_returns_false_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IDEER_NETWORK_MODE", None)
            assert is_offline() is False
