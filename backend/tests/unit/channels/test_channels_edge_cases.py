"""Coverage tests for WeCom and Discord channel uncovered lines.

Targets specific uncovered code paths identified by the coverage report:

wecom.py: lines 67-68, 128, 171-173, 291-292, 301-302, 311, 331-336, 356-357, 383
discord.py: lines 102, 165-166, 279-281, 495-505, 516-521
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.channels.message_bus import (
    MessageBus,
    OutboundMessage,
    ResolvedAttachment,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_bus() -> MessageBus:
    return MessageBus()


def _make_outbound(**overrides) -> OutboundMessage:
    defaults = {
        "channel_name": "wecom",
        "chat_id": "user_1",
        "thread_id": "thread_1",
        "text": "Hello",
        "thread_ts": "msg_1",
        "is_final": True,
    }
    defaults.update(overrides)
    return OutboundMessage(**defaults)


def _make_attachment(**overrides) -> ResolvedAttachment:
    defaults = {
        "virtual_path": "/mnt/user-data/outputs/test.txt",
        "actual_path": Path("/tmp/test.txt"),
        "filename": "test.txt",
        "mime_type": "text/plain",
        "size": 1024,
        "is_image": False,
    }
    defaults.update(overrides)
    return ResolvedAttachment(**defaults)


def _make_frame(body: dict | None = None, msg_id: str = "msg_1", userid: str = "user_1") -> dict:
    return {
        "body": {
            "msgid": msg_id,
            "from": {"userid": userid},
            "aibotid": "bot_1",
            "chattype": "single",
            **(body or {}),
        }
    }


def _run(coro):
    """Run an async coroutine in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ===================================================================
# WeCom Coverage Tests
# ===================================================================


class TestWeComStartMissingCredentials:
    """Cover lines 67-68: early return when bot_id or bot_secret is missing."""

    @pytest.mark.anyio
    async def test_start_missing_bot_id(self, caplog):
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_secret": "secret_only"})
        with caplog.at_level(logging.ERROR):
            await ch.start()
        assert ch._running is False
        assert "requires bot_id and bot_secret" in caplog.text

    @pytest.mark.anyio
    async def test_start_missing_bot_secret(self, caplog):
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_id": "id_only"})
        with caplog.at_level(logging.ERROR):
            await ch.start()
        assert ch._running is False
        assert "requires bot_id and bot_secret" in caplog.text

    @pytest.mark.anyio
    async def test_start_empty_string_credentials(self, caplog):
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_id": "", "bot_secret": ""})
        with caplog.at_level(logging.ERROR):
            await ch.start()
        assert ch._running is False
        assert "requires bot_id and bot_secret" in caplog.text

    @pytest.mark.anyio
    async def test_start_non_string_credentials(self, caplog):
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_id": 123, "bot_secret": True})
        with caplog.at_level(logging.ERROR):
            await ch.start()
        assert ch._running is False
        assert "requires bot_id and bot_secret" in caplog.text


class TestWeComOnOutboundFileUploadSkipped:
    """Cover line 128: warning when send_file returns False."""

    @pytest.mark.anyio
    async def test_on_outbound_file_upload_skipped(self, caplog):
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_id": "b", "bot_secret": "s"})
        msg = _make_outbound(attachments=[_make_attachment()])
        with patch.object(ch, "send", new_callable=AsyncMock):
            with patch.object(ch, "send_file", new_callable=AsyncMock, return_value=False):
                with caplog.at_level(logging.WARNING):
                    await ch._on_outbound(msg)
        assert "file upload skipped" in caplog.text


