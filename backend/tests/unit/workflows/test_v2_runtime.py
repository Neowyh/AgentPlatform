from __future__ import annotations

import asyncio

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from ideer.workflows.v2.adapters import ActionAdapterRegistry, ActionResolutionError
from ideer.workflows.v2.compiler import WorkflowCancelled, WorkflowGraphCompiler, WorkflowNodeFailed, WorkflowNodeTimeout
from ideer.workflows.v2.file_roots import workflow_state_root
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
async def test_compiler_renders_agent_file_access_into_action_context() -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: scoped
inputs:
  upload_dir: {type: string}
  output_base_dir: {type: string}
state: {}
entrypoint: collect
nodes:
  - id: collect
    type: action
    action:
      kind: agent
      name: scoped-agent
      file_access:
        read: ["{{inputs.upload_dir}}"]
        write: ["{{inputs.output_base_dir}}/artifacts/evidence"]
edges: []
"""
    )
    captured = None

    class Adapter:
        async def run(self, context, params):
            nonlocal captured
            captured = context.file_access
            return "ok"

    graph = WorkflowGraphCompiler(
        definition,
        ActionAdapterRegistry({("agent", "scoped-agent"): Adapter()}),
    ).compile()
    await graph.ainvoke(
        {
            "inputs": {"upload_dir": "/inputs/case", "output_base_dir": "/outputs/run"},
            "state": {},
            "outputs": {},
        },
        config={"configurable": {"thread_id": "wf:scoped"}},
    )

    assert captured == {
        "read": ["/inputs/case", workflow_state_root()],
        "write": ["/outputs/run/artifacts/evidence"],
    }


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
async def test_compiler_materializes_state_to_workspace_and_extends_read_roots(tmp_path) -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: handoff
inputs: {}
state: {findings: {type: string}}
entrypoint: produce
nodes:
  - id: produce
    type: action
    action: {kind: tool, name: produce}
    writes: [$.state.findings]
  - id: consume
    type: action
    action:
      kind: agent
      name: consume
      file_access:
        read: ["/mnt/user-data/outputs/artifacts/"]
        write: []
      params:
        prompt: |
          读取 {{state_files.findings}}
edges: [{from: produce, to: consume}]
"""
    )
    state_root = workflow_state_root()
    state_file_host = tmp_path / "runs" / "run-1" / ".workflow" / "state" / "findings.md"

    def resolver(p: str) -> str | None:
        if p == state_root or p.startswith(f"{state_root}/"):
            return str(state_file_host if p.endswith("findings.md") else tmp_path / "runs" / "run-1" / ".workflow" / "state")
        return None

    captured: dict = {}

    class Adapter:
        async def run(self, context, params):
            captured[context.node_id] = (params, context.file_access)
            return "findings report" if context.node_id == "produce" else "done"

    graph = WorkflowGraphCompiler(
        definition,
        ActionAdapterRegistry({("tool", "produce"): Adapter(), ("agent", "consume"): Adapter()}),
        artifact_resolver=resolver,
    ).compile()
    result = await graph.ainvoke({"run_id": "run-1", "inputs": {}, "state": {}, "outputs": {}}, config={"configurable": {"thread_id": "wf:handoff"}})

    assert state_file_host.read_text(encoding="utf-8") == "findings report"
    assert result["state"]["findings"] == "findings report"

    consume_params, consume_access = captured["consume"]
    assert "读取 /mnt/user-data/workspace/.workflow/state/findings.md" in consume_params["prompt"]
    assert consume_access["read"] == ["/mnt/user-data/outputs/artifacts/", workflow_state_root()]


@pytest.mark.asyncio
async def test_compiler_materializes_structured_state_as_json(tmp_path) -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: json-state
inputs: {}
state: {payload: {type: object}}
entrypoint: emit
nodes:
  - id: emit
    type: action
    action: {kind: tool, name: emit}
    writes: [$.state.payload]
edges: []
"""
    )
    state_file_host = tmp_path / "runs" / "run-1" / ".workflow" / "state" / "payload.json"

    def resolver(p: str) -> str | None:
        return str(state_file_host) if p.endswith("payload.json") else None

    class Adapter:
        async def run(self, context, params):
            return {"a": 1}

    graph = WorkflowGraphCompiler(
        definition,
        ActionAdapterRegistry({("tool", "emit"): Adapter()}),
        artifact_resolver=resolver,
    ).compile()
    await graph.ainvoke({"run_id": "run-1", "inputs": {}, "state": {}, "outputs": {}}, config={"configurable": {"thread_id": "wf:json-state"}})

    assert state_file_host.read_text(encoding="utf-8") == '{\n  "a": 1\n}'


@pytest.mark.asyncio
async def test_compiler_fails_node_on_failed_marker_and_retries() -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: failed
inputs: {}
state: {task: {type: string}}
entrypoint: task
nodes:
  - id: task
    type: action
    retry: {max_attempts: 2}
    action: {kind: tool, name: flaky}
    writes: [$.state.task]
edges: []
"""
    )
    attempts = 0
    events: list[tuple[str, dict]] = []

    class Adapter:
        async def run(self, context, params):
            nonlocal attempts
            attempts += 1
            return "FAILED: 无法读取证据文件"

    async def emit(event_type: str, payload: dict) -> None:
        events.append((event_type, payload))

    graph = WorkflowGraphCompiler(
        definition,
        ActionAdapterRegistry({("tool", "flaky"): Adapter()}),
        emit_event=emit,
    ).compile()

    with pytest.raises(WorkflowNodeFailed, match="reported failure"):
        await graph.ainvoke({"run_id": "run-1", "inputs": {}, "state": {}, "outputs": {}}, config={"configurable": {"thread_id": "wf:failed"}})

    assert attempts == 2
    assert ("node_failed", {"node_id": "task", "idempotency_key": "wf:run-1:node:task", "error": "node 'task' reported failure: FAILED: 无法读取证据文件"}) in events


