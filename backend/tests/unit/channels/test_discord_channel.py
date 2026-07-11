"""Comprehensive tests for app.channels.discord — DiscordChannel.

Targets 98%+ branch coverage of every method in the module (375 statements).
Mocks the discord module completely so tests run without discord.py installed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.channels.discord import DiscordChannel
from app.channels.message_bus import (
    InboundMessageType,
    MessageBus,
    OutboundMessage,
    ResolvedAttachment,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    """Run an async coroutine in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_bus() -> MessageBus:
    return MessageBus()


def _make_channel(bus=None, config=None):
    """Create a DiscordChannel with sensible defaults."""
    bus = bus or _make_bus()
    config = config or {"bot_token": "test-token"}
    return DiscordChannel(bus, config)


def _make_outbound(**overrides):
    defaults = {
        "channel_name": "discord",
        "chat_id": "100001",
        "thread_id": "thread_1",
        "text": "Hello from bot",
        "thread_ts": None,
        "is_final": True,
    }
    defaults.update(overrides)
    return OutboundMessage(**defaults)


def _mock_rcts_and_wf():
    """Return a context manager that patches asyncio.run_coroutine_threadsafe and wrap_future."""
    loop = asyncio.new_event_loop()

    def _resolved_future(*args, **kwargs):
        f = loop.create_future()
        f.set_result(None)
        return f

    return (
        patch("asyncio.run_coroutine_threadsafe", return_value=MagicMock()),
        patch("asyncio.wrap_future", side_effect=_resolved_future),
    )


def _make_attachment(**overrides):
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


def _make_mock_message(
    content="hello bot",
    author_id="user1",
    author_bot=False,
    guild_id=None,
    channel_id="200001",
    message_id="msg_001",
    author_display_name="TestUser",
    channel_type=None,
):
    """Build a mock discord message object."""
    msg = MagicMock()
    msg.content = content
    msg.id = message_id
    msg.author.id = author_id
    msg.author.bot = author_bot
    msg.author.display_name = author_display_name
    msg.channel.id = channel_id
    msg.channel.type = channel_type
    msg.guild = None

    if guild_id is not None:
        msg.guild = MagicMock()
        msg.guild.id = guild_id

    # Thread-specific
    msg.channel.parent_id = None

    # Mock create_thread on the channel
    msg.create_thread = AsyncMock()

    return msg


# ---------------------------------------------------------------------------
# __init__ tests
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_config(self):
        ch = _make_channel()
        assert ch.name == "discord"
        assert ch._bot_token == "test-token"
        assert ch._allowed_guilds == set()
        assert ch._mention_only is False
        assert ch._thread_mode is False  # defaults to mention_only
        assert ch._allowed_channels == set()
        assert ch._active_threads == {}
        assert ch._active_thread_ids == set()
        assert ch._typing_tasks == {}
        assert ch._client is None
        assert ch._thread is None
        assert ch._discord_loop is None
        assert ch._main_loop is None
        assert ch._discord_module is None
        assert ch._running is False

    def test_full_config(self):
        config = {
            "bot_token": "secret-token",
            "allowed_guilds": [111, 222, "333"],
            "mention_only": True,
            "thread_mode": True,
            "allowed_channels": ["ch1", "ch2"],
        }
        ch = _make_channel(config=config)
        assert ch._bot_token == "secret-token"
        assert ch._allowed_guilds == {111, 222, 333}
        assert ch._mention_only is True
        assert ch._thread_mode is True
        assert ch._allowed_channels == {"ch1", "ch2"}

    def test_allowed_guilds_skips_invalid(self):
        config = {"bot_token": "t", "allowed_guilds": [100, "bad", None, 200]}
        ch = _make_channel(config=config)
        assert ch._allowed_guilds == {100, 200}

    def test_thread_mode_defaults_to_mention_only(self):
        config = {"bot_token": "t", "mention_only": True}
        ch = _make_channel(config=config)
        assert ch._thread_mode is True

    def test_thread_mode_can_be_set_independently(self):
        config = {"bot_token": "t", "mention_only": False, "thread_mode": True}
        ch = _make_channel(config=config)
        assert ch._mention_only is False
        assert ch._thread_mode is True

    def test_channel_store_path_from_config(self):
        store = MagicMock()
        store._path = Path("/data/channels/store.json")
        config = {"bot_token": "t", "channel_store": store}
        ch = _make_channel(config=config)
        assert ch._thread_store_path == Path("/data/channels/discord_threads.json")

    def test_default_thread_store_path(self):
        config = {"bot_token": "t"}
        ch = _make_channel(config=config)
        assert ch._thread_store_path == Path.home() / ".ideer" / "channels" / "discord_threads.json"

    def test_empty_bot_token(self):
        config = {"bot_token": ""}
        ch = _make_channel(config=config)
        assert ch._bot_token == ""

    def test_whitespace_bot_token_stripped(self):
        config = {"bot_token": "  token123  "}
        ch = _make_channel(config=config)
        assert ch._bot_token == "token123"


# ---------------------------------------------------------------------------
# _split_text tests
# ---------------------------------------------------------------------------


class TestSplitText:
    def test_empty_string(self):
        assert DiscordChannel._split_text("") == [""]

    def test_short_text(self):
        assert DiscordChannel._split_text("hello") == ["hello"]

    def test_exactly_2000_chars(self):
        text = "a" * 2000
        assert DiscordChannel._split_text(text) == [text]

    def test_2001_chars_splits_at_newline(self):
        text = "a" * 1999 + "\n" + "b" * 10
        result = DiscordChannel._split_text(text)
        assert len(result) == 2
        assert result[0] == "a" * 1999
        assert result[1] == "b" * 10

    def test_no_newline_splits_at_limit(self):
        text = "a" * 2500
        result = DiscordChannel._split_text(text)
        assert len(result) == 2
        assert result[0] == "a" * 2000
        assert result[1] == "a" * 500

    def test_multiple_splits(self):
        # Create text with newlines that force multiple splits
        chunk = "a" * 1999 + "\n"
        text = chunk * 3 + "end"
        result = DiscordChannel._split_text(text)
        assert len(result) >= 3
        assert result[-1] == "end"

    def test_leading_newline_stripped(self):
        text = "a" * 2000 + "\n\nextra"
        result = DiscordChannel._split_text(text)
        assert result[1] == "extra"

    def test_split_at_last_newline_before_limit(self):
        # Newline at position 1500, text is 2200 chars
        text = "a" * 1500 + "\n" + "b" * 699
        result = DiscordChannel._split_text(text)
        assert result[0] == "a" * 1500
        assert result[1] == "b" * 699


