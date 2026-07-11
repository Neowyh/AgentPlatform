"""Comprehensive tests for app.channels.message_bus.

Covers every public class, dataclass, enum value, and method including all
error-handling branches. All external I/O (asyncio.Queue internals aside from
what the module itself creates) is mocked.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.channels.message_bus import (
    InboundMessage,
    InboundMessageType,
    MessageBus,
    OutboundCallback,
    OutboundMessage,
    ResolvedAttachment,
)

# ---------------------------------------------------------------------------
# InboundMessageType enum
# ---------------------------------------------------------------------------


class TestInboundMessageType:
    """Verify the StrEnum values and string behaviour."""

    def test_chat_value(self) -> None:
        assert InboundMessageType.CHAT == "chat"

    def test_command_value(self) -> None:
        assert InboundMessageType.COMMAND == "command"

    def test_str_coercion(self) -> None:
        assert str(InboundMessageType.CHAT) == "chat"
        assert str(InboundMessageType.COMMAND) == "command"

    def test_enum_member_count(self) -> None:
        assert len(InboundMessageType) == 2

    def test_is_str_subclass(self) -> None:
        assert isinstance(InboundMessageType.CHAT, str)

    def test_enum_iteration(self) -> None:
        members = list(InboundMessageType)
        assert InboundMessageType.CHAT in members
        assert InboundMessageType.COMMAND in members


# ---------------------------------------------------------------------------
# InboundMessage dataclass
# ---------------------------------------------------------------------------


class TestInboundMessage:
    """Test construction, defaults, and field access on InboundMessage."""

    def test_minimal_construction(self) -> None:
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="chat_001",
            user_id="user_001",
            text="hello",
        )
        assert msg.channel_name == "feishu"
        assert msg.chat_id == "chat_001"
        assert msg.user_id == "user_001"
        assert msg.text == "hello"

    def test_default_msg_type_is_chat(self) -> None:
        msg = InboundMessage(
            channel_name="slack",
            chat_id="c1",
            user_id="u1",
            text="hi",
        )
        assert msg.msg_type == InboundMessageType.CHAT

    def test_default_thread_ts_is_none(self) -> None:
        msg = InboundMessage(
            channel_name="slack",
            chat_id="c1",
            user_id="u1",
            text="hi",
        )
        assert msg.thread_ts is None

    def test_default_topic_id_is_none(self) -> None:
        msg = InboundMessage(
            channel_name="slack",
            chat_id="c1",
            user_id="u1",
            text="hi",
        )
        assert msg.topic_id is None

    def test_default_files_is_empty_list(self) -> None:
        msg = InboundMessage(
            channel_name="slack",
            chat_id="c1",
            user_id="u1",
            text="hi",
        )
        assert msg.files == []
        # Ensure each instance gets its own list (not shared reference).
        msg2 = InboundMessage(
            channel_name="slack",
            chat_id="c2",
            user_id="u2",
            text="bye",
        )
        msg.files.append({"name": "a.txt"})
        assert msg2.files == []

    def test_default_metadata_is_empty_dict(self) -> None:
        msg = InboundMessage(
            channel_name="slack",
            chat_id="c1",
            user_id="u1",
            text="hi",
        )
        assert msg.metadata == {}
        # Ensure each instance gets its own dict.
        msg2 = InboundMessage(
            channel_name="slack",
            chat_id="c2",
            user_id="u2",
            text="bye",
        )
        msg.metadata["key"] = "val"
        assert "key" not in msg2.metadata

    def test_default_created_at_is_numeric(self) -> None:
        before = time.time()
        msg = InboundMessage(
            channel_name="slack",
            chat_id="c1",
            user_id="u1",
            text="hi",
        )
        after = time.time()
        assert before <= msg.created_at <= after

    def test_explicit_command_type(self) -> None:
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="/help",
            msg_type=InboundMessageType.COMMAND,
        )
        assert msg.msg_type == InboundMessageType.COMMAND

    def test_explicit_thread_ts(self) -> None:
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="reply",
            thread_ts="ts_123",
        )
        assert msg.thread_ts == "ts_123"

    def test_explicit_topic_id(self) -> None:
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="topic msg",
            topic_id="topic_abc",
        )
        assert msg.topic_id == "topic_abc"

    def test_explicit_files(self) -> None:
        files = [{"name": "report.pdf", "url": "https://example.com/report.pdf"}]
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="see attached",
            files=files,
        )
        assert msg.files == files
        assert msg.files[0]["name"] == "report.pdf"

    def test_explicit_metadata(self) -> None:
        meta = {"source": "bot", "priority": "high"}
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="meta msg",
            metadata=meta,
        )
        assert msg.metadata == meta

    def test_explicit_created_at(self) -> None:
        ts = 1700000000.0
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="ts msg",
            created_at=ts,
        )
        assert msg.created_at == ts

    def test_all_fields_explicit(self) -> None:
        files = [{"name": "a.png"}]
        meta = {"k": "v"}
        ts = 1700000000.0
        msg = InboundMessage(
            channel_name="wechat",
            chat_id="group_1",
            user_id="user_99",
            text="full",
            msg_type=InboundMessageType.COMMAND,
            thread_ts="thread_1",
            topic_id="topic_1",
            files=files,
            metadata=meta,
            created_at=ts,
        )
        assert msg.channel_name == "wechat"
        assert msg.chat_id == "group_1"
        assert msg.user_id == "user_99"
        assert msg.text == "full"
        assert msg.msg_type == InboundMessageType.COMMAND
        assert msg.thread_ts == "thread_1"
        assert msg.topic_id == "topic_1"
        assert msg.files == files
        assert msg.metadata == meta
        assert msg.created_at == ts


# ---------------------------------------------------------------------------
# ResolvedAttachment dataclass
# ---------------------------------------------------------------------------


class TestResolvedAttachment:
    """Test ResolvedAttachment construction and field access."""

    def test_construction(self) -> None:
        att = ResolvedAttachment(
            virtual_path="/mnt/user-data/outputs/report.pdf",
            actual_path=Path("/real/path/report.pdf"),
            filename="report.pdf",
            mime_type="application/pdf",
            size=1024,
            is_image=False,
        )
        assert att.virtual_path == "/mnt/user-data/outputs/report.pdf"
        assert att.actual_path == Path("/real/path/report.pdf")
        assert att.filename == "report.pdf"
        assert att.mime_type == "application/pdf"
        assert att.size == 1024
        assert att.is_image is False

    def test_image_attachment(self) -> None:
        att = ResolvedAttachment(
            virtual_path="/mnt/user-data/img.png",
            actual_path=Path("/tmp/img.png"),
            filename="img.png",
            mime_type="image/png",
            size=2048,
            is_image=True,
        )
        assert att.is_image is True
        assert att.mime_type.startswith("image/")

    def test_actual_path_is_pathlib(self) -> None:
        att = ResolvedAttachment(
            virtual_path="/v",
            actual_path=Path("/a/b"),
            filename="b",
            mime_type="text/plain",
            size=0,
            is_image=False,
        )
        assert isinstance(att.actual_path, Path)


# ---------------------------------------------------------------------------
# OutboundMessage dataclass
# ---------------------------------------------------------------------------


class TestOutboundMessage:
    """Test OutboundMessage construction and defaults."""

    def test_minimal_construction(self) -> None:
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="response",
        )
        assert msg.channel_name == "feishu"
        assert msg.chat_id == "c1"
        assert msg.thread_id == "t1"
        assert msg.text == "response"

    def test_default_artifacts_empty(self) -> None:
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="r",
        )
        assert msg.artifacts == []
        # Each instance gets its own list.
        msg2 = OutboundMessage(
            channel_name="feishu",
            chat_id="c2",
            thread_id="t2",
            text="r2",
        )
        msg.artifacts.append("/path/to/artifact")
        assert msg2.artifacts == []

    def test_default_attachments_empty(self) -> None:
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="r",
        )
        assert msg.attachments == []
        # Each instance gets its own list.
        msg2 = OutboundMessage(
            channel_name="feishu",
            chat_id="c2",
            thread_id="t2",
            text="r2",
        )
        msg.attachments.append(
            ResolvedAttachment(
                virtual_path="/v",
                actual_path=Path("/a"),
                filename="a",
                mime_type="text/plain",
                size=0,
                is_image=False,
            )
        )
        assert msg2.attachments == []

    def test_default_is_final_true(self) -> None:
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="r",
        )
        assert msg.is_final is True

    def test_explicit_is_final_false(self) -> None:
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="streaming...",
            is_final=False,
        )
        assert msg.is_final is False

    def test_default_thread_ts_none(self) -> None:
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="r",
        )
        assert msg.thread_ts is None

    def test_explicit_thread_ts(self) -> None:
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="r",
            thread_ts="ts_456",
        )
        assert msg.thread_ts == "ts_456"

    def test_default_metadata_empty(self) -> None:
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="r",
        )
        assert msg.metadata == {}
        msg2 = OutboundMessage(
            channel_name="feishu",
            chat_id="c2",
            thread_id="t2",
            text="r2",
        )
        msg.metadata["k"] = "v"
        assert "k" not in msg2.metadata

    def test_default_created_at_is_numeric(self) -> None:
        before = time.time()
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="r",
        )
        after = time.time()
        assert before <= msg.created_at <= after

    def test_explicit_artifacts(self) -> None:
        arts = ["/out/file1.pdf", "/out/file2.csv"]
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="r",
            artifacts=arts,
        )
        assert msg.artifacts == arts

    def test_explicit_attachments(self) -> None:
        att = ResolvedAttachment(
            virtual_path="/v",
            actual_path=Path("/a"),
            filename="a",
            mime_type="text/plain",
            size=100,
            is_image=False,
        )
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="r",
            attachments=[att],
        )
        assert len(msg.attachments) == 1
        assert msg.attachments[0] is att

    def test_all_fields_explicit(self) -> None:
        att = ResolvedAttachment(
            virtual_path="/v",
            actual_path=Path("/a"),
            filename="a",
            mime_type="text/plain",
            size=50,
            is_image=False,
        )
        meta = {"status": "ok"}
        ts = 1700000000.0
        msg = OutboundMessage(
            channel_name="slack",
            chat_id="group_2",
            thread_id="thread_2",
            text="full response",
            artifacts=["/a1"],
            attachments=[att],
            is_final=False,
            thread_ts="platform_ts",
            metadata=meta,
            created_at=ts,
        )
        assert msg.channel_name == "slack"
        assert msg.chat_id == "group_2"
        assert msg.thread_id == "thread_2"
        assert msg.text == "full response"
        assert msg.artifacts == ["/a1"]
        assert msg.attachments == [att]
        assert msg.is_final is False
        assert msg.thread_ts == "platform_ts"
        assert msg.metadata == meta
        assert msg.created_at == ts


# ---------------------------------------------------------------------------
# MessageBus
# ---------------------------------------------------------------------------


class TestMessageBusInit:
    """Test MessageBus initialisation."""

    def test_creates_inbound_queue(self) -> None:
        bus = MessageBus()
        assert isinstance(bus._inbound_queue, asyncio.Queue)
        assert bus._inbound_queue.empty()

    def test_creates_empty_outbound_listeners(self) -> None:
        bus = MessageBus()
        assert bus._outbound_listeners == []

    def test_inbound_queue_property(self) -> None:
        bus = MessageBus()
        assert bus.inbound_queue is bus._inbound_queue


@pytest.mark.anyio
class TestMessageBusPublishInbound:
    """Test publish_inbound enqueuing and logging."""

    async def test_enqueues_message(self) -> None:
        bus = MessageBus()
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="hello",
        )
        await bus.publish_inbound(msg)
        assert bus.inbound_queue.qsize() == 1

    async def test_enqueued_message_is_retrievable(self) -> None:
        bus = MessageBus()
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="hello",
        )
        await bus.publish_inbound(msg)
        got = await bus.get_inbound()
        assert got is msg
        assert got.text == "hello"

    async def test_multiple_messages_fifo_order(self) -> None:
        bus = MessageBus()
        msgs = [
            InboundMessage(
                channel_name="feishu",
                chat_id=f"c{i}",
                user_id=f"u{i}",
                text=f"msg{i}",
            )
            for i in range(5)
        ]
        for m in msgs:
            await bus.publish_inbound(m)

        assert bus.inbound_queue.qsize() == 5
        for m in msgs:
            got = await bus.get_inbound()
            assert got is m

    async def test_logs_on_publish(self, caplog: pytest.LogCaptureFixture) -> None:
        bus = MessageBus()
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="hello",
        )
        with caplog.at_level(logging.INFO, logger="app.channels.message_bus"):
            await bus.publish_inbound(msg)
        assert any("inbound enqueued" in r.message for r in caplog.records)
        assert any("channel=feishu" in r.message for r in caplog.records)
        assert any("chat_id=c1" in r.message for r in caplog.records)
        assert any("type=chat" in r.message for r in caplog.records)
        assert any("queue_size=1" in r.message for r in caplog.records)

    async def test_logs_command_type(self, caplog: pytest.LogCaptureFixture) -> None:
        bus = MessageBus()
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="/help",
            msg_type=InboundMessageType.COMMAND,
        )
        with caplog.at_level(logging.INFO, logger="app.channels.message_bus"):
            await bus.publish_inbound(msg)
        assert any("type=command" in r.message for r in caplog.records)

    async def test_queue_size_reflects_multiple(self) -> None:
        bus = MessageBus()
        for i in range(3):
            await bus.publish_inbound(
                InboundMessage(
                    channel_name="feishu",
                    chat_id=f"c{i}",
                    user_id=f"u{i}",
                    text=f"m{i}",
                )
            )
        assert bus.inbound_queue.qsize() == 3


@pytest.mark.anyio
class TestMessageBusGetInbound:
    """Test get_inbound blocking behaviour."""

    async def test_returns_message_after_publish(self) -> None:
        bus = MessageBus()
        msg = InboundMessage(
            channel_name="slack",
            chat_id="c1",
            user_id="u1",
            text="test",
        )
        await bus.publish_inbound(msg)
        result = await bus.get_inbound()
        assert result is msg

    async def test_queue_empties_after_get(self) -> None:
        bus = MessageBus()
        msg = InboundMessage(
            channel_name="slack",
            chat_id="c1",
            user_id="u1",
            text="test",
        )
        await bus.publish_inbound(msg)
        await bus.get_inbound()
        assert bus.inbound_queue.empty()

    async def test_get_inbound_blocks_until_message(self) -> None:
        """Verify get_inbound blocks and resolves when a message arrives."""
        bus = MessageBus()
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="c1",
            user_id="u1",
            text="delayed",
        )

        async def _publish_after_delay() -> None:
            await asyncio.sleep(0.05)
            await bus.publish_inbound(msg)

        # Start publisher task, then block on get_inbound.
        publisher = asyncio.create_task(_publish_after_delay())
        result = await bus.get_inbound()
        await publisher
        assert result is msg

    async def test_get_inbound_can_be_cancelled(self) -> None:
        """Verify that a pending get_inbound can be cancelled."""
        bus = MessageBus()
        task = asyncio.create_task(bus.get_inbound())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


class TestMessageBusSubscribeOutbound:
    """Test subscribe_outbound."""

    def test_adds_callback(self) -> None:
        bus = MessageBus()
        cb = AsyncMock()
        bus.subscribe_outbound(cb)
        assert cb in bus._outbound_listeners

    def test_adds_multiple_callbacks(self) -> None:
        bus = MessageBus()
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        bus.subscribe_outbound(cb1)
        bus.subscribe_outbound(cb2)
        assert len(bus._outbound_listeners) == 2
        assert cb1 in bus._outbound_listeners
        assert cb2 in bus._outbound_listeners

    def test_same_callback_can_be_added_twice(self) -> None:
        bus = MessageBus()
        cb = AsyncMock()
        bus.subscribe_outbound(cb)
        bus.subscribe_outbound(cb)
        assert len(bus._outbound_listeners) == 2

    def test_appends_to_end(self) -> None:
        bus = MessageBus()
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        bus.subscribe_outbound(cb1)
        bus.subscribe_outbound(cb2)
        assert bus._outbound_listeners[-1] is cb2


class TestMessageBusUnsubscribeOutbound:
    """Test unsubscribe_outbound."""

    def test_removes_callback(self) -> None:
        bus = MessageBus()
        cb = AsyncMock()
        bus.subscribe_outbound(cb)
        bus.unsubscribe_outbound(cb)
        assert cb not in bus._outbound_listeners

    def test_removes_only_specified_callback(self) -> None:
        bus = MessageBus()
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        bus.subscribe_outbound(cb1)
        bus.subscribe_outbound(cb2)
        bus.unsubscribe_outbound(cb1)
        assert cb1 not in bus._outbound_listeners
        assert cb2 in bus._outbound_listeners
        assert len(bus._outbound_listeners) == 1

    def test_noop_when_callback_not_present(self) -> None:
        bus = MessageBus()
        cb = AsyncMock()
        # Should not raise.
        bus.unsubscribe_outbound(cb)
        assert len(bus._outbound_listeners) == 0

    def test_removes_all_occurrences(self) -> None:
        """If the same callback was added multiple times, all copies are removed."""
        bus = MessageBus()
        cb = AsyncMock()
        bus.subscribe_outbound(cb)
        bus.subscribe_outbound(cb)
        bus.unsubscribe_outbound(cb)
        assert cb not in bus._outbound_listeners
        assert len(bus._outbound_listeners) == 0

    def test_preserves_order_after_removal(self) -> None:
        bus = MessageBus()
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        cb3 = AsyncMock()
        bus.subscribe_outbound(cb1)
        bus.subscribe_outbound(cb2)
        bus.subscribe_outbound(cb3)
        bus.unsubscribe_outbound(cb2)
        assert bus._outbound_listeners == [cb1, cb3]


@pytest.mark.anyio
class TestMessageBusPublishOutbound:
    """Test publish_outbound dispatching and error handling."""

    async def test_dispatches_to_single_listener(self) -> None:
        bus = MessageBus()
        cb = AsyncMock()
        bus.subscribe_outbound(cb)
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="response",
        )
        await bus.publish_outbound(msg)
        cb.assert_awaited_once_with(msg)

    async def test_dispatches_to_multiple_listeners(self) -> None:
        bus = MessageBus()
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        cb3 = AsyncMock()
        bus.subscribe_outbound(cb1)
        bus.subscribe_outbound(cb2)
        bus.subscribe_outbound(cb3)
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="response",
        )
        await bus.publish_outbound(msg)
        cb1.assert_awaited_once_with(msg)
        cb2.assert_awaited_once_with(msg)
        cb3.assert_awaited_once_with(msg)

    async def test_no_listeners_does_not_raise(self) -> None:
        bus = MessageBus()
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="response",
        )
        # Should complete without error even with zero listeners.
        await bus.publish_outbound(msg)

    async def test_callback_exception_is_caught(self) -> None:
        """A failing callback should not prevent other callbacks from running."""
        bus = MessageBus()
        failing_cb = AsyncMock(side_effect=RuntimeError("boom"))
        ok_cb = AsyncMock()
        bus.subscribe_outbound(failing_cb)
        bus.subscribe_outbound(ok_cb)
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="response",
        )
        # Should not raise despite the first callback failing.
        await bus.publish_outbound(msg)
        ok_cb.assert_awaited_once_with(msg)

    async def test_callback_exception_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        bus = MessageBus()
        failing_cb = AsyncMock(side_effect=ValueError("bad value"))
        bus.subscribe_outbound(failing_cb)
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="response",
        )
        with caplog.at_level(logging.ERROR, logger="app.channels.message_bus"):
            await bus.publish_outbound(msg)
        assert any("Error in outbound callback" in r.message for r in caplog.records)
        assert any("channel=feishu" in r.message for r in caplog.records)

    async def test_multiple_failing_callbacks_all_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """All failing callbacks should be caught independently."""
        bus = MessageBus()
        cb1 = AsyncMock(side_effect=RuntimeError("err1"))
        cb2 = AsyncMock(side_effect=RuntimeError("err2"))
        bus.subscribe_outbound(cb1)
        bus.subscribe_outbound(cb2)
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="response",
        )
        with caplog.at_level(logging.ERROR, logger="app.channels.message_bus"):
            await bus.publish_outbound(msg)
        error_records = [r for r in caplog.records if "Error in outbound callback" in r.message]
        assert len(error_records) == 2

    async def test_failing_then_succeeding_both_called(self) -> None:
        """A failing callback should not prevent subsequent callbacks from running."""
        bus = MessageBus()
        cb1 = AsyncMock(side_effect=RuntimeError("fail"))
        cb2 = AsyncMock()
        cb3 = AsyncMock()
        bus.subscribe_outbound(cb1)
        bus.subscribe_outbound(cb2)
        bus.subscribe_outbound(cb3)
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="response",
        )
        await bus.publish_outbound(msg)
        cb2.assert_awaited_once_with(msg)
        cb3.assert_awaited_once_with(msg)

    async def test_logs_on_publish(self, caplog: pytest.LogCaptureFixture) -> None:
        bus = MessageBus()
        cb = AsyncMock()
        bus.subscribe_outbound(cb)
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="hello world",
        )
        with caplog.at_level(logging.INFO, logger="app.channels.message_bus"):
            await bus.publish_outbound(msg)
        assert any("outbound dispatching" in r.message for r in caplog.records)
        assert any("channel=feishu" in r.message for r in caplog.records)
        assert any("chat_id=c1" in r.message for r in caplog.records)
        assert any("listeners=1" in r.message for r in caplog.records)
        assert any("text_len=11" in r.message for r in caplog.records)

    async def test_empty_text_logs_zero_length(self, caplog: pytest.LogCaptureFixture) -> None:
        bus = MessageBus()
        bus.subscribe_outbound(AsyncMock())
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="",
        )
        with caplog.at_level(logging.INFO, logger="app.channels.message_bus"):
            await bus.publish_outbound(msg)
        assert any("text_len=0" in r.message for r in caplog.records)

    async def test_callback_receives_exact_message_object(self) -> None:
        """Callback receives the same OutboundMessage instance, not a copy."""
        bus = MessageBus()
        received: list[OutboundMessage] = []

        async def _capture(msg: OutboundMessage) -> None:
            received.append(msg)

        bus.subscribe_outbound(_capture)
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="test",
        )
        await bus.publish_outbound(msg)
        assert received[0] is msg

    async def test_unsubscribed_callback_not_called(self) -> None:
        """A callback that is unsubscribed before publish should not be called."""
        bus = MessageBus()
        cb = AsyncMock()
        bus.subscribe_outbound(cb)
        bus.unsubscribe_outbound(cb)
        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="test",
        )
        await bus.publish_outbound(msg)
        cb.assert_not_awaited()


# ---------------------------------------------------------------------------
# Type alias check
# ---------------------------------------------------------------------------


class TestOutboundCallbackTypeAlias:
    """Verify that the OutboundCallback type alias is correctly defined."""

    def test_outbound_callback_is_callable(self) -> None:
        # OutboundCallback is a type alias, so we can't directly test it at
        # runtime with typing.get_type_hints in a portable way, but we can
        # verify that a proper async function satisfies the protocol.
        async def valid_callback(msg: OutboundMessage) -> None:
            pass

        # Should be assignable to OutboundCallback without type errors.
        cb: OutboundCallback = valid_callback
        assert callable(cb)


# ---------------------------------------------------------------------------
# Integration: full round-trip through the bus
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestMessageBusIntegration:
    """End-to-end scenarios combining publish and consume paths."""

    async def test_inbound_round_trip(self) -> None:
        """Publish an inbound message, then consume it via get_inbound."""
        bus = MessageBus()
        original = InboundMessage(
            channel_name="feishu",
            chat_id="chat_42",
            user_id="user_7",
            text="What is the weather?",
            msg_type=InboundMessageType.CHAT,
            topic_id="weather_topic",
        )
        await bus.publish_inbound(original)
        consumed = await bus.get_inbound()
        assert consumed.channel_name == "feishu"
        assert consumed.chat_id == "chat_42"
        assert consumed.user_id == "user_7"
        assert consumed.text == "What is the weather?"
        assert consumed.topic_id == "weather_topic"
        assert bus.inbound_queue.empty()

    async def test_outbound_round_trip(self) -> None:
        """Publish an outbound message and verify all listeners receive it."""
        bus = MessageBus()
        received_by_cb1: list[OutboundMessage] = []
        received_by_cb2: list[OutboundMessage] = []

        async def cb1(msg: OutboundMessage) -> None:
            received_by_cb1.append(msg)

        async def cb2(msg: OutboundMessage) -> None:
            received_by_cb2.append(msg)

        bus.subscribe_outbound(cb1)
        bus.subscribe_outbound(cb2)

        outbound = OutboundMessage(
            channel_name="feishu",
            chat_id="chat_42",
            thread_id="thread_1",
            text="It is sunny today.",
            is_final=True,
        )
        await bus.publish_outbound(outbound)

        assert len(received_by_cb1) == 1
        assert len(received_by_cb2) == 1
        assert received_by_cb1[0].text == "It is sunny today."
        assert received_by_cb2[0].text == "It is sunny today."

    async def test_multiple_inbound_messages_consumed_in_order(self) -> None:
        """Publish several inbound messages and consume them all in FIFO order."""
        bus = MessageBus()
        texts = ["first", "second", "third"]
        for t in texts:
            await bus.publish_inbound(
                InboundMessage(
                    channel_name="slack",
                    chat_id="c1",
                    user_id="u1",
                    text=t,
                )
            )

        consumed = []
        for _ in texts:
            consumed.append(await bus.get_inbound())

        assert [m.text for m in consumed] == texts
        assert bus.inbound_queue.empty()

    async def test_outbound_with_failing_and_success_listeners(self) -> None:
        """Mix of failing and succeeding listeners: all get called, errors isolated."""
        bus = MessageBus()
        results: list[str] = []

        async def failing(msg: OutboundMessage) -> None:
            raise RuntimeError("listener crash")

        async def succeed_after(msg: OutboundMessage) -> None:
            results.append(msg.text)

        bus.subscribe_outbound(failing)
        bus.subscribe_outbound(succeed_after)

        msg = OutboundMessage(
            channel_name="feishu",
            chat_id="c1",
            thread_id="t1",
            text="important",
        )
        await bus.publish_outbound(msg)
        assert results == ["important"]
