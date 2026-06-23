"""Tests for app.channels.manager — ChannelManager and related functions."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.channels.manager import (
    DEFAULT_ASSISTANT_ID,
    DEFAULT_LANGGRAPH_URL,
    ChannelManager,
    InvalidChannelSessionConfigError,
    _accumulate_stream_text,
    _as_dict,
    _extract_artifacts,
    _extract_response_text,
    _extract_stream_message_id,
    _extract_text_content,
    _format_artifact_text,
    _format_uploaded_files_block,
    _is_thread_busy_error,
    _merge_dicts,
    _merge_stream_text,
    _normalize_custom_agent_name,
    _read_http_inbound_file,
    _read_wechat_inbound_file,
    _slim_metadata,
)
from app.channels.message_bus import InboundMessage, InboundMessageType, MessageBus, OutboundMessage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_inbound(**overrides) -> InboundMessage:
    defaults = {
        "channel_name": "feishu",
        "chat_id": "chat_1",
        "user_id": "user_1",
        "text": "hello",
        "msg_type": InboundMessageType.CHAT,
        "thread_ts": "msg_1",
    }
    defaults.update(overrides)
    return InboundMessage(**defaults)


def _make_outbound(**overrides) -> OutboundMessage:
    defaults = {
        "channel_name": "feishu",
        "chat_id": "chat_1",
        "thread_id": "thread_1",
        "text": "response",
    }
    defaults.update(overrides)
    return OutboundMessage(**defaults)


def _make_manager(**overrides) -> ChannelManager:
    defaults = {
        "bus": MagicMock(),
        "store": MagicMock(),
    }
    defaults.update(overrides)
    return ChannelManager(**defaults)


# ---------------------------------------------------------------------------
# _slim_metadata
# ---------------------------------------------------------------------------


class TestSlimMetadata:
    def test_removes_raw_message(self):
        result = _slim_metadata({"key": "val", "raw_message": "big"})
        assert "raw_message" not in result
        assert result == {"key": "val"}

    def test_removes_ref_msg(self):
        result = _slim_metadata({"ref_msg": "data", "key": "val"})
        assert "ref_msg" not in result

    def test_keeps_other_keys(self):
        result = _slim_metadata({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_empty(self):
        result = _slim_metadata({})
        assert result == {}


# ---------------------------------------------------------------------------
# _as_dict
# ---------------------------------------------------------------------------


class TestAsDict:
    def test_with_mapping(self):
        assert _as_dict({"a": 1}) == {"a": 1}

    def test_with_non_mapping(self):
        assert _as_dict(None) == {}
        assert _as_dict("string") == {}
        assert _as_dict(42) == {}


# ---------------------------------------------------------------------------
# _merge_dicts
# ---------------------------------------------------------------------------


class TestMergeDicts:
    def test_basic_merge(self):
        result = _merge_dicts({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_later_overrides(self):
        result = _merge_dicts({"a": 1}, {"a": 2})
        assert result == {"a": 2}

    def test_non_mapping_skipped(self):
        result = _merge_dicts({"a": 1}, None, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_empty(self):
        result = _merge_dicts()
        assert result == {}


# ---------------------------------------------------------------------------
# _is_thread_busy_error
# ---------------------------------------------------------------------------


class TestIsThreadBusyError:
    def test_none(self):
        assert _is_thread_busy_error(None) is False

    def test_conflict_error(self):
        from langgraph_sdk.errors import ConflictError

        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.headers = {}
        mock_response.json.return_value = {"detail": "conflict"}
        exc = ConflictError(message="conflict", response=mock_response, body={"detail": "conflict"})
        assert _is_thread_busy_error(exc) is True

    def test_already_running(self):
        exc = RuntimeError("thread is already running a task")
        assert _is_thread_busy_error(exc) is True

    def test_other_error(self):
        exc = ValueError("something else")
        assert _is_thread_busy_error(exc) is False


# ---------------------------------------------------------------------------
# _normalize_custom_agent_name
# ---------------------------------------------------------------------------


class TestNormalizeCustomAgentName:
    def test_basic(self):
        assert _normalize_custom_agent_name("my-agent") == "my-agent"

    def test_with_underscores(self):
        assert _normalize_custom_agent_name("my_agent") == "my-agent"

    def test_uppercase(self):
        assert _normalize_custom_agent_name("MyAgent") == "myagent"

    def test_empty_raises(self):
        with pytest.raises(InvalidChannelSessionConfigError):
            _normalize_custom_agent_name("")

    def test_whitespace_only_raises(self):
        with pytest.raises(InvalidChannelSessionConfigError):
            _normalize_custom_agent_name("   ")

    def test_invalid_chars_raises(self):
        with pytest.raises(InvalidChannelSessionConfigError):
            _normalize_custom_agent_name("my agent!")

    def test_valid_chars(self):
        assert _normalize_custom_agent_name("Agent-123") == "agent-123"


# ---------------------------------------------------------------------------
# _extract_response_text
# ---------------------------------------------------------------------------


class TestExtractResponseText:
    def test_from_dict_with_messages(self):
        result = {
            "messages": [
                {"type": "human", "content": "question"},
                {"type": "ai", "content": "answer"},
            ]
        }
        assert _extract_response_text(result) == "answer"

    def test_from_list(self):
        result = [
            {"type": "human", "content": "q"},
            {"type": "ai", "content": "a"},
        ]
        assert _extract_response_text(result) == "a"

    def test_empty(self):
        assert _extract_response_text({}) == ""
        assert _extract_response_text([]) == ""

    def test_non_dict_list(self):
        assert _extract_response_text("invalid") == ""

    def test_content_as_list(self):
        result = {
            "messages": [
                {
                    "type": "ai",
                    "content": [
                        {"type": "text", "text": "hello"},
                        {"type": "text", "text": " world"},
                    ],
                },
            ]
        }
        assert _extract_response_text(result) == "hello world"

    def test_content_as_list_with_str(self):
        result = {
            "messages": [
                {"type": "ai", "content": ["hello", " world"]},
            ]
        }
        assert _extract_response_text(result) == "hello world"

    def test_tool_message_clarification(self):
        result = {
            "messages": [
                {"type": "human", "content": "q"},
                {"type": "tool", "name": "ask_clarification", "content": "Please clarify"},
            ]
        }
        assert _extract_response_text(result) == "Please clarify"

    def test_stops_at_human_message(self):
        result = {
            "messages": [
                {"type": "ai", "content": "old answer"},
                {"type": "human", "content": "new question"},
                {"type": "ai", "content": "new answer"},
            ]
        }
        assert _extract_response_text(result) == "new answer"


# ---------------------------------------------------------------------------
# _extract_text_content
# ---------------------------------------------------------------------------


class TestExtractTextContent:
    def test_string(self):
        assert _extract_text_content("hello") == "hello"

    def test_list_of_strings(self):
        assert _extract_text_content(["a", "b"]) == "ab"

    def test_list_of_dicts(self):
        assert _extract_text_content([{"text": "a"}, {"text": "b"}]) == "ab"

    def test_list_with_content_key(self):
        assert _extract_text_content([{"content": "nested"}]) == "nested"

    def test_dict_with_text(self):
        assert _extract_text_content({"text": "val"}) == "val"

    def test_dict_with_content(self):
        assert _extract_text_content({"content": "val"}) == "val"

    def test_empty(self):
        assert _extract_text_content(None) == ""
        assert _extract_text_content({}) == ""


# ---------------------------------------------------------------------------
# _merge_stream_text
# ---------------------------------------------------------------------------


class TestMergeStreamText:
    def test_empty_chunk(self):
        assert _merge_stream_text("existing", "") == "existing"

    def test_empty_existing(self):
        assert _merge_stream_text("", "chunk") == "chunk"

    def test_identical(self):
        assert _merge_stream_text("text", "text") == "text"

    def test_cumulative(self):
        assert _merge_stream_text("hel", "hello") == "hello"

    def test_duplicate_suffix(self):
        assert _merge_stream_text("hello", "lo") == "hello"

    def test_append(self):
        assert _merge_stream_text("hello", " world") == "hello world"


# ---------------------------------------------------------------------------
# _extract_stream_message_id
# ---------------------------------------------------------------------------


class TestExtractStreamMessageId:
    def test_from_payload(self):
        assert _extract_stream_message_id({"id": "msg_1"}, None) == "msg_1"

    def test_from_metadata(self):
        assert _extract_stream_message_id({}, {"id": "msg_2"}) == "msg_2"

    def test_from_kwargs(self):
        assert _extract_stream_message_id({"kwargs": {"message_id": "msg_3"}}, None) == "msg_3"

    def test_none(self):
        assert _extract_stream_message_id({}, {}) is None


# ---------------------------------------------------------------------------
# _accumulate_stream_text
# ---------------------------------------------------------------------------


class TestAccumulateStreamText:
    def test_string_payload(self):
        buffers = {}
        text, mid = _accumulate_stream_text(buffers, None, "hello")
        assert text == "hello"
        assert mid == "__default__"

    def test_dict_payload(self):
        buffers = {}
        payload = {"type": "ai", "content": "response"}
        text, mid = _accumulate_stream_text(buffers, None, payload)
        assert text == "response"

    def test_tool_payload_ignored(self):
        buffers = {}
        payload = {"type": "tool_call"}
        text, mid = _accumulate_stream_text(buffers, None, payload)
        assert text is None

    def test_tuple_payload(self):
        buffers = {}
        payload = ({"type": "ai", "content": "resp"}, {"id": "m1"})
        text, mid = _accumulate_stream_text(buffers, None, payload)
        assert text == "resp"
        assert mid == "m1"

    def test_non_mapping_payload(self):
        buffers = {}
        text, mid = _accumulate_stream_text(buffers, "m1", 123)
        assert text is None


# ---------------------------------------------------------------------------
# _extract_artifacts
# ---------------------------------------------------------------------------


class TestExtractArtifacts:
    def test_with_present_files(self):
        result = {
            "messages": [
                {"type": "human", "content": "q"},
                {"type": "ai", "tool_calls": [{"name": "present_files", "args": {"filepaths": ["/out/file1.txt", "/out/file2.txt"]}}]},
            ]
        }
        arts = _extract_artifacts(result)
        assert arts == ["/out/file1.txt", "/out/file2.txt"]

    def test_stops_at_human(self):
        result = {
            "messages": [
                {"type": "ai", "tool_calls": [{"name": "present_files", "args": {"filepaths": ["/old.txt"]}}]},
                {"type": "human", "content": "q"},
            ]
        }
        arts = _extract_artifacts(result)
        assert arts == []

    def test_empty(self):
        assert _extract_artifacts({}) == []

    def test_list_input(self):
        assert _extract_artifacts([{"type": "ai", "tool_calls": []}]) == []

    def test_invalid_input(self):
        assert _extract_artifacts("bad") == []


# ---------------------------------------------------------------------------
# _format_artifact_text
# ---------------------------------------------------------------------------


class TestFormatArtifactText:
    def test_single(self):
        result = _format_artifact_text(["/mnt/user-data/outputs/report.pdf"])
        assert "report.pdf" in result
        assert "Created File" in result

    def test_multiple(self):
        result = _format_artifact_text(["/a.txt", "/b.txt"])
        assert "Created Files" in result


# ---------------------------------------------------------------------------
# _format_uploaded_files_block
# ---------------------------------------------------------------------------


class TestFormatUploadedFilesBlock:
    def test_empty(self):
        result = _format_uploaded_files_block([])
        assert "(empty)" in result

    def test_with_files(self):
        files = [
            {"filename": "test.txt", "size": 2048, "path": "/mnt/user-data/uploads/test.txt", "is_image": False},
        ]
        result = _format_uploaded_files_block(files)
        assert "test.txt" in result
        assert "2.0 KB" in result

    def test_image_file(self):
        files = [
            {"filename": "photo.png", "size": 1024 * 1024, "path": "/mnt/user-data/uploads/photo.png", "is_image": True},
        ]
        result = _format_uploaded_files_block(files)
        assert "image" in result
        assert "1.0 MB" in result


# ---------------------------------------------------------------------------
# _read_http_inbound_file
# ---------------------------------------------------------------------------


class TestReadHttpInboundFile:
    @pytest.mark.asyncio
    async def test_success(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b"file_data"
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await _read_http_inbound_file({"url": "http://example.com/file.txt"}, mock_client)
        assert result == b"file_data"

    @pytest.mark.asyncio
    async def test_no_url(self):
        result = await _read_http_inbound_file({}, MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_non_string_url(self):
        result = await _read_http_inbound_file({"url": 123}, MagicMock())
        assert result is None


# ---------------------------------------------------------------------------
# _read_wechat_inbound_file
# ---------------------------------------------------------------------------


class TestReadWechatInboundFile:
    @pytest.mark.asyncio
    async def test_with_local_path(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"local_data")
        result = await _read_wechat_inbound_file({"path": str(test_file)}, MagicMock())
        assert result == b"local_data"

    @pytest.mark.asyncio
    async def test_with_full_url(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b"url_data"
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await _read_wechat_inbound_file({"full_url": "http://example.com/file.txt"}, mock_client)
        assert result == b"url_data"

    @pytest.mark.asyncio
    async def test_no_info(self):
        result = await _read_wechat_inbound_file({}, MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_local_path_not_found(self):
        result = await _read_wechat_inbound_file({"path": "/nonexistent/file.txt"}, MagicMock())
        assert result is None


# ---------------------------------------------------------------------------
# ChannelManager construction
# ---------------------------------------------------------------------------


class TestChannelManagerInit:
    def test_defaults(self):
        mgr = _make_manager()
        assert mgr._max_concurrency == 5
        assert mgr._langgraph_url == DEFAULT_LANGGRAPH_URL
        assert mgr._assistant_id == DEFAULT_ASSISTANT_ID
        assert mgr._running is False

    def test_custom_config(self):
        mgr = ChannelManager(
            bus=MagicMock(),
            store=MagicMock(),
            max_concurrency=10,
            langgraph_url="http://custom:9000/api",
            gateway_url="http://custom:9000",
            assistant_id="custom_agent",
        )
        assert mgr._max_concurrency == 10
        assert mgr._langgraph_url == "http://custom:9000/api"
        assert mgr._assistant_id == "custom_agent"


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------


class TestChannelManagerLifecycle:
    @pytest.mark.asyncio
    async def test_start(self):
        mgr = _make_manager()
        await mgr.start()
        assert mgr._running is True
        assert mgr._semaphore is not None
        assert mgr._task is not None
        await mgr.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        mgr = _make_manager()
        await mgr.start()
        task1 = mgr._task
        await mgr.start()
        assert mgr._task is task1
        await mgr.stop()

    @pytest.mark.asyncio
    async def test_stop(self):
        mgr = _make_manager()
        await mgr.start()
        await mgr.stop()
        assert mgr._running is False
        assert mgr._task is None


# ---------------------------------------------------------------------------
# _resolve_run_params
# ---------------------------------------------------------------------------


class TestResolveRunParams:
    def test_defaults(self):
        mgr = _make_manager()
        msg = _make_inbound()
        assistant_id, run_config, run_context = mgr._resolve_run_params(msg, "thread_1")
        assert assistant_id == DEFAULT_ASSISTANT_ID
        assert run_config["configurable"]["thread_id"] == "thread_1"
        assert run_context["thread_id"] == "thread_1"

    def test_custom_agent(self):
        mgr = _make_manager(default_session={"assistant_id": "my-agent"})
        msg = _make_inbound()
        assistant_id, run_config, run_context = mgr._resolve_run_params(msg, "thread_1")
        assert assistant_id == DEFAULT_ASSISTANT_ID
        assert run_context.get("agent_name") == "my-agent"

    def test_channel_session_override(self):
        mgr = _make_manager(
            channel_sessions={"feishu": {"assistant_id": "channel-agent"}},
        )
        msg = _make_inbound(channel_name="feishu")
        assistant_id, _, run_context = mgr._resolve_run_params(msg, "thread_1")
        assert assistant_id == DEFAULT_ASSISTANT_ID
        assert run_context.get("agent_name") == "channel-agent"

    def test_user_session_override(self):
        mgr = _make_manager(
            channel_sessions={"feishu": {"users": {"user_1": {"assistant_id": "user-agent"}}}},
        )
        msg = _make_inbound(channel_name="feishu", user_id="user_1")
        assistant_id, _, run_context = mgr._resolve_run_params(msg, "thread_1")
        assert run_context.get("agent_name") == "user-agent"


# ---------------------------------------------------------------------------
# _channel_supports_streaming
# ---------------------------------------------------------------------------


class TestChannelSupportsStreaming:
    def test_known_streaming_channel(self):
        with patch("app.channels.service.get_channel_service", return_value=None):
            assert ChannelManager._channel_supports_streaming("feishu") is True

    def test_known_non_streaming(self):
        with patch("app.channels.service.get_channel_service", return_value=None):
            assert ChannelManager._channel_supports_streaming("slack") is False

    def test_unknown_channel(self):
        with patch("app.channels.service.get_channel_service", return_value=None):
            assert ChannelManager._channel_supports_streaming("unknown") is False

    def test_service_channel(self):
        mock_channel = MagicMock()
        mock_channel.supports_streaming = True
        mock_service = MagicMock()
        mock_service.get_channel.return_value = mock_channel
        with patch("app.channels.service.get_channel_service", return_value=mock_service):
            assert ChannelManager._channel_supports_streaming("custom") is True


# ---------------------------------------------------------------------------
# _dispatch_loop
# ---------------------------------------------------------------------------


class TestDispatchLoop:
    @pytest.mark.asyncio
    async def test_dispatch_loop_processes_messages(self):
        """Test that the dispatch loop receives and dispatches inbound messages."""
        bus = MessageBus()
        store = MagicMock()
        store.get_thread_id.return_value = None
        mgr = ChannelManager(bus=bus, store=store, max_concurrency=1)

        msg = _make_inbound()
        await bus.publish_inbound(msg)

        handled = []

        async def track_handler(m):
            handled.append(m)

        with patch.object(mgr, "_handle_message", side_effect=track_handler):
            await mgr.start()
            # Give the dispatch loop time to pick up the message
            for _ in range(100):
                if handled:
                    break
                await asyncio.sleep(0.05)
            await mgr.stop()
            assert len(handled) == 1


# ---------------------------------------------------------------------------
# _handle_message
# ---------------------------------------------------------------------------


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_chat_message(self):
        mgr = _make_manager()
        mgr._semaphore = asyncio.Semaphore(1)
        msg = _make_inbound(msg_type=InboundMessageType.CHAT)

        with patch.object(mgr, "_handle_chat", new_callable=AsyncMock) as mock_chat:
            await mgr._handle_message(msg)
            mock_chat.assert_called_once_with(msg)

    @pytest.mark.asyncio
    async def test_command_message(self):
        mgr = _make_manager()
        mgr._semaphore = asyncio.Semaphore(1)
        msg = _make_inbound(msg_type=InboundMessageType.COMMAND, text="/help")

        with patch.object(mgr, "_handle_command", new_callable=AsyncMock) as mock_cmd:
            await mgr._handle_message(msg)
            mock_cmd.assert_called_once_with(msg)

    @pytest.mark.asyncio
    async def test_invalid_config_error(self):
        mgr = _make_manager()
        mgr._semaphore = asyncio.Semaphore(1)
        msg = _make_inbound()

        with patch.object(mgr, "_handle_chat", new_callable=AsyncMock, side_effect=InvalidChannelSessionConfigError("bad")):
            with patch.object(mgr, "_send_error", new_callable=AsyncMock) as mock_err:
                await mgr._handle_message(msg)
                mock_err.assert_called_once()

    @pytest.mark.asyncio
    async def test_generic_exception(self):
        mgr = _make_manager()
        mgr._semaphore = asyncio.Semaphore(1)
        msg = _make_inbound()

        with patch.object(mgr, "_handle_chat", new_callable=AsyncMock, side_effect=RuntimeError("unexpected")):
            with patch.object(mgr, "_send_error", new_callable=AsyncMock) as mock_err:
                await mgr._handle_message(msg)
                mock_err.assert_called_once()


# ---------------------------------------------------------------------------
# _handle_command
# ---------------------------------------------------------------------------


class TestHandleCommand:
    @pytest.mark.asyncio
    async def test_help_command(self):
        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = "thread_1"
        msg = _make_inbound(msg_type=InboundMessageType.COMMAND, text="/help")

        with patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub:
            await mgr._handle_command(msg)
            outbound = mock_pub.call_args[0][0]
            assert "Available commands" in outbound.text

    @pytest.mark.asyncio
    async def test_new_command(self):
        mgr = _make_manager()
        mock_client = MagicMock()
        mock_client.threads.create = AsyncMock(return_value={"thread_id": "new_thread"})
        mgr._client = mock_client
        msg = _make_inbound(msg_type=InboundMessageType.COMMAND, text="/new")

        with patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub:
            await mgr._handle_command(msg)
            outbound = mock_pub.call_args[0][0]
            assert "New conversation" in outbound.text

    @pytest.mark.asyncio
    async def test_status_command_with_thread(self):
        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = "thread_1"
        msg = _make_inbound(msg_type=InboundMessageType.COMMAND, text="/status")

        with patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub:
            await mgr._handle_command(msg)
            outbound = mock_pub.call_args[0][0]
            assert "thread_1" in outbound.text

    @pytest.mark.asyncio
    async def test_status_command_no_thread(self):
        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = None
        msg = _make_inbound(msg_type=InboundMessageType.COMMAND, text="/status")

        with patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub:
            await mgr._handle_command(msg)
            outbound = mock_pub.call_args[0][0]
            assert "No active" in outbound.text

    @pytest.mark.asyncio
    async def test_unknown_command(self):
        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = None
        msg = _make_inbound(msg_type=InboundMessageType.COMMAND, text="/unknown")

        with patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub:
            await mgr._handle_command(msg)
            outbound = mock_pub.call_args[0][0]
            assert "Unknown command" in outbound.text

    @pytest.mark.asyncio
    async def test_models_command(self):
        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = None

        with patch.object(mgr, "_fetch_gateway", new_callable=AsyncMock, return_value="model list"):
            msg = _make_inbound(msg_type=InboundMessageType.COMMAND, text="/models")
            with patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub:
                await mgr._handle_command(msg)
                outbound = mock_pub.call_args[0][0]
                assert "model list" in outbound.text

    @pytest.mark.asyncio
    async def test_memory_command(self):
        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = None

        with patch.object(mgr, "_fetch_gateway", new_callable=AsyncMock, return_value="memory info"):
            msg = _make_inbound(msg_type=InboundMessageType.COMMAND, text="/memory")
            with patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub:
                await mgr._handle_command(msg)
                outbound = mock_pub.call_args[0][0]
                assert "memory info" in outbound.text

    @pytest.mark.asyncio
    async def test_bootstrap_command(self):
        mgr = _make_manager()
        msg = _make_inbound(msg_type=InboundMessageType.COMMAND, text="/bootstrap init workspace")

        with patch.object(mgr, "_handle_chat", new_callable=AsyncMock) as mock_chat:
            await mgr._handle_command(msg)
            chat_msg = mock_chat.call_args[0][0]
            assert chat_msg.text == "init workspace"


# ---------------------------------------------------------------------------
# _fetch_gateway
# ---------------------------------------------------------------------------


class TestFetchGateway:
    @pytest.mark.asyncio
    async def test_fetch_models(self):
        mgr = _make_manager()
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "gpt-4"}, {"name": "claude"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("app.channels.manager.httpx.AsyncClient", return_value=mock_client):
            result = await mgr._fetch_gateway("/api/models", "models")
            assert "gpt-4" in result

    @pytest.mark.asyncio
    async def test_fetch_memory(self):
        mgr = _make_manager()
        mock_response = MagicMock()
        mock_response.json.return_value = {"facts": ["fact1", "fact2"]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("app.channels.manager.httpx.AsyncClient", return_value=mock_client):
            result = await mgr._fetch_gateway("/api/memory", "memory")
            assert "2" in result

    @pytest.mark.asyncio
    async def test_fetch_failure(self):
        mgr = _make_manager()

        # Create a mock that acts as an async context manager
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(side_effect=RuntimeError("network error"))
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.channels.manager.httpx.AsyncClient", return_value=mock_ctx):
            result = await mgr._fetch_gateway("/api/models", "models")
            assert "Failed" in result


# ---------------------------------------------------------------------------
# _send_error
# ---------------------------------------------------------------------------


class TestSendError:
    @pytest.mark.asyncio
    async def test_sends_error(self):
        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = "thread_1"
        msg = _make_inbound()

        with patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub:
            await mgr._send_error(msg, "Something went wrong")
            outbound = mock_pub.call_args[0][0]
            assert outbound.text == "Something went wrong"


# ---------------------------------------------------------------------------
# _create_thread
# ---------------------------------------------------------------------------


class TestCreateThread:
    @pytest.mark.asyncio
    async def test_creates_thread(self):
        mgr = _make_manager()
        mock_client = MagicMock()
        mock_client.threads.create = AsyncMock(return_value={"thread_id": "new_thread_123"})
        msg = _make_inbound()

        thread_id = await mgr._create_thread(mock_client, msg)
        assert thread_id == "new_thread_123"
        mgr.store.set_thread_id.assert_called_once()


# ---------------------------------------------------------------------------
# _log_task_error (static)
# ---------------------------------------------------------------------------


class TestLogTaskError:
    def test_cancelled(self):
        task = MagicMock()
        task.cancelled.return_value = True
        ChannelManager._log_task_error(task)

    def test_with_exception(self):
        task = MagicMock()
        task.cancelled.return_value = False
        task.exception.return_value = RuntimeError("error")
        ChannelManager._log_task_error(task)

    def test_no_exception(self):
        task = MagicMock()
        task.cancelled.return_value = False
        task.exception.return_value = None
        ChannelManager._log_task_error(task)


# ---------------------------------------------------------------------------
# _handle_chat (non-streaming path)
# ---------------------------------------------------------------------------


class TestHandleChat:
    @pytest.mark.asyncio
    async def test_chat_creates_thread(self):
        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = None
        mock_client = MagicMock()
        mock_client.threads.create = AsyncMock(return_value={"thread_id": "new_t"})
        mock_client.runs.wait = AsyncMock(
            return_value={
                "messages": [
                    {"type": "human", "content": "hi"},
                    {"type": "ai", "content": "hello back"},
                ]
            }
        )
        mgr._client = mock_client

        msg = _make_inbound(channel_name="slack")  # non-streaming

        with patch("app.channels.service.get_channel_service", return_value=None):
            with patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub:
                await mgr._handle_chat(msg)
                mock_pub.assert_called()
                outbound = mock_pub.call_args[0][0]
                assert "hello back" in outbound.text

    @pytest.mark.asyncio
    async def test_chat_reuses_thread(self):
        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = "existing_thread"
        mock_client = MagicMock()
        mock_client.runs.wait = AsyncMock(
            return_value={
                "messages": [
                    {"type": "ai", "content": "response"},
                ]
            }
        )
        mgr._client = mock_client

        msg = _make_inbound(channel_name="slack")

        with patch("app.channels.service.get_channel_service", return_value=None):
            with patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub:
                await mgr._handle_chat(msg)
                outbound = mock_pub.call_args[0][0]
                assert "response" in outbound.text

    @pytest.mark.asyncio
    async def test_chat_thread_busy(self):
        from langgraph_sdk.errors import ConflictError

        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = "existing_thread"
        mock_client = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.headers = {}
        mock_response.json.return_value = {"detail": "already running"}
        mock_client.runs.wait = AsyncMock(side_effect=ConflictError(message="already running", response=mock_response, body={"detail": "already running"}))
        mgr._client = mock_client

        msg = _make_inbound(channel_name="slack")

        with patch("app.channels.service.get_channel_service", return_value=None):
            with patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub:
                await mgr._handle_chat(msg)
                outbound = mock_pub.call_args[0][0]
                assert "already processing" in outbound.text

    @pytest.mark.asyncio
    async def test_chat_empty_response(self):
        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = "t"
        mock_client = MagicMock()
        mock_client.runs.wait = AsyncMock(return_value={})
        mgr._client = mock_client

        msg = _make_inbound(channel_name="slack")

        with patch("app.channels.service.get_channel_service", return_value=None):
            with patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub:
                await mgr._handle_chat(msg)
                outbound = mock_pub.call_args[0][0]
                assert outbound.text  # Should have some fallback text


# ---------------------------------------------------------------------------
# _handle_streaming_chat
# ---------------------------------------------------------------------------


class TestHandleStreamingChat:
    @pytest.mark.asyncio
    async def test_streaming_basic(self):
        mgr = _make_manager()
        mock_client = MagicMock()
        mgr._client = mock_client

        chunks = [
            SimpleNamespace(event="messages-tuple", data=("hel", {"id": "m1"})),
            SimpleNamespace(event="messages-tuple", data=("hello", {"id": "m1"})),
            SimpleNamespace(event="values", data={"messages": [{"type": "ai", "content": "hello"}]}),
        ]

        async def mock_stream(*args, **kwargs):
            for chunk in chunks:
                yield chunk

        mock_client.runs.stream = mock_stream

        msg = _make_inbound(channel_name="feishu")

        with patch("app.channels.service.get_channel_service", return_value=None):
            with patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub:
                await mgr._handle_streaming_chat(mock_client, msg, "thread_1", "lead_agent", {}, {})
                # Should have published at least the final message
                assert mock_pub.call_count >= 1
                last_call = mock_pub.call_args_list[-1][0][0]
                assert last_call.is_final is True

    @pytest.mark.asyncio
    async def test_streaming_with_error(self):
        mgr = _make_manager()
        mock_client = MagicMock()
        mgr._client = mock_client

        async def mock_stream(*args, **kwargs):
            raise RuntimeError("stream error")
            yield  # Make it an async generator

        mock_client.runs.stream = mock_stream

        msg = _make_inbound(channel_name="feishu")

        with patch("app.channels.service.get_channel_service", return_value=None):
            with patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub:
                await mgr._handle_streaming_chat(mock_client, msg, "thread_1", "lead_agent", {}, {})
                assert mock_pub.call_count >= 1


# ---------------------------------------------------------------------------
# Edge cases for helper functions
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_extract_response_text_non_dict_in_messages(self):
        result = {"messages": [None, "string", {"type": "ai", "content": "ok"}]}
        assert _extract_response_text(result) == "ok"

    def test_accumulate_stream_with_list_data(self):
        buffers = {}
        text, mid = _accumulate_stream_text(buffers, None, [{"type": "ai", "content": "hi"}])
        assert text == "hi"

    def test_extract_artifacts_mixed_messages(self):
        result = {
            "messages": [
                "not_a_dict",
                {
                    "type": "ai",
                    "tool_calls": [
                        {"name": "present_files", "args": {"filepaths": ["/a.txt"]}},
                        {"name": "other_tool", "args": {}},
                    ],
                },
            ]
        }
        arts = _extract_artifacts(result)
        assert "/a.txt" in arts

    def test_merge_stream_both_empty(self):
        assert _merge_stream_text("", "") == ""

    def test_extract_text_content_none(self):
        assert _extract_text_content(None) == ""

    def test_format_uploaded_files_no_size(self):
        files = [{"filename": "empty.txt", "size": 0, "path": "/p", "is_image": False}]
        result = _format_uploaded_files_block(files)
        assert "empty.txt" in result
