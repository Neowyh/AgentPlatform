"""Worker happy-path run through a mock agent factory.

The legacy T1 first-token timing log (``stage=agent_build``) no longer exists
in the upstream runtime, so the harness now asserts the upstream-equivalent
contract: a run driven by a mock factory terminates with a success status and
a published end frame.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deerflow.runtime.runs.manager import RunStartOutcome
from deerflow.runtime.runs.schemas import RunStatus
from deerflow.runtime.runs.worker import RunContext, run_agent


@pytest.mark.asyncio
async def test_run_agent_success_with_mock_factory():
    """run_agent drives a mock factory's agent to a successful terminal state."""
    bridge = MagicMock()
    bridge.publish = AsyncMock()
    bridge.publish_end = AsyncMock()
    bridge.cleanup = AsyncMock()

    run_manager = MagicMock()
    run_manager.set_status = AsyncMock()
    run_manager.update_model_name = AsyncMock()
    run_manager.update_run_completion = AsyncMock()
    run_manager.update_run_progress = MagicMock()
    run_manager.wait_for_prior_finalizing = AsyncMock()
    run_manager.try_start = AsyncMock(return_value=RunStartOutcome.started)
    run_manager.set_status_if_not_cancelled = AsyncMock(return_value=None)
    run_manager.set_finalizing = AsyncMock()
    run_manager.update_finalizing_progress = AsyncMock()
    run_manager.persist_current_status = AsyncMock()
    run_manager.has_later_started_run = AsyncMock(return_value=False)
    run_manager.cleanup = AsyncMock()

    record = MagicMock()
    record.run_id = "run_1"
    record.thread_id = "thread_1"
    record.assistant_id = "lead_agent"
    record.model_name = "gpt-4"
    record.abort_event = MagicMock()
    record.abort_event.is_set.return_value = False
    record.status = RunStatus.success

    ctx = RunContext(checkpointer=None, store=None)

    mock_agent = MagicMock()
    mock_agent.metadata = {"model_name": "gpt-4"}

    async def _empty_astream(*args, **kwargs):
        return
        yield  # make it an async generator

    mock_agent.astream = _empty_astream

    def agent_factory(config=None, app_config=None):
        return mock_agent

    with patch("deerflow.runtime.runs.worker.inject_langfuse_metadata"):
        with patch("deerflow.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
            with patch("deerflow.runtime.runs.worker.os.environ", {}):
                with patch("deerflow.runtime.runs.worker.resolve_root_run_name", return_value="test_run"):
                    await run_agent(
                        bridge,
                        run_manager,
                        record,
                        ctx=ctx,
                        agent_factory=agent_factory,
                        graph_input={"messages": []},
                        config={},
                    )

    run_manager.set_status_if_not_cancelled.assert_awaited_once()
    assert run_manager.set_status_if_not_cancelled.await_args.args[1] is RunStatus.success
    bridge.publish_end.assert_awaited_once_with("run_1")
