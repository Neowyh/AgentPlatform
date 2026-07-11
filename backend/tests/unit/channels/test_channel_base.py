"""Comprehensive tests for the Channel base class in app.channels.base.

Covers every method, property, and code path including:
- __init__ and attribute assignment
- is_running / supports_streaming properties
- Abstract method enforcement
- send_file default behavior
- _make_inbound factory with all parameter combinations
- _on_outbound callback routing, error handling, and attachment logic
- receive_file default passthrough
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.channels.base import Channel
from app.channels.message_bus import (
    InboundMessage,
    InboundMessageType,
    MessageBus,
    OutboundMessage,
    ResolvedAttachment,
)

# ---------------------------------------------------------------------------
# Concrete test subclass (Channel is abstract)
# ---------------------------------------------------------------------------


class StubChannel(Channel):
    """Minimal concrete implementation for testing the base class."""

    def __init__(self, name: str = "test-channel", bus: MessageBus | None = None, config: dict | None = None):
        super().__init__(name=name, bus=bus or MessageBus(), config=config or {})
        self.started = False
        self.stopped = False
        self.sent_messages: list[OutboundMessage] = []
        self.send_side_effect: Exception | None = None
        self.send_file_return: bool = True
        self.send_file_side_effect: Exception | None = None
        self.sent_file_args: list[tuple[OutboundMessage, ResolvedAttachment]] = []

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def send(self, msg: OutboundMessage) -> None:
        if self.send_side_effect:
            raise self.send_side_effect
        self.sent_messages.append(msg)

    async def send_file(self, msg: OutboundMessage, attachment: ResolvedAttachment) -> bool:
        if self.send_file_side_effect:
            raise self.send_file_side_effect
        self.sent_file_args.append((msg, attachment))
        return self.send_file_return


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def bus() -> MessageBus:
    return MessageBus()


@pytest.fixture()
def channel(bus: MessageBus) -> StubChannel:
    return StubChannel(name="my-channel", bus=bus, config={"key": "value"})


def _make_outbound(**kwargs) -> OutboundMessage:
    """Helper to build an OutboundMessage with sensible defaults."""
    defaults = dict(
        channel_name="my-channel",
        chat_id="chat-1",
        thread_id="thread-1",
        text="hello",
    )
    defaults.update(kwargs)
    return OutboundMessage(**defaults)


def _make_attachment(filename: str = "report.pdf") -> ResolvedAttachment:
    return ResolvedAttachment(
        virtual_path=f"/virtual/{filename}",
        actual_path=Path(f"/tmp/{filename}"),
        filename=filename,
        mime_type="application/pdf",
        size=1024,
        is_image=False,
    )


# ===================================================================
# __init__
# ===================================================================


class TestInit:
    def test_stores_name(self, bus: MessageBus):
        ch = StubChannel(name="feishu", bus=bus, config={})
        assert ch.name == "feishu"

    def test_stores_bus(self, bus: MessageBus):
        ch = StubChannel(name="x", bus=bus, config={})
        assert ch.bus is bus

    def test_stores_config(self, bus: MessageBus):
        cfg = {"token": "abc", "enabled": True}
        ch = StubChannel(name="x", bus=bus, config=cfg)
        assert ch.config is cfg

    def test_running_defaults_false(self, bus: MessageBus):
        ch = StubChannel(name="x", bus=bus, config={})
        assert ch._running is False


# ===================================================================
# Properties
# ===================================================================


class TestProperties:
    def test_is_running_reflects_internal_state(self, channel: StubChannel):
        assert channel.is_running is False
        channel._running = True
        assert channel.is_running is True
        channel._running = False
        assert channel.is_running is False

    def test_supports_streaming_is_false(self, channel: StubChannel):
        assert channel.supports_streaming is False


# ===================================================================
# Abstract methods (concrete subclass satisfies them)
# ===================================================================


class TestAbstractMethods:
    @pytest.mark.asyncio()
    async def test_start_is_callable(self, channel: StubChannel):
        await channel.start()
        assert channel.started is True

    @pytest.mark.asyncio()
    async def test_stop_is_callable(self, channel: StubChannel):
        await channel.stop()
        assert channel.stopped is True

    @pytest.mark.asyncio()
    async def test_send_is_callable(self, channel: StubChannel):
        msg = _make_outbound()
        await channel.send(msg)
        assert msg in channel.sent_messages

    def test_cannot_instantiate_abstract(self):
        """Channel itself cannot be instantiated without implementing abstracts."""
        with pytest.raises(TypeError, match="start"):
            Channel(name="x", bus=MessageBus(), config={})


# ===================================================================
# send_file (base default)
# ===================================================================


class TestSendFileDefault:
    """Test the default Channel.send_file which always returns False."""

    @pytest.mark.asyncio()
    async def test_default_returns_false(self, bus: MessageBus):
        """The base Channel.send_file returns False without StubChannel's override."""

        class MinimalChannel(Channel):
            async def start(self):
                pass

            async def stop(self):
                pass

            async def send(self, msg):
                pass

        ch = MinimalChannel(name="min", bus=bus, config={})
        msg = _make_outbound()
        att = _make_attachment()
        result = await ch.send_file(msg, att)
        assert result is False


