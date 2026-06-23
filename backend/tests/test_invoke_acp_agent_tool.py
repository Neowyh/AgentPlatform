"""Tests for the built-in ACP invocation tool."""

import sys
from types import SimpleNamespace

import pytest

from ideer.config.acp_config import ACPAgentConfig
from ideer.config.extensions_config import ExtensionsConfig, McpServerConfig, set_extensions_config
from ideer.tools.builtins.invoke_acp_agent_tool import (
    _build_acp_mcp_servers,
    _build_mcp_servers,
    _build_permission_response,
    _format_invocation_error,
    _get_work_dir,
    build_invoke_acp_agent_tool,
)
from ideer.tools.tools import get_available_tools

# ---------------------------------------------------------------------------
# _build_mcp_servers
# ---------------------------------------------------------------------------


def test_build_mcp_servers_filters_disabled_and_maps_transports():
    set_extensions_config(ExtensionsConfig(mcp_servers={"stale": McpServerConfig(enabled=True, type="stdio", command="echo")}, skills={}))
    fresh_config = ExtensionsConfig(
        mcp_servers={
            "stdio": McpServerConfig(enabled=True, type="stdio", command="npx", args=["srv"]),
            "http": McpServerConfig(enabled=True, type="http", url="https://example.com/mcp"),
            "disabled": McpServerConfig(enabled=False, type="stdio", command="echo"),
        },
        skills={},
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "ideer.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(lambda cls: fresh_config),
    )

    try:
        assert _build_mcp_servers() == {
            "stdio": {"transport": "stdio", "command": "npx", "args": ["srv"]},
            "http": {"transport": "http", "url": "https://example.com/mcp"},
        }
    finally:
        monkeypatch.undo()
        set_extensions_config(ExtensionsConfig(mcp_servers={}, skills={}))


# ---------------------------------------------------------------------------
# _build_acp_mcp_servers
# ---------------------------------------------------------------------------


def test_build_acp_mcp_servers_formats_list_payload():
    set_extensions_config(ExtensionsConfig(mcp_servers={"stale": McpServerConfig(enabled=True, type="stdio", command="echo")}, skills={}))
    fresh_config = ExtensionsConfig(
        mcp_servers={
            "stdio": McpServerConfig(enabled=True, type="stdio", command="npx", args=["srv"], env={"FOO": "bar"}),
            "http": McpServerConfig(enabled=True, type="http", url="https://example.com/mcp", headers={"Authorization": "Bearer token"}),
            "disabled": McpServerConfig(enabled=False, type="stdio", command="echo"),
        },
        skills={},
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "ideer.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(lambda cls: fresh_config),
    )

    try:
        assert _build_acp_mcp_servers() == [
            {
                "name": "stdio",
                "type": "stdio",
                "command": "npx",
                "args": ["srv"],
                "env": [{"name": "FOO", "value": "bar"}],
            },
            {
                "name": "http",
                "type": "http",
                "url": "https://example.com/mcp",
                "headers": [{"name": "Authorization", "value": "Bearer token"}],
            },
        ]
    finally:
        monkeypatch.undo()
        set_extensions_config(ExtensionsConfig(mcp_servers={}, skills={}))


def test_build_acp_mcp_servers_sse_transport():
    """SSE transport should be treated like http."""
    fresh_config = ExtensionsConfig(
        mcp_servers={
            "sse_srv": McpServerConfig(enabled=True, type="sse", url="https://example.com/sse", headers={"X-Key": "val"}),
        },
        skills={},
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "ideer.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(lambda cls: fresh_config),
    )

    try:
        result = _build_acp_mcp_servers()
        assert len(result) == 1
        assert result[0]["type"] == "sse"
        assert result[0]["url"] == "https://example.com/sse"
    finally:
        monkeypatch.undo()


def test_build_acp_mcp_servers_stdio_missing_command_raises():
    """stdio transport without command should raise ValueError."""
    fresh_config = ExtensionsConfig(
        mcp_servers={
            "bad": McpServerConfig(enabled=True, type="stdio", command=None),
        },
        skills={},
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "ideer.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(lambda cls: fresh_config),
    )

    try:
        with pytest.raises(ValueError, match="requires 'command'"):
            _build_acp_mcp_servers()
    finally:
        monkeypatch.undo()