class TestWeComSendFileException:
    """Cover lines 171-173: exception during upload/send file via ws."""

    @pytest.mark.anyio
    async def test_send_file_upload_exception(self, caplog):
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_id": "b", "bot_secret": "s"})
        ch._ws_client = MagicMock()
        ch._ws_frames = {"msg_1": {"body": {}}}

        with patch.object(ch, "_upload_media_ws", new_callable=AsyncMock, side_effect=RuntimeError("upload boom")):
            with caplog.at_level(logging.ERROR):
                result = await ch.send_file(_make_outbound(), _make_attachment())
        assert result is False
        assert "failed to upload/send file via ws" in caplog.text

    @pytest.mark.anyio
    async def test_send_file_reply_exception(self, caplog):
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_id": "b", "bot_secret": "s"})
        mock_ws = MagicMock()
        mock_ws.reply = AsyncMock(side_effect=RuntimeError("reply boom"))
        ch._ws_client = mock_ws
        ch._ws_frames = {"msg_1": {"body": {}}}

        with patch.object(ch, "_upload_media_ws", new_callable=AsyncMock, return_value="media_1"):
            with caplog.at_level(logging.ERROR):
                result = await ch.send_file(_make_outbound(), _make_attachment())
        assert result is False
        assert "failed to upload/send file via ws" in caplog.text


class TestWeComPublishWsInboundReplyStreamError:
    """Cover lines 291-292: exception during reply_stream for working message."""

    @pytest.mark.anyio
    async def test_publish_ws_inbound_reply_stream_error(self):
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_id": "b", "bot_secret": "s"})
        mock_ws = MagicMock()
        mock_ws.reply_stream = AsyncMock(side_effect=RuntimeError("stream error"))
        ch._ws_client = mock_ws

        frame = _make_frame()
        mock_aibot = MagicMock()
        mock_aibot.generate_req_id.return_value = "stream_123"

        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            with patch.object(ch.bus, "publish_inbound", new_callable=AsyncMock) as mock_pub:
                # Should not raise -- exception is caught and swallowed (lines 291-292)
                await ch._publish_ws_inbound(frame, "hello")
                mock_pub.assert_called_once()


class TestWeComSendWsImportFailure:
    """Cover lines 301-302: import of generate_req_id fails in _send_ws."""

    @pytest.mark.anyio
    async def test_send_ws_import_failure_falls_through(self):
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_id": "b", "bot_secret": "s"})
        mock_ws = MagicMock()
        mock_ws.send_message = AsyncMock()
        ch._ws_client = mock_ws
        ch._ws_frames = {}
        ch._ws_stream_ids = {}

        with patch("builtins.__import__", side_effect=ImportError("no aibot")):
            await ch._send_ws(_make_outbound(thread_ts="nonexistent_msg"))
        # Should fall through to send_message fallback (generate_req_id is None)
        mock_ws.send_message.assert_called_once()


class TestWeComSendWsNoStreamId:
    """Cover line 311: return when stream_id is None after failed generation."""

    @pytest.mark.anyio
    async def test_send_ws_no_stream_id_returns(self):
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_id": "b", "bot_secret": "s"})
        mock_ws = MagicMock()
        mock_ws.reply_stream = AsyncMock()
        ch._ws_client = mock_ws
        ch._ws_frames = {"msg_1": {"body": {}}}
        ch._ws_stream_ids = {}  # No stream ID for msg_1

        # Mock aibot but make generate_req_id return None
        mock_aibot = MagicMock()
        mock_aibot.generate_req_id.return_value = None

        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            await ch._send_ws(_make_outbound())
        # Should have returned at line 311 without calling reply_stream
        mock_ws.reply_stream.assert_not_called()


class TestWeComSendWsFallbackSendMessage:
    """Cover lines 331-336: fallback send_message retry loop with exception and final raise."""

    @pytest.mark.anyio
    async def test_send_ws_fallback_retries_and_raises(self):
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_id": "b", "bot_secret": "s"})
        mock_ws = MagicMock()
        mock_ws.send_message = AsyncMock(side_effect=RuntimeError("send_message fail"))
        ch._ws_client = mock_ws
        ch._ws_frames = {}  # No frame -> fallback path

        with pytest.raises(RuntimeError, match="send_message fail"):
            await ch._send_ws(_make_outbound(thread_ts="no_such_frame"), _max_retries=2)
        assert mock_ws.send_message.call_count == 2

    @pytest.mark.anyio
    async def test_send_ws_fallback_retries_then_succeeds(self):
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_id": "b", "bot_secret": "s"})
        mock_ws = MagicMock()
        mock_ws.send_message = AsyncMock(side_effect=[RuntimeError("fail once"), None])
        ch._ws_client = mock_ws
        ch._ws_frames = {}

        await ch._send_ws(_make_outbound(thread_ts="no_such_frame"), _max_retries=2)
        assert mock_ws.send_message.call_count == 2


