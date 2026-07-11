"""Tests for ideer.workflows.steps.human_step — human review step executor."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ideer.workflows.state import RunStatus, WorkflowState


def _make_state(**kwargs) -> WorkflowState:
    return WorkflowState(workflow_name="test", run_id="run-1", **kwargs)


# ---------------------------------------------------------------------------
# execute_human_review_step
# ---------------------------------------------------------------------------


class TestExecuteHumanReviewStep:
    @pytest.mark.asyncio
    async def test_review_submitted_immediately(self):
        from ideer.workflows.steps.human_step import execute_human_review_step

        step_def = {"id": "review1", "type": "human_review"}
        state = _make_state()

        review_result = {"approved": True, "comment": "Looks good"}
        loaded_state = _make_state()
        loaded_state.status = RunStatus.RUNNING
        loaded_state.review_result = review_result

        mock_store = AsyncMock()
        mock_store.save_run_state = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=loaded_state)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await execute_human_review_step(step_def, state, mock_store)
            assert result == review_result
            assert state.status == RunStatus.RUNNING
            assert "review1" in state.steps

    @pytest.mark.asyncio
    async def test_review_cancelled(self):
        from ideer.workflows.steps.human_step import execute_human_review_step

        step_def = {"id": "review1", "type": "human_review"}
        state = _make_state()

        loaded_state = _make_state()
        loaded_state.status = RunStatus.CANCELLED

        mock_store = AsyncMock()
        mock_store.save_run_state = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=loaded_state)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="cancelled"):
                await execute_human_review_step(step_def, state, mock_store)
            assert state.status == RunStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_timeout(self):
        from ideer.workflows.steps.human_step import execute_human_review_step

        step_def = {"id": "review1", "type": "human_review", "timeout": 0.05}
        state = _make_state()

        loaded_state = _make_state()
        loaded_state.status = RunStatus.WAITING_HUMAN

        mock_store = AsyncMock()
        mock_store.save_run_state = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=loaded_state)

        # Use a counter to advance elapsed past timeout by making each sleep
        # add a large chunk of fake time
        call_count = 0
        _real_sleep = asyncio.sleep

        async def _fast_sleep(t):
            nonlocal call_count
            call_count += 1
            # Don't actually sleep, just return immediately
            # The loop increments elapsed by poll_interval, so we need
            # enough iterations for elapsed to exceed timeout

        with patch("ideer.workflows.steps.human_step.asyncio.sleep", side_effect=_fast_sleep):
            with pytest.raises(TimeoutError, match="timed out"):
                await execute_human_review_step(step_def, state, mock_store)
            assert state.status == RunStatus.FAILED

    @pytest.mark.asyncio
    async def test_run_disappeared(self):
        from ideer.workflows.steps.human_step import execute_human_review_step

        step_def = {"id": "review1", "type": "human_review"}
        state = _make_state()

        mock_store = AsyncMock()
        mock_store.save_run_state = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=None)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="disappeared"):
                await execute_human_review_step(step_def, state, mock_store)

    @pytest.mark.asyncio
    async def test_unexpected_error_persists_failed_state(self):
        from ideer.workflows.steps.human_step import execute_human_review_step

        step_def = {"id": "review1", "type": "human_review"}
        state = _make_state()
        state.status = RunStatus.WAITING_HUMAN

        mock_store = AsyncMock()
        mock_store.save_run_state = AsyncMock()
        mock_store.load_run_state = AsyncMock(side_effect=Exception("db error"))

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception, match="db error"):
                await execute_human_review_step(step_def, state, mock_store)
            assert state.status == RunStatus.FAILED

    @pytest.mark.asyncio
    async def test_default_timeout(self):
        from ideer.workflows.steps.human_step import execute_human_review_step

        step_def = {"id": "review1", "type": "human_review"}
        state = _make_state()

        loaded_state = _make_state()
        loaded_state.status = RunStatus.RUNNING
        loaded_state.review_result = {"ok": True}

        mock_store = AsyncMock()
        mock_store.save_run_state = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=loaded_state)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await execute_human_review_step(step_def, state, mock_store)
            assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_persistence_called_on_pause(self):
        from ideer.workflows.steps.human_step import execute_human_review_step

        step_def = {"id": "review1", "type": "human_review"}
        state = _make_state()

        loaded_state = _make_state()
        loaded_state.status = RunStatus.RUNNING
        loaded_state.review_result = {"approved": True}

        # Track the status at the time of each save_run_state call
        saved_statuses = []

        async def _save(state_ref):
            saved_statuses.append(state_ref.status)

        mock_store = AsyncMock()
        mock_store.save_run_state = AsyncMock(side_effect=_save)
        mock_store.load_run_state = AsyncMock(return_value=loaded_state)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await execute_human_review_step(step_def, state, mock_store)
            # First save should have WAITING_HUMAN status
            assert saved_statuses[0] == RunStatus.WAITING_HUMAN

    @pytest.mark.asyncio
    async def test_polls_until_review_submitted(self):
        from ideer.workflows.steps.human_step import execute_human_review_step

        step_def = {"id": "review1", "type": "human_review"}
        state = _make_state()

        waiting_state = _make_state()
        waiting_state.status = RunStatus.WAITING_HUMAN

        submitted_state = _make_state()
        submitted_state.status = RunStatus.RUNNING
        submitted_state.review_result = {"decision": "approve"}

        mock_store = AsyncMock()
        mock_store.save_run_state = AsyncMock()
        mock_store.load_run_state = AsyncMock(
            side_effect=[
                waiting_state,
                waiting_state,
                submitted_state,
            ]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await execute_human_review_step(step_def, state, mock_store)
            assert result == {"decision": "approve"}
            assert mock_store.load_run_state.call_count == 3

    @pytest.mark.asyncio
    async def test_step_result_recorded(self):
        from ideer.workflows.steps.human_step import execute_human_review_step

        step_def = {"id": "review1", "type": "human_review"}
        state = _make_state()

        loaded_state = _make_state()
        loaded_state.status = RunStatus.RUNNING
        loaded_state.review_result = {"score": 95}

        mock_store = AsyncMock()
        mock_store.save_run_state = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=loaded_state)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await execute_human_review_step(step_def, state, mock_store)
            assert "review1" in state.steps
            assert state.steps["review1"].status == "completed"
            assert state.steps["review1"].output == {"score": 95}
