import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, call
from uuid import uuid4

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.memory import InMemorySaver

from deerflow.runtime.checkpoint_state import CheckpointStateAccessor, build_state_mutation_graph
from deerflow.runtime.runs.manager import RunManager
from deerflow.runtime.runs.schemas import RunStatus
from deerflow.runtime.runs.worker import (
    RollbackPoint,
    RunContext,
    _agent_factory_supports_app_config,
    _build_runtime_context,
    _capture_rollback_point,
    _install_runtime_context,
    _rollback_to_pre_run_checkpoint,
    run_agent,
)


class _RollbackFakeCheckpointer:
    """Checkpointer double exposing the methods the rollback path may call."""

    def __init__(self):
        self.adelete_thread = AsyncMock()
        self.aget_tuple = AsyncMock(return_value=None)
        self.aput_writes = AsyncMock()


def _rollback_accessor(checkpointer):
    return CheckpointStateAccessor(graph=SimpleNamespace(), checkpointer=checkpointer, mode="full")


def _make_rollback_point(*, checkpoint_id="ckpt_1", messages=("before",), pending_writes=()):
    return RollbackPoint(
        config={
            "configurable": {
                "thread_id": "thread-1",
                "checkpoint_ns": "",
                "checkpoint_id": checkpoint_id,
            }
        },
        state_values={},
        messages=tuple(messages),
        metadata={"source": "input"},
        pending_writes=tuple(pending_writes),
    )


def _stub_mutation_graph(monkeypatch, *, restored_config):
    """Replace the rollback mutation graph with a stub returning ``restored_config``.

    The compiled LangGraph mutation graph is infrastructure; stubbing it keeps
    the worker's rollback orchestration (config checks, message overwrite,
    pending-write validation and grouping) under test.
    """
    mock_graph = SimpleNamespace()
    mock_graph.aupdate_state = AsyncMock(return_value=restored_config)
    monkeypatch.setattr(
        "deerflow.runtime.runs.worker.build_state_mutation_graph",
        lambda *args, **kwargs: mock_graph,
    )
    return mock_graph


def _make_checkpoint(checkpoint_id: str, messages: list[str]):
    checkpoint = empty_checkpoint()
    checkpoint["id"] = checkpoint_id
    checkpoint["channel_values"] = {"messages": messages}
    return checkpoint


def test_build_runtime_context_includes_app_config_when_present():
    app_config = object()

    context = _build_runtime_context("thread-1", "run-1", None, app_config)

    assert context["thread_id"] == "thread-1"
    assert context["run_id"] == "run-1"
    assert context["app_config"] is app_config


def test_install_runtime_context_preserves_existing_thread_id_and_threads_app_config():
    app_config = object()
    config = {"context": {"thread_id": "caller-thread"}}

    _install_runtime_context(
        config,
        {
            "thread_id": "record-thread",
            "run_id": "run-1",
            "app_config": app_config,
        },
    )

    assert config["context"]["thread_id"] == "caller-thread"
    assert config["context"]["run_id"] == "run-1"
    assert config["context"]["app_config"] is app_config


@pytest.mark.anyio
async def test_run_agent_threads_explicit_app_config_into_config_only_factory():
    run_manager = RunManager()
    record = await run_manager.create("thread-1")
    bridge = SimpleNamespace(
        publish=AsyncMock(),
        publish_end=AsyncMock(),
        cleanup=AsyncMock(),
    )
    app_config = object()
    captured: dict[str, object] = {}

    class DummyAgent:
        async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
            captured["astream_context"] = config["context"]
            yield {"messages": []}

    def factory(*, config):
        captured["factory_context"] = config["context"]
        return DummyAgent()

    await run_agent(
        bridge,
        run_manager,
        record,
        ctx=RunContext(checkpointer=None, app_config=app_config),
        agent_factory=factory,
        graph_input={},
        config={},
    )
    await asyncio.sleep(0)

    assert captured["factory_context"]["app_config"] is app_config
    assert captured["astream_context"]["app_config"] is app_config
    fetched = await run_manager.get(record.run_id)
    assert fetched is not None
    assert fetched.status == RunStatus.success
    bridge.publish_end.assert_awaited_once_with(record.run_id)
    bridge.cleanup.assert_awaited_once_with(record.run_id, delay=60)


@pytest.mark.anyio
async def test_run_agent_defaults_root_run_name_from_assistant_id():
    run_manager = RunManager()
    record = await run_manager.create("thread-1", assistant_id="lead_agent")
    bridge = SimpleNamespace(
        publish=AsyncMock(),
        publish_end=AsyncMock(),
        cleanup=AsyncMock(),
    )
    captured: dict[str, object] = {}

    class DummyAgent:
        async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
            captured["astream_run_name"] = config["run_name"]
            yield {"messages": []}

    def factory(*, config):
        captured["factory_run_name"] = config["run_name"]
        return DummyAgent()

    await run_agent(
        bridge,
        run_manager,
        record,
        ctx=RunContext(checkpointer=None),
        agent_factory=factory,
        graph_input={},
        config={},
    )

    assert captured["factory_run_name"] == "lead_agent"
    assert captured["astream_run_name"] == "lead_agent"


