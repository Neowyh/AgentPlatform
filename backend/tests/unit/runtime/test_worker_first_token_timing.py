"""First-token timing logs (T1): agent-build stage emits one timing record."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideer.runtime.runs.worker import RunContext


@pytest.mark.asyncio
async def test_agent_build_stage_emits_timing(caplog):
    """run_agent logs stage=agent_build timing around the factory call."""
    from ideer.runtime.runs.schemas import RunStatus
    from ideer.runtime.runs.worker import run_agent

    bridge = MagicMock()
    bridge.publish = AsyncMock()
    bridge.publish_end = AsyncMock()
    bridge.cleanup = AsyncMock()

    run_manager = MagicMock()
    run_manager.set_status = AsyncMock()
    run_manager.update_model_name = AsyncMock()
    run_manager.update_run_completion = AsyncMock()
    run_manager.update_run_progress = MagicMock()

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

    with patch("ideer.runtime.runs.worker.inject_langfuse_metadata"):
        with patch("ideer.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
            with patch("ideer.runtime.runs.worker.os.environ", {}):
                with patch("ideer.runtime.runs.worker.resolve_root_run_name", return_value="test_run"):
                    with caplog.at_level(logging.INFO, logger="ideer.runtime.runs.worker"):
                        await run_agent(
                            bridge,
                            run_manager,
                            record,
                            ctx=ctx,
                            agent_factory=agent_factory,
                            graph_input={"messages": []},
                            config={},
                        )

    assert any("first_token_timing" in message and "stage=agent_build" in message for message in caplog.messages)
