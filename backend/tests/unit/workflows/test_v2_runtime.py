from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from ideer.workflows.v2.adapters import ActionAdapterRegistry, ActionResolutionError
from ideer.workflows.v2.compiler import WorkflowCancelled, WorkflowGraphCompiler
from ideer.workflows.v2.parser import parse_workflow_v2


def test_registry_resolves_adapter_again_for_each_run() -> None:
    registry = ActionAdapterRegistry()
    calls: list[str] = []

    class Adapter:
        async def run(self, context, params):
            calls.append(context.idempotency_key)
            return {"ok": True}

    registry.register("tool", "echo", Adapter())
    assert registry.resolve("tool", "echo") is registry.resolve("tool", "echo")
    assert calls == []
    with pytest.raises(ActionResolutionError, match="unknown tool adapter 'missing'"):
        registry.resolve("tool", "missing")


@pytest.mark.asyncio
async def test_compiler_runs_action_and_writes_structured_output() -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: hello
inputs: {}
state: {}
entrypoint: hello
nodes:
  - id: hello
    type: action
    action:
      kind: tool
      name: echo
edges: []
"""
    )

    class Adapter:
        async def run(self, context, params):
            return {"message": "done"}

    graph = WorkflowGraphCompiler(definition, ActionAdapterRegistry({("tool", "echo"): Adapter()})).compile()
    result = await graph.ainvoke({"inputs": {}, "state": {}, "outputs": {}}, config={"configurable": {"thread_id": "wf:test"}})

    assert result["outputs"]["hello"] == {"message": "done"}


@pytest.mark.asyncio
async def test_compiler_retries_only_when_explicitly_configured() -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: retry
inputs: {}
state: {}
entrypoint: task
nodes:
  - id: task
    type: action
    retry: {max_attempts: 2}
    action: {kind: tool, name: flaky}
edges: []
"""
    )
    attempts = 0

    class Adapter:
        async def run(self, context, params):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("transient")
            return "ok"

    graph = WorkflowGraphCompiler(definition, ActionAdapterRegistry({("tool", "flaky"): Adapter()})).compile()
    result = await graph.ainvoke({"inputs": {}, "state": {}, "outputs": {}}, config={"configurable": {"thread_id": "wf:retry"}})
    assert result["outputs"]["task"] == "ok"
    assert attempts == 2


@pytest.mark.asyncio
async def test_compiler_applies_declared_state_write_without_overwriting_other_state() -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: state-write
inputs: {}
state: {left: {type: integer}, right: {type: integer}}
entrypoint: left
nodes:
  - id: left
    type: action
    action: {kind: tool, name: left}
    writes: [$.state.left]
  - id: right
    type: action
    action: {kind: tool, name: right}
    writes: [$.state.right]
edges: [{from: left, to: right}]
"""
    )

    class Adapter:
        async def run(self, context, params):
            return 1 if context.node_id == "left" else 2

    graph = WorkflowGraphCompiler(definition, ActionAdapterRegistry({("tool", "left"): Adapter(), ("tool", "right"): Adapter()})).compile()
    result = await graph.ainvoke({"inputs": {}, "state": {}, "outputs": {}}, config={"configurable": {"thread_id": "wf:state"}})

    assert result["state"] == {"left": 1, "right": 2}


def test_route_expression_rejects_calls_and_attribute_access() -> None:
    with pytest.raises(ValueError, match="unsupported syntax"):
        parse_workflow_v2(
            """
schema_version: 2
name: unsafe
inputs: {}
state: {flag: {type: boolean}}
entrypoint: route
nodes:
  - id: route
    type: route
    expression: "$.state.flag.__class__"
  - id: safe
    type: interrupt
    roles: [user]
  - id: other
    type: interrupt
    roles: [user]