# ---------------------------------------------------------------------------
# _load_active_threads / _save_thread tests
# ---------------------------------------------------------------------------


class TestThreadPersistence:
    def test_load_active_threads_no_file(self, tmp_path):
        ch = _make_channel()
        ch._thread_store_path = tmp_path / "nonexistent.json"
        ch._load_active_threads()
        assert ch._active_threads == {}
        assert ch._active_thread_ids == set()

    def test_load_active_threads_with_data(self, tmp_path):
        store_file = tmp_path / "discord_threads.json"
        store_file.write_text(json.dumps({"ch1": "t1", "ch2": "t2"}))

        ch = _make_channel()
        ch._thread_store_path = store_file
        ch._load_active_threads()

        assert ch._active_threads == {"ch1": "t1", "ch2": "t2"}
        assert ch._active_thread_ids == {"t1", "t2"}

    def test_load_clears_existing_data(self, tmp_path):
        store_file = tmp_path / "discord_threads.json"
        store_file.write_text(json.dumps({"new_ch": "new_t"}))

        ch = _make_channel()
        ch._thread_store_path = store_file
        ch._active_threads = {"old_ch": "old_t"}
        ch._active_thread_ids = {"old_t"}
        ch._load_active_threads()

        assert ch._active_threads == {"new_ch": "new_t"}
        assert ch._active_thread_ids == {"new_t"}

    def test_load_handles_corrupt_json(self, tmp_path, caplog):
        store_file = tmp_path / "discord_threads.json"
        store_file.write_text("not valid json!!!{")

        ch = _make_channel()
        ch._thread_store_path = store_file
        ch._load_active_threads()
        # Should not raise; old data preserved
        assert ch._active_threads == {}

    def test_save_thread_creates_file(self, tmp_path):
        ch = _make_channel()
        ch._thread_store_path = tmp_path / "discord_threads.json"
        ch._save_thread("ch1", "t1")

        assert ch._thread_store_path.exists()
        data = json.loads(ch._thread_store_path.read_text())
        assert data == {"ch1": "t1"}
        assert ch._active_thread_ids == {"t1"}

    def test_save_thread_updates_existing(self, tmp_path):
        store_file = tmp_path / "discord_threads.json"
        store_file.write_text(json.dumps({"ch1": "old_t"}))

        ch = _make_channel()
        ch._thread_store_path = store_file
        ch._active_thread_ids = {"old_t"}
        ch._save_thread("ch1", "new_t")

        data = json.loads(store_file.read_text())
        assert data == {"ch1": "new_t"}
        assert "old_t" not in ch._active_thread_ids
        assert "new_t" in ch._active_thread_ids

    def test_save_thread_creates_parent_dirs(self, tmp_path):
        ch = _make_channel()
        ch._thread_store_path = tmp_path / "nested" / "dir" / "threads.json"
        ch._save_thread("ch1", "t1")
        assert ch._thread_store_path.exists()

    def test_save_thread_handles_write_error(self, tmp_path, caplog):
        ch = _make_channel()
        ch._thread_store_path = tmp_path / "discord_threads.json"
        ch._thread_store_path.write_text(json.dumps({"existing": "data"}))
        # Make the file unreadable to trigger read error during save
        ch._thread_store_path = Path("/nonexistent/dir/file.json")
        ch._save_thread("ch1", "t1")
        # Should not raise


# ---------------------------------------------------------------------------
# _publish tests
# ---------------------------------------------------------------------------


class TestPublish:
    def test_publish_when_main_loop_running(self):
        ch = _make_channel()
        main_loop = MagicMock()
        main_loop.is_running.return_value = True
        ch._main_loop = main_loop

        inbound = MagicMock()
        ch._publish(inbound)

        main_loop.create_task.assert_not_called()  # uses run_coroutine_threadsafe

    def test_publish_when_no_main_loop(self):
        ch = _make_channel()
        ch._main_loop = None
        # Should not raise
        ch._publish(MagicMock())

    def test_publish_when_main_loop_not_running(self):
        ch = _make_channel()
        main_loop = MagicMock()
        main_loop.is_running.return_value = False
        ch._main_loop = main_loop
        # Should not call run_coroutine_threadsafe
        ch._publish(MagicMock())


# ---------------------------------------------------------------------------
# _run_client tests
# ---------------------------------------------------------------------------


class TestRunClient:
    def test_run_client_starts_event_loop(self):
        ch = _make_channel()
        ch._bot_token = "test-token"
        ch._client = MagicMock()
        ch._client.start = AsyncMock(side_effect=KeyboardInterrupt)
        ch._client.is_closed.return_value = True
        ch._running = True

        # Run _run_client in a thread; it will exit after client.start raises
        t = threading.Thread(target=ch._run_client)
        t.start()
        t.join(timeout=5)

        assert ch._discord_loop is not None

    def test_run_client_handles_start_exception(self, caplog):
        ch = _make_channel()
        ch._bot_token = "test-token"
        ch._client = MagicMock()
        ch._client.start = AsyncMock(side_effect=RuntimeError("connection failed"))
        ch._client.is_closed.return_value = True
        ch._running = True

        t = threading.Thread(target=ch._run_client)
        t.start()
        t.join(timeout=5)

        # Should log the exception
        assert ch._discord_loop is not None

    def test_run_client_closes_on_stop(self):
        ch = _make_channel()
        ch._bot_token = "test-token"
        ch._client = MagicMock()
        ch._client.start = AsyncMock(side_effect=KeyboardInterrupt)
        ch._client.is_closed.return_value = False
        ch._client.close = AsyncMock()
        ch._running = False

        t = threading.Thread(target=ch._run_client)
        t.start()
        t.join(timeout=5)

    def test_run_client_handles_close_error(self, caplog):
        ch = _make_channel()
        ch._bot_token = "test-token"
        ch._client = MagicMock()
        ch._client.start = AsyncMock(side_effect=KeyboardInterrupt)
        ch._client.is_closed.return_value = False
        ch._client.close = AsyncMock(side_effect=RuntimeError("close failed"))
        ch._running = True

        t = threading.Thread(target=ch._run_client)
        t.start()
        t.join(timeout=5)


