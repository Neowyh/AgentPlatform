"""T2: pre-run checkpoint references stored without deepcopy; copy only on rollback."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideer.runtime.runs.worker import RunContext


def _success_harness():
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
    from ideer.runtime.runs.schemas import RunStatus

    record.status = RunStatus.success

    fake_tuple = SimpleNamespace(
        config={"configurable": {"checkpoint_id": "ckpt-1", "checkpoint_ns": ""}},
        checkpoint={"id": "ckpt-1", "channel_values": {}},
        metadata={},
        pending_writes=[],
    )
    checkpointer = SimpleNamespace(aget_tuple=AsyncMock(return_value=fake_tuple))
    ctx = RunContext(checkpointer=checkpointer, store=None)

    mock_agent = MagicMock()
    mock_agent.metadata = {"model_name": "gpt-4"}

    async def _empty_astream(*args, **kwargs):
        return
        yield  # make it an async generator

    mock_agent.astream = _empty_astream

    def agent_factory(config=None, app_config=None):
        return mock_agent

    return bridge, run_manager, record, ctx, agent_factory


@pytest.mark.asyncio
async def test_success_path_copies_nothing():
    """The happy path must not pay deepcopy: rollback-only data stays by reference."""
    import ideer.runtime.runs.worker as worker_mod
    from ideer.runtime.runs.worker import run_agent

    bridge, run_manager, record, ctx, agent_factory = _success_harness()
    with patch.object(worker_mod, "copy") as mock_copy:
        with patch("ideer.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("ideer.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("ideer.runtime.runs.worker.os.environ", {}):
                    with patch("ideer.runtime.runs.worker.resolve_root_run_name", return_value="test_run"):
                        await run_agent(
                            bridge,
                            run_manager,
                            record,
                            ctx=ctx,
                            agent_factory=agent_factory,
                            graph_input={"messages": []},
                            config={},
                        )
    mock_copy.deepcopy.assert_not_called()