class TestWeComUploadMediaWsInvalidChunks:
    """Cover lines 356-357: invalid total_chunks (too many chunks)."""

    @pytest.mark.anyio
    async def test_upload_media_ws_too_many_chunks(self, tmp_path, caplog):
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_id": "b", "bot_secret": "s"})
        ch._ws_client = MagicMock()

        # Create a small file but pass a huge size to trigger >100 chunks
        # chunk_size = 512*1024, total_chunks = ceil(size/chunk_size)
        # 101 * 512*1024 = 53,477,376
        test_file = tmp_path / "tiny.txt"
        test_file.write_bytes(b"x" * 10)

        mock_aibot = MagicMock()
        mock_aibot.generate_req_id.return_value = "req_1"

        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            with caplog.at_level(logging.WARNING):
                result = await ch._upload_media_ws(
                    media_type="file",
                    filename="tiny.txt",
                    path=str(test_file),
                    size=101 * 512 * 1024,
                )
        assert result is None
        assert "invalid total_chunks" in caplog.text

    @pytest.mark.anyio
    async def test_upload_media_ws_zero_chunks(self, tmp_path, caplog):
        """Edge case: size=0 gives total_chunks=0 (invalid, < 1)."""
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_id": "b", "bot_secret": "s"})
        ch._ws_client = MagicMock()

        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        mock_aibot = MagicMock()
        mock_aibot.generate_req_id.return_value = "req_1"

        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            with caplog.at_level(logging.WARNING):
                result = await ch._upload_media_ws(
                    media_type="file",
                    filename="empty.txt",
                    path=str(test_file),
                    size=0,
                )
        assert result is None
        assert "invalid total_chunks" in caplog.text


class TestWeComUploadMediaWsChunkBreak:
    """Cover line 383: break when f.read(chunk_size) returns empty bytes during chunk loop."""

    @pytest.mark.anyio
    async def test_upload_media_ws_empty_chunk_break(self, tmp_path):
        """File smaller than the reported size: the loop iterates past the
        actual file content, and f.read() returns b"" triggering break."""
        from app.channels.wecom import WeComChannel

        ch = WeComChannel(_make_bus(), {"bot_id": "b", "bot_secret": "s"})
        ch._ws_client = MagicMock()

        # 100 bytes file, but tell it the size is 2 chunks worth
        # chunk_size = 512KB, total_chunks = ceil(1048576/524288) = 2
        test_file = tmp_path / "small.bin"
        test_file.write_bytes(b"A" * 100)

        mock_aibot = MagicMock()
        mock_aibot.generate_req_id.side_effect = lambda prefix: f"{prefix}_id"

        chunks_sent = []

        async def mock_send_cmd(req_id, body, cmd):
            if cmd == "aibot_upload_media_init":
                return {"body": {"upload_id": "upload_1"}}
            if cmd == "aibot_upload_media_chunk":
                chunks_sent.append(body)
                return {}
            if cmd == "aibot_upload_media_finish":
                return {"body": {"media_id": "media_xyz"}}
            return {}

        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            with patch.object(ch, "_send_ws_upload_command", side_effect=mock_send_cmd):
                # Pass size = 2 * chunk_size so total_chunks = 2.
                # First iteration reads 100 bytes (non-empty), second reads 0 -> break
                result = await ch._upload_media_ws(
                    media_type="file",
                    filename="small.bin",
                    path=str(test_file),
                    size=2 * 512 * 1024,
                )
        assert result == "media_xyz"
        # Only 1 chunk is sent (second iteration hits break at line 383)
        assert len(chunks_sent) == 1


# ===================================================================
# Discord Coverage Tests
# ===================================================================


