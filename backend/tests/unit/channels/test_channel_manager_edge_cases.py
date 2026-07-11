"""Coverage-gap tests for app.channels.manager.

Each test targets a specific uncovered line or branch identified by the
coverage report.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.channels.manager import (
    DEFAULT_ASSISTANT_ID,
    THREAD_BUSY_MESSAGE,
    ChannelManager,
    _accumulate_stream_text,
    _extract_response_text,
    _ingest_inbound_files,
    _prepare_artifact_delivery,
    _read_wecom_inbound_file,
    _resolve_attachments,
)
from app.channels.message_bus import (
    InboundMessage,
    InboundMessageType,
    ResolvedAttachment,
)

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


def _make_manager(**overrides) -> ChannelManager:
    defaults: dict = {
        "bus": MagicMock(),
        "store": MagicMock(),
    }
    defaults.update(overrides)
    return ChannelManager(**defaults)


# ===========================================================================
# Lines 78-92: _read_wecom_inbound_file
# ===========================================================================


class TestReadWecomInboundFile:
    """Cover the _read_wecom_inbound_file function (lines 78-92)."""

    @pytest.mark.asyncio
    async def test_http_read_returns_none(self):
        """Line 78-80: propagate None when underlying HTTP read fails."""
        mock_client = MagicMock()
        with patch(
            "app.channels.manager._read_http_inbound_file",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await _read_wecom_inbound_file({"url": "http://x/f"}, mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_aeskey_returns_raw_data(self):
        """Lines 82-84: return raw data when aeskey is missing."""
        mock_client = MagicMock()
        with patch(
            "app.channels.manager._read_http_inbound_file",
            new_callable=AsyncMock,
            return_value=b"raw_bytes",
        ):
            result = await _read_wecom_inbound_file({"url": "http://x/f"}, mock_client)
        assert result == b"raw_bytes"

    @pytest.mark.asyncio
    async def test_aeskey_is_not_string_returns_raw(self):
        """Lines 82-84: non-string aeskey treated as missing."""
        mock_client = MagicMock()
        with patch(
            "app.channels.manager._read_http_inbound_file",
            new_callable=AsyncMock,
            return_value=b"raw",
        ):
            result = await _read_wecom_inbound_file(
                {"url": "http://x/f", "aeskey": 12345},
                mock_client,
            )
        assert result == b"raw"

    @pytest.mark.asyncio
    async def test_aeskey_present_decrypt_success(self):
        """Lines 86-92: successful decryption path."""
        mock_client = MagicMock()
        mock_decrypt = MagicMock(return_value=b"decrypted")
        mock_module = MagicMock()
        mock_module.decrypt_file = mock_decrypt

        with (
            patch(
                "app.channels.manager._read_http_inbound_file",
                new_callable=AsyncMock,
                return_value=b"cipher",
            ),
            patch.dict("sys.modules", {"aibot.crypto_utils": mock_module}),
        ):
            result = await _read_wecom_inbound_file(
                {"url": "http://x/f", "aeskey": "secretkey"},
                mock_client,
            )
        assert result == b"decrypted"
        mock_decrypt.assert_called_once_with(b"cipher", "secretkey")

    @pytest.mark.asyncio
    async def test_aeskey_present_import_failure(self):
        """Lines 86-90: return None when aibot.crypto_utils cannot be imported."""
        mock_client = MagicMock()

        import builtins

        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "aibot.crypto_utils":
                raise ImportError("no module")
            return original_import(name, *args, **kwargs)

        with (
            patch(
                "app.channels.manager._read_http_inbound_file",
                new_callable=AsyncMock,
                return_value=b"cipher",
            ),
            patch("builtins.__import__", side_effect=fake_import),
        ):
            result = await _read_wecom_inbound_file(
                {"url": "http://x/f", "aeskey": "key123"},
                mock_client,
            )
        assert result is None


# ===========================================================================
# Line 170: _extract_response_text — non-dict element in messages list
# ===========================================================================


class TestExtractResponseTextLine170:
    """Cover line 170: continue when msg in messages list is not a dict."""

    def test_non_dict_messages_skipped(self):
        messages = [
            "a plain string",
            42,
            None,
            {"type": "ai", "content": "found it"},
        ]
        assert _extract_response_text({"messages": messages}) == "found it"

    def test_all_non_dict_returns_empty(self):
        messages = ["str", 123, None, [1, 2]]
        assert _extract_response_text({"messages": messages}) == ""


# ===========================================================================
# Line 286: _accumulate_stream_text — kwargs content extraction
# ===========================================================================


class TestAccumulateStreamTextLine286:
    """Cover line 286: text extracted from payload['kwargs']['content']."""

    def test_kwargs_content_string(self):
        buffers = {}
        payload = {"type": "ai", "content": "", "kwargs": {"content": "from_kwargs"}}
        text, mid = _accumulate_stream_text(buffers, None, payload)
        assert text == "from_kwargs"

    def test_kwargs_content_list(self):
        buffers = {}
        payload = {
            "type": "ai",
            "content": "",
            "kwargs": {"content": [{"type": "text", "text": "block"}]},
        }
        text, mid = _accumulate_stream_text(buffers, None, payload)
        assert text == "block"

    def test_kwargs_content_empty_string_skipped(self):
        """When both content and kwargs.content are empty, returns None."""
        buffers = {}
        payload = {"type": "ai", "content": "", "kwargs": {"content": ""}}
        text, mid = _accumulate_stream_text(buffers, None, payload)
        assert text is None


# ===========================================================================
# Line 288: _accumulate_stream_text — no text at all returns None
# ===========================================================================


class TestAccumulateStreamTextLine288:
    """Cover line 288: return None when no text is extractable."""

    def test_ai_message_with_empty_content(self):
        buffers = {}
        payload = {"type": "ai", "content": ""}
        text, mid = _accumulate_stream_text(buffers, "m1", payload)
        assert text is None
        assert mid == "m1"

    def test_ai_message_with_none_content(self):
        buffers = {}
        payload = {"type": "ai", "content": None}
        text, mid = _accumulate_stream_text(buffers, None, payload)
        assert text is None


# ===========================================================================
# Lines 386-387: _resolve_attachments — ValueError/OSError exception handler
# ===========================================================================


class TestResolveAttachmentsLine386:
    """Cover lines 386-387: exception when resolving artifact path."""

    def test_value_error_during_resolve(self):
        """paths.resolve_virtual_path raises ValueError."""
        mock_paths = MagicMock()
        mock_paths.sandbox_outputs_dir.return_value = Path("/tmp/outputs")
        mock_paths.resolve_virtual_path.side_effect = ValueError("bad path")

        with (
            patch("ideer.config.paths.get_paths", return_value=mock_paths),
            patch("app.channels.manager.get_effective_user_id", return_value="u1"),
        ):
            result = _resolve_attachments("thread_1", ["/mnt/user-data/outputs/file.txt"])
        assert result == []

    def test_os_error_during_resolve(self):
        """paths.resolve_virtual_path raises OSError."""
        mock_paths = MagicMock()
        mock_paths.sandbox_outputs_dir.return_value = Path("/tmp/outputs")
        mock_paths.resolve_virtual_path.side_effect = OSError("disk error")

        with (
            patch("ideer.config.paths.get_paths", return_value=mock_paths),
            patch("app.channels.manager.get_effective_user_id", return_value="u1"),
        ):
            result = _resolve_attachments("thread_1", ["/mnt/user-data/outputs/file.txt"])
        assert result == []


# ===========================================================================
# Lines 412-413: _prepare_artifact_delivery — resolved attachment text
# ===========================================================================


class TestPrepareArtifactDeliveryLine412:
    """Cover lines 412-413: append resolved attachment filenames to text."""

    def test_resolved_attachments_text_appended(self):
        """When all artifacts resolve, their filenames are appended as text fallback."""
        resolved = [
            ResolvedAttachment(
                virtual_path="/mnt/user-data/outputs/report.pdf",
                actual_path=Path("/real/report.pdf"),
                filename="report.pdf",
                mime_type="application/pdf",
                size=1024,
                is_image=False,
            )
        ]
        with patch(
            "app.channels.manager._resolve_attachments",
            return_value=resolved,
        ):
            text, attachments = _prepare_artifact_delivery(
                "t1",
                "Here is your file.",
                ["/mnt/user-data/outputs/report.pdf"],
            )
        assert "report.pdf" in text
        assert len(attachments) == 1

    def test_resolved_and_unresolved_mix(self):
        """Both unresolved and resolved filenames appear in the text."""
        resolved = [
            ResolvedAttachment(
                virtual_path="/mnt/user-data/outputs/ok.txt",
                actual_path=Path("/real/ok.txt"),
                filename="ok.txt",
                mime_type="text/plain",
                size=100,
                is_image=False,
            )
        ]
        with patch(
            "app.channels.manager._resolve_attachments",
            return_value=resolved,
        ):
            text, attachments = _prepare_artifact_delivery(
                "t1",
                "",
                ["/mnt/user-data/outputs/ok.txt", "/mnt/user-data/outputs/missing.txt"],
            )
        assert "ok.txt" in text
        assert "missing.txt" in text


# ===========================================================================
# Line 438: _ingest_inbound_files — non-dict file entry
# ===========================================================================


class TestIngestInboundFilesLine438:
    """Cover line 438: skip non-dict entries in msg.files."""

    @pytest.mark.asyncio
    async def test_non_dict_file_skipped(self, tmp_path):
        """A file entry that is not a dict (e.g. a string) is skipped."""
        msg = _make_inbound(
            channel_name="slack",
            files=["not_a_dict", 42, None],
        )

        mock_uploads_dir = MagicMock()
        mock_uploads_dir.iterdir.return_value = []

        with (
            patch("ideer.uploads.manager.ensure_uploads_dir", return_value=mock_uploads_dir),
            patch.dict("app.channels.manager.INBOUND_FILE_READERS", {}, clear=False),
        ):
            result = await _ingest_inbound_files("thread_1", msg)
        assert result == []


# ===========================================================================
# Lines 462-465: _ingest_inbound_files — filename generation when empty
# ===========================================================================


class TestIngestInboundFilesLine462:
    """Cover lines 462-465: auto-generate filename when none provided."""

    @pytest.mark.asyncio
    async def test_image_file_generates_png_name(self, tmp_path):
        """Image type without filename generates .png extension."""
        msg = _make_inbound(
            channel_name="slack",
            thread_ts="ts_123",
            files=[{"type": "image", "url": "http://x/img"}],
        )

        mock_uploads_dir = MagicMock()
        mock_uploads_dir.iterdir.return_value = []

        async def mock_reader(file_info, client):
            return b"image_bytes"

        with (
            patch("ideer.uploads.manager.ensure_uploads_dir", return_value=mock_uploads_dir),
            patch("ideer.uploads.manager.normalize_filename", side_effect=lambda x: x),
            patch("ideer.uploads.manager.claim_unique_filename", side_effect=lambda name, seen: name),
            patch("ideer.uploads.manager.write_upload_file_no_symlink", side_effect=lambda d, n, b: d / n),
            patch.dict(
                "app.channels.manager.INBOUND_FILE_READERS",
                {"slack": mock_reader},
                clear=False,
            ),
        ):
            result = await _ingest_inbound_files("thread_1", msg)
        assert len(result) == 1
        assert result[0]["filename"].endswith(".png")

    @pytest.mark.asyncio
    async def test_non_image_file_generates_bin_name(self, tmp_path):
        """Non-image type without filename generates .bin extension."""
        msg = _make_inbound(
            channel_name="slack",
            thread_ts=None,
            files=[{"type": "file", "url": "http://x/doc"}],
        )

        mock_uploads_dir = MagicMock()
        mock_uploads_dir.iterdir.return_value = []

        async def mock_reader(file_info, client):
            return b"file_bytes"

        with (
            patch("ideer.uploads.manager.ensure_uploads_dir", return_value=mock_uploads_dir),
            patch("ideer.uploads.manager.normalize_filename", side_effect=lambda x: x),
            patch("ideer.uploads.manager.claim_unique_filename", side_effect=lambda name, seen: name),
            patch("ideer.uploads.manager.write_upload_file_no_symlink", side_effect=lambda d, n, b: d / n),
            patch.dict(
                "app.channels.manager.INBOUND_FILE_READERS",
                {"slack": mock_reader},
                clear=False,
            ),
        ):
            result = await _ingest_inbound_files("thread_1", msg)
        assert len(result) == 1
        assert result[0]["filename"].endswith(".bin")


# ===========================================================================
# Lines 469-475: _ingest_inbound_files — ValueError from claim_unique_filename
# ===========================================================================


class TestIngestInboundFilesLine469:
    """Cover lines 469-475: skip file when claim_unique_filename raises ValueError."""

    @pytest.mark.asyncio
    async def test_unsafe_filename_skipped(self, tmp_path):
        msg = _make_inbound(
            channel_name="slack",
            files=[{"type": "file", "filename": "bad/name.txt", "url": "http://x/f"}],
        )

        mock_uploads_dir = MagicMock()
        mock_uploads_dir.iterdir.return_value = []

        async def mock_reader(file_info, client):
            return b"data"

        with (
            patch("ideer.uploads.manager.ensure_uploads_dir", return_value=mock_uploads_dir),
            patch("ideer.uploads.manager.normalize_filename", return_value="bad/name.txt"),
            patch("ideer.uploads.manager.claim_unique_filename", side_effect=ValueError("unsafe")),
            patch.dict(
                "app.channels.manager.INBOUND_FILE_READERS",
                {"slack": mock_reader},
                clear=False,
            ),
        ):
            result = await _ingest_inbound_files("thread_1", msg)
        assert result == []


# ===========================================================================
# Lines 483-485: _ingest_inbound_files — generic Exception from write
# ===========================================================================


class TestIngestInboundFilesLine483:
    """Cover lines 483-485: skip file when write_upload_file_no_symlink raises."""

    @pytest.mark.asyncio
    async def test_write_failure_skipped(self, tmp_path):
        msg = _make_inbound(
            channel_name="slack",
            files=[{"type": "file", "filename": "ok.txt", "url": "http://x/f"}],
        )

        mock_uploads_dir = MagicMock()
        mock_uploads_dir.iterdir.return_value = []

        async def mock_reader(file_info, client):
            return b"data"

        with (
            patch("ideer.uploads.manager.ensure_uploads_dir", return_value=mock_uploads_dir),
            patch("ideer.uploads.manager.normalize_filename", return_value="ok.txt"),
            patch("ideer.uploads.manager.claim_unique_filename", return_value="ok.txt"),
            patch(
                "ideer.uploads.manager.write_upload_file_no_symlink",
                side_effect=RuntimeError("disk full"),
            ),
            patch.dict(
                "app.channels.manager.INBOUND_FILE_READERS",
                {"slack": mock_reader},
                clear=False,
            ),
        ):
            result = await _ingest_inbound_files("thread_1", msg)
        assert result == []


# ===========================================================================
# Line 582: _resolve_run_params — invalid assistant_id falls back
# ===========================================================================


class TestResolveRunParamsLine582:
    """Cover line 582: fallback when assistant_id is empty/whitespace/non-string."""

    def test_empty_assistant_id_falls_back(self):
        """An empty string assistant_id in the session chain falls back to default."""
        mgr = _make_manager(
            default_session={"assistant_id": "  "},
        )
        msg = _make_inbound()
        assistant_id, _, _ = mgr._resolve_run_params(msg, "thread_1")
        assert assistant_id == DEFAULT_ASSISTANT_ID

    def test_non_string_assistant_id_falls_back(self):
        """A non-string assistant_id (e.g. int) falls back to default."""
        mgr = _make_manager(
            default_session={"assistant_id": 123},
        )
        msg = _make_inbound()
        assistant_id, _, _ = mgr._resolve_run_params(msg, "thread_1")
        assert assistant_id == DEFAULT_ASSISTANT_ID


# ===========================================================================
# Line 593: _resolve_run_params — non-Mapping configurable
# ===========================================================================


class TestResolveRunParamsLine593:
    """Cover line 593: configurable is not a Mapping → empty dict."""

    def test_configurable_is_list(self):
        mgr = _make_manager(
            default_session={"config": {"configurable": [1, 2, 3]}},
        )
        msg = _make_inbound()
        _, run_config, _ = mgr._resolve_run_params(msg, "thread_1")
        assert run_config["configurable"] == {"checkpoint_ns": "", "thread_id": "thread_1"}

    def test_configurable_is_string(self):
        mgr = _make_manager(
            default_session={"config": {"configurable": "not_a_dict"}},
        )
        msg = _make_inbound()
        _, run_config, _ = mgr._resolve_run_params(msg, "thread_1")
        assert run_config["configurable"] == {"checkpoint_ns": "", "thread_id": "thread_1"}

    def test_configurable_is_none(self):
        mgr = _make_manager(
            default_session={"config": {"configurable": None}},
        )
        msg = _make_inbound()
        _, run_config, _ = mgr._resolve_run_params(msg, "thread_1")
        assert run_config["configurable"] == {"checkpoint_ns": "", "thread_id": "thread_1"}


# ===========================================================================
# Line 761: _handle_chat — uploaded files block prepended to text
# ===========================================================================


class TestHandleChatLine761:
    """Cover line 761: msg.text is updated with uploaded files block."""

    @pytest.mark.asyncio
    async def test_uploaded_files_block_prepended(self):
        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = "existing_thread"
        mock_client = MagicMock()
        mock_client.runs.wait = AsyncMock(
            return_value={
                "messages": [{"type": "ai", "content": "done"}],
            }
        )
        mgr._client = mock_client

        msg = _make_inbound(channel_name="slack", text="see attached")

        uploaded_files = [
            {"filename": "data.csv", "size": 512, "path": "/mnt/user-data/uploads/data.csv", "is_image": False},
        ]

        with (
            patch("app.channels.service.get_channel_service", return_value=None),
            patch(
                "app.channels.manager._ingest_inbound_files",
                new_callable=AsyncMock,
                return_value=uploaded_files,
            ),
            patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub,
        ):
            await mgr._handle_chat(msg)
            mock_pub.assert_called()
            # The agent should have received the uploaded files block in the input
            call_args = mock_client.runs.wait.call_args
            input_text = call_args[1]["input"]["messages"][0]["content"]
            assert "uploaded_files" in input_text
            assert "data.csv" in input_text


# ===========================================================================
# Line 790: _handle_chat — re-raise non-busy exceptions
# ===========================================================================


class TestHandleChatLine790:
    """Cover line 790: non-busy exceptions from runs.wait are re-raised."""

    @pytest.mark.asyncio
    async def test_non_busy_error_is_raised(self):
        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = "existing_thread"
        mock_client = MagicMock()
        mock_client.runs.wait = AsyncMock(side_effect=RuntimeError("server error"))
        mgr._client = mock_client

        msg = _make_inbound(channel_name="slack")

        with (
            patch("app.channels.service.get_channel_service", return_value=None),
            patch("app.channels.manager._ingest_inbound_files", new_callable=AsyncMock, return_value=[]),
            pytest.raises(RuntimeError, match="server error"),
        ):
            await mgr._handle_chat(msg)


# ===========================================================================
# Line 806: _handle_chat — response_text from artifacts when empty
# ===========================================================================


class TestHandleChatLine806:
    """Cover line 806: when response_text is empty but attachments exist."""

    @pytest.mark.asyncio
    async def test_empty_text_with_attachments_uses_artifact_text(self):
        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = "t1"
        mock_client = MagicMock()
        mock_client.runs.wait = AsyncMock(
            return_value={
                "messages": [
                    {"type": "human", "content": "q"},
                    {
                        "type": "ai",
                        "content": "",
                        "tool_calls": [
                            {
                                "name": "present_files",
                                "args": {"filepaths": ["/mnt/user-data/outputs/out.pdf"]},
                            }
                        ],
                    },
                ],
            }
        )
        mgr._client = mock_client

        mock_attachment = ResolvedAttachment(
            virtual_path="/mnt/user-data/outputs/out.pdf",
            actual_path=Path("/real/out.pdf"),
            filename="out.pdf",
            mime_type="application/pdf",
            size=2048,
            is_image=False,
        )

        msg = _make_inbound(channel_name="slack")

        with (
            patch("app.channels.service.get_channel_service", return_value=None),
            patch("app.channels.manager._ingest_inbound_files", new_callable=AsyncMock, return_value=[]),
            patch(
                "app.channels.manager._prepare_artifact_delivery",
                return_value=("", [mock_attachment]),
            ),
            patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub,
        ):
            await mgr._handle_chat(msg)
            outbound = mock_pub.call_args[0][0]
            assert "out.pdf" in outbound.text


# ===========================================================================
# Line 899: _handle_streaming_chat — error path with no attachments
# ===========================================================================


class TestHandleStreamingChatLine899:
    """Cover line 899: stream error, no attachments, busy error message."""

    @pytest.mark.asyncio
    async def test_stream_busy_error_no_attachments(self):
        mgr = _make_manager()
        mock_client = MagicMock()

        from langgraph_sdk.errors import ConflictError

        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.headers = {}
        mock_response.json.return_value = {"detail": "already running"}

        async def mock_stream(*args, **kwargs):
            raise ConflictError(
                message="already running",
                response=mock_response,
                body={"detail": "already running"},
            )
            yield  # pragma: no cover

        mock_client.runs.stream = mock_stream

        msg = _make_inbound(channel_name="feishu")

        with (
            patch("app.channels.service.get_channel_service", return_value=None),
            patch(
                "app.channels.manager._prepare_artifact_delivery",
                return_value=("", []),
            ),
            patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub,
        ):
            await mgr._handle_streaming_chat(
                mock_client,
                msg,
                "thread_1",
                "lead_agent",
                {},
                {},
            )
            final_msg = mock_pub.call_args_list[-1][0][0]
            assert THREAD_BUSY_MESSAGE in final_msg.text


# ===========================================================================
# Line 906: _handle_streaming_chat — no response fallback
# ===========================================================================


class TestHandleStreamingChatLine906:
    """Cover line 906: no text, no attachments, no error → fallback text."""

    @pytest.mark.asyncio
    async def test_no_text_no_error_fallback(self):
        mgr = _make_manager()
        mock_client = MagicMock()

        # Stream yields no useful data
        async def mock_stream(*args, **kwargs):
            # Yield nothing useful
            if False:
                yield  # pragma: no cover

        mock_client.runs.stream = mock_stream

        msg = _make_inbound(channel_name="feishu")

        with (
            patch("app.channels.service.get_channel_service", return_value=None),
            patch(
                "app.channels.manager._prepare_artifact_delivery",
                return_value=("", []),
            ),
            patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub,
        ):
            await mgr._handle_streaming_chat(
                mock_client,
                msg,
                "thread_1",
                "lead_agent",
                {},
                {},
            )
            final_msg = mock_pub.call_args_list[-1][0][0]
            # Falls back to "(No response from agent)"
            assert "No response" in final_msg.text or final_msg.text == ""


# ===========================================================================
# Line 906 (alternate): _handle_streaming_chat — non-busy error message
# ===========================================================================


class TestHandleStreamingChatLine906Alternate:
    """Cover the non-busy error branch (line 904) in the finally block."""

    @pytest.mark.asyncio
    async def test_non_busy_stream_error_message(self):
        mgr = _make_manager()
        mock_client = MagicMock()

        async def mock_stream(*args, **kwargs):
            raise RuntimeError("some other error")
            yield  # pragma: no cover

        mock_client.runs.stream = mock_stream

        msg = _make_inbound(channel_name="feishu")

        with (
            patch("app.channels.service.get_channel_service", return_value=None),
            patch(
                "app.channels.manager._prepare_artifact_delivery",
                return_value=("", []),
            ),
            patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub,
        ):
            await mgr._handle_streaming_chat(
                mock_client,
                msg,
                "thread_1",
                "lead_agent",
                {},
                {},
            )
            final_msg = mock_pub.call_args_list[-1][0][0]
            assert "error" in final_msg.text.lower()


# ===========================================================================
# Line 1011: _fetch_gateway — unknown kind fallback
# ===========================================================================


class TestFetchGatewayLine1011:
    """Cover line 1011: return str(data) for unknown kind values."""

    @pytest.mark.asyncio
    async def test_unknown_kind_returns_stringified_data(self):
        mgr = _make_manager()

        mock_response = MagicMock()
        mock_response.json.return_value = {"custom": "data"}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.channels.manager.httpx.AsyncClient", return_value=mock_ctx):
            result = await mgr._fetch_gateway("/api/custom", "custom_kind")
        assert "custom" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_models_empty_list(self):
        """models with empty list returns 'No models configured.'."""
        mgr = _make_manager()

        mock_response = MagicMock()
        mock_response.json.return_value = {"models": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.channels.manager.httpx.AsyncClient", return_value=mock_ctx):
            result = await mgr._fetch_gateway("/api/models", "models")
        assert "No models" in result


# ===========================================================================
# Additional coverage: _handle_chat with uploaded files and no agent response
# ===========================================================================


class TestHandleChatUploadedFilesNoResponse:
    """Cover the combination: uploaded files + empty agent response + no attachments."""

    @pytest.mark.asyncio
    async def test_uploaded_files_with_no_agent_response(self):
        mgr = _make_manager()
        mgr.store.get_thread_id.return_value = "t1"
        mock_client = MagicMock()
        mock_client.runs.wait = AsyncMock(return_value={})
        mgr._client = mock_client

        msg = _make_inbound(channel_name="slack", text="hello")

        uploaded_files = [
            {"filename": "doc.pdf", "size": 1024, "path": "/mnt/user-data/uploads/doc.pdf", "is_image": False},
        ]

        with (
            patch("app.channels.service.get_channel_service", return_value=None),
            patch(
                "app.channels.manager._ingest_inbound_files",
                new_callable=AsyncMock,
                return_value=uploaded_files,
            ),
            patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub,
        ):
            await mgr._handle_chat(msg)
            outbound = mock_pub.call_args[0][0]
            # Should have some fallback text
            assert outbound.text


# ===========================================================================
# Additional: _resolve_run_params with custom agent normalization
# ===========================================================================


class TestResolveRunParamsCustomAgent:
    """Cover the custom agent normalization path with user-level override."""

    def test_user_level_custom_agent(self):
        mgr = _make_manager(
            channel_sessions={
                "feishu": {
                    "users": {
                        "user_1": {"assistant_id": "special-bot"},
                    },
                },
            },
        )
        msg = _make_inbound(channel_name="feishu", user_id="user_1")
        assistant_id, _, run_context = mgr._resolve_run_params(msg, "thread_1")
        assert assistant_id == DEFAULT_ASSISTANT_ID
        assert run_context["agent_name"] == "special-bot"


# ===========================================================================
# Additional: _handle_command bootstrap without arguments
# ===========================================================================


class TestHandleCommandBootstrap:
    """Cover bootstrap command with no arguments (default text)."""

    @pytest.mark.asyncio
    async def test_bootstrap_no_args(self):
        mgr = _make_manager()
        msg = _make_inbound(msg_type=InboundMessageType.COMMAND, text="/bootstrap")

        with patch.object(mgr, "_handle_chat", new_callable=AsyncMock) as mock_chat:
            await mgr._handle_command(msg)
            chat_msg = mock_chat.call_args[0][0]
            assert chat_msg.text == "Initialize workspace"


# ===========================================================================
# Additional: _handle_streaming_chat with attachments in final message
# ===========================================================================


class TestHandleStreamingChatWithAttachments:
    """Cover streaming finalization when artifacts are present."""

    @pytest.mark.asyncio
    async def test_streaming_with_artifacts(self):
        mgr = _make_manager()
        mock_client = MagicMock()

        values_data = {
            "messages": [
                {"type": "human", "content": "q"},
                {
                    "type": "ai",
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "present_files",
                            "args": {"filepaths": ["/mnt/user-data/outputs/report.xlsx"]},
                        }
                    ],
                },
            ],
        }

        async def mock_stream(*args, **kwargs):
            yield SimpleNamespace(event="values", data=values_data)

        mock_client.runs.stream = mock_stream

        mock_attachment = ResolvedAttachment(
            virtual_path="/mnt/user-data/outputs/report.xlsx",
            actual_path=Path("/real/report.xlsx"),
            filename="report.xlsx",
            mime_type="application/vnd.ms-excel",
            size=4096,
            is_image=False,
        )

        msg = _make_inbound(channel_name="feishu")

        with (
            patch("app.channels.service.get_channel_service", return_value=None),
            patch(
                "app.channels.manager._prepare_artifact_delivery",
                return_value=("", [mock_attachment]),
            ),
            patch.object(mgr.bus, "publish_outbound", new_callable=AsyncMock) as mock_pub,
        ):
            await mgr._handle_streaming_chat(
                mock_client,
                msg,
                "thread_1",
                "lead_agent",
                {},
                {},
            )
            final_msg = mock_pub.call_args_list[-1][0][0]
            assert "report.xlsx" in final_msg.text


# ===========================================================================
# Additional: _ingest_inbound_files with reader exception
# ===========================================================================


class TestIngestInboundFilesReaderException:
    """Cover lines 444-451: file_reader raises an exception."""

    @pytest.mark.asyncio
    async def test_reader_exception_skips_file(self, tmp_path):
        msg = _make_inbound(
            channel_name="custom_channel",
            files=[{"type": "file", "filename": "test.txt", "url": "http://x/f"}],
        )

        mock_uploads_dir = MagicMock()
        mock_uploads_dir.iterdir.return_value = []

        async def bad_reader(file_info, client):
            raise ConnectionError("network down")

        with (
            patch("ideer.uploads.manager.ensure_uploads_dir", return_value=mock_uploads_dir),
            patch.dict(
                "app.channels.manager.INBOUND_FILE_READERS",
                {"custom_channel": bad_reader},
                clear=False,
            ),
        ):
            result = await _ingest_inbound_files("thread_1", msg)
        assert result == []


# ===========================================================================
# Additional: _ingest_inbound_files with no data returned
# ===========================================================================


class TestIngestInboundFilesNoData:
    """Cover lines 453-459: file_reader returns None."""

    @pytest.mark.asyncio
    async def test_reader_returns_none_skips_file(self, tmp_path):
        msg = _make_inbound(
            channel_name="custom_channel",
            files=[{"type": "file", "filename": "test.txt", "url": "http://x/f"}],
        )

        mock_uploads_dir = MagicMock()
        mock_uploads_dir.iterdir.return_value = []

        async def null_reader(file_info, client):
            return None

        with (
            patch("ideer.uploads.manager.ensure_uploads_dir", return_value=mock_uploads_dir),
            patch.dict(
                "app.channels.manager.INBOUND_FILE_READERS",
                {"custom_channel": null_reader},
                clear=False,
            ),
        ):
            result = await _ingest_inbound_files("thread_1", msg)
        assert result == []


# ===========================================================================
# Additional: _resolve_attachments — path escapes outputs dir
# ===========================================================================


class TestResolveAttachmentsPathEscape:
    """Cover line 369: resolved path escapes outputs directory."""

    def test_path_traversal_rejected(self):
        mock_paths = MagicMock()
        mock_outputs_dir = MagicMock()
        mock_outputs_dir.resolve.return_value = Path("/safe/outputs")
        mock_paths.sandbox_outputs_dir.return_value = mock_outputs_dir

        escape_path = MagicMock()
        escape_path.resolve.return_value.relative_to.side_effect = ValueError("not relative")
        mock_paths.resolve_virtual_path.return_value = escape_path

        with (
            patch("ideer.config.paths.get_paths", return_value=mock_paths),
            patch("app.channels.manager.get_effective_user_id", return_value="u1"),
        ):
            result = _resolve_attachments("thread_1", ["/mnt/user-data/outputs/../../etc/passwd"])
        assert result == []


# ===========================================================================
# Additional: _resolve_attachments — file not found
# ===========================================================================


class TestResolveAttachmentsFileNotFound:
    """Cover line 372: resolved file is not a file on disk."""

    def test_not_a_file_skipped(self):
        mock_paths = MagicMock()
        mock_outputs_dir = MagicMock()
        mock_outputs_dir.resolve.return_value = Path("/safe/outputs")
        mock_paths.sandbox_outputs_dir.return_value = mock_outputs_dir

        resolved_path = MagicMock()
        resolved_path.resolve.return_value.relative_to.return_value = Path("file.txt")
        resolved_path.is_file.return_value = False
        mock_paths.resolve_virtual_path.return_value = resolved_path

        with (
            patch("ideer.config.paths.get_paths", return_value=mock_paths),
            patch("app.channels.manager.get_effective_user_id", return_value="u1"),
        ):
            result = _resolve_attachments("thread_1", ["/mnt/user-data/outputs/file.txt"])
        assert result == []