edges: [{from: route, to: safe}, {from: route, to: other}]
"""
        )


@pytest.mark.asyncio
async def test_compiler_waits_for_all_fork_branches_before_join() -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: parallel
inputs: {}
state: {}
entrypoint: fork
nodes:
  - id: fork
    type: fork
    branches: [left, right]
    join: join
  - id: left
    type: action
    action: {kind: tool, name: branch}
  - id: right
    type: action
    action: {kind: tool, name: branch}
  - id: join
    type: join
    fork: fork
    
edges:
  - {from: fork, to: left}
  - {from: fork, to: right}
  - {from: left, to: join}
  - {from: right, to: join}
"""
    )
    seen: list[str] = []

    class Adapter:
        async def run(self, context, params):
            seen.append(context.node_id)
            return context.node_id

    graph = WorkflowGraphCompiler(definition, ActionAdapterRegistry({("tool", "branch"): Adapter()})).compile()
    result = await graph.ainvoke({"inputs": {}, "state": {}, "outputs": {}}, config={"configurable": {"thread_id": "wf:parallel"}})

    assert set(seen) == {"left", "right"}
    assert set(result["outputs"]) == {"left", "right"}


@pytest.mark.asyncio
async def test_compiler_emits_action_lifecycle_events_with_idempotency_key() -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: lifecycle
inputs: {}
state: {}
entrypoint: task
nodes:
  - id: task
    type: action
    action: {kind: tool, name: echo}
edges: []
"""
    )
    events: list[tuple[str, dict]] = []

    class Adapter:
        async def run(self, context, params):
            return {"ok": True}

    async def emit(event_type: str, payload: dict) -> None:
        events.append((event_type, payload))

    graph = WorkflowGraphCompiler(
        definition,
        ActionAdapterRegistry({("tool", "echo"): Adapter()}),
        emit_event=emit,
    ).compile()
    await graph.ainvoke({"run_id": "run-1", "inputs": {}, "state": {}, "outputs": {}}, config={"configurable": {"thread_id": "wf:lifecycle"}})

    assert [event_type for event_type, _ in events] == ["node_started", "node_completed"]
    assert events[1][1]["idempotency_key"] == "wf:run-1:node:task"


@pytest.mark.asyncio
async def test_compiler_stops_at_node_boundary_when_cancel_requested() -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: cancel
inputs: {}
state: {}
entrypoint: first
nodes:
  - id: first
    type: action
    action: {kind: tool, name: echo}
  - id: second
    type: action
    action: {kind: tool, name: echo}
edges: [{from: first, to: second}]
"""
    )
    calls: list[str] = []

    class Adapter:
        async def run(self, context, params):
            calls.append(context.node_id)
            return context.node_id

    async def is_cancelled() -> bool:
        return bool(calls)

    graph = WorkflowGraphCompiler(
        definition,
        ActionAdapterRegistry({("tool", "echo"): Adapter()}),
        is_cancelled=is_cancelled,
    ).compile()

    with pytest.raises(WorkflowCancelled, match="cancelled"):
        await graph.ainvoke({"run_id": "run-1", "inputs": {}, "state": {}, "outputs": {}}, config={"configurable": {"thread_id": "wf:cancel"}})
    assert calls == ["first"]


@pytest.mark.asyncio
async def test_compiler_interrupts_and_resumes_from_checkpoint_without_repeating_prior_action() -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: approval
inputs: {}
state: {}
entrypoint: prepare
nodes:
  - id: prepare
    type: action
    action: {kind: tool, name: prepare}
  - id: review
    type: interrupt
    roles: [admin]
  - id: finish
    type: action
    action: {kind: tool, name: finish}
edges:
  - {from: prepare, to: review}
  - {from: review, to: finish}
"""
    )
    calls: list[str] = []

    class Adapter:
        async def run(self, context, params):
            calls.append(context.node_id)
            return context.node_id

    graph = WorkflowGraphCompiler(
        definition,
        ActionAdapterRegistry({("tool", "prepare"): Adapter(), ("tool", "finish"): Adapter()}),
    ).compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "wf:approval"}}
    paused = await graph.ainvoke({"run_id": "run-1", "inputs": {}, "state": {}, "outputs": {}}, config=config)

    assert paused["__interrupt__"]
    assert calls == ["prepare"]

    completed = await graph.ainvoke(Command(resume={"approved": True}), config=config)

    assert completed["outputs"]["finish"] == "finish"
    assert calls == ["prepare", "finish"]