@pytest.mark.anyio
async def test_run_agent_defaults_root_run_name_from_context_agent_name():
    run_manager = RunManager()
    record = await run_manager.create("thread-1", assistant_id="lead_agent")
    bridge = SimpleNamespace(
        publish=AsyncMock(),
        publish_end=AsyncMock(),
        cleanup=AsyncMock(),
    )
    captured: dict[str, object] = {}

    class DummyAgent:
        async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
            captured["astream_run_name"] = config["run_name"]
            yield {"messages": []}

    def factory(*, config):
        captured["factory_run_name"] = config["run_name"]
        return DummyAgent()

    await run_agent(
        bridge,
        run_manager,
        record,
        ctx=RunContext(checkpointer=None),
        agent_factory=factory,
        graph_input={},
        config={"context": {"agent_name": "finalis"}},
    )

    assert captured["factory_run_name"] == "finalis"
    assert captured["astream_run_name"] == "finalis"


@pytest.mark.anyio
async def test_run_agent_defaults_root_run_name_from_configurable_agent_name():
    run_manager = RunManager()
    record = await run_manager.create("thread-1", assistant_id="lead_agent")
    bridge = SimpleNamespace(
        publish=AsyncMock(),
        publish_end=AsyncMock(),
        cleanup=AsyncMock(),
    )
    captured: dict[str, object] = {}

    class DummyAgent:
        async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
            captured["astream_run_name"] = config["run_name"]
            yield {"messages": []}

    def factory(*, config):
        captured["factory_run_name"] = config["run_name"]
        return DummyAgent()

    await run_agent(
        bridge,
        run_manager,
        record,
        ctx=RunContext(checkpointer=None),
        agent_factory=factory,
        graph_input={},
        config={"configurable": {"agent_name": "finalis"}},
    )

    assert captured["factory_run_name"] == "finalis"
    assert captured["astream_run_name"] == "finalis"


@pytest.mark.anyio
async def test_rollback_restores_snapshot_without_deleting_thread(monkeypatch):
    checkpointer = _RollbackFakeCheckpointer()
    restored_config = {"configurable": {"thread_id": "thread-1", "checkpoint_ns": "", "checkpoint_id": "restored-1"}}
    mock_graph = _stub_mutation_graph(monkeypatch, restored_config=restored_config)
    rollback_point = _make_rollback_point(
        pending_writes=[
            ("task-a", "messages", {"content": "first"}),
            ("task-a", "status", "done"),
            ("task-b", "events", {"type": "tool"}),
        ],
    )

    completed = await _rollback_to_pre_run_checkpoint(
        accessor=_rollback_accessor(checkpointer),
        checkpointer=checkpointer,
        thread_id="thread-1",
        run_id="run-1",
        rollback_point=rollback_point,
        snapshot_capture_failed=False,
    )

    assert completed is True
    # The thread is restored, not deleted.
    checkpointer.adelete_thread.assert_not_awaited()
    # Full mode forks the pre-run checkpoint: the captured messages overwrite
    # the forked head via the rollback_restore mutation node.
    mock_graph.aupdate_state.assert_awaited_once()
    update_config, update_values = mock_graph.aupdate_state.await_args.args[:2]
    assert update_config["configurable"]["checkpoint_id"] == "ckpt_1"
    assert update_config["configurable"]["thread_id"] == "thread-1"
    from langgraph.types import Overwrite

    overwrite = update_values["messages"]
    assert isinstance(overwrite, Overwrite)
    assert overwrite.value == ["before"]
    assert mock_graph.aupdate_state.await_args.kwargs["as_node"] == "rollback_restore"
    # Pending writes are re-applied grouped by task id onto the restored head.
    assert checkpointer.aput_writes.await_args_list == [
        call(restored_config, [("messages", {"content": "first"}), ("status", "done")], task_id="task-a"),
        call(restored_config, [("events", {"type": "tool"})], task_id="task-b"),
    ]