def test_build_acp_mcp_servers_http_missing_url_raises():
    """http transport without url should raise ValueError."""
    fresh_config = ExtensionsConfig(
        mcp_servers={
            "bad": McpServerConfig(enabled=True, type="http", url=None),
        },
        skills={},
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "ideer.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(lambda cls: fresh_config),
    )

    try:
        with pytest.raises(ValueError, match="requires 'url'"):
            _build_acp_mcp_servers()
    finally:
        monkeypatch.undo()


def test_build_acp_mcp_servers_unsupported_transport_raises():
    """Unsupported transport type should raise ValueError."""
    fresh_config = ExtensionsConfig(
        mcp_servers={
            "bad": McpServerConfig(enabled=True, type="grpc", url="grpc://localhost"),
        },
        skills={},
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "ideer.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(lambda cls: fresh_config),
    )

    try:
        with pytest.raises(ValueError, match="unsupported transport type"):
            _build_acp_mcp_servers()
    finally:
        monkeypatch.undo()


# ---------------------------------------------------------------------------
# _build_permission_response
# ---------------------------------------------------------------------------


def test_build_permission_response_prefers_allow_once():
    response = _build_permission_response(
        [
            SimpleNamespace(kind="reject_once", optionId="deny"),
            SimpleNamespace(kind="allow_always", optionId="always"),
            SimpleNamespace(kind="allow_once", optionId="once"),
        ],
        auto_approve=True,
    )

    assert response.outcome.outcome == "selected"
    assert response.outcome.option_id == "once"


def test_build_permission_response_falls_back_to_allow_always():
    """When no allow_once is available, falls back to allow_always."""
    response = _build_permission_response(
        [
            SimpleNamespace(kind="reject_once", optionId="deny"),
            SimpleNamespace(kind="allow_always", optionId="always"),
        ],
        auto_approve=True,
    )

    assert response.outcome.outcome == "selected"
    assert response.outcome.option_id == "always"


def test_build_permission_response_denies_when_no_allow_option():
    response = _build_permission_response(
        [
            SimpleNamespace(kind="reject_once", optionId="deny"),
            SimpleNamespace(kind="reject_always", optionId="deny-forever"),
        ],
        auto_approve=True,
    )

    assert response.outcome.outcome == "cancelled"


def test_build_permission_response_denies_when_auto_approve_false():
    response = _build_permission_response(
        [
            SimpleNamespace(kind="allow_once", optionId="once"),
            SimpleNamespace(kind="allow_always", optionId="always"),
        ],
        auto_approve=False,
    )

    assert response.outcome.outcome == "cancelled"


def test_build_permission_response_option_without_option_id():
    """Options without option_id (or optionId) should be skipped."""
    response = _build_permission_response(
        [
            SimpleNamespace(kind="allow_once"),  # no optionId
            SimpleNamespace(kind="reject_once", optionId="deny"),
        ],
        auto_approve=True,
    )

    assert response.outcome.outcome == "cancelled"


def test_build_permission_response_uses_option_id_attr():
    """When option has option_id attribute (not optionId), should still work."""
    response = _build_permission_response(
        [SimpleNamespace(kind="allow_once", option_id="my-id")],
        auto_approve=True,
    )

    assert response.outcome.outcome == "selected"
    assert response.outcome.option_id == "my-id"


# ---------------------------------------------------------------------------
# _format_invocation_error
# ---------------------------------------------------------------------------


def test_format_invocation_error_non_file_not_found():
    result = _format_invocation_error("codex", "codex-acp", RuntimeError("bad"))
    assert "Error invoking ACP agent 'codex'" in result
    assert "bad" in result


def test_format_invocation_error_file_not_found_generic():
    with pytest.MonkeyPatch().context() as m:
        m.setattr("shutil.which", lambda cmd: None)
        result = _format_invocation_error("my-agent", "my-cmd", FileNotFoundError())

    assert "Command 'my-cmd' was not found on PATH" in result
    assert "my-agent" in result
    assert "config.yaml" in result


