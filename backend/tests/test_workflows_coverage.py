"""Targeted tests to cover missing lines in executor.py and template.py.

Covers:
- executor.py lines 142-151: except block in WorkflowExecutor.run()
    - Normal exception sets FAILED status and persists error
    - CANCELLED status is preserved during exception
    - Inner save_run_state failure is caught and logged
- template.py line 61: _render_item list branch
- template.py lines 98-103: _resolve dunder attribute block and AttributeError
- template.py lines 118-119: _resolve_safe rejects excessively long expressions
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.harness.ideer.workflows.executor import WorkflowExecutor
from packages.harness.ideer.workflows.schema import StepDef, StepType, WorkflowDef
from packages.harness.ideer.workflows.state import RunStatus
from packages.harness.ideer.workflows.template import (
    _MAX_EXPR_LENGTH,
    _MISSING,
    _render_item,
    _resolve,
    _resolve_safe,
    render_params,
    render_value,
)

# ── Helpers ─────────────────────────────────────────────────────────


def _make_executor(steps=None, store=None):
    wf = WorkflowDef(name="test-wf", steps=steps or [])
    if store is None:
        store = MagicMock()
        store.save_run_state = AsyncMock()
    return WorkflowExecutor(wf, store=store)


# ── executor.py lines 142-151: except block in run() ──────────────


class TestExecutorRunExceptionHandling:
    """Tests for the except block in WorkflowExecutor.run()."""

    @pytest.mark.asyncio
    async def test_exception_sets_failed_status_and_persists(self):
        """Lines 142-150: A normal exception sets FAILED status, stores error, and persists."""
        step = StepDef(id="s1", type=StepType.TOOL, tool="bad_tool")
        executor = _make_executor(steps=[step])

        with patch.object(executor, "_execute_step", side_effect=RuntimeError("boom")):
            state = await executor.run({})

        assert state.status == RunStatus.FAILED
        assert state.error == "boom"
        # save_run_state was called at least for initial + error states
        assert executor.store.save_run_state.await_count >= 2

    @pytest.mark.asyncio
    async def test_exception_preserves_cancelled_status(self):
        """Lines 142-144: If state is already CANCELLED, the exception does not overwrite it."""
        step = StepDef(id="s1", type=StepType.TOOL, tool="bad_tool")
        executor = _make_executor(steps=[step])

        async def _cancel_then_raise(step_arg, state_arg):
            state_arg.status = RunStatus.CANCELLED
            raise RuntimeError("interrupted")

        with patch.object(executor, "_execute_step", side_effect=_cancel_then_raise):
            state = await executor.run({})

        assert state.status == RunStatus.CANCELLED
        assert state.error == "interrupted"

    @pytest.mark.asyncio
    async def test_exception_persist_failure_is_logged(self):
        """Lines 148-151: If save_run_state itself raises during error handling, it is caught."""
        step = StepDef(id="s1", type=StepType.TOOL, tool="bad_tool")
        executor = _make_executor(steps=[step])

        call_count = 0

        async def _flaky_save(state_arg):
            nonlocal call_count
            call_count += 1
            # First call is the initial persist (line 108) - let it succeed.
            # Second call is inside the except block (line 149) - make it fail.
            if call_count >= 2:
                raise RuntimeError("db down")

        executor.store.save_run_state = _flaky_save

        # Should not raise — the inner except swallows the save failure
        with patch.object(executor, "_execute_step", side_effect=RuntimeError("boom")):
            state = await executor.run({})

        assert state.status == RunStatus.FAILED
        assert state.error == "boom"


# ── template.py line 61: _render_item list branch ──────────────────


class TestRenderItemList:
    def test_render_item_list(self):
        """Line 61: _render_item returns a list with each element rendered."""
        ctx = {"inputs": {"a": "alpha", "b": "beta"}}
        result = _render_item(["{{inputs.a}}", "{{inputs.b}}"], ctx)
        assert result == ["alpha", "beta"]

    def test_render_item_nested_list(self):
        """Line 61: _render_item handles nested lists."""
        ctx = {"inputs": {"x": "X"}}
        result = _render_item([["{{inputs.x}}", "plain"]], ctx)
        assert result == [["X", "plain"]]

    def test_render_item_mixed_types_in_list(self):
        """Line 61: _render_item handles a list containing strings, dicts, ints."""
        ctx = {"inputs": {"v": "val"}}
        result = _render_item(["{{inputs.v}}", 42, {"key": "{{inputs.v}}"}], ctx)
        assert result == ["val", 42, {"key": "val"}]

    def test_render_params_with_list_value(self):
        """render_params delegates list values through _render_item (line 76)."""
        ctx = {"inputs": {"n": "hello"}}
        result = render_params({"items": ["{{inputs.n}}", "world"]}, ctx)
        assert result == {"items": ["hello", "world"]}


# ── template.py lines 98-103: _resolve dunder + AttributeError ─────


class TestResolveAttributeAccess:
    def test_dunder_attribute_blocked(self):
        """Line 98-99: Accessing __class__ raises AttributeError."""

        class Obj:
            pass

        ctx = {"obj": Obj()}
        with pytest.raises(AttributeError, match="forbidden"):
            _resolve("obj.__class__", ctx)

    def test_dunder_globals_blocked(self):
        """Line 98-99: Accessing __globals__ raises AttributeError."""

        def func():
            pass

        ctx = {"fn": func}
        with pytest.raises(AttributeError, match="forbidden"):
            _resolve("fn.__globals__", ctx)

    def test_nonexistent_attribute_raises(self):
        """Line 102-103: Accessing a missing attribute raises AttributeError."""

        class Obj:
            pass

        ctx = {"obj": Obj()}
        with pytest.raises(AttributeError, match="not found on Obj"):
            _resolve("obj.nonexistent", ctx)

    def test_valid_attribute_resolves(self):
        """Normal attribute access on a non-dict object works."""

        class Obj:
            name = "test"

        ctx = {"obj": Obj()}
        assert _resolve("obj.name", ctx) == "test"


# ── template.py lines 118-119: _resolve_safe long expression ──────


class TestResolveSafeLongExpression:
    def test_long_expression_returns_missing(self):
        """Lines 117-119: Expressions exceeding _MAX_EXPR_LENGTH return _MISSING."""
        long_expr = "a" * (_MAX_EXPR_LENGTH + 1)
        result = _resolve_safe(long_expr, {})
        assert result is _MISSING

    def test_max_length_expression_not_rejected(self):
        """Expressions at exactly _MAX_EXPR_LENGTH are not rejected by the length check."""
        expr = "a" * _MAX_EXPR_LENGTH
        ctx = {expr: "ok"}
        result = _resolve_safe(expr, ctx)
        assert result == "ok"

    def test_render_value_returns_none_for_long_template(self):
        """render_value returns None for a full-string template with too-long expression."""
        long_expr = "{{" + "x" * (_MAX_EXPR_LENGTH + 1) + "}}"
        result = render_value(long_expr, {})
        assert result is None

    def test_render_value_preserves_placeholder_for_long_partial(self):
        """render_value preserves the placeholder when the inner expression is too long."""
        long_expr = "prefix {{" + "x" * (_MAX_EXPR_LENGTH + 1) + "}} suffix"
        result = render_value(long_expr, {})
        # The placeholder is preserved since _resolve_safe returns _MISSING
        assert "x" * (_MAX_EXPR_LENGTH + 1) in str(result)
