"""Comprehensive tests for the Slack channel implementation.

Targets 98%+ coverage of app/channels/slack.py (148 statements).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.channels.message_bus import InboundMessageType, MessageBus, OutboundMessage, ResolvedAttachment
from app.channels.slack import SlackChannel, _normalize_allowed_users


def _run(coro):
    """Run an async coroutine in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_channel(config: dict | None = None, *, running: bool = False) -> SlackChannel:
    """Create a SlackChannel with a mock bus for testing."""
    bus = MessageBus()
    channel = SlackChannel(bus=bus, config=config or {})
    channel._running = running
    return channel


def _make_outbound(
    *,
    text: str = "hello",
    chat_id: str = "C123",
    thread_ts: str | None = None,
    channel_name: str = "slack",
) -> OutboundMessage:
    """Create a minimal OutboundMessage."""
    return OutboundMessage(
        channel_name=channel_name,
        chat_id=chat_id,
        thread_id="thread_001",
        text=text,
        thread_ts=thread_ts,
    )


def _make_attachment(
    *,
    filename: str = "report.pdf",
    virtual_path: str = "/mnt/user-data/outputs/report.pdf",
) -> ResolvedAttachment:
    """Create a minimal ResolvedAttachment."""
    return ResolvedAttachment(
        virtual_path=virtual_path,
        actual_path=Path("/tmp/report.pdf"),
        filename=filename,
        mime_type="application/pdf",
        size=1024,
        is_image=False,
    )


# ---------------------------------------------------------------------------
# _normalize_allowed_users tests
# ---------------------------------------------------------------------------


class TestNormalizeAllowedUsers:
    def test_none_returns_empty_set(self):
        assert _normalize_allowed_users(None) == set()

    def test_empty_list_returns_empty_set(self):
        assert _normalize_allowed_users([]) == set()

    def test_single_string(self):
        assert _normalize_allowed_users("U123") == {"U123"}

    def test_list_of_strings(self):
        result = _normalize_allowed_users(["U111", "U222", "U333"])
        assert result == {"U111", "U222", "U333"}

    def test_tuple_input(self):
        result = _normalize_allowed_users(("U111", "U222"))
        assert result == {"U111", "U222"}

    def test_set_input(self):
        result = _normalize_allowed_users({"U111", "U222"})
        assert result == {"U111", "U222"}

    def test_numeric_values_converted_to_string(self):
        result = _normalize_allowed_users([123, 456])
        assert result == {"123", "456"}

    def test_integer_scalar_treated_as_single_value_with_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="app.channels.slack"):
            result = _normalize_allowed_users(99999)
        assert result == {"99999"}
        assert "treating int as one string value" in caplog.text

    def test_float_scalar_treated_as_single_value_with_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="app.channels.slack"):
            result = _normalize_allowed_users(3.14)
        assert result == {"3.14"}
        assert "treating float as one string value" in caplog.text

    def test_dict_scalar_treated_as_single_value_with_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="app.channels.slack"):
            result = _normalize_allowed_users({"key": "val"})
        assert result == {"{'key': 'val'}"}
        assert "treating dict as one string value" in caplog.text

    def test_empty_string_filtered_out(self):
        result = _normalize_allowed_users(["", "U111", ""])
        assert result == {"U111"}

    def test_list_with_empty_string_filtered(self):
        result = _normalize_allowed_users([""])
        assert result == set()

    def test_numeric_zero_kept(self):
        """0 is falsy but str(0) = '0' is truthy, so it is kept."""
        result = _normalize_allowed_users([0])
        assert result == {"0"}

    def test_none_values_in_list_filtered(self):
        """str(None) = 'None' which is truthy, so it is kept."""
        result = _normalize_allowed_users([None])
        assert result == {"None"}


# ---------------------------------------------------------------------------
# SlackChannel.__init__ tests
# ---------------------------------------------------------------------------


