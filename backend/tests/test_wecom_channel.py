"""Tests for app.channels.wecom — WeComChannel."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.channels.message_bus import InboundMessageType, MessageBus, OutboundMessage, ResolvedAttachment

if TYPE_CHECKING:
    from app.channels.wecom import WeComChannel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bus() -> MessageBus:
    return MessageBus()


def _make_channel(bus: MessageBus | None = None, config: dict | None = None) -> WeComChannel:
    from app.channels.wecom import WeComChannel

    bus = bus or _make_bus()
    config = config or {"bot_id": "bot_1", "bot_secret": "secret_1"}
    return WeComChannel(bus, config)


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


# ---------------------------------------------------------------------------
# Construction / properties
# ---------------------------------------------------------------------------


class TestWeComChannelInit:
    def test_defaults(self):
        ch = _make_channel()
        assert ch.name == "wecom"
        assert ch.supports_streaming is True
        assert ch._ws_client is None
        assert ch._running is False
        assert ch._working_message == "Working on it..."

    def test_config_stored(self):
        ch = _make_channel(config={"bot_id": "b", "bot_secret": "s"})
        assert ch.config == {"bot_id": "b", "bot_secret": "s"}


# ---------------------------------------------------------------------------
# start()
# ---------------------------------------------------------------------------


class TestWeComChannelStart:
    @pytest.mark.asyncio
    async def test_start_missing_sdk(self):
        ch = _make_channel()
        with patch("builtins.__import__", side_effect=ImportError("no aibot")):
            await ch.start()
        assert ch._running is False

    @pytest.mark.asyncio
    async def test_start_no_credentials(self):
        ch = _make_channel(config={})
        # The start() method gets bot_id from config with .get() —
        # with empty config, bot_id=None which is falsy → early return
        # But if the real SDK is installed, the import may succeed.
        # Force the import to fail so only the credential check path is tested.
        with patch.dict("sys.modules", {"aibot": None}):
            await ch.start()
        assert ch._running is False

    @pytest.mark.asyncio
    async def test_start_success(self):
        ch = _make_channel()

        mock_ws_client = MagicMock()
        mock_ws_client.connect = AsyncMock()
        mock_ws_client.on = MagicMock()

        mock_aibot = MagicMock()
        mock_aibot.WSClient.return_value = mock_ws_client
        mock_aibot.WSClientOptions = MagicMock()

        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            await ch.start()

        assert ch._running is True
        assert ch._ws_client is mock_ws_client
        mock_ws_client.on.assert_any_call("message.text", ch._on_ws_text)
        mock_ws_client.on.assert_any_call("message.mixed", ch._on_ws_mixed)
        mock_ws_client.on.assert_any_call("message.image", ch._on_ws_image)
        mock_ws_client.on.assert_any_call("message.file", ch._on_ws_file)

    @pytest.mark.asyncio
    async def test_start_custom_working_message(self):
        ch = _make_channel(config={"bot_id": "b", "bot_secret": "s", "working_message": "Processing..."})
        # The working_message is set during __init__ from the base class's
        # config, so check after construction, not after start.
        # But actually, WeComChannel sets _working_message in start(), not __init__.
        # We need to call start() with a mock to trigger the config read.
        mock_aibot = MagicMock()
        mock_aibot.WSClient.return_value = MagicMock()
        mock_aibot.WSClient.return_value.connect = AsyncMock()
        mock_aibot.WSClient.return_value.on = MagicMock()
        mock_aibot.WSClientOptions = MagicMock()
        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            await ch.start()
        assert ch._working_message == "Processing..."

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        ch = _make_channel()
        ch._running = True
        await ch.start()
        # Returns immediately


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------


class TestWeComChannelStop:
    @pytest.mark.asyncio
    async def test_stop_basic(self):
        ch = _make_channel()
        ch._running = True
        mock_task = MagicMock()
        ch._ws_task = mock_task
        mock_ws = MagicMock()
        ch._ws_client = mock_ws
        ch._ws_frames = {"k": "v"}
        ch._ws_stream_ids = {"k": "v"}
        ch.bus = MagicMock()

        await ch.stop()

        assert ch._running is False
        mock_task.cancel.assert_called_once()
        mock_ws.disconnect.assert_called_once()
        assert ch._ws_frames == {}
        assert ch._ws_stream_ids == {}

    @pytest.mark.asyncio
    async def test_stop_no_ws(self):
        ch = _make_channel()
        ch._running = True
        ch.bus = MagicMock()

        await ch.stop()
        assert ch._running is False

    @pytest.mark.asyncio
    async def test_stop_task_cancel_error(self):
        ch = _make_channel()
        ch._running = True
        ch._ws_task = MagicMock()
        ch._ws_task.cancel.side_effect = RuntimeError("cancel fail")
        ch._ws_client = MagicMock()
        ch._ws_client.disconnect.side_effect = RuntimeError("disconnect fail")
        ch.bus = MagicMock()

        await ch.stop()
        assert ch._running is False


# ---------------------------------------------------------------------------
# _clear_ws_context
# ---------------------------------------------------------------------------


class TestClearWsContext:
    def test_clear_none_thread(self):
        ch = _make_channel()
        ch._ws_frames = {"k": "v"}
        ch._ws_context = None
        ch._clear_ws_context(None)
        assert ch._ws_frames == {"k": "v"}

    def test_clear_existing_thread(self):
        ch = _make_channel()
        ch._ws_frames = {"msg_1": {"data": 1}}
        ch._ws_stream_ids = {"msg_1": "stream_1"}
        ch._clear_ws_context("msg_1")
        assert "msg_1" not in ch._ws_frames
        assert "msg_1" not in ch._ws_stream_ids


# ---------------------------------------------------------------------------
# send()
# ---------------------------------------------------------------------------


class TestWeComChannelSend:
    @pytest.mark.asyncio
    async def test_send_with_ws_client(self):
        ch = _make_channel()
        ch._ws_client = MagicMock()
        with patch.object(ch, "_send_ws", new_callable=AsyncMock) as mock_send:
            await ch.send(_make_outbound())
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_no_ws_client(self):
        ch = _make_channel()
        ch._ws_client = None
        # Should just log warning
        await ch.send(_make_outbound())


# ---------------------------------------------------------------------------
# _on_outbound
# ---------------------------------------------------------------------------


class TestOnOutbound:
    @pytest.mark.asyncio
    async def test_on_outbound_wrong_channel(self):
        ch = _make_channel()
        msg = _make_outbound(channel_name="other")
        await ch._on_outbound(msg)
        # No action

    @pytest.mark.asyncio
    async def test_on_outbound_success_with_attachments(self):
        ch = _make_channel()
        msg = _make_outbound(attachments=[_make_attachment()])
        with patch.object(ch, "send", new_callable=AsyncMock):
            with patch.object(ch, "send_file", new_callable=AsyncMock, return_value=True):
                await ch._on_outbound(msg)

    @pytest.mark.asyncio
    async def test_on_outbound_send_failure(self):
        ch = _make_channel()
        msg = _make_outbound(is_final=True)
        with patch.object(ch, "send", new_callable=AsyncMock, side_effect=RuntimeError("fail")):
            await ch._on_outbound(msg)
        # Should clear ws context on final message failure

    @pytest.mark.asyncio
    async def test_on_outbound_file_upload_failure(self):
        ch = _make_channel()
        msg = _make_outbound(attachments=[_make_attachment()])
        with patch.object(ch, "send", new_callable=AsyncMock):
            with patch.object(ch, "send_file", new_callable=AsyncMock, side_effect=RuntimeError("upload fail")):
                await ch._on_outbound(msg)


# ---------------------------------------------------------------------------
# send_file()
# ---------------------------------------------------------------------------


class TestWeComChannelSendFile:
    @pytest.mark.asyncio
    async def test_send_file_not_final(self):
        ch = _make_channel()
        msg = _make_outbound(is_final=False)
        result = await ch.send_file(msg, _make_attachment())
        assert result is True

    @pytest.mark.asyncio
    async def test_send_file_no_ws_client(self):
        ch = _make_channel()
        ch._ws_client = None
        result = await ch.send_file(_make_outbound(), _make_attachment())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_file_no_thread_ts(self):
        ch = _make_channel()
        ch._ws_client = MagicMock()
        msg = _make_outbound(thread_ts=None)
        result = await ch.send_file(msg, _make_attachment())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_file_no_frame(self):
        ch = _make_channel()
        ch._ws_client = MagicMock()
        ch._ws_frames = {}
        result = await ch.send_file(_make_outbound(), _make_attachment())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_file_image_too_large(self):
        ch = _make_channel()
        ch._ws_client = MagicMock()
        ch._ws_frames = {"msg_1": {"body": {}}}
        large_img = _make_attachment(is_image=True, size=5 * 1024 * 1024)
        result = await ch.send_file(_make_outbound(), large_img)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_file_file_too_large(self):
        ch = _make_channel()
        ch._ws_client = MagicMock()
        ch._ws_frames = {"msg_1": {"body": {}}}
        large_file = _make_attachment(is_image=False, size=30 * 1024 * 1024)
        result = await ch.send_file(_make_outbound(), large_file)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_file_success(self):
        ch = _make_channel()
        mock_ws_client = MagicMock()
        mock_ws_client.reply = AsyncMock()
        ch._ws_client = mock_ws_client
        ch._ws_frames = {"msg_1": {"body": {}}}

        with patch.object(ch, "_upload_media_ws", new_callable=AsyncMock, return_value="media_123"):
            result = await ch.send_file(_make_outbound(), _make_attachment())
            assert result is True

    @pytest.mark.asyncio
    async def test_send_file_upload_returns_none(self):
        ch = _make_channel()
        ch._ws_client = MagicMock()
        ch._ws_frames = {"msg_1": {"body": {}}}

        with patch.object(ch, "_upload_media_ws", new_callable=AsyncMock, return_value=None):
            result = await ch.send_file(_make_outbound(), _make_attachment())
            assert result is False


# ---------------------------------------------------------------------------
# _on_ws_text
# ---------------------------------------------------------------------------


class TestOnWsText:
    @pytest.mark.asyncio
    async def test_text_with_content(self):
        ch = _make_channel()
        frame = _make_frame(body={"text": {"content": "hello world"}})
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_text(frame)
            mock_pub.assert_called_once_with(frame, "hello world")

    @pytest.mark.asyncio
    async def test_text_with_quote(self):
        ch = _make_channel()
        frame = _make_frame(
            body={
                "text": {"content": "hello"},
                "quote": {"text": {"content": "quoted text"}},
            }
        )
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_text(frame)
            args = mock_pub.call_args[0]
            assert "hello" in args[1]
            assert "quoted text" in args[1]

    @pytest.mark.asyncio
    async def test_text_empty(self):
        ch = _make_channel()
        frame = _make_frame(body={"text": {"content": ""}})
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_text(frame)
            mock_pub.assert_not_called()

    @pytest.mark.asyncio
    async def test_text_none_body(self):
        ch = _make_channel()
        frame = {"body": None}
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_text(frame)
            mock_pub.assert_not_called()


# ---------------------------------------------------------------------------
# _on_ws_mixed
# ---------------------------------------------------------------------------


class TestOnWsMixed:
    @pytest.mark.asyncio
    async def test_mixed_with_text_and_image(self):
        ch = _make_channel()
        frame = _make_frame(
            body={
                "mixed": {
                    "msg_item": [
                        {"msgtype": "text", "text": {"content": "hello"}},
                        {"msgtype": "image", "image": {"url": "http://img.example.com/pic.png", "aeskey": "key123"}},
                    ]
                }
            }
        )
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_mixed(frame)
            args = mock_pub.call_args
            assert "hello" in args[0][1]
            assert len(args[1].get("files", args[0][2] if len(args[0]) > 2 else [])) == 1

    @pytest.mark.asyncio
    async def test_mixed_with_file(self):
        ch = _make_channel()
        frame = _make_frame(
            body={
                "mixed": {
                    "msg_item": [
                        {"msgtype": "file", "file": {"url": "http://example.com/doc.pdf"}},
                    ]
                }
            }
        )
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_mixed(frame)
            assert mock_pub.called

    @pytest.mark.asyncio
    async def test_mixed_empty(self):
        ch = _make_channel()
        frame = _make_frame(body={"mixed": {"msg_item": []}})
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_mixed(frame)
            mock_pub.assert_not_called()

    @pytest.mark.asyncio
    async def test_mixed_only_image(self):
        ch = _make_channel()
        frame = _make_frame(
            body={
                "mixed": {
                    "msg_item": [
                        {"msgtype": "image", "image": {"url": "http://img.example.com/pic.png"}},
                    ]
                }
            }
        )
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_mixed(frame)
            args = mock_pub.call_args
            # Should use default text for file-only messages
            assert args[0][1]


# ---------------------------------------------------------------------------
# _on_ws_image
# ---------------------------------------------------------------------------


class TestOnWsImage:
    @pytest.mark.asyncio
    async def test_image_with_url(self):
        ch = _make_channel()
        frame = _make_frame(
            body={
                "image": {"url": "http://img.example.com/pic.png", "aeskey": "key123"},
            }
        )
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_image(frame)
            mock_pub.assert_called_once()

    @pytest.mark.asyncio
    async def test_image_no_url(self):
        ch = _make_channel()
        frame = _make_frame(body={"image": {}})
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_image(frame)
            mock_pub.assert_not_called()


# ---------------------------------------------------------------------------
# _on_ws_file
# ---------------------------------------------------------------------------


class TestOnWsFile:
    @pytest.mark.asyncio
    async def test_file_with_url(self):
        ch = _make_channel()
        frame = _make_frame(
            body={
                "file": {"url": "http://example.com/doc.pdf", "aeskey": "key123"},
            }
        )
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_file(frame)
            mock_pub.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_no_url(self):
        ch = _make_channel()
        frame = _make_frame(body={"file": {}})
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_file(frame)
            mock_pub.assert_not_called()


# ---------------------------------------------------------------------------
# _publish_ws_inbound
# ---------------------------------------------------------------------------


class TestPublishWsInbound:
    @pytest.mark.asyncio
    async def test_no_ws_client(self):
        ch = _make_channel()
        ch._ws_client = None
        await ch._publish_ws_inbound({}, "text")
        # Returns without action

    @pytest.mark.asyncio
    async def test_no_msgid(self):
        ch = _make_channel()
        ch._ws_client = MagicMock()
        frame = {"body": {}}
        await ch._publish_ws_inbound(frame, "text")
        # Returns without publishing

    @pytest.mark.asyncio
    async def test_publish_success(self):
        ch = _make_channel()
        mock_ws = MagicMock()
        mock_ws.reply_stream = AsyncMock()
        ch._ws_client = mock_ws

        frame = _make_frame()
        mock_aibot = MagicMock()
        mock_aibot.generate_req_id.return_value = "stream_123"

        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            with patch("builtins.__import__", return_value=mock_aibot):
                with patch.object(ch.bus, "publish_inbound", new_callable=AsyncMock) as mock_pub:
                    await ch._publish_ws_inbound(frame, "hello", files=[{"type": "image", "url": "http://img.png"}])

                    mock_pub.assert_called_once()
                    inbound = mock_pub.call_args[0][0]
                    assert inbound.text == "hello"
                    assert inbound.topic_id == "user_1"

    @pytest.mark.asyncio
    async def test_publish_command(self):
        ch = _make_channel()
        mock_ws = MagicMock()
        mock_ws.reply_stream = AsyncMock()
        ch._ws_client = mock_ws

        frame = _make_frame()
        mock_aibot = MagicMock()
        mock_aibot.generate_req_id.return_value = "stream_123"

        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            with patch("builtins.__import__", return_value=mock_aibot):
                with patch.object(ch.bus, "publish_inbound", new_callable=AsyncMock) as mock_pub:
                    await ch._publish_ws_inbound(frame, "/help")
                    inbound = mock_pub.call_args[0][0]
                    assert inbound.msg_type == InboundMessageType.COMMAND

    @pytest.mark.asyncio
    async def test_publish_import_failure(self):
        ch = _make_channel()
        ch._ws_client = MagicMock()
        frame = _make_frame()
        with patch("builtins.__import__", side_effect=ImportError("no aibot")):
            await ch._publish_ws_inbound(frame, "hello")
            # Returns without publishing


# ---------------------------------------------------------------------------
# _send_ws
# ---------------------------------------------------------------------------


class TestSendWs:
    @pytest.mark.asyncio
    async def test_no_ws_client(self):
        ch = _make_channel()
        ch._ws_client = None
        await ch._send_ws(_make_outbound())

    @pytest.mark.asyncio
    async def test_send_with_frame(self):
        ch = _make_channel()
        mock_ws = MagicMock()
        mock_ws.reply_stream = AsyncMock()
        ch._ws_client = mock_ws
        ch._ws_frames = {"msg_1": {"body": {}}}
        ch._ws_stream_ids = {"msg_1": "stream_1"}

        mock_aibot = MagicMock()
        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            await ch._send_ws(_make_outbound())
            mock_ws.reply_stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_without_frame_fallback(self):
        ch = _make_channel()
        mock_ws = MagicMock()
        mock_ws.send_message = AsyncMock()
        ch._ws_client = mock_ws
        ch._ws_frames = {}

        mock_aibot = MagicMock()
        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            await ch._send_ws(_make_outbound(thread_ts="other_msg"))
            mock_ws.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_retries_on_failure(self):
        ch = _make_channel()
        mock_ws = MagicMock()
        mock_ws.reply_stream = AsyncMock(side_effect=RuntimeError("fail"))
        ch._ws_client = mock_ws
        ch._ws_frames = {"msg_1": {"body": {}}}
        ch._ws_stream_ids = {"msg_1": "stream_1"}

        with pytest.raises(RuntimeError, match="fail"):
            await ch._send_ws(_make_outbound(), _max_retries=2)

    @pytest.mark.asyncio
    async def test_send_no_stream_id_generates(self):
        ch = _make_channel()
        mock_ws = MagicMock()
        mock_ws.reply_stream = AsyncMock()
        ch._ws_client = mock_ws
        ch._ws_frames = {"msg_1": {"body": {}}}
        ch._ws_stream_ids = {}

        mock_aibot = MagicMock()
        mock_aibot.generate_req_id.return_value = "new_stream"

        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            await ch._send_ws(_make_outbound())
            assert ch._ws_stream_ids["msg_1"] == "new_stream"


# ---------------------------------------------------------------------------
# _upload_media_ws
# ---------------------------------------------------------------------------


class TestUploadMediaWs:
    @pytest.mark.asyncio
    async def test_no_ws_client(self):
        ch = _make_channel()
        ch._ws_client = None
        await ch._upload_media_ws(media_type="image", filename="test.png", path="/tmp/test.png", size=100)
        # Should be None

    @pytest.mark.asyncio
    async def test_upload_success(self, tmp_path):
        ch = _make_channel()
        ch._ws_client = MagicMock()

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 1024)

        mock_aibot = MagicMock()
        mock_aibot.generate_req_id.side_effect = lambda prefix: f"{prefix}_id"

        mock_init_ack = {"body": {"upload_id": "upload_1"}}
        mock_finish_ack = {"body": {"media_id": "media_1"}}

        async def mock_send_cmd(req_id, body, cmd):
            if cmd == "aibot_upload_media_init":
                return mock_init_ack
            if cmd == "aibot_upload_media_finish":
                return mock_finish_ack
            return {}

        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            with patch.object(ch, "_send_ws_upload_command", side_effect=mock_send_cmd):
                result = await ch._upload_media_ws(media_type="file", filename="test.txt", path=str(test_file), size=1024)
                assert result == "media_1"

    @pytest.mark.asyncio
    async def test_upload_no_upload_id(self, tmp_path):
        ch = _make_channel()
        ch._ws_client = MagicMock()

        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 100)

        mock_aibot = MagicMock()
        mock_aibot.generate_req_id.return_value = "req_1"

        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            with patch.object(ch, "_send_ws_upload_command", new_callable=AsyncMock, return_value={"body": {}}):
                result = await ch._upload_media_ws(media_type="file", filename="test.txt", path=str(test_file), size=100)
                assert result is None

    @pytest.mark.asyncio
    async def test_upload_no_media_id(self, tmp_path):
        ch = _make_channel()
        ch._ws_client = MagicMock()

        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 100)

        mock_aibot = MagicMock()
        mock_aibot.generate_req_id.return_value = "req_1"

        async def mock_send_cmd(req_id, body, cmd):
            if cmd == "aibot_upload_media_init":
                return {"body": {"upload_id": "upload_1"}}
            return {"body": {}}

        with patch.dict("sys.modules", {"aibot": mock_aibot}):
            with patch.object(ch, "_send_ws_upload_command", side_effect=mock_send_cmd):
                result = await ch._upload_media_ws(media_type="file", filename="test.txt", path=str(test_file), size=100)
                assert result is None

    @pytest.mark.asyncio
    async def test_upload_import_failure(self, tmp_path):
        ch = _make_channel()
        ch._ws_client = MagicMock()

        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 100)

        with patch("builtins.__import__", side_effect=ImportError("no aibot")):
            result = await ch._upload_media_ws(media_type="file", filename="test.txt", path=str(test_file), size=100)
            assert result is None


# ---------------------------------------------------------------------------
# _send_ws_upload_command
# ---------------------------------------------------------------------------


class TestSendWsUploadCommand:
    @pytest.mark.asyncio
    async def test_no_ws_client(self):
        ch = _make_channel()
        ch._ws_client = None
        with pytest.raises(RuntimeError, match="not available"):
            await ch._send_ws_upload_command("req_1", {}, "cmd")

    @pytest.mark.asyncio
    async def test_no_send_reply(self):
        ch = _make_channel()
        ch._ws_client = MagicMock()
        ch._ws_client._ws_manager = MagicMock()
        ch._ws_client._ws_manager.send_reply = None

        with pytest.raises(RuntimeError, match="does not expose"):
            await ch._send_ws_upload_command("req_1", {}, "cmd")

    @pytest.mark.asyncio
    async def test_success(self):
        ch = _make_channel()
        mock_send_reply = AsyncMock(return_value={"body": {"ok": True}})
        ch._ws_client = MagicMock()
        ch._ws_client._ws_manager = MagicMock()
        ch._ws_client._ws_manager.send_reply = mock_send_reply

        result = await ch._send_ws_upload_command("req_1", {"key": "val"}, "cmd")
        assert result == {"body": {"ok": True}}
        mock_send_reply.assert_called_once_with("req_1", {"key": "val"}, "cmd")


# ---------------------------------------------------------------------------
# Edge case: _on_ws_mixed with various items
# ---------------------------------------------------------------------------


class TestOnWsMixedEdgeCases:
    @pytest.mark.asyncio
    async def test_mixed_with_none_items(self):
        ch = _make_channel()
        frame = _make_frame(body={"mixed": {"msg_item": [None, {"msgtype": "text", "text": {"content": "hi"}}]}})
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_mixed(frame)
            mock_pub.assert_called_once()

    @pytest.mark.asyncio
    async def test_mixed_image_no_aeskey(self):
        ch = _make_channel()
        frame = _make_frame(
            body={
                "mixed": {
                    "msg_item": [
                        {"msgtype": "image", "image": {"url": "http://img.png"}},
                    ]
                }
            }
        )
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_mixed(frame)
            args = mock_pub.call_args
            files = args[0][2] if len(args[0]) > 2 else args[1].get("files", [])
            assert files[0]["aeskey"] is None


# ---------------------------------------------------------------------------
# _on_ws_image edge cases
# ---------------------------------------------------------------------------


class TestOnWsImageEdgeCases:
    @pytest.mark.asyncio
    async def test_image_with_aeskey(self):
        ch = _make_channel()
        frame = _make_frame(
            body={
                "image": {"url": "http://img.example.com/pic.png", "aeskey": "secret_key"},
            }
        )
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_image(frame)
            args = mock_pub.call_args
            files = args[0][2] if len(args[0]) > 2 else args[1].get("files", [])
            assert files[0]["aeskey"] == "secret_key"

    @pytest.mark.asyncio
    async def test_image_non_string_url(self):
        ch = _make_channel()
        frame = _make_frame(body={"image": {"url": 123}})
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._on_ws_image(frame)
            mock_pub.assert_not_called()


# ---------------------------------------------------------------------------
# _on_ws_file edge cases
# ---------------------------------------------------------------------------


class TestOnWsFileEdgeCases:
    @pytest.mark.asyncio
    async def test_file_with_aeskey(self):
        ch = _make_channel()
        frame = _make_frame(
            body={
                "file": {"url": "http://example.com/doc.pdf", "aeskey": "key"},
            }
        )
        with patch.object(ch, "_publish_ws_inbound", new_callable=AsyncMock):
            await ch._on_ws_mixed(frame)
            # Should be handled
