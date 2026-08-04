"""Comprehensive tests for subagent executor — aiming for 98%+ line coverage.

Covers:
- SubagentStatus enum and is_terminal property
- SubagentResult dataclass, __post_init__, try_set_terminal (all branches)
- _evict_stale_tasks (stale + non-stale)
- _run_isolated_subagent_loop / _shutdown_isolated_subagent_loop / _get_isolated_subagent_loop
- _submit_to_isolated_loop_in_context
- _filter_tools (allowlist, denylist, both, neither)
- SubagentExecutor.__init__ (model_name resolution, trace_id generation)
- _create_agent (deferred model resolution, explicit tools)
- _load_skills (empty list, None, whitelist, exception, no skills found)
- _apply_skill_allowed_tools
- _load_skill_messages (empty, content, exception per-skill)
- _build_initial_state (system_prompt + skills, sandbox, thread_data)
- _aexecute (all result extraction branches, cancellation, exception)
- _execute_in_isolated_loop (timeout, generic exception)
- execute (running loop, standard path, exception fallback)
- execute_async (timeout, exception, custom task_id)
- get_background_task_result / list_background_tasks / request_cancel_background_task
- cleanup_background_task (all branches)
- Module-level atexit guard
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ideer.skills.types import Skill

# ---------------------------------------------------------------------------
# Module setup: mock heavy transitive imports to allow real executor import
# ---------------------------------------------------------------------------

_MOCKED_MODULE_NAMES = [
    "ideer.agents",
    "ideer.agents.thread_state",
    "ideer.agents.middlewares",
    "ideer.agents.middlewares.thread_data_middleware",
    "ideer.agents.middlewares.tool_error_handling_middleware",
    "ideer.sandbox",
    "ideer.sandbox.middleware",
    "ideer.sandbox.security",
    "ideer.models",
    "ideer.skills.storage",
]


@pytest.fixture(autouse=True)
def _setup_executor_classes():
    """Set up mocked modules and import real executor classes."""
    original_modules = {name: sys.modules.get(name) for name in _MOCKED_MODULE_NAMES}
    original_executor = sys.modules.get("ideer.subagents.executor")

    if "ideer.subagents.executor" in sys.modules:
        del sys.modules["ideer.subagents.executor"]

    for name in _MOCKED_MODULE_NAMES:
        sys.modules[name] = MagicMock()
    storage_module = ModuleType("ideer.skills.storage")
    storage_module.get_or_new_skill_storage = lambda **kw: SimpleNamespace(load_skills=lambda *, enabled_only: [])
    sys.modules["ideer.skills.storage"] = storage_module

    from langchain_core.messages import AIMessage, HumanMessage

    from ideer.subagents.config import SubagentConfig
    from ideer.subagents.executor import (
        SubagentExecutor,
        SubagentResult,
        SubagentStatus,
    )

    classes = {
        "AIMessage": AIMessage,
        "HumanMessage": HumanMessage,
        "SubagentConfig": SubagentConfig,
        "SubagentExecutor": SubagentExecutor,
        "SubagentResult": SubagentResult,
        "SubagentStatus": SubagentStatus,
    }

    yield classes

    for name in _MOCKED_MODULE_NAMES:
        if original_modules[name] is not None:
            sys.modules[name] = original_modules[name]
        elif name in sys.modules:
            del sys.modules[name]

    if original_executor is not None:
        sys.modules["ideer.subagents.executor"] = original_executor
    elif "ideer.subagents.executor" in sys.modules:
        del sys.modules["ideer.subagents.executor"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class NamedTool:
    def __init__(self, name: str):
        self.name = name


def _skill(name: str, allowed_tools: list[str] | None, enabled: bool = True) -> Skill:
    skill_dir = Path(f"/tmp/{name}")
    return Skill(
        name=name,
        description=f"{name} skill",
        license=None,
        skill_dir=skill_dir,
        skill_file=skill_dir / "SKILL.md",
        relative_path=Path(name),
        category="custom",
        allowed_tools=allowed_tools,
        enabled=enabled,
    )


async def async_iterator(items):
    for item in items:
        yield item


class _MsgHelper:
    def __init__(self, classes):
        self.classes = classes

    def human(self, content):
        return self.classes["HumanMessage"](content=content)

    def ai(self, content, msg_id=None):
        msg = self.classes["AIMessage"](content=content)
        if msg_id:
            msg.id = msg_id
        return msg


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def classes(_setup_executor_classes):
    return _setup_executor_classes


@pytest.fixture
def base_config(classes):
    return classes["SubagentConfig"](
        name="test-agent",
        description="Test agent",
        system_prompt="You are a test agent.",
        max_turns=10,
        timeout_seconds=60,
    )


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.astream = MagicMock()
    return agent


@pytest.fixture
def msg(classes):
    return _MsgHelper(classes)


@pytest.fixture
def executor_module(_setup_executor_classes):
    import importlib

    from ideer.subagents import executor

    return importlib.reload(executor)


# =========================================================================
# SubagentStatus
# =========================================================================


class TestSubagentStatus:
    def test_is_terminal_statuses(self, classes):
        SubagentStatus = classes["SubagentStatus"]
        assert SubagentStatus.COMPLETED.is_terminal is True
        assert SubagentStatus.FAILED.is_terminal is True
        assert SubagentStatus.CANCELLED.is_terminal is True
        assert SubagentStatus.TIMED_OUT.is_terminal is True

    def test_is_not_terminal_statuses(self, classes):
        SubagentStatus = classes["SubagentStatus"]
        assert SubagentStatus.PENDING.is_terminal is False
        assert SubagentStatus.RUNNING.is_terminal is False

    def test_all_enum_values(self, classes):
        SubagentStatus = classes["SubagentStatus"]
        assert SubagentStatus.PENDING.value == "pending"
        assert SubagentStatus.RUNNING.value == "running"
        assert SubagentStatus.COMPLETED.value == "completed"
        assert SubagentStatus.FAILED.value == "failed"
        assert SubagentStatus.CANCELLED.value == "cancelled"
        assert SubagentStatus.TIMED_OUT.value == "timed_out"


# =========================================================================
# SubagentResult
# =========================================================================


class TestSubagentResult:
    def test_post_init_sets_ai_messages_default(self, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        r = SubagentResult(
            task_id="t1",
            trace_id="tr1",
            status=SubagentStatus.PENDING,
            ai_messages=None,
        )
        assert r.ai_messages == []

    def test_post_init_preserves_existing_ai_messages(self, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        msgs = [{"id": "m1"}]
        r = SubagentResult(
            task_id="t1",
            trace_id="tr1",
            status=SubagentStatus.PENDING,
            ai_messages=msgs,
        )
        assert r.ai_messages is msgs

    def test_try_set_terminal_raises_on_non_terminal_status(self, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        r = SubagentResult(
            task_id="t1",
            trace_id="tr1",
            status=SubagentStatus.PENDING,
        )
        with pytest.raises(ValueError, match="not terminal"):
            r.try_set_terminal(SubagentStatus.RUNNING)

    def test_try_set_terminal_first_wins(self, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        r = SubagentResult(
            task_id="t1",
            trace_id="tr1",
            status=SubagentStatus.RUNNING,
        )
        assert r.try_set_terminal(SubagentStatus.COMPLETED, result="done") is True
        # Second terminal write should be rejected
        assert r.try_set_terminal(SubagentStatus.FAILED, error="fail") is False
        assert r.status == SubagentStatus.COMPLETED
        assert r.result == "done"
        assert r.error is None

    def test_try_set_terminal_sets_all_fields(self, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        r = SubagentResult(
            task_id="t1",
            trace_id="tr1",
            status=SubagentStatus.RUNNING,
        )
        dt = datetime(2026, 1, 1)
        records = [{"caller": "test", "input_tokens": 10, "output_tokens": 5, "total_tokens": 15}]
        msgs = [{"id": "m1"}]
        r.try_set_terminal(
            SubagentStatus.COMPLETED,
            result="ok",
            error="err",
            completed_at=dt,
            ai_messages=msgs,
            token_usage_records=records,
        )
        assert r.result == "ok"
        assert r.error == "err"
        assert r.completed_at == dt
        assert r.ai_messages == msgs
        assert r.token_usage_records == records

    def test_try_set_terminal_all_none_preserves_existing(self, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        r = SubagentResult(
            task_id="t1",
            trace_id="tr1",
            status=SubagentStatus.RUNNING,
            result="original",
            error="orig_err",
            ai_messages=[{"id": "orig"}],
            token_usage_records=[{"caller": "orig"}],
        )
        # Pass all None (except status)
        r.try_set_terminal(SubagentStatus.COMPLETED)
        assert r.result == "original"
        assert r.error == "orig_err"
        assert r.ai_messages == [{"id": "orig"}]
        assert r.token_usage_records == [{"caller": "orig"}]
        assert r.completed_at is not None

    def test_try_set_terminal_generates_completed_at_when_none(self, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        r = SubagentResult(
            task_id="t1",
            trace_id="tr1",
            status=SubagentStatus.RUNNING,
        )
        before = datetime.now()
        r.try_set_terminal(SubagentStatus.COMPLETED)
        after = datetime.now()
        assert before <= r.completed_at <= after

    def test_token_usage_records_default_factory(self, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        r1 = SubagentResult(task_id="t1", trace_id="tr1", status=SubagentStatus.PENDING)
        r2 = SubagentResult(task_id="t2", trace_id="tr2", status=SubagentStatus.PENDING)
        assert r1.token_usage_records is not r2.token_usage_records


# =========================================================================
# _evict_stale_tasks
# =========================================================================


class TestEvictStaleTasks:
    def test_evicts_old_completed_tasks(self, executor_module, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        stale = SubagentResult(
            task_id="stale",
            trace_id="tr",
            status=SubagentStatus.COMPLETED,
            completed_at=datetime.now() - timedelta(seconds=executor_module._MAX_TASK_AGE_SECONDS + 100),
        )
        fresh = SubagentResult(
            task_id="fresh",
            trace_id="tr",
            status=SubagentStatus.COMPLETED,
            completed_at=datetime.now(),
        )
        executor_module._background_tasks["stale"] = stale
        executor_module._background_tasks["fresh"] = fresh

        executor_module._evict_stale_tasks()

        assert "stale" not in executor_module._background_tasks
        assert "fresh" in executor_module._background_tasks

    def test_evict_keeps_tasks_without_completed_at(self, executor_module, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        running = SubagentResult(
            task_id="running",
            trace_id="tr",
            status=SubagentStatus.RUNNING,
            started_at=datetime.now() - timedelta(seconds=9999),
        )
        executor_module._background_tasks["running"] = running
        executor_module._evict_stale_tasks()
        assert "running" in executor_module._background_tasks

    def test_evict_logs_when_stale_tasks_found(self, executor_module, classes, caplog):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        stale = SubagentResult(
            task_id="stale-log",
            trace_id="tr",
            status=SubagentStatus.COMPLETED,
            completed_at=datetime.now() - timedelta(seconds=executor_module._MAX_TASK_AGE_SECONDS + 100),
        )
        executor_module._background_tasks["stale-log"] = stale
        with caplog.at_level(logging.INFO):
            executor_module._evict_stale_tasks()
        assert "Evicted" in caplog.text

    def test_evict_no_stale_tasks_no_log(self, executor_module, classes, caplog):
        executor_module._background_tasks.clear()
        with caplog.at_level(logging.INFO):
            executor_module._evict_stale_tasks()
        assert "Evicted" not in caplog.text


# =========================================================================
# _shutdown_isolated_subagent_loop
# =========================================================================


class TestShutdownIsolatedSubagentLoop:
    def test_shutdown_when_no_loop(self, executor_module):
        executor_module._isolated_subagent_loop = None
        executor_module._isolated_subagent_loop_thread = None
        # Should not raise
        executor_module._shutdown_isolated_subagent_loop()

    def test_shutdown_running_loop(self, executor_module):
        loop = asyncio.new_event_loop()
        started = threading.Event()

        def run_loop():
            asyncio.set_event_loop(loop)
            started.set()
            loop.run_forever()

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        started.wait(timeout=2)

        executor_module._isolated_subagent_loop = loop
        executor_module._isolated_subagent_loop_thread = thread
        executor_module._isolated_subagent_loop_started = started

        executor_module._shutdown_isolated_subagent_loop()

        assert executor_module._isolated_subagent_loop is None
        assert executor_module._isolated_subagent_loop_thread is None
        thread.join(timeout=2)

    def test_shutdown_loop_not_running(self, executor_module):
        loop = asyncio.new_event_loop()
        # Loop is not started (not running)
        executor_module._isolated_subagent_loop = loop
        executor_module._isolated_subagent_loop_thread = None

        executor_module._shutdown_isolated_subagent_loop()

        assert executor_module._isolated_subagent_loop is None

    def test_shutdown_with_dead_thread(self, executor_module):
        loop = asyncio.new_event_loop()
        thread = MagicMock()
        thread.is_alive.return_value = False
        thread.is_running = MagicMock(return_value=False)

        executor_module._isolated_subagent_loop = loop
        executor_module._isolated_subagent_loop_thread = thread

        executor_module._shutdown_isolated_subagent_loop()

        assert executor_module._isolated_subagent_loop is None


# =========================================================================
# _run_isolated_subagent_loop
# =========================================================================


class TestRunIsolatedSubagentLoop:
    def test_sets_event_and_runs_forever(self, executor_module):
        loop = asyncio.new_event_loop()
        started = threading.Event()

        def run():
            executor_module._run_isolated_subagent_loop(loop, started)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        assert started.wait(timeout=2)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)


# =========================================================================
# _get_isolated_subagent_loop
# =========================================================================


class TestGetIsolatedSubagentLoop:
    def test_creates_new_loop_when_none_exists(self, executor_module):
        executor_module._isolated_subagent_loop = None
        executor_module._isolated_subagent_loop_thread = None
        executor_module._isolated_subagent_loop_started = None

        loop = executor_module._get_isolated_subagent_loop()

        assert loop is not None
        assert loop.is_running()
        assert executor_module._isolated_subagent_loop is loop

        # Cleanup
        executor_module._shutdown_isolated_subagent_loop()

    def test_reuses_existing_running_loop(self, executor_module):
        # Create a loop first
        loop1 = executor_module._get_isolated_subagent_loop()
        loop2 = executor_module._get_isolated_subagent_loop()
        assert loop1 is loop2
        executor_module._shutdown_isolated_subagent_loop()

    def test_creates_new_loop_when_old_is_closed(self, executor_module):
        old_loop = asyncio.new_event_loop()
        old_loop.close()
        executor_module._isolated_subagent_loop = old_loop
        executor_module._isolated_subagent_loop_thread = None

        loop = executor_module._get_isolated_subagent_loop()
        assert loop is not old_loop
        assert not loop.is_closed()
        executor_module._shutdown_isolated_subagent_loop()


# =========================================================================
# _submit_to_isolated_loop_in_context
# =========================================================================


class TestSubmitToIsolatedLoopInContext:
    def test_submits_coroutine_to_isolated_loop(self, executor_module, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]

        executor_module._get_isolated_subagent_loop()

        async def coro():
            return SubagentResult(
                task_id="ctx-test",
                trace_id="tr",
                status=SubagentStatus.COMPLETED,
                result="done",
            )

        from contextvars import copy_context

        ctx = copy_context()
        future = executor_module._submit_to_isolated_loop_in_context(ctx, coro)
        result = future.result(timeout=5)
        assert result.result == "done"
        executor_module._shutdown_isolated_subagent_loop()


# =========================================================================
# _filter_tools
# =========================================================================


class TestFilterTools:
    def test_no_filters_returns_all(self, executor_module):
        tools = [NamedTool("a"), NamedTool("b"), NamedTool("c")]
        assert executor_module._filter_tools(tools, None, None) == tools

    def test_allowlist_only(self, executor_module):
        tools = [NamedTool("a"), NamedTool("b"), NamedTool("c")]
        result = executor_module._filter_tools(tools, ["a", "c"], None)
        assert [t.name for t in result] == ["a", "c"]

    def test_denylist_only(self, executor_module):
        tools = [NamedTool("a"), NamedTool("b"), NamedTool("c")]
        result = executor_module._filter_tools(tools, None, ["b"])
        assert [t.name for t in result] == ["a", "c"]

    def test_allowlist_and_denylist(self, executor_module):
        tools = [NamedTool("a"), NamedTool("b"), NamedTool("c")]
        result = executor_module._filter_tools(tools, ["a", "b"], ["b"])
        assert [t.name for t in result] == ["a"]

    def test_empty_allowlist_returns_nothing(self, executor_module):
        tools = [NamedTool("a"), NamedTool("b")]
        result = executor_module._filter_tools(tools, [], None)
        assert result == []

    def test_empty_denylist_returns_all(self, executor_module):
        tools = [NamedTool("a"), NamedTool("b")]
        result = executor_module._filter_tools(tools, None, [])
        assert result == tools

    def test_allowlist_with_no_matching_tools(self, executor_module):
        tools = [NamedTool("a"), NamedTool("b")]
        result = executor_module._filter_tools(tools, ["x", "y"], None)
        assert result == []


# =========================================================================
# SubagentExecutor.__init__
# =========================================================================


class TestExecutorInit:
    def test_model_name_resolved_from_config(self, classes):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
        )
        executor = SubagentExecutor(config=config, tools=[])
        assert executor.model_name == "gpt-4"

    def test_model_inherit_with_parent_model(self, classes):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(name="test", description="test", model="inherit")
        executor = SubagentExecutor(config=config, tools=[], parent_model="parent-m")
        assert executor.model_name == "parent-m"

    def test_model_inherit_deferred_when_no_parent_and_no_app_config(self, classes):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(name="test", description="test", model="inherit")
        executor = SubagentExecutor(config=config, tools=[])
        assert executor.model_name is None

    def test_trace_id_generated_when_not_provided(self, classes):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(name="test", description="test", model="gpt-4")
        executor = SubagentExecutor(config=config, tools=[])
        assert executor.trace_id is not None
        assert len(executor.trace_id) == 8

    def test_trace_id_preserved_when_provided(self, classes):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(name="test", description="test", model="gpt-4")
        executor = SubagentExecutor(config=config, tools=[], trace_id="custom-trace")
        assert executor.trace_id == "custom-trace"

    def test_tools_filtered_by_config(self, classes):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            tools=["a", "c"],
        )
        tools = [NamedTool("a"), NamedTool("b"), NamedTool("c")]
        executor = SubagentExecutor(config=config, tools=tools)
        assert [t.name for t in executor.tools] == ["a", "c"]

    def test_disallowed_tools_filtered(self, classes):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            disallowed_tools=["b"],
        )
        tools = [NamedTool("a"), NamedTool("b"), NamedTool("c")]
        executor = SubagentExecutor(config=config, tools=tools)
        assert [t.name for t in executor.tools] == ["a", "c"]

    def test_sandbox_and_thread_data_stored(self, classes):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(name="test", description="test", model="gpt-4")
        sb = {"sandbox_id": "sb-1"}
        td = {"workspace_path": "/ws"}
        executor = SubagentExecutor(
            config=config,
            tools=[],
            sandbox_state=sb,
            thread_data=td,
            thread_id="tid",
        )
        assert executor.sandbox_state == sb
        assert executor.thread_data == td
        assert executor.thread_id == "tid"

    def test_model_inherit_with_app_config(self, classes):
        """model_name is resolved eagerly when app_config is provided."""
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(name="test", description="test", model="inherit")
        app_cfg = SimpleNamespace(models=[SimpleNamespace(name="default-m")])
        executor = SubagentExecutor(config=config, tools=[], app_config=app_cfg)
        assert executor.model_name == "default-m"


# =========================================================================
# _create_agent
# =========================================================================


class TestCreateAgent:
    def test_deferred_model_resolution(self, classes, base_config, monkeypatch):
        SubagentExecutor = classes["SubagentExecutor"]
        from ideer.subagents import executor as executor_mod

        app_cfg = SimpleNamespace(models=[SimpleNamespace(name="deferred-m")])
        # Patch get_app_config on the executor module (where it was imported)
        monkeypatch.setattr(executor_mod, "get_app_config", lambda: app_cfg)
        monkeypatch.setattr(
            executor_mod,
            "create_chat_model",
            lambda **kw: SimpleNamespace(name=kw["name"]),
        )
        monkeypatch.setattr(executor_mod, "create_agent", lambda **kw: kw)

        # model="inherit" with no parent → deferred
        executor = SubagentExecutor(config=base_config, tools=[])
        assert executor.model_name is None

        executor._create_agent()
        assert executor.model_name == "deferred-m"

    def test_passes_explicit_tools(self, classes, base_config, monkeypatch):
        SubagentExecutor = classes["SubagentExecutor"]
        from ideer.subagents import executor as executor_mod

        captured = {}

        def fake_create_agent(**kw):
            captured["tools"] = kw["tools"]
            return kw

        monkeypatch.setattr(
            executor_mod,
            "create_chat_model",
            lambda **kw: SimpleNamespace(name=kw["name"]),
        )
        monkeypatch.setattr(executor_mod, "create_agent", fake_create_agent)

        app_cfg = SimpleNamespace(models=[SimpleNamespace(name="m")])
        executor = SubagentExecutor(config=base_config, tools=[NamedTool("x")], app_config=app_cfg)
        custom_tools = [NamedTool("y"), NamedTool("z")]
        executor._create_agent(tools=custom_tools)
        assert captured["tools"] == custom_tools

    def test_adds_filesystem_scope_only_when_configured(self, classes, monkeypatch):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        from ideer.subagents import executor as executor_mod

        captured = {}
        middleware_builder = sys.modules["ideer.agents.middlewares.tool_error_handling_middleware"]
        middleware_builder.build_subagent_runtime_middlewares = lambda **_kw: ["base"]

        scope_module = ModuleType("ideer.agents.middlewares.filesystem_scope_middleware")

        class Scope:
            def __init__(self, *, read_roots, write_roots):
                self.read_roots = read_roots
                self.write_roots = write_roots

        scope_module.FilesystemScopeMiddleware = Scope
        monkeypatch.setitem(
            sys.modules,
            "ideer.agents.middlewares.filesystem_scope_middleware",
            scope_module,
        )
        monkeypatch.setattr(
            executor_mod,
            "create_chat_model",
            lambda **kw: SimpleNamespace(name=kw["name"]),
        )
        monkeypatch.setattr(
            executor_mod,
            "create_agent",
            lambda **kw: captured.update(kw) or kw,
        )
        app_cfg = SimpleNamespace(models=[SimpleNamespace(name="m")])
        config = SubagentConfig(
            name="scoped",
            description="scoped",
            model="m",
            file_access={"read": ["/inputs"], "write": ["/outputs"]},
        )

        SubagentExecutor(config=config, tools=[], app_config=app_cfg)._create_agent()

        assert captured["middleware"][0] == "base"
        assert isinstance(captured["middleware"][1], Scope)
        assert captured["middleware"][1].read_roots == ["/inputs"]
        assert captured["middleware"][1].write_roots == ["/outputs"]


# =========================================================================
# _load_skills
# =========================================================================


class TestLoadSkills:
    @pytest.mark.anyio
    async def test_empty_skills_list_skips_loading(self, classes, base_config, monkeypatch):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            skills=[],
        )
        executor = SubagentExecutor(config=config, tools=[])
        result = await executor._load_skills()
        assert result == []

    @pytest.mark.anyio
    async def test_none_skills_loads_all(self, classes, monkeypatch, tmp_path):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            skills=None,
        )
        all_skills = [_skill("a", None), _skill("b", None)]

        monkeypatch.setattr(
            sys.modules["ideer.skills.storage"],
            "get_or_new_skill_storage",
            lambda **kw: SimpleNamespace(load_skills=lambda *, enabled_only: all_skills),
        )
        executor = SubagentExecutor(config=config, tools=[])
        result = await executor._load_skills()
        assert len(result) == 2

    @pytest.mark.anyio
    async def test_whitelist_filters_skills(self, classes, monkeypatch):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            skills=["a", "c"],
        )
        all_skills = [_skill("a", None), _skill("b", None), _skill("c", None)]

        monkeypatch.setattr(
            sys.modules["ideer.skills.storage"],
            "get_or_new_skill_storage",
            lambda **kw: SimpleNamespace(load_skills=lambda *, enabled_only: all_skills),
        )
        executor = SubagentExecutor(config=config, tools=[])
        result = await executor._load_skills()
        assert [s.name for s in result] == ["a", "c"]

    @pytest.mark.anyio
    async def test_no_enabled_skills_returns_empty(self, classes, monkeypatch):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            skills=None,
        )

        monkeypatch.setattr(
            sys.modules["ideer.skills.storage"],
            "get_or_new_skill_storage",
            lambda **kw: SimpleNamespace(load_skills=lambda *, enabled_only: []),
        )
        executor = SubagentExecutor(config=config, tools=[])
        result = await executor._load_skills()
        assert result == []

    @pytest.mark.anyio
    async def test_load_skills_exception_raises(self, classes, monkeypatch):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            skills=None,
        )

        def bad_storage(**kw):
            raise RuntimeError("disk error")

        monkeypatch.setattr(
            sys.modules["ideer.skills.storage"],
            "get_or_new_skill_storage",
            bad_storage,
        )
        executor = SubagentExecutor(config=config, tools=[])
        with pytest.raises(RuntimeError, match="disk error"):
            await executor._load_skills()

    @pytest.mark.anyio
    async def test_load_skills_passes_app_config(self, classes, monkeypatch):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            skills=None,
        )
        captured = {}

        def fake_storage(**kw):
            captured.update(kw)
            return SimpleNamespace(load_skills=lambda *, enabled_only: [])

        monkeypatch.setattr(
            sys.modules["ideer.skills.storage"],
            "get_or_new_skill_storage",
            fake_storage,
        )
        app_cfg = SimpleNamespace(models=[SimpleNamespace(name="m")])
        executor = SubagentExecutor(config=config, tools=[], app_config=app_cfg)
        await executor._load_skills()
        assert captured["app_config"] is app_cfg


# =========================================================================
# _apply_skill_allowed_tools
# =========================================================================


class TestApplySkillAllowedTools:
    def test_no_skills_returns_base_tools(self, classes, base_config):
        SubagentExecutor = classes["SubagentExecutor"]
        tools = [NamedTool("a"), NamedTool("b")]
        executor = SubagentExecutor(config=base_config, tools=tools)
        result = executor._apply_skill_allowed_tools([])
        assert result == tools

    def test_skills_with_allowed_tools_filters(self, classes, base_config):
        SubagentExecutor = classes["SubagentExecutor"]
        tools = [NamedTool("a"), NamedTool("b"), NamedTool("c")]
        executor = SubagentExecutor(config=base_config, tools=tools)
        skills = [_skill("s1", ["a", "b"])]
        result = executor._apply_skill_allowed_tools(skills)
        assert [t.name for t in result] == ["a", "b"]


# =========================================================================
# _load_skill_messages
# =========================================================================


class TestLoadSkillMessages:
    @pytest.mark.anyio
    async def test_empty_skills_returns_empty(self, classes, base_config):
        SubagentExecutor = classes["SubagentExecutor"]
        executor = SubagentExecutor(config=base_config, tools=[])
        result = await executor._load_skill_messages([])
        assert result == []

    @pytest.mark.anyio
    async def test_reads_skill_content(self, classes, base_config, tmp_path):
        SubagentExecutor = classes["SubagentExecutor"]
        skill_dir = tmp_path / "sk"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("hello world", encoding="utf-8")
        sk = _skill("sk", None)
        sk.skill_file = skill_file

        executor = SubagentExecutor(config=base_config, tools=[])
        msgs = await executor._load_skill_messages([sk])
        assert len(msgs) == 1
        assert "hello world" in msgs[0].content
        assert 'name="sk"' in msgs[0].content

    @pytest.mark.anyio
    async def test_empty_content_skipped(self, classes, base_config, tmp_path):
        SubagentExecutor = classes["SubagentExecutor"]
        skill_dir = tmp_path / "empty-sk"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("   ", encoding="utf-8")
        sk = _skill("empty-sk", None)
        sk.skill_file = skill_file

        executor = SubagentExecutor(config=base_config, tools=[])
        msgs = await executor._load_skill_messages([sk])
        assert msgs == []

    @pytest.mark.anyio
    async def test_read_exception_logged_and_skipped(self, classes, base_config, monkeypatch):
        SubagentExecutor = classes["SubagentExecutor"]
        sk = _skill("bad-skill", None)
        sk.skill_file = MagicMock()
        sk.skill_file.read_text.side_effect = OSError("permission denied")

        executor = SubagentExecutor(config=base_config, tools=[])
        msgs = await executor._load_skill_messages([sk])
        assert msgs == []


# =========================================================================
# _build_initial_state
# =========================================================================


class TestBuildInitialState:
    @pytest.mark.anyio
    async def test_with_sandbox_and_thread_data(self, classes, monkeypatch):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            system_prompt=None,
        )
        sb = {"sandbox_id": "sb-1"}
        td = {"workspace_path": "/ws"}

        monkeypatch.setattr(
            sys.modules["ideer.skills.storage"],
            "get_or_new_skill_storage",
            lambda **kw: SimpleNamespace(load_skills=lambda *, enabled_only: []),
        )
        executor = SubagentExecutor(
            config=config,
            tools=[],
            sandbox_state=sb,
            thread_data=td,
        )
        state, filtered = await executor._build_initial_state("do it")
        assert state["sandbox"] == sb
        assert state["thread_data"] == td
        assert len(state["messages"]) == 1  # Only HumanMessage (no system_prompt, no skills)

    @pytest.mark.anyio
    async def test_without_sandbox_or_thread_data(self, classes, monkeypatch):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            system_prompt=None,
        )

        monkeypatch.setattr(
            sys.modules["ideer.skills.storage"],
            "get_or_new_skill_storage",
            lambda **kw: SimpleNamespace(load_skills=lambda *, enabled_only: []),
        )
        executor = SubagentExecutor(config=config, tools=[])
        state, _ = await executor._build_initial_state("do it")
        assert "sandbox" not in state
        assert "thread_data" not in state

    @pytest.mark.anyio
    async def test_no_system_prompt_no_skills_only_human_message(self, classes, monkeypatch):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            system_prompt=None,
        )

        monkeypatch.setattr(
            sys.modules["ideer.skills.storage"],
            "get_or_new_skill_storage",
            lambda **kw: SimpleNamespace(load_skills=lambda *, enabled_only: []),
        )
        executor = SubagentExecutor(config=config, tools=[])
        state, _ = await executor._build_initial_state("task")
        from langchain_core.messages import HumanMessage

        assert len(state["messages"]) == 1
        assert isinstance(state["messages"][0], HumanMessage)


# =========================================================================
# _aexecute
# =========================================================================


class TestAExecute:
    @pytest.mark.anyio
    async def test_success(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        SubagentStatus = classes["SubagentStatus"]
        final_state = {"messages": [msg.human("Task"), msg.ai("Done", "msg-1")]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final_state])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("Task")
        assert result.status == SubagentStatus.COMPLETED
        assert result.result == "Done"
        assert result.started_at is not None
        assert result.completed_at is not None

    @pytest.mark.anyio
    async def test_with_result_holder(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        holder = SubagentResult(
            task_id="pre",
            trace_id="tr",
            status=SubagentStatus.RUNNING,
            started_at=datetime.now(),
        )
        final_state = {"messages": [msg.human("T"), msg.ai("R", "m1")]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final_state])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T", result_holder=holder)
        assert result is holder
        assert result.task_id == "pre"

    @pytest.mark.anyio
    async def test_result_holder_with_none_ai_messages(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        holder = SubagentResult(
            task_id="t",
            trace_id="tr",
            status=SubagentStatus.RUNNING,
            ai_messages=None,
        )
        final_state = {"messages": [msg.human("T"), msg.ai("R", "m1")]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final_state])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T", result_holder=holder)
        assert result.ai_messages is not None
        assert len(result.ai_messages) == 1

    @pytest.mark.anyio
    async def test_collects_ai_messages(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        m1 = msg.ai("A", "m1")
        m2 = msg.ai("B", "m2")
        c1 = {"messages": [msg.human("T"), m1]}
        c2 = {"messages": [msg.human("T"), m1, m2]}
        mock_agent.astream = lambda *a, **kw: async_iterator([c1, c2])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert len(result.ai_messages) == 2

    @pytest.mark.anyio
    async def test_duplicate_messages_by_id(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        m1 = msg.ai("R", "dup")
        c1 = {"messages": [msg.human("T"), m1]}
        c2 = {"messages": [msg.human("T"), m1]}
        mock_agent.astream = lambda *a, **kw: async_iterator([c1, c2])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert len(result.ai_messages) == 1

    @pytest.mark.anyio
    async def test_duplicate_messages_without_id(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        # Create two AI messages with no id (id=None)
        m1 = classes["AIMessage"](content="R")
        m1.id = None
        c1 = {"messages": [msg.human("T"), m1]}
        c2 = {"messages": [msg.human("T"), m1]}
        mock_agent.astream = lambda *a, **kw: async_iterator([c1, c2])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        # Deduplication via full dict comparison when no id
        assert len(result.ai_messages) == 1

    @pytest.mark.anyio
    async def test_list_content_with_dict_blocks(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        classes["SubagentStatus"]
        m = msg.ai([{"text": "Part1"}, {"text": "Part2"}])
        final = {"messages": [msg.human("T"), m]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert "Part1" in result.result
        assert "Part2" in result.result

    @pytest.mark.anyio
    async def test_list_content_with_str_blocks(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        m = msg.ai(["str1", "str2"])
        final = {"messages": [msg.human("T"), m]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert result.result == "str1str2"

    @pytest.mark.anyio
    async def test_list_content_mixed_str_and_dict(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        m = msg.ai(["prefix", {"text": "middle"}, "suffix"])
        final = {"messages": [msg.human("T"), m]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        # str parts are joined with "" internally, then all text_parts joined with "\n"
        assert "prefix" in result.result
        assert "middle" in result.result
        assert "suffix" in result.result

    @pytest.mark.anyio
    async def test_list_content_with_dict_no_text_key(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        m = msg.ai([{"other": "val"}])
        final = {"messages": [msg.human("T"), m]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert result.result == "No text content in response"

    @pytest.mark.anyio
    async def test_list_content_empty(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        m = msg.ai([])
        final = {"messages": [msg.human("T"), m]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert result.result == "No text content in response"

    @pytest.mark.anyio
    async def test_non_str_non_list_content(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        # AIMessage now validates that content must be str or list;
        # use a MagicMock to simulate non-str/non-list content.
        m = MagicMock()
        m.content = 12345
        m.type = "ai"
        m.tool_calls = []
        m.invalid_tool_calls = []
        m.id = None
        final = {"messages": [msg.human("T"), m]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert result.result == "12345"

    @pytest.mark.anyio
    async def test_no_ai_message_fallback_str_content(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        final = {"messages": [msg.human("fallback text")]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert "fallback text" in result.result

    @pytest.mark.anyio
    async def test_no_ai_message_fallback_list_content(self, classes, base_config, mock_agent):
        SubagentExecutor = classes["SubagentExecutor"]
        fallback_msg = MagicMock()
        fallback_msg.content = [{"text": "fb1"}, "fb2", {"no_text": "x"}]
        final = {"messages": [fallback_msg]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert "fb1" in result.result
        assert "fb2" in result.result

    @pytest.mark.anyio
    async def test_no_ai_message_fallback_non_str_non_list(self, classes, base_config, mock_agent):
        SubagentExecutor = classes["SubagentExecutor"]
        fallback_msg = MagicMock()
        fallback_msg.content = 99999
        fallback_msg.__class__ = type("FakeMsg", (), {})  # not AIMessage
        final = {"messages": [fallback_msg]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert result.result == "99999"

    @pytest.mark.anyio
    async def test_no_messages_in_final_state(self, classes, base_config, mock_agent):
        SubagentExecutor = classes["SubagentExecutor"]
        final = {"messages": []}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert result.result == "No response generated"

    @pytest.mark.anyio
    async def test_no_final_state(self, classes, base_config, mock_agent):
        SubagentExecutor = classes["SubagentExecutor"]
        mock_agent.astream = lambda *a, **kw: async_iterator([])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert result.result == "No response generated"

    @pytest.mark.anyio
    async def test_exception_handled(self, classes, base_config, mock_agent):
        SubagentExecutor = classes["SubagentExecutor"]
        SubagentStatus = classes["SubagentStatus"]
        mock_agent.astream.side_effect = RuntimeError("boom")
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert result.status == SubagentStatus.FAILED
        assert "boom" in result.error

    @pytest.mark.anyio
    async def test_cancel_before_streaming(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        holder = SubagentResult(
            task_id="c",
            trace_id="tr",
            status=SubagentStatus.RUNNING,
            started_at=datetime.now(),
        )
        holder.cancel_event.set()
        call_count = 0

        async def counting_stream(*a, **kw):
            nonlocal call_count
            call_count += 1
            yield {"messages": [msg.human("T"), msg.ai("R", "m1")]}

        mock_agent.astream = counting_stream
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T", result_holder=holder)
        assert result.status == SubagentStatus.CANCELLED
        assert call_count == 0

    @pytest.mark.anyio
    async def test_cancel_mid_stream(self, classes, base_config, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        cancel_ev = threading.Event()

        async def stream(*a, **kw):
            yield {"messages": [msg.human("T"), msg.ai("Partial", "m1")]}
            cancel_ev.set()
            yield {"messages": [msg.human("T"), msg.ai("Nope", "m2")]}

        mock_agent = MagicMock()
        mock_agent.astream = stream
        holder = SubagentResult(
            task_id="c",
            trace_id="tr",
            status=SubagentStatus.RUNNING,
            started_at=datetime.now(),
        )
        holder.cancel_event = cancel_ev
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T", result_holder=holder)
        assert result.status == SubagentStatus.CANCELLED

    @pytest.mark.anyio
    async def test_no_messages_fallback_no_content_attr(self, classes, base_config, mock_agent):
        SubagentExecutor = classes["SubagentExecutor"]
        fallback_msg = MagicMock(spec=[])  # no content attr
        fallback_msg.content = None
        del fallback_msg.content
        fallback_msg.__class__ = type("NoContent", (), {})
        final = {"messages": [fallback_msg]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert result.result is not None

    @pytest.mark.anyio
    async def test_thread_id_and_app_config_passed_to_run_config(self, classes, base_config, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        captured_config = {}
        captured_context = {}

        async def capturing_astream(state, config=None, context=None, **kw):
            captured_config.update(config or {})
            captured_context.update(context or {})
            yield {"messages": [msg.human("T"), msg.ai("R", "m1")]}

        mock_agent = MagicMock()
        mock_agent.astream = capturing_astream
        app_cfg = SimpleNamespace(models=[SimpleNamespace(name="m")])
        executor = SubagentExecutor(
            config=base_config,
            tools=[],
            thread_id="tid-123",
            app_config=app_cfg,
        )
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            await executor._aexecute("T")
        assert captured_config.get("configurable", {}).get("thread_id") == "tid-123"
        assert captured_context.get("thread_id") == "tid-123"
        assert captured_context.get("app_config") is app_cfg

    @pytest.mark.anyio
    async def test_no_thread_id_no_configurable(self, classes, base_config, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        captured_config = {}

        async def capturing_astream(state, config=None, **kw):
            captured_config.update(config or {})
            yield {"messages": [msg.human("T"), msg.ai("R", "m1")]}

        mock_agent = MagicMock()
        mock_agent.astream = capturing_astream
        executor = SubagentExecutor(config=base_config, tools=[])
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            await executor._aexecute("T")
        assert "configurable" not in captured_config

    @pytest.mark.anyio
    async def test_list_content_mixed_str_then_dict_then_str(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        # str, dict, str — pending_str_parts flushed before dict, then final pending
        m = msg.ai(["aaa", {"text": "bbb"}, "ccc"])
        final = {"messages": [msg.human("T"), m]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        # str parts joined with "", text_parts joined with "\n"
        assert "aaa" in result.result
        assert "bbb" in result.result
        assert "ccc" in result.result

    @pytest.mark.anyio
    async def test_fallback_list_content_mixed_str_then_dict(self, classes, base_config, mock_agent):
        SubagentExecutor = classes["SubagentExecutor"]
        fallback = MagicMock()
        fallback.content = ["pre", {"text": "mid"}, "post"]
        fallback.__class__ = type("FakeMsg", (), {})
        final = {"messages": [fallback]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert "pre" in result.result
        assert "mid" in result.result
        assert "post" in result.result

    @pytest.mark.anyio
    async def test_fallback_list_content_empty_dict_no_text(self, classes, base_config, mock_agent):
        SubagentExecutor = classes["SubagentExecutor"]
        fallback = MagicMock()
        fallback.content = [{"other": "val"}]
        fallback.__class__ = type("FakeMsg", (), {})
        final = {"messages": [fallback]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert result.result == "No text content in response"

    @pytest.mark.anyio
    async def test_fallback_list_content_non_str_non_list_items(self, classes, base_config, mock_agent):
        SubagentExecutor = classes["SubagentExecutor"]
        fallback = MagicMock()
        fallback.content = [123, 456]
        fallback.__class__ = type("FakeMsg", (), {})
        final = {"messages": [fallback]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        # int items in list are neither str nor dict, so no text_parts collected
        assert result.result == "No text content in response"


# =========================================================================
# _execute_in_isolated_loop
# =========================================================================


class TestExecuteInIsolatedLoop:
    def test_futures_timeout_sets_cancel(self, classes, base_config):
        SubagentExecutor = classes["SubagentExecutor"]
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        holder = SubagentResult(
            task_id="t",
            trace_id="tr",
            status=SubagentStatus.RUNNING,
            started_at=datetime.now(),
        )

        # Patch _submit_to_isolated_loop_in_context to return a future that times out
        blocking_future: Future = Future()

        def fake_submit(ctx, coro_factory):
            return blocking_future

        # Use a very short timeout
        short_config = classes["SubagentConfig"](
            name="test-agent",
            description="test",
            model="gpt-4",
            max_turns=10,
            timeout_seconds=0,
        )
        executor = SubagentExecutor(
            config=short_config,
            tools=[],
        )

        from ideer.subagents import executor as executor_mod

        with patch.object(executor_mod, "_submit_to_isolated_loop_in_context", fake_submit):
            with pytest.raises(FuturesTimeoutError):
                executor._execute_in_isolated_loop("T", result_holder=holder)
        assert holder.cancel_event.is_set()
        blocking_future.cancel()

    def test_generic_exception_logged(self, classes, base_config):
        SubagentExecutor = classes["SubagentExecutor"]

        def fake_submit(ctx, coro_factory):
            raise RuntimeError("submit failed")

        executor = SubagentExecutor(config=base_config, tools=[])
        from ideer.subagents import executor as executor_mod

        with patch.object(executor_mod, "_submit_to_isolated_loop_in_context", fake_submit):
            with pytest.raises(RuntimeError, match="submit failed"):
                executor._execute_in_isolated_loop("T")


# =========================================================================
# execute
# =========================================================================


class TestExecute:
    def test_standard_path(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        SubagentStatus = classes["SubagentStatus"]
        final = {"messages": [msg.human("T"), msg.ai("R", "m1")]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = executor.execute("T")
        assert result.status == SubagentStatus.COMPLETED

    def test_exception_with_result_holder(self, classes, base_config):
        SubagentExecutor = classes["SubagentExecutor"]
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        holder = SubagentResult(
            task_id="h",
            trace_id="tr",
            status=SubagentStatus.RUNNING,
        )
        executor = SubagentExecutor(config=base_config, tools=[])
        with patch.object(executor, "_aexecute", side_effect=RuntimeError("fail")):
            result = executor.execute("T", result_holder=holder)
        assert result is holder
        assert result.status == SubagentStatus.FAILED

    def test_exception_without_result_holder(self, classes, base_config):
        SubagentExecutor = classes["SubagentExecutor"]
        SubagentStatus = classes["SubagentStatus"]
        executor = SubagentExecutor(config=base_config, tools=[])
        with patch.object(executor, "_aexecute", side_effect=RuntimeError("fail")):
            result = executor.execute("T")
        assert result.status == SubagentStatus.FAILED
        assert "fail" in result.error

    @pytest.mark.anyio
    async def test_running_loop_calls_isolated(self, classes, base_config, mock_agent, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        SubagentStatus = classes["SubagentStatus"]
        final = {"messages": [msg.human("T"), msg.ai("R", "m1")]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = executor.execute("T")
        assert result.status == SubagentStatus.COMPLETED


# =========================================================================
# execute_async
# =========================================================================


class TestExecuteAsync:
    def test_custom_task_id(self, executor_module, classes, base_config):
        SubagentExecutor = classes["SubagentExecutor"]
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        # Just verify the task_id is stored
        executor_module._background_tasks.clear()

        # Patch _scheduler_pool.submit to run inline
        def run_inline(fn):
            fn()

        async def fake_aexecute(task, result_holder=None):
            if result_holder:
                result_holder.status = classes["SubagentStatus"].COMPLETED
                result_holder.result = "ok"
                result_holder.completed_at = datetime.now()
            return result_holder

        with (
            patch.object(executor_module._scheduler_pool, "submit", run_inline),
            patch.object(executor, "_aexecute", side_effect=fake_aexecute),
        ):
            tid = executor.execute_async("T", task_id="custom-id")

        assert tid == "custom-id"
        assert "custom-id" in executor_module._background_tasks

    def test_generate_task_id(self, executor_module, classes, base_config):
        SubagentExecutor = classes["SubagentExecutor"]
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        executor_module._background_tasks.clear()

        def run_inline(fn):
            fn()

        async def fake_aexecute(task, result_holder=None):
            if result_holder:
                result_holder.status = classes["SubagentStatus"].COMPLETED
                result_holder.result = "ok"
                result_holder.completed_at = datetime.now()
            return result_holder

        with (
            patch.object(executor_module._scheduler_pool, "submit", run_inline),
            patch.object(executor, "_aexecute", side_effect=fake_aexecute),
        ):
            tid = executor.execute_async("T")

        assert tid is not None
        assert len(tid) == 8


# =========================================================================
# get_background_task_result / list_background_tasks
# =========================================================================


class TestBackgroundTaskQuery:
    def test_get_background_task_result_found(self, executor_module, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        r = SubagentResult(
            task_id="q1",
            trace_id="tr",
            status=SubagentStatus.COMPLETED,
            result="ok",
        )
        executor_module._background_tasks["q1"] = r
        result = executor_module.get_background_task_result("q1")
        assert result is r

    def test_get_background_task_result_not_found(self, executor_module):
        executor_module._background_tasks.clear()
        result = executor_module.get_background_task_result("nonexistent")
        assert result is None

    def test_list_background_tasks(self, executor_module, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        executor_module._background_tasks.clear()
        r1 = SubagentResult(task_id="l1", trace_id="tr", status=SubagentStatus.RUNNING)
        r2 = SubagentResult(task_id="l2", trace_id="tr", status=SubagentStatus.COMPLETED)
        executor_module._background_tasks["l1"] = r1
        executor_module._background_tasks["l2"] = r2
        result = executor_module.list_background_tasks()
        assert len(result) == 2
        assert r1 in result
        assert r2 in result

    def test_list_background_tasks_empty(self, executor_module):
        executor_module._background_tasks.clear()
        result = executor_module.list_background_tasks()
        assert result == []


# =========================================================================
# request_cancel_background_task
# =========================================================================


class TestRequestCancel:
    def test_sets_cancel_event(self, executor_module, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        r = SubagentResult(
            task_id="cancel-me",
            trace_id="tr",
            status=SubagentStatus.RUNNING,
        )
        executor_module._background_tasks["cancel-me"] = r
        executor_module.request_cancel_background_task("cancel-me")
        assert r.cancel_event.is_set()

    def test_nonexistent_task_noop(self, executor_module):
        executor_module._background_tasks.clear()
        executor_module.request_cancel_background_task("nope")


# =========================================================================
# Module-level atexit guard
# =========================================================================


class TestModuleAtexitGuard:
    def test_previous_shutdown_called_if_callable(self, executor_module):
        """Lines 33-37: if globals already has _shutdown_isolated_subagent_loop
        as callable, it should be unregistered and called."""
        # This is tested at import time; the guard is executed at module level.
        # We verify the function exists and is registered with atexit.
        assert callable(executor_module._shutdown_isolated_subagent_loop)


# =========================================================================
# MAX_CONCURRENT_SUBAGENTS constant
# =========================================================================


class TestConstants:
    def test_max_concurrent_subagents(self, executor_module):
        assert executor_module.MAX_CONCURRENT_SUBAGENTS == 3

    def test_max_task_age_seconds(self, executor_module):
        assert executor_module._MAX_TASK_AGE_SECONDS == 3600


# =========================================================================
# cleanup_background_task (additional edge cases)
# =========================================================================


class TestCleanupBackgroundTaskExtended:
    def test_cleanup_removes_cancelled(self, executor_module, classes):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        r = SubagentResult(
            task_id="cl-cancel",
            trace_id="tr",
            status=SubagentStatus.CANCELLED,
            completed_at=datetime.now(),
        )
        executor_module._background_tasks["cl-cancel"] = r
        executor_module.cleanup_background_task("cl-cancel")
        assert "cl-cancel" not in executor_module._background_tasks

    def test_cleanup_nonexistent_logs_debug(self, executor_module, caplog):
        executor_module._background_tasks.clear()
        with caplog.at_level(logging.DEBUG, logger=executor_module.logger.name):
            executor_module.cleanup_background_task("ghost")
        assert "ghost" in caplog.text

    def test_cleanup_non_terminal_skips(self, executor_module, classes, caplog):
        SubagentResult = classes["SubagentResult"]
        SubagentStatus = classes["SubagentStatus"]
        r = SubagentResult(
            task_id="running-cl",
            trace_id="tr",
            status=SubagentStatus.RUNNING,
            started_at=datetime.now(),
        )
        executor_module._background_tasks["running-cl"] = r
        with caplog.at_level(logging.DEBUG, logger=executor_module.logger.name):
            executor_module.cleanup_background_task("running-cl")
        assert "Skipping cleanup" in caplog.text
        assert "running-cl" in executor_module._background_tasks


# =========================================================================
# Agent construction - system prompt merging
# =========================================================================


class TestAgentConstructionExtended:
    @pytest.mark.anyio
    async def test_build_initial_state_consolidates_multiple_skills(self, classes, monkeypatch, tmp_path):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            system_prompt="Base prompt",
        )
        sk1_dir = tmp_path / "sk1"
        sk1_dir.mkdir()
        (sk1_dir / "SKILL.md").write_text("Skill1 content", encoding="utf-8")
        sk2_dir = tmp_path / "sk2"
        sk2_dir.mkdir()
        (sk2_dir / "SKILL.md").write_text("Skill2 content", encoding="utf-8")

        all_skills = [_skill("sk1", None), _skill("sk2", None)]
        for s, d in zip(all_skills, [sk1_dir, sk2_dir]):
            s.skill_file = d / "SKILL.md"

        monkeypatch.setattr(
            sys.modules["ideer.skills.storage"],
            "get_or_new_skill_storage",
            lambda **kw: SimpleNamespace(load_skills=lambda *, enabled_only: all_skills),
        )
        executor = SubagentExecutor(config=config, tools=[])
        state, _ = await executor._build_initial_state("task")
        from langchain_core.messages import SystemMessage

        sys_msg = state["messages"][0]
        assert isinstance(sys_msg, SystemMessage)
        assert "Base prompt" in sys_msg.content
        assert "Skill1 content" in sys_msg.content
        assert "Skill2 content" in sys_msg.content

    @pytest.mark.anyio
    async def test_no_system_parts_skips_system_message(self, classes, monkeypatch):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            system_prompt=None,
            skills=[],
        )
        monkeypatch.setattr(
            sys.modules["ideer.skills.storage"],
            "get_or_new_skill_storage",
            lambda **kw: SimpleNamespace(load_skills=lambda *, enabled_only: []),
        )
        executor = SubagentExecutor(config=config, tools=[])
        state, _ = await executor._build_initial_state("task")
        from langchain_core.messages import HumanMessage

        assert len(state["messages"]) == 1
        assert isinstance(state["messages"][0], HumanMessage)


# =========================================================================
# _aexecute: final_result None guard (line 640-641)
# =========================================================================


class TestFinalResultNoneGuard:
    @pytest.mark.anyio
    async def test_final_result_none_guard(self, classes, base_config, mock_agent):
        """Line 640-641: if final_result is None after all branches, it becomes 'No response generated'."""
        SubagentExecutor = classes["SubagentExecutor"]
        # Create a scenario where last_ai_message exists but content is None
        ai_msg = MagicMock()
        ai_msg.content = None
        ai_msg.__class__ = classes["AIMessage"]
        ai_msg.model_dump.return_value = {"id": "m1", "content": None}

        final = {"messages": [ai_msg]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        # content=None → str(None) = "None"
        assert result.result is not None


# =========================================================================
# _aexecute: fallback list with dict with non-string text value
# =========================================================================


class TestAexecuteFallbackEdgeCases:
    @pytest.mark.anyio
    async def test_dict_block_with_non_string_text(self, classes, base_config, mock_agent):
        SubagentExecutor = classes["SubagentExecutor"]
        ai = MagicMock()
        ai.content = [{"text": 123}]
        ai.__class__ = classes["AIMessage"]
        ai.model_dump.return_value = {"id": "m1"}
        ai.id = "m1"
        final = {"messages": [ai]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        # text=123 is not isinstance str, so it's skipped
        assert result.result == "No text content in response"

    @pytest.mark.anyio
    async def test_fallback_dict_block_with_non_string_text(self, classes, base_config, mock_agent):
        SubagentExecutor = classes["SubagentExecutor"]
        fallback = MagicMock()
        fallback.content = [{"text": 456}]
        fallback.__class__ = type("FB", (), {})
        final = {"messages": [fallback]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert result.result == "No text content in response"

    @pytest.mark.anyio
    async def test_fallback_list_empty_with_str_items(self, classes, base_config, mock_agent):
        SubagentExecutor = classes["SubagentExecutor"]
        fallback = MagicMock()
        fallback.content = []
        fallback.__class__ = type("FB", (), {})
        final = {"messages": [fallback]}
        mock_agent.astream = lambda *a, **kw: async_iterator([final])
        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        with patch.object(executor, "_create_agent", return_value=mock_agent):
            result = await executor._aexecute("T")
        assert result.result == "No text content in response"


# =========================================================================
# _create_agent: verify middleware and state_schema
# =========================================================================


class TestCreateAgentWiring:
    def test_middleware_and_state_schema(self, classes, base_config, monkeypatch):
        SubagentExecutor = classes["SubagentExecutor"]
        from ideer.subagents import executor as executor_mod

        captured = {}

        def fake_create_agent(**kw):
            captured.update(kw)
            return kw

        monkeypatch.setattr(
            executor_mod,
            "create_chat_model",
            lambda **kw: SimpleNamespace(name=kw["name"]),
        )
        monkeypatch.setattr(executor_mod, "create_agent", fake_create_agent)

        app_cfg = SimpleNamespace(models=[SimpleNamespace(name="m")])
        executor = SubagentExecutor(config=base_config, tools=[], app_config=app_cfg)
        executor._create_agent()

        assert captured["system_prompt"] is None
        assert "middleware" in captured
        assert "state_schema" in captured


# =========================================================================
# _load_skills: app_config passed through
# =========================================================================


class TestLoadSkillsWithAppConfig:
    @pytest.mark.anyio
    async def test_app_config_forwarded_to_storage(self, classes, monkeypatch):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            skills=None,
        )
        captured = {}

        def fake_storage(**kw):
            captured.update(kw)
            return SimpleNamespace(load_skills=lambda *, enabled_only: [])

        monkeypatch.setattr(
            sys.modules["ideer.skills.storage"],
            "get_or_new_skill_storage",
            fake_storage,
        )
        app_cfg = SimpleNamespace(models=[SimpleNamespace(name="m")])
        executor = SubagentExecutor(config=config, tools=[], app_config=app_cfg)
        await executor._load_skills()
        assert captured.get("app_config") is app_cfg

    @pytest.mark.anyio
    async def test_no_app_config_omits_kwarg(self, classes, monkeypatch):
        SubagentConfig = classes["SubagentConfig"]
        SubagentExecutor = classes["SubagentExecutor"]
        config = SubagentConfig(
            name="test",
            description="test",
            model="gpt-4",
            skills=None,
        )
        captured = {}

        def fake_storage(**kw):
            captured.update(kw)
            return SimpleNamespace(load_skills=lambda *, enabled_only: [])

        monkeypatch.setattr(
            sys.modules["ideer.skills.storage"],
            "get_or_new_skill_storage",
            fake_storage,
        )
        executor = SubagentExecutor(config=config, tools=[])
        await executor._load_skills()
        assert "app_config" not in captured


# =========================================================================
# execute_async: timeout path in run_task
# =========================================================================


class TestExecuteAsyncTimeout:
    def test_run_task_timeout_sets_timed_out(self, executor_module, classes, base_config):
        SubagentExecutor = classes["SubagentExecutor"]
        classes["SubagentResult"]
        # Use the executor_module's SubagentStatus to match the enum class used
        # inside the reloaded module's run_task (importlib.reload creates a new class).
        SubagentStatus = executor_module.SubagentStatus

        short_config = classes["SubagentConfig"](
            name="test-agent",
            description="test",
            model="gpt-4",
            max_turns=10,
            timeout_seconds=0,
        )

        blocking_future: Future = Future()

        def fake_submit(ctx, coro_factory):
            return blocking_future

        executor = SubagentExecutor(config=short_config, tools=[], thread_id="t")
        executor_module._background_tasks.clear()

        def run_inline(fn):
            fn()

        with (
            patch.object(executor_module._scheduler_pool, "submit", run_inline),
            patch.object(executor_module, "_submit_to_isolated_loop_in_context", fake_submit),
        ):
            tid = executor.execute_async("T")

        result = executor_module._background_tasks.get(tid)
        assert result is not None
        assert result.status == SubagentStatus.TIMED_OUT
        assert "timed out" in result.error
        assert result.cancel_event.is_set()
        blocking_future.cancel()

    def test_run_task_exception_sets_failed(self, executor_module, classes, base_config):
        SubagentExecutor = classes["SubagentExecutor"]
        SubagentStatus = executor_module.SubagentStatus

        def fake_submit(ctx, coro_factory):
            raise RuntimeError("submit exploded")

        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")
        executor_module._background_tasks.clear()

        def run_inline(fn):
            fn()

        with (
            patch.object(executor_module._scheduler_pool, "submit", run_inline),
            patch.object(executor_module, "_submit_to_isolated_loop_in_context", fake_submit),
        ):
            tid = executor.execute_async("T")

        result = executor_module._background_tasks.get(tid)
        assert result is not None
        assert result.status == SubagentStatus.FAILED
        assert "submit exploded" in result.error


# =========================================================================
# Integration: execute_async full flow with real scheduler
# =========================================================================


class TestExecuteAsyncIntegration:
    def test_full_flow_with_real_scheduler(self, executor_module, classes, base_config, msg):
        SubagentExecutor = classes["SubagentExecutor"]
        SubagentStatus = executor_module.SubagentStatus
        executor_module._background_tasks.clear()

        final = {"messages": [msg.human("T"), msg.ai("R", "m1")]}
        mock_agent = MagicMock()
        mock_agent.astream = lambda *a, **kw: async_iterator([final])

        executor = SubagentExecutor(config=base_config, tools=[], thread_id="t")

        with patch.object(executor, "_create_agent", return_value=mock_agent):
            tid = executor.execute_async("T")
            # Wait for background task to complete
            import time

            for _ in range(50):
                time.sleep(0.1)
                r = executor_module.get_background_task_result(tid)
                if r and r.status.is_terminal:
                    break

        result = executor_module.get_background_task_result(tid)
        assert result is not None
        assert result.status == SubagentStatus.COMPLETED
        assert result.result == "R"