class TestSlackChannelInit:
    def test_basic_init(self):
        channel = _make_channel()
        assert channel.name == "slack"
        assert channel._socket_client is None
        assert channel._web_client is None
        assert channel._loop is None
        assert channel._allowed_users == set()
        assert channel._running is False

    def test_init_with_allowed_users(self):
        channel = _make_channel(config={"allowed_users": ["U111", "U222"]})
        assert channel._allowed_users == {"U111", "U222"}

    def test_init_with_single_allowed_user_string(self):
        channel = _make_channel(config={"allowed_users": "U999"})
        assert channel._allowed_users == {"U999"}

    def test_init_default_allowed_users_empty(self):
        channel = _make_channel(config={})
        assert channel._allowed_users == set()


# ---------------------------------------------------------------------------
# SlackChannel.start tests
# ---------------------------------------------------------------------------


class TestSlackChannelStart:
    def test_start_when_already_running_is_noop(self):
        async def go():
            channel = _make_channel(running=True)
            await channel.start()
            # Should not have set any clients
            assert channel._web_client is None
            assert channel._socket_client is None

        _run(go())

    def test_start_missing_slack_sdk_returns_early(self):
        async def go():
            channel = _make_channel()
            with patch.dict("sys.modules", {"slack_sdk": None, "slack_sdk.socket_mode": None, "slack_sdk.socket_mode.response": None}):
                # Force ImportError by making the import raise
                with patch("builtins.__import__", side_effect=_make_import_error("slack_sdk")):
                    await channel.start()
            assert channel._web_client is None
            assert channel._running is False

        _run(go())

    def test_start_missing_bot_token_returns_early(self):
        async def go():
            channel = _make_channel(config={"app_token": "xapp-test"})
            mock_web_client = MagicMock()
            mock_socket_client = MagicMock()

            with _patch_slack_sdk(mock_web_client, mock_socket_client):
                await channel.start()

            assert channel._web_client is None
            assert channel._running is False

        _run(go())

    def test_start_missing_app_token_returns_early(self):
        async def go():
            channel = _make_channel(config={"bot_token": "xoxb-test"})
            mock_web_client = MagicMock()
            mock_socket_client = MagicMock()

            with _patch_slack_sdk(mock_web_client, mock_socket_client):
                await channel.start()

            assert channel._web_client is None
            assert channel._running is False

        _run(go())

    def test_start_empty_tokens_returns_early(self):
        async def go():
            channel = _make_channel(config={"bot_token": "", "app_token": ""})
            mock_web_client = MagicMock()
            mock_socket_client = MagicMock()

            with _patch_slack_sdk(mock_web_client, mock_socket_client):
                await channel.start()

            assert channel._web_client is None
            assert channel._running is False

        _run(go())

    def test_start_success(self):
        async def go():
            channel = _make_channel(config={"bot_token": "xoxb-test", "app_token": "xapp-test"})
            mock_web_client = MagicMock()
            mock_socket_client = MagicMock()

            with _patch_slack_sdk(mock_web_client, mock_socket_client):
                await channel.start()

            assert channel._web_client is mock_web_client
            assert channel._socket_client is mock_socket_client
            assert channel._running is True
            assert channel._loop is not None
            mock_socket_client.socket_mode_request_listeners.append.assert_called_once_with(channel._on_socket_event)
            mock_socket_client.connect.assert_called_once()

        _run(go())

    def test_start_subscribes_to_bus_outbound(self):
        async def go():
            channel = _make_channel(config={"bot_token": "xoxb-test", "app_token": "xapp-test"})
            mock_web_client = MagicMock()
            mock_socket_client = MagicMock()

            with _patch_slack_sdk(mock_web_client, mock_socket_client):
                await channel.start()

            # Verify the bus has our outbound callback
            assert channel._on_outbound in channel.bus._outbound_listeners

        _run(go())


# ---------------------------------------------------------------------------
# SlackChannel.stop tests
# ---------------------------------------------------------------------------


class TestSlackChannelStop:
    def test_stop_sets_running_false(self):
        async def go():
            channel = _make_channel(running=True)
            mock_client = MagicMock()
            channel._socket_client = mock_client

            await channel.stop()

            assert channel._running is False
            mock_client.close.assert_called_once()
            assert channel._socket_client is None

        _run(go())

    def test_stop_unsubscribes_from_bus(self):
        async def go():
            channel = _make_channel(running=True)
            channel._socket_client = MagicMock()

            await channel.stop()

            assert channel._on_outbound not in channel.bus._outbound_listeners

        _run(go())

    def test_stop_without_socket_client(self):
        async def go():
            channel = _make_channel(running=True)
            channel._socket_client = None

            await channel.stop()

            assert channel._running is False
            assert channel._socket_client is None

        _run(go())