# ---------------------------------------------------------------------------
# start / stop lifecycle tests
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_start_imports_discord(self):
        ch = _make_channel(config={"bot_token": "test-token"})
        mock_discord = MagicMock()
        mock_client = MagicMock()
        mock_discord.Client.return_value = mock_client
        mock_discord.Intents.default.return_value = MagicMock()
        mock_discord.AllowedMentions.none.return_value = MagicMock()

        with patch.dict("sys.modules", {"discord": mock_discord}):
            loop = asyncio.new_event_loop()
            ch._main_loop = loop

            async def _start():
                await ch.start()

            loop.run_until_complete(_start())

        assert ch._running is True
        assert ch._client is mock_client
        assert ch._discord_module is mock_discord
        assert ch._thread is not None
        assert ch._thread.daemon is True

        # Clean up
        ch._running = False
        ch._client = None
        if ch._thread:
            ch._thread.join(timeout=2)

    def test_start_already_running_is_noop(self):
        ch = _make_channel()
        ch._running = True

        _run(ch.start())
        # Should return immediately without importing discord

    def test_start_missing_discord_module(self, caplog):
        ch = _make_channel()
        with patch.dict("sys.modules", {"discord": None}):
            # Force ImportError
            import builtins

            real_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "discord":
                    raise ImportError("No module named 'discord'")
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                _run(ch.start())

        assert ch._running is False
        assert "discord.py is not installed" in caplog.text

    def test_start_empty_bot_token(self, caplog):
        ch = _make_channel(config={"bot_token": ""})
        mock_discord = MagicMock()
        with patch.dict("sys.modules", {"discord": mock_discord}):
            _run(ch.start())

        assert ch._running is False
        assert "requires bot_token" in caplog.text

    def test_stop_cancels_typing_tasks(self):
        ch = _make_channel()
        ch._running = True

        # Create mock typing tasks
        task1 = MagicMock()
        task1.done.return_value = False
        task2 = MagicMock()
        task2.done.return_value = True
        ch._typing_tasks = {"target1": task1, "target2": task2}

        loop = asyncio.new_event_loop()

        async def _stop():
            await ch.stop()

        loop.run_until_complete(_stop())

        task1.cancel.assert_called_once()
        task2.cancel.assert_not_called()  # already done
        assert ch._typing_tasks == {}

    def test_stop_closes_client(self):
        ch = _make_channel()
        ch._running = True
        ch._discord_loop = asyncio.new_event_loop()

        client = MagicMock()
        client.close = AsyncMock()
        ch._client = client

        loop = asyncio.new_event_loop()

        async def _stop():
            await ch.stop()

        loop.run_until_complete(_stop())
        assert ch._client is None
        assert ch._discord_loop is None

    def test_stop_joins_thread(self):
        ch = _make_channel()
        ch._running = True
        mock_thread = MagicMock()
        mock_thread.join = MagicMock()
        ch._thread = mock_thread

        loop = asyncio.new_event_loop()

        async def _stop():
            await ch.stop()

        loop.run_until_complete(_stop())
        mock_thread.join.assert_called_once_with(timeout=10)

    def test_stop_timeout_on_client_close(self, caplog):
        ch = _make_channel()
        ch._running = True

        # Start a discord loop in a background thread so is_running() returns True
        discord_loop = asyncio.new_event_loop()
        ch._discord_loop = discord_loop
        loop_thread = threading.Thread(target=discord_loop.run_forever, daemon=True)
        loop_thread.start()

        client = MagicMock()

        async def _close():
            await asyncio.sleep(100)

        client.close = _close
        ch._client = client

        main_loop = asyncio.new_event_loop()

        try:
            with caplog.at_level(logging.WARNING, logger="app.channels.discord"):
                original_wait_for = asyncio.wait_for

                async def _mock_wait_for(fut, timeout=None):
                    raise TimeoutError("simulated timeout")

                asyncio.wait_for = _mock_wait_for
                try:
                    main_loop.run_until_complete(ch.stop())
                finally:
                    asyncio.wait_for = original_wait_for
            assert "timed out" in caplog.text
        finally:
            discord_loop.call_soon_threadsafe(discord_loop.stop)
            loop_thread.join(timeout=2)


# ---------------------------------------------------------------------------
# _start_typing / _stop_typing tests
# ---------------------------------------------------------------------------


class TestTyping:
    @pytest.mark.anyio
    async def test_start_typing_creates_task(self):
        ch = _make_channel()
        channel = MagicMock()
        channel.trigger_typing = AsyncMock()

        await ch._start_typing(channel, "chat1", "thread1")

        assert "thread1" in ch._typing_tasks
        task = ch._typing_tasks["thread1"]
        assert not task.done()

        # Clean up
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.anyio
    async def test_start_typing_uses_chat_id_when_no_thread(self):
        ch = _make_channel()
        channel = MagicMock()
        channel.trigger_typing = AsyncMock()

        await ch._start_typing(channel, "chat1")

        assert "chat1" in ch._typing_tasks
        ch._typing_tasks["chat1"].cancel()
        try:
            await ch._typing_tasks["chat1"]
        except asyncio.CancelledError:
            pass

    @pytest.mark.anyio
    async def test_start_typing_no_duplicate(self):
        ch = _make_channel()
        channel = MagicMock()
        channel.trigger_typing = AsyncMock()

        await ch._start_typing(channel, "chat1", "thread1")
        first_task = ch._typing_tasks["thread1"]

        await ch._start_typing(channel, "chat1", "thread1")
        assert ch._typing_tasks["thread1"] is first_task

        first_task.cancel()
        try:
            await first_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.anyio
    async def test_stop_typing_cancels_task(self):
        ch = _make_channel()
        channel = MagicMock()
        channel.trigger_typing = AsyncMock()

        await ch._start_typing(channel, "chat1", "thread1")
        assert "thread1" in ch._typing_tasks

        await ch._stop_typing("chat1", "thread1")
        assert "thread1" not in ch._typing_tasks

    @pytest.mark.anyio
    async def test_stop_typing_no_task(self):
        ch = _make_channel()
        # Should not raise when no task exists
        await ch._stop_typing("nonexistent", "thread1")

    @pytest.mark.anyio
    async def test_stop_typing_already_done(self):
        ch = _make_channel()
        task = MagicMock()
        task.done.return_value = True
        ch._typing_tasks["target1"] = task

        await ch._stop_typing("chat1", "target1")
        task.cancel.assert_not_called()


# ---------------------------------------------------------------------------
# _add_reaction tests
# ---------------------------------------------------------------------------


class TestAddReaction:
    @pytest.mark.anyio
    async def test_add_reaction_success(self):
        ch = _make_channel()
        msg = MagicMock()
        msg.add_reaction = AsyncMock()
        msg.id = "msg1"

        await ch._add_reaction(msg)
        msg.add_reaction.assert_called_once_with("✅")

    @pytest.mark.anyio
    async def test_add_reaction_failure(self, caplog):
        ch = _make_channel()
        msg = MagicMock()
        msg.add_reaction = AsyncMock(side_effect=RuntimeError("no permission"))
        msg.id = "msg1"

        await ch._add_reaction(msg)
        # Should not raise