# ===================================================================
# _make_inbound
# ===================================================================


class TestMakeInbound:
    def test_basic_fields(self, channel: StubChannel):
        msg = channel._make_inbound("chat-1", "user-1", "hello")
        assert isinstance(msg, InboundMessage)
        assert msg.channel_name == "my-channel"
        assert msg.chat_id == "chat-1"
        assert msg.user_id == "user-1"
        assert msg.text == "hello"
        assert msg.msg_type == InboundMessageType.CHAT

    def test_default_optional_fields(self, channel: StubChannel):
        msg = channel._make_inbound("c", "u", "t")
        assert msg.thread_ts is None
        assert msg.files == []
        assert msg.metadata == {}

    def test_custom_msg_type(self, channel: StubChannel):
        msg = channel._make_inbound("c", "u", "t", msg_type=InboundMessageType.COMMAND)
        assert msg.msg_type == InboundMessageType.COMMAND

    def test_thread_ts(self, channel: StubChannel):
        msg = channel._make_inbound("c", "u", "t", thread_ts="ts-123")
        assert msg.thread_ts == "ts-123"

    def test_files(self, channel: StubChannel):
        files = [{"name": "a.pdf", "url": "http://example.com/a.pdf"}]
        msg = channel._make_inbound("c", "u", "t", files=files)
        assert msg.files == files

    def test_files_none_becomes_empty_list(self, channel: StubChannel):
        msg = channel._make_inbound("c", "u", "t", files=None)
        assert msg.files == []

    def test_metadata(self, channel: StubChannel):
        meta = {"source": "webhook"}
        msg = channel._make_inbound("c", "u", "t", metadata=meta)
        assert msg.metadata == meta

    def test_metadata_none_becomes_empty_dict(self, channel: StubChannel):
        msg = channel._make_inbound("c", "u", "t", metadata=None)
        assert msg.metadata == {}

    def test_all_params(self, channel: StubChannel):
        files = [{"name": "x.png"}]
        meta = {"key": "val"}
        msg = channel._make_inbound(
            "chat-99",
            "user-99",
            "full test",
            msg_type=InboundMessageType.COMMAND,
            thread_ts="thread-abc",
            files=files,
            metadata=meta,
        )
        assert msg.channel_name == "my-channel"
        assert msg.chat_id == "chat-99"
        assert msg.user_id == "user-99"
        assert msg.text == "full test"
        assert msg.msg_type == InboundMessageType.COMMAND
        assert msg.thread_ts == "thread-abc"
        assert msg.files == files
        assert msg.metadata == meta


# ===================================================================
# _on_outbound
# ===================================================================