class TestDiscordOnMessageEvent:
    """Cover line 102: the on_message event handler wiring and invocation."""

    def test_start_wires_and_invokes_on_message_handler(self):
        """Verify start() registers on_message and the handler delegates to _on_message."""
        from app.channels.discord import DiscordChannel

        ch = DiscordChannel(_make_bus(), {"bot_token": "test-token"})

        mock_discord = MagicMock()
        mock_client = MagicMock()
        mock_discord.Client.return_value = mock_client
        mock_discord.Intents.default.return_value = MagicMock()
        mock_discord.AllowedMentions.none.return_value = MagicMock()

        captured_handlers: dict[str, object] = {}

        def capture_event(handler):
            captured_handlers["on_message"] = handler
            return handler

        mock_client.event.side_effect = capture_event

        loop = asyncio.new_event_loop()
        ch._main_loop = loop

        async def _start():
            await ch.start()

        with patch.dict("sys.modules", {"discord": mock_discord}):
            loop.run_until_complete(_start())

        # The on_message handler should have been registered via @client.event
        assert "on_message" in captured_handlers

        # Now actually invoke the captured handler to cover line 102
        on_message_handler = captured_handlers["on_message"]
        mock_message = MagicMock()
        mock_message.author.bot = True  # Will be short-circuited in _on_message
        with patch.object(ch, "_on_message", new_callable=AsyncMock) as mock_on_msg:
            loop.run_until_complete(on_message_handler(mock_message))
            mock_on_msg.assert_called_once_with(mock_message)

        # Clean up
        ch._running = False
        ch._client = None
        if ch._thread:
            ch._thread.join(timeout=2)


class TestDiscordStopCloseException:
    """Cover lines 165-166: general exception during client close in stop()."""

    def test_stop_general_exception_during_close(self, caplog):
        from app.channels.discord import DiscordChannel

        ch = DiscordChannel(_make_bus(), {"bot_token": "test-token"})
        ch._running = True

        # Start a discord loop in a background thread so is_running() returns True
        discord_loop = asyncio.new_event_loop()
        ch._discord_loop = discord_loop
        loop_thread = threading.Thread(target=discord_loop.run_forever, daemon=True)
        loop_thread.start()

        client = MagicMock()

        async def _close():
            raise RuntimeError("unexpected close error")

        client.close = _close
        ch._client = client

        main_loop = asyncio.new_event_loop()

        try:
            with caplog.at_level(logging.WARNING, logger="app.channels.discord"):
                # Patch wait_for so the RuntimeError propagates instead of
                # being wrapped as TimeoutError
                original_wait_for = asyncio.wait_for

                async def _mock_wait_for(fut, timeout=None):
                    return await fut

                asyncio.wait_for = _mock_wait_for
                try:
                    main_loop.run_until_complete(ch.stop())
                finally:
                    asyncio.wait_for = original_wait_for
            assert "error while closing client" in caplog.text
        finally:
            discord_loop.call_soon_threadsafe(discord_loop.stop)
            loop_thread.join(timeout=2)


class TestDiscordOnMessageUserNone:
    """Cover lines 279-281: bot_mention/alt_mention/standard_mention when client.user is None."""

    @pytest.mark.anyio
    async def test_on_message_client_user_is_none(self):
        from app.channels.discord import DiscordChannel

        ch = DiscordChannel(_make_bus(), {"bot_token": "test-token"})
        ch._running = True

        mock_discord = MagicMock()
        mock_discord.Thread = type("Thread", (), {})
        ch._discord_module = mock_discord

        # Client with user=None
        client = MagicMock()
        client.user = None
        ch._client = client

        main_loop = MagicMock()
        main_loop.is_running.return_value = True
        ch._main_loop = main_loop
        ch._publish = MagicMock()

        msg = MagicMock()
        msg.content = "hello bot"
        msg.id = "msg_001"
        msg.author.id = "user1"
        msg.author.bot = False
        msg.author.display_name = "TestUser"
        msg.channel.id = "200001"
        msg.guild = None
        msg.create_thread = AsyncMock()

        # Channel type that does not match text/news (so no thread is created)
        unknown_type = MagicMock()
        mock_discord.ChannelType.text = MagicMock()
        mock_discord.ChannelType.news = MagicMock()
        msg.channel.type = unknown_type

        await ch._on_message(msg)

        # user is None => bot_mention/alt_mention/standard_mention are None/""
        # has_mention = False. With default config (not mention_only), still processes.
        ch._publish.assert_called_once()