# ---------------------------------------------------------------------------
# _create_thread tests
# ---------------------------------------------------------------------------


class TestCreateThread:
    @pytest.mark.anyio
    async def test_create_thread_success(self):
        ch = _make_channel()
        ch._discord_module = MagicMock()

        # Set up channel type as text (type 0)
        text_type = MagicMock()
        text_type.value = 0
        text_type.name = "text"
        ch._discord_module.ChannelType.text = text_type
        ch._discord_module.ChannelType.news = MagicMock()

        msg = _make_mock_message(channel_type=text_type)
        thread_obj = MagicMock()
        msg.create_thread = AsyncMock(return_value=thread_obj)

        result = await ch._create_thread(msg)
        assert result is thread_obj
        msg.create_thread.assert_called_once()

    @pytest.mark.anyio
    async def test_create_thread_news_channel(self):
        ch = _make_channel()
        ch._discord_module = MagicMock()

        news_type = MagicMock()
        news_type.value = 10
        news_type.name = "news"
        ch._discord_module.ChannelType.text = MagicMock()
        ch._discord_module.ChannelType.news = news_type

        msg = _make_mock_message(channel_type=news_type)
        thread_obj = MagicMock()
        msg.create_thread = AsyncMock(return_value=thread_obj)

        result = await ch._create_thread(msg)
        assert result is thread_obj

    @pytest.mark.anyio
    async def test_create_thread_unsupported_channel_type(self, caplog):
        ch = _make_channel()
        ch._discord_module = MagicMock()

        # Use sentinel objects that won't equal the channel type
        text_type = object()
        news_type = object()
        ch._discord_module.ChannelType.text = text_type
        ch._discord_module.ChannelType.news = news_type

        voice_type = MagicMock()
        voice_type.value = 2
        voice_type.name = "voice"

        msg = _make_mock_message(channel_type=voice_type)

        with caplog.at_level(logging.INFO):
            result = await ch._create_thread(msg)
        assert result is None
        assert "does not support threads" in caplog.text

    @pytest.mark.anyio
    async def test_create_thread_no_discord_module(self):
        ch = _make_channel()
        ch._discord_module = None
        msg = _make_mock_message()

        result = await ch._create_thread(msg)
        assert result is None

    @pytest.mark.anyio
    async def test_create_thread_http_exception_50024(self, caplog):
        ch = _make_channel()
        mock_discord = MagicMock()
        ch._discord_module = mock_discord

        # Use real type objects for channel types so `in` comparison works
        text_type = MagicMock()
        text_type.value = 0
        text_type.name = "text"
        text_type.__hash__ = lambda self: hash("text_type")
        text_type.__eq__ = lambda self, other: other is text_type
        mock_discord.ChannelType.text = text_type
        news_type = object()
        mock_discord.ChannelType.news = news_type

        # Create a proper exception class with a `code` attribute
        class MockHTTPException(Exception):
            def __init__(self, code=0):
                super().__init__()
                self.code = code

        mock_discord.errors.HTTPException = MockHTTPException

        msg = _make_mock_message(channel_type=text_type)
        msg.create_thread = AsyncMock(side_effect=MockHTTPException(code=50024))

        with caplog.at_level(logging.INFO):
            result = await ch._create_thread(msg)
        assert result is None

    @pytest.mark.anyio
    async def test_create_thread_http_exception_other_code(self, caplog):
        ch = _make_channel()
        mock_discord = MagicMock()
        ch._discord_module = mock_discord

        text_type = MagicMock()
        text_type.value = 0
        text_type.name = "text"
        text_type.__hash__ = lambda self: hash("text_type")
        text_type.__eq__ = lambda self, other: other is text_type
        mock_discord.ChannelType.text = text_type
        news_type = object()
        mock_discord.ChannelType.news = news_type

        class MockHTTPException(Exception):
            def __init__(self, code=0):
                super().__init__()
                self.code = code

        mock_discord.errors.HTTPException = MockHTTPException

        msg = _make_mock_message(channel_type=text_type)
        msg.create_thread = AsyncMock(side_effect=MockHTTPException(code=50013))

        with caplog.at_level(logging.INFO):
            result = await ch._create_thread(msg)
        assert result is None

    @pytest.mark.anyio
    async def test_create_thread_generic_exception(self, caplog):
        ch = _make_channel()
        mock_discord = MagicMock()
        ch._discord_module = mock_discord

        text_type = MagicMock()
        text_type.value = 0
        text_type.name = "text"
        text_type.__hash__ = lambda self: hash("text_type")
        text_type.__eq__ = lambda self, other: other is text_type
        mock_discord.ChannelType.text = text_type
        news_type = object()
        mock_discord.ChannelType.news = news_type

        class MockHTTPException(Exception):
            pass

        mock_discord.errors.HTTPException = MockHTTPException

        msg = _make_mock_message(channel_type=text_type)
        msg.create_thread = AsyncMock(side_effect=RuntimeError("permission denied"))

        with caplog.at_level(logging.INFO):
            result = await ch._create_thread(msg)
        assert result is None
        assert "failed to create thread" in caplog.text


# ---------------------------------------------------------------------------
# _get_channel_or_thread / _fetch_channel tests
# ---------------------------------------------------------------------------


class TestResolveChannel:
    @pytest.mark.anyio
    async def test_get_channel_or_thread_valid_id(self):
        ch = _make_channel()
        ch._client = MagicMock()
        ch._discord_loop = asyncio.new_event_loop()

        expected = MagicMock()
        ch._client.get_channel.return_value = expected

        # _get_channel_or_thread uses run_coroutine_threadsafe, which needs a running loop
        # We need to test _fetch_channel directly
        result = await ch._fetch_channel(200001)
        assert result is expected

    @pytest.mark.anyio
    async def test_get_channel_or_thread_invalid_id(self):
        ch = _make_channel()
        ch._client = MagicMock()
        ch._discord_loop = asyncio.new_event_loop()

        result = await ch._get_channel_or_thread("not-a-number")
        assert result is None

    @pytest.mark.anyio
    async def test_get_channel_or_thread_no_client(self):
        ch = _make_channel()
        ch._client = None
        ch._discord_loop = None

        result = await ch._get_channel_or_thread("200001")
        assert result is None

    @pytest.mark.anyio
    async def test_fetch_channel_get_returns_none_then_fetches(self):
        ch = _make_channel()
        ch._client = MagicMock()
        ch._client.get_channel.return_value = None
        ch._client.fetch_channel = AsyncMock(return_value=MagicMock())

        result = await ch._fetch_channel(200001)
        assert result is not None
        ch._client.fetch_channel.assert_called_once_with(200001)

    @pytest.mark.anyio
    async def test_fetch_channel_fetch_also_fails(self):
        ch = _make_channel()
        ch._client = MagicMock()
        ch._client.get_channel.return_value = None
        ch._client.fetch_channel = AsyncMock(side_effect=RuntimeError("not found"))

        result = await ch._fetch_channel(200001)
        assert result is None

    @pytest.mark.anyio
    async def test_fetch_channel_no_client(self):
        ch = _make_channel()
        ch._client = None
        result = await ch._fetch_channel(200001)
        assert result is None


