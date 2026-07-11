"""Tests to boost coverage for modules with highest missed lines.

Covers uncovered code paths in:
- app/channels/manager.py
- app/gateway/routers/agents.py
- app/gateway/routers/auth.py
- app/gateway/routers/memory.py
- app/gateway/routers/thread_runs.py
- app/gateway/routers/feedback.py
- app/gateway/routers/suggestions.py
- app/gateway/routers/mcp.py
- app/gateway/services.py
- app/gateway/deps.py
- app/gateway/csrf_middleware.py
- ideer/mcp/cache.py
- ideer/mcp/oauth.py
- ideer/models/credential_loader.py
- ideer/tools/tools.py
- ideer/tools/registry.py
- ideer/utils/time.py
- ideer/utils/readability.py
- ideer/utils/file_conversion.py
- ideer/runtime/serialization.py
- ideer/skills/parser.py
- ideer/skills/validation.py
- ideer/skills/installer.py
- ideer/skills/storage/local_skill_storage.py
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# app/channels/manager.py — _read_http_inbound_file, _read_wecom_inbound_file,
# _read_wechat_inbound_file, register_inbound_file_reader, _extract_text_content,
# _merge_stream_text, _accumulate_stream_text, _extract_stream_message_id,
# _extract_artifacts, _format_artifact_text, _format_uploaded_files_block
# ---------------------------------------------------------------------------


class TestReadHttpInboundFile:
    """Tests for _read_http_inbound_file."""

    @pytest.mark.asyncio
    async def test_missing_url(self):
        from app.channels.manager import _read_http_inbound_file

        result = await _read_http_inbound_file({}, AsyncMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_url(self):
        from app.channels.manager import _read_http_inbound_file

        result = await _read_http_inbound_file({"url": ""}, AsyncMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_non_string_url(self):
        from app.channels.manager import _read_http_inbound_file

        result = await _read_http_inbound_file({"url": 123}, AsyncMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        from app.channels.manager import _read_http_inbound_file

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.content = b"file data"
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        result = await _read_http_inbound_file({"url": "http://example.com/file"}, mock_client)
        assert result == b"file data"


class TestReadWechatInboundFile:
    """Tests for _read_wechat_inbound_file."""

    @pytest.mark.asyncio
    async def test_no_data(self):
        from app.channels.manager import _read_wechat_inbound_file

        result = await _read_wechat_inbound_file({}, AsyncMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_local_path(self):
        from app.channels.manager import _read_wechat_inbound_file

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test data")
            path = f.name
        try:
            result = await _read_wechat_inbound_file({"path": path}, AsyncMock())
            assert result == b"test data"
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_local_path_not_found(self):
        from app.channels.manager import _read_wechat_inbound_file

        result = await _read_wechat_inbound_file({"path": "/nonexistent/file.txt"}, AsyncMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_local_path_whitespace(self):
        from app.channels.manager import _read_wechat_inbound_file

        result = await _read_wechat_inbound_file({"path": "  "}, AsyncMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_full_url(self):
        from app.channels.manager import _read_wechat_inbound_file

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.content = b"url data"
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        result = await _read_wechat_inbound_file({"full_url": "http://example.com/file"}, mock_client)
        assert result == b"url data"


class TestReadWecomInboundFile:
    """Tests for _read_wecom_inbound_file."""

    @pytest.mark.asyncio
    async def test_no_data(self):
        from app.channels.manager import _read_wecom_inbound_file

        result = await _read_wecom_inbound_file({}, AsyncMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_no_aeskey(self):
        from app.channels.manager import _read_wecom_inbound_file

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.content = b"raw data"
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        result = await _read_wecom_inbound_file({"url": "http://example.com/file"}, mock_client)
        assert result == b"raw data"

    @pytest.mark.asyncio
    async def test_with_aeskey_import_fails(self):
        from app.channels.manager import _read_wecom_inbound_file

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.content = b"encrypted"
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        # When aibot.crypto_utils is not available
        with patch.dict("sys.modules", {"aibot.crypto_utils": None}):
            result = await _read_wecom_inbound_file(
                {"url": "http://example.com/file", "aeskey": "key123"},
                mock_client,
            )
            assert result is None


class TestRegisterInboundFileReader:
    def test_register_and_retrieve(self):
        from app.channels.manager import INBOUND_FILE_READERS

        original = INBOUND_FILE_READERS.get("test_channel")
        try:

            async def test_reader(file_info, client):
                return b"test"

            from app.channels.manager import register_inbound_file_reader

            register_inbound_file_reader("test_channel", test_reader)
            assert INBOUND_FILE_READERS["test_channel"] is test_reader
        finally:
            if original is not None:
                INBOUND_FILE_READERS["test_channel"] = original
            else:
                INBOUND_FILE_READERS.pop("test_channel", None)


class TestExtractTextContent:
    """Tests for _extract_text_content."""

    def test_string(self):
        from app.channels.manager import _extract_text_content

        assert _extract_text_content("hello") == "hello"

    def test_list_of_strings(self):
        from app.channels.manager import _extract_text_content

        assert _extract_text_content(["a", "b"]) == "ab"

    def test_list_of_dicts_with_text(self):
        from app.channels.manager import _extract_text_content

        assert _extract_text_content([{"type": "text", "text": "hello"}]) == "hello"

    def test_list_of_dicts_with_content(self):
        from app.channels.manager import _extract_text_content

        assert _extract_text_content([{"type": "text", "content": "hello"}]) == "hello"

    def test_list_of_dicts_without_text(self):
        from app.channels.manager import _extract_text_content

        assert _extract_text_content([{"type": "other"}]) == ""

    def test_mapping_with_text(self):
        from app.channels.manager import _extract_text_content

        assert _extract_text_content({"text": "hello"}) == "hello"

    def test_mapping_with_content(self):
        from app.channels.manager import _extract_text_content

        assert _extract_text_content({"content": "hello"}) == "hello"

    def test_none(self):
        from app.channels.manager import _extract_text_content

        assert _extract_text_content(None) == ""

    def test_int(self):
        from app.channels.manager import _extract_text_content

        assert _extract_text_content(42) == ""

    def test_list_of_non_string_non_mapping(self):
        from app.channels.manager import _extract_text_content

        assert _extract_text_content([1, 2, 3]) == ""


class TestMergeStreamText:
    """Tests for _merge_stream_text."""

    def test_empty_chunk(self):
        from app.channels.manager import _merge_stream_text

        assert _merge_stream_text("existing", "") == "existing"

    def test_empty_existing(self):
        from app.channels.manager import _merge_stream_text

        assert _merge_stream_text("", "new") == "new"

    def test_chunk_equals_existing(self):
        from app.channels.manager import _merge_stream_text

        assert _merge_stream_text("text", "text") == "text"

    def test_chunk_starts_with_existing(self):
        from app.channels.manager import _merge_stream_text

        assert _merge_stream_text("hel", "hello") == "hello"

    def test_existing_ends_with_chunk(self):
        from app.channels.manager import _merge_stream_text

        assert _merge_stream_text("hello", "llo") == "hello"

    def test_concat(self):
        from app.channels.manager import _merge_stream_text

        assert _merge_stream_text("hel", "lo") == "hello"

    def test_both_empty(self):
        from app.channels.manager import _merge_stream_text

        assert _merge_stream_text("", "") == ""


class TestExtractStreamMessageId:
    """Tests for _extract_stream_message_id."""

    def test_from_payload_id(self):
        from app.channels.manager import _extract_stream_message_id

        assert _extract_stream_message_id({"id": "msg1"}, None) == "msg1"

    def test_from_payload_message_id(self):
        from app.channels.manager import _extract_stream_message_id

        assert _extract_stream_message_id({"message_id": "msg2"}, None) == "msg2"

    def test_from_metadata(self):
        from app.channels.manager import _extract_stream_message_id

        assert _extract_stream_message_id({}, {"id": "meta_id"}) == "meta_id"

    def test_from_kwargs(self):
        from app.channels.manager import _extract_stream_message_id

        assert _extract_stream_message_id({"kwargs": {"id": "kw_id"}}, None) == "kw_id"

    def test_none(self):
        from app.channels.manager import _extract_stream_message_id

        assert _extract_stream_message_id(None, None) is None

    def test_empty(self):
        from app.channels.manager import _extract_stream_message_id

        assert _extract_stream_message_id({}, {}) is None


class TestFormatArtifactText:
    """Tests for _format_artifact_text."""

    def test_single_file(self):
        from app.channels.manager import _format_artifact_text

        result = _format_artifact_text(["/mnt/user-data/outputs/file.pdf"])
        assert "Created File:" in result
        assert "file.pdf" in result

    def test_multiple_files(self):
        from app.channels.manager import _format_artifact_text

        result = _format_artifact_text(
            [
                "/mnt/user-data/outputs/a.pdf",
                "/mnt/user-data/outputs/b.pdf",
            ]
        )
        assert "Created Files:" in result
        assert "a.pdf" in result
        assert "b.pdf" in result


class TestFormatUploadedFilesBlock:
    """Tests for _format_uploaded_files_block."""

    def test_empty_files(self):
        from app.channels.manager import _format_uploaded_files_block

        result = _format_uploaded_files_block([])
        assert "(empty)" in result

    def test_with_files(self):
        from app.channels.manager import _format_uploaded_files_block

        files = [{"filename": "test.txt", "size": 1024, "path": "/path/test.txt", "is_image": False}]
        result = _format_uploaded_files_block(files)
        assert "test.txt" in result
        assert "1.0 KB" in result
        assert "file" in result

    def test_image_file(self):
        from app.channels.manager import _format_uploaded_files_block

        files = [{"filename": "img.png", "size": 500, "path": "/path/img.png", "is_image": True}]
        result = _format_uploaded_files_block(files)
        assert "image" in result

    def test_large_file(self):
        from app.channels.manager import _format_uploaded_files_block

        files = [{"filename": "big.bin", "size": 2 * 1024 * 1024, "path": "/path/big.bin", "is_image": False}]
        result = _format_uploaded_files_block(files)
        assert "MB" in result


class TestPrepareArtifactDelivery:
    """Tests for _prepare_artifact_delivery."""

    def test_no_artifacts(self):
        from app.channels.manager import _prepare_artifact_delivery

        text, attachments = _prepare_artifact_delivery("t1", "response", [])
        assert text == "response"
        assert attachments == []

    @patch("app.channels.manager._resolve_attachments", return_value=[])
    def test_unresolved_artifacts(self, mock_resolve):
        from app.channels.manager import _prepare_artifact_delivery

        text, attachments = _prepare_artifact_delivery("t1", "response", ["/mnt/user-data/outputs/file.pdf"])
        assert "file.pdf" in text

    @patch("app.channels.manager._resolve_attachments")
    def test_resolved_artifacts(self, mock_resolve):
        from app.channels.manager import ResolvedAttachment, _prepare_artifact_delivery

        mock_resolve.return_value = [
            ResolvedAttachment(
                virtual_path="/mnt/user-data/outputs/file.pdf",
                actual_path=Path("/tmp/file.pdf"),
                filename="file.pdf",
                mime_type="application/pdf",
                size=100,
                is_image=False,
            )
        ]
        text, attachments = _prepare_artifact_delivery("t1", "response", ["/mnt/user-data/outputs/file.pdf"])
        assert len(attachments) == 1
        assert "file.pdf" in text


class TestAccumulateStreamText:
    """Tests for _accumulate_stream_text."""

    def test_string_payload(self):
        from app.channels.manager import _accumulate_stream_text

        buffers = {}
        text, msg_id = _accumulate_stream_text(buffers, None, "hello")
        assert text == "hello"
        assert msg_id == "__default__"

    def test_string_payload_with_existing_id(self):
        from app.channels.manager import _accumulate_stream_text

        buffers = {}
        text, msg_id = _accumulate_stream_text(buffers, "existing_id", "hello")
        assert text == "hello"
        assert msg_id == "existing_id"

    def test_non_mapping_payload(self):
        from app.channels.manager import _accumulate_stream_text

        buffers = {}
        text, msg_id = _accumulate_stream_text(buffers, None, 42)
        assert text is None

    def test_tool_message(self):
        from app.channels.manager import _accumulate_stream_text

        buffers = {}
        payload = {"type": "tool", "content": "tool output"}
        text, msg_id = _accumulate_stream_text(buffers, None, payload)
        assert text is None

    def test_ai_message_with_content(self):
        from app.channels.manager import _accumulate_stream_text

        buffers = {}
        payload = {"type": "ai", "content": "hello"}
        text, msg_id = _accumulate_stream_text(buffers, None, payload)
        assert text == "hello"

    def test_ai_message_with_kwargs_content(self):
        from app.channels.manager import _accumulate_stream_text

        buffers = {}
        payload = {"type": "ai", "kwargs": {"content": "from kwargs"}}
        text, msg_id = _accumulate_stream_text(buffers, None, payload)
        assert text == "from kwargs"

    def test_tuple_payload(self):
        from app.channels.manager import _accumulate_stream_text

        buffers = {}
        payload = {"type": "ai", "content": "hello"}
        text, msg_id = _accumulate_stream_text(buffers, None, (payload, {"id": "msg1"}))
        assert text == "hello"
        assert msg_id == "msg1"

    def test_empty_tuple(self):
        from app.channels.manager import _accumulate_stream_text

        buffers = {}
        text, msg_id = _accumulate_stream_text(buffers, None, ())
        assert text is None


class TestExtractArtifacts:
    """Tests for _extract_artifacts."""

    def test_list_input(self):
        from app.channels.manager import _extract_artifacts

        messages = [
            {"type": "human", "content": "q"},
            {"type": "ai", "content": "a", "tool_calls": [{"name": "present_files", "args": {"filepaths": ["/mnt/user-data/outputs/file.pdf"]}}]},
        ]
        result = _extract_artifacts(messages)
        assert "/mnt/user-data/outputs/file.pdf" in result

    def test_dict_input(self):
        from app.channels.manager import _extract_artifacts

        result = _extract_artifacts(
            {
                "messages": [
                    {"type": "human", "content": "q"},
                    {"type": "ai", "content": "a", "tool_calls": [{"name": "present_files", "args": {"filepaths": ["/mnt/user-data/outputs/out.png"]}}]},
                ]
            }
        )
        assert "/mnt/user-data/outputs/out.png" in result

    def test_invalid_input(self):
        from app.channels.manager import _extract_artifacts

        assert _extract_artifacts("invalid") == []

    def test_non_dict_messages(self):
        from app.channels.manager import _extract_artifacts

        result = _extract_artifacts([None, 42, "str"])
        assert result == []

    def test_no_tool_calls(self):
        from app.channels.manager import _extract_artifacts

        result = _extract_artifacts(
            [
                {"type": "ai", "content": "hello", "tool_calls": []},
            ]
        )
        assert result == []

    def test_non_present_files_tool(self):
        from app.channels.manager import _extract_artifacts

        result = _extract_artifacts(
            [
                {"type": "ai", "content": "hello", "tool_calls": [{"name": "other_tool", "args": {}}]},
            ]
        )
        assert result == []


# ---------------------------------------------------------------------------
# app/gateway/routers/suggestions.py — _strip_markdown_code_fence,
# _parse_json_string_list, _extract_response_text, _format_conversation
# ---------------------------------------------------------------------------


class TestSuggestionsHelpers:
    """Tests for suggestion helper functions."""

    def test_strip_markdown_code_fence(self):
        from app.gateway.routers.suggestions import _strip_markdown_code_fence

        assert _strip_markdown_code_fence('```json\n["q1"]\n```') == '["q1"]'
        assert _strip_markdown_code_fence("no fence") == "no fence"
        assert _strip_markdown_code_fence("```single") == "```single"

    def test_parse_json_string_list(self):
        from app.gateway.routers.suggestions import _parse_json_string_list

        assert _parse_json_string_list('["q1", "q2"]') == ["q1", "q2"]
        assert _parse_json_string_list("not json") is None
        assert _parse_json_string_list('{"key": "value"}') is None
        assert _parse_json_string_list("") is None
        assert _parse_json_string_list('["q1", "", "q2"]') == ["q1", "q2"]
        assert _parse_json_string_list("[1, 2, 3]") == []

    def test_parse_json_with_code_fence(self):
        from app.gateway.routers.suggestions import _parse_json_string_list

        assert _parse_json_string_list('```\n["q1"]\n```') == ["q1"]

    def test_extract_response_text_str(self):
        from app.gateway.routers.suggestions import _extract_response_text

        assert _extract_response_text("hello") == "hello"

    def test_extract_response_text_list(self):
        from app.gateway.routers.suggestions import _extract_response_text

        result = _extract_response_text(
            [
                {"type": "text", "text": "hello"},
                {"type": "output_text", "text": "world"},
                {"type": "other"},
            ]
        )
        assert "hello" in result
        assert "world" in result

    def test_extract_response_text_none(self):
        from app.gateway.routers.suggestions import _extract_response_text

        assert _extract_response_text(None) == ""

    def test_extract_response_text_int(self):
        from app.gateway.routers.suggestions import _extract_response_text

        assert _extract_response_text(42) == "42"

    def test_format_conversation(self):
        from app.gateway.routers.suggestions import SuggestionMessage, _format_conversation

        messages = [
            SuggestionMessage(role="user", content="Hello"),
            SuggestionMessage(role="assistant", content="Hi!"),
            SuggestionMessage(role="human", content="Bye"),
            SuggestionMessage(role="ai", content="Goodbye"),
        ]
        result = _format_conversation(messages)
        assert "User: Hello" in result
        assert "Assistant: Hi!" in result
        assert "User: Bye" in result
        assert "Assistant: Goodbye" in result

    def test_format_conversation_unknown_role(self):
        from app.gateway.routers.suggestions import SuggestionMessage, _format_conversation

        messages = [SuggestionMessage(role="system", content="System message")]
        result = _format_conversation(messages)
        assert "system: System message" in result


# ---------------------------------------------------------------------------
# app/gateway/csrf_middleware.py — helpers
# ---------------------------------------------------------------------------


class TestCSRFMiddlewareHelpers:
    def test_should_check_csrf_get(self):
        from app.gateway.csrf_middleware import should_check_csrf

        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/test"
        assert should_check_csrf(request) is False

    def test_should_check_csrf_post(self):
        from app.gateway.csrf_middleware import should_check_csrf

        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/test"
        assert should_check_csrf(request) is True

    def test_should_check_csrf_me_exempt(self):
        from app.gateway.csrf_middleware import should_check_csrf

        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/v1/auth/me"
        assert should_check_csrf(request) is False

    def test_is_auth_endpoint(self):
        from app.gateway.csrf_middleware import is_auth_endpoint

        request = MagicMock()
        request.url.path = "/api/v1/auth/login/local"
        assert is_auth_endpoint(request) is True

        request.url.path = "/api/test"
        assert is_auth_endpoint(request) is False

    def test_normalize_origin_valid(self):
        from app.gateway.csrf_middleware import _normalize_origin

        assert _normalize_origin("https://example.com") == "https://example.com"
        assert _normalize_origin("http://example.com:8080") == "http://example.com:8080"
        assert _normalize_origin("https://example.com:443") == "https://example.com"

    def test_normalize_origin_invalid(self):
        from app.gateway.csrf_middleware import _normalize_origin

        assert _normalize_origin("") is None
        assert _normalize_origin("not-a-url") is None
        assert _normalize_origin("ftp://example.com") is None

    def test_normalize_origin_with_path(self):
        from app.gateway.csrf_middleware import _normalize_origin

        assert _normalize_origin("https://example.com/path") is None

    def test_normalize_origin_with_query(self):
        from app.gateway.csrf_middleware import _normalize_origin

        assert _normalize_origin("https://example.com?q=1") is None

    def test_host_with_optional_port_default_http(self):
        from app.gateway.csrf_middleware import _host_with_optional_port

        assert _host_with_optional_port("example.com", 80, "http") == "example.com"

    def test_host_with_optional_port_default_https(self):
        from app.gateway.csrf_middleware import _host_with_optional_port

        assert _host_with_optional_port("example.com", 443, "https") == "example.com"

    def test_host_with_optional_port_custom(self):
        from app.gateway.csrf_middleware import _host_with_optional_port

        assert _host_with_optional_port("example.com", 8080, "http") == "example.com:8080"

    def test_host_with_optional_port_none(self):
        from app.gateway.csrf_middleware import _host_with_optional_port

        assert _host_with_optional_port("example.com", None, "http") == "example.com"

    def test_host_ipv6(self):
        from app.gateway.csrf_middleware import _host_with_optional_port

        result = _host_with_optional_port("::1", 8080, "http")
        assert "[::1]:8080" == result

    def test_first_header_value(self):
        from app.gateway.csrf_middleware import _first_header_value

        assert _first_header_value("first, second") == "first"
        assert _first_header_value("") is None
        assert _first_header_value(None) is None

    def test_configured_cors_origins_empty(self):
        from app.gateway.csrf_middleware import _configured_cors_origins

        with patch.dict(os.environ, {"GATEWAY_CORS_ORIGINS": ""}, clear=False):
            result = _configured_cors_origins()
            assert isinstance(result, set)

    def test_configured_cors_origins_star(self):
        from app.gateway.csrf_middleware import _configured_cors_origins

        with patch.dict(os.environ, {"GATEWAY_CORS_ORIGINS": "*"}, clear=False):
            result = _configured_cors_origins()
            assert len(result) == 0

    def test_is_allowed_auth_origin_no_origin(self):
        from app.gateway.csrf_middleware import is_allowed_auth_origin

        request = MagicMock()
        request.headers = {}
        assert is_allowed_auth_origin(request) is True

    def test_is_allowed_auth_origin_bad_origin(self):
        from app.gateway.csrf_middleware import is_allowed_auth_origin

        request = MagicMock()
        request.headers = {"origin": "not-a-url"}
        assert is_allowed_auth_origin(request) is False

    def test_is_allowed_auth_origin_same_origin(self):
        from app.gateway.csrf_middleware import is_allowed_auth_origin

        request = MagicMock()
        request.headers = {"origin": "https://example.com", "host": "example.com"}
        request.url.scheme = "https"
        request.url.netloc = "example.com"
        assert is_allowed_auth_origin(request) is True

    def test_forwarded_param(self):
        from app.gateway.csrf_middleware import _forwarded_param

        request = MagicMock()
        request.headers = {"forwarded": "proto=https;host=example.com"}
        assert _forwarded_param(request, "proto") == "https"
        assert _forwarded_param(request, "host") == "example.com"

    def test_forwarded_param_no_header(self):
        from app.gateway.csrf_middleware import _forwarded_param

        request = MagicMock()
        request.headers = {}
        assert _forwarded_param(request, "proto") is None

    def test_get_csrf_token(self):
        from app.gateway.csrf_middleware import get_csrf_token

        request = MagicMock()
        request.cookies = {"csrf_token": "my_token"}
        assert get_csrf_token(request) == "my_token"

    def test_get_csrf_token_missing(self):
        from app.gateway.csrf_middleware import get_csrf_token

        request = MagicMock()
        request.cookies = {}
        assert get_csrf_token(request) is None


# ---------------------------------------------------------------------------
# app/gateway/services.py — format_sse, normalize_stream_modes, normalize_input
# ---------------------------------------------------------------------------


class TestFormatSse:
    def test_basic(self):
        from app.gateway.services import format_sse

        result = format_sse("message", {"text": "hello"})
        assert "event: message" in result
        assert "data:" in result
        assert '"text": "hello"' in result

    def test_with_event_id(self):
        from app.gateway.services import format_sse

        result = format_sse("message", {"text": "hello"}, event_id="123")
        assert "id: 123" in result


class TestNormalizeStreamModes:
    def test_none(self):
        from app.gateway.services import normalize_stream_modes

        assert normalize_stream_modes(None) == ["values"]

    def test_string(self):
        from app.gateway.services import normalize_stream_modes

        assert normalize_stream_modes("messages") == ["messages"]

    def test_list(self):
        from app.gateway.services import normalize_stream_modes

        assert normalize_stream_modes(["values", "messages-tuple"]) == ["values", "messages-tuple"]

    def test_empty_list(self):
        from app.gateway.services import normalize_stream_modes

        assert normalize_stream_modes([]) == ["values"]

    def test_empty_string(self):
        from app.gateway.services import normalize_stream_modes

        # Empty string is a str, so isinstance branch returns [""]
        assert normalize_stream_modes("") == [""]


class TestNormalizeInput:
    def test_none(self):
        from app.gateway.services import normalize_input

        assert normalize_input(None) == {}

    def test_empty(self):
        from app.gateway.services import normalize_input

        assert normalize_input({}) == {}

    def test_with_messages(self):
        from app.gateway.services import normalize_input

        result = normalize_input({"messages": [{"role": "human", "content": "hello"}]})
        assert "messages" in result

    def test_without_messages(self):
        from app.gateway.services import normalize_input

        result = normalize_input({"key": "value"})
        assert "key" in result


# ---------------------------------------------------------------------------
# app/gateway/deps.py — _require, get_config, get_store, get_current_user
# ---------------------------------------------------------------------------


class TestDeps:
    def test_require_with_value(self):
        from app.gateway.deps import _require

        dep = _require("stream_bridge", "Stream bridge")
        mock_request = MagicMock()
        mock_request.app.state.stream_bridge = "bridge"
        assert dep(mock_request) == "bridge"

    def test_require_with_none(self):
        from app.gateway.deps import _require

        dep = _require("stream_bridge", "Stream bridge")
        mock_request = MagicMock()
        mock_request.app.state.stream_bridge = None
        with pytest.raises(Exception) as exc_info:
            dep(mock_request)
        assert "503" in str(exc_info.value.status_code) or exc_info.value.status_code == 503

    def test_get_store_with_value(self):
        from app.gateway.deps import get_store

        mock_request = MagicMock()
        mock_request.app.state.store = "store"
        assert get_store(mock_request) == "store"

    def test_get_store_with_none(self):
        from app.gateway.deps import get_store

        mock_request = MagicMock()
        mock_request.app.state.store = None
        assert get_store(mock_request) is None

    def test_get_store_missing(self):
        from app.gateway.deps import get_store

        mock_request = MagicMock(spec=[])
        mock_request.app = SimpleNamespace(state=SimpleNamespace())
        assert get_store(mock_request) is None


# ---------------------------------------------------------------------------
# app/gateway/routers/mcp.py — _mask_server_config, _merge_preserving_secrets
# ---------------------------------------------------------------------------


class TestMCPRouterHelpers:
    def test_mask_server_config(self):
        from app.gateway.routers.mcp import McpServerConfigResponse, _mask_server_config

        server = McpServerConfigResponse(
            env={"TOKEN": "secret123"},
            headers={"Authorization": "Bearer token"},
            oauth=None,
        )
        masked = _mask_server_config(server)
        assert masked.env["TOKEN"] == "***"
        assert masked.headers["Authorization"] == "***"

    def test_mask_server_config_with_oauth(self):
        from app.gateway.routers.mcp import McpOAuthConfigResponse, McpServerConfigResponse, _mask_server_config

        oauth = McpOAuthConfigResponse(client_secret="secret", refresh_token="refresh")
        server = McpServerConfigResponse(oauth=oauth)
        masked = _mask_server_config(server)
        assert masked.oauth.client_secret is None
        assert masked.oauth.refresh_token is None

    def test_merge_preserving_secrets_env(self):
        from app.gateway.routers.mcp import McpServerConfigResponse, _merge_preserving_secrets

        existing = McpServerConfigResponse(env={"TOKEN": "real_secret"})
        incoming = McpServerConfigResponse(env={"TOKEN": "***"})
        merged = _merge_preserving_secrets(incoming, existing)
        assert merged.env["TOKEN"] == "real_secret"

    def test_merge_preserving_secrets_new_key_masked(self):
        from app.gateway.routers.mcp import McpServerConfigResponse, _merge_preserving_secrets

        existing = McpServerConfigResponse(env={})
        incoming = McpServerConfigResponse(env={"NEW_KEY": "***"})
        with pytest.raises(Exception) as exc_info:
            _merge_preserving_secrets(incoming, existing)
        assert exc_info.value.status_code == 400

    def test_merge_preserving_secrets_headers(self):
        from app.gateway.routers.mcp import McpServerConfigResponse, _merge_preserving_secrets

        existing = McpServerConfigResponse(headers={"Auth": "real"})
        incoming = McpServerConfigResponse(headers={"Auth": "***"})
        merged = _merge_preserving_secrets(incoming, existing)
        assert merged.headers["Auth"] == "real"

    def test_merge_preserving_secrets_new_header_masked(self):
        from app.gateway.routers.mcp import McpServerConfigResponse, _merge_preserving_secrets

        existing = McpServerConfigResponse(headers={})
        incoming = McpServerConfigResponse(headers={"New": "***"})
        with pytest.raises(Exception) as exc_info:
            _merge_preserving_secrets(incoming, existing)
        assert exc_info.value.status_code == 400

    def test_merge_preserving_secrets_oauth(self):
        from app.gateway.routers.mcp import McpOAuthConfigResponse, McpServerConfigResponse, _merge_preserving_secrets

        existing_oauth = McpOAuthConfigResponse(client_secret="real_secret", refresh_token="real_refresh")
        existing = McpServerConfigResponse(oauth=existing_oauth)
        incoming_oauth = McpOAuthConfigResponse(client_secret=None, refresh_token=None)
        incoming = McpServerConfigResponse(oauth=incoming_oauth)
        merged = _merge_preserving_secrets(incoming, existing)
        assert merged.oauth.client_secret == "real_secret"
        assert merged.oauth.refresh_token == "real_refresh"

    def test_merge_preserving_secrets_oauth_explicit_clear(self):
        from app.gateway.routers.mcp import McpOAuthConfigResponse, McpServerConfigResponse, _merge_preserving_secrets

        existing_oauth = McpOAuthConfigResponse(client_secret="real_secret")
        existing = McpServerConfigResponse(oauth=existing_oauth)
        incoming_oauth = McpOAuthConfigResponse(client_secret="")
        incoming = McpServerConfigResponse(oauth=incoming_oauth)
        merged = _merge_preserving_secrets(incoming, existing)
        assert merged.oauth.client_secret is None


# ---------------------------------------------------------------------------
# ideer/utils/time.py — now_iso, coerce_iso
# ---------------------------------------------------------------------------


class TestTimeUtils:
    def test_now_iso(self):
        from ideer.utils.time import now_iso

        result = now_iso()
        assert isinstance(result, str)
        assert "T" in result

    def test_coerce_iso_none(self):
        from ideer.utils.time import coerce_iso

        assert coerce_iso(None) == ""

    def test_coerce_iso_empty_string(self):
        from ideer.utils.time import coerce_iso

        assert coerce_iso("") == ""

    def test_coerce_iso_bool(self):
        from ideer.utils.time import coerce_iso

        assert coerce_iso(True) == "True"
        assert coerce_iso(False) == "False"

    def test_coerce_iso_datetime(self):
        from ideer.utils.time import coerce_iso

        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        result = coerce_iso(dt)
        assert "2024-01-15" in result

    def test_coerce_iso_datetime_naive(self):
        from ideer.utils.time import coerce_iso

        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = coerce_iso(dt)
        assert "2024-01-15" in result

    def test_coerce_iso_int(self):
        from ideer.utils.time import coerce_iso

        result = coerce_iso(1705312200)
        assert "2024" in result

    def test_coerce_iso_float(self):
        from ideer.utils.time import coerce_iso

        result = coerce_iso(1705312200.5)
        assert "2024" in result

    def test_coerce_iso_unix_string(self):
        from ideer.utils.time import coerce_iso

        result = coerce_iso("1705312200")
        assert "2024" in result

    def test_coerce_iso_iso_string(self):
        from ideer.utils.time import coerce_iso

        result = coerce_iso("2024-01-15T10:30:00+00:00")
        assert result == "2024-01-15T10:30:00+00:00"

    def test_coerce_iso_other_type(self):
        from ideer.utils.time import coerce_iso

        assert coerce_iso([1, 2, 3]) == "[1, 2, 3]"

    def test_coerce_iso_overflow(self):
        from ideer.utils.time import coerce_iso

        result = coerce_iso(99999999999999999)
        # Should fallback to str()
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# ideer/runtime/serialization.py — serialize_lc_object, serialize_channel_values,
# serialize_messages_tuple, serialize
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_serialize_lc_object_none(self):
        from ideer.runtime.serialization import serialize_lc_object

        assert serialize_lc_object(None) is None

    def test_serialize_lc_object_str(self):
        from ideer.runtime.serialization import serialize_lc_object

        assert serialize_lc_object("hello") == "hello"

    def test_serialize_lc_object_int(self):
        from ideer.runtime.serialization import serialize_lc_object

        assert serialize_lc_object(42) == 42

    def test_serialize_lc_object_float(self):
        from ideer.runtime.serialization import serialize_lc_object

        assert serialize_lc_object(3.14) == 3.14

    def test_serialize_lc_object_bool(self):
        from ideer.runtime.serialization import serialize_lc_object

        assert serialize_lc_object(True) is True

    def test_serialize_lc_object_dict(self):
        from ideer.runtime.serialization import serialize_lc_object

        assert serialize_lc_object({"a": 1}) == {"a": 1}

    def test_serialize_lc_object_list(self):
        from ideer.runtime.serialization import serialize_lc_object

        assert serialize_lc_object([1, 2, 3]) == [1, 2, 3]

    def test_serialize_lc_object_tuple(self):
        from ideer.runtime.serialization import serialize_lc_object

        assert serialize_lc_object((1, 2)) == [1, 2]

    def test_serialize_lc_object_pydantic_v2(self):
        from ideer.runtime.serialization import serialize_lc_object

        mock_obj = MagicMock()
        mock_obj.model_dump.return_value = {"key": "value"}
        del mock_obj.dict  # Ensure model_dump is used
        assert serialize_lc_object(mock_obj) == {"key": "value"}

    def test_serialize_lc_object_pydantic_v1(self):
        from ideer.runtime.serialization import serialize_lc_object

        mock_obj = MagicMock(spec=["dict"])
        mock_obj.dict.return_value = {"key": "value"}
        assert serialize_lc_object(mock_obj) == {"key": "value"}

    def test_serialize_lc_object_fallback(self):
        from ideer.runtime.serialization import serialize_lc_object

        class Custom:
            def __str__(self):
                return "custom"

        result = serialize_lc_object(Custom())
        assert result == "custom"

    def test_serialize_channel_values(self):
        from ideer.runtime.serialization import serialize_channel_values

        result = serialize_channel_values({"messages": [1, 2], "__pregel_meta": "x", "__interrupt__": True})
        assert "messages" in result
        assert "__pregel_meta" not in result
        assert "__interrupt__" not in result

    def test_serialize_messages_tuple(self):
        from ideer.runtime.serialization import serialize_messages_tuple

        result = serialize_messages_tuple(("hello", {"id": "1"}))
        assert result == ["hello", {"id": "1"}]

    def test_serialize_messages_tuple_non_tuple(self):
        from ideer.runtime.serialization import serialize_messages_tuple

        result = serialize_messages_tuple("hello")
        assert result == "hello"

    def test_serialize_mode_messages(self):
        from ideer.runtime.serialization import serialize

        result = serialize(("hello", {}), mode="messages")
        assert result == ["hello", {}]

    def test_serialize_mode_values(self):
        from ideer.runtime.serialization import serialize

        result = serialize({"key": "value"}, mode="values")
        assert result == {"key": "value"}

    def test_serialize_mode_values_non_dict(self):
        from ideer.runtime.serialization import serialize

        result = serialize("hello", mode="values")
        assert result == "hello"

    def test_serialize_no_mode(self):
        from ideer.runtime.serialization import serialize

        result = serialize({"key": "value"})
        assert result == {"key": "value"}


# ---------------------------------------------------------------------------
# ideer/tools/registry.py — ToolRegistry
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_register_and_get(self):
        from ideer.tools.registry import ToolInfo, ToolRegistry

        registry = ToolRegistry()
        tool = ToolInfo(name="test", description="Test tool", group="test")
        registry.register(tool)
        assert registry.get("test") is tool

    def test_get_missing(self):
        from ideer.tools.registry import ToolRegistry

        registry = ToolRegistry()
        assert registry.get("missing") is None

    def test_list_all(self):
        from ideer.tools.registry import ToolInfo, ToolRegistry

        registry = ToolRegistry()
        registry.register(ToolInfo(name="a", description="A", group="g1"))
        registry.register(ToolInfo(name="b", description="B", group="g2"))
        assert len(registry.list_all()) == 2

    def test_list_by_group(self):
        from ideer.tools.registry import ToolInfo, ToolRegistry

        registry = ToolRegistry()
        registry.register(ToolInfo(name="a", description="A", group="g1"))
        registry.register(ToolInfo(name="b", description="B", group="g2"))
        registry.register(ToolInfo(name="c", description="C", group="g1"))
        assert len(registry.list_by_group("g1")) == 2

    def test_search(self):
        from ideer.tools.registry import ToolInfo, ToolRegistry

        registry = ToolRegistry()
        registry.register(ToolInfo(name="file_reader", description="Read files", group="io"))
        registry.register(ToolInfo(name="web_search", description="Search the web", group="io"))
        results = registry.search("file")
        assert len(results) == 1
        assert results[0].name == "file_reader"

    def test_search_description(self):
        from ideer.tools.registry import ToolInfo, ToolRegistry

        registry = ToolRegistry()
        registry.register(ToolInfo(name="tool1", description="Read files", group="io"))
        results = registry.search("read")
        assert len(results) == 1

    def test_update_config_success(self):
        from ideer.tools.registry import ToolInfo, ToolRegistry

        registry = ToolRegistry()
        tool = ToolInfo(name="test", description="Test", group="g", configurable=True)
        registry.register(tool)
        assert registry.update_config("test", {"key": "value"}) is True
        assert tool.config["key"] == "value"

    def test_update_config_not_found(self):
        from ideer.tools.registry import ToolRegistry

        registry = ToolRegistry()
        assert registry.update_config("missing", {}) is False

    def test_update_config_not_configurable(self):
        from ideer.tools.registry import ToolInfo, ToolRegistry

        registry = ToolRegistry()
        tool = ToolInfo(name="test", description="Test", group="g", configurable=False)
        registry.register(tool)
        assert registry.update_config("test", {}) is False

    def test_update_config_unexpected_keys(self):
        from ideer.tools.registry import ToolInfo, ToolRegistry

        registry = ToolRegistry()
        tool = ToolInfo(
            name="test",
            description="Test",
            group="g",
            configurable=True,
            config_schema={"properties": {"allowed_key": {"type": "string"}}},
        )
        registry.register(tool)
        assert registry.update_config("test", {"unexpected_key": "val"}) is False

    def test_update_config_type_mismatch(self):
        from ideer.tools.registry import ToolInfo, ToolRegistry

        registry = ToolRegistry()
        tool = ToolInfo(
            name="test",
            description="Test",
            group="g",
            configurable=True,
            config_schema={"properties": {"count": {"type": "integer"}}},
        )
        registry.register(tool)
        assert registry.update_config("test", {"count": "not_int"}) is False

    def test_update_config_enum_violation(self):
        from ideer.tools.registry import ToolInfo, ToolRegistry

        registry = ToolRegistry()
        tool = ToolInfo(
            name="test",
            description="Test",
            group="g",
            configurable=True,
            config_schema={"properties": {"mode": {"type": "string", "enum": ["a", "b"]}}},
        )
        registry.register(tool)
        assert registry.update_config("test", {"mode": "c"}) is False

    def test_register_overwrite(self):
        from ideer.tools.registry import ToolInfo, ToolRegistry

        registry = ToolRegistry()
        registry.register(ToolInfo(name="test", description="v1", group="g"))
        registry.register(ToolInfo(name="test", description="v2", group="g"))
        assert registry.get("test").description == "v2"

    def test_get_tool_registry(self):
        from ideer.tools.registry import get_tool_registry

        registry = get_tool_registry()
        assert registry is not None
        assert hasattr(registry, "register")


# ---------------------------------------------------------------------------
# ideer/models/credential_loader.py — credential loading helpers
# ---------------------------------------------------------------------------


class TestCredentialLoader:
    def test_is_oauth_token(self):
        from ideer.models.credential_loader import is_oauth_token

        assert is_oauth_token("sk-ant-oat01-xxx") is True
        assert is_oauth_token("sk-xxx") is False
        assert is_oauth_token("") is False

    def test_claude_code_credential_expired(self):
        from ideer.models.credential_loader import ClaudeCodeCredential

        cred = ClaudeCodeCredential(
            access_token="token",
            expires_at=int(time.time() * 1000) - 120_000,
        )
        assert cred.is_expired is True

    def test_claude_code_credential_not_expired(self):
        from ideer.models.credential_loader import ClaudeCodeCredential

        cred = ClaudeCodeCredential(
            access_token="token",
            expires_at=0,
        )
        assert cred.is_expired is False

    def test_claude_code_credential_not_expired_future(self):
        from ideer.models.credential_loader import ClaudeCodeCredential

        cred = ClaudeCodeCredential(
            access_token="token",
            expires_at=int(time.time() * 1000) + 3_600_000,
        )
        assert cred.is_expired is False

    def test_load_json_file_not_found(self):
        from ideer.models.credential_loader import _load_json_file

        result = _load_json_file(Path("/nonexistent/file.json"), "test")
        assert result is None

    def test_load_json_file_is_dir(self):
        from ideer.models.credential_loader import _load_json_file

        with tempfile.TemporaryDirectory() as tmpdir:
            result = _load_json_file(Path(tmpdir), "test")
            assert result is None

    def test_load_json_file_invalid_json(self):
        from ideer.models.credential_loader import _load_json_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json {{{")
            path = f.name
        try:
            result = _load_json_file(Path(path), "test")
            assert result is None
        finally:
            os.unlink(path)

    def test_load_json_file_valid(self):
        from ideer.models.credential_loader import _load_json_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"key": "value"}, f)
            path = f.name
        try:
            result = _load_json_file(Path(path), "test")
            assert result == {"key": "value"}
        finally:
            os.unlink(path)

    def test_credential_from_direct_token(self):
        from ideer.models.credential_loader import _credential_from_direct_token

        cred = _credential_from_direct_token("sk-ant-oat01-xxx", "test")
        assert cred is not None
        assert cred.access_token == "sk-ant-oat01-xxx"

    def test_credential_from_direct_token_empty(self):
        from ideer.models.credential_loader import _credential_from_direct_token

        assert _credential_from_direct_token("", "test") is None
        assert _credential_from_direct_token("  ", "test") is None

    def test_read_secret_from_file_descriptor_invalid(self):
        from ideer.models.credential_loader import _read_secret_from_file_descriptor

        with patch.dict(os.environ, {"TEST_FD": "not_a_number"}):
            result = _read_secret_from_file_descriptor("TEST_FD")
            assert result is None

    def test_read_secret_from_file_descriptor_missing(self):
        from ideer.models.credential_loader import _read_secret_from_file_descriptor

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TEST_FD_MISSING", None)
            result = _read_secret_from_file_descriptor("TEST_FD_MISSING")
            assert result is None

    def test_load_codex_cli_credential_not_found(self):
        from ideer.models.credential_loader import load_codex_cli_credential

        with patch.dict(os.environ, {"CODEX_AUTH_PATH": "/nonexistent/path.json"}):
            result = load_codex_cli_credential()
            assert result is None

    def test_load_codex_cli_credential_no_token(self):
        from ideer.models.credential_loader import load_codex_cli_credential

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"tokens": {}}, f)
            path = f.name
        try:
            with patch.dict(os.environ, {"CODEX_AUTH_PATH": path}):
                result = load_codex_cli_credential()
                assert result is None
        finally:
            os.unlink(path)

    def test_load_claude_code_credential_from_env(self):
        from ideer.models.credential_loader import load_claude_code_credential

        with patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-test"}):
            result = load_claude_code_credential()
            assert result is not None
            assert result.access_token == "sk-ant-oat01-test"

    def test_load_claude_code_credential_from_anthropic_env(self):
        from ideer.models.credential_loader import load_claude_code_credential

        with patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "sk-ant-oat01-test2"}):
            result = load_claude_code_credential()
            assert result is not None

    def test_load_claude_code_credential_from_file(self):
        from ideer.models.credential_loader import load_claude_code_credential

        cred_data = {
            "claudeAiOauth": {
                "accessToken": "sk-ant-oat01-filetoken",
                "refreshToken": "refresh",
                "expiresAt": int(time.time() * 1000) + 3_600_000,
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(cred_data, f)
            path = f.name
        try:
            with patch.dict(
                os.environ,
                {
                    "CLAUDE_CODE_OAUTH_TOKEN": "",
                    "ANTHROPIC_AUTH_TOKEN": "",
                    "CLAUDE_CODE_CREDENTIALS_PATH": path,
                },
            ):
                result = load_claude_code_credential()
                assert result is not None
                assert result.access_token == "sk-ant-oat01-filetoken"
        finally:
            os.unlink(path)

    def test_extract_claude_code_credential_expired(self):
        from ideer.models.credential_loader import _extract_claude_code_credential

        data = {
            "claudeAiOauth": {
                "accessToken": "token",
                "expiresAt": int(time.time() * 1000) - 120_000,
            }
        }
        result = _extract_claude_code_credential(data, "test")
        assert result is None

    def test_extract_claude_code_credential_no_token(self):
        from ideer.models.credential_loader import _extract_claude_code_credential

        data = {"claudeAiOauth": {}}
        result = _extract_claude_code_credential(data, "test")
        assert result is None


# ---------------------------------------------------------------------------
# ideer/mcp/oauth.py — OAuthTokenManager
# ---------------------------------------------------------------------------


class TestOAuthTokenManager:
    def test_from_extensions_config_no_oauth(self):
        from ideer.mcp.oauth import OAuthTokenManager

        config = MagicMock()
        config.get_enabled_mcp_servers.return_value = {}
        mgr = OAuthTokenManager.from_extensions_config(config)
        assert mgr.has_oauth_servers() is False

    def test_has_oauth_servers(self):
        from ideer.mcp.oauth import OAuthTokenManager

        mgr = OAuthTokenManager({"server1": MagicMock()})
        assert mgr.has_oauth_servers() is True

    def test_oauth_server_names(self):
        from ideer.mcp.oauth import OAuthTokenManager

        mgr = OAuthTokenManager({"a": MagicMock(), "b": MagicMock()})
        names = mgr.oauth_server_names()
        assert "a" in names
        assert "b" in names

    def test_get_authorization_header_no_server(self):
        from ideer.mcp.oauth import OAuthTokenManager

        mgr = OAuthTokenManager({})
        result = asyncio.run(mgr.get_authorization_header("nonexistent"))
        assert result is None

    def test_is_expiring(self):
        from ideer.mcp.oauth import OAuthTokenManager, _OAuthToken

        oauth = MagicMock()
        oauth.refresh_skew_seconds = 60
        # Token that expires in 30 seconds (less than skew)
        token = _OAuthToken(
            access_token="token",
            token_type="Bearer",
            expires_at=datetime.now(UTC) + timedelta(seconds=30),
        )
        assert OAuthTokenManager._is_expiring(token, oauth) is True

    def test_is_not_expiring(self):
        from ideer.mcp.oauth import OAuthTokenManager, _OAuthToken

        oauth = MagicMock()
        oauth.refresh_skew_seconds = 60
        token = _OAuthToken(
            access_token="token",
            token_type="Bearer",
            expires_at=datetime.now(UTC) + timedelta(seconds=300),
        )
        assert OAuthTokenManager._is_expiring(token, oauth) is False


# ---------------------------------------------------------------------------
# ideer/skills/parser.py — parse_allowed_tools, parse_skill_file
# ---------------------------------------------------------------------------


class TestSkillParser:
    def test_parse_allowed_tools_none(self):
        from ideer.skills.parser import parse_allowed_tools

        assert parse_allowed_tools(None, Path("test.md")) is None

    def test_parse_allowed_tools_list(self):
        from ideer.skills.parser import parse_allowed_tools

        result = parse_allowed_tools(["tool1", "tool2"], Path("test.md"))
        assert result == ["tool1", "tool2"]

    def test_parse_allowed_tools_empty_list(self):
        from ideer.skills.parser import parse_allowed_tools

        result = parse_allowed_tools([], Path("test.md"))
        assert result == []

    def test_parse_allowed_tools_not_list(self):
        from ideer.skills.parser import parse_allowed_tools

        with pytest.raises(ValueError):
            parse_allowed_tools("not a list", Path("test.md"))

    def test_parse_allowed_tools_non_string_item(self):
        from ideer.skills.parser import parse_allowed_tools

        with pytest.raises(ValueError):
            parse_allowed_tools([123], Path("test.md"))

    def test_parse_allowed_tools_empty_name(self):
        from ideer.skills.parser import parse_allowed_tools

        with pytest.raises(ValueError):
            parse_allowed_tools([""], Path("test.md"))

    def test_parse_skill_file_not_exists(self):
        from ideer.skills.parser import parse_skill_file
        from ideer.skills.types import SkillCategory

        result = parse_skill_file(Path("/nonexistent/SKILL.md"), SkillCategory.CUSTOM)
        assert result is None

    def test_parse_skill_file_wrong_name(self):
        from ideer.skills.parser import parse_skill_file
        from ideer.skills.types import SkillCategory

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("---\nname: test\n---\n")
            path = f.name
        try:
            result = parse_skill_file(Path(path), SkillCategory.CUSTOM)
            assert result is None
        finally:
            os.unlink(path)

    def test_parse_skill_file_valid(self):
        from ideer.skills.parser import parse_skill_file
        from ideer.skills.types import SkillCategory

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("---\nname: my-skill\ndescription: A test skill\n---\n# Content\n")
            result = parse_skill_file(skill_file, SkillCategory.CUSTOM)
            assert result is not None
            assert result.name == "my-skill"

    def test_parse_skill_file_no_frontmatter(self):
        from ideer.skills.parser import parse_skill_file
        from ideer.skills.types import SkillCategory

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("# No frontmatter\n")
            result = parse_skill_file(skill_file, SkillCategory.CUSTOM)
            assert result is None

    def test_parse_skill_file_invalid_yaml(self):
        from ideer.skills.parser import parse_skill_file
        from ideer.skills.types import SkillCategory

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("---\n: invalid: yaml: [[\n---\n")
            result = parse_skill_file(skill_file, SkillCategory.CUSTOM)
            assert result is None

    def test_parse_skill_file_missing_name(self):
        from ideer.skills.parser import parse_skill_file
        from ideer.skills.types import SkillCategory

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("---\ndescription: A test skill\n---\n")
            result = parse_skill_file(skill_file, SkillCategory.CUSTOM)
            assert result is None

    def test_parse_skill_file_missing_description(self):
        from ideer.skills.parser import parse_skill_file
        from ideer.skills.types import SkillCategory

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("---\nname: my-skill\n---\n")
            result = parse_skill_file(skill_file, SkillCategory.CUSTOM)
            assert result is None

    def test_parse_skill_file_with_license(self):
        from ideer.skills.parser import parse_skill_file
        from ideer.skills.types import SkillCategory

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("---\nname: my-skill\ndescription: Test\nlicense: MIT\n---\n")
            result = parse_skill_file(skill_file, SkillCategory.CUSTOM)
            assert result is not None
            assert result.license == "MIT"

    def test_parse_skill_file_with_allowed_tools(self):
        from ideer.skills.parser import parse_skill_file
        from ideer.skills.types import SkillCategory

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("---\nname: my-skill\ndescription: Test\nallowed-tools:\n  - tool1\n---\n")
            result = parse_skill_file(skill_file, SkillCategory.CUSTOM)
            assert result is not None
            assert result.allowed_tools == ["tool1"]

    def test_parse_skill_file_invalid_allowed_tools(self):
        from ideer.skills.parser import parse_skill_file
        from ideer.skills.types import SkillCategory

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("---\nname: my-skill\ndescription: Test\nallowed-tools: not-a-list\n---\n")
            result = parse_skill_file(skill_file, SkillCategory.CUSTOM)
            assert result is None


# ---------------------------------------------------------------------------
# ideer/skills/validation.py — _validate_skill_frontmatter
# ---------------------------------------------------------------------------


class TestSkillValidation:
    def test_no_skill_md(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False
            assert "not found" in msg

    def test_no_frontmatter(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("# Just a heading\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False

    def test_invalid_frontmatter_format(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\nnot closed properly\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False

    def test_invalid_yaml(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\n: invalid: yaml: [[\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False
            assert "Invalid YAML" in msg

    def test_non_dict_frontmatter(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\n- item1\n- item2\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False

    def test_unexpected_keys(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\nname: test\ndescription: test\nunknown_key: value\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False
            assert "Unexpected key" in msg

    def test_missing_name(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\ndescription: test\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False
            assert "Missing 'name'" in msg

    def test_missing_description(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\nname: test\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False
            assert "Missing 'description'" in msg

    def test_name_not_string(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\nname: 123\ndescription: test\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False

    def test_name_empty(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\nname: ' '\ndescription: test\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False

    def test_name_invalid_format(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\nname: My_Skill\ndescription: test\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False
            assert "hyphen-case" in msg

    def test_name_starts_with_hyphen(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\nname: -test\ndescription: test\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False

    def test_name_ends_with_hyphen(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\nname: test-\ndescription: test\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False

    def test_name_consecutive_hyphens(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\nname: my--skill\ndescription: test\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False

    def test_name_too_long(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            long_name = "a" * 65
            skill_md.write_text(f"---\nname: {long_name}\ndescription: test\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False
            assert "too long" in msg

    def test_description_not_string(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\nname: test\ndescription: 123\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False

    def test_description_angle_brackets(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\nname: test\ndescription: 'test <html>'\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False
            assert "angle brackets" in msg

    def test_description_too_long(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            long_desc = "a" * 1025
            skill_md.write_text(f"---\nname: test\ndescription: '{long_desc}'\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is False
            assert "too long" in msg

    def test_valid_skill(self):
        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = Path(tmpdir) / "SKILL.md"
            skill_md.write_text("---\nname: my-skill\ndescription: A valid skill\n---\n")
            valid, msg, name = _validate_skill_frontmatter(Path(tmpdir))
            assert valid is True
            assert name == "my-skill"


# ---------------------------------------------------------------------------
# ideer/skills/installer.py — archive safety helpers
# ---------------------------------------------------------------------------


class TestSkillInstaller:
    def test_is_unsafe_zip_member_absolute(self):
        from ideer.skills.installer import is_unsafe_zip_member

        info = MagicMock()
        info.filename = "/etc/passwd"
        assert is_unsafe_zip_member(info) is True

    def test_is_unsafe_zip_member_traversal(self):
        from ideer.skills.installer import is_unsafe_zip_member

        info = MagicMock()
        info.filename = "../../../etc/passwd"
        assert is_unsafe_zip_member(info) is True

    def test_is_unsafe_zip_member_safe(self):
        from ideer.skills.installer import is_unsafe_zip_member

        info = MagicMock()
        info.filename = "skill/file.txt"
        assert is_unsafe_zip_member(info) is False

    def test_is_unsafe_zip_member_empty(self):
        from ideer.skills.installer import is_unsafe_zip_member

        info = MagicMock()
        info.filename = ""
        assert is_unsafe_zip_member(info) is False

    def test_is_unsafe_zip_member_windows_absolute(self):
        from ideer.skills.installer import is_unsafe_zip_member

        info = MagicMock()
        info.filename = "C:\\Windows\\System32\\file"
        assert is_unsafe_zip_member(info) is True

    def test_is_symlink_member(self):
        from ideer.skills.installer import is_symlink_member

        info = MagicMock()
        # S_ISLNK checks mode bits, need to set the symlink type bits
        # external_attr stores Unix permission in upper 16 bits
        # For symlink: mode = S_IFLNK | perms = 0o120000
        info.external_attr = 0o120777 << 16
        assert is_symlink_member(info) is True

    def test_is_not_symlink_member(self):
        from ideer.skills.installer import is_symlink_member

        info = MagicMock()
        info.external_attr = 0
        assert is_symlink_member(info) is False

    def test_should_ignore_archive_entry(self):
        from ideer.skills.installer import should_ignore_archive_entry

        assert should_ignore_archive_entry(Path(".DS_Store")) is True
        assert should_ignore_archive_entry(Path("__MACOSX")) is True
        assert should_ignore_archive_entry(Path("skill")) is False

    def test_resolve_skill_dir_single_dir(self):
        from ideer.skills.installer import resolve_skill_dir_from_archive

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("test")
            result = resolve_skill_dir_from_archive(Path(tmpdir))
            assert result == skill_dir

    def test_resolve_skill_dir_multiple_items(self):
        from ideer.skills.installer import resolve_skill_dir_from_archive

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "file1.txt").write_text("test")
            (Path(tmpdir) / "file2.txt").write_text("test")
            result = resolve_skill_dir_from_archive(Path(tmpdir))
            assert result == Path(tmpdir)

    def test_resolve_skill_dir_empty(self):
        from ideer.skills.installer import resolve_skill_dir_from_archive

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="empty"):
                resolve_skill_dir_from_archive(Path(tmpdir))

    def test_resolve_skill_dir_filters_macosx(self):
        from ideer.skills.installer import resolve_skill_dir_from_archive

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "__MACOSX").mkdir()
            (Path(tmpdir) / ".DS_Store").write_text("test")
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            result = resolve_skill_dir_from_archive(Path(tmpdir))
            assert result == skill_dir

    def test_safe_extract_skill_archive_unsafe_member(self):
        from ideer.skills.installer import safe_extract_skill_archive

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "test.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("../../../etc/passwd", "evil")
            with zipfile.ZipFile(zip_path, "r") as zf:
                with pytest.raises(ValueError, match="unsafe"):
                    safe_extract_skill_archive(zf, Path(tmpdir) / "dest")

    def test_safe_extract_skill_archive_size_limit(self):
        from ideer.skills.installer import safe_extract_skill_archive

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "test.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("big_file.txt", "x" * 1024)
            with zipfile.ZipFile(zip_path, "r") as zf:
                with pytest.raises(ValueError, match="too large"):
                    safe_extract_skill_archive(zf, Path(tmpdir) / "dest", max_total_size=100)

    def test_safe_extract_skill_archive_symlink_skipped(self):
        """Verify that symlink entries are skipped during extraction."""
        from ideer.skills.installer import safe_extract_skill_archive

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "test.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                # Create a normal file
                zf.writestr("normal.txt", "hello")
                # Create a symlink entry
                info = zipfile.ZipInfo("link.txt")
                # S_IFLNK = 0o120000, shifted left by 16 for external_attr
                info.external_attr = 0o120000 << 16
                zf.writestr(info, "target")
            with zipfile.ZipFile(zip_path, "r") as zf:
                dest = Path(tmpdir) / "dest"
                dest.mkdir()
                safe_extract_skill_archive(zf, dest)
                # Normal file should exist, symlink should be skipped
                assert (dest / "normal.txt").exists()
                assert not (dest / "link.txt").exists()


# ---------------------------------------------------------------------------
# ideer/utils/file_conversion.py — _pymupdf_output_too_sparse, _get_pdf_converter,
# _clean_bold_title, extract_outline
# ---------------------------------------------------------------------------


class TestFileConversion:
    def test_pymupdf_output_too_sparse_no_pages(self):
        from ideer.utils.file_conversion import _pymupdf_output_too_sparse

        # When pymupdf is not installed, the import inside the function fails
        with patch.dict("sys.modules", {"pymupdf": None}):
            result = _pymupdf_output_too_sparse("short", Path("/fake/file.pdf"))
            # No pages available, fallback to absolute threshold: chars < 200
            assert result is True

    def test_pymupdf_output_too_sparse_enough(self):
        from ideer.utils.file_conversion import _pymupdf_output_too_sparse

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)

        mock_pymupdf = MagicMock()
        mock_pymupdf.open.return_value = mock_doc

        with patch.dict("sys.modules", {"pymupdf": mock_pymupdf}):
            result = _pymupdf_output_too_sparse("x" * 100, Path("/fake/file.pdf"))
            assert result is False

    def test_get_pdf_converter_default(self):
        from ideer.utils.file_conversion import _get_pdf_converter

        with patch("ideer.utils.file_conversion._get_uploads_config_value", return_value="auto"):
            assert _get_pdf_converter() == "auto"

    def test_get_pdf_converter_invalid(self):
        from ideer.utils.file_conversion import _get_pdf_converter

        with patch("ideer.utils.file_conversion._get_uploads_config_value", return_value="INVALID"):
            assert _get_pdf_converter() == "auto"

    def test_clean_bold_title(self):
        from ideer.utils.file_conversion import _clean_bold_title

        assert _clean_bold_title("**Overview**") == "Overview"
        assert _clean_bold_title("plain text") == "plain text"
        assert _clean_bold_title("**A** **B**") == "A B"

    def test_extract_outline_empty(self):
        from ideer.utils.file_conversion import extract_outline

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("No headings here\nJust plain text\n")
            path = f.name
        try:
            result = extract_outline(Path(path))
            assert result == []
        finally:
            os.unlink(path)

    def test_extract_outline_with_headings(self):
        from ideer.utils.file_conversion import extract_outline

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Heading 1\nSome text\n## Heading 2\nMore text\n")
            path = f.name
        try:
            result = extract_outline(Path(path))
            assert len(result) == 2
            assert result[0]["title"] == "Heading 1"
            assert result[1]["title"] == "Heading 2"
        finally:
            os.unlink(path)

    def test_extract_outline_bold_heading(self):
        from ideer.utils.file_conversion import extract_outline

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("**ITEM 1. BUSINESS**\nSome text\n")
            path = f.name
        try:
            result = extract_outline(Path(path))
            assert len(result) == 1
            assert "ITEM 1. BUSINESS" in result[0]["title"]
        finally:
            os.unlink(path)

    def test_extract_outline_split_bold(self):
        from ideer.utils.file_conversion import extract_outline

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("**1** **Introduction**\nSome text\n")
            path = f.name
        try:
            result = extract_outline(Path(path))
            assert len(result) == 1
            assert "1" in result[0]["title"]
            assert "Introduction" in result[0]["title"]
        finally:
            os.unlink(path)

    def test_extract_outline_truncation(self):
        from ideer.utils.file_conversion import MAX_OUTLINE_ENTRIES, extract_outline

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            for i in range(MAX_OUTLINE_ENTRIES + 5):
                f.write(f"# Heading {i}\n\n")
            path = f.name
        try:
            result = extract_outline(Path(path))
            assert len(result) == MAX_OUTLINE_ENTRIES + 1  # +1 for truncated sentinel
            assert result[-1].get("truncated") is True
        finally:
            os.unlink(path)

    def test_extract_outline_nonexistent_file(self):
        from ideer.utils.file_conversion import extract_outline

        result = extract_outline(Path("/nonexistent/file.md"))
        assert result == []


# ---------------------------------------------------------------------------
# ideer/utils/readability.py — Article
# ---------------------------------------------------------------------------


class TestReadability:
    def test_article_to_markdown(self):
        from ideer.utils.readability import Article

        article = Article(title="Test Title", html_content="<p>Hello world</p>")
        md = article.to_markdown()
        assert "Test Title" in md
        assert "Hello world" in md

    def test_article_to_markdown_no_title(self):
        from ideer.utils.readability import Article

        article = Article(title="Test", html_content="<p>Content</p>")
        md = article.to_markdown(including_title=False)
        assert "Test" not in md
        assert "Content" in md

    def test_article_to_markdown_empty_content(self):
        from ideer.utils.readability import Article

        article = Article(title="Test", html_content="")
        md = article.to_markdown()
        assert "No content available" in md

    def test_article_to_markdown_none_content(self):
        from ideer.utils.readability import Article

        article = Article(title="Test", html_content=None)
        md = article.to_markdown()
        assert "No content available" in md

    def test_article_to_message(self):
        from ideer.utils.readability import Article

        article = Article(title="Test", html_content="<p>Hello</p>")
        article.url = "http://example.com"
        msg = article.to_message()
        assert isinstance(msg, list)
        assert len(msg) > 0

    def test_article_to_message_with_images(self):
        from ideer.utils.readability import Article

        article = Article(title="Test", html_content='<p>Text</p><img src="image.png"><p>More</p>')
        article.url = "http://example.com"
        msg = article.to_message()
        assert isinstance(msg, list)

    def test_article_to_message_empty(self):
        from ideer.utils.readability import Article

        article = Article(title="Test", html_content="")
        article.url = "http://example.com"
        msg = article.to_message()
        assert len(msg) == 1
        assert msg[0]["type"] == "text"

    def test_readability_extractor(self):
        from ideer.utils.readability import ReadabilityExtractor

        extractor = ReadabilityExtractor()
        article = extractor.extract_article("<html><head><title>Test</title></head><body><p>Hello world</p></body></html>")
        assert article.title is not None
        assert article.html_content is not None

    def test_readability_extractor_empty(self):
        from ideer.utils.readability import ReadabilityExtractor

        extractor = ReadabilityExtractor()
        article = extractor.extract_article("<html><body></body></html>")
        # Should fallback to default content
        assert article.title == "Untitled" or article.html_content == "No content could be extracted from this page"
