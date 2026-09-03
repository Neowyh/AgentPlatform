"""Regression guard: subagent completion must be noticed promptly.

The task tool used to poll background subagent results on a fixed 5s
interval, adding an average 2.5s dead wait per subtask. SubagentResult now
exposes a ``terminal_event`` that is set exactly once on the first terminal
transition; waiters block on it and wake immediately.

These tests pin the two invariants:
1. ``terminal_event`` is set when (and only when) a terminal status lands.
2. ``_await_subagent_terminal`` returns well under the old 5s poll interval
   when the underlying task finishes quickly.

The real executor module is normally shadowed by a MagicMock in
tests/conftest.py (to break a circular import), so we follow the same
setup/teardown pattern as tests/unit/gateway/test_subagent_executor.py:
mock the heavy transitive imports, drop the executor mock, import the real
module, and restore sys.modules afterwards.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import threading
import time
import types
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

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


@pytest.fixture()
def real_executor_modules():
    """Import the REAL ideer.subagents.executor and task_tool modules."""
    original_modules = {name: sys.modules.get(name) for name in _MOCKED_MODULE_NAMES}
    original_executor = sys.modules.get("ideer.subagents.executor")
    original_subagents = sys.modules.get("ideer.subagents")
    original_task_tool = sys.modules.get("ideer.tools.builtins.task_tool")

    for name in ("ideer.tools.builtins.task_tool", "ideer.subagents.executor", "ideer.subagents"):
        sys.modules.pop(name, None)

    for name in _MOCKED_MODULE_NAMES:
        sys.modules[name] = MagicMock()
    storage_module = ModuleType("ideer.skills.storage")
    storage_module.get_or_new_skill_storage = lambda **kw: SimpleNamespace(load_skills=lambda *, enabled_only: [])
    sys.modules["ideer.skills.storage"] = storage_module

    import ideer.subagents.executor as executor_module

    importlib.reload(executor_module)

    # NOTE: `from ideer.tools.builtins import task_tool` would return the
    # StructuredTool re-exported by the package __init__, shadowing the
    # submodule. `import ... as` binds the submodule itself (py3.7+).
    import ideer.tools.builtins.task_tool as task_tool_module

    assert isinstance(task_tool_module._await_subagent_terminal, types.FunctionType)

    yield executor_module, task_tool_module

    for name in _MOCKED_MODULE_NAMES:
        if original_modules[name] is not None:
            sys.modules[name] = original_modules[name]
        elif name in sys.modules:
            del sys.modules[name]

    if original_executor is not None:
        sys.modules["ideer.subagents.executor"] = original_executor
    elif "ideer.subagents.executor" in sys.modules:
        del sys.modules["ideer.subagents.executor"]

    if original_subagents is not None:
        sys.modules["ideer.subagents"] = original_subagents
    elif "ideer.subagents" in sys.modules:
        del sys.modules["ideer.subagents"]

    if original_task_tool is not None:
        sys.modules["ideer.tools.builtins.task_tool"] = original_task_tool
    elif "ideer.tools.builtins.task_tool" in sys.modules:
        del sys.modules["ideer.tools.builtins.task_tool"]


class TestTerminalEvent:
    def test_event_set_on_terminal_transition(self, real_executor_modules) -> None:
        executor, _ = real_executor_modules
        result = executor.SubagentResult(task_id="t1", trace_id="tr1", status=executor.SubagentStatus.RUNNING)
        assert not result.terminal_event.is_set()

        assert result.try_set_terminal(executor.SubagentStatus.COMPLETED, result="done") is True
        assert result.terminal_event.is_set()

    def test_event_not_set_for_non_terminal_write_attempt(self, real_executor_modules) -> None:
        executor, _ = real_executor_modules
        result = executor.SubagentResult(task_id="t2", trace_id="tr2", status=executor.SubagentStatus.RUNNING)
        with pytest.raises(ValueError, match="is not terminal"):
            result.try_set_terminal(executor.SubagentStatus.RUNNING)
        assert not result.terminal_event.is_set()

    def test_event_stays_set_after_lost_race(self, real_executor_modules) -> None:
        executor, _ = real_executor_modules
        result = executor.SubagentResult(task_id="t3", trace_id="tr3", status=executor.SubagentStatus.RUNNING)
        assert result.try_set_terminal(executor.SubagentStatus.COMPLETED, result="first") is True
        # A late terminal write (timeout/cancel race) must not unset the event.
        assert result.try_set_terminal(executor.SubagentStatus.FAILED, error="late") is False
        assert result.terminal_event.is_set()
        assert result.status == executor.SubagentStatus.COMPLETED


class TestCompletionLatency:
    @pytest.mark.asyncio
    async def test_await_terminal_wakes_promptly_after_completion(self, real_executor_modules) -> None:
        """A task completing after 100ms must be observed in well under 1.5s.

        The old 5s polling loop would observe it only after up to 5s; this
        guard fails if the event-driven wake-up regresses back to interval
        polling.
        """
        executor, task_tool = real_executor_modules

        result = executor.SubagentResult(task_id="latency-guard", trace_id="tr4", status=executor.SubagentStatus.RUNNING)
        with executor._background_tasks_lock:
            executor._background_tasks[result.task_id] = result
        try:
            finished = threading.Event()

            def finish_soon() -> None:
                time.sleep(0.1)
                result.try_set_terminal(executor.SubagentStatus.COMPLETED, result="done")
                finished.set()

            threading.Thread(target=finish_soon, daemon=True).start()

            start = time.monotonic()
            observed = await asyncio.wait_for(
                task_tool._await_subagent_terminal("latency-guard", max_polls=30),
                timeout=10.0,
            )
            elapsed = time.monotonic() - start

            assert observed is result
            assert finished.is_set()
            assert elapsed < 1.5, f"completion observed after {elapsed:.2f}s — event wake-up likely regressed to fixed-interval polling"
        finally:
            with executor._background_tasks_lock:
                executor._background_tasks.pop(result.task_id, None)

    @pytest.mark.asyncio
    async def test_await_terminal_returns_none_after_poll_budget(self, real_executor_modules) -> None:
        """A never-completing task exhausts its poll budget instead of hanging."""
        executor, task_tool = real_executor_modules

        result = executor.SubagentResult(task_id="never-done", trace_id="tr5", status=executor.SubagentStatus.RUNNING)
        with executor._background_tasks_lock:
            executor._background_tasks[result.task_id] = result
        try:
            observed = await task_tool._await_subagent_terminal("never-done", max_polls=1)
            assert observed is None
        finally:
            with executor._background_tasks_lock:
                executor._background_tasks.pop(result.task_id, None)