# ---------------------------------------------------------------------------
# _resolve_target tests
# ---------------------------------------------------------------------------


class TestResolveTarget:
    @pytest.mark.anyio
    async def test_resolve_target_no_client(self):
        ch = _make_channel()
        ch._client = None
        ch._discord_loop = None

        msg = _make_outbound()
        result = await ch._resolve_target(msg)
        assert result is None

    @pytest.mark.anyio
    async def test_resolve_target_tries_thread_ts_first(self):
        ch = _make_channel()
        ch._client = MagicMock()
        ch._discord_loop = asyncio.new_event_loop()

        expected = MagicMock()
        ch._client.get_channel.return_value = expected

        _make_outbound(thread_ts="300001")
        # Test via _fetch_channel directly since _get_channel_or_thread uses run_coroutine_threadsafe
        result = await ch._fetch_channel(300001)
        assert result is expected

    @pytest.mark.anyio
    async def test_resolve_target_falls_back_to_chat_id(self):
        ch = _make_channel()
        ch._client = MagicMock()
        ch._discord_loop = asyncio.new_event_loop()

        expected = MagicMock()
        ch._client.get_channel.return_value = expected

        result = await ch._fetch_channel(100001)
        assert result is expected


# ---------------------------------------------------------------------------
# send tests
# ---------------------------------------------------------------------------


class TestSend:
    @pytest.mark.anyio
    async def test_send_resolves_target_and_sends(self):
        ch = _make_channel()
        ch._discord_loop = MagicMock()

        target = MagicMock()
        target.send = AsyncMock()

        msg = _make_outbound(text="Hello!")

        ch._resolve_target = AsyncMock(return_value=target)
        ch._stop_typing = AsyncMock()

        rcts_ctx, wf_ctx = _mock_rcts_and_wf()
        with rcts_ctx, wf_ctx:
            await ch.send(msg)

        ch._stop_typing.assert_called_once_with(msg.chat_id, msg.thread_ts)
        target.send.assert_called_once_with("Hello!")

    @pytest.mark.anyio
    async def test_send_no_target(self):
        ch = _make_channel()
        ch._discord_loop = MagicMock()

        msg = _make_outbound()
        ch._resolve_target = AsyncMock(return_value=None)
        ch._stop_typing = AsyncMock()

        rcts_ctx, wf_ctx = _mock_rcts_and_wf()
        with rcts_ctx, wf_ctx:
            await ch.send(msg)

    @pytest.mark.anyio
    async def test_send_splits_long_text(self):
        ch = _make_channel()
        ch._discord_loop = MagicMock()

        target = MagicMock()
        target.send = AsyncMock()

        long_text = "a" * 2500
        msg = _make_outbound(text=long_text)
        ch._resolve_target = AsyncMock(return_value=target)
        ch._stop_typing = AsyncMock()

        rcts_ctx, wf_ctx = _mock_rcts_and_wf()
        with rcts_ctx, wf_ctx:
            await ch.send(msg)
        assert target.send.call_count == 2

    @pytest.mark.anyio
    async def test_send_empty_text(self):
        ch = _make_channel()
        ch._discord_loop = MagicMock()

        target = MagicMock()
        target.send = AsyncMock()

        msg = _make_outbound(text="")
        ch._resolve_target = AsyncMock(return_value=target)
        ch._stop_typing = AsyncMock()

        rcts_ctx, wf_ctx = _mock_rcts_and_wf()
        with rcts_ctx, wf_ctx:
            await ch.send(msg)
        target.send.assert_called_once_with("")

    @pytest.mark.anyio
    async def test_send_none_text(self):
        ch = _make_channel()
        ch._discord_loop = MagicMock()

        target = MagicMock()
        target.send = AsyncMock()

        msg = _make_outbound(text=None)
        ch._resolve_target = AsyncMock(return_value=target)
        ch._stop_typing = AsyncMock()

        rcts_ctx, wf_ctx = _mock_rcts_and_wf()
        with rcts_ctx, wf_ctx:
            await ch.send(msg)
        target.send.assert_called_once_with("")


# ---------------------------------------------------------------------------
# send_file tests
# ---------------------------------------------------------------------------


class TestSendFile:
    @pytest.mark.anyio
    async def test_send_file_success(self, tmp_path):
        ch = _make_channel()
        ch._discord_loop = MagicMock()
        ch._discord_module = MagicMock()

        target = MagicMock()
        target.send = AsyncMock()
        attachment = _make_attachment(actual_path=tmp_path / "test.txt")
        attachment.actual_path.write_text("content")

        msg = _make_outbound()
        ch._resolve_target = AsyncMock(return_value=target)
        ch._stop_typing = AsyncMock()

        rcts_ctx, wf_ctx = _mock_rcts_and_wf()
        with rcts_ctx, wf_ctx:
            result = await ch.send_file(msg, attachment)
        assert result is True

    @pytest.mark.anyio
    async def test_send_file_no_target(self):
        ch = _make_channel()
        ch._discord_loop = MagicMock()
        ch._discord_module = MagicMock()

        msg = _make_outbound()
        attachment = _make_attachment()
        ch._resolve_target = AsyncMock(return_value=None)
        ch._stop_typing = AsyncMock()

        rcts_ctx, wf_ctx = _mock_rcts_and_wf()
        with rcts_ctx, wf_ctx:
            result = await ch.send_file(msg, attachment)
        assert result is False

    @pytest.mark.anyio
    async def test_send_file_no_discord_module(self):
        ch = _make_channel()
        ch._discord_loop = MagicMock()
        ch._discord_module = None

        target = MagicMock()
        msg = _make_outbound()
        attachment = _make_attachment()
        ch._resolve_target = AsyncMock(return_value=target)
        ch._stop_typing = AsyncMock()

        rcts_ctx, wf_ctx = _mock_rcts_and_wf()
        with rcts_ctx, wf_ctx:
            result = await ch.send_file(msg, attachment)
        assert result is False

    @pytest.mark.anyio
    async def test_send_file_exception(self, tmp_path, caplog):
        ch = _make_channel()
        ch._discord_loop = MagicMock()
        ch._discord_module = MagicMock()
        # Make File constructor raise to trigger the except path
        ch._discord_module.File = MagicMock(side_effect=RuntimeError("file error"))

        target = MagicMock()
        attachment = _make_attachment(actual_path=tmp_path / "test.txt")
        attachment.actual_path.write_text("content")

        msg = _make_outbound()
        ch._resolve_target = AsyncMock(return_value=target)
        ch._stop_typing = AsyncMock()

        rcts_ctx, wf_ctx = _mock_rcts_and_wf()
        with rcts_ctx, wf_ctx:
            result = await ch.send_file(msg, attachment)
        assert result is False
        assert "failed to upload file" in caplog.text