class TestDiscordResolveTargetIntegration:
    """Cover lines 495-505: _resolve_target method with actual target ID resolution."""

    @pytest.mark.anyio
    async def test_resolve_target_tries_thread_ts_then_chat_id(self):
        from app.channels.discord import DiscordChannel

        ch = DiscordChannel(_make_bus(), {"bot_token": "test-token"})
        ch._client = MagicMock()
        ch._discord_loop = asyncio.new_event_loop()

        # First call (thread_ts) returns None, second (chat_id) returns target
        call_count = [0]
        expected_target = MagicMock()

        async def mock_get(raw_id):
            call_count[0] += 1
            if call_count[0] == 1:
                return None  # thread_ts not found
            return expected_target  # chat_id found

        ch._get_channel_or_thread = mock_get

        msg = _make_outbound(thread_ts="thread_123", chat_id="chat_456", channel_name="discord")
        result = await ch._resolve_target(msg)
        assert result is expected_target

    @pytest.mark.anyio
    async def test_resolve_target_neither_found(self):
        from app.channels.discord import DiscordChannel

        ch = DiscordChannel(_make_bus(), {"bot_token": "test-token"})
        ch._client = MagicMock()
        ch._discord_loop = asyncio.new_event_loop()
        ch._get_channel_or_thread = AsyncMock(return_value=None)

        msg = _make_outbound(thread_ts="thread_123", chat_id="chat_456", channel_name="discord")
        result = await ch._resolve_target(msg)
        assert result is None

    @pytest.mark.anyio
    async def test_resolve_target_deduplicates_ids(self):
        """When thread_ts == chat_id, only one lookup should happen."""
        from app.channels.discord import DiscordChannel

        ch = DiscordChannel(_make_bus(), {"bot_token": "test-token"})
        ch._client = MagicMock()
        ch._discord_loop = asyncio.new_event_loop()

        lookup_count = [0]
        expected_target = MagicMock()

        async def mock_get(raw_id):
            lookup_count[0] += 1
            return expected_target

        ch._get_channel_or_thread = mock_get

        msg = _make_outbound(thread_ts="same_id", chat_id="same_id", channel_name="discord")
        result = await ch._resolve_target(msg)
        assert result is expected_target
        assert lookup_count[0] == 1


class TestDiscordGetChannelOrThreadException:
    """Cover lines 516-521: exception during _get_channel_or_thread fetch."""

    @pytest.mark.anyio
    async def test_get_channel_or_thread_future_exception(self):
        from app.channels.discord import DiscordChannel

        ch = DiscordChannel(_make_bus(), {"bot_token": "test-token"})
        ch._client = MagicMock()
        ch._discord_loop = MagicMock()

        mock_future = MagicMock()

        def mock_wrap(fut):
            async def _raise():
                raise RuntimeError("fetch failed")

            return _raise()

        with patch("asyncio.run_coroutine_threadsafe", return_value=mock_future):
            with patch("asyncio.wrap_future", side_effect=mock_wrap):
                result = await ch._get_channel_or_thread("200001")
        assert result is None

    @pytest.mark.anyio
    async def test_get_channel_or_thread_valid_id_through_integration(self):
        """Integration test: valid ID goes through full path with run_coroutine_threadsafe."""
        from app.channels.discord import DiscordChannel

        ch = DiscordChannel(_make_bus(), {"bot_token": "test-token"})
        ch._client = MagicMock()
        ch._discord_loop = MagicMock()

        expected = MagicMock()

        def mock_rcts(coro, loop):
            return MagicMock()

        async def mock_wrap(fut):
            return expected

        with patch("asyncio.run_coroutine_threadsafe", side_effect=mock_rcts):
            with patch("asyncio.wrap_future", side_effect=mock_wrap):
                result = await ch._get_channel_or_thread("12345")
        assert result is expected