class TestOnOutbound:
    """Test the outbound callback routing logic."""

    @pytest.mark.asyncio()
    async def test_ignores_message_for_different_channel(self, channel: StubChannel):
        msg = _make_outbound(channel_name="other-channel")
        await channel._on_outbound(msg)
        assert channel.sent_messages == []

    @pytest.mark.asyncio()
    async def test_sends_message_for_matching_channel(self, channel: StubChannel):
        msg = _make_outbound()
        await channel._on_outbound(msg)
        assert channel.sent_messages == [msg]

    @pytest.mark.asyncio()
    async def test_no_attachments_calls_send_only(self, channel: StubChannel):
        msg = _make_outbound(attachments=[])
        await channel._on_outbound(msg)
        assert channel.sent_messages == [msg]
        assert channel.sent_file_args == []

    @pytest.mark.asyncio()
    async def test_sends_then_uploads_attachments(self, channel: StubChannel):
        att1 = _make_attachment("a.pdf")
        att2 = _make_attachment("b.png")
        msg = _make_outbound(attachments=[att1, att2])
        await channel._on_outbound(msg)
        assert channel.sent_messages == [msg]
        assert len(channel.sent_file_args) == 2
        assert channel.sent_file_args[0] == (msg, att1)
        assert channel.sent_file_args[1] == (msg, att2)

    @pytest.mark.asyncio()
    async def test_send_exception_skips_attachments(self, channel: StubChannel, caplog):
        channel.send_side_effect = RuntimeError("network down")
        att = _make_attachment()
        msg = _make_outbound(attachments=[att])
        with caplog.at_level(logging.ERROR, logger="app.channels.base"):
            await channel._on_outbound(msg)
        assert channel.sent_messages == []
        assert channel.sent_file_args == []
        assert "Failed to send outbound message" in caplog.text

    @pytest.mark.asyncio()
    async def test_send_file_returns_false_logs_warning(self, channel: StubChannel, caplog):
        channel.send_file_return = False
        att = _make_attachment("doc.pdf")
        msg = _make_outbound(attachments=[att])
        with caplog.at_level(logging.WARNING, logger="app.channels.base"):
            await channel._on_outbound(msg)
        assert channel.sent_messages == [msg]
        assert "file upload skipped" in caplog.text
        assert "doc.pdf" in caplog.text

    @pytest.mark.asyncio()
    async def test_send_file_exception_logs_error(self, channel: StubChannel, caplog):
        channel.send_file_side_effect = OSError("disk full")
        att = _make_attachment("img.png")
        msg = _make_outbound(attachments=[att])
        with caplog.at_level(logging.ERROR, logger="app.channels.base"):
            await channel._on_outbound(msg)
        assert channel.sent_messages == [msg]
        assert "failed to upload file" in caplog.text
        assert "img.png" in caplog.text

    @pytest.mark.asyncio()
    async def test_mixed_attachment_results(self, channel: StubChannel, caplog):
        """One attachment succeeds, one returns False, one raises."""
        att_ok = _make_attachment("ok.pdf")
        att_skip = _make_attachment("skip.pdf")
        att_err = _make_attachment("err.pdf")

        call_count = 0

        async def side_effect(msg, attachment):
            nonlocal call_count
            call_count += 1
            if attachment is att_skip:
                return False
            if attachment is att_err:
                raise OSError("boom")
            return True

        channel.send_file = side_effect
        msg = _make_outbound(attachments=[att_ok, att_skip, att_err])
        with caplog.at_level(logging.WARNING, logger="app.channels.base"):
            await channel._on_outbound(msg)
        assert channel.sent_messages == [msg]
        assert "file upload skipped" in caplog.text
        assert "failed to upload file" in caplog.text

    @pytest.mark.asyncio()
    async def test_send_exception_does_not_log_file_warning(self, channel: StubChannel, caplog):
        """When send() fails, no file-related log entries should appear."""
        channel.send_side_effect = RuntimeError("fail")
        att = _make_attachment()
        msg = _make_outbound(attachments=[att])
        with caplog.at_level(logging.WARNING, logger="app.channels.base"):
            await channel._on_outbound(msg)
        assert "file upload skipped" not in caplog.text
        assert "failed to upload file" not in caplog.text


# ===================================================================
# receive_file
# ===================================================================


class TestReceiveFile:
    @pytest.mark.asyncio()
    async def test_default_returns_same_message(self, channel: StubChannel):
        msg = InboundMessage(
            channel_name="my-channel",
            chat_id="c",
            user_id="u",
            text="hello",
            files=[{"name": "a.pdf"}],
        )
        result = await channel.receive_file(msg, "thread-1")
        assert result is msg

    @pytest.mark.asyncio()
    async def test_default_preserves_text(self, channel: StubChannel):
        msg = InboundMessage(
            channel_name="my-channel",
            chat_id="c",
            user_id="u",
            text="original text",
        )
        result = await channel.receive_file(msg, "thread-abc")
        assert result.text == "original text"

    @pytest.mark.asyncio()
    async def test_default_ignores_thread_id(self, channel: StubChannel):
        msg = InboundMessage(
            channel_name="my-channel",
            chat_id="c",
            user_id="u",
            text="t",
        )
        result = await channel.receive_file(msg, "any-thread-id")
        assert result is msg


# ===================================================================
# Integration: _make_inbound -> _on_outbound round-trip
# ===================================================================


class TestIntegration:
    @pytest.mark.asyncio()
    async def test_inbound_created_with_channel_name_matches_outbound_routing(self, channel: StubChannel):
        """Messages created via _make_inbound carry the channel name, which
        _on_outbound uses to route replies back."""
        inbound = channel._make_inbound("c", "u", "hi")
        assert inbound.channel_name == channel.name

        outbound = _make_outbound(channel_name=inbound.channel_name)
        await channel._on_outbound(outbound)
        assert outbound in channel.sent_messages

    @pytest.mark.asyncio()
    async def test_outbound_with_different_name_not_delivered(self, channel: StubChannel):
        inbound = channel._make_inbound("c", "u", "hi")
        outbound = _make_outbound(channel_name=inbound.channel_name + "-other")
        await channel._on_outbound(outbound)
        assert outbound not in channel.sent_messages