# ---------------------------------------------------------------------------
# _on_message tests — the most complex method
# ---------------------------------------------------------------------------


class TestOnMessage:
    def _setup_channel(self, config=None, **kwargs):
        """Set up a DiscordChannel with mocked discord module for _on_message testing."""
        ch = _make_channel(config=config or {"bot_token": "test-token"})
        ch._running = True

        mock_discord = MagicMock()
        thread_type = MagicMock()
        thread_type.__eq__ = lambda self, other: other is thread_type
        mock_discord.Thread = type("Thread", (), {})

        # Set a proper exception class for HTTPException so except clauses work
        class MockHTTPException(Exception):
            def __init__(self, code=0):
                super().__init__()
                self.code = code

        mock_discord.errors.HTTPException = MockHTTPException

        # Set up channel types
        text_type = MagicMock()
        text_type.value = 0
        text_type.name = "text"
        text_type.__hash__ = lambda self: hash("text_type")
        text_type.__eq__ = lambda self, other: other is text_type
        mock_discord.ChannelType.text = text_type
        news_type = object()
        mock_discord.ChannelType.news = news_type

        ch._discord_module = mock_discord

        # Mock client user
        client = MagicMock()
        client.user.id = "bot123"
        client.user.mention = "<@bot123>"
        ch._client = client

        # Mock main loop for _publish
        main_loop = MagicMock()
        main_loop.is_running.return_value = True
        ch._main_loop = main_loop

        return ch

    @pytest.mark.anyio
    async def test_on_message_not_running(self):
        ch = _make_channel()
        ch._running = False

        msg = _make_mock_message()
        await ch._on_message(msg)
        # Should return immediately

    @pytest.mark.anyio
    async def test_on_message_no_client(self):
        ch = _make_channel()
        ch._running = True
        ch._client = None

        msg = _make_mock_message()
        await ch._on_message(msg)

    @pytest.mark.anyio
    async def test_on_message_author_is_bot(self):
        ch = self._setup_channel()
        msg = _make_mock_message(author_bot=True)

        await ch._on_message(msg)
        # Should be ignored

    @pytest.mark.anyio
    async def test_on_message_author_is_self(self):
        ch = self._setup_channel()
        msg = _make_mock_message(author_id="bot123")

        await ch._on_message(msg)
        # Should be ignored

    @pytest.mark.anyio
    async def test_on_message_guild_not_allowed(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "allowed_guilds": [999],
            }
        )
        msg = _make_mock_message(guild_id=888)

        await ch._on_message(msg)
        # Should be ignored

    @pytest.mark.anyio
    async def test_on_message_guild_allowed(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "allowed_guilds": [100],
            }
        )
        ch._publish = MagicMock()

        msg = _make_mock_message(guild_id=100)
        await ch._on_message(msg)

        ch._publish.assert_called_once()

    @pytest.mark.anyio
    async def test_on_message_no_guild_when_guilds_required(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "allowed_guilds": [100],
            }
        )
        msg = _make_mock_message(guild_id=None)

        await ch._on_message(msg)
        # Should be ignored

    @pytest.mark.anyio
    async def test_on_message_empty_content(self):
        ch = self._setup_channel()
        msg = _make_mock_message(content="")

        await ch._on_message(msg)
        # Should be ignored

    @pytest.mark.anyio
    async def test_on_message_no_discord_module(self):
        ch = self._setup_channel()
        ch._discord_module = None
        msg = _make_mock_message(content="hello")

        await ch._on_message(msg)
        # Should be ignored

    @pytest.mark.anyio
    async def test_on_message_strips_mention(self):
        ch = self._setup_channel()
        ch._publish = MagicMock()

        msg = _make_mock_message(content="<@bot123> hello there")
        await ch._on_message(msg)

        ch._publish.assert_called_once()
        inbound = ch._publish.call_args[0][0]
        assert inbound.text == "hello there"

    @pytest.mark.anyio
    async def test_on_message_alt_mention_format(self):
        ch = self._setup_channel()
        ch._publish = MagicMock()

        msg = _make_mock_message(content="<@!bot123> hello")
        await ch._on_message(msg)

        inbound = ch._publish.call_args[0][0]
        assert inbound.text == "hello"

    @pytest.mark.anyio
    async def test_on_message_mention_only_with_empty_text_after_strip(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "mention_only": True,
            }
        )
        ch._publish = MagicMock()

        msg = _make_mock_message(content="<@bot123>")
        await ch._on_message(msg)

        # Should still process (empty text is ok for mention-only)
        ch._publish.assert_called_once()

    @pytest.mark.anyio
    async def test_on_message_mention_only_no_mention_skips(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "mention_only": True,
            }
        )
        ch._publish = MagicMock()

        msg = _make_mock_message(content="just talking without mention")
        await ch._on_message(msg)

        ch._publish.assert_not_called()

    @pytest.mark.anyio
    async def test_on_message_mention_only_allowed_channel_no_mention(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "mention_only": True,
                "allowed_channels": ["200001"],
            }
        )
        ch._publish = MagicMock()

        msg = _make_mock_message(content="hello", channel_id="200001")
        await ch._on_message(msg)

        ch._publish.assert_called_once()

    @pytest.mark.anyio
    async def test_on_message_mention_creates_thread(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "mention_only": True,
            }
        )
        ch._publish = MagicMock()

        mock_discord = ch._discord_module
        text_type = MagicMock()
        text_type.value = 0
        text_type.name = "text"
        mock_discord.ChannelType.text = text_type
        mock_discord.ChannelType.news = MagicMock()

        thread_obj = MagicMock()
        thread_obj.id = "thread_001"
        msg = _make_mock_message(content="<@bot123> ask something", channel_type=text_type)
        msg.create_thread = AsyncMock(return_value=thread_obj)

        await ch._on_message(msg)

        ch._publish.assert_called_once()
        inbound = ch._publish.call_args[0][0]
        assert inbound.thread_ts == "thread_001"
        assert ch._active_threads["200001"] == "thread_001"

    @pytest.mark.anyio
    async def test_on_message_mention_creates_thread_failure_fallback(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "mention_only": True,
            }
        )
        ch._publish = MagicMock()

        mock_discord = ch._discord_module
        text_type = MagicMock()
        text_type.value = 0
        text_type.name = "text"
        mock_discord.ChannelType.text = text_type
        mock_discord.ChannelType.news = MagicMock()

        msg = _make_mock_message(content="<@bot123> ask something", channel_type=text_type)
        msg.create_thread = AsyncMock(side_effect=RuntimeError("no perms"))

        await ch._on_message(msg)

        ch._publish.assert_called_once()
        inbound = ch._publish.call_args[0][0]
        # Falls back to channel ID
        assert inbound.thread_ts == "200001"

    @pytest.mark.anyio
    async def test_on_message_thread_mode_creates_thread(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "thread_mode": True,
            }
        )
        ch._publish = MagicMock()

        mock_discord = ch._discord_module
        text_type = MagicMock()
        text_type.value = 0
        text_type.name = "text"
        mock_discord.ChannelType.text = text_type
        mock_discord.ChannelType.news = MagicMock()

        thread_obj = MagicMock()
        thread_obj.id = "thread_002"
        msg = _make_mock_message(channel_type=text_type)
        msg.create_thread = AsyncMock(return_value=thread_obj)

        await ch._on_message(msg)

        ch._publish.assert_called_once()
        assert ch._active_threads["200001"] == "thread_002"

    @pytest.mark.anyio
    async def test_on_message_thread_mode_failure_fallback(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "thread_mode": True,
            }
        )
        ch._publish = MagicMock()

        mock_discord = ch._discord_module
        text_type = MagicMock()
        text_type.value = 0
        text_type.name = "text"
        mock_discord.ChannelType.text = text_type
        mock_discord.ChannelType.news = MagicMock()

        msg = _make_mock_message(channel_type=text_type)
        msg.create_thread = AsyncMock(side_effect=RuntimeError("fail"))

        await ch._on_message(msg)

        ch._publish.assert_called_once()
        inbound = ch._publish.call_args[0][0]
        assert inbound.thread_ts == "200001"  # Falls back to channel

    @pytest.mark.anyio
    async def test_on_message_no_thread_mode_direct_reply(self):
        ch = self._setup_channel()
        ch._publish = MagicMock()

        msg = _make_mock_message(content="hello bot")
        await ch._on_message(msg)

        ch._publish.assert_called_once()
        inbound = ch._publish.call_args[0][0]
        assert inbound.thread_ts == "200001"  # channel_id

    @pytest.mark.anyio
    async def test_on_message_command_type(self):
        ch = self._setup_channel()
        ch._publish = MagicMock()

        msg = _make_mock_message(content="/help")
        await ch._on_message(msg)

        inbound = ch._publish.call_args[0][0]
        assert inbound.msg_type == InboundMessageType.COMMAND

    @pytest.mark.anyio
    async def test_on_message_chat_type(self):
        ch = self._setup_channel()
        ch._publish = MagicMock()

        msg = _make_mock_message(content="just chatting")
        await ch._on_message(msg)

        inbound = ch._publish.call_args[0][0]
        assert inbound.msg_type == InboundMessageType.CHAT

    @pytest.mark.anyio
    async def test_on_message_metadata(self):
        ch = self._setup_channel()
        ch._publish = MagicMock()

        msg = _make_mock_message(guild_id=42, channel_id="200001", message_id="msg_999")
        await ch._on_message(msg)

        inbound = ch._publish.call_args[0][0]
        assert inbound.metadata["guild_id"] == "42"
        assert inbound.metadata["channel_id"] == "200001"
        assert inbound.metadata["message_id"] == "msg_999"

    @pytest.mark.anyio
    async def test_on_message_no_guild_metadata(self):
        ch = self._setup_channel()
        ch._publish = MagicMock()

        msg = _make_mock_message(guild_id=None)
        await ch._on_message(msg)

        inbound = ch._publish.call_args[0][0]
        assert inbound.metadata["guild_id"] is None

    # --- Thread-based message routing ---

    @pytest.mark.anyio
    async def test_on_message_in_active_thread(self):
        ch = self._setup_channel()
        ch._publish = MagicMock()
        ch._active_threads = {"200001": "thread_123"}
        ch._active_thread_ids = {"thread_123"}

        mock_discord = ch._discord_module
        thread_cls = type("Thread", (), {})

        msg = _make_mock_message(content="reply in thread", channel_id="200001")
        msg.channel = MagicMock()
        msg.channel.id = "thread_123"
        msg.channel.parent_id = "200001"
        msg.channel.__class__ = thread_cls
        mock_discord.Thread = thread_cls

        await ch._on_message(msg)

        ch._publish.assert_called_once()
        inbound = ch._publish.call_args[0][0]
        assert inbound.thread_ts == "thread_123"
        assert inbound.chat_id == "200001"

    @pytest.mark.anyio
    async def test_on_message_in_orphaned_thread(self):
        ch = self._setup_channel()
        ch._publish = MagicMock()
        # Thread is not in active_thread_ids

        mock_discord = ch._discord_module
        thread_cls = type("Thread", (), {})
        mock_discord.Thread = thread_cls

        text_type = MagicMock()
        text_type.value = 0
        text_type.name = "text"
        mock_discord.ChannelType.text = text_type
        mock_discord.ChannelType.news = MagicMock()

        msg = _make_mock_message(content="orphaned thread msg", channel_id="200001")
        msg.channel = MagicMock()
        msg.channel.id = "orphan_thread"
        msg.channel.parent_id = "200001"
        msg.channel.type = text_type
        msg.channel.__class__ = thread_cls
        msg.create_thread = AsyncMock()
        msg.create_thread.return_value = MagicMock(id="new_thread")

        await ch._on_message(msg)

        # Should process as a new message (orphaned thread falls through)
        ch._publish.assert_called_once()

    @pytest.mark.anyio
    async def test_on_message_existing_session_mention_replaces_thread(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "mention_only": True,
            }
        )
        ch._publish = MagicMock()
        ch._active_threads = {"200001": "old_thread"}
        ch._active_thread_ids = {"old_thread"}

        mock_discord = ch._discord_module
        text_type = MagicMock()
        text_type.value = 0
        text_type.name = "text"
        mock_discord.ChannelType.text = text_type
        mock_discord.ChannelType.news = MagicMock()

        thread_obj = MagicMock()
        thread_obj.id = "new_thread_001"
        msg = _make_mock_message(content="<@bot123> new topic", channel_type=text_type)
        msg.create_thread = AsyncMock(return_value=thread_obj)

        await ch._on_message(msg)

        ch._publish.assert_called_once()
        inbound = ch._publish.call_args[0][0]
        assert inbound.thread_ts == "new_thread_001"
        assert ch._active_threads["200001"] == "new_thread_001"

    @pytest.mark.anyio
    async def test_on_message_existing_session_mention_thread_failure(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "mention_only": True,
            }
        )
        ch._publish = MagicMock()
        ch._active_threads = {"200001": "old_thread"}
        ch._active_thread_ids = {"old_thread"}

        mock_discord = ch._discord_module
        text_type = MagicMock()
        text_type.value = 0
        text_type.name = "text"
        mock_discord.ChannelType.text = text_type
        mock_discord.ChannelType.news = MagicMock()

        msg = _make_mock_message(content="<@bot123> new topic", channel_type=text_type)
        msg.create_thread = AsyncMock(side_effect=RuntimeError("fail"))

        await ch._on_message(msg)

        ch._publish.assert_called_once()
        inbound = ch._publish.call_args[0][0]
        # Falls back to channel_id
        assert inbound.thread_ts == "200001"

    @pytest.mark.anyio
    async def test_on_message_existing_session_no_mention_skipped(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "mention_only": True,
            }
        )
        ch._publish = MagicMock()
        ch._active_threads = {"200001": "thread_abc"}
        ch._active_thread_ids = {"thread_abc"}

        msg = _make_mock_message(content="continue conversation", channel_id="200001")
        # Ensure msg.channel is NOT a Thread instance (regular channel)
        msg.channel = MagicMock()
        msg.channel.id = "200001"

        await ch._on_message(msg)

        # With mention_only=True and no mention, message is skipped
        ch._publish.assert_not_called()

    @pytest.mark.anyio
    async def test_on_message_mention_only_existing_session_skips_no_mention(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "mention_only": True,
            }
        )
        ch._publish = MagicMock()
        ch._active_threads = {"200001": "thread_abc"}
        ch._active_thread_ids = {"thread_abc"}

        msg = _make_mock_message(content="no mention in channel")

        # The message is in a channel, not a thread, and there's an active thread
        # mention_only is true, no mention, not in allowed_channels -> skip
        await ch._on_message(msg)

        ch._publish.assert_not_called()

    @pytest.mark.anyio
    async def test_on_message_mention_only_allowed_channel_existing_session(self):
        ch = self._setup_channel(
            config={
                "bot_token": "test",
                "mention_only": True,
                "allowed_channels": ["200001"],
            }
        )
        ch._publish = MagicMock()
        ch._active_threads = {"200001": "thread_abc"}
        ch._active_thread_ids = {"thread_abc"}

        typing_target = MagicMock()
        typing_target.trigger_typing = AsyncMock()
        ch._get_channel_or_thread = AsyncMock(return_value=typing_target)

        msg = _make_mock_message(content="no mention but allowed channel")
        await ch._on_message(msg)

        ch._publish.assert_called_once()

    @pytest.mark.anyio
    async def test_on_message_thread_command_type(self):
        ch = self._setup_channel()
        ch._publish = MagicMock()
        ch._active_threads = {"200001": "thread_123"}
        ch._active_thread_ids = {"thread_123"}

        mock_discord = ch._discord_module
        thread_cls = type("Thread", (), {})
        mock_discord.Thread = thread_cls

        msg = _make_mock_message(content="/status", channel_id="200001")
        msg.channel = MagicMock()
        msg.channel.id = "thread_123"
        msg.channel.parent_id = "200001"
        msg.channel.__class__ = thread_cls

        await ch._on_message(msg)

        inbound = ch._publish.call_args[0][0]
        assert inbound.msg_type == InboundMessageType.COMMAND

    @pytest.mark.anyio
    async def test_on_message_thread_parent_id_fallback(self):
        ch = self._setup_channel()
        ch._publish = MagicMock()
        ch._active_threads = {"thread_123": "thread_123"}
        ch._active_thread_ids = {"thread_123"}

        mock_discord = ch._discord_module
        thread_cls = type("Thread", (), {})
        mock_discord.Thread = thread_cls

        msg = _make_mock_message(content="hello", channel_id="200001")
        msg.channel = MagicMock()
        msg.channel.id = "thread_123"
        msg.channel.parent_id = None  # No parent
        msg.channel.__class__ = thread_cls

        await ch._on_message(msg)

        inbound = ch._publish.call_args[0][0]
        # Falls back to channel.id when parent_id is None
        assert inbound.chat_id == "thread_123"


