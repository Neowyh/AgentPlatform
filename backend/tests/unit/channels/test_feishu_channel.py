"""Comprehensive tests for app.channels.feishu — FeishuChannel.

Targets 98%+ branch coverage of every method in the module.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.channels.message_bus import (
    InboundMessage,
    InboundMessageType,
    MessageBus,
    OutboundMessage,
    ResolvedAttachment,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bus() -> MessageBus:
    return MessageBus()


def _make_channel(bus: MessageBus | None = None, config: dict | None = None):
    from app.channels.feishu import FeishuChannel

    bus = bus if bus is not None else _make_bus()
    config = config if config is not None else {"app_id": "test_app", "app_secret": "test_secret"}
    return FeishuChannel(bus, config)


def _make_outbound(**overrides) -> OutboundMessage:
    defaults = {
        "channel_name": "feishu",
        "chat_id": "chat_1",
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


def _make_event(
    content_dict,
    chat_id="chat_1",
    msg_id="msg_1",
    sender_id="user_1",
    root_id=None,
):
    """Build a mock Feishu event object."""
    event = MagicMock()
    event.event.message.chat_id = chat_id
    event.event.message.message_id = msg_id
    event.event.message.content = json.dumps(content_dict)
    event.event.message.root_id = root_id
    event.event.sender.sender_id.open_id = sender_id
    return event


def _run_on_message_with_loop(ch, content_dict, **kwargs):
    """Run _on_message with a live event loop in a background thread."""
    loop = asyncio.new_event_loop()
    ch._main_loop = loop
    ch._running = True

    event = _make_event(content_dict, **kwargs)
    published = []

    async def mock_prepare(msg_id, inbound):
        published.append(inbound)

    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()

    try:
        with patch.object(ch, "_prepare_inbound", side_effect=mock_prepare):
            ch._on_message(event)
            time.sleep(0.2)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        loop_thread.join(timeout=2)
        loop.close()

    return published


# ---------------------------------------------------------------------------
# _is_feishu_command
# ---------------------------------------------------------------------------


class TestIsFeishuCommand:
    def test_slash_command(self):
        from app.channels.feishu import _is_feishu_command

        assert _is_feishu_command("/help") is True

    def test_slash_command_with_args(self):
        from app.channels.feishu import _is_feishu_command

        assert _is_feishu_command("/bootstrap init") is True

    def test_slash_command_case_insensitive(self):
        from app.channels.feishu import _is_feishu_command

        assert _is_feishu_command("/HELP") is True

    def test_slash_command_uppercase(self):
        from app.channels.feishu import _is_feishu_command

        assert _is_feishu_command("/NEW") is True

    def test_not_a_command(self):
        from app.channels.feishu import _is_feishu_command

        assert _is_feishu_command("hello world") is False

    def test_unknown_slash_command(self):
        from app.channels.feishu import _is_feishu_command

        assert _is_feishu_command("/unknown") is False

    def test_absolute_path_not_command(self):
        from app.channels.feishu import _is_feishu_command

        assert _is_feishu_command("/tmp/some/file") is False

    def test_empty_string(self):
        from app.channels.feishu import _is_feishu_command

        assert _is_feishu_command("") is False

    def test_just_slash(self):
        from app.channels.feishu import _is_feishu_command

        # "/" has no command name after splitting → not in KNOWN_CHANNEL_COMMANDS
        assert _is_feishu_command("/") is False

    def test_all_known_commands(self):
        from app.channels.feishu import _is_feishu_command

        for cmd in ["/bootstrap", "/new", "/status", "/models", "/memory", "/help"]:
            assert _is_feishu_command(cmd) is True


# ---------------------------------------------------------------------------
# Construction / properties
# ---------------------------------------------------------------------------


class TestFeishuChannelInit:
    def test_defaults(self):
        ch = _make_channel()
        assert ch.name == "feishu"
        assert ch._thread is None
        assert ch._api_client is None
        assert ch.supports_streaming is True
        assert ch._running is False

    def test_config_stored(self):
        ch = _make_channel(config={"app_id": "a", "app_secret": "b"})
        assert ch.config == {"app_id": "a", "app_secret": "b"}

    def test_initial_background_tasks_empty(self):
        ch = _make_channel()
        assert ch._background_tasks == set()
        assert ch._running_card_ids == {}
        assert ch._running_card_tasks == {}

    def test_initial_lock_exists(self):
        ch = _make_channel()
        assert isinstance(ch._thread_lock, type(threading.Lock()))

    def test_lark_classes_initially_none(self):
        ch = _make_channel()
        assert ch._CreateMessageReactionRequest is None
        assert ch._CreateMessageReactionRequestBody is None
        assert ch._Emoji is None
        assert ch._PatchMessageRequest is None
        assert ch._PatchMessageRequestBody is None
        assert ch._CreateFileRequest is None
        assert ch._CreateFileRequestBody is None
        assert ch._CreateImageRequest is None
        assert ch._CreateImageRequestBody is None
        assert ch._GetMessageResourceRequest is None


# ---------------------------------------------------------------------------
# start()
# ---------------------------------------------------------------------------


class TestFeishuChannelStart:
    @pytest.mark.asyncio
    async def test_start_missing_lark(self):
        ch = _make_channel()
        with patch.dict("sys.modules", {"lark_oapi": None}):
            with patch("builtins.__import__", side_effect=ImportError("no lark")):
                await ch.start()
        assert ch._running is False

    @pytest.mark.asyncio
    async def test_start_no_credentials(self):
        ch = _make_channel(config={})
        mock_lark = MagicMock()
        mock_im_v1 = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "lark_oapi": mock_lark,
                "lark_oapi.api": MagicMock(),
                "lark_oapi.api.im": MagicMock(),
                "lark_oapi.api.im.v1": mock_im_v1,
            },
        ):
            await ch.start()
        # Without credentials, start() returns before setting _running=True
        assert ch._running is False

    @pytest.mark.asyncio
    async def test_start_empty_credentials(self):
        ch = _make_channel(config={"app_id": "", "app_secret": ""})
        mock_lark = MagicMock()
        mock_im_v1 = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "lark_oapi": mock_lark,
                "lark_oapi.api": MagicMock(),
                "lark_oapi.api.im": MagicMock(),
                "lark_oapi.api.im.v1": mock_im_v1,
            },
        ):
            await ch.start()
        assert ch._running is False

    @pytest.mark.asyncio
    async def test_start_only_app_id_no_secret(self):
        ch = _make_channel(config={"app_id": "test_id", "app_secret": ""})
        mock_lark = MagicMock()
        mock_im_v1 = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "lark_oapi": mock_lark,
                "lark_oapi.api": MagicMock(),
                "lark_oapi.api.im": MagicMock(),
                "lark_oapi.api.im.v1": mock_im_v1,
            },
        ):
            await ch.start()
        assert ch._running is False

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        ch = _make_channel()
        ch._running = True
        await ch.start()
        # Should return immediately

    @pytest.mark.asyncio
    async def test_start_success(self):
        ch = _make_channel()
        mock_lark = MagicMock()
        mock_lark.LogLevel.INFO = 1

        # Build a mock for the lark_oapi.api.im.v1 imports
        mock_im_v1 = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "lark_oapi": mock_lark,
                "lark_oapi.api": MagicMock(),
                "lark_oapi.api.im": MagicMock(),
                "lark_oapi.api.im.v1": mock_im_v1,
            },
        ):
            with patch("threading.Thread") as mock_thread_cls:
                mock_thread = MagicMock()
                mock_thread_cls.return_value = mock_thread
                await ch.start()

        assert ch._running is True
        assert ch._api_client is not None
        assert ch._main_loop is not None
        mock_thread.start.assert_called_once()
        ch.bus._outbound_listeners  # should have registered _on_outbound

    @pytest.mark.asyncio
    async def test_start_custom_domain(self):
        ch = _make_channel(config={"app_id": "a", "app_secret": "b", "domain": "https://custom.feishu.cn"})
        mock_lark = MagicMock()
        mock_lark.LogLevel.INFO = 1

        with patch.dict(
            "sys.modules",
            {
                "lark_oapi": mock_lark,
                "lark_oapi.api": MagicMock(),
                "lark_oapi.api.im": MagicMock(),
                "lark_oapi.api.im.v1": MagicMock(),
            },
        ):
            with patch("threading.Thread") as mock_thread_cls:
                mock_thread = MagicMock()
                mock_thread_cls.return_value = mock_thread
                await ch.start()

        assert ch._running is True


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------


class TestFeishuChannelStop:
    @pytest.mark.asyncio
    async def test_stop_basic(self):
        ch = _make_channel()
        ch._running = True
        mock_thread = MagicMock()
        ch._thread = mock_thread
        mock_task = MagicMock()
        mock_task.cancel = MagicMock()
        ch._background_tasks = {mock_task}
        ch._running_card_tasks = {"key": mock_task}
        ch.bus = MagicMock()

        await ch.stop()

        assert ch._running is False
        mock_task.cancel.assert_called()
        mock_thread.join.assert_called_once_with(timeout=5)
        assert ch._thread is None

    @pytest.mark.asyncio
    async def test_stop_no_thread(self):
        ch = _make_channel()
        ch._running = True
        ch.bus = MagicMock()

        await ch.stop()
        assert ch._running is False

    @pytest.mark.asyncio
    async def test_stop_clears_background_tasks(self):
        ch = _make_channel()
        ch._running = True
        ch.bus = MagicMock()
        task1 = MagicMock()
        task2 = MagicMock()
        ch._background_tasks = {task1, task2}

        await ch.stop()

        assert len(ch._background_tasks) == 0
        task1.cancel.assert_called_once()
        task2.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_clears_running_card_tasks(self):
        ch = _make_channel()
        ch._running = True
        ch.bus = MagicMock()
        task = MagicMock()
        ch._running_card_tasks = {"msg_1": task, "msg_2": task}

        await ch.stop()

        assert len(ch._running_card_tasks) == 0

    @pytest.mark.asyncio
    async def test_stop_unsubscribes_outbound(self):
        ch = _make_channel()
        ch._running = True
        bus = MagicMock()
        ch.bus = bus

        await ch.stop()
        bus.unsubscribe_outbound.assert_called_once()


# ---------------------------------------------------------------------------
# send()
# ---------------------------------------------------------------------------


class TestFeishuChannelSend:
    @pytest.mark.asyncio
    async def test_send_no_client(self):
        ch = _make_channel()
        ch._api_client = None
        await ch.send(_make_outbound())

    @pytest.mark.asyncio
    async def test_send_success(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        msg = _make_outbound(thread_ts="msg_1")

        with patch.object(ch, "_send_card_message", new_callable=AsyncMock) as mock_send:
            await ch.send(msg)
            mock_send.assert_called_once_with(msg)

    @pytest.mark.asyncio
    async def test_send_retries_on_failure(self):
        ch = _make_channel()
        ch._api_client = MagicMock()

        with patch.object(ch, "_send_card_message", new_callable=AsyncMock, side_effect=RuntimeError("fail")):
            with pytest.raises(RuntimeError, match="fail"):
                await ch.send(_make_outbound(), _max_retries=2)

    @pytest.mark.asyncio
    async def test_send_retries_then_succeeds(self):
        ch = _make_channel()
        ch._api_client = MagicMock()

        call_count = 0

        async def side_effect(msg):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("temporary fail")

        with patch.object(ch, "_send_card_message", side_effect=side_effect):
            await ch.send(_make_outbound(), _max_retries=3)
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_send_all_retries_fail_raises_last(self):
        ch = _make_channel()
        ch._api_client = MagicMock()

        with patch.object(
            ch,
            "_send_card_message",
            new_callable=AsyncMock,
            side_effect=RuntimeError("persistent fail"),
        ):
            with pytest.raises(RuntimeError, match="persistent fail"):
                await ch.send(_make_outbound(), _max_retries=3)

    @pytest.mark.asyncio
    async def test_send_logs_each_retry(self, caplog):
        ch = _make_channel()
        ch._api_client = MagicMock()

        call_count = 0

        async def side_effect(msg):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        with caplog.at_level(logging.WARNING):
            with patch.object(ch, "_send_card_message", side_effect=side_effect):
                with pytest.raises(RuntimeError):
                    await ch.send(_make_outbound(), _max_retries=3)

        # Should have logged warnings for attempts 1 and 2 (not the last)
        assert any("retrying" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# send_file()
# ---------------------------------------------------------------------------


class TestFeishuChannelSendFile:
    @pytest.mark.asyncio
    async def test_send_file_no_client(self):
        ch = _make_channel()
        ch._api_client = None
        result = await ch.send_file(_make_outbound(), _make_attachment())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_file_image_too_large(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        large = _make_attachment(is_image=True, size=20 * 1024 * 1024)
        result = await ch.send_file(_make_outbound(), large)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_file_file_too_large(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        large = _make_attachment(is_image=False, size=40 * 1024 * 1024)
        result = await ch.send_file(_make_outbound(), large)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_file_image_exactly_at_limit(self):
        """Image at exactly 10MB should still be sent (boundary)."""
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._ReplyMessageRequest = MagicMock()
        ch._ReplyMessageRequestBody = MagicMock()
        ch._CreateMessageRequest = MagicMock()
        ch._CreateMessageRequestBody = MagicMock()

        # Exactly 10MB — NOT > 10MB, so should pass the check
        with patch.object(ch, "_upload_image", new_callable=AsyncMock, return_value="img_key"):
            result = await ch.send_file(
                _make_outbound(thread_ts=None),
                _make_attachment(is_image=True, size=10 * 1024 * 1024),
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_send_file_file_exactly_at_limit(self):
        """File at exactly 30MB should still be sent (boundary)."""
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._ReplyMessageRequest = MagicMock()
        ch._ReplyMessageRequestBody = MagicMock()
        ch._CreateMessageRequest = MagicMock()
        ch._CreateMessageRequestBody = MagicMock()

        with patch.object(ch, "_upload_file", new_callable=AsyncMock, return_value="file_key"):
            result = await ch.send_file(
                _make_outbound(thread_ts=None),
                _make_attachment(is_image=False, size=30 * 1024 * 1024),
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_send_file_image_success_no_thread(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateMessageRequest = MagicMock()
        ch._CreateMessageRequestBody = MagicMock()

        with patch.object(ch, "_upload_image", new_callable=AsyncMock, return_value="img_key"):
            result = await ch.send_file(_make_outbound(thread_ts=None), _make_attachment(is_image=True))
            assert result is True

    @pytest.mark.asyncio
    async def test_send_file_image_success_with_thread(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._ReplyMessageRequest = MagicMock()
        ch._ReplyMessageRequestBody = MagicMock()

        with patch.object(ch, "_upload_image", new_callable=AsyncMock, return_value="img_key"):
            result = await ch.send_file(_make_outbound(thread_ts="msg_1"), _make_attachment(is_image=True))
            assert result is True

    @pytest.mark.asyncio
    async def test_send_file_file_success_with_thread(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._ReplyMessageRequest = MagicMock()
        ch._ReplyMessageRequestBody = MagicMock()

        with patch.object(ch, "_upload_file", new_callable=AsyncMock, return_value="file_key"):
            result = await ch.send_file(_make_outbound(thread_ts="msg_1"), _make_attachment())
            assert result is True

    @pytest.mark.asyncio
    async def test_send_file_file_success_no_thread(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateMessageRequest = MagicMock()
        ch._CreateMessageRequestBody = MagicMock()

        with patch.object(ch, "_upload_file", new_callable=AsyncMock, return_value="file_key"):
            result = await ch.send_file(_make_outbound(thread_ts=None), _make_attachment())
            assert result is True

    @pytest.mark.asyncio
    async def test_send_file_exception(self):
        ch = _make_channel()
        ch._api_client = MagicMock()

        with patch.object(ch, "_upload_file", new_callable=AsyncMock, side_effect=RuntimeError("upload fail")):
            result = await ch.send_file(_make_outbound(), _make_attachment())
            assert result is False


# ---------------------------------------------------------------------------
# _upload_image / _upload_file
# ---------------------------------------------------------------------------


class TestUploadHelpers:
    @pytest.mark.asyncio
    async def test_upload_image_success(self, tmp_path):
        ch = _make_channel()
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG")

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.data.image_key = "img_123"

        ch._api_client = MagicMock()
        ch._CreateImageRequest = MagicMock()
        ch._CreateImageRequestBody = MagicMock()
        ch._api_client.im.v1.image.create.return_value = mock_response

        result = await ch._upload_image(img_file)
        assert result == "img_123"

    @pytest.mark.asyncio
    async def test_upload_image_failure(self, tmp_path):
        ch = _make_channel()
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG")

        mock_response = MagicMock()
        mock_response.success.return_value = False
        mock_response.code = 500
        mock_response.msg = "internal error"

        ch._api_client = MagicMock()
        ch._CreateImageRequest = MagicMock()
        ch._CreateImageRequestBody = MagicMock()
        ch._api_client.im.v1.image.create.return_value = mock_response

        with pytest.raises(RuntimeError, match="Feishu image upload failed"):
            await ch._upload_image(img_file)

    @pytest.mark.asyncio
    async def test_upload_file_various_types(self, tmp_path):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateFileRequest = MagicMock()
        ch._CreateFileRequestBody = MagicMock()

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.data.file_key = "file_123"
        ch._api_client.im.v1.file.create.return_value = mock_response

        for ext, expected_type in [
            (".xls", "xls"),
            (".xlsx", "xls"),
            (".csv", "xls"),
            (".ppt", "ppt"),
            (".pptx", "ppt"),
            (".pdf", "pdf"),
            (".doc", "doc"),
            (".docx", "doc"),
            (".txt", "stream"),
            (".zip", "stream"),
            (".mp4", "stream"),
        ]:
            path = tmp_path / f"test{ext}"
            path.write_bytes(b"data")
            result = await ch._upload_file(path, f"test{ext}")
            assert result == "file_123"

    @pytest.mark.asyncio
    async def test_upload_file_failure(self, tmp_path):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateFileRequest = MagicMock()
        ch._CreateFileRequestBody = MagicMock()

        mock_response = MagicMock()
        mock_response.success.return_value = False
        mock_response.code = 400
        mock_response.msg = "bad request"
        ch._api_client.im.v1.file.create.return_value = mock_response

        path = tmp_path / "test.txt"
        path.write_bytes(b"data")

        with pytest.raises(RuntimeError, match="Feishu file upload failed"):
            await ch._upload_file(path, "test.txt")

    @pytest.mark.asyncio
    async def test_upload_file_path_without_suffix(self, tmp_path):
        """When path has no suffix attribute, file_type defaults to 'stream'."""
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateFileRequest = MagicMock()
        ch._CreateFileRequestBody = MagicMock()

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.data.file_key = "file_456"
        ch._api_client.im.v1.file.create.return_value = mock_response

        # Use a string path (no .suffix attribute, hasattr returns False)
        path = tmp_path / "somefile"
        path.write_bytes(b"data")
        result = await ch._upload_file(str(path), "somefile")
        assert result == "file_456"


# ---------------------------------------------------------------------------
# receive_file()
# ---------------------------------------------------------------------------


class TestReceiveFile:
    @pytest.mark.asyncio
    async def test_receive_file_no_thread_ts(self):
        ch = _make_channel()
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="hello",
            thread_ts=None,
            files=[{"image_key": "img1"}],
        )
        result = await ch.receive_file(msg, "thread_1")
        assert result is msg

    @pytest.mark.asyncio
    async def test_receive_file_no_files(self):
        ch = _make_channel()
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="hello",
            thread_ts="msg_1",
            files=[],
        )
        result = await ch.receive_file(msg, "thread_1")
        assert result is msg

    @pytest.mark.asyncio
    async def test_receive_file_with_image(self):
        ch = _make_channel()
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="[image]",
            thread_ts="msg_1",
            files=[{"image_key": "img_123"}],
        )

        with patch.object(ch, "_receive_single_file", new_callable=AsyncMock, return_value="/mnt/user-data/uploads/photo.png"):
            result = await ch.receive_file(msg, "thread_1")
            assert "/mnt/user-data/uploads/photo.png" in result.text

    @pytest.mark.asyncio
    async def test_receive_file_with_file_key(self):
        ch = _make_channel()
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="[file]",
            thread_ts="msg_1",
            files=[{"file_key": "file_123"}],
        )

        with patch.object(ch, "_receive_single_file", new_callable=AsyncMock, return_value="/mnt/user-data/uploads/doc.pdf"):
            result = await ch.receive_file(msg, "thread_1")
            assert "/mnt/user-data/uploads/doc.pdf" in result.text

    @pytest.mark.asyncio
    async def test_receive_file_multiple_files(self):
        """Multiple files are processed in order, each replacing the first placeholder."""
        ch = _make_channel()
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="[image] and [image]",
            thread_ts="msg_1",
            files=[{"image_key": "img_1"}, {"image_key": "img_2"}],
        )

        call_count = 0

        async def mock_receive(ts, key, type_, tid):
            nonlocal call_count
            call_count += 1
            return f"/mnt/user-data/uploads/file{call_count}.png"

        with patch.object(ch, "_receive_single_file", side_effect=mock_receive):
            result = await ch.receive_file(msg, "thread_1")
            assert "/mnt/user-data/uploads/file1.png" in result.text
            assert "/mnt/user-data/uploads/file2.png" in result.text

    @pytest.mark.asyncio
    async def test_receive_file_mixed_image_and_file(self):
        ch = _make_channel()
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="[image] and [file]",
            thread_ts="msg_1",
            files=[{"image_key": "img_1"}, {"file_key": "file_1"}],
        )

        async def mock_receive(ts, key, type_, tid):
            if type_ == "image":
                return "/mnt/user-data/uploads/img.png"
            return "/mnt/user-data/uploads/doc.pdf"

        with patch.object(ch, "_receive_single_file", side_effect=mock_receive):
            result = await ch.receive_file(msg, "thread_1")
            assert "/mnt/user-data/uploads/img.png" in result.text
            assert "/mnt/user-data/uploads/doc.pdf" in result.text

    @pytest.mark.asyncio
    async def test_receive_file_unknown_file_entry_skipped(self):
        """File entries with neither image_key nor file_key are silently skipped."""
        ch = _make_channel()
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="[image] and [file]",
            thread_ts="msg_1",
            files=[{"image_key": "img_1"}, {"sticker_key": "sticker_1"}],
        )

        async def mock_receive(ts, key, type_, tid):
            return "/mnt/user-data/uploads/img.png"

        with patch.object(ch, "_receive_single_file", side_effect=mock_receive) as mock_fn:
            await ch.receive_file(msg, "thread_1")
            # Only the image file was processed, sticker was skipped
            assert mock_fn.call_count == 1


# ---------------------------------------------------------------------------
# _receive_single_file — full path coverage
# ---------------------------------------------------------------------------


class TestReceiveSingleFile:
    @pytest.mark.asyncio
    async def test_api_exception(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._GetMessageResourceRequest = MagicMock()
        ch._api_client.im.v1.message_resource.get.side_effect = RuntimeError("api error")

        result = await ch._receive_single_file("msg_1", "file_key", "file", "thread_1")
        assert "Failed" in result

    @pytest.mark.asyncio
    async def test_api_failure(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._GetMessageResourceRequest = MagicMock()

        mock_response = MagicMock()
        mock_response.success.return_value = False
        mock_response.code = 404
        mock_response.msg = "not found"
        mock_response.get_log_id.return_value = "log_123"
        ch._api_client.im.v1.message_resource.get.return_value = mock_response

        result = await ch._receive_single_file("msg_1", "file_key", "file", "thread_1")
        assert "Failed" in result

    @pytest.mark.asyncio
    async def test_no_stream(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._GetMessageResourceRequest = MagicMock()

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.file = None
        ch._api_client.im.v1.message_resource.get.return_value = mock_response

        result = await ch._receive_single_file("msg_1", "file_key", "file", "thread_1")
        assert "Failed" in result

    @pytest.mark.asyncio
    async def test_read_exception(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._GetMessageResourceRequest = MagicMock()

        mock_stream = MagicMock()
        mock_stream.read.side_effect = OSError("read error")

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.file = mock_stream
        ch._api_client.im.v1.message_resource.get.return_value = mock_response

        result = await ch._receive_single_file("msg_1", "file_key", "file", "thread_1")
        assert "Failed" in result

    @pytest.mark.asyncio
    async def test_empty_content(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._GetMessageResourceRequest = MagicMock()

        mock_stream = MagicMock()
        mock_stream.read.return_value = b""

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.file = mock_stream
        ch._api_client.im.v1.message_resource.get.return_value = mock_response

        result = await ch._receive_single_file("msg_1", "file_key", "file", "thread_1")
        assert "Failed" in result

    @pytest.mark.asyncio
    async def test_success_with_file_name_containing_dots(self, tmp_path):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._GetMessageResourceRequest = MagicMock()

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()

        mock_stream = MagicMock()
        mock_stream.read.return_value = b"file content"

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.file = mock_stream
        mock_response.file_name = "my.document.pdf"
        ch._api_client.im.v1.message_resource.get.return_value = mock_response

        mock_paths = MagicMock()
        mock_paths.sandbox_uploads_dir.return_value = uploads_dir

        mock_sandbox_provider = MagicMock()
        mock_sandbox_provider.acquire.return_value = "local"

        with (
            patch("app.channels.feishu.get_paths", return_value=mock_paths),
            patch("app.channels.feishu.get_effective_user_id", return_value="user_1"),
            patch("app.channels.feishu.get_sandbox_provider", return_value=mock_sandbox_provider),
        ):
            result = await ch._receive_single_file("msg_1", "fk_123", "file", "thread_1")

        assert "/mnt/user-data/uploads/" in result
        assert "my_document.pdf" in result  # dots in name sanitized

    @pytest.mark.asyncio
    async def test_success_with_default_filename_image(self, tmp_path):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._GetMessageResourceRequest = MagicMock()

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()

        mock_stream = MagicMock()
        mock_stream.read.return_value = b"image bytes"

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.file = mock_stream
        # No file_name attribute
        del mock_response.file_name
        ch._api_client.im.v1.message_resource.get.return_value = mock_response

        mock_paths = MagicMock()
        mock_paths.sandbox_uploads_dir.return_value = uploads_dir

        mock_sandbox_provider = MagicMock()
        mock_sandbox_provider.acquire.return_value = "local"

        with (
            patch("app.channels.feishu.get_paths", return_value=mock_paths),
            patch("app.channels.feishu.get_effective_user_id", return_value="user_1"),
            patch("app.channels.feishu.get_sandbox_provider", return_value=mock_sandbox_provider),
        ):
            result = await ch._receive_single_file("msg_1", "abc123def456ghi", "image", "thread_1")

        assert "/mnt/user-data/uploads/" in result
        # Default filename uses last 12 chars + .png for images
        assert "def456ghi.png" in result

    @pytest.mark.asyncio
    async def test_success_filename_without_dots(self, tmp_path):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._GetMessageResourceRequest = MagicMock()

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()

        mock_stream = MagicMock()
        mock_stream.read.return_value = b"data"

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.file = mock_stream
        mock_response.file_name = "filename_no_ext"
        ch._api_client.im.v1.message_resource.get.return_value = mock_response

        mock_paths = MagicMock()
        mock_paths.sandbox_uploads_dir.return_value = uploads_dir

        mock_sandbox_provider = MagicMock()
        mock_sandbox_provider.acquire.return_value = "local"

        with (
            patch("app.channels.feishu.get_paths", return_value=mock_paths),
            patch("app.channels.feishu.get_effective_user_id", return_value="user_1"),
            patch("app.channels.feishu.get_sandbox_provider", return_value=mock_sandbox_provider),
        ):
            result = await ch._receive_single_file("msg_1", "fk_123", "file", "thread_1")

        assert "/mnt/user-data/uploads/filename_no_ext" in result

    @pytest.mark.asyncio
    async def test_success_non_local_sandbox(self, tmp_path):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._GetMessageResourceRequest = MagicMock()

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()

        mock_stream = MagicMock()
        mock_stream.read.return_value = b"data"

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.file = mock_stream
        mock_response.file_name = "test.pdf"
        ch._api_client.im.v1.message_resource.get.return_value = mock_response

        mock_paths = MagicMock()
        mock_paths.sandbox_uploads_dir.return_value = uploads_dir

        mock_sandbox = MagicMock()
        mock_sandbox_provider = MagicMock()
        mock_sandbox_provider.acquire.return_value = "sandbox_abc"
        mock_sandbox_provider.get.return_value = mock_sandbox

        with (
            patch("app.channels.feishu.get_paths", return_value=mock_paths),
            patch("app.channels.feishu.get_effective_user_id", return_value="user_1"),
            patch("app.channels.feishu.get_sandbox_provider", return_value=mock_sandbox_provider),
        ):
            result = await ch._receive_single_file("msg_1", "fk_123", "file", "thread_1")

        assert "/mnt/user-data/uploads/" in result
        mock_sandbox.update_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_sandbox_not_found(self, tmp_path):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._GetMessageResourceRequest = MagicMock()

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()

        mock_stream = MagicMock()
        mock_stream.read.return_value = b"data"

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.file = mock_stream
        mock_response.file_name = "test.bin"
        ch._api_client.im.v1.message_resource.get.return_value = mock_response

        mock_paths = MagicMock()
        mock_paths.sandbox_uploads_dir.return_value = uploads_dir

        mock_sandbox_provider = MagicMock()
        mock_sandbox_provider.acquire.return_value = "sandbox_abc"
        mock_sandbox_provider.get.return_value = None

        with (
            patch("app.channels.feishu.get_paths", return_value=mock_paths),
            patch("app.channels.feishu.get_effective_user_id", return_value="user_1"),
            patch("app.channels.feishu.get_sandbox_provider", return_value=mock_sandbox_provider),
        ):
            result = await ch._receive_single_file("msg_1", "fk_123", "file", "thread_1")

        assert "Failed" in result

    @pytest.mark.asyncio
    async def test_sandbox_sync_exception(self, tmp_path):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._GetMessageResourceRequest = MagicMock()

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()

        mock_stream = MagicMock()
        mock_stream.read.return_value = b"data"

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.file = mock_stream
        mock_response.file_name = "test.bin"
        ch._api_client.im.v1.message_resource.get.return_value = mock_response

        mock_paths = MagicMock()
        mock_paths.sandbox_uploads_dir.return_value = uploads_dir

        mock_sandbox_provider = MagicMock()
        mock_sandbox_provider.acquire.side_effect = RuntimeError("sandbox error")

        with (
            patch("app.channels.feishu.get_paths", return_value=mock_paths),
            patch("app.channels.feishu.get_effective_user_id", return_value="user_1"),
            patch("app.channels.feishu.get_sandbox_provider", return_value=mock_sandbox_provider),
        ):
            result = await ch._receive_single_file("msg_1", "fk_123", "file", "thread_1")

        assert "Failed" in result

    @pytest.mark.asyncio
    async def test_download_write_exception(self, tmp_path):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._GetMessageResourceRequest = MagicMock()

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()

        mock_stream = MagicMock()
        mock_stream.read.return_value = b"data"

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.file = mock_stream
        mock_response.file_name = "test.bin"
        ch._api_client.im.v1.message_resource.get.return_value = mock_response

        mock_paths = MagicMock()
        mock_paths.sandbox_uploads_dir.return_value = uploads_dir

        with (
            patch("app.channels.feishu.get_paths", return_value=mock_paths),
            patch("app.channels.feishu.get_effective_user_id", return_value="user_1"),
            patch.object(Path, "write_bytes", side_effect=OSError("write error")),
        ):
            result = await ch._receive_single_file("msg_1", "fk_123", "file", "thread_1")

        assert "Failed" in result

    @pytest.mark.asyncio
    async def test_success_file_name_with_path_chars(self, tmp_path):
        """Filename containing path separators should be sanitized."""
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._GetMessageResourceRequest = MagicMock()

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()

        mock_stream = MagicMock()
        mock_stream.read.return_value = b"data"

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.file = mock_stream
        mock_response.file_name = "path/to/file.txt"
        ch._api_client.im.v1.message_resource.get.return_value = mock_response

        mock_paths = MagicMock()
        mock_paths.sandbox_uploads_dir.return_value = uploads_dir

        mock_sandbox_provider = MagicMock()
        mock_sandbox_provider.acquire.return_value = "local"

        with (
            patch("app.channels.feishu.get_paths", return_value=mock_paths),
            patch("app.channels.feishu.get_effective_user_id", return_value="user_1"),
            patch("app.channels.feishu.get_sandbox_provider", return_value=mock_sandbox_provider),
        ):
            result = await ch._receive_single_file("msg_1", "fk_123", "file", "thread_1")

        assert "/mnt/user-data/uploads/" in result
        # path/to should be sanitized
        assert "path_to" in result


# ---------------------------------------------------------------------------
# _build_card_content
# ---------------------------------------------------------------------------


class TestBuildCardContent:
    def test_build_card(self):
        from app.channels.feishu import FeishuChannel

        card_json = FeishuChannel._build_card_content("Hello **world**")
        card = json.loads(card_json)
        assert card["config"]["wide_screen_mode"] is True
        assert card["config"]["update_multi"] is True
        assert card["elements"][0]["tag"] == "markdown"
        assert card["elements"][0]["content"] == "Hello **world**"

    def test_build_card_empty_text(self):
        from app.channels.feishu import FeishuChannel

        card_json = FeishuChannel._build_card_content("")
        card = json.loads(card_json)
        assert card["elements"][0]["content"] == ""

    def test_build_card_multiline(self):
        from app.channels.feishu import FeishuChannel

        text = "Line 1\nLine 2\n**bold**"
        card_json = FeishuChannel._build_card_content(text)
        card = json.loads(card_json)
        assert card["elements"][0]["content"] == text


# ---------------------------------------------------------------------------
# Reaction helpers
# ---------------------------------------------------------------------------


class TestReactionHelpers:
    @pytest.mark.asyncio
    async def test_add_reaction_no_client(self):
        ch = _make_channel()
        ch._api_client = None
        await ch._add_reaction("msg_1")
        # No error

    @pytest.mark.asyncio
    async def test_add_reaction_no_request_class(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateMessageReactionRequest = None
        await ch._add_reaction("msg_1")
        # Should return early without calling API

    @pytest.mark.asyncio
    async def test_add_reaction_success(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateMessageReactionRequest = MagicMock()
        ch._CreateMessageReactionRequestBody = MagicMock()
        ch._Emoji = MagicMock()
        await ch._add_reaction("msg_1", "OK")
        ch._api_client.im.v1.message_reaction.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_reaction_default_emoji(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateMessageReactionRequest = MagicMock()
        ch._CreateMessageReactionRequestBody = MagicMock()
        ch._Emoji = MagicMock()
        await ch._add_reaction("msg_1")
        ch._api_client.im.v1.message_reaction.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_reaction_exception(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateMessageReactionRequest = MagicMock()
        ch._CreateMessageReactionRequestBody = MagicMock()
        ch._Emoji = MagicMock()
        ch._api_client.im.v1.message_reaction.create.side_effect = RuntimeError("api fail")

        # Should not raise, just log
        await ch._add_reaction("msg_1", "OK")


# ---------------------------------------------------------------------------
# Card helpers
# ---------------------------------------------------------------------------


class TestCardHelpers:
    @pytest.mark.asyncio
    async def test_reply_card_no_client(self):
        ch = _make_channel()
        ch._api_client = None
        result = await ch._reply_card("msg_1", "text")
        assert result is None

    @pytest.mark.asyncio
    async def test_reply_card_success(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._ReplyMessageRequest = MagicMock()
        ch._ReplyMessageRequestBody = MagicMock()

        mock_response = MagicMock()
        mock_response.data.message_id = "card_123"
        ch._api_client.im.v1.message.reply.return_value = mock_response

        result = await ch._reply_card("msg_1", "Hello")
        assert result == "card_123"

    @pytest.mark.asyncio
    async def test_reply_card_no_data(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._ReplyMessageRequest = MagicMock()
        ch._ReplyMessageRequestBody = MagicMock()

        mock_response = MagicMock()
        mock_response.data = None
        ch._api_client.im.v1.message.reply.return_value = mock_response

        result = await ch._reply_card("msg_1", "Hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_card_no_client(self):
        ch = _make_channel()
        ch._api_client = None
        await ch._create_card("chat_1", "text")
        # No error

    @pytest.mark.asyncio
    async def test_create_card_success(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateMessageRequest = MagicMock()
        ch._CreateMessageRequestBody = MagicMock()

        await ch._create_card("chat_1", "Hello")
        ch._api_client.im.v1.message.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_card_no_client(self):
        ch = _make_channel()
        ch._api_client = None
        await ch._update_card("msg_1", "text")
        # No error

    @pytest.mark.asyncio
    async def test_update_card_no_patch_request(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._PatchMessageRequest = None
        await ch._update_card("msg_1", "text")
        # Should return early

    @pytest.mark.asyncio
    async def test_update_card_success(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._PatchMessageRequest = MagicMock()
        ch._PatchMessageRequestBody = MagicMock()

        await ch._update_card("msg_1", "Hello")
        ch._api_client.im.v1.message.patch.assert_called_once()


# ---------------------------------------------------------------------------
# Running card management
# ---------------------------------------------------------------------------


class TestRunningCardManagement:
    @pytest.mark.asyncio
    async def test_create_running_card(self):
        ch = _make_channel()
        with patch.object(ch, "_reply_card", new_callable=AsyncMock, return_value="card_msg_1"):
            result = await ch._create_running_card("src_msg", "Working...")
            assert result == "card_msg_1"
            assert ch._running_card_ids["src_msg"] == "card_msg_1"

    @pytest.mark.asyncio
    async def test_create_running_card_no_id(self):
        ch = _make_channel()
        with patch.object(ch, "_reply_card", new_callable=AsyncMock, return_value=None):
            result = await ch._create_running_card("src_msg", "Working...")
            assert result is None
            assert "src_msg" not in ch._running_card_ids

    def test_ensure_running_card_started_already_exists(self):
        ch = _make_channel()
        ch._running_card_ids["src_msg"] = "card_1"
        result = ch._ensure_running_card_started("src_msg")
        assert result is None

    def test_ensure_running_card_started_already_task(self):
        ch = _make_channel()
        mock_task = MagicMock()
        ch._running_card_tasks["src_msg"] = mock_task
        result = ch._ensure_running_card_started("src_msg")
        assert result is mock_task

    def test_ensure_running_card_started_creates_new_task(self):
        ch = _make_channel()
        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task
            result = ch._ensure_running_card_started("src_msg", "Loading...")
            assert result is mock_task
            assert ch._running_card_tasks["src_msg"] is mock_task
            mock_task.add_done_callback.assert_called_once()

    def test_ensure_running_card_started_default_text(self):
        ch = _make_channel()
        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task
            ch._ensure_running_card_started("src_msg")
            # Default text is "Working on it..."

    @pytest.mark.asyncio
    async def test_ensure_running_card_returns_cached(self):
        ch = _make_channel()
        ch._running_card_ids["src_msg"] = "card_1"
        result = await ch._ensure_running_card("src_msg")
        assert result == "card_1"

    @pytest.mark.asyncio
    async def test_ensure_running_card_starts_and_awaits(self):
        ch = _make_channel()

        async def fake_create(mid, text="Working on it..."):
            ch._running_card_ids[mid] = "new_card"
            return "new_card"

        with patch.object(ch, "_create_running_card", side_effect=fake_create):
            result = await ch._ensure_running_card("src_msg")
            assert result == "new_card"

    @pytest.mark.asyncio
    async def test_ensure_running_card_started_returns_none_then_cached(self):
        """When _ensure_running_card_started returns None but card was cached meanwhile."""
        ch = _make_channel()
        ch._running_card_ids["src_msg"] = "card_cached"

        # _ensure_running_card_started returns None because running_card_id exists
        result = await ch._ensure_running_card("src_msg")
        assert result == "card_cached"

    @pytest.mark.asyncio
    async def test_ensure_running_card_concurrent_caching(self):
        """When _ensure_running_card_started returns None because a concurrent callback
        set the running card ID between the first check and _ensure_running_card_started."""
        ch = _make_channel()
        # running_card_id is not set at the start

        def side_effect_started(source_message_id, text="Working on it..."):
            # Simulate a concurrent callback that sets the card ID
            ch._running_card_ids[source_message_id] = "card_from_callback"
            return None

        with patch.object(ch, "_ensure_running_card_started", side_effect=side_effect_started):
            result = await ch._ensure_running_card("src_msg")
            assert result == "card_from_callback"

    def test_finalize_running_card_task(self):
        ch = _make_channel()
        task = MagicMock()
        task.exception.return_value = None
        ch._running_card_tasks["src_msg"] = task
        ch._finalize_running_card_task("src_msg", task)
        assert "src_msg" not in ch._running_card_tasks

    def test_finalize_running_card_task_different_task(self):
        """When the stored task differs from the callback task, don't remove it."""
        ch = _make_channel()
        stored_task = MagicMock()
        stored_task.exception.return_value = None
        callback_task = MagicMock()
        callback_task.exception.return_value = None
        ch._running_card_tasks["src_msg"] = stored_task
        ch._finalize_running_card_task("src_msg", callback_task)
        # Stored task should NOT be removed
        assert ch._running_card_tasks["src_msg"] is stored_task

    def test_finalize_running_card_task_no_entry(self):
        """When no task is stored for the message, should not raise."""
        ch = _make_channel()
        task = MagicMock()
        task.exception.return_value = None
        ch._finalize_running_card_task("nonexistent", task)