@pytest.mark.anyio
async def test_rollback_restored_checkpoint_becomes_latest_with_real_checkpointer(monkeypatch):
    """The restored head is a real checkpoint on a real checkpointer, and the
    pre-run pending writes become attached to it while the cancelled run's
    writes stay behind on the abandoned head."""
    checkpointer = InMemorySaver()
    thread_config = {"configurable": {"thread_id": "thread-1", "checkpoint_ns": ""}}
    before_id, after_id = uuid4().hex, uuid4().hex
    before_config = checkpointer.put(thread_config, _make_checkpoint(before_id, ["before"]), {}, {})
    after_config = checkpointer.put(before_config, _make_checkpoint(after_id, ["after"]), {}, {})
    checkpointer.put_writes(after_config, [("messages", "pending-after")], task_id="task-after")

    # The stubbed mutation graph's materialized effect: a fresh fork-head
    # checkpoint carrying the pre-run messages, created through the real
    # checkpointer.
    restored_id = uuid4().hex
    restored_config = checkpointer.put(
        {"configurable": {"thread_id": "thread-1", "checkpoint_ns": "", "checkpoint_id": before_id}},
        _make_checkpoint(restored_id, ["before"]),
        {},
        {},
    )
    mock_graph = SimpleNamespace()
    mock_graph.aupdate_state = AsyncMock(return_value=restored_config)
    monkeypatch.setattr("deerflow.runtime.runs.worker.build_state_mutation_graph", lambda *args, **kwargs: mock_graph)

    completed = await _rollback_to_pre_run_checkpoint(
        accessor=_rollback_accessor(checkpointer),
        checkpointer=checkpointer,
        thread_id="thread-1",
        run_id="run-1",
        rollback_point=_make_rollback_point(
            checkpoint_id=before_id,
            pending_writes=[("task-before", "messages", "pending-before")],
        ),
        snapshot_capture_failed=False,
    )

    assert completed is True
    assert restored_id not in {before_id, after_id}
    restored_tuple = checkpointer.get_tuple(restored_config)
    assert restored_tuple is not None
    assert ("task-before", "messages", "pending-before") in restored_tuple.pending_writes
    # The cancelled run's pending writes stay on the abandoned head.
    after_tuple = checkpointer.get_tuple(after_config)
    assert ("task-after", "messages", "pending-after") in after_tuple.pending_writes
    assert ("task-before", "messages", "pending-before") not in after_tuple.pending_writes


@pytest.mark.anyio
async def test_rollback_deletes_thread_when_no_snapshot_exists():
    checkpointer = _RollbackFakeCheckpointer()

    completed = await _rollback_to_pre_run_checkpoint(
        accessor=_rollback_accessor(checkpointer),
        checkpointer=checkpointer,
        thread_id="thread-1",
        run_id="run-1",
        rollback_point=None,
        snapshot_capture_failed=False,
    )

    assert completed is True
    checkpointer.adelete_thread.assert_awaited_once_with("thread-1")
    checkpointer.aput_writes.assert_not_awaited()


@pytest.mark.anyio
async def test_rollback_skips_when_restore_config_has_no_checkpoint_id(monkeypatch):
    """Upstream fail-closed semantics: a rollback point without a checkpoint id
    skips the restore (returns False) instead of raising."""
    checkpointer = _RollbackFakeCheckpointer()
    mock_graph = _stub_mutation_graph(monkeypatch, restored_config={"configurable": {"thread_id": "thread-1", "checkpoint_ns": ""}})

    completed = await _rollback_to_pre_run_checkpoint(
        accessor=_rollback_accessor(checkpointer),
        checkpointer=checkpointer,
        thread_id="thread-1",
        run_id="run-1",
        rollback_point=_make_rollback_point(checkpoint_id=None),
        snapshot_capture_failed=False,
    )

    assert completed is False
    checkpointer.adelete_thread.assert_not_awaited()
    mock_graph.aupdate_state.assert_not_awaited()
    checkpointer.aput_writes.assert_not_awaited()


@pytest.mark.anyio
async def test_capture_rollback_point_normalizes_checkpoint_ns_to_root():
    """_capture_rollback_point normalizes a falsy checkpoint_ns to the root
    namespace so the restore lands on the thread's root checkpoint."""
    checkpointer = InMemorySaver()
    thread_config = {"configurable": {"thread_id": "thread-1", "checkpoint_ns": ""}}
    checkpoint_id = uuid4().hex
    checkpointer.put(thread_config, _make_checkpoint(checkpoint_id, ["before"]), {}, {})

    accessor = CheckpointStateAccessor.bind(build_state_mutation_graph("rollback_restore", "full"), checkpointer, mode="full")
    rollback_point = await _capture_rollback_point(accessor, checkpointer, thread_config)

    assert rollback_point is not None
    assert rollback_point.config["configurable"]["checkpoint_ns"] == ""
    assert rollback_point.config["configurable"]["checkpoint_id"] == checkpoint_id