# ---------------------------------------------------------------------------
# Integration: _on_outbound
# ---------------------------------------------------------------------------


class TestOnOutbound:
    @pytest.mark.anyio
    async def test_on_outbound_matching_channel(self):
        ch = _make_channel()
        ch.send = AsyncMock()
        ch.send_file = AsyncMock()

        msg = _make_outbound(channel_name="discord")
        attachment = _make_attachment()
        msg.attachments = [attachment]

        await ch._on_outbound(msg)

        ch.send.assert_called_once_with(msg)
        ch.send_file.assert_called_once_with(msg, attachment)

    @pytest.mark.anyio
    async def test_on_outbound_non_matching_channel(self):
        ch = _make_channel()
        ch.send = AsyncMock()

        msg = _make_outbound(channel_name="slack")
        await ch._on_outbound(msg)

        ch.send.assert_not_called()

    @pytest.mark.anyio
    async def test_on_outbound_send_failure_skips_files(self, caplog):
        ch = _make_channel()
        ch.send = AsyncMock(side_effect=RuntimeError("send failed"))
        ch.send_file = AsyncMock()

        msg = _make_outbound(channel_name="discord")
        msg.attachments = [_make_attachment()]

        await ch._on_outbound(msg)

        ch.send_file.assert_not_called()

    @pytest.mark.anyio
    async def test_on_outbound_file_upload_failure(self, caplog):
        ch = _make_channel()
        ch.send = AsyncMock()
        ch.send_file = AsyncMock(side_effect=RuntimeError("upload error"))

        msg = _make_outbound(channel_name="discord")
        msg.attachments = [_make_attachment()]

        await ch._on_outbound(msg)
        # Should log but not raise

    @pytest.mark.anyio
    async def test_on_outbound_file_upload_returns_false(self, caplog):
        ch = _make_channel()
        ch.send = AsyncMock()
        ch.send_file = AsyncMock(return_value=False)

        msg = _make_outbound(channel_name="discord")
        msg.attachments = [_make_attachment()]

        await ch._on_outbound(msg)
        # Should log warning about skipped upload