# ---------------------------------------------------------------------------
# Background task tracking
# ---------------------------------------------------------------------------


class TestBackgroundTaskTracking:
    def test_track_background_task(self):
        ch = _make_channel()
        task = MagicMock()
        ch._track_background_task(task, name="test", msg_id="msg_1")
        assert task in ch._background_tasks
        task.add_done_callback.assert_called_once()

    def test_finalize_background_task(self):
        ch = _make_channel()
        task = MagicMock()
        task.exception.return_value = None
        ch._background_tasks.add(task)
        ch._finalize_background_task(task, "test", "msg_1")
        assert task not in ch._background_tasks

    def test_finalize_background_task_not_in_set(self):
        """Discarding a task not in the set should not raise."""
        ch = _make_channel()
        task = MagicMock()
        task.exception.return_value = None
        ch._finalize_background_task(task, "test", "msg_1")
        assert task not in ch._background_tasks


# ---------------------------------------------------------------------------
# _send_card_message — comprehensive branch coverage
# ---------------------------------------------------------------------------


class TestSendCardMessage:
    @pytest.mark.asyncio
    async def test_no_thread_ts_creates_card(self):
        ch = _make_channel()
        msg = _make_outbound(thread_ts=None)
        with patch.object(ch, "_create_card", new_callable=AsyncMock) as mock_create:
            await ch._send_card_message(msg)
            mock_create.assert_called_once_with(msg.chat_id, msg.text)

    @pytest.mark.asyncio
    async def test_with_running_card_updates(self):
        ch = _make_channel()
        ch._running_card_ids["msg_1"] = "card_1"
        msg = _make_outbound(thread_ts="msg_1")
        with patch.object(ch, "_update_card", new_callable=AsyncMock) as mock_update:
            with patch.object(ch, "_add_reaction", new_callable=AsyncMock):
                await ch._send_card_message(msg)
                mock_update.assert_called_once_with("card_1", msg.text)

    @pytest.mark.asyncio
    async def test_final_without_card_replies(self):
        ch = _make_channel()
        msg = _make_outbound(thread_ts="msg_1", is_final=True)
        with patch.object(ch, "_reply_card", new_callable=AsyncMock) as mock_reply:
            with patch.object(ch, "_add_reaction", new_callable=AsyncMock):
                await ch._send_card_message(msg)
                mock_reply.assert_called_once_with("msg_1", msg.text)

    @pytest.mark.asyncio
    async def test_final_clears_running_card(self):
        ch = _make_channel()
        ch._running_card_ids["msg_1"] = "card_1"
        msg = _make_outbound(thread_ts="msg_1", is_final=True)
        with patch.object(ch, "_update_card", new_callable=AsyncMock):
            with patch.object(ch, "_add_reaction", new_callable=AsyncMock):
                await ch._send_card_message(msg)
                assert "msg_1" not in ch._running_card_ids

    @pytest.mark.asyncio
    async def test_final_adds_done_reaction(self):
        ch = _make_channel()
        ch._running_card_ids["msg_1"] = "card_1"
        msg = _make_outbound(thread_ts="msg_1", is_final=True)
        with patch.object(ch, "_update_card", new_callable=AsyncMock):
            with patch.object(ch, "_add_reaction", new_callable=AsyncMock) as mock_reaction:
                await ch._send_card_message(msg)
                mock_reaction.assert_called_once_with("msg_1", "DONE")

    @pytest.mark.asyncio
    async def test_update_fails_non_final_raises(self):
        ch = _make_channel()
        ch._running_card_ids["msg_1"] = "card_1"
        msg = _make_outbound(thread_ts="msg_1", is_final=False)
        with patch.object(ch, "_update_card", new_callable=AsyncMock, side_effect=RuntimeError("fail")):
            with pytest.raises(RuntimeError, match="fail"):
                await ch._send_card_message(msg)

    @pytest.mark.asyncio
    async def test_update_fails_final_fallback(self):
        ch = _make_channel()
        ch._running_card_ids["msg_1"] = "card_1"
        msg = _make_outbound(thread_ts="msg_1", is_final=True)
        with patch.object(ch, "_update_card", new_callable=AsyncMock, side_effect=RuntimeError("fail")):
            with patch.object(ch, "_reply_card", new_callable=AsyncMock) as mock_reply:
                with patch.object(ch, "_add_reaction", new_callable=AsyncMock):
                    await ch._send_card_message(msg)
                    mock_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_final_no_card_no_task_ensures_running(self):
        """Non-final message with no running card or task → _ensure_running_card."""
        ch = _make_channel()
        msg = _make_outbound(thread_ts="msg_1", is_final=False)
        with patch.object(ch, "_ensure_running_card", new_callable=AsyncMock) as mock_ensure:
            await ch._send_card_message(msg)
            mock_ensure.assert_called_once_with("msg_1", msg.text)

    @pytest.mark.asyncio
    async def test_awaited_task_gives_card_id_then_updates(self):
        """When running_card_task is pending and returns a card ID, we update it."""
        ch = _make_channel()
        msg = _make_outbound(thread_ts="msg_1", is_final=False)

        # Simulate a pending task that resolves to a card ID
        async def fake_task():
            return "resolved_card_id"

        ch._running_card_tasks["msg_1"] = asyncio.ensure_future(fake_task())

        with patch.object(ch, "_update_card", new_callable=AsyncMock) as mock_update:
            await ch._send_card_message(msg)
            mock_update.assert_called_once_with("resolved_card_id", msg.text)

    @pytest.mark.asyncio
    async def test_awaited_task_no_id_final_replies(self):
        """When awaited task returns None and message is final → reply_card."""
        ch = _make_channel()
        msg = _make_outbound(thread_ts="msg_1", is_final=True)

        async def fake_task():
            return None

        ch._running_card_tasks["msg_1"] = asyncio.ensure_future(fake_task())

        with patch.object(ch, "_reply_card", new_callable=AsyncMock) as mock_reply:
            with patch.object(ch, "_add_reaction", new_callable=AsyncMock):
                await ch._send_card_message(msg)
                mock_reply.assert_called_once_with("msg_1", msg.text)

    @pytest.mark.asyncio
    async def test_awaited_task_no_id_non_final_logs_warning(self):
        """When awaited task returns None and message is not final → warning log."""
        ch = _make_channel()
        msg = _make_outbound(thread_ts="msg_1", is_final=False)

        async def fake_task():
            return None

        ch._running_card_tasks["msg_1"] = asyncio.ensure_future(fake_task())

        with patch.object(ch, "_update_card", new_callable=AsyncMock):
            with patch.object(ch, "_ensure_running_card", new_callable=AsyncMock) as mock_ensure:
                # The warning path should NOT call ensure_running_card
                await ch._send_card_message(msg)
                mock_ensure.assert_not_called()