def test_format_invocation_error_codex_without_acp_adapter():
    with pytest.MonkeyPatch().context() as m:
        m.setattr("shutil.which", lambda cmd: "/usr/bin/codex" if cmd == "codex" else None)
        result = _format_invocation_error("codex", "codex-acp", FileNotFoundError())

    assert "codex-acp" in result
    assert "codex-acp" in result or "ACP adapter" in result


def test_format_invocation_error_codex_no_codex_binary():
    with pytest.MonkeyPatch().context() as m:
        m.setattr("shutil.which", lambda cmd: None)
        result = _format_invocation_error("codex", "codex-acp", FileNotFoundError())

    assert "not found on PATH" in result


# ---------------------------------------------------------------------------
# _get_work_dir
# ---------------------------------------------------------------------------


def test_get_work_dir_uses_base_dir_when_no_thread_id(monkeypatch, tmp_path):
    from ideer.config import paths as paths_module

    monkeypatch.setattr(paths_module, "get_paths", lambda: paths_module.Paths(base_dir=tmp_path))
    result = _get_work_dir(None)
    expected = tmp_path / "acp-workspace"
    assert result == str(expected)
    assert expected.exists()


def test_get_work_dir_uses_per_thread_path_when_thread_id_given(monkeypatch, tmp_path):
    from ideer.config import paths as paths_module
    from ideer.runtime import user_context as uc_module

    monkeypatch.setattr(paths_module, "get_paths", lambda: paths_module.Paths(base_dir=tmp_path))
    monkeypatch.setattr(uc_module, "get_effective_user_id", lambda: None)
    result = _get_work_dir("thread-abc-123")
    expected = tmp_path / "threads" / "thread-abc-123" / "acp-workspace"
    assert result == str(expected)
    assert expected.exists()


def test_get_work_dir_falls_back_to_global_for_invalid_thread_id(monkeypatch, tmp_path):
    from ideer.config import paths as paths_module

    monkeypatch.setattr(paths_module, "get_paths", lambda: paths_module.Paths(base_dir=tmp_path))
    result = _get_work_dir("../../evil")
    expected = tmp_path / "acp-workspace"
    assert result == str(expected)
    assert expected.exists()


# ---------------------------------------------------------------------------
# build_invoke_acp_agent_tool — description + unknown agent
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_build_invoke_tool_description_and_unknown_agent_error():
    tool = build_invoke_acp_agent_tool(
        {
            "codex": ACPAgentConfig(command="codex-acp", description="Codex CLI"),
            "claude_code": ACPAgentConfig(command="claude-code-acp", description="Claude Code"),
        }
    )

    assert "Available agents:" in tool.description
    assert "- codex: Codex CLI" in tool.description
    assert "- claude_code: Claude Code" in tool.description
    assert "Do NOT include /mnt/user-data paths" in tool.description
    assert "/mnt/acp-workspace/" in tool.description

    result = await tool.coroutine(agent="missing", prompt="do work")
    assert result == "Error: Unknown agent 'missing'. Available: codex, claude_code"