@pytest.mark.asyncio
async def test_compiler_accepts_result_after_transient_failed_marker() -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: recover
inputs: {}
state: {task: {type: string}}
entrypoint: task
nodes:
  - id: task
    type: action
    retry: {max_attempts: 2}
    action: {kind: tool, name: flaky}
    writes: [$.state.task]
edges: []
"""
    )
    attempts = 0

    class Adapter:
        async def run(self, context, params):
            nonlocal attempts
            attempts += 1
            return "FAILED: 临时问题" if attempts == 1 else "ok"

    graph = WorkflowGraphCompiler(definition, ActionAdapterRegistry({("tool", "flaky"): Adapter()})).compile()
    result = await graph.ainvoke({"run_id": "run-1", "inputs": {}, "state": {}, "outputs": {}}, config={"configurable": {"thread_id": "wf:recover"}})

    assert result["state"]["task"] == "ok"
    assert attempts == 2


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
async def test_compiler_routes_join_to_next_node() -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: parallel-next
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
  - id: next
    type: action
    action: {kind: tool, name: branch}
edges:
  - {from: fork, to: left}
  - {from: fork, to: right}
  - {from: left, to: join}
  - {from: right, to: join}
  - {from: join, to: next}
"""
    )
    seen: list[str] = []

    class Adapter:
        async def run(self, context, params):
            seen.append(context.node_id)
            return context.node_id

    graph = WorkflowGraphCompiler(definition, ActionAdapterRegistry({("tool", "branch"): Adapter()})).compile()
    result = await graph.ainvoke({"inputs": {}, "state": {}, "outputs": {}}, config={"configurable": {"thread_id": "wf:parallel-next"}})

    assert seen == ["left", "right", "next"]
    assert set(result["outputs"]) == {"left", "right", "next"}


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
async def test_compiler_persists_platform_token_and_progress_events() -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: streaming
inputs: {}
state: {}
entrypoint: task
nodes:
  - id: task
    type: action
    action: {kind: agent, name: stream}
edges: []
"""
    )
    events: list[tuple[str, dict]] = []

    class Adapter:
        async def run(self, context, params):
            raise AssertionError("streaming adapters must use astream")

        async def astream(self, context, params):
            yield {"type": "token", "text": "hello"}
            yield {"type": "progress", "message": "working"}
            yield {"type": "result", "value": {"ok": True}}

    async def emit(event_type: str, payload: dict) -> None:
        events.append((event_type, payload))

    graph = WorkflowGraphCompiler(
        definition,
        ActionAdapterRegistry({("agent", "stream"): Adapter()}),
        emit_event=emit,
    ).compile()
    result = await graph.ainvoke(
        {"run_id": "run-1", "inputs": {}, "state": {}, "outputs": {}},
        config={"configurable": {"thread_id": "wf:streaming"}},
    )

    assert [event_type for event_type, _ in events] == [
        "node_started",
        "action_token",
        "action_progress",
        "node_completed",
    ]
    assert events[1][1]["text"] == "hello"
    assert result["outputs"]["task"] == {"ok": True}


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
async def test_compiler_fails_node_when_action_exceeds_configured_timeout() -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: timeout
inputs: {}
state: {}
entrypoint: wait
nodes:
  - id: wait
    type: action
    action: {kind: tool, name: slow}
edges: []
"""
    )

    class Adapter:
        async def run(self, context, params):
            await asyncio.sleep(1)

    graph = WorkflowGraphCompiler(
        definition,
        ActionAdapterRegistry({("tool", "slow"): Adapter()}),
        node_timeout_seconds=0.01,
    ).compile()

    with pytest.raises(WorkflowNodeTimeout, match="workflow_node_timeout"):
        await graph.ainvoke({"run_id": "run-1", "inputs": {}, "state": {}, "outputs": {}}, config={"configurable": {"thread_id": "wf:timeout"}})


@pytest.mark.asyncio
async def test_compiler_stops_a_declared_back_edge_at_its_iteration_limit() -> None:
    definition = parse_workflow_v2(
        """
schema_version: 2
name: bounded-loop
inputs: {}
state: {}
entrypoint: first
nodes:
  - id: first
    type: action
    action: {kind: tool, name: record}
  - id: second
    type: action
    action: {kind: tool, name: record}
edges:
  - {from: first, to: second, max_iterations: 10}
  - {from: second, to: first, max_iterations: 1}
"""
    )
    calls: list[str] = []
    events: list[tuple[str, dict]] = []

    class Adapter:
        async def run(self, context, params):
            calls.append(context.node_id)
            return context.node_id

    async def emit(event_type: str, payload: dict) -> None:
        events.append((event_type, payload))

    from ideer.workflows.v2.compiler import WorkflowIterationLimit

    graph = WorkflowGraphCompiler(
        definition,
        ActionAdapterRegistry({("tool", "record"): Adapter()}),
        emit_event=emit,
    ).compile()

    with pytest.raises(WorkflowIterationLimit, match="workflow_iteration_limit_exceeded"):
        await graph.ainvoke({"run_id": "run-1", "inputs": {}, "state": {}, "outputs": {}}, config={"configurable": {"thread_id": "wf:bounded-loop"}})

    assert calls == ["first", "second", "first", "second"]
    assert events[-1] == ("node_failed", {"node_id": "second", "error": "workflow_iteration_limit_exceeded"})


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