# ---------------------------------------------------------------------------
# Static log helpers
# ---------------------------------------------------------------------------


class TestLogHelpers:
    def test_log_future_error_with_exception(self):
        from app.channels.feishu import FeishuChannel

        fut = MagicMock()
        fut.exception.return_value = RuntimeError("test error")
        # Should not raise
        FeishuChannel._log_future_error(fut, "test", "msg_1")

    def test_log_future_error_no_exception(self):
        from app.channels.feishu import FeishuChannel

        fut = MagicMock()
        fut.exception.return_value = None
        FeishuChannel._log_future_error(fut, "test", "msg_1")

    def test_log_future_error_exception_getting_exception(self):
        """When fut.exception() itself raises, should be silently caught."""
        from app.channels.feishu import FeishuChannel

        fut = MagicMock()
        fut.exception.side_effect = RuntimeError("cancelled")
        FeishuChannel._log_future_error(fut, "test", "msg_1")

    def test_log_task_error_with_exception(self):
        from app.channels.feishu import FeishuChannel

        task = MagicMock()
        task.exception.return_value = RuntimeError("test")
        FeishuChannel._log_task_error(task, "test", "msg_1")

    def test_log_task_error_no_exception(self):
        from app.channels.feishu import FeishuChannel

        task = MagicMock()
        task.exception.return_value = None
        FeishuChannel._log_task_error(task, "test", "msg_1")

    def test_log_task_error_cancelled(self):
        from app.channels.feishu import FeishuChannel

        task = MagicMock()
        task.exception.side_effect = asyncio.CancelledError()
        FeishuChannel._log_task_error(task, "test", "msg_1")

    def test_log_task_error_generic_exception(self):
        """When task.exception() raises a non-CancelledError Exception."""
        from app.channels.feishu import FeishuChannel

        task = MagicMock()
        task.exception.side_effect = RuntimeError("unexpected")
        FeishuChannel._log_task_error(task, "test", "msg_1")