# ---------------------------------------------------------------------------
# Full integration tests with dummy ACP module
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_invoke_acp_agent_uses_fixed_acp_workspace(monkeypatch, tmp_path):
    from ideer.config import paths as paths_module

    monkeypatch.setattr(paths_module, "get_paths", lambda: paths_module.Paths(base_dir=tmp_path))

    monkeypatch.setattr(
        "ideer.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(
            lambda cls: ExtensionsConfig(
                mcp_servers={"github": McpServerConfig(enabled=True, type="stdio", command="npx", args=["github-mcp"])},
                skills={},
            )
        ),
    )

    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self) -> None:
            self._chunks: list[str] = []

        @property
        def collected_text(self) -> str:
            return "".join(self._chunks)

        async def session_update(self, session_id: str, update, **kwargs) -> None:
            if hasattr(update, "content") and hasattr(update.content, "text"):
                self._chunks.append(update.content.text)

        async def request_permission(self, options, session_id: str, tool_call, **kwargs):
            raise AssertionError("request_permission should not be called in this test")

    class DummyConn:
        async def initialize(self, **kwargs):
            captured["initialize"] = kwargs

        async def new_session(self, **kwargs):
            captured["new_session"] = kwargs
            return SimpleNamespace(session_id="session-1")

        async def prompt(self, **kwargs):
            captured["prompt"] = kwargs
            client = captured["client"]
            # Must use TextContentBlock instance so isinstance check passes
            text_block_cls = sys.modules["acp.schema"].TextContentBlock
            await client.session_update(
                "session-1",
                SimpleNamespace(content=text_block_cls("ACP result")),
            )

    class DummyProcessContext:
        def __init__(self, client, cmd, *args, cwd):
            captured["client"] = client
            captured["spawn"] = {"cmd": cmd, "args": list(args), "cwd": cwd}

        async def __aenter__(self):
            return DummyConn(), object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setitem(
        sys.modules,
        "acp",
        SimpleNamespace(
            PROTOCOL_VERSION="2026-03-24",
            Client=DummyClient,
            spawn_agent_process=lambda client, cmd, *args, env=None, cwd: DummyProcessContext(client, cmd, *args, cwd=cwd),
            text_block=lambda text: {"type": "text", "text": text},
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "acp.schema",
        SimpleNamespace(
            ClientCapabilities=lambda: {"supports": []},
            Implementation=lambda **kwargs: kwargs,
            TextContentBlock=type(
                "TextContentBlock",
                (),
                {"__init__": lambda self, text: setattr(self, "text", text)},
            ),
            AllowedOutcome=lambda **kwargs: SimpleNamespace(**kwargs),
            DeniedOutcome=lambda **kwargs: SimpleNamespace(**kwargs),
            RequestPermissionResponse=lambda outcome: SimpleNamespace(outcome=outcome),
        ),
    )

    expected_cwd = str(tmp_path / "acp-workspace")

    tool = build_invoke_acp_agent_tool(
        {
            "codex": ACPAgentConfig(
                command="codex-acp",
                args=["--json"],
                description="Codex CLI",
                model="gpt-5-codex",
            )
        }
    )

    try:
        result = await tool.coroutine(
            agent="codex",
            prompt="Implement the fix",
        )
    finally:
        sys.modules.pop("acp", None)
        sys.modules.pop("acp.schema", None)

    assert result == "ACP result"
    assert captured["spawn"] == {"cmd": "codex-acp", "args": ["--json"], "cwd": expected_cwd}
    assert captured["new_session"] == {
        "cwd": expected_cwd,
        "mcp_servers": [
            {
                "name": "github",
                "type": "stdio",
                "command": "npx",
                "args": ["github-mcp"],
                "env": [],
            }
        ],
        "model": "gpt-5-codex",
    }
    assert captured["prompt"] == {
        "session_id": "session-1",
        "prompt": [{"type": "text", "text": "Implement the fix"}],
    }


@pytest.mark.anyio
async def test_invoke_acp_agent_uses_per_thread_workspace_when_thread_id_in_config(monkeypatch, tmp_path):
    from ideer.config import paths as paths_module
    from ideer.runtime import user_context as uc_module

    monkeypatch.setattr(paths_module, "get_paths", lambda: paths_module.Paths(base_dir=tmp_path))
    monkeypatch.setattr(uc_module, "get_effective_user_id", lambda: None)

    monkeypatch.setattr(
        "ideer.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(lambda cls: ExtensionsConfig(mcp_servers={}, skills={})),
    )

    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self) -> None:
            self._chunks: list[str] = []

        @property
        def collected_text(self) -> str:
            return "".join(self._chunks)

        async def session_update(self, session_id, update, **kwargs):
            pass

        async def request_permission(self, options, session_id, tool_call, **kwargs):
            raise AssertionError("should not be called")

    class DummyConn:
        async def initialize(self, **kwargs):
            pass

        async def new_session(self, **kwargs):
            captured["new_session"] = kwargs
            return SimpleNamespace(session_id="s1")

        async def prompt(self, **kwargs):
            pass

    class DummyProcessContext:
        def __init__(self, client, cmd, *args, cwd):
            captured["cwd"] = cwd

        async def __aenter__(self):
            return DummyConn(), object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setitem(
        sys.modules,
        "acp",
        SimpleNamespace(
            PROTOCOL_VERSION="2026-03-24",
            Client=DummyClient,
            spawn_agent_process=lambda client, cmd, *args, env=None, cwd: DummyProcessContext(client, cmd, *args, cwd=cwd),
            text_block=lambda text: {"type": "text", "text": text},
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "acp.schema",
        SimpleNamespace(
            ClientCapabilities=lambda: {},
            Implementation=lambda **kwargs: kwargs,
            TextContentBlock=type("TextContentBlock", (), {"__init__": lambda self, text: setattr(self, "text", text)}),
            AllowedOutcome=lambda **kwargs: SimpleNamespace(**kwargs),
            DeniedOutcome=lambda **kwargs: SimpleNamespace(**kwargs),
            RequestPermissionResponse=lambda outcome: SimpleNamespace(outcome=outcome),
        ),
    )

    thread_id = "thread-xyz-789"
    expected_cwd = str(tmp_path / "threads" / thread_id / "acp-workspace")

    tool = build_invoke_acp_agent_tool({"codex": ACPAgentConfig(command="codex-acp", description="Codex CLI")})

    try:
        await tool.coroutine(
            agent="codex",
            prompt="Do something",
            config={"configurable": {"thread_id": thread_id}},
        )
    finally:
        sys.modules.pop("acp", None)
        sys.modules.pop("acp.schema", None)

    assert captured["cwd"] == expected_cwd


@pytest.mark.anyio
async def test_invoke_acp_agent_passes_env_to_spawn(monkeypatch, tmp_path):
    from ideer.config import paths as paths_module

    monkeypatch.setattr(paths_module, "get_paths", lambda: paths_module.Paths(base_dir=tmp_path))
    monkeypatch.setattr(
        "ideer.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(lambda cls: ExtensionsConfig(mcp_servers={}, skills={})),
    )
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-from-env")

    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self) -> None:
            self._chunks: list[str] = []

        @property
        def collected_text(self) -> str:
            return ""

        async def session_update(self, session_id, update, **kwargs):
            pass

        async def request_permission(self, options, session_id, tool_call, **kwargs):
            raise AssertionError("should not be called")

    class DummyConn:
        async def initialize(self, **kwargs):
            pass

        async def new_session(self, **kwargs):
            return SimpleNamespace(session_id="s1")

        async def prompt(self, **kwargs):
            pass

    class DummyProcessContext:
        def __init__(self, client, cmd, *args, env=None, cwd):
            captured["env"] = env

        async def __aenter__(self):
            return DummyConn(), object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setitem(
        sys.modules,
        "acp",
        SimpleNamespace(
            PROTOCOL_VERSION="2026-03-24",
            Client=DummyClient,
            spawn_agent_process=lambda client, cmd, *args, env=None, cwd: DummyProcessContext(client, cmd, *args, env=env, cwd=cwd),
            text_block=lambda text: {"type": "text", "text": text},
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "acp.schema",
        SimpleNamespace(
            ClientCapabilities=lambda: {},
            Implementation=lambda **kwargs: kwargs,
            TextContentBlock=type("TextContentBlock", (), {"__init__": lambda self, text: setattr(self, "text", text)}),
            AllowedOutcome=lambda **kwargs: SimpleNamespace(**kwargs),
            DeniedOutcome=lambda **kwargs: SimpleNamespace(**kwargs),
            RequestPermissionResponse=lambda outcome: SimpleNamespace(outcome=outcome),
        ),
    )

    tool = build_invoke_acp_agent_tool(
        {
            "codex": ACPAgentConfig(
                command="codex-acp",
                description="Codex CLI",
                env={"OPENAI_API_KEY": "$TEST_OPENAI_KEY", "FOO": "bar"},
            )
        }
    )

    try:
        await tool.coroutine(agent="codex", prompt="Do something")
    finally:
        sys.modules.pop("acp", None)
        sys.modules.pop("acp.schema", None)

    assert captured["env"] == {"OPENAI_API_KEY": "sk-from-env", "FOO": "bar"}


@pytest.mark.anyio
async def test_invoke_acp_agent_skips_invalid_mcp_servers(monkeypatch, tmp_path, caplog):
    from ideer.config import paths as paths_module

    monkeypatch.setattr(paths_module, "get_paths", lambda: paths_module.Paths(base_dir=tmp_path))
    monkeypatch.setattr(
        "ideer.tools.builtins.invoke_acp_agent_tool._build_acp_mcp_servers",
        lambda: (_ for _ in ()).throw(ValueError("missing command")),
    )

    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self) -> None:
            self._chunks: list[str] = []

        @property
        def collected_text(self) -> str:
            return ""

        async def session_update(self, session_id, update, **kwargs):
            pass

        async def request_permission(self, options, session_id, tool_call, **kwargs):
            raise AssertionError("should not be called")

    class DummyConn:
        async def initialize(self, **kwargs):
            pass

        async def new_session(self, **kwargs):
            captured["new_session"] = kwargs
            return SimpleNamespace(session_id="s1")

        async def prompt(self, **kwargs):
            pass

    class DummyProcessContext:
        def __init__(self, client, cmd, *args, env=None, cwd=None):
            captured["spawn"] = {"cmd": cmd, "args": list(args), "env": env, "cwd": cwd}

        async def __aenter__(self):
            return DummyConn(), object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setitem(
        sys.modules,
        "acp",
        SimpleNamespace(
            PROTOCOL_VERSION="2026-03-24",
            Client=DummyClient,
            spawn_agent_process=lambda client, cmd, *args, env=None, cwd: DummyProcessContext(client, cmd, *args, env=env, cwd=cwd),
            text_block=lambda text: {"type": "text", "text": text},
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "acp.schema",
        SimpleNamespace(
            ClientCapabilities=lambda: {},
            Implementation=lambda **kwargs: kwargs,
            TextContentBlock=type("TextContentBlock", (), {"__init__": lambda self, text: setattr(self, "text", text)}),
            AllowedOutcome=lambda **kwargs: SimpleNamespace(**kwargs),
            DeniedOutcome=lambda **kwargs: SimpleNamespace(**kwargs),
            RequestPermissionResponse=lambda outcome: SimpleNamespace(outcome=outcome),
        ),
    )

    tool = build_invoke_acp_agent_tool({"codex": ACPAgentConfig(command="codex-acp", description="Codex CLI")})
    caplog.set_level("WARNING")

    try:
        await tool.coroutine(agent="codex", prompt="Do something")
    finally:
        sys.modules.pop("acp", None)
        sys.modules.pop("acp.schema", None)

    assert captured["new_session"]["mcp_servers"] == []
    assert "continuing without MCP servers" in caplog.text
    assert "missing command" in caplog.text


@pytest.mark.anyio
async def test_invoke_acp_agent_passes_none_env_when_not_configured(monkeypatch, tmp_path):
    from ideer.config import paths as paths_module

    monkeypatch.setattr(paths_module, "get_paths", lambda: paths_module.Paths(base_dir=tmp_path))
    monkeypatch.setattr(
        "ideer.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(lambda cls: ExtensionsConfig(mcp_servers={}, skills={})),
    )

    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self) -> None:
            self._chunks: list[str] = []

        @property
        def collected_text(self) -> str:
            return ""

        async def session_update(self, session_id, update, **kwargs):
            pass

        async def request_permission(self, options, session_id, tool_call, **kwargs):
            raise AssertionError("should not be called")

    class DummyConn:
        async def initialize(self, **kwargs):
            pass

        async def new_session(self, **kwargs):
            return SimpleNamespace(session_id="s1")

        async def prompt(self, **kwargs):
            pass

    class DummyProcessContext:
        def __init__(self, client, cmd, *args, env=None, cwd):
            captured["env"] = env

        async def __aenter__(self):
            return DummyConn(), object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setitem(
        sys.modules,
        "acp",
        SimpleNamespace(
            PROTOCOL_VERSION="2026-03-24",
            Client=DummyClient,
            spawn_agent_process=lambda client, cmd, *args, env=None, cwd: DummyProcessContext(client, cmd, *args, env=env, cwd=cwd),
            text_block=lambda text: {"type": "text", "text": text},
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "acp.schema",
        SimpleNamespace(
            ClientCapabilities=lambda: {},
            Implementation=lambda **kwargs: kwargs,
            TextContentBlock=type("TextContentBlock", (), {"__init__": lambda self, text: setattr(self, "text", text)}),
            AllowedOutcome=lambda **kwargs: SimpleNamespace(**kwargs),
            DeniedOutcome=lambda **kwargs: SimpleNamespace(**kwargs),
            RequestPermissionResponse=lambda outcome: SimpleNamespace(outcome=outcome),
        ),
    )

    tool = build_invoke_acp_agent_tool({"codex": ACPAgentConfig(command="codex-acp", description="Codex CLI")})

    try:
        await tool.coroutine(agent="codex", prompt="Do something")
    finally:
        sys.modules.pop("acp", None)
        sys.modules.pop("acp.schema", None)

    assert captured["env"] is None


@pytest.mark.anyio
async def test_invoke_acp_agent_returns_no_response_when_empty(monkeypatch, tmp_path):
    """When collected_text is empty, tool returns '(no response)'."""
    from ideer.config import paths as paths_module

    monkeypatch.setattr(paths_module, "get_paths", lambda: paths_module.Paths(base_dir=tmp_path))
    monkeypatch.setattr(
        "ideer.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(lambda cls: ExtensionsConfig(mcp_servers={}, skills={})),
    )

    class DummyClient:
        def __init__(self) -> None:
            self._chunks: list[str] = []

        @property
        def collected_text(self) -> str:
            return ""

        async def session_update(self, session_id, update, **kwargs):
            pass

        async def request_permission(self, options, session_id, tool_call, **kwargs):
            raise AssertionError("should not be called")

    class DummyConn:
        async def initialize(self, **kwargs):
            pass

        async def new_session(self, **kwargs):
            return SimpleNamespace(session_id="s1")

        async def prompt(self, **kwargs):
            pass

    class DummyProcessContext:
        def __init__(self, client, cmd, *args, env=None, cwd):
            pass

        async def __aenter__(self):
            return DummyConn(), object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setitem(
        sys.modules,
        "acp",
        SimpleNamespace(
            PROTOCOL_VERSION="2026-03-24",
            Client=DummyClient,
            spawn_agent_process=lambda client, cmd, *args, env=None, cwd: DummyProcessContext(client, cmd, *args, cwd=cwd),
            text_block=lambda text: {"type": "text", "text": text},
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "acp.schema",
        SimpleNamespace(
            ClientCapabilities=lambda: {},
            Implementation=lambda **kwargs: kwargs,
            TextContentBlock=type("TextContentBlock", (), {"__init__": lambda self, text: setattr(self, "text", text)}),
            AllowedOutcome=lambda **kwargs: SimpleNamespace(**kwargs),
            DeniedOutcome=lambda **kwargs: SimpleNamespace(**kwargs),
            RequestPermissionResponse=lambda outcome: SimpleNamespace(outcome=outcome),
        ),
    )

    tool = build_invoke_acp_agent_tool({"codex": ACPAgentConfig(command="codex-acp", description="Codex CLI")})

    try:
        result = await tool.coroutine(agent="codex", prompt="Do something")
    finally:
        sys.modules.pop("acp", None)
        sys.modules.pop("acp.schema", None)

    assert result == "(no response)"


@pytest.mark.anyio
async def test_invoke_acp_agent_handles_spawn_exception(monkeypatch, tmp_path):
    """When spawn_agent_process raises, the tool returns a formatted error."""
    from ideer.config import paths as paths_module

    monkeypatch.setattr(paths_module, "get_paths", lambda: paths_module.Paths(base_dir=tmp_path))
    monkeypatch.setattr(
        "ideer.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(lambda cls: ExtensionsConfig(mcp_servers={}, skills={})),
    )

    class DummyClient:
        def __init__(self) -> None:
            self._chunks: list[str] = []

        @property
        def collected_text(self) -> str:
            return ""

        async def session_update(self, session_id, update, **kwargs):
            pass

        async def request_permission(self, options, session_id, tool_call, **kwargs):
            raise AssertionError("should not be called")

    def failing_spawn(client, cmd, *args, env=None, cwd):
        raise FileNotFoundError("codex-acp")

    monkeypatch.setitem(
        sys.modules,
        "acp",
        SimpleNamespace(
            PROTOCOL_VERSION="2026-03-24",
            Client=DummyClient,
            spawn_agent_process=failing_spawn,
            text_block=lambda text: {"type": "text", "text": text},
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "acp.schema",
        SimpleNamespace(
            ClientCapabilities=lambda: {},
            Implementation=lambda **kwargs: kwargs,
            AllowedOutcome=lambda **kwargs: SimpleNamespace(**kwargs),
            DeniedOutcome=lambda **kwargs: SimpleNamespace(**kwargs),
            RequestPermissionResponse=lambda outcome: SimpleNamespace(outcome=outcome),
        ),
    )

    tool = build_invoke_acp_agent_tool({"codex": ACPAgentConfig(command="codex-acp", description="Codex CLI")})

    try:
        result = await tool.coroutine(agent="codex", prompt="Do something")
    finally:
        sys.modules.pop("acp", None)
        sys.modules.pop("acp.schema", None)

    assert "Error invoking ACP agent 'codex'" in result
    assert "not found on PATH" in result


@pytest.mark.anyio
async def test_invoke_acp_agent_handles_import_error(monkeypatch, tmp_path):
    """When acp package is not installed, returns a helpful error."""
    from ideer.config import paths as paths_module

    monkeypatch.setattr(paths_module, "get_paths", lambda: paths_module.Paths(base_dir=tmp_path))

    # Make acp importable but raise ImportError on specific import
    original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

    def fake_import(name, *args, **kwargs):
        if name == "acp":
            raise ImportError("No module named 'acp'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    tool = build_invoke_acp_agent_tool({"codex": ACPAgentConfig(command="codex-acp", description="Codex CLI")})

    result = await tool.coroutine(agent="codex", prompt="Do something")
    assert "agent-client-protocol package is not installed" in result


# ---------------------------------------------------------------------------
# Integration with get_available_tools
# ---------------------------------------------------------------------------


def test_get_available_tools_includes_invoke_acp_agent_when_agents_configured(monkeypatch):
    from ideer.config.acp_config import load_acp_config_from_dict

    load_acp_config_from_dict(
        {
            "codex": {
                "command": "codex-acp",
                "args": [],
                "description": "Codex CLI",
            }
        }
    )

    fake_config = SimpleNamespace(
        tools=[],
        models=[],
        tool_search=SimpleNamespace(enabled=False),
        get_model_config=lambda name: None,
    )
    monkeypatch.setattr("ideer.tools.tools.get_app_config", lambda: fake_config)
    monkeypatch.setattr(
        "ideer.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(lambda cls: ExtensionsConfig(mcp_servers={}, skills={})),
    )

    tools = get_available_tools(include_mcp=True, subagent_enabled=False)
    assert "invoke_acp_agent" in [tool.name for tool in tools]

    load_acp_config_from_dict({})


def test_get_available_tools_uses_explicit_app_config_for_acp_agents(monkeypatch):
    explicit_agents = {"codex": ACPAgentConfig(command="codex-acp", description="Codex CLI")}
    explicit_config = SimpleNamespace(
        tools=[],
        models=[],
        tool_search=SimpleNamespace(enabled=False),
        skill_evolution=SimpleNamespace(enabled=False),
        get_model_config=lambda name: None,
        acp_agents=explicit_agents,
    )
    sentinel_tool = SimpleNamespace(name="invoke_acp_agent")
    captured: dict[str, object] = {}

    def fail_get_acp_agents():
        raise AssertionError("ambient get_acp_agents() must not be used when app_config is explicit")

    def fake_build_invoke_acp_agent_tool(agents):
        captured["agents"] = agents
        return sentinel_tool

    monkeypatch.setattr("ideer.tools.tools.is_host_bash_allowed", lambda config=None: True)
    monkeypatch.setattr("ideer.config.acp_config.get_acp_agents", fail_get_acp_agents)
    monkeypatch.setattr("ideer.tools.builtins.invoke_acp_agent_tool.build_invoke_acp_agent_tool", fake_build_invoke_acp_agent_tool)

    tools = get_available_tools(include_mcp=False, subagent_enabled=False, app_config=explicit_config)

    assert captured["agents"] is explicit_agents
    assert "invoke_acp_agent" in [tool.name for tool in tools]
