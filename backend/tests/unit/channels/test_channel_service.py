"""Comprehensive tests for app.channels.service — targeting 98%+ coverage."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_channel_mock(name: str = "test", *, running: bool = True) -> MagicMock:
    """Return a mock Channel with controllable is_running."""
    ch = MagicMock()
    ch.name = name
    ch.is_running = running
    ch.start = AsyncMock()
    ch.stop = AsyncMock()
    return ch


def _make_app_config(extra: dict[str, Any] | None = None) -> MagicMock:
    """Return a mock AppConfig whose model_extra contains *extra*."""
    cfg = MagicMock()
    cfg.model_extra = extra or {}
    return cfg


# ---------------------------------------------------------------------------
# _resolve_service_url
# ---------------------------------------------------------------------------


class TestResolveServiceUrl:
    """Tests for the module-level _resolve_service_url helper."""

    def test_config_value_used(self):
        from app.channels.service import _resolve_service_url

        config = {"my_key": "http://from-config"}
        result = _resolve_service_url(config, "my_key", "UNUSED_ENV", "http://default")
        assert result == "http://from-config"
        # config key is popped
        assert "my_key" not in config

    def test_config_value_empty_string_falls_through(self):
        from app.channels.service import _resolve_service_url

        config: dict[str, Any] = {"my_key": "   "}
        result = _resolve_service_url(config, "my_key", "UNUSED_ENV", "http://default")
        assert result == "http://default"

    def test_config_value_not_string_falls_through(self):
        from app.channels.service import _resolve_service_url

        config: dict[str, Any] = {"my_key": 123}
        result = _resolve_service_url(config, "my_key", "UNUSED_ENV", "http://default")
        assert result == "http://default"

    def test_env_value_used(self):
        from app.channels.service import _resolve_service_url

        config: dict[str, Any] = {}
        with patch.dict(os.environ, {"TEST_SVC_URL": "http://from-env"}):
            result = _resolve_service_url(config, "my_key", "TEST_SVC_URL", "http://default")
        assert result == "http://from-env"

    def test_env_value_empty_falls_through(self):
        from app.channels.service import _resolve_service_url

        config: dict[str, Any] = {}
        with patch.dict(os.environ, {"TEST_SVC_URL": "   "}):
            result = _resolve_service_url(config, "my_key", "TEST_SVC_URL", "http://default")
        assert result == "http://default"

    def test_default_used(self):
        from app.channels.service import _resolve_service_url

        config: dict[str, Any] = {}
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NONEXISTENT_ENV", None)
            result = _resolve_service_url(config, "my_key", "NONEXISTENT_ENV", "http://default")
        assert result == "http://default"


# ---------------------------------------------------------------------------
# ChannelService.__init__
# ---------------------------------------------------------------------------


class TestChannelServiceInit:
    """Tests for ChannelService.__init__ constructor logic."""

    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    def test_init_default(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        svc = ChannelService()
        mock_bus_cls.assert_called_once()
        mock_store_cls.assert_called_once()
        mock_mgr_cls.assert_called_once()
        assert svc._channels == {}
        assert svc._running is False

    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    def test_init_with_langgraph_url_in_config(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        config = {"langgraph_url": "http://custom-lg", "gateway_url": "http://custom-gw"}
        ChannelService(channels_config=config)
        # langgraph_url and gateway_url should be popped and passed to manager
        call_kwargs = mock_mgr_cls.call_args
        assert call_kwargs.kwargs["langgraph_url"] == "http://custom-lg"
        assert call_kwargs.kwargs["gateway_url"] == "http://custom-gw"

    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    def test_init_with_session_dict(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        config: dict[str, Any] = {"session": {"assistant_id": "custom"}}
        ChannelService(channels_config=config)
        call_kwargs = mock_mgr_cls.call_args.kwargs
        assert call_kwargs["default_session"] == {"assistant_id": "custom"}

    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    def test_init_with_session_non_dict(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        config: dict[str, Any] = {"session": "invalid"}
        ChannelService(channels_config=config)
        call_kwargs = mock_mgr_cls.call_args.kwargs
        assert call_kwargs["default_session"] is None

    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    def test_init_channel_sessions_extracted(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        config: dict[str, Any] = {
            "slack": {"enabled": True, "session": {"assistant_id": "a1"}},
            "feishu": {"enabled": True},
            "not_a_dict": 42,
        }
        ChannelService(channels_config=config)
        call_kwargs = mock_mgr_cls.call_args.kwargs
        # slack has session, feishu has None, not_a_dict skipped (not dict)
        assert call_kwargs["channel_sessions"]["slack"] == {"assistant_id": "a1"}
        assert call_kwargs["channel_sessions"]["feishu"] is None
        assert "not_a_dict" not in call_kwargs["channel_sessions"]

    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    def test_init_none_config(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        svc = ChannelService(channels_config=None)
        assert svc._config == {}


# ---------------------------------------------------------------------------
# ChannelService.from_app_config
# ---------------------------------------------------------------------------


class TestFromAppConfig:
    """Tests for the from_app_config classmethod."""

    @patch("app.channels.service.ChannelService.__init__", return_value=None)
    def test_from_app_config_with_channels(self, mock_init):
        from app.channels.service import ChannelService

        app_cfg = _make_app_config(extra={"channels": {"slack": {"enabled": True}}})
        ChannelService.from_app_config(app_cfg)
        mock_init.assert_called_once_with(channels_config={"slack": {"enabled": True}})

    @patch("app.channels.service.ChannelService.__init__", return_value=None)
    def test_from_app_config_without_channels_key(self, mock_init):
        from app.channels.service import ChannelService

        app_cfg = _make_app_config(extra={})
        ChannelService.from_app_config(app_cfg)
        mock_init.assert_called_once_with(channels_config={})

    @patch("app.channels.service.ChannelService.__init__", return_value=None)
    def test_from_app_config_none_extra(self, mock_init):
        from app.channels.service import ChannelService

        app_cfg = _make_app_config(extra=None)
        app_cfg.model_extra = None
        ChannelService.from_app_config(app_cfg)
        mock_init.assert_called_once_with(channels_config={})

    @patch("ideer.config.app_config.get_app_config")
    @patch("app.channels.service.ChannelService.__init__", return_value=None)
    def test_from_app_config_none_uses_get_app_config(self, mock_init, mock_get):
        from app.channels.service import ChannelService

        mock_get.return_value = _make_app_config(extra={"channels": {"feishu": {}}})
        ChannelService.from_app_config(None)
        mock_get.assert_called_once()
        mock_init.assert_called_once_with(channels_config={"feishu": {}})


# ---------------------------------------------------------------------------
# ChannelService.start
# ---------------------------------------------------------------------------


class TestChannelServiceStart:
    """Tests for ChannelService.start."""

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_start_already_running(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        svc = ChannelService()
        svc._running = True
        await svc.start()
        # manager.start() should not be called
        mock_mgr_cls.return_value.start.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_start_no_channels(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        svc = ChannelService()
        svc.manager = AsyncMock()
        await svc.start()
        svc.manager.start.assert_awaited_once()
        assert svc._running is True

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_start_skips_non_dict_config(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        svc = ChannelService(channels_config={"not_a_dict": "string_value"})
        svc.manager = AsyncMock()
        svc._start_channel = AsyncMock()
        await svc.start()
        svc._start_channel.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_start_disabled_channel_no_creds_logs_info(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        config: dict[str, Any] = {"slack": {"enabled": False}}
        svc = ChannelService(channels_config=config)
        svc.manager = AsyncMock()
        svc._start_channel = AsyncMock()
        await svc.start()
        svc._start_channel.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_start_disabled_channel_with_creds_logs_warning(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        config: dict[str, Any] = {
            "slack": {"enabled": False, "bot_token": "xoxb-real-token", "app_token": "xapp-real"},
        }
        svc = ChannelService(channels_config=config)
        svc.manager = AsyncMock()
        svc._start_channel = AsyncMock()
        await svc.start()
        svc._start_channel.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_start_disabled_channel_bool_creds_not_counted(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """Boolean credential values should not count as configured credentials."""
        from app.channels.service import ChannelService

        config: dict[str, Any] = {
            "slack": {"enabled": False, "bot_token": True, "app_token": False},
        }
        svc = ChannelService(channels_config=config)
        svc.manager = AsyncMock()
        svc._start_channel = AsyncMock()
        await svc.start()
        svc._start_channel.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_start_disabled_channel_empty_creds_not_counted(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """Whitespace-only credential values should not count."""
        from app.channels.service import ChannelService

        config: dict[str, Any] = {
            "telegram": {"enabled": False, "bot_token": "   "},
        }
        svc = ChannelService(channels_config=config)
        svc.manager = AsyncMock()
        svc._start_channel = AsyncMock()
        await svc.start()
        svc._start_channel.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_start_enabled_channel_calls_start_channel(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        config: dict[str, Any] = {"slack": {"enabled": True, "bot_token": "tok"}}
        svc = ChannelService(channels_config=config)
        svc.manager = AsyncMock()
        svc._start_channel = AsyncMock(return_value=True)
        await svc.start()
        svc._start_channel.assert_awaited_once_with("slack", config["slack"])
        assert svc._running is True

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_start_channel_missing_cred_key_treated_as_no_creds(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """A disabled channel whose config lacks any credential key is logged as info."""
        from app.channels.service import ChannelService

        config: dict[str, Any] = {"dingtalk": {"enabled": False}}
        svc = ChannelService(channels_config=config)
        svc.manager = AsyncMock()
        svc._start_channel = AsyncMock()
        await svc.start()
        svc._start_channel.assert_not_awaited()


# ---------------------------------------------------------------------------
# ChannelService.stop
# ---------------------------------------------------------------------------


class TestChannelServiceStop:
    """Tests for ChannelService.stop."""

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_stop_clears_channels(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        svc = ChannelService()
        ch1 = _make_channel_mock("ch1")
        ch2 = _make_channel_mock("ch2")
        svc._channels = {"ch1": ch1, "ch2": ch2}
        svc.manager = AsyncMock()

        await svc.stop()
        ch1.stop.assert_awaited_once()
        ch2.stop.assert_awaited_once()
        assert svc._channels == {}
        svc.manager.stop.assert_awaited_once()
        assert svc._running is False

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_stop_channel_error_continues(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """An error stopping one channel should not prevent stopping others."""
        from app.channels.service import ChannelService

        svc = ChannelService()
        ch_err = _make_channel_mock("err")
        ch_err.stop.side_effect = RuntimeError("boom")
        ch_ok = _make_channel_mock("ok")
        svc._channels = {"err": ch_err, "ok": ch_ok}
        svc.manager = AsyncMock()

        await svc.stop()
        ch_err.stop.assert_awaited_once()
        ch_ok.stop.assert_awaited_once()
        assert svc._channels == {}

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_stop_no_channels(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        svc = ChannelService()
        svc.manager = AsyncMock()
        await svc.stop()
        svc.manager.stop.assert_awaited_once()
        assert svc._running is False


# ---------------------------------------------------------------------------
# ChannelService.restart_channel
# ---------------------------------------------------------------------------


class TestRestartChannel:
    """Tests for ChannelService.restart_channel."""

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_restart_existing_channel_success(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        svc = ChannelService(channels_config={"slack": {"enabled": True}})
        old_ch = _make_channel_mock("slack")
        svc._channels = {"slack": old_ch}
        svc._start_channel = AsyncMock(return_value=True)

        result = await svc.restart_channel("slack")
        old_ch.stop.assert_awaited_once()
        assert "slack" not in svc._channels or svc._start_channel.awaited
        svc._start_channel.assert_awaited_once_with("slack", {"enabled": True})
        assert result is True

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_restart_existing_channel_stop_error(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """Stopping the old channel can fail; restart should still proceed."""
        from app.channels.service import ChannelService

        svc = ChannelService(channels_config={"slack": {"enabled": True}})
        old_ch = _make_channel_mock("slack")
        old_ch.stop.side_effect = RuntimeError("stop fail")
        svc._channels = {"slack": old_ch}
        svc._start_channel = AsyncMock(return_value=True)

        result = await svc.restart_channel("slack")
        old_ch.stop.assert_awaited_once()
        svc._start_channel.assert_awaited_once()
        assert result is True

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_restart_channel_not_running_no_existing(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """Restarting a channel that isn't currently running."""
        from app.channels.service import ChannelService

        svc = ChannelService(channels_config={"slack": {"enabled": True}})
        svc._start_channel = AsyncMock(return_value=True)

        result = await svc.restart_channel("slack")
        svc._start_channel.assert_awaited_once_with("slack", {"enabled": True})
        assert result is True

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_restart_no_config(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        svc = ChannelService()
        result = await svc.restart_channel("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_restart_non_dict_config(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        svc = ChannelService(channels_config={"slack": "not-a-dict"})
        result = await svc.restart_channel("slack")
        assert result is False


# ---------------------------------------------------------------------------
# ChannelService._start_channel
# ---------------------------------------------------------------------------


class TestStartChannel:
    """Tests for ChannelService._start_channel (private method)."""

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_start_channel_unknown_type(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        svc = ChannelService()
        result = await svc._start_channel("unknown_channel_type", {"enabled": True})
        assert result is False

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    @patch("ideer.reflection.resolve_class")
    async def test_start_channel_import_failure(self, mock_resolve, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        mock_resolve.side_effect = ImportError("no module")
        svc = ChannelService()
        result = await svc._start_channel("slack", {"enabled": True})
        assert result is False

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    @patch("ideer.reflection.resolve_class")
    async def test_start_channel_instantiation_failure(self, mock_resolve, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        mock_cls = MagicMock(side_effect=RuntimeError("bad init"))
        mock_resolve.return_value = mock_cls
        svc = ChannelService()
        result = await svc._start_channel("slack", {"enabled": True, "bot_token": "tok"})
        assert result is False
        assert "slack" not in svc._channels

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    @patch("ideer.reflection.resolve_class")
    async def test_start_channel_not_running_after_start(self, mock_resolve, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        ch = _make_channel_mock("slack", running=False)
        mock_cls = MagicMock(return_value=ch)
        mock_resolve.return_value = mock_cls
        svc = ChannelService()

        result = await svc._start_channel("slack", {"enabled": True, "bot_token": "tok"})
        assert result is False
        ch.start.assert_awaited_once()
        assert "slack" not in svc._channels

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    @patch("ideer.reflection.resolve_class")
    async def test_start_channel_success(self, mock_resolve, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        ch = _make_channel_mock("slack", running=True)
        mock_cls = MagicMock(return_value=ch)
        mock_resolve.return_value = mock_cls
        svc = ChannelService()

        config: dict[str, Any] = {"enabled": True, "bot_token": "tok"}
        result = await svc._start_channel("slack", config)
        assert result is True
        assert svc._channels["slack"] is ch
        ch.start.assert_awaited_once()
        # config dict should have channel_store injected
        call_kwargs = mock_cls.call_args.kwargs
        assert "channel_store" in call_kwargs["config"] or "channel_store" in call_kwargs

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    @patch("ideer.reflection.resolve_class")
    async def test_start_channel_start_raises(self, mock_resolve, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """channel.start() raises an exception."""
        from app.channels.service import ChannelService

        ch = _make_channel_mock("slack")
        ch.start.side_effect = RuntimeError("start failed")
        mock_cls = MagicMock(return_value=ch)
        mock_resolve.return_value = mock_cls
        svc = ChannelService()

        result = await svc._start_channel("slack", {"enabled": True})
        assert result is False
        assert "slack" not in svc._channels


# ---------------------------------------------------------------------------
# ChannelService.get_status
# ---------------------------------------------------------------------------


class TestGetStatus:
    """Tests for ChannelService.get_status."""

    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    def test_get_status_service_not_running(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import _CHANNEL_REGISTRY, ChannelService

        svc = ChannelService()
        status = svc.get_status()
        assert status["service_running"] is False
        # All channels should be present
        for name in _CHANNEL_REGISTRY:
            assert name in status["channels"]
            assert status["channels"][name]["enabled"] is False
            assert status["channels"][name]["running"] is False

    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    def test_get_status_enabled_and_running(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        ch = _make_channel_mock("slack", running=True)
        config: dict[str, Any] = {"slack": {"enabled": True}}
        svc = ChannelService(channels_config=config)
        svc._channels = {"slack": ch}
        svc._running = True

        status = svc.get_status()
        assert status["service_running"] is True
        assert status["channels"]["slack"]["enabled"] is True
        assert status["channels"]["slack"]["running"] is True

    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    def test_get_status_enabled_but_not_running(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """Channel is enabled in config but not in _channels (failed to start)."""
        from app.channels.service import ChannelService

        config: dict[str, Any] = {"slack": {"enabled": True}}
        svc = ChannelService(channels_config=config)
        # _channels is empty — channel didn't start
        status = svc.get_status()
        assert status["channels"]["slack"]["enabled"] is True
        assert status["channels"]["slack"]["running"] is False

    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    def test_get_status_channel_running_but_config_not_dict(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """Config value is not a dict, so enabled should be False."""
        from app.channels.service import ChannelService

        config: dict[str, Any] = {"slack": "not-a-dict"}
        svc = ChannelService(channels_config=config)
        ch = _make_channel_mock("slack", running=True)
        svc._channels = {"slack": ch}
        status = svc.get_status()
        assert status["channels"]["slack"]["enabled"] is False
        assert status["channels"]["slack"]["running"] is True

    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    def test_get_status_channel_in_channels_but_not_running(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """Channel instance exists but is_running is False."""
        from app.channels.service import ChannelService

        config: dict[str, Any] = {"slack": {"enabled": True}}
        svc = ChannelService(channels_config=config)
        ch = _make_channel_mock("slack", running=False)
        svc._channels = {"slack": ch}
        status = svc.get_status()
        assert status["channels"]["slack"]["enabled"] is True
        assert status["channels"]["slack"]["running"] is False


# ---------------------------------------------------------------------------
# ChannelService.get_channel
# ---------------------------------------------------------------------------


class TestGetChannel:
    """Tests for ChannelService.get_channel."""

    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    def test_get_channel_found(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        svc = ChannelService()
        ch = _make_channel_mock("slack")
        svc._channels = {"slack": ch}
        assert svc.get_channel("slack") is ch

    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    def test_get_channel_not_found(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        from app.channels.service import ChannelService

        svc = ChannelService()
        assert svc.get_channel("nonexistent") is None


# ---------------------------------------------------------------------------
# Singleton module-level functions
# ---------------------------------------------------------------------------


class TestSingletonFunctions:
    """Tests for get_channel_service, start_channel_service, stop_channel_service."""

    def test_get_channel_service_returns_none_when_not_started(self):
        import app.channels.service as svc_mod

        # Ensure the module-level singleton is None
        original = svc_mod._channel_service
        svc_mod._channel_service = None
        try:
            assert svc_mod.get_channel_service() is None
        finally:
            svc_mod._channel_service = original

    def test_get_channel_service_returns_instance(self):
        import app.channels.service as svc_mod

        mock_svc = MagicMock()
        original = svc_mod._channel_service
        svc_mod._channel_service = mock_svc
        try:
            assert svc_mod.get_channel_service() is mock_svc
        finally:
            svc_mod._channel_service = original

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelService")
    async def test_start_channel_service_creates_and_starts(self, mock_svc_cls):
        import app.channels.service as svc_mod

        mock_instance = AsyncMock()
        mock_svc_cls.from_app_config.return_value = mock_instance
        original = svc_mod._channel_service
        svc_mod._channel_service = None
        try:
            result = await svc_mod.start_channel_service("fake_config")
            mock_svc_cls.from_app_config.assert_called_once_with("fake_config")
            mock_instance.start.assert_awaited_once()
            assert result is mock_instance
            assert svc_mod._channel_service is mock_instance
        finally:
            svc_mod._channel_service = original

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelService")
    async def test_start_channel_service_returns_existing(self, mock_svc_cls):
        import app.channels.service as svc_mod

        existing = MagicMock()
        original = svc_mod._channel_service
        svc_mod._channel_service = existing
        try:
            result = await svc_mod.start_channel_service()
            mock_svc_cls.from_app_config.assert_not_called()
            assert result is existing
        finally:
            svc_mod._channel_service = original

    @pytest.mark.asyncio
    async def test_stop_channel_service_stops_and_clears(self):
        import app.channels.service as svc_mod

        mock_svc = AsyncMock()
        original = svc_mod._channel_service
        svc_mod._channel_service = mock_svc
        try:
            await svc_mod.stop_channel_service()
            mock_svc.stop.assert_awaited_once()
            assert svc_mod._channel_service is None
        finally:
            svc_mod._channel_service = original

    @pytest.mark.asyncio
    async def test_stop_channel_service_noop_when_none(self):
        import app.channels.service as svc_mod

        original = svc_mod._channel_service
        svc_mod._channel_service = None
        try:
            await svc_mod.stop_channel_service()  # should not raise
        finally:
            svc_mod._channel_service = original


# ---------------------------------------------------------------------------
# Module-level registries
# ---------------------------------------------------------------------------


class TestRegistries:
    """Verify the module-level registries are present and complete."""

    def test_channel_registry_entries(self):
        from app.channels.service import _CHANNEL_REGISTRY

        expected = {"dingtalk", "discord", "feishu", "slack", "telegram", "wechat", "wecom"}
        assert set(_CHANNEL_REGISTRY.keys()) == expected

    def test_channel_credential_keys_entries(self):
        from app.channels.service import _CHANNEL_CREDENTIAL_KEYS

        expected = {"dingtalk", "discord", "feishu", "slack", "telegram", "wechat", "wecom"}
        assert set(_CHANNEL_CREDENTIAL_KEYS.keys()) == expected

    def test_env_var_constants(self):
        from app.channels.service import _CHANNELS_GATEWAY_URL_ENV, _CHANNELS_LANGGRAPH_URL_ENV

        assert _CHANNELS_LANGGRAPH_URL_ENV == "IDEER_CHANNELS_LANGGRAPH_URL"
        assert _CHANNELS_GATEWAY_URL_ENV == "IDEER_CHANNELS_GATEWAY_URL"


# ---------------------------------------------------------------------------
# Integration: start_channel_service full flow
# ---------------------------------------------------------------------------


class TestStartChannelServiceIntegration:
    """Integration tests for the start_channel_service full flow."""

    @pytest.mark.asyncio
    @patch("ideer.reflection.resolve_class")
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_start_with_enabled_channel(self, mock_bus_cls, mock_store_cls, mock_mgr_cls, mock_resolve):
        """Full flow: start_channel_service with an enabled channel."""
        import app.channels.service as svc_mod

        ch = _make_channel_mock("slack", running=True)
        mock_resolve.return_value = MagicMock(return_value=ch)
        mock_mgr_instance = AsyncMock()
        mock_mgr_cls.return_value = mock_mgr_instance

        original = svc_mod._channel_service
        svc_mod._channel_service = None
        try:
            app_cfg = _make_app_config(extra={"channels": {"slack": {"enabled": True, "bot_token": "tok"}}})
            result = await svc_mod.start_channel_service(app_cfg)
            assert result._running is True
            assert "slack" in result._channels
            mock_mgr_instance.start.assert_awaited_once()
        finally:
            svc_mod._channel_service = original

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelService.stop", new_callable=AsyncMock)
    async def test_stop_after_start(self, mock_stop):
        """Full flow: start then stop clears the singleton."""
        import app.channels.service as svc_mod

        mock_svc = MagicMock()
        mock_svc.stop = mock_stop
        original = svc_mod._channel_service
        svc_mod._channel_service = mock_svc
        try:
            await svc_mod.stop_channel_service()
            mock_stop.assert_awaited_once()
            assert svc_mod._channel_service is None
        finally:
            svc_mod._channel_service = original


# ---------------------------------------------------------------------------
# Edge cases for _start_channel with various registry types
# ---------------------------------------------------------------------------


class TestStartChannelEdgeCases:
    """Edge cases for _start_channel code paths."""

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    @patch("ideer.reflection.resolve_class")
    async def test_start_channel_class_not_subclass_of_channel(self, mock_resolve, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """resolve_class returns a class that can still be instantiated (no base_class check)."""
        from app.channels.service import ChannelService

        ch = _make_channel_mock("dingtalk", running=True)
        mock_cls = MagicMock(return_value=ch)
        mock_resolve.return_value = mock_cls

        svc = ChannelService()
        config: dict[str, Any] = {"enabled": True, "client_id": "cid", "client_secret": "csec"}
        result = await svc._start_channel("dingtalk", config)
        assert result is True
        mock_resolve.assert_called_once_with("app.channels.dingtalk:DingTalkChannel", base_class=None)

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    @patch("ideer.reflection.resolve_class")
    async def test_start_channel_config_gets_channel_store(self, mock_resolve, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """Verify that channel_store is injected into the config dict."""
        from app.channels.service import ChannelService

        ch = _make_channel_mock("slack", running=True)
        mock_cls = MagicMock(return_value=ch)
        mock_resolve.return_value = mock_cls

        svc = ChannelService()
        config: dict[str, Any] = {"enabled": True, "bot_token": "tok"}
        await svc._start_channel("slack", config)
        # The config dict passed to the channel class should have channel_store
        call_args = mock_cls.call_args
        passed_config = call_args.kwargs.get("config") or call_args[1].get("config")
        if passed_config is None:
            # positional args: bus=, config=
            passed_config = call_args[0][1] if len(call_args[0]) > 1 else call_args.kwargs.get("config")
        assert passed_config is not None
        assert "channel_store" in passed_config

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_start_channel_for_all_registry_types(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """Test that all registered channel types can be started (with resolve_class mocked)."""
        from app.channels.service import _CHANNEL_REGISTRY, ChannelService

        for name, import_path in _CHANNEL_REGISTRY.items():
            svc = ChannelService()
            with patch("ideer.reflection.resolve_class") as mock_resolve:
                ch = _make_channel_mock(name, running=True)
                mock_resolve.return_value = MagicMock(return_value=ch)
                config: dict[str, Any] = {"enabled": True}
                result = await svc._start_channel(name, config)
                assert result is True, f"Failed to start channel {name}"
                mock_resolve.assert_called_once_with(import_path, base_class=None)


# ---------------------------------------------------------------------------
# Additional edge cases for full coverage
# ---------------------------------------------------------------------------


class TestCoverageCompleteness:
    """Additional tests to ensure every branch is hit."""

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_start_disabled_unknown_channel_type(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """A disabled channel with an unknown type (not in credential keys) — info log path."""
        from app.channels.service import ChannelService

        config: dict[str, Any] = {"custom_thing": {"enabled": False}}
        svc = ChannelService(channels_config=config)
        svc.manager = AsyncMock()
        svc._start_channel = AsyncMock()
        await svc.start()
        # custom_thing has no cred keys defined, so has_creds is False -> info log
        svc._start_channel.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_restart_channel_no_running_instance(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """restart_channel when the channel isn't in _channels but config exists."""
        from app.channels.service import ChannelService

        config: dict[str, Any] = {"telegram": {"enabled": True, "bot_token": "tok"}}
        svc = ChannelService(channels_config=config)
        svc._start_channel = AsyncMock(return_value=True)

        result = await svc.restart_channel("telegram")
        svc._start_channel.assert_awaited_once_with("telegram", config["telegram"])
        assert result is True

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    @patch("ideer.reflection.resolve_class")
    async def test_start_channel_running_check_false_then_pop(self, mock_resolve, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """Verify the is_running=False branch pops the channel from _channels."""
        from app.channels.service import ChannelService

        ch = MagicMock()
        ch.is_running = False
        ch.start = AsyncMock()
        mock_resolve.return_value = MagicMock(return_value=ch)
        svc = ChannelService()

        result = await svc._start_channel("wechat", {"enabled": True, "bot_token": "tok"})
        assert result is False
        assert "wechat" not in svc._channels

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    async def test_stop_running_flag_set_false(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """Ensure _running is set to False after stop, even with channel errors."""
        from app.channels.service import ChannelService

        svc = ChannelService()
        ch = _make_channel_mock("test")
        ch.stop.side_effect = RuntimeError("fail")
        svc._channels = {"test": ch}
        svc.manager = AsyncMock()
        svc._running = True

        await svc.stop()
        assert svc._running is False

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelService")
    async def test_start_channel_service_with_none_config(self, mock_svc_cls):
        """start_channel_service called with no args (app_config=None)."""
        import app.channels.service as svc_mod

        mock_instance = AsyncMock()
        mock_svc_cls.from_app_config.return_value = mock_instance
        original = svc_mod._channel_service
        svc_mod._channel_service = None
        try:
            result = await svc_mod.start_channel_service()
            mock_svc_cls.from_app_config.assert_called_once_with(None)
            assert result is mock_instance
        finally:
            svc_mod._channel_service = original

    @pytest.mark.asyncio
    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    @patch("ideer.reflection.resolve_class")
    async def test_start_channel_exception_during_start_cleans_up(self, mock_resolve, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """When channel.start() raises, the channel should be removed from _channels."""
        from app.channels.service import ChannelService

        ch = MagicMock()
        ch.is_running = True
        ch.start = AsyncMock(side_effect=ConnectionError("network down"))
        mock_resolve.return_value = MagicMock(return_value=ch)
        svc = ChannelService()

        result = await svc._start_channel("feishu", {"enabled": True, "app_id": "aid", "app_secret": "asec"})
        assert result is False
        assert "feishu" not in svc._channels

    @patch("app.channels.service.ChannelManager")
    @patch("app.channels.service.ChannelStore")
    @patch("app.channels.service.MessageBus")
    def test_init_with_all_config_options(self, mock_bus_cls, mock_store_cls, mock_mgr_cls):
        """Test constructor with all possible config options at once."""
        from app.channels.service import ChannelService

        config: dict[str, Any] = {
            "langgraph_url": "http://lg",
            "gateway_url": "http://gw",
            "session": {"assistant_id": "a1", "config": {"recursion_limit": 50}},
            "slack": {
                "enabled": True,
                "bot_token": "tok",
                "session": {"assistant_id": "slack-agent"},
            },
            "feishu": {"enabled": False},
            "not_a_dict": 99,
        }
        ChannelService(channels_config=config)
        call_kwargs = mock_mgr_cls.call_args.kwargs
        assert call_kwargs["langgraph_url"] == "http://lg"
        assert call_kwargs["gateway_url"] == "http://gw"
        assert call_kwargs["default_session"]["assistant_id"] == "a1"
        assert call_kwargs["channel_sessions"]["slack"] == {"assistant_id": "slack-agent"}
        assert call_kwargs["channel_sessions"]["feishu"] is None