# ---------------------------------------------------------------------------
# _prepare_inbound
# ---------------------------------------------------------------------------


class TestPrepareInbound:
    @pytest.mark.asyncio
    async def test_prepare_inbound(self):
        ch = _make_channel()
        inbound = MagicMock()
        inbound.topic_id = "topic_1"

        with patch.object(ch, "_add_reaction", new_callable=AsyncMock):
            with patch.object(ch, "_ensure_running_card_started"):
                with patch.object(ch.bus, "publish_inbound", new_callable=AsyncMock) as mock_pub:
                    await ch._prepare_inbound("msg_1", inbound)
                    mock_pub.assert_called_once_with(inbound)

    @pytest.mark.asyncio
    async def test_prepare_inbound_creates_reaction_task(self):
        ch = _make_channel()
        inbound = MagicMock()

        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task
            with patch.object(ch, "_add_reaction", new_callable=AsyncMock):
                with patch.object(ch, "_ensure_running_card_started"):
                    with patch.object(ch.bus, "publish_inbound", new_callable=AsyncMock):
                        await ch._prepare_inbound("msg_1", inbound)
            mock_create_task.assert_called_once()
            assert mock_task in ch._background_tasks


# ---------------------------------------------------------------------------
# _run_ws
# ---------------------------------------------------------------------------


