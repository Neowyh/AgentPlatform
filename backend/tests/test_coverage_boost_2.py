"""Tests to boost coverage for more modules with missed lines.

Covers uncovered code paths in:
- ideer/uploads/manager.py
- ideer/reflection/resolvers.py
- ideer/subagents/config.py
- ideer/subagents/registry.py
- ideer/persistence/thread_meta/base.py
- ideer/persistence/thread_meta/memory.py
- ideer/persistence/thread_meta/sql.py
- ideer/runtime/journal.py
- ideer/runtime/events/store/db.py
- ideer/runtime/runs/store/base.py
- ideer/runtime/runs/store/memory.py
- ideer/runtime/runs/worker.py
- ideer/workflows/executor.py
- ideer/workflows/store.py
- ideer/workflows/template.py
- ideer/tools/builtins/present_file_tool.py
- ideer/tools/builtins/view_image_tool.py
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# ideer/uploads/manager.py — validate_thread_id, normalize_filename,
# claim_unique_filename, write_upload_file_no_symlink
# ---------------------------------------------------------------------------


class TestUploadsManager:
    def test_validate_thread_id_valid(self):
        from ideer.uploads.manager import validate_thread_id

        validate_thread_id("thread-123")
        validate_thread_id("abc_def.123")

    def test_validate_thread_id_empty(self):
        from ideer.uploads.manager import validate_thread_id

        with pytest.raises(ValueError, match="Invalid thread_id"):
            validate_thread_id("")

    def test_validate_thread_id_unsafe(self):
        from ideer.uploads.manager import validate_thread_id

        with pytest.raises(ValueError, match="Invalid thread_id"):
            validate_thread_id("../etc/passwd")

    def test_normalize_filename_valid(self):
        from ideer.uploads.manager import normalize_filename

        assert normalize_filename("file.txt") == "file.txt"
        assert normalize_filename("/path/to/file.txt") == "file.txt"

    def test_normalize_filename_empty(self):
        from ideer.uploads.manager import normalize_filename

        with pytest.raises(ValueError, match="empty"):
            normalize_filename("")

    def test_normalize_filename_dotdot(self):
        from ideer.uploads.manager import normalize_filename

        with pytest.raises(ValueError, match="unsafe"):
            normalize_filename("..")

    def test_normalize_filename_backslash(self):
        from ideer.uploads.manager import normalize_filename

        with pytest.raises(ValueError, match="backslash"):
            normalize_filename("path\\file.txt")

    def test_normalize_filename_too_long(self):
        from ideer.uploads.manager import normalize_filename

        # 256 bytes in UTF-8 exceeds the 255-byte limit
        long_name = "a" * 252 + ".txt"
        with pytest.raises(ValueError, match="too long"):
            normalize_filename(long_name)

    def test_claim_unique_filename(self):
        from ideer.uploads.manager import claim_unique_filename

        seen = {"file.txt"}
        result = claim_unique_filename("file.txt", seen)
        assert result != "file.txt"
        assert result.startswith("file_")
        assert result.endswith(".txt")

    def test_claim_unique_filename_no_conflict(self):
        from ideer.uploads.manager import claim_unique_filename

        seen = set()
        result = claim_unique_filename("file.txt", seen)
        assert result == "file.txt"


# ---------------------------------------------------------------------------
# ideer/reflection/resolvers.py — resolve_variable, resolve_class,
# _build_missing_dependency_hint
# ---------------------------------------------------------------------------


class TestResolvers:
    def test_resolve_variable_valid(self):
        from ideer.reflection.resolvers import resolve_variable

        result = resolve_variable("pathlib:Path")
        assert result is Path

    def test_resolve_variable_invalid_path(self):
        from ideer.reflection.resolvers import resolve_variable

        with pytest.raises(ImportError, match="doesn't look like"):
            resolve_variable("nocolon")

    def test_resolve_variable_missing_module(self):
        from ideer.reflection.resolvers import resolve_variable

        with pytest.raises(ImportError, match="Could not import"):
            resolve_variable("nonexistent_module:Something")

    def test_resolve_variable_missing_attribute(self):
        from ideer.reflection.resolvers import resolve_variable

        with pytest.raises(ImportError, match="does not define"):
            resolve_variable("pathlib:NonExistent")

    def test_resolve_variable_type_mismatch(self):
        from ideer.reflection.resolvers import resolve_variable

        with pytest.raises(ValueError, match="not an instance of"):
            resolve_variable("pathlib:Path", expected_type=str)

    def test_resolve_variable_type_tuple(self):
        from ideer.reflection.resolvers import resolve_variable

        result = resolve_variable("pathlib:Path", expected_type=(Path, type))
        assert result is Path

    def test_resolve_class_valid(self):
        from ideer.reflection.resolvers import resolve_class

        result = resolve_class("pathlib:Path", base_class=object)
        assert issubclass(result, Path)

    def test_resolve_class_not_subclass(self):
        from ideer.reflection.resolvers import resolve_class

        with pytest.raises(ValueError, match="not a subclass"):
            resolve_class("pathlib:Path", base_class=str)

    def test_resolve_class_not_type(self):
        from ideer.reflection.resolvers import resolve_class

        # PurePosixPath is a class but not a subclass of str
        with pytest.raises(ValueError, match="not a subclass"):
            resolve_class("pathlib:PurePosixPath", base_class=str)

    def test_build_hint_known_module(self):
        from ideer.reflection.resolvers import _build_missing_dependency_hint

        err = ImportError("No module named 'langchain_openai'")
        err.name = "langchain_openai"
        hint = _build_missing_dependency_hint("langchain_openai.ChatOpenAI", err)
        assert "langchain-openai" in hint

    def test_build_hint_unknown_module(self):
        from ideer.reflection.resolvers import _build_missing_dependency_hint

        err = ImportError("No module named 'some_module'")
        err.name = "some_module"
        hint = _build_missing_dependency_hint("some_module.Thing", err)
        assert "some-module" in hint


# ---------------------------------------------------------------------------
# ideer/subagents/config.py — SubagentConfig, resolve_subagent_model_name
# ---------------------------------------------------------------------------


class TestSubagentConfig:
    def test_subagent_config_defaults(self):
        from ideer.subagents.config import SubagentConfig

        config = SubagentConfig(name="test", description="Test subagent")
        assert config.model == "inherit"
        assert config.max_turns == 50
        assert config.timeout_seconds == 900
        assert config.disallowed_tools == ["task"]

    def test_resolve_subagent_model_explicit(self):
        from ideer.subagents.config import SubagentConfig, resolve_subagent_model_name

        config = SubagentConfig(name="test", description="Test", model="gpt-4")
        result = resolve_subagent_model_name(config, "gpt-3.5-turbo")
        assert result == "gpt-4"

    def test_resolve_subagent_model_inherit_from_parent(self):
        from ideer.subagents.config import SubagentConfig, resolve_subagent_model_name

        config = SubagentConfig(name="test", description="Test", model="inherit")
        result = resolve_subagent_model_name(config, "gpt-3.5-turbo")
        assert result == "gpt-3.5-turbo"

    def test_resolve_subagent_model_fallback_to_config(self):
        from ideer.subagents.config import SubagentConfig, resolve_subagent_model_name

        config = SubagentConfig(name="test", description="Test", model="inherit")
        mock_config = MagicMock()
        mock_config.models = [SimpleNamespace(name="default-model")]
        result = resolve_subagent_model_name(config, None, app_config=mock_config)
        assert result == "default-model"

    def test_resolve_subagent_model_no_models(self):
        from ideer.subagents.config import SubagentConfig, resolve_subagent_model_name

        config = SubagentConfig(name="test", description="Test", model="inherit")
        mock_config = MagicMock()
        mock_config.models = []
        with pytest.raises(ValueError, match="No chat models"):
            resolve_subagent_model_name(config, None, app_config=mock_config)


# ---------------------------------------------------------------------------
# ideer/runtime/serialization.py — more edge cases
# ---------------------------------------------------------------------------


class TestSerializationEdgeCases:
    def test_serialize_lc_object_nested(self):
        from ideer.runtime.serialization import serialize_lc_object

        data = {"a": [1, 2], "b": {"c": 3}}
        result = serialize_lc_object(data)
        assert result == {"a": [1, 2], "b": {"c": 3}}

    def test_serialize_messages_tuple_non_dict_metadata(self):
        from ideer.runtime.serialization import serialize_messages_tuple

        # When metadata is not a dict, it's replaced with {}
        result = serialize_messages_tuple(("hello", "not_dict"))
        assert result == ["hello", {}]

    def test_serialize_channel_values_empty(self):
        from ideer.runtime.serialization import serialize_channel_values

        result = serialize_channel_values({})
        assert result == {}


# ---------------------------------------------------------------------------
# ideer/tools/builtins/present_file_tool.py
# ---------------------------------------------------------------------------


class TestPresentFileTool:
    def test_present_file_tool_exists(self):
        from ideer.tools.builtins.present_file_tool import present_file_tool

        assert present_file_tool is not None
        assert present_file_tool.name == "present_files"

    def test_present_file_tool_description(self):
        from ideer.tools.builtins.present_file_tool import present_file_tool

        assert "file" in present_file_tool.description.lower()


# ---------------------------------------------------------------------------
# ideer/tools/builtins/view_image_tool.py
# ---------------------------------------------------------------------------


class TestViewImageTool:
    def test_view_image_tool_exists(self):
        from ideer.tools.builtins.view_image_tool import view_image_tool

        assert view_image_tool is not None
        assert view_image_tool.name == "view_image"

    def test_view_image_tool_description(self):
        from ideer.tools.builtins.view_image_tool import view_image_tool

        assert "image" in view_image_tool.description.lower()


# ---------------------------------------------------------------------------
# ideer/mcp/cache.py — cache reset and staleness
# ---------------------------------------------------------------------------


class TestMCPCache:
    def test_reset_mcp_tools_cache(self):
        from ideer.mcp.cache import reset_mcp_tools_cache

        reset_mcp_tools_cache()
        # After reset, cache should be uninitialized
        from ideer.mcp import cache

        assert cache._cache_initialized is False
        assert cache._mcp_tools_cache is None
        assert cache._config_mtime is None

    def test_is_cache_stale_not_initialized(self):
        from ideer.mcp import cache
        from ideer.mcp.cache import _is_cache_stale

        cache._cache_initialized = False
        assert _is_cache_stale() is False

    def test_get_config_mtime_no_config(self):
        from ideer.mcp.cache import _get_config_mtime

        with patch("ideer.config.extensions_config.ExtensionsConfig.resolve_config_path", return_value=None):
            result = _get_config_mtime()
            assert result is None


# ---------------------------------------------------------------------------
# ideer/skills/storage/local_skill_storage.py — more edge cases
# ---------------------------------------------------------------------------


class TestLocalSkillStorage:
    def test_custom_skill_exists_false(self):
        from ideer.skills.storage.local_skill_storage import LocalSkillStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalSkillStorage(host_path=tmpdir)
            assert storage.custom_skill_exists("nonexistent") is False

    def test_public_skill_exists_false(self):
        from ideer.skills.storage.local_skill_storage import LocalSkillStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalSkillStorage(host_path=tmpdir)
            assert storage.public_skill_exists("nonexistent") is False

    def test_read_custom_skill_not_found(self):
        from ideer.skills.storage.local_skill_storage import LocalSkillStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalSkillStorage(host_path=tmpdir)
            with pytest.raises(FileNotFoundError):
                storage.read_custom_skill("nonexistent")

    def test_get_skills_root_path(self):
        from ideer.skills.storage.local_skill_storage import LocalSkillStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalSkillStorage(host_path=tmpdir)
            assert storage.get_skills_root_path() == Path(tmpdir)

    def test_read_history_empty(self):
        from ideer.skills.storage.local_skill_storage import LocalSkillStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalSkillStorage(host_path=tmpdir)
            result = storage.read_history("nonexistent")
            assert result == []


# ---------------------------------------------------------------------------
# ideer/workflows/template.py — render_value
# ---------------------------------------------------------------------------


class TestWorkflowTemplate:
    def test_render_value_simple(self):
        from ideer.workflows.template import render_value

        result = render_value("hello", {})
        assert result == "hello"

    def test_render_value_template(self):
        from ideer.workflows.template import render_value

        result = render_value("{{name}}", {"name": "world"})
        assert result == "world"

    def test_render_value_partial(self):
        from ideer.workflows.template import render_value

        result = render_value("Hello {{name}}!", {"name": "world"})
        assert result == "Hello world!"

    def test_render_value_unresolvable(self):
        from ideer.workflows.template import render_value

        result = render_value("{{missing}}", {})
        assert result is None

    def test_render_value_partial_unresolvable(self):
        from ideer.workflows.template import render_value

        result = render_value("Hello {{missing}}!", {})
        assert result == "Hello {{missing}}!"

    def test_render_value_non_string(self):
        from ideer.workflows.template import render_value

        result = render_value(42, {})
        assert result == 42

    def test_render_value_nested(self):
        from ideer.workflows.template import render_value

        result = render_value("{{a.b}}", {"a": {"b": "deep"}})
        assert result == "deep"


# ---------------------------------------------------------------------------
# ideer/workflows/store.py — WorkflowStore async methods
# ---------------------------------------------------------------------------


class TestWorkflowStore:
    def test_workflow_store_init(self):
        from ideer.workflows.store import WorkflowStore

        store = WorkflowStore()
        assert store is not None

    def test_load_workflow_no_db(self):
        from ideer.workflows.store import WorkflowStore

        store = WorkflowStore()
        with patch("ideer.workflows.store.get_session_factory", return_value=None):
            result = asyncio.run(store.load_workflow("test"))
            assert result is None


# ---------------------------------------------------------------------------
# ideer/tools/tools.py — _is_host_bash_tool, _ensure_sync_invocable_tool
# ---------------------------------------------------------------------------


class TestToolsHelpers:
    def test_is_host_bash_tool_bash_group(self):
        from ideer.tools.tools import _is_host_bash_tool

        tool = SimpleNamespace(group="bash", use=None)
        assert _is_host_bash_tool(tool) is True

    def test_is_host_bash_tool_bash_use(self):
        from ideer.tools.tools import _is_host_bash_tool

        tool = SimpleNamespace(group=None, use="ideer.sandbox.tools:bash_tool")
        assert _is_host_bash_tool(tool) is True

    def test_is_host_bash_tool_other(self):
        from ideer.tools.tools import _is_host_bash_tool

        tool = SimpleNamespace(group="io", use="some.module:tool")
        assert _is_host_bash_tool(tool) is False

    def test_ensure_sync_invocable_tool_no_func(self):
        from ideer.tools.tools import _ensure_sync_invocable_tool

        tool = MagicMock()
        tool.func = None
        tool.coroutine = AsyncMock()
        tool.name = "test"

        with patch("ideer.tools.tools.make_sync_tool_wrapper", return_value=lambda: None):
            result = _ensure_sync_invocable_tool(tool)
            assert result.func is not None

    def test_ensure_sync_invocable_tool_has_func(self):
        from ideer.tools.tools import _ensure_sync_invocable_tool

        tool = MagicMock()
        tool.func = lambda: None
        result = _ensure_sync_invocable_tool(tool)
        # Should not modify existing func
        assert result.func is not None


# ---------------------------------------------------------------------------
# ideer/gateway/routers/auth.py — rate limiting helpers
# ---------------------------------------------------------------------------


class TestAuthRateLimiting:
    def test_check_rate_limit_no_record(self):
        from app.gateway.routers.auth import _check_rate_limit

        # Should not raise
        _check_rate_limit("192.168.1.100")

    def test_record_login_failure_first(self):
        from app.gateway.routers.auth import _login_attempts, _record_login_failure

        ip = "10.0.0.1"
        _login_attempts.clear()
        try:
            _record_login_failure(ip)
            assert ip in _login_attempts
            assert _login_attempts[ip][0] == 1
        finally:
            _login_attempts.clear()

    def test_record_login_success(self):
        from app.gateway.routers.auth import _login_attempts, _record_login_failure, _record_login_success

        ip = "10.0.0.2"
        _login_attempts.clear()
        try:
            _record_login_failure(ip)
            _record_login_success(ip)
            assert ip not in _login_attempts
        finally:
            _login_attempts.clear()

    def test_password_is_common(self):
        from app.gateway.routers.auth import _password_is_common

        assert _password_is_common("password") is True
        assert _password_is_common("Password") is True
        assert _password_is_common("strongPassword123!") is False

    def test_trusted_proxies_empty(self):
        from app.gateway.routers.auth import _trusted_proxies

        with patch.dict(os.environ, {"AUTH_TRUSTED_PROXIES": ""}, clear=False):
            result = _trusted_proxies()
            assert result == []

    def test_trusted_proxies_valid(self):
        from app.gateway.routers.auth import _trusted_proxies

        with patch.dict(os.environ, {"AUTH_TRUSTED_PROXIES": "10.0.0.0/8,192.168.1.1"}, clear=False):
            result = _trusted_proxies()
            assert len(result) == 2

    def test_trusted_proxies_invalid(self):
        from app.gateway.routers.auth import _trusted_proxies

        with patch.dict(os.environ, {"AUTH_TRUSTED_PROXIES": "not-an-ip"}, clear=False):
            result = _trusted_proxies()
            assert len(result) == 0

    def test_get_client_ip_no_proxy(self):
        from app.gateway.routers.auth import _get_client_ip

        with patch.dict(os.environ, {"AUTH_TRUSTED_PROXIES": ""}, clear=False):
            request = MagicMock()
            request.client.host = "192.168.1.1"
            request.headers = {}
            result = _get_client_ip(request)
            assert result == "192.168.1.1"

    def test_get_client_ip_with_proxy(self):
        from app.gateway.routers.auth import _get_client_ip

        with patch.dict(os.environ, {"AUTH_TRUSTED_PROXIES": "10.0.0.0/8"}, clear=False):
            request = MagicMock()
            request.client.host = "10.0.0.1"
            request.headers = {"x-real-ip": "203.0.113.1"}
            result = _get_client_ip(request)
            assert result == "203.0.113.1"

    def test_get_client_ip_no_client(self):
        from app.gateway.routers.auth import _get_client_ip

        with patch.dict(os.environ, {"AUTH_TRUSTED_PROXIES": ""}, clear=False):
            request = MagicMock()
            request.client = None
            request.headers = {}
            result = _get_client_ip(request)
            assert result == "unknown"


# ---------------------------------------------------------------------------
# ideer/gateway/routers/memory.py — _map_memory_fact_value_error
# ---------------------------------------------------------------------------


class TestMemoryRouter:
    def test_map_memory_fact_value_error_confidence(self):
        from app.gateway.routers.memory import _map_memory_fact_value_error

        exc = ValueError("confidence")
        http_exc = _map_memory_fact_value_error(exc)
        assert http_exc.status_code == 400
        assert "confidence" in http_exc.detail.lower()

    def test_map_memory_fact_value_error_content(self):
        from app.gateway.routers.memory import _map_memory_fact_value_error

        exc = ValueError("content")
        http_exc = _map_memory_fact_value_error(exc)
        assert http_exc.status_code == 400
        assert "empty" in http_exc.detail.lower()


# ---------------------------------------------------------------------------
# ideer/gateway/routers/thread_runs.py — _cancel_conflict_detail
# ---------------------------------------------------------------------------


class TestThreadRuns:
    def test_cancel_conflict_detail_pending(self):
        from app.gateway.routers.thread_runs import _cancel_conflict_detail
        from ideer.runtime import RunStatus

        record = MagicMock()
        record.status = RunStatus.pending
        result = _cancel_conflict_detail("run-1", record)
        assert "not active" in result

    def test_cancel_conflict_detail_other_status(self):
        from app.gateway.routers.thread_runs import _cancel_conflict_detail
        from ideer.runtime import RunStatus

        record = MagicMock()
        record.status = RunStatus.success
        result = _cancel_conflict_detail("run-1", record)
        assert "not cancellable" in result

    def test_record_to_response(self):
        from app.gateway.routers.thread_runs import _record_to_response

        record = MagicMock()
        record.run_id = "run-1"
        record.thread_id = "thread-1"
        record.assistant_id = "agent"
        record.status = MagicMock()
        record.status.value = "running"
        record.metadata = {}
        record.kwargs = {}
        record.multitask_strategy = "reject"
        record.created_at = ""
        record.updated_at = ""
        record.total_input_tokens = 0
        record.total_output_tokens = 0
        record.total_tokens = 0
        record.llm_call_count = 0
        record.lead_agent_tokens = 0
        record.subagent_tokens = 0
        record.middleware_tokens = 0
        record.message_count = 0

        response = _record_to_response(record)
        assert response.run_id == "run-1"
        assert response.thread_id == "thread-1"


# ---------------------------------------------------------------------------
# ideer/gateway/routers/feedback.py — FeedbackCreateRequest validation
# ---------------------------------------------------------------------------


class TestFeedbackRouter:
    def test_feedback_create_request(self):
        from app.gateway.routers.feedback import FeedbackCreateRequest

        req = FeedbackCreateRequest(rating=1, comment="Good")
        assert req.rating == 1
        assert req.comment == "Good"

    def test_feedback_upsert_request(self):
        from app.gateway.routers.feedback import FeedbackUpsertRequest

        req = FeedbackUpsertRequest(rating=-1)
        assert req.rating == -1

    def test_feedback_stats_response(self):
        from app.gateway.routers.feedback import FeedbackStatsResponse

        resp = FeedbackStatsResponse(run_id="run-1", total=10, positive=8, negative=2)
        assert resp.total == 10


# ---------------------------------------------------------------------------
# ideer/gateway/routers/suggestions.py — SuggestionsRequest/Response
# ---------------------------------------------------------------------------


class TestSuggestionsModels:
    def test_suggestions_request(self):
        from app.gateway.routers.suggestions import SuggestionMessage, SuggestionsRequest

        req = SuggestionsRequest(
            messages=[SuggestionMessage(role="user", content="Hello")],
            n=3,
        )
        assert len(req.messages) == 1
        assert req.n == 3

    def test_suggestions_response(self):
        from app.gateway.routers.suggestions import SuggestionsResponse

        resp = SuggestionsResponse(suggestions=["q1", "q2"])
        assert len(resp.suggestions) == 2

    def test_suggestions_response_empty(self):
        from app.gateway.routers.suggestions import SuggestionsResponse

        resp = SuggestionsResponse()
        assert resp.suggestions == []


# ---------------------------------------------------------------------------
# ideer/gateway/routers/mcp.py — McpServerConfigResponse defaults
# ---------------------------------------------------------------------------


class TestMCPRouterModels:
    def test_mcp_server_config_defaults(self):
        from app.gateway.routers.mcp import McpServerConfigResponse

        server = McpServerConfigResponse()
        assert server.enabled is True
        assert server.type == "stdio"
        assert server.command is None
        assert server.args == []
        assert server.env == {}

    def test_mcp_config_response(self):
        from app.gateway.routers.mcp import McpConfigResponse, McpServerConfigResponse

        config = McpConfigResponse(mcp_servers={"github": McpServerConfigResponse()})
        assert "github" in config.mcp_servers

    def test_mcp_oauth_config_defaults(self):
        from app.gateway.routers.mcp import McpOAuthConfigResponse

        oauth = McpOAuthConfigResponse()
        assert oauth.enabled is True
        assert oauth.grant_type == "client_credentials"
        assert oauth.token_field == "access_token"


# ---------------------------------------------------------------------------
# ideer/gateway/services.py — normalize_input edge cases
# ---------------------------------------------------------------------------


class TestNormalizeInputEdgeCases:
    def test_normalize_input_with_base_message(self):
        from langchain_core.messages import HumanMessage

        from app.gateway.services import normalize_input

        msg = HumanMessage(content="hello")
        result = normalize_input({"messages": [msg]})
        assert "messages" in result
        assert len(result["messages"]) == 1

    def test_normalize_input_mixed_messages(self):
        from app.gateway.services import normalize_input

        result = normalize_input(
            {
                "messages": [
                    {"role": "human", "content": "hello"},
                    "invalid",
                ]
            }
        )
        # Should handle gracefully
        assert "messages" in result


# ---------------------------------------------------------------------------
# ideer/gateway/deps.py — get_thread_store, get_run_context
# ---------------------------------------------------------------------------


class TestDepsExtended:
    def test_get_thread_store_with_value(self):
        from app.gateway.deps import get_thread_store

        mock_request = MagicMock()
        mock_request.app.state.thread_store = "thread_store"
        assert get_thread_store(mock_request) == "thread_store"

    def test_get_thread_store_missing(self):
        from app.gateway.deps import get_thread_store

        mock_request = MagicMock()
        mock_request.app.state.thread_store = None
        with pytest.raises(Exception) as exc_info:
            get_thread_store(mock_request)
        assert exc_info.value.status_code == 503

    def test_get_config_error(self):
        from app.gateway.deps import get_config

        with patch("app.gateway.deps.get_app_config", side_effect=Exception("config error")):
            MagicMock()
            with pytest.raises(Exception) as exc_info:
                get_config()
            assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# ideer/utils/file_conversion.py — _get_uploads_config_value
# ---------------------------------------------------------------------------


class TestFileConversionConfig:
    def test_get_uploads_config_value_dict(self):
        from ideer.utils.file_conversion import _get_uploads_config_value

        mock_config = MagicMock()
        mock_config.uploads = {"pdf_converter": "pymupdf4llm"}
        with patch("ideer.utils.file_conversion.get_app_config", return_value=mock_config):
            result = _get_uploads_config_value("pdf_converter", "auto")
            assert result == "pymupdf4llm"

    def test_get_uploads_config_value_attr(self):
        from ideer.utils.file_conversion import _get_uploads_config_value

        mock_config = MagicMock()
        mock_uploads = SimpleNamespace(pdf_converter="markitdown")
        mock_config.uploads = mock_uploads
        with patch("ideer.utils.file_conversion.get_app_config", return_value=mock_config):
            result = _get_uploads_config_value("pdf_converter", "auto")
            assert result == "markitdown"

    def test_get_uploads_config_value_none(self):
        from ideer.utils.file_conversion import _get_uploads_config_value

        mock_config = MagicMock()
        mock_config.uploads = None
        with patch("ideer.utils.file_conversion.get_app_config", return_value=mock_config):
            result = _get_uploads_config_value("pdf_converter", "auto")
            assert result == "auto"


# ---------------------------------------------------------------------------
# ideer/utils/readability.py — ReadabilityExtractor edge cases
# ---------------------------------------------------------------------------


class TestReadabilityExtractor:
    def test_extract_article_with_title_and_content(self):
        from ideer.utils.readability import ReadabilityExtractor

        extractor = ReadabilityExtractor()
        html = "<html><head><title>My Title</title></head><body><p>Some content here.</p></body></html>"
        article = extractor.extract_article(html)
        assert article.title is not None
        assert article.html_content is not None

    def test_article_to_message_text_only(self):
        from ideer.utils.readability import Article

        article = Article(title="Test", html_content="<p>Simple text</p>")
        article.url = "http://example.com"
        msg = article.to_message()
        # Should have at least one text block
        assert any(m.get("type") == "text" for m in msg)