@pytest.mark.anyio
async def test_rollback_raises_on_malformed_pending_write_not_a_tuple(monkeypatch):
    """pending_writes containing a non-3-tuple item should raise RuntimeError."""
    checkpointer = _RollbackFakeCheckpointer()
    _stub_mutation_graph(monkeypatch, restored_config={"configurable": {"thread_id": "thread-1", "checkpoint_ns": "", "checkpoint_id": "restored-1"}})

    with pytest.raises(RuntimeError, match="rollback failed: pending_write is not a 3-tuple"):
        await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(checkpointer),
            checkpointer=checkpointer,
            thread_id="thread-1",
            run_id="run-1",
            rollback_point=_make_rollback_point(
                pending_writes=[
                    ("task-a", "messages", "valid"),
                    ["only", "two"],  # malformed: only 2 elements
                ],
            ),
            snapshot_capture_failed=False,
        )

    # The restore succeeded but aput_writes must not run with malformed data.
    checkpointer.aput_writes.assert_not_awaited()


@pytest.mark.anyio
async def test_rollback_raises_on_malformed_pending_write_non_string_channel(monkeypatch):
    """pending_writes containing a non-string channel should raise RuntimeError."""
    checkpointer = _RollbackFakeCheckpointer()
    _stub_mutation_graph(monkeypatch, restored_config={"configurable": {"thread_id": "thread-1", "checkpoint_ns": "", "checkpoint_id": "restored-1"}})

    with pytest.raises(RuntimeError, match="rollback failed: pending_write has non-string channel"):
        await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(checkpointer),
            checkpointer=checkpointer,
            thread_id="thread-1",
            run_id="run-1",
            rollback_point=_make_rollback_point(
                pending_writes=[
                    ("task-a", 123, "value"),  # malformed: channel is not a string
                ],
            ),
            snapshot_capture_failed=False,
        )

    checkpointer.aput_writes.assert_not_awaited()


@pytest.mark.anyio
async def test_rollback_propagates_aput_writes_failure(monkeypatch):
    """If aput_writes fails, the exception should propagate (not be swallowed)."""
    checkpointer = _RollbackFakeCheckpointer()
    checkpointer.aput_writes.side_effect = RuntimeError("Database connection lost")
    _stub_mutation_graph(monkeypatch, restored_config={"configurable": {"thread_id": "thread-1", "checkpoint_ns": "", "checkpoint_id": "restored-1"}})

    with pytest.raises(RuntimeError, match="Database connection lost"):
        await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(checkpointer),
            checkpointer=checkpointer,
            thread_id="thread-1",
            run_id="run-1",
            rollback_point=_make_rollback_point(
                pending_writes=[
                    ("task-a", "messages", "value"),
                ],
            ),
            snapshot_capture_failed=False,
        )

    # The restore succeeded and aput_writes was attempted but failed.
    checkpointer.aput_writes.assert_awaited_once()


def test_agent_factory_supports_app_config_detects_supported_signature():
    def factory(*, config, app_config=None):
        return (config, app_config)

    assert _agent_factory_supports_app_config(factory) is True


def test_build_runtime_context_defaults_to_thread_and_run_id():
    ctx = _build_runtime_context("thread-1", "run-1", None)
    assert ctx == {"thread_id": "thread-1", "run_id": "run-1"}


def test_build_runtime_context_merges_caller_context():
    """Regression for issue #2677: keys from ``config['context']`` (e.g. ``agent_name``)
    must be merged into the Runtime's context so that ``ToolRuntime.context`` — which
    is what ``setup_agent`` reads — can see them."""
    caller_context = {"agent_name": "my-agent", "is_bootstrap": True, "model_name": "gpt-4"}

    ctx = _build_runtime_context("thread-1", "run-1", caller_context)

    assert ctx["thread_id"] == "thread-1"
    assert ctx["run_id"] == "run-1"
    assert ctx["agent_name"] == "my-agent"
    assert ctx["is_bootstrap"] is True
    assert ctx["model_name"] == "gpt-4"


def test_build_runtime_context_caller_cannot_override_thread_id_or_run_id():
    """A malicious or buggy caller must not be able to overwrite the worker-assigned
    ``thread_id`` / ``run_id`` by stuffing them into ``config['context']``."""
    caller_context = {"thread_id": "spoofed", "run_id": "spoofed", "agent_name": "ok"}

    ctx = _build_runtime_context("real-thread", "real-run", caller_context)

    assert ctx["thread_id"] == "real-thread"
    assert ctx["run_id"] == "real-run"
    assert ctx["agent_name"] == "ok"


def test_build_runtime_context_ignores_non_dict_caller_context():
    ctx = _build_runtime_context("thread-1", "run-1", "not-a-dict")
    assert ctx == {"thread_id": "thread-1", "run_id": "run-1"}


def test_agent_factory_supports_app_config_returns_false_when_signature_lookup_fails(monkeypatch):
    class BrokenCallable:
        def __call__(self, **kwargs):
            return kwargs

    monkeypatch.setattr("deerflow.runtime.runs.worker.inspect.signature", lambda _obj: (_ for _ in ()).throw(ValueError("boom")))

    assert _agent_factory_supports_app_config(BrokenCallable()) is False