class TestRunWs:
    def test_run_ws_success(self):
        ch = _make_channel()
        ch._running = True

        mock_lark = MagicMock()
        mock_ws_mod = MagicMock()

        with patch.dict("sys.modules", {"lark_oapi": mock_lark, "lark_oapi.ws.client": mock_ws_mod}):
            ch._run_ws("app_id", "app_secret", "https://open.feishu.cn")
            mock_lark.ws.Client.assert_called_once()
            mock_lark.ws.Client.return_value.start.assert_called_once()

    def test_run_ws_creates_new_event_loop(self):
        """Verify that _run_ws creates a new event loop for the thread."""
        ch = _make_channel()
        ch._running = True

        mock_lark = MagicMock()
        mock_lark.LogLevel.INFO = 1
        captured_loop = None

        original_new_event_loop = asyncio.new_event_loop

        def capture_loop():
            nonlocal captured_loop
            captured_loop = original_new_event_loop()
            return captured_loop

        with patch.dict("sys.modules", {"lark_oapi": mock_lark}):
            with patch("asyncio.new_event_loop", side_effect=capture_loop):
                with patch("asyncio.set_event_loop"):
                    ch._run_ws("app_id", "app_secret", "https://open.feishu.cn")

        # new_event_loop was called
        assert captured_loop is not None
        captured_loop.close()

    def test_run_ws_exception(self):
        ch = _make_channel()
        ch._running = True

        with patch.dict("sys.modules", {"lark_oapi": MagicMock()}):
            with patch("builtins.__import__", side_effect=RuntimeError("ws fail")):
                # Should not raise, just log
                ch._run_ws("app_id", "app_secret", "https://open.feishu.cn")

    def test_run_ws_exception_when_not_running(self):
        ch = _make_channel()
        ch._running = False
        # Should not log the exception
        with patch.dict("sys.modules", {"lark_oapi": MagicMock()}):
            with patch("builtins.__import__", side_effect=RuntimeError("ws fail")):
                ch._run_ws("app_id", "app_secret", "https://open.feishu.cn")


