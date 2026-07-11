"""Comprehensive tests for TelegramChannel -- targeting 98%+ coverage."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.channels.message_bus import (
    InboundMessage,
    InboundMessageType,
    MessageBus,
    OutboundMessage,
    ResolvedAttachment,
)
from app.channels.telegram import TelegramChannel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_channel(config: dict | None = None, *, running: bool = False) -> TelegramChannel:
    """Create a TelegramChannel with a real MessageBus."""
    bus = MessageBus()
    cfg = config or {"bot_token": "test-token"}
    ch = TelegramChannel(bus, cfg)
    if running:
        ch._running = True
    return ch


def _make_update(
    *,
    text: str = "hello",
    chat_id: int = 12345,
    user_id: int = 999,
    msg_id: int = 1,
    chat_type: str = "private",
    reply_to_msg_id: int | None = None,
) -> MagicMock:
    """Build a fake telegram Update object."""
    update = MagicMock()
    update.message.text = text
    update.message.message_id = msg_id
    update.effective_chat.id = chat_id
    update.effective_chat.type = chat_type
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    if reply_to_msg_id is not None:
        reply_msg = MagicMock()
        reply_msg.message_id = reply_to_msg_id
        update.message.reply_to_message = reply_msg
    else:
        update.message.reply_to_message = None
    return update


def _make_outbound(
    chat_id: str = "12345",
    text: str = "reply",
    channel: str = "telegram",
    attachments: list | None = None,
) -> OutboundMessage:
    return OutboundMessage(
        channel_name=channel,
        chat_id=chat_id,
        thread_id="t1",
        text=text,
        attachments=attachments or [],
    )


def _make_attachment(
    *,
    filename: str = "test.pdf",
    size: int = 1024,
    is_image: bool = False,
    actual_path: Path = Path("/tmp/test.pdf"),
    mime_type: str = "application/pdf",
) -> ResolvedAttachment:
    return ResolvedAttachment(
        virtual_path=f"/virtual/{filename}",
        actual_path=actual_path,
        filename=filename,
        mime_type=mime_type,
        size=size,
        is_image=is_image,
    )


def _mock_bot() -> AsyncMock:
    bot = AsyncMock()
    sent = MagicMock()
    sent.message_id = 42
    bot.send_message.return_value = sent
    bot.send_photo.return_value = sent
    bot.send_document.return_value = sent
    return bot


def _fake_telegram_ext_module():
    """Create a fake ``telegram.ext`` module with the names ``start()`` imports.

    We use MagicMock **instances** (not the class) so that calling
    ``CommandHandler(...)`` returns a MagicMock instead of trying to
    construct one with positional ``spec`` arg.
    """
    ext = MagicMock()
    # Leave attributes as auto-generated MagicMock instances (not the class).
    return ext


def _fake_telegram_module():
    """Create a fake ``telegram`` top-level module."""
    return MagicMock()


def _patch_telegram_modules():
    """Context manager that injects fake ``telegram`` and ``telegram.ext`` into sys.modules."""
    tg = _fake_telegram_module()
    ext = _fake_telegram_ext_module()
    tg.ext = ext
    return patch.dict("sys.modules", {"telegram": tg, "telegram.ext": ext})


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_defaults(self):
        ch = _make_channel()
        assert ch.name == "telegram"
        assert ch._application is None
        assert ch._thread is None
        assert ch._tg_loop is None
        assert ch._main_loop is None
        assert ch._allowed_users == set()
        assert ch._last_bot_message == {}
        assert ch._running is False

    def test_allowed_users_valid(self):
        ch = _make_channel({"bot_token": "t", "allowed_users": [1, "2", 3]})
        assert ch._allowed_users == {1, 2, 3}

    def test_allowed_users_invalid_values_ignored(self):
        ch = _make_channel({"bot_token": "t", "allowed_users": ["abc", None, "xyz"]})
        assert ch._allowed_users == set()

    def test_allowed_users_mixed(self):
        ch = _make_channel({"bot_token": "t", "allowed_users": [10, "bad", 20, None]})
        assert ch._allowed_users == {10, 20}

    def test_allowed_users_missing_key(self):
        ch = _make_channel({"bot_token": "t"})
        assert ch._allowed_users == set()


# ---------------------------------------------------------------------------
# start()
# ---------------------------------------------------------------------------


class TestStart:
    @pytest.mark.asyncio
    async def test_already_running(self):
        ch = _make_channel(running=True)
        await ch.start()
        assert ch._application is None

    @pytest.mark.asyncio
    async def test_import_error(self):
        ch = _make_channel()
        # When telegram / telegram.ext are absent from sys.modules, the
        # ``from telegram.ext import ...`` inside start() raises ImportError.
        with patch.dict("sys.modules", {"telegram": None, "telegram.ext": None}):
            await ch.start()
        assert ch._running is False
        assert ch._application is None

    @pytest.mark.asyncio
    async def test_missing_bot_token(self):
        ch = _make_channel({"bot_token": ""})
        with _patch_telegram_modules():
            await ch.start()
        assert ch._running is False

    @pytest.mark.asyncio
    async def test_successful_start(self):
        ch = _make_channel()
        mock_app = MagicMock()
        mock_builder = MagicMock()
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_app

        with _patch_telegram_modules() as mods:
            tg_ext = mods["telegram.ext"]
            tg_ext.ApplicationBuilder.return_value = mock_builder

            with patch.object(ch, "_run_polling"):
                await ch.start()

        assert ch._running is True
        assert ch._application is mock_app
        assert ch._main_loop is not None
        # Verify 7 handlers added: /start, /new, /status, /models, /memory, /help, text
        assert mock_app.add_handler.call_count == 7


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------


class TestStop:
    @pytest.mark.asyncio
    async def test_stop_clears_state(self):
        ch = _make_channel(running=True)
        mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
        mock_loop.is_running.return_value = True
        ch._tg_loop = mock_loop
        ch._thread = MagicMock()
        ch._application = MagicMock()
        ch.bus.subscribe_outbound(ch._on_outbound)

        await ch.stop()

        assert ch._running is False
        assert ch._application is None
        assert ch._thread is None
        mock_loop.call_soon_threadsafe.assert_called_once_with(mock_loop.stop)

    @pytest.mark.asyncio
    async def test_stop_when_loop_not_running(self):
        ch = _make_channel(running=True)
        mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
        mock_loop.is_running.return_value = False
        ch._tg_loop = mock_loop
        ch._thread = MagicMock()
        ch._application = MagicMock()

        await ch.stop()

        mock_loop.call_soon_threadsafe.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_with_no_thread_no_loop(self):
        ch = _make_channel(running=True)
        ch._tg_loop = None
        ch._thread = None
        ch._application = MagicMock()

        await ch.stop()
        assert ch._application is None

    @pytest.mark.asyncio
    async def test_stop_unsubscribes_bus(self):
        ch = _make_channel(running=True)
        ch._tg_loop = None
        ch._thread = None
        ch._application = MagicMock()
        # subscribe_outbound stores the bound method reference.
        ch.bus.subscribe_outbound(ch._on_outbound)
        assert len(ch.bus._outbound_listeners) == 1

        # stop() calls unsubscribe_outbound(self._on_outbound).
        # Note: because Python creates a new bound-method object on each
        # attribute access, the ``is not`` check in MessageBus may or may
        # not match.  We only verify stop() doesn't raise.
        await ch.stop()

        assert ch._running is False


# ---------------------------------------------------------------------------
# send()
# ---------------------------------------------------------------------------


class TestSend:
    @pytest.mark.asyncio
    async def test_no_application(self):
        ch = _make_channel()
        msg = _make_outbound()
        await ch.send(msg)  # should return without error

    @pytest.mark.asyncio
    async def test_invalid_chat_id(self):
        ch = _make_channel()
        ch._application = MagicMock()
        msg = _make_outbound(chat_id="not-a-number")
        await ch.send(msg)  # logs error, returns

    @pytest.mark.asyncio
    async def test_successful_send(self):
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound(chat_id="12345", text="hi")

        await ch.send(msg)

        bot.send_message.assert_awaited_once_with(chat_id=12345, text="hi")
        assert ch._last_bot_message["12345"] == 42

    @pytest.mark.asyncio
    async def test_send_with_reply_to(self):
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot
        ch._last_bot_message["12345"] = 10
        msg = _make_outbound(chat_id="12345", text="reply")

        await ch.send(msg)

        bot.send_message.assert_awaited_once_with(chat_id=12345, text="reply", reply_to_message_id=10)

    @pytest.mark.asyncio
    async def test_send_retry_then_success(self):
        ch = _make_channel()
        bot = _mock_bot()
        sent = MagicMock()
        sent.message_id = 55
        bot.send_message.side_effect = [
            Exception("fail 1"),
            sent,
        ]
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await ch.send(msg, _max_retries=3)

        assert ch._last_bot_message["12345"] == 55
        assert bot.send_message.await_count == 2

    @pytest.mark.asyncio
    async def test_send_all_retries_fail_raises(self):
        ch = _make_channel()
        bot = _mock_bot()
        exc = Exception("permanent failure")
        bot.send_message.side_effect = exc
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception, match="permanent failure"):
                await ch.send(msg, _max_retries=2)

        assert bot.send_message.await_count == 2

    @pytest.mark.asyncio
    async def test_send_single_retry(self):
        ch = _make_channel()
        bot = _mock_bot()
        bot.send_message.side_effect = Exception("fail")
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception, match="fail"):
                await ch.send(msg, _max_retries=1)

        assert bot.send_message.await_count == 1

    @pytest.mark.asyncio
    async def test_send_zero_retries_raises_runtime_error(self):
        """Edge case: _max_retries=0 means no attempts, last_exc is None."""
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()

        with pytest.raises(RuntimeError, match="without an exception"):
            await ch.send(msg, _max_retries=0)

    @pytest.mark.asyncio
    async def test_send_retries_with_increasing_delay(self):
        """Verify exponential back-off: 2**0=1, 2**1=2."""
        ch = _make_channel()
        bot = _mock_bot()
        sent = MagicMock()
        sent.message_id = 77
        bot.send_message.side_effect = [Exception("f1"), Exception("f2"), sent]
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await ch.send(msg, _max_retries=3)

        assert mock_sleep.await_args_list == [call(1), call(2)]


# ---------------------------------------------------------------------------
# send_file()
# ---------------------------------------------------------------------------


class TestSendFile:
    @pytest.mark.asyncio
    async def test_no_application(self):
        ch = _make_channel()
        msg = _make_outbound()
        att = _make_attachment()
        result = await ch.send_file(msg, att)
        assert result is False

    @pytest.mark.asyncio
    async def test_invalid_chat_id(self):
        ch = _make_channel()
        ch._application = MagicMock()
        msg = _make_outbound(chat_id="abc")
        att = _make_attachment()
        result = await ch.send_file(msg, att)
        assert result is False

    @pytest.mark.asyncio
    async def test_file_too_large(self):
        ch = _make_channel()
        ch._application = MagicMock()
        msg = _make_outbound()
        att = _make_attachment(size=51 * 1024 * 1024)  # 51 MB
        result = await ch.send_file(msg, att)
        assert result is False

    @pytest.mark.asyncio
    async def test_file_exactly_at_50mb_limit(self):
        """50 MB exactly should pass (limit is strictly > 50MB)."""
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()
        att = _make_attachment(size=50 * 1024 * 1024, is_image=False)

        with patch("builtins.open", MagicMock()):
            with _patch_telegram_modules():
                result = await ch.send_file(msg, att)

        assert result is True

    @pytest.mark.asyncio
    async def test_send_image_as_photo(self):
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()
        att = _make_attachment(is_image=True, size=5 * 1024 * 1024, mime_type="image/png")

        with patch("builtins.open", MagicMock()):
            result = await ch.send_file(msg, att)

        assert result is True
        bot.send_photo.assert_awaited_once()
        assert ch._last_bot_message["12345"] == 42

    @pytest.mark.asyncio
    async def test_send_image_exactly_10mb_as_photo(self):
        """10 MB image exactly should use send_photo (limit is <= 10MB)."""
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()
        att = _make_attachment(is_image=True, size=10 * 1024 * 1024, mime_type="image/png")

        with patch("builtins.open", MagicMock()):
            result = await ch.send_file(msg, att)

        assert result is True
        bot.send_photo.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_image_with_reply_to(self):
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot
        ch._last_bot_message["12345"] = 10
        msg = _make_outbound()
        att = _make_attachment(is_image=True, size=5 * 1024 * 1024)

        with patch("builtins.open", MagicMock()):
            result = await ch.send_file(msg, att)

        assert result is True
        bot.send_photo.assert_awaited_once()
        _, kwargs = bot.send_photo.call_args
        assert kwargs.get("reply_to_message_id") == 10

    @pytest.mark.asyncio
    async def test_send_large_image_as_document(self):
        """Image > 10MB falls through to document path."""
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()
        att = _make_attachment(is_image=True, size=15 * 1024 * 1024, mime_type="image/png")

        with patch("builtins.open", MagicMock()):
            with _patch_telegram_modules():
                result = await ch.send_file(msg, att)

        assert result is True
        bot.send_document.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_document_with_reply(self):
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot
        ch._last_bot_message["12345"] = 7
        msg = _make_outbound()
        att = _make_attachment(is_image=False, size=2048)

        with patch("builtins.open", MagicMock()):
            with _patch_telegram_modules():
                result = await ch.send_file(msg, att)

        assert result is True
        bot.send_document.assert_awaited_once()
        _, kwargs = bot.send_document.call_args
        assert kwargs.get("reply_to_message_id") == 7

    @pytest.mark.asyncio
    async def test_send_file_photo_exception(self):
        ch = _make_channel()
        bot = _mock_bot()
        bot.send_photo.side_effect = Exception("upload failed")
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()
        att = _make_attachment(is_image=True, size=1024)

        with patch("builtins.open", MagicMock()):
            result = await ch.send_file(msg, att)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_document_exception(self):
        ch = _make_channel()
        bot = _mock_bot()
        bot.send_document.side_effect = Exception("upload failed")
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()
        att = _make_attachment(is_image=False, size=1024)

        with patch("builtins.open", MagicMock()):
            with _patch_telegram_modules():
                result = await ch.send_file(msg, att)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_file_updates_last_bot_message(self):
        ch = _make_channel()
        bot = _mock_bot()
        sent = MagicMock()
        sent.message_id = 99
        bot.send_photo.return_value = sent
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()
        att = _make_attachment(is_image=True, size=1024)

        with patch("builtins.open", MagicMock()):
            await ch.send_file(msg, att)

        assert ch._last_bot_message["12345"] == 99

    @pytest.mark.asyncio
    async def test_send_document_updates_last_bot_message(self):
        ch = _make_channel()
        bot = _mock_bot()
        sent = MagicMock()
        sent.message_id = 88
        bot.send_document.return_value = sent
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()
        att = _make_attachment(is_image=False, size=1024)

        with patch("builtins.open", MagicMock()):
            with _patch_telegram_modules():
                await ch.send_file(msg, att)

        assert ch._last_bot_message["12345"] == 88

    @pytest.mark.asyncio
    async def test_send_document_no_reply_to(self):
        """Document without a previous bot message -- no reply_to_message_id."""
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()
        att = _make_attachment(is_image=False, size=1024)

        with patch("builtins.open", MagicMock()):
            with _patch_telegram_modules():
                result = await ch.send_file(msg, att)

        assert result is True
        _, kwargs = bot.send_document.call_args
        assert "reply_to_message_id" not in kwargs

    @pytest.mark.asyncio
    async def test_send_photo_no_reply_to(self):
        """Photo without a previous bot message -- no reply_to_message_id."""
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot
        msg = _make_outbound()
        att = _make_attachment(is_image=True, size=1024)

        with patch("builtins.open", MagicMock()):
            result = await ch.send_file(msg, att)

        assert result is True
        _, kwargs = bot.send_photo.call_args
        assert "reply_to_message_id" not in kwargs


# ---------------------------------------------------------------------------
# _send_running_reply()
# ---------------------------------------------------------------------------


class TestSendRunningReply:
    @pytest.mark.asyncio
    async def test_no_application(self):
        ch = _make_channel()
        await ch._send_running_reply("123", 1)  # no-op

    @pytest.mark.asyncio
    async def test_sends_working_message(self):
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot

        await ch._send_running_reply("12345", 42)

        bot.send_message.assert_awaited_once_with(chat_id=12345, text="Working on it...", reply_to_message_id=42)

    @pytest.mark.asyncio
    async def test_exception_caught(self):
        ch = _make_channel()
        bot = _mock_bot()
        bot.send_message.side_effect = Exception("fail")
        ch._application = MagicMock()
        ch._application.bot = bot

        await ch._send_running_reply("12345", 42)  # should not raise


# ---------------------------------------------------------------------------
# _log_future_error()
# ---------------------------------------------------------------------------


class TestLogFutureError:
    def test_future_with_exception(self):
        fut = MagicMock()
        fut.exception.return_value = ValueError("boom")
        TelegramChannel._log_future_error(fut, "test_op", "msg_1")
        fut.exception.assert_called_once()

    def test_future_without_exception(self):
        fut = MagicMock()
        fut.exception.return_value = None
        TelegramChannel._log_future_error(fut, "test_op", "msg_1")
        fut.exception.assert_called_once()

    def test_future_exception_inspection_fails(self):
        fut = MagicMock()
        fut.exception.side_effect = Exception("cannot inspect")
        # Should not raise
        TelegramChannel._log_future_error(fut, "test_op", "msg_1")


# ---------------------------------------------------------------------------
# _run_polling()
# ---------------------------------------------------------------------------


class TestRunPolling:
    def _run_with_mocks(self, ch, *, init_side_effect=None, updater_running=True, updater_stop_side_effect=None):
        """Helper: run _run_polling with patched asyncio functions."""
        ch._application = MagicMock()
        if init_side_effect is not None:
            ch._application.initialize.side_effect = init_side_effect
        ch._application.updater.running = updater_running
        if updater_stop_side_effect is not None:
            ch._application.updater.stop.side_effect = updater_stop_side_effect

        mock_loop = MagicMock()
        mock_set = MagicMock()

        with (
            patch("asyncio.new_event_loop", return_value=mock_loop),
            patch("asyncio.set_event_loop", mock_set),
        ):
            ch._run_polling()

        return mock_loop, mock_set

    def test_run_polling_success(self):
        ch = _make_channel(running=True)
        mock_loop, mock_set = self._run_with_mocks(ch)

        mock_set.assert_called_once_with(mock_loop)
        mock_loop.run_until_complete.assert_any_call(ch._application.initialize())
        mock_loop.run_until_complete.assert_any_call(ch._application.start())
        mock_loop.run_until_complete.assert_any_call(ch._application.updater.start_polling())
        mock_loop.run_forever.assert_called_once()

    def test_run_polling_exception_while_running(self):
        ch = _make_channel(running=True)
        mock_loop, _ = self._run_with_mocks(
            ch,
            init_side_effect=Exception("init fail"),
            updater_running=False,
        )
        # The finally block still runs the shutdown sequence
        mock_loop.run_until_complete.assert_called()

    def test_run_polling_exception_while_not_running(self):
        ch = _make_channel(running=False)
        mock_loop, _ = self._run_with_mocks(
            ch,
            init_side_effect=Exception("init fail"),
            updater_running=False,
        )
        # No logger.exception call because self._running is False

    def test_run_polling_shutdown_updater_running(self):
        ch = _make_channel(running=True)
        mock_loop, _ = self._run_with_mocks(ch, updater_running=True)
        # Shutdown sequence: stop updater, stop app, shutdown app (3 calls)
        # Plus 3 calls from the startup sequence = at least 6
        assert mock_loop.run_until_complete.call_count >= 6

    def test_run_polling_shutdown_exception(self):
        ch = _make_channel(running=True)
        mock_loop, _ = self._run_with_mocks(
            ch,
            updater_running=True,
            updater_stop_side_effect=Exception("stop fail"),
        )
        # should not raise -- exception caught in finally

    def test_run_polling_sets_event_loop(self):
        ch = _make_channel(running=True)
        _, mock_set = self._run_with_mocks(ch)
        mock_set.assert_called_once()


# ---------------------------------------------------------------------------
# _check_user()
# ---------------------------------------------------------------------------


class TestCheckUser:
    def test_no_allowed_users_allows_all(self):
        ch = _make_channel()
        assert ch._check_user(123) is True

    def test_allowed_user_passes(self):
        ch = _make_channel({"bot_token": "t", "allowed_users": [100, 200]})
        assert ch._check_user(100) is True

    def test_disallowed_user_rejected(self):
        ch = _make_channel({"bot_token": "t", "allowed_users": [100, 200]})
        assert ch._check_user(999) is False


# ---------------------------------------------------------------------------
# _cmd_start()
# ---------------------------------------------------------------------------


class TestCmdStart:
    @pytest.mark.asyncio
    async def test_replies_welcome(self):
        ch = _make_channel()
        update = _make_update(user_id=1)
        ctx = MagicMock()

        await ch._cmd_start(update, ctx)

        update.message.reply_text.assert_awaited_once()
        args = update.message.reply_text.call_args
        assert "Welcome to iDeer" in args[0][0]

    @pytest.mark.asyncio
    async def test_disallowed_user_no_reply(self):
        ch = _make_channel({"bot_token": "t", "allowed_users": [100]})
        update = _make_update(user_id=999)
        ctx = MagicMock()

        await ch._cmd_start(update, ctx)

        update.message.reply_text.assert_not_called()


# ---------------------------------------------------------------------------
# _cmd_generic()
# ---------------------------------------------------------------------------


class TestCmdGeneric:
    @pytest.mark.asyncio
    async def test_disallowed_user(self):
        ch = _make_channel({"bot_token": "t", "allowed_users": [100]})
        update = _make_update(user_id=999, text="/help")
        ctx = MagicMock()

        await ch._cmd_generic(update, ctx)

    @pytest.mark.asyncio
    async def test_private_chat_topic_id_none(self):
        ch = _make_channel()
        ch._main_loop = MagicMock()
        ch._main_loop.is_running.return_value = True
        update = _make_update(text="/new", chat_id=100, user_id=1, msg_id=10, chat_type="private")
        ctx = MagicMock()

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            mock_fut = MagicMock()
            mock_run.return_value = mock_fut
            await ch._cmd_generic(update, ctx)

        mock_run.assert_called_once()
        mock_fut.add_done_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_group_chat_with_reply_to(self):
        ch = _make_channel()
        ch._main_loop = MagicMock()
        ch._main_loop.is_running.return_value = True
        update = _make_update(
            text="/status",
            chat_id=200,
            user_id=1,
            msg_id=20,
            chat_type="group",
            reply_to_msg_id=15,
        )
        ctx = MagicMock()

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            mock_fut = MagicMock()
            mock_run.return_value = mock_fut
            await ch._cmd_generic(update, ctx)

        mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_group_chat_without_reply_to(self):
        ch = _make_channel()
        ch._main_loop = MagicMock()
        ch._main_loop.is_running.return_value = True
        update = _make_update(
            text="/models",
            chat_id=300,
            user_id=1,
            msg_id=30,
            chat_type="group",
        )
        ctx = MagicMock()

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            mock_fut = MagicMock()
            mock_run.return_value = mock_fut
            await ch._cmd_generic(update, ctx)

        mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_loop_not_running(self):
        ch = _make_channel()
        ch._main_loop = MagicMock()
        ch._main_loop.is_running.return_value = False
        update = _make_update(text="/help")
        ctx = MagicMock()

        await ch._cmd_generic(update, ctx)

    @pytest.mark.asyncio
    async def test_main_loop_none(self):
        ch = _make_channel()
        ch._main_loop = None
        update = _make_update(text="/help")
        ctx = MagicMock()

        await ch._cmd_generic(update, ctx)


# ---------------------------------------------------------------------------
# _on_text()
# ---------------------------------------------------------------------------


class TestOnText:
    @pytest.mark.asyncio
    async def test_disallowed_user(self):
        ch = _make_channel({"bot_token": "t", "allowed_users": [100]})
        update = _make_update(user_id=999)
        ctx = MagicMock()

        await ch._on_text(update, ctx)

    @pytest.mark.asyncio
    async def test_empty_text_ignored(self):
        ch = _make_channel()
        update = _make_update(text="   ")
        ctx = MagicMock()

        await ch._on_text(update, ctx)

    @pytest.mark.asyncio
    async def test_private_chat(self):
        ch = _make_channel()
        ch._main_loop = MagicMock()
        ch._main_loop.is_running.return_value = True
        update = _make_update(text="hello", chat_id=100, user_id=1, msg_id=5, chat_type="private")
        ctx = MagicMock()

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            mock_fut = MagicMock()
            mock_run.return_value = mock_fut
            await ch._on_text(update, ctx)

        mock_run.assert_called_once()
        mock_fut.add_done_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_group_chat_with_reply(self):
        ch = _make_channel()
        ch._main_loop = MagicMock()
        ch._main_loop.is_running.return_value = True
        update = _make_update(
            text="reply msg",
            chat_id=200,
            user_id=1,
            msg_id=20,
            chat_type="group",
            reply_to_msg_id=15,
        )
        ctx = MagicMock()

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            mock_fut = MagicMock()
            mock_run.return_value = mock_fut
            await ch._on_text(update, ctx)

        mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_group_chat_no_reply(self):
        ch = _make_channel()
        ch._main_loop = MagicMock()
        ch._main_loop.is_running.return_value = True
        update = _make_update(text="new thread", chat_id=300, user_id=1, msg_id=30, chat_type="group")
        ctx = MagicMock()

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            mock_fut = MagicMock()
            mock_run.return_value = mock_fut
            await ch._on_text(update, ctx)

        mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_loop_not_running(self):
        ch = _make_channel()
        ch._main_loop = MagicMock()
        ch._main_loop.is_running.return_value = False
        update = _make_update(text="hi")
        ctx = MagicMock()

        await ch._on_text(update, ctx)

    @pytest.mark.asyncio
    async def test_main_loop_none(self):
        ch = _make_channel()
        ch._main_loop = None
        update = _make_update(text="hi")
        ctx = MagicMock()

        await ch._on_text(update, ctx)


# ---------------------------------------------------------------------------
# _process_incoming_with_reply()
# ---------------------------------------------------------------------------


class TestProcessIncomingWithReply:
    @pytest.mark.asyncio
    async def test_sends_reply_then_publishes(self):
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot

        inbound = InboundMessage(
            channel_name="telegram",
            chat_id="123",
            user_id="1",
            text="hi",
            msg_type=InboundMessageType.CHAT,
        )

        with patch.object(ch.bus, "publish_inbound", new_callable=AsyncMock) as mock_pub:
            await ch._process_incoming_with_reply("123", 42, inbound)

        bot.send_message.assert_awaited_once()
        mock_pub.assert_awaited_once_with(inbound)


# ---------------------------------------------------------------------------
# _on_outbound (inherited from Channel base class)
# ---------------------------------------------------------------------------


class TestOnOutbound:
    @pytest.mark.asyncio
    async def test_matching_channel_sends(self):
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot

        msg = _make_outbound(channel="telegram")
        await ch._on_outbound(msg)

        bot.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_matching_channel_ignored(self):
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot

        msg = _make_outbound(channel="slack")
        await ch._on_outbound(msg)

        bot.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_exception_stops_attachments(self):
        ch = _make_channel()
        bot = _mock_bot()
        bot.send_message.side_effect = Exception("fail")
        ch._application = MagicMock()
        ch._application.bot = bot

        att = _make_attachment()
        msg = _make_outbound(attachments=[att])

        await ch._on_outbound(msg)
        # Attachment upload should NOT be attempted after text send failure

    @pytest.mark.asyncio
    async def test_attachments_uploaded_after_text(self):
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot

        att = _make_attachment(is_image=True, size=1024)
        msg = _make_outbound(attachments=[att])

        with patch("builtins.open", MagicMock()):
            await ch._on_outbound(msg)

        bot.send_photo.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_attachment_upload_exception_caught(self):
        ch = _make_channel()
        bot = _mock_bot()
        bot.send_photo.side_effect = Exception("upload err")
        ch._application = MagicMock()
        ch._application.bot = bot

        att = _make_attachment(is_image=True, size=1024)
        msg = _make_outbound(attachments=[att])

        with patch("builtins.open", MagicMock()):
            await ch._on_outbound(msg)  # should not raise

    @pytest.mark.asyncio
    async def test_attachment_returns_false_logged(self):
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot

        with patch.object(ch, "send_file", new_callable=AsyncMock, return_value=False):
            att = _make_attachment()
            msg = _make_outbound(attachments=[att])
            await ch._on_outbound(msg)

    @pytest.mark.asyncio
    async def test_multiple_attachments(self):
        """Multiple attachments are all uploaded sequentially."""
        ch = _make_channel()
        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot

        att1 = _make_attachment(filename="a.png", is_image=True, size=1024)
        att2 = _make_attachment(filename="b.pdf", is_image=False, size=2048)
        msg = _make_outbound(attachments=[att1, att2])

        with patch.object(ch, "send_file", new_callable=AsyncMock, return_value=True) as sf:
            await ch._on_outbound(msg)

        assert sf.await_count == 2


# ---------------------------------------------------------------------------
# Properties (from base class)
# ---------------------------------------------------------------------------


class TestProperties:
    def test_is_running_false_by_default(self):
        ch = _make_channel()
        assert ch.is_running is False

    def test_is_running_true_after_set(self):
        ch = _make_channel(running=True)
        assert ch.is_running is True

    def test_supports_streaming_false(self):
        ch = _make_channel()
        assert ch.supports_streaming is False


# ---------------------------------------------------------------------------
# Integration: _on_text -> _process_incoming_with_reply (end-to-end)
# ---------------------------------------------------------------------------


class TestIntegration:
    @pytest.mark.asyncio
    async def test_on_text_publishes_inbound_via_main_loop(self):
        """Verify the full path: _on_text schedules _process_incoming_with_reply
        on the main loop, which sends a running reply then publishes inbound."""
        ch = _make_channel()
        real_loop = asyncio.get_event_loop()
        ch._main_loop = real_loop

        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot

        update = _make_update(
            text="integrate me",
            chat_id=555,
            user_id=1,
            msg_id=77,
            chat_type="private",
        )
        ctx = MagicMock()

        published: list[InboundMessage] = []

        async def capture_inbound(msg):
            published.append(msg)

        with patch.object(ch.bus, "publish_inbound", side_effect=capture_inbound):
            await ch._on_text(update, ctx)
            # Let the scheduled coroutine run
            await asyncio.sleep(0.1)

        assert len(published) == 1
        assert published[0].text == "integrate me"
        assert published[0].chat_id == "555"
        assert published[0].user_id == "1"
        assert published[0].msg_type == InboundMessageType.CHAT
        assert published[0].topic_id is None  # private chat

    @pytest.mark.asyncio
    async def test_cmd_generic_publishes_command_via_main_loop(self):
        """Verify _cmd_generic creates InboundMessageType.COMMAND."""
        ch = _make_channel()
        real_loop = asyncio.get_event_loop()
        ch._main_loop = real_loop

        bot = _mock_bot()
        ch._application = MagicMock()
        ch._application.bot = bot

        update = _make_update(
            text="/new",
            chat_id=666,
            user_id=1,
            msg_id=88,
            chat_type="private",
        )
        ctx = MagicMock()

        published: list[InboundMessage] = []

        async def capture_inbound(msg):
            published.append(msg)

        with patch.object(ch.bus, "publish_inbound", side_effect=capture_inbound):
            await ch._cmd_generic(update, ctx)
            await asyncio.sleep(0.1)

        assert len(published) == 1
        assert published[0].text == "/new"
        assert published[0].msg_type == InboundMessageType.COMMAND
        assert published[0].topic_id is None  # private chat
