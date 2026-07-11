"""Comprehensive tests for condition_step — targeting 98%+ coverage."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.harness.ideer.workflows.state import WorkflowState
from packages.harness.ideer.workflows.steps.condition_step import (
    _evaluate_expression,
    _execute_branch,
    execute_condition_step,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**inputs) -> WorkflowState:
    state = WorkflowState(workflow_name="test", run_id="run-1", inputs=inputs)
    state.get_context = MagicMock(return_value={"inputs": inputs, "steps": {}})
    return state


# Correct mock targets — render_value and execute_step are imported locally
# inside condition_step functions, so we must patch their source modules.
_RENDER_MOCK = "packages.harness.ideer.workflows.template.render_value"
_STEP_EXEC_MOCK = "packages.harness.ideer.workflows.steps.execute_step"


def _identity_render(expr, ctx):
    """Mock render_value that returns expression as-is but converts
    'true'/'false' keywords to actual booleans for realistic evaluation."""
    s = expr.strip()
    if s == "true":
        return True
    if s == "false":
        return False
    return expr


# ===========================================================================
# _evaluate_expression
# ===========================================================================


class TestEvaluateExpression:
    """All branches of _evaluate_expression."""

    def test_non_string_rendered_returns_bool(self):
        """Line 33-34: render_value returns non-str → bool(result)."""
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            return_value=42,
        ):
            assert _evaluate_expression("{{x}}", {}) is True

        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            return_value=0,
        ):
            assert _evaluate_expression("{{x}}", {}) is False

        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            return_value=None,
        ):
            assert _evaluate_expression("{{x}}", {}) is False

    def test_non_string_rendered_list_true(self):
        """Non-empty list rendered → True."""
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            return_value=[1],
        ):
            assert _evaluate_expression("{{x}}", {}) is True

    # -- Logical operators --------------------------------------------------

    def test_and_operator_both_true(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("true and true", {}) is True

    def test_and_operator_left_false(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("false and true", {}) is False

    def test_and_operator_right_false_short_circuit(self):
        """and short-circuits: right side not evaluated when left is False."""
        call_count = 0

        def fake_render(expr, ctx):
            nonlocal call_count
            call_count += 1
            return _identity_render(expr, ctx)

        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=fake_render,
        ):
            result = _evaluate_expression("false and whatever", {})
            assert result is False
            # render_value called once for the initial full expression,
            # then once for the left part "false" in the recursive call
            assert call_count == 2

    def test_or_operator_either_true(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("false or true", {}) is True

    def test_or_operator_both_false(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("false or false", {}) is False

    def test_or_operator_left_true_short_circuit(self):
        call_count = 0

        def fake_render(expr, ctx):
            nonlocal call_count
            call_count += 1
            return expr

        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=fake_render,
        ):
            result = _evaluate_expression("true or whatever", {})
            assert result is True
            assert call_count == 2

    def test_not_operator_true(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("not false", {}) is True

    def test_not_operator_false(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("not true", {}) is False

    # -- Comparison operators (float success) --------------------------------

    def test_ge_float_true(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("5 >= 3", {}) is True

    def test_ge_float_false(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("3 >= 5", {}) is False

    def test_le_float_true(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("3 <= 5", {}) is True

    def test_le_float_false(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("5 <= 3", {}) is False

    def test_ne_float_true(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("5 != 3", {}) is True

    def test_ne_float_false(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("5 != 5", {}) is False

    def test_eq_float_true(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("5 == 5", {}) is True

    def test_eq_float_false(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("5 == 3", {}) is False

    def test_gt_float_true(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("5 > 3", {}) is True

    def test_gt_float_false(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("3 > 5", {}) is False

    def test_lt_float_true(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("3 < 5", {}) is True

    def test_lt_float_false(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("5 < 3", {}) is False

    # -- Comparison operators (float fails → string fallback) ----------------

    def test_eq_string_fallback_true(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("abc == abc", {}) is True

    def test_eq_string_fallback_false(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("abc == xyz", {}) is False

    def test_ne_string_fallback_true(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("abc != xyz", {}) is True

    def test_ne_string_fallback_false(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("abc != abc", {}) is False

    def test_gt_string_not_float_returns_false(self):
        """Line 59: non-numeric comparison with > returns False."""
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("abc > xyz", {}) is False

    def test_ge_string_not_float_returns_false(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("abc >= xyz", {}) is False

    def test_lt_string_not_float_returns_false(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("abc < xyz", {}) is False

    def test_le_string_not_float_returns_false(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("abc <= xyz", {}) is False

    # -- Fallback: plain string truthiness ----------------------------------

    def test_plain_truthy_string(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            return_value="yes",
        ):
            assert _evaluate_expression("yes", {}) is True

    def test_plain_empty_string(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            return_value="",
        ):
            assert _evaluate_expression("empty", {}) is False

    def test_plain_falsy_string(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            return_value="false",
        ):
            # "false" is a non-empty string → bool("false") is True
            assert _evaluate_expression("false", {}) is True

    # -- Nested logical + comparison ----------------------------------------

    def test_nested_and_with_comparison(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("5 > 3 and 10 > 2", {}) is True

    def test_nested_or_with_comparison(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("5 < 3 or 10 > 2", {}) is True

    def test_not_with_comparison(self):
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            side_effect=_identity_render,
        ):
            assert _evaluate_expression("not 5 < 3", {}) is True

    # -- Default expression --------------------------------------------------

    def test_default_expression_true(self):
        """When no expression given, defaults to 'true'."""
        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            return_value="true",
        ):
            assert _evaluate_expression("true", {}) is True


# ===========================================================================
# _execute_branch
# ===========================================================================


class TestExecuteBranch:
    """All branches of _execute_branch."""

    @pytest.mark.asyncio
    async def test_dict_branch_with_type_and_id(self):
        """Lines 68-75: dict branch with type + id → execute_step + set_step_result."""
        state = _make_state()
        mock_result = {"output": "ok"}

        with patch(
            "packages.harness.ideer.workflows.steps.execute_step",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_exec:
            result = await _execute_branch(
                {"type": "tool", "id": "sub-1", "name": "search"},
                "cond-1",
                state,
            )

        mock_exec.assert_called_once_with("tool", {"type": "tool", "id": "sub-1", "name": "search"}, state)
        assert result == mock_result

    @pytest.mark.asyncio
    async def test_dict_branch_with_type_no_id(self):
        """Lines 68-75: dict with type but no id → execute_step, no set_step_result."""
        state = _make_state()

        with patch(
            "packages.harness.ideer.workflows.steps.execute_step",
            new_callable=AsyncMock,
            return_value="res",
        ) as mock_exec:
            result = await _execute_branch({"type": "tool"}, "cond-1", state)

        mock_exec.assert_called_once()
        assert result == "res"

    @pytest.mark.asyncio
    async def test_dict_branch_no_type(self):
        """Lines 76-80: dict without 'type' → warning log, return None."""
        state = _make_state()

        with patch(
            "packages.harness.ideer.workflows.steps.condition_step.logger",
        ) as mock_logger:
            result = await _execute_branch({"name": "foo"}, "cond-1", state)

        assert result is None
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_branch_multiple_steps(self):
        """Lines 83-91: list branch with multiple sub-steps → returns list of results."""
        state = _make_state()
        sub_1 = {"type": "tool", "id": "s1", "name": "a"}
        sub_2 = {"type": "tool", "id": "s2", "name": "b"}

        with patch(
            "packages.harness.ideer.workflows.steps.execute_step",
            new_callable=AsyncMock,
            side_effect=["r1", "r2"],
        ) as mock_exec:
            result = await _execute_branch([sub_1, sub_2], "cond-1", state)

        assert result == ["r1", "r2"]
        assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_list_branch_single_step_returns_scalar(self):
        """Line 98: list with exactly one result → returns the single result."""
        state = _make_state()
        sub = {"type": "tool", "id": "s1", "name": "a"}

        with patch(
            "packages.harness.ideer.workflows.steps.execute_step",
            new_callable=AsyncMock,
            return_value="only",
        ):
            result = await _execute_branch([sub], "cond-1", state)

        assert result == "only"

    @pytest.mark.asyncio
    async def test_list_branch_item_missing_type(self):
        """Lines 93-97: list item without 'type' → warning, skipped."""
        state = _make_state()

        with patch(
            "packages.harness.ideer.workflows.steps.execute_step",
            new_callable=AsyncMock,
        ) as mock_exec:
            with patch(
                "packages.harness.ideer.workflows.steps.condition_step.logger",
            ) as mock_logger:
                result = await _execute_branch([{"id": "no-type"}], "cond-1", state)

        mock_exec.assert_not_called()
        mock_logger.warning.assert_called_once()
        # No valid results → empty list, len != 1 so returns []
        assert result == []

    @pytest.mark.asyncio
    async def test_list_branch_mixed_valid_and_invalid(self):
        """List with valid + invalid items → only valid results returned."""
        state = _make_state()

        with patch(
            "packages.harness.ideer.workflows.steps.execute_step",
            new_callable=AsyncMock,
            return_value="ok",
        ):
            with patch(
                "packages.harness.ideer.workflows.steps.condition_step.logger",
            ) as mock_logger:
                result = await _execute_branch(
                    [{"type": "tool"}, "not-a-dict", {"id": "no-type"}],
                    "cond-1",
                    state,
                )

        # Only {"type": "tool"} is valid; "not-a-dict" and {"id": "no-type"} are skipped.
        # When a list branch yields exactly 1 result, _execute_branch unwraps it.
        assert result == "ok"
        assert mock_logger.warning.call_count == 2  # "not-a-dict" + {"id": "no-type"}

    @pytest.mark.asyncio
    async def test_string_branch_goto(self):
        """Lines 101-102: string branch → goto directive."""
        state = _make_state()
        result = await _execute_branch("step-42", "cond-1", state)
        assert result == "goto:step-42"

    @pytest.mark.asyncio
    async def test_none_branch(self):
        """Line 104: None branch → return None."""
        state = _make_state()
        result = await _execute_branch(None, "cond-1", state)
        assert result is None

    @pytest.mark.asyncio
    async def test_int_branch_returns_none(self):
        """Line 104: unexpected type (int) → return None."""
        state = _make_state()
        result = await _execute_branch(999, "cond-1", state)
        assert result is None


# ===========================================================================
# execute_condition_step
# ===========================================================================


class TestExecuteConditionStep:
    """All branches of execute_condition_step."""

    @pytest.mark.asyncio
    async def test_true_branch_then(self):
        """Expression true → execute 'then' branch."""
        state = _make_state()
        step_def = {
            "id": "cond-1",
            "expression": "true",
            "then": {"type": "tool", "id": "t1"},
        }

        with patch(
            "packages.harness.ideer.workflows.steps.condition_step._evaluate_expression",
            return_value=True,
        ):
            with patch(
                "packages.harness.ideer.workflows.steps.condition_step._execute_branch",
                new_callable=AsyncMock,
                return_value="then-result",
            ) as mock_branch:
                result = await execute_condition_step(step_def, state)

        mock_branch.assert_called_once_with({"type": "tool", "id": "t1"}, "cond-1", state)
        assert result == "then-result"

    @pytest.mark.asyncio
    async def test_false_branch_else(self):
        """Expression false → execute 'else' branch."""
        state = _make_state()
        step_def = {
            "id": "cond-1",
            "expression": "false",
            "then": {"type": "tool", "id": "t1"},
            "else": {"type": "tool", "id": "e1"},
        }

        with patch(
            "packages.harness.ideer.workflows.steps.condition_step._evaluate_expression",
            return_value=False,
        ):
            with patch(
                "packages.harness.ideer.workflows.steps.condition_step._execute_branch",
                new_callable=AsyncMock,
                return_value="else-result",
            ) as mock_branch:
                result = await execute_condition_step(step_def, state)

        mock_branch.assert_called_once_with({"type": "tool", "id": "e1"}, "cond-1", state)
        assert result == "else-result"

    @pytest.mark.asyncio
    async def test_no_branch_returns_bool(self):
        """No then/else → return raw boolean result."""
        state = _make_state()
        step_def = {"id": "cond-1", "expression": "true"}

        with patch(
            "packages.harness.ideer.workflows.steps.condition_step._evaluate_expression",
            return_value=True,
        ):
            with patch(
                "packages.harness.ideer.workflows.steps.condition_step._execute_branch",
                new_callable=AsyncMock,
            ) as mock_branch:
                result = await execute_condition_step(step_def, state)

        mock_branch.assert_not_called()
        assert result is True

    @pytest.mark.asyncio
    async def test_default_expression(self):
        """Missing expression key → defaults to 'true'."""
        state = _make_state()
        step_def = {"id": "cond-1", "then": "next-step"}

        with patch(
            "packages.harness.ideer.workflows.template.render_value",
            return_value="true",
        ):
            with patch(
                "packages.harness.ideer.workflows.steps.condition_step._execute_branch",
                new_callable=AsyncMock,
                return_value="goto:next-step",
            ):
                result = await execute_condition_step(step_def, state)

        assert result == "goto:next-step"

    @pytest.mark.asyncio
    async def test_false_expression_no_else_returns_false(self):
        """Expression false but no else branch → return False."""
        state = _make_state()
        step_def = {"id": "cond-1", "expression": "false"}

        with patch(
            "packages.harness.ideer.workflows.steps.condition_step._evaluate_expression",
            return_value=False,
        ):
            result = await execute_condition_step(step_def, state)

        assert result is False

    @pytest.mark.asyncio
    async def test_context_from_state(self):
        """Verify get_context() is called and passed to _evaluate_expression."""
        state = _make_state(x=10)
        step_def = {"id": "cond-1", "expression": "{{inputs.x}} > 5"}

        with patch(
            "packages.harness.ideer.workflows.steps.condition_step._evaluate_expression",
            return_value=True,
        ) as mock_eval:
            with patch(
                "packages.harness.ideer.workflows.steps.condition_step._execute_branch",
                new_callable=AsyncMock,
                return_value=True,
            ):
                await execute_condition_step(step_def, state)

        state.get_context.assert_called_once()
        mock_eval.assert_called_once_with("{{inputs.x}} > 5", {"inputs": {"x": 10}, "steps": {}})