# ---------------------------------------------------------------------------
# _on_message parsing — comprehensive
# ---------------------------------------------------------------------------


class TestOnMessage:
    def test_parse_text_message(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"text": "hello"})
        assert len(published) == 1
        assert published[0].text == "hello"
        assert published[0].msg_type == InboundMessageType.CHAT

    def test_parse_file_message(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"file_key": "file_abc"})
        assert published[0].text == "[file]"
        assert published[0].files == [{"file_key": "file_abc"}]

    def test_parse_image_message(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"image_key": "img_abc"})
        assert published[0].text == "[image]"
        assert published[0].files == [{"image_key": "img_abc"}]

    def test_parse_rich_text_message(self):
        ch = _make_channel()
        content = {
            "content": [
                [
                    {"tag": "text", "text": "hello "},
                    {"tag": "text", "text": "world"},
                ]
            ]
        }
        published = _run_on_message_with_loop(ch, content)
        assert "hello" in published[0].text
        assert "world" in published[0].text

    def test_parse_rich_text_with_image(self):
        ch = _make_channel()
        content = {
            "content": [
                [
                    {"tag": "img", "image_key": "img_rich"},
                ]
            ]
        }
        published = _run_on_message_with_loop(ch, content)
        assert "[image]" in published[0].text
        assert published[0].files == [{"image_key": "img_rich"}]

    def test_empty_message_ignored(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"text": ""})
        assert len(published) == 0

    def test_command_message_type(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"text": "/help"})
        assert published[0].msg_type == InboundMessageType.COMMAND

    def test_root_id_used_as_topic(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"text": "hi"}, root_id="root_1")
        assert published[0].topic_id == "root_1"

    def test_no_root_id_uses_msg_id(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"text": "hi"}, root_id=None)
        assert published[0].topic_id == "msg_1"

    def test_main_loop_not_running(self):
        ch = _make_channel()
        ch._main_loop = None
        event = _make_event({"text": "hi"})
        # Should not raise
        ch._on_message(event)

    def test_main_loop_exists_but_not_running(self):
        ch = _make_channel()
        ch._main_loop = asyncio.new_event_loop()
        ch._running = True
        event = _make_event({"text": "hi"})
        # Should not raise, logs warning
        ch._on_message(event)
        ch._main_loop.close()

    def test_parse_unknown_content(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {})
        assert len(published) == 0

    def test_parse_exception_caught(self):
        ch = _make_channel()
        event = MagicMock()
        event.event.message = None  # Will raise
        # Should not raise
        ch._on_message(event)

    def test_file_key_empty_string(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"file_key": ""})
        # Empty string file_key → text = "", no files → ignored
        assert len(published) == 0

    def test_file_key_not_string(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"file_key": 123})
        # Non-string file_key → text = "", no files → ignored
        assert len(published) == 0

    def test_image_key_empty_string(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"image_key": ""})
        assert len(published) == 0

    def test_image_key_not_string(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"image_key": None})
        assert len(published) == 0

    def test_rich_text_with_at_mention(self):
        ch = _make_channel()
        content = {
            "content": [
                [
                    {"tag": "at", "text": "@user"},
                    {"tag": "text", "text": " hello"},
                ]
            ]
        }
        published = _run_on_message_with_loop(ch, content)
        assert "@user" in published[0].text

    def test_rich_text_with_file(self):
        ch = _make_channel()
        content = {
            "content": [
                [
                    {"tag": "file", "file_key": "fk_123"},
                ]
            ]
        }
        published = _run_on_message_with_loop(ch, content)
        assert "[file]" in published[0].text
        assert published[0].files == [{"file_key": "fk_123"}]

    def test_rich_text_with_media_tag(self):
        ch = _make_channel()
        content = {
            "content": [
                [
                    {"tag": "media", "file_key": "media_123"},
                ]
            ]
        }
        published = _run_on_message_with_loop(ch, content)
        assert "[file]" in published[0].text
        assert published[0].files == [{"file_key": "media_123"}]

    def test_rich_text_empty_paragraph(self):
        ch = _make_channel()
        content = {"content": [[]]}
        published = _run_on_message_with_loop(ch, content)
        # Empty paragraphs → empty text → ignored
        assert len(published) == 0

    def test_rich_text_non_list_paragraph_skipped(self):
        ch = _make_channel()
        content = {"content": ["not a list"]}
        published = _run_on_message_with_loop(ch, content)
        assert len(published) == 0

    def test_rich_text_non_dict_element_skipped(self):
        ch = _make_channel()
        content = {"content": [["string_element", 123]]}
        published = _run_on_message_with_loop(ch, content)
        assert len(published) == 0

    def test_rich_text_unknown_tag_skipped(self):
        ch = _make_channel()
        content = {
            "content": [
                [
                    {"tag": "unknown", "text": "ignored"},
                    {"tag": "text", "text": "visible"},
                ]
            ]
        }
        published = _run_on_message_with_loop(ch, content)
        assert "visible" in published[0].text
        assert "ignored" not in published[0].text

    def test_rich_text_empty_text_skipped(self):
        ch = _make_channel()
        content = {
            "content": [
                [
                    {"tag": "text", "text": ""},
                    {"tag": "text", "text": "visible"},
                ]
            ]
        }
        published = _run_on_message_with_loop(ch, content)
        assert published[0].text == "visible"

    def test_rich_text_img_without_image_key(self):
        ch = _make_channel()
        content = {
            "content": [
                [
                    {"tag": "img"},
                ]
            ]
        }
        published = _run_on_message_with_loop(ch, content)
        # No image_key → not added to files, no [image] placeholder
        assert len(published) == 0

    def test_rich_text_img_empty_image_key(self):
        ch = _make_channel()
        content = {
            "content": [
                [
                    {"tag": "img", "image_key": ""},
                ]
            ]
        }
        published = _run_on_message_with_loop(ch, content)
        assert len(published) == 0

    def test_rich_text_file_without_file_key(self):
        ch = _make_channel()
        content = {
            "content": [
                [
                    {"tag": "file"},
                ]
            ]
        }
        published = _run_on_message_with_loop(ch, content)
        assert len(published) == 0

    def test_rich_text_file_empty_file_key(self):
        ch = _make_channel()
        content = {
            "content": [
                [
                    {"tag": "file", "file_key": ""},
                ]
            ]
        }
        published = _run_on_message_with_loop(ch, content)
        assert len(published) == 0

    def test_rich_text_multiple_paragraphs(self):
        ch = _make_channel()
        content = {
            "content": [
                [{"tag": "text", "text": "paragraph one"}],
                [{"tag": "text", "text": "paragraph two"}],
            ]
        }
        published = _run_on_message_with_loop(ch, content)
        assert "paragraph one" in published[0].text
        assert "paragraph two" in published[0].text
        # Paragraphs joined with double newline
        assert "\n\n" in published[0].text

    def test_rich_text_paragraph_text_parts_joined_with_spaces(self):
        """Text parts within a paragraph are joined with spaces."""
        ch = _make_channel()
        content = {
            "content": [
                [
                    {"tag": "text", "text": "hello"},
                    {"tag": "text", "text": "world"},
                ]
            ]
        }
        published = _run_on_message_with_loop(ch, content)
        assert "hello world" in published[0].text

    def test_on_message_metadata(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"text": "hi"}, msg_id="m123", root_id="r456")
        assert published[0].metadata["message_id"] == "m123"
        assert published[0].metadata["root_id"] == "r456"

    def test_on_message_sender_id(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"text": "hi"}, sender_id="open_id_123")
        assert published[0].user_id == "open_id_123"

    def test_on_message_chat_id(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"text": "hi"}, chat_id="chat_abc")
        assert published[0].chat_id == "chat_abc"

    def test_on_message_thread_ts_is_msg_id(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"text": "hi"}, msg_id="msg_xyz")
        assert published[0].thread_ts == "msg_xyz"

    def test_content_list_at_top_level_not_content_key(self):
        """content without 'content' key but with a list value should not match rich text."""
        ch = _make_channel()
        content = {"other_key": [{"tag": "text", "text": "hi"}]}
        published = _run_on_message_with_loop(ch, content)
        # "other_key" is not "content", so this falls through to the else branch
        assert len(published) == 0