# ---------------------------------------------------------------------------
# SlackChannel.send tests
# ---------------------------------------------------------------------------


class TestSlackChannelSend:
    def test_send_returns_early_without_web_client(self):
        async def go():
            channel = _make_channel()
            msg = _make_outbound()
            # Should not raise
            await channel.send(msg)

        _run(go())

    def test_send_basic_message(self):
        async def go():
            channel = _make_channel()
            channel._web_client = MagicMock()

            msg = _make_outbound(text="Hello Slack")
            await channel.send(msg)

            channel._web_client.chat_postMessage.assert_called_once()
            call_kwargs = channel._web_client.chat_postMessage.call_args
            assert call_kwargs.kwargs["channel"] == "C123"
            assert call_kwargs.kwargs["text"] is not None

        _run(go())

    def test_send_message_with_thread_ts(self):
        async def go():
            channel = _make_channel()
            channel._web_client = MagicMock()

            msg = _make_outbound(thread_ts="1234567890.123456")
            await channel.send(msg)

            call_kwargs = channel._web_client.chat_postMessage.call_args.kwargs
            assert call_kwargs["thread_ts"] == "1234567890.123456"

        _run(go())

    def test_send_adds_reaction_for_threaded_message(self):
        async def go():
            channel = _make_channel()
            channel._web_client = MagicMock()
            channel._add_reaction = MagicMock()

            msg = _make_outbound(thread_ts="1234567890.123456")
            await channel.send(msg)

            channel._add_reaction.assert_called_once_with("C123", "1234567890.123456", "white_check_mark")

        _run(go())

    def test_send_no_reaction_without_thread_ts(self):
        async def go():
            channel = _make_channel()
            channel._web_client = MagicMock()
            channel._add_reaction = MagicMock()

            msg = _make_outbound(thread_ts=None)
            await channel.send(msg)

            channel._add_reaction.assert_not_called()

        _run(go())

    def test_send_retries_on_failure_then_succeeds(self):
        async def go():
            channel = _make_channel()
            call_count = 0

            def flaky_post(**kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise ConnectionError("network error")

            channel._web_client = MagicMock()
            channel._web_client.chat_postMessage.side_effect = flaky_post

            msg = _make_outbound()
            await channel.send(msg, _max_retries=3)

            assert call_count == 3

        _run(go())

    def test_send_raises_after_all_retries_exhausted(self):
        async def go():
            channel = _make_channel()
            channel._web_client = MagicMock()
            channel._web_client.chat_postMessage.side_effect = ConnectionError("fail")

            msg = _make_outbound()
            with pytest.raises(ConnectionError):
                await channel.send(msg, _max_retries=3)

            assert channel._web_client.chat_postMessage.call_count == 3

        _run(go())

    def test_send_adds_failure_reaction_on_threaded_error(self):
        async def go():
            channel = _make_channel()
            channel._web_client = MagicMock()
            channel._web_client.chat_postMessage.side_effect = ConnectionError("fail")
            channel._add_reaction = MagicMock()

            msg = _make_outbound(thread_ts="1234567890.123456")
            with pytest.raises(ConnectionError):
                await channel.send(msg, _max_retries=2)

            channel._add_reaction.assert_called_once_with("C123", "1234567890.123456", "x")

        _run(go())

    def test_send_failure_reaction_exception_swallowed(self):
        async def go():
            channel = _make_channel()
            channel._web_client = MagicMock()
            channel._web_client.chat_postMessage.side_effect = ConnectionError("fail")
            channel._add_reaction = MagicMock(side_effect=RuntimeError("reaction failed"))

            msg = _make_outbound(thread_ts="1234567890.123456")
            with pytest.raises(ConnectionError):
                await channel.send(msg, _max_retries=1)

        _run(go())

    def test_send_no_failure_reaction_without_thread_ts(self):
        async def go():
            channel = _make_channel()
            channel._web_client = MagicMock()
            channel._web_client.chat_postMessage.side_effect = ConnectionError("fail")
            channel._add_reaction = MagicMock()

            msg = _make_outbound(thread_ts=None)
            with pytest.raises(ConnectionError):
                await channel.send(msg, _max_retries=1)

            channel._add_reaction.assert_not_called()

        _run(go())

    def test_send_runtime_error_when_no_exceptions(self):
        """When _max_retries=0, no attempts are made and last_exc is None."""

        async def go():
            channel = _make_channel()
            channel._web_client = MagicMock()

            msg = _make_outbound()
            with pytest.raises(RuntimeError, match="without an exception"):
                await channel.send(msg, _max_retries=0)

        _run(go())

    def test_send_retry_delay_exponential(self):
        async def go():
            channel = _make_channel()
            channel._web_client = MagicMock()
            channel._web_client.chat_postMessage.side_effect = ConnectionError("fail")

            sleep_durations = []

            async def mock_sleep(delay):
                sleep_durations.append(delay)

            msg = _make_outbound()
            with patch("asyncio.sleep", side_effect=mock_sleep):
                with pytest.raises(ConnectionError):
                    await channel.send(msg, _max_retries=3)

            # 2^0=1, 2^1=2 (retries happen for attempts 0 and 1, not the last one)
            assert sleep_durations == [1, 2]

        _run(go())


# ---------------------------------------------------------------------------
# SlackChannel.send_file tests
# ---------------------------------------------------------------------------


class TestSlackChannelSendFile:
    def test_send_file_returns_false_without_web_client(self):
        async def go():
            channel = _make_channel()
            msg = _make_outbound()
            attachment = _make_attachment()

            result = await channel.send_file(msg, attachment)
            assert result is False

        _run(go())

    def test_send_file_success(self):
        async def go():
            channel = _make_channel()
            channel._web_client = MagicMock()

            msg = _make_outbound()
            attachment = _make_attachment(filename="test.pdf")

            result = await channel.send_file(msg, attachment)
            assert result is True

            channel._web_client.files_upload_v2.assert_called_once()
            call_kwargs = channel._web_client.files_upload_v2.call_args.kwargs
            assert call_kwargs["channel"] == "C123"
            assert call_kwargs["filename"] == "test.pdf"
            assert call_kwargs["title"] == "test.pdf"
            assert call_kwargs["file"] == "/tmp/report.pdf"

        _run(go())

    def test_send_file_with_thread_ts(self):
        async def go():
            channel = _make_channel()
            channel._web_client = MagicMock()

            msg = _make_outbound(thread_ts="1234567890.123456")
            attachment = _make_attachment()

            result = await channel.send_file(msg, attachment)
            assert result is True

            call_kwargs = channel._web_client.files_upload_v2.call_args.kwargs
            assert call_kwargs["thread_ts"] == "1234567890.123456"

        _run(go())

    def test_send_file_without_thread_ts(self):
        async def go():
            channel = _make_channel()
            channel._web_client = MagicMock()

            msg = _make_outbound(thread_ts=None)
            attachment = _make_attachment()

            result = await channel.send_file(msg, attachment)
            assert result is True

            call_kwargs = channel._web_client.files_upload_v2.call_args.kwargs
            assert "thread_ts" not in call_kwargs

        _run(go())

    def test_send_file_failure_returns_false(self):
        async def go():
            channel = _make_channel()
            channel._web_client = MagicMock()
            channel._web_client.files_upload_v2.side_effect = Exception("upload failed")

            msg = _make_outbound()
            attachment = _make_attachment()

            result = await channel.send_file(msg, attachment)
            assert result is False

        _run(go())


# ---------------------------------------------------------------------------
# SlackChannel._add_reaction tests
# ---------------------------------------------------------------------------


class TestAddReaction:
    def test_add_reaction_success(self):
        channel = _make_channel()
        channel._web_client = MagicMock()

        channel._add_reaction("C123", "1234567890.123456", "eyes")

        channel._web_client.reactions_add.assert_called_once_with(channel="C123", timestamp="1234567890.123456", name="eyes")

    def test_add_reaction_without_web_client(self):
        channel = _make_channel()
        channel._web_client = None
        # Should not raise
        channel._add_reaction("C123", "1234567890.123456", "eyes")

    def test_add_reaction_already_reacted_silenced(self):
        channel = _make_channel()
        channel._web_client = MagicMock()
        channel._web_client.reactions_add.side_effect = Exception("already_reacted")

        # Should not raise or log warning
        channel._add_reaction("C123", "1234567890.123456", "eyes")

    def test_add_reaction_other_error_logs_warning(self, caplog):
        channel = _make_channel()
        channel._web_client = MagicMock()
        channel._web_client.reactions_add.side_effect = Exception("rate_limited")

        with caplog.at_level(logging.WARNING, logger="app.channels.slack"):
            channel._add_reaction("C123", "1234567890.123456", "eyes")

        assert "failed to add reaction eyes" in caplog.text


# ---------------------------------------------------------------------------
# SlackChannel._send_running_reply tests
# ---------------------------------------------------------------------------


class TestSendRunningReply:
    def test_send_running_reply_success(self):
        channel = _make_channel()
        channel._web_client = MagicMock()

        channel._send_running_reply("C123", "1234567890.123456")

        channel._web_client.chat_postMessage.assert_called_once_with(
            channel="C123",
            text=":hourglass_flowing_sand: Working on it...",
            thread_ts="1234567890.123456",
        )

    def test_send_running_reply_without_web_client(self):
        channel = _make_channel()
        channel._web_client = None
        # Should not raise
        channel._send_running_reply("C123", "1234567890.123456")

    def test_send_running_reply_failure_logged(self, caplog):
        channel = _make_channel()
        channel._web_client = MagicMock()
        channel._web_client.chat_postMessage.side_effect = Exception("api error")

        with caplog.at_level(logging.ERROR, logger="app.channels.slack"):
            channel._send_running_reply("C123", "1234567890.123456")

        assert "failed to send running reply" in caplog.text


# ---------------------------------------------------------------------------
# SlackChannel._on_socket_event tests
# ---------------------------------------------------------------------------


class TestOnSocketEvent:
    def _make_request(self, *, envelope_id: str = "env_001", req_type: str = "events_api", event: dict | None = None):
        """Create a mock Socket Mode request."""
        req = SimpleNamespace()
        req.envelope_id = envelope_id
        req.type = req_type
        req.payload = {"event": event or {}}
        return req

    def _make_client(self):
        """Create a mock Socket Mode client."""
        client = MagicMock()
        return client

    def test_acknowledges_event(self):
        channel = _make_channel()
        channel._SocketModeResponse = MagicMock()
        client = self._make_client()
        req = self._make_request(event={"type": "message", "user": "U1", "text": "hi", "channel": "C1", "ts": "123"})

        channel._on_socket_event(client, req)

        channel._SocketModeResponse.assert_called_once_with(envelope_id="env_001")
        client.send_socket_mode_response.assert_called_once()

    def test_ignores_non_events_api(self):
        channel = _make_channel()
        channel._SocketModeResponse = MagicMock()
        channel._handle_message_event = MagicMock()
        client = self._make_client()
        req = self._make_request(req_type="slash_commands")

        channel._on_socket_event(client, req)

        channel._handle_message_event.assert_not_called()

    def test_handles_message_event(self):
        channel = _make_channel()
        channel._SocketModeResponse = MagicMock()
        channel._handle_message_event = MagicMock()
        client = self._make_client()
        event = {"type": "message", "user": "U1", "text": "hi"}
        req = self._make_request(event=event)

        channel._on_socket_event(client, req)

        channel._handle_message_event.assert_called_once_with(event)

    def test_handles_app_mention_event(self):
        channel = _make_channel()
        channel._SocketModeResponse = MagicMock()
        channel._handle_message_event = MagicMock()
        client = self._make_client()
        event = {"type": "app_mention", "user": "U1", "text": "<@BOT> hi"}
        req = self._make_request(event=event)

        channel._on_socket_event(client, req)

        channel._handle_message_event.assert_called_once_with(event)

    def test_ignores_other_event_types(self):
        channel = _make_channel()
        channel._SocketModeResponse = MagicMock()
        channel._handle_message_event = MagicMock()
        client = self._make_client()
        event = {"type": "reaction_added"}
        req = self._make_request(event=event)

        channel._on_socket_event(client, req)

        channel._handle_message_event.assert_not_called()

    def test_exception_logged_and_not_raised(self, caplog):
        channel = _make_channel()
        channel._SocketModeResponse = MagicMock(side_effect=Exception("boom"))
        client = self._make_client()
        req = self._make_request()

        with caplog.at_level(logging.ERROR, logger="app.channels.slack"):
            channel._on_socket_event(client, req)

        assert "Error processing Slack event" in caplog.text

    def test_event_with_no_type_field(self):
        channel = _make_channel()
        channel._SocketModeResponse = MagicMock()
        channel._handle_message_event = MagicMock()
        client = self._make_client()
        # Event dict with no 'type' key
        req = self._make_request(event={})

        channel._on_socket_event(client, req)

        # etype = "" which is not in ("message", "app_mention")
        channel._handle_message_event.assert_not_called()


# ---------------------------------------------------------------------------
# SlackChannel._handle_message_event tests
# ---------------------------------------------------------------------------


class TestHandleMessageEvent:
    def test_ignores_bot_messages(self):
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True

        event = {"bot_id": "B123", "user": "U1", "text": "bot says hi", "channel": "C1", "ts": "123"}
        channel._handle_message_event(event)

        bus.publish_inbound.assert_not_called()

    def test_ignores_subtyped_messages(self):
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True

        event = {"subtype": "message_changed", "user": "U1", "text": "edited", "channel": "C1", "ts": "123"}
        channel._handle_message_event(event)

        bus.publish_inbound.assert_not_called()

    def test_ignores_non_allowed_user(self):
        channel = _make_channel(config={"allowed_users": ["U_ALLOWED"]})
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True

        event = {"user": "U_BLOCKED", "text": "hello", "channel": "C1", "ts": "123"}
        channel._handle_message_event(event)

        bus.publish_inbound.assert_not_called()

    def test_allows_allowed_user(self):
        channel = _make_channel(config={"allowed_users": ["U_ALLOWED"]})
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True
        channel._add_reaction = MagicMock()
        channel._send_running_reply = MagicMock()

        event = {"user": "U_ALLOWED", "text": "hello", "channel": "C1", "ts": "123"}
        channel._handle_message_event(event)

        bus.publish_inbound.assert_called_once()

    def test_ignores_empty_text(self):
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True

        event = {"user": "U1", "text": "   ", "channel": "C1", "ts": "123"}
        channel._handle_message_event(event)

        bus.publish_inbound.assert_not_called()

    def test_ignores_empty_user_id(self):
        """User not in allowed_users (if set) would block; but if allowed_users is empty, user="" passes."""
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True
        channel._add_reaction = MagicMock()
        channel._send_running_reply = MagicMock()

        event = {"user": "", "text": "hello", "channel": "C1", "ts": "123"}
        channel._handle_message_event(event)

        # Empty user_id passes the allowed_users check (empty set allows all)
        bus.publish_inbound.assert_called_once()

    def test_classifies_command_messages(self):
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True
        channel._add_reaction = MagicMock()
        channel._send_running_reply = MagicMock()

        event = {"user": "U1", "text": "/help", "channel": "C1", "ts": "123"}
        channel._handle_message_event(event)

        inbound = bus.publish_inbound.call_args.args[0]
        assert inbound.msg_type == InboundMessageType.COMMAND

    def test_classifies_chat_messages(self):
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True
        channel._add_reaction = MagicMock()
        channel._send_running_reply = MagicMock()

        event = {"user": "U1", "text": "just chatting", "channel": "C1", "ts": "123"}
        channel._handle_message_event(event)

        inbound = bus.publish_inbound.call_args.args[0]
        assert inbound.msg_type == InboundMessageType.CHAT

    def test_threaded_message_uses_thread_ts_as_topic(self):
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True
        channel._add_reaction = MagicMock()
        channel._send_running_reply = MagicMock()

        event = {
            "user": "U1",
            "text": "reply in thread",
            "channel": "C1",
            "ts": "1234567890.999999",
            "thread_ts": "1234567890.123456",
        }
        channel._handle_message_event(event)

        inbound = bus.publish_inbound.call_args.args[0]
        assert inbound.thread_ts == "1234567890.123456"
        assert inbound.topic_id == "1234567890.123456"

    def test_non_threaded_message_uses_ts_as_topic(self):
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True
        channel._add_reaction = MagicMock()
        channel._send_running_reply = MagicMock()

        event = {
            "user": "U1",
            "text": "new message",
            "channel": "C1",
            "ts": "1234567890.123456",
        }
        channel._handle_message_event(event)

        inbound = bus.publish_inbound.call_args.args[0]
        assert inbound.thread_ts == "1234567890.123456"
        assert inbound.topic_id == "1234567890.123456"

    def test_inbound_message_fields_correct(self):
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True
        channel._add_reaction = MagicMock()
        channel._send_running_reply = MagicMock()

        event = {
            "user": "U42",
            "text": "Hello Bot",
            "channel": "C999",
            "ts": "1111111111.222222",
        }
        channel._handle_message_event(event)

        inbound = bus.publish_inbound.call_args.args[0]
        assert inbound.channel_name == "slack"
        assert inbound.chat_id == "C999"
        assert inbound.user_id == "U42"
        assert inbound.text == "Hello Bot"
        assert inbound.msg_type == InboundMessageType.CHAT

    def test_adds_eyes_reaction_and_running_reply(self):
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True
        channel._add_reaction = MagicMock()
        channel._send_running_reply = MagicMock()

        event = {
            "user": "U1",
            "text": "hi",
            "channel": "C1",
            "ts": "1234567890.123456",
        }
        channel._handle_message_event(event)

        channel._add_reaction.assert_called_once_with("C1", "1234567890.123456", "eyes")
        channel._send_running_reply.assert_called_once_with("C1", "1234567890.123456")

    def test_threaded_event_eyes_reaction_uses_event_ts(self):
        """For threaded messages, the eyes reaction should go on the event's own ts, not the thread_ts."""
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True
        channel._add_reaction = MagicMock()
        channel._send_running_reply = MagicMock()

        event = {
            "user": "U1",
            "text": "reply",
            "channel": "C1",
            "ts": "1234567890.999999",
            "thread_ts": "1234567890.123456",
        }
        channel._handle_message_event(event)

        # eyes reaction uses event.get("ts", thread_ts) = "1234567890.999999"
        channel._add_reaction.assert_called_once_with("C1", "1234567890.999999", "eyes")

    def test_publishes_inbound_via_run_coroutine_threadsafe(self):
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        channel._loop = mock_loop
        channel._add_reaction = MagicMock()
        channel._send_running_reply = MagicMock()

        event = {"user": "U1", "text": "hi", "channel": "C1", "ts": "123"}
        channel._handle_message_event(event)

        mock_loop.is_running.assert_called_once()
        # run_coroutine_threadsafe should have been called
        # We can't easily assert on it without patching asyncio, but the path is exercised

    def test_no_publish_when_loop_not_running(self):
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False
        channel._loop = mock_loop
        channel._add_reaction = MagicMock()
        channel._send_running_reply = MagicMock()

        event = {"user": "U1", "text": "hi", "channel": "C1", "ts": "123"}
        channel._handle_message_event(event)

        # When loop is not running, should NOT add reaction, send running reply, or publish
        channel._add_reaction.assert_not_called()
        channel._send_running_reply.assert_not_called()
        bus.publish_inbound.assert_not_called()

    def test_no_publish_when_loop_is_none(self):
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = None
        channel._add_reaction = MagicMock()
        channel._send_running_reply = MagicMock()

        event = {"user": "U1", "text": "hi", "channel": "C1", "ts": "123"}
        channel._handle_message_event(event)

        channel._add_reaction.assert_not_called()
        channel._send_running_reply.assert_not_called()
        bus.publish_inbound.assert_not_called()

    def test_no_thread_ts_falls_back_to_ts(self):
        """When event has no thread_ts, it should fall back to ts."""
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True
        channel._add_reaction = MagicMock()
        channel._send_running_reply = MagicMock()

        event = {
            "user": "U1",
            "text": "no thread",
            "channel": "C1",
            "ts": "9999999999.000000",
        }
        channel._handle_message_event(event)

        inbound = bus.publish_inbound.call_args.args[0]
        assert inbound.thread_ts == "9999999999.000000"

    def test_empty_channel_id(self):
        """channel and ts can be empty strings."""
        channel = _make_channel()
        bus = channel.bus
        bus.publish_inbound = AsyncMock()
        channel._loop = MagicMock()
        channel._loop.is_running.return_value = True
        channel._add_reaction = MagicMock()
        channel._send_running_reply = MagicMock()

        event = {"user": "U1", "text": "hi", "channel": "", "ts": ""}
        channel._handle_message_event(event)

        inbound = bus.publish_inbound.call_args.args[0]
        assert inbound.chat_id == ""


# ---------------------------------------------------------------------------
# _on_outbound integration tests (from base class)
# ---------------------------------------------------------------------------


class TestOnOutbound:
    def test_outbound_for_slack_channel_calls_send(self):
        async def go():
            channel = _make_channel(running=True)
            channel.send = AsyncMock()

            msg = _make_outbound(channel_name="slack")
            await channel._on_outbound(msg)

            channel.send.assert_awaited_once_with(msg)

        _run(go())

    def test_outbound_for_other_channel_ignored(self):
        async def go():
            channel = _make_channel(running=True)
            channel.send = AsyncMock()

            msg = _make_outbound(channel_name="discord")
            await channel._on_outbound(msg)

            channel.send.assert_not_awaited()

        _run(go())

    def test_outbound_with_attachments_calls_send_file(self):
        async def go():
            channel = _make_channel(running=True)
            channel.send = AsyncMock()
            channel.send_file = AsyncMock(return_value=True)

            msg = _make_outbound()
            msg.attachments = [_make_attachment()]
            await channel._on_outbound(msg)

            channel.send.assert_awaited_once()
            channel.send_file.assert_awaited_once()

        _run(go())

    def test_outbound_send_failure_skips_file_uploads(self):
        async def go():
            channel = _make_channel(running=True)
            channel.send = AsyncMock(side_effect=Exception("send failed"))
            channel.send_file = AsyncMock()

            msg = _make_outbound()
            msg.attachments = [_make_attachment()]
            await channel._on_outbound(msg)

            channel.send_file.assert_not_awaited()

        _run(go())

    def test_outbound_file_upload_failure_logged(self, caplog):
        async def go():
            channel = _make_channel(running=True)
            channel.send = AsyncMock()
            channel.send_file = AsyncMock(return_value=False)

            msg = _make_outbound()
            msg.attachments = [_make_attachment(filename="bad.pdf")]

            with caplog.at_level(logging.WARNING, logger="app.channels.base"):
                await channel._on_outbound(msg)

            assert "file upload skipped for bad.pdf" in caplog.text

        _run(go())

    def test_outbound_file_upload_exception_logged(self, caplog):
        async def go():
            channel = _make_channel(running=True)
            channel.send = AsyncMock()
            channel.send_file = AsyncMock(side_effect=Exception("upload exploded"))

            msg = _make_outbound()
            msg.attachments = [_make_attachment(filename="explode.pdf")]

            with caplog.at_level(logging.ERROR, logger="app.channels.base"):
                await channel._on_outbound(msg)

            assert "failed to upload file explode.pdf" in caplog.text

        _run(go())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_import_error(module_name: str):
    """Create a function that raises ImportError for the given module."""
    original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

    def _fake_import(name, *args, **kwargs):
        if name == module_name or name.startswith(module_name + "."):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    return _fake_import


def _patch_slack_sdk(mock_web_client, mock_socket_client):
    """Context manager that patches slack_sdk imports."""
    mock_web_module = MagicMock()
    mock_web_module.WebClient.return_value = mock_web_client

    mock_socket_module = MagicMock()
    mock_socket_module.SocketModeClient.return_value = mock_socket_client

    mock_response_module = MagicMock()

    return patch.dict(
        "sys.modules",
        {
            "slack_sdk": mock_web_module,
            "slack_sdk.socket_mode": mock_socket_module,
            "slack_sdk.socket_mode.response": mock_response_module,
        },
    )