# ---------------------------------------------------------------------------
# _send_running_reply
# ---------------------------------------------------------------------------


class TestSendRunningReply:
    @pytest.mark.asyncio
    async def test_send_running_reply_success(self):
        ch = _make_channel()
        with patch.object(ch, "_ensure_running_card", new_callable=AsyncMock) as mock_ensure:
            await ch._send_running_reply("msg_1")
            mock_ensure.assert_called_once_with("msg_1")

    @pytest.mark.asyncio
    async def test_send_running_reply_exception(self):
        ch = _make_channel()
        with patch.object(ch, "_ensure_running_card", new_callable=AsyncMock, side_effect=RuntimeError("fail")):
            # Should not raise
            await ch._send_running_reply("msg_1")


# ---------------------------------------------------------------------------
# Integration: start() then stop()
# ---------------------------------------------------------------------------


class TestStartStopIntegration:
    @pytest.mark.asyncio
    async def test_start_then_stop(self):
        ch = _make_channel()
        mock_lark = MagicMock()
        mock_lark.LogLevel.INFO = 1

        with patch.dict(
            "sys.modules",
            {
                "lark_oapi": mock_lark,
                "lark_oapi.api": MagicMock(),
                "lark_oapi.api.im": MagicMock(),
                "lark_oapi.api.im.v1": MagicMock(),
            },
        ):
            with patch("threading.Thread") as mock_thread_cls:
                mock_thread = MagicMock()
                mock_thread_cls.return_value = mock_thread
                await ch.start()

        assert ch._running is True

        ch.bus = MagicMock()
        await ch.stop()

        assert ch._running is False
        assert ch._thread is None


# ---------------------------------------------------------------------------
# Edge cases and defensive paths
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_send_file_image_at_exactly_10mb_plus_1(self):
        """Image just over 10MB should be rejected."""
        ch = _make_channel()
        ch._api_client = MagicMock()
        large = _make_attachment(is_image=True, size=10 * 1024 * 1024 + 1)
        result = await ch.send_file(_make_outbound(), large)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_file_file_at_exactly_30mb_plus_1(self):
        """File just over 30MB should be rejected."""
        ch = _make_channel()
        ch._api_client = MagicMock()
        large = _make_attachment(is_image=False, size=30 * 1024 * 1024 + 1)
        result = await ch.send_file(_make_outbound(), large)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_file_zero_size_image(self):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateMessageRequest = MagicMock()
        ch._CreateMessageRequestBody = MagicMock()

        with patch.object(ch, "_upload_image", new_callable=AsyncMock, return_value="img_key"):
            result = await ch.send_file(_make_outbound(thread_ts=None), _make_attachment(is_image=True, size=0))
            assert result is True

    @pytest.mark.asyncio
    async def test_reply_card_response_no_message_id(self):
        """When response.data exists but has no message_id."""
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._ReplyMessageRequest = MagicMock()
        ch._ReplyMessageRequestBody = MagicMock()

        mock_response = MagicMock()
        mock_response.data = SimpleNamespace()  # No message_id attribute
        ch._api_client.im.v1.message.reply.return_value = mock_response

        result = await ch._reply_card("msg_1", "Hello")
        assert result is None

    def test_on_message_whitespace_only_text_ignored(self):
        ch = _make_channel()
        ch._main_loop = None
        event = _make_event({"text": "   "})
        # text.strip() = "" and no files → ignored
        ch._on_message(event)

    def test_on_message_preserves_text_stripping(self):
        ch = _make_channel()
        published = _run_on_message_with_loop(ch, {"text": "  hello  "})
        assert published[0].text == "hello"

    @pytest.mark.asyncio
    async def test_ensure_running_card_started_then_task_completes(self):
        """Test the done callback on running card tasks."""
        ch = _make_channel()

        # Create a real asyncio task
        async def fake_coro():
            return "card_id"

        loop = asyncio.get_event_loop()
        task = loop.create_task(fake_coro())
        ch._running_card_tasks["msg_1"] = task
        task.add_done_callback(lambda done_task, mid="msg_1": ch._finalize_running_card_task(mid, done_task))

        # Wait for task to complete
        await task

        # Task should be removed from tracking
        assert "msg_1" not in ch._running_card_tasks

    @pytest.mark.asyncio
    async def test_track_background_task_callback_removes(self):
        """Test that the done callback on background tasks removes the task."""
        ch = _make_channel()

        async def fake_coro():
            return "done"

        loop = asyncio.get_event_loop()
        task = loop.create_task(fake_coro())
        ch._track_background_task(task, name="test", msg_id="msg_1")

        assert task in ch._background_tasks

        await task

        # Task should be removed
        assert task not in ch._background_tasks

    def test_is_feishu_command_slash_with_only_whitespace(self):
        from app.channels.feishu import _is_feishu_command

        # "/ " → split gives ["/"] → "/" not in commands
        assert _is_feishu_command("/ ") is False

    @pytest.mark.asyncio
    async def test_upload_file_csv_suffix(self, tmp_path):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateFileRequest = MagicMock()
        ch._CreateFileRequestBody = MagicMock()

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.data.file_key = "file_csv"
        ch._api_client.im.v1.file.create.return_value = mock_response

        path = tmp_path / "data.csv"
        path.write_bytes(b"a,b,c")
        result = await ch._upload_file(path, "data.csv")
        assert result == "file_csv"

    @pytest.mark.asyncio
    async def test_upload_file_xlsx_suffix(self, tmp_path):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateFileRequest = MagicMock()
        ch._CreateFileRequestBody = MagicMock()

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.data.file_key = "file_xlsx"
        ch._api_client.im.v1.file.create.return_value = mock_response

        path = tmp_path / "data.xlsx"
        path.write_bytes(b"data")
        result = await ch._upload_file(path, "data.xlsx")
        assert result == "file_xlsx"

    @pytest.mark.asyncio
    async def test_upload_file_doc_suffix(self, tmp_path):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateFileRequest = MagicMock()
        ch._CreateFileRequestBody = MagicMock()

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.data.file_key = "file_doc"
        ch._api_client.im.v1.file.create.return_value = mock_response

        path = tmp_path / "report.doc"
        path.write_bytes(b"data")
        result = await ch._upload_file(path, "report.doc")
        assert result == "file_doc"

    @pytest.mark.asyncio
    async def test_upload_file_ppt_suffix(self, tmp_path):
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._CreateFileRequest = MagicMock()
        ch._CreateFileRequestBody = MagicMock()

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.data.file_key = "file_ppt"
        ch._api_client.im.v1.file.create.return_value = mock_response

        path = tmp_path / "slides.ppt"
        path.write_bytes(b"data")
        result = await ch._upload_file(path, "slides.ppt")
        assert result == "file_ppt"

    @pytest.mark.asyncio
    async def test_receive_single_file_success_default_file_type(self, tmp_path):
        """Default filename for non-image type uses .bin extension."""
        ch = _make_channel()
        ch._api_client = MagicMock()
        ch._GetMessageResourceRequest = MagicMock()

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()

        mock_stream = MagicMock()
        mock_stream.read.return_value = b"data"

        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.file = mock_stream
        # No file_name attribute
        del mock_response.file_name
        ch._api_client.im.v1.message_resource.get.return_value = mock_response

        mock_paths = MagicMock()
        mock_paths.sandbox_uploads_dir.return_value = uploads_dir

        mock_sandbox_provider = MagicMock()
        mock_sandbox_provider.acquire.return_value = "local"

        with (
            patch("app.channels.feishu.get_paths", return_value=mock_paths),
            patch("app.channels.feishu.get_effective_user_id", return_value="user_1"),
            patch("app.channels.feishu.get_sandbox_provider", return_value=mock_sandbox_provider),
        ):
            result = await ch._receive_single_file("msg_1", "abc123def456", "file", "thread_1")

        assert "/mnt/user-data/uploads/" in result
        assert ".bin" in result

    @pytest.mark.asyncio
    async def test_receive_file_thread_ts_set(self):
        """Verify thread_ts is passed correctly to _receive_single_file."""
        ch = _make_channel()
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="[image]",
            thread_ts="msg_thread_ts",
            files=[{"image_key": "img_123"}],
        )

        with patch.object(ch, "_receive_single_file", new_callable=AsyncMock, return_value="/path") as mock_receive:
            await ch.receive_file(msg, "tid")
            mock_receive.assert_called_once_with("msg_thread_ts", "img_123", "image", "tid")

    @pytest.mark.asyncio
    async def test_send_uses_exponential_backoff_delays(self):
        """Verify the delay values are 2^attempt."""
        ch = _make_channel()
        ch._api_client = MagicMock()

        attempt_count = 0

        async def failing_send(msg):
            nonlocal attempt_count
            attempt_count += 1
            raise RuntimeError(f"fail {attempt_count}")

        with patch.object(ch, "_send_card_message", side_effect=failing_send):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                with pytest.raises(RuntimeError):
                    await ch.send(_make_outbound(), _max_retries=3)

                # Should have slept with delays 1, 2 (2^0, 2^1)
                assert mock_sleep.call_count == 2
                mock_sleep.assert_any_call(1)
                mock_sleep.assert_any_call(2)
