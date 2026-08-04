"""Compile the constrained workflow graph into a LangGraph StateGraph."""

from __future__ import annotations

import ast
import asyncio
import operator
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict

from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .adapters import ActionAdapterRegistry, ActionContext
from .file_roots import lookup_path, materialize_state, missing_written_artifacts, render_template, workflow_state_path, workflow_state_root
from .schema import EdgeV2, NodeV2, WorkflowV2


class WorkflowCancelled(RuntimeError):
    """Raised when a queued cancellation is observed at a node boundary."""


class WorkflowNodeTimeout(RuntimeError):
    """Raised when a node exceeds the configured execution limit."""


class WorkflowIterationLimit(RuntimeError):
    """Raised when a declared workflow back-edge exceeds its bound."""


class WorkflowNodeFailed(RuntimeError):
    """Raised when a node's response declares failure via the ``FAILED:`` marker."""


class WorkflowTransientError(RuntimeError):
    """Raised when a node action failed for a transient provider/network reason.

    Transient errors are retried with a dedicated backoff budget (independent of the
    node's retry policy) and then interrupt the run as ``paused`` instead of failing it,
    so an operator can resume once the provider recovers.
    """


class ArtifactsMissing(RuntimeError):
    """Raised when a node's declared write roots produced no usable data."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"artifacts_missing: {', '.join(missing)}")


# Transient provider/network failures are retried with a dedicated backoff
# budget before the run is interrupted as ``paused``. These are module-level
# so tests can shrink the schedule without touching node retry policies.
_TRANSIENT_MAX_ATTEMPTS = 3
_TRANSIENT_BACKOFF_BASE_SECONDS = 30.0


def _merge_maps(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class _GraphState(TypedDict, total=False):
    run_id: str
    inputs: dict[str, Any]
    state: Annotated[dict[str, Any], _merge_maps]
    outputs: Annotated[dict[str, Any], _merge_maps]
    edge_iterations: Annotated[dict[str, int], _merge_maps]


class WorkflowGraphCompiler:
    def __init__(
        self,
        definition: WorkflowV2,
        adapters: ActionAdapterRegistry,
        emit_event: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None,
        is_cancelled: Callable[[], Awaitable[bool]] | None = None,
        node_timeout_seconds: float | None = None,
        artifact_resolver: Callable[[str], str | None] | None = None,
    ) -> None:
        self.definition = definition
        self.adapters = adapters
        self.emit_event = emit_event
        self.is_cancelled = is_cancelled
        self.node_timeout_seconds = node_timeout_seconds
        self.artifact_resolver = artifact_resolver

    def compile(self, *, checkpointer: Any = None) -> Any:
        graph = StateGraph(_GraphState)
        outgoing: dict[str, list[str]] = {node.id: [] for node in self.definition.nodes}
        for edge in self.definition.edges:
            outgoing[edge.from_].append(edge.to)
        loop_edges = {(edge.from_, edge.to): edge for edge in self.definition.edges if self._has_path(edge.to, edge.from_, outgoing)}
        edge_targets = {key: f"__loop_gate__{edge.from_}__{edge.to}" for key, edge in loop_edges.items()}
        for node in self.definition.nodes:
            graph.add_node(node.id, self._node_handler(node))
        for key, edge in loop_edges.items():
            graph.add_node(edge_targets[key], self._loop_gate(edge))
        graph.add_edge(START, self.definition.entrypoint)

        def target_for(source: str, target: str) -> str:
            return edge_targets.get((source, target), target)

        incoming: dict[str, list[str]] = {node.id: [] for node in self.definition.nodes}
        for source, targets in outgoing.items():
            for target in targets:
                incoming[target].append(source)
        for node in self.definition.nodes:
            targets = outgoing[node.id]
            if node.type == "fork":
                for target in targets:
                    graph.add_edge(node.id, target_for(node.id, target))
            elif node.type == "join":
                branches = [source for source in incoming[node.id] if source in (self._node(node.fork).branches if node.fork else [])]
                if branches:
                    if not any((source, node.id) in edge_targets for source in branches):
                        graph.add_edge(branches, node.id)
                    else:
                        gated_branches = [target_for(source, node.id) for source in branches]
                        for source, gated in zip(branches, gated_branches, strict=True):
                            if gated != source:
                                graph.add_edge(source, gated)
                        graph.add_edge(gated_branches, node.id)
                else:
                    graph.add_edge(node.id, END)
                for target in targets:
                    graph.add_edge(node.id, target_for(node.id, target))
            elif node.type == "route":
                graph.add_conditional_edges(
                    node.id,
                    self._route_selector(node, targets, {target: target_for(node.id, target) for target in targets}),
                    [target_for(node.id, target) for target in targets],
                )
            elif targets:
                target = targets[0]
                if not (self._node(target).type == "join" and node.id in incoming[target]):
                    graph.add_edge(node.id, target_for(node.id, target))
            else:
                graph.add_edge(node.id, END)
        for (source, target), gate in edge_targets.items():
            graph.add_edge(gate, target)
        return graph.compile(checkpointer=checkpointer)

    @staticmethod
    def _has_path(start: str, target: str, outgoing: dict[str, list[str]]) -> bool:
        pending = [start]
        seen: set[str] = set()
        while pending:
            node = pending.pop()
            if node == target:
                return True
            if node not in seen:
                seen.add(node)
                pending.extend(outgoing[node])
        return False

    def _loop_gate(self, edge: EdgeV2):
        key = f"{edge.from_}->{edge.to}"

        async def run(state: dict[str, Any]) -> dict[str, Any]:
            count = int(state.get("edge_iterations", {}).get(key, 0)) + 1
            if count > edge.max_iterations:  # parser guarantees this for cycle edges
                await self._emit("node_failed", {"node_id": edge.from_, "error": "workflow_iteration_limit_exceeded"})
                raise WorkflowIterationLimit("workflow_iteration_limit_exceeded")
            return {"edge_iterations": {key: count}}

        return run

    def _node_handler(self, node: NodeV2):
        async def run(state: dict[str, Any]) -> dict[str, Any]:
            if self.is_cancelled is not None and await self.is_cancelled():
                raise WorkflowCancelled(f"workflow cancelled before node '{node.id}'")
            if node.type == "interrupt":
                await self._emit("node_started", {"node_id": node.id, "started_at": _now_iso()})
                return {"interrupt": interrupt({"node_id": node.id, "roles": node.roles})}
            if node.type != "action":
                return state
            context_state = dict(state.get("state", {}))
            state_files = {key: workflow_state_path(key, structured=isinstance(value, (dict, list))) for key, value in context_state.items()}
            render_state = {**state, "state_files": state_files}
            file_access = render_template(node.action.file_access.model_dump(), render_state) if node.action is not None and node.action.file_access is not None else None
            if file_access is not None:
                read_roots = file_access.setdefault("read", [])
                state_root = workflow_state_root()
                if not any(read_root == state_root for read_root in read_roots):
                    read_roots.append(state_root)
            context = ActionContext(
                workflow_name=self.definition.name,
                run_id=_run_id(state),
                node_id=node.id,
                inputs=dict(state.get("inputs", {})),
                state=context_state,
                outputs=dict(state.get("outputs", {})),
                file_access=file_access,
            )
            params = render_template(node.action.params, render_state)  # type: ignore[union-attr]
            await self._emit("node_started", {"node_id": node.id, "idempotency_key": context.idempotency_key, "started_at": _now_iso()})
            try:
                adapter = self.adapters.resolve(node.action.kind, node.action.name)  # type: ignore[union-attr]
                last_error: Exception | None = None
                result: Any = None
                transient_attempts = 0
                while True:
                    last_error = None
                    for attempt in range(node.retry.max_attempts):
                        try:
                            action = self._run_action(adapter, context, params)
                            try:
                                result = await asyncio.wait_for(action, timeout=self.node_timeout_seconds) if self.node_timeout_seconds is not None else await action
                            except TimeoutError as exc:
                                raise WorkflowNodeTimeout("workflow_node_timeout") from exc
                            if isinstance(result, str) and result.startswith("FAILED:"):
                                raise WorkflowNodeFailed(f"node '{node.id}' reported failure: {result[:200]}")
                            if self.artifact_resolver is not None and context.file_access is not None:
                                missing = missing_written_artifacts(context.file_access.get("write", []), self.artifact_resolver)
                                if missing:
                                    raise ArtifactsMissing(missing)
                            break
                        except WorkflowTransientError as exc:
                            # transient provider/network errors leave the node-retry
                            # policy and get their own backoff budget below
                            last_error = exc
                            break
                        except Exception as exc:  # retry policy is deliberately node-local
                            last_error = exc
                            if attempt + 1 < node.retry.max_attempts and node.retry.backoff_seconds:
                                await asyncio.sleep(node.retry.backoff_seconds)
                    else:
                        if isinstance(last_error, ArtifactsMissing):
                            # Two-phase interrupt so every resume re-verifies the
                            # gate: on resume the node re-runs and the first
                            # interrupt() consumes the resume value without raising,
                            # then the second interrupt() has no resume value left
                            # and raises a fresh GraphInterrupt — pausing again.
                            interrupt({"type": "artifacts_missing", "node_id": node.id, "missing": last_error.missing})
                            return {"interrupt": interrupt({"type": "artifacts_missing", "node_id": node.id, "missing": last_error.missing})}
                        raise last_error or RuntimeError(f"node '{node.id}' failed")
                    if isinstance(last_error, WorkflowTransientError):
                        transient_attempts += 1
                        if transient_attempts < _TRANSIENT_MAX_ATTEMPTS:
                            await asyncio.sleep(_TRANSIENT_BACKOFF_BASE_SECONDS * transient_attempts)
                            continue
                        # Two-phase interrupt, mirroring the artifacts_missing gate:
                        # resuming re-runs the node, which retries the action and
                        # either completes or pauses again with a fresh interrupt.
                        interrupt({"type": "transient_error", "node_id": node.id, "error": str(last_error)})
                        return {"interrupt": interrupt({"type": "transient_error", "node_id": node.id, "error": str(last_error)})}
                    break
            except GraphInterrupt:
                raise
            except Exception as exc:
                await self._emit(
                    "node_failed",
                    {"node_id": node.id, "idempotency_key": context.idempotency_key, "error": str(exc), "finished_at": _now_iso()},
                )
                raise
            await self._emit(
                "node_completed",
                {"node_id": node.id, "idempotency_key": context.idempotency_key, "result": result, "finished_at": _now_iso()},
            )
            outputs = dict(state.get("outputs", {}))
            outputs[node.id] = result
            update: dict[str, Any] = {"outputs": {node.id: result}}
            if node.writes:
                if len(node.writes) != 1:
                    raise ValueError(f"action node '{node.id}' must declare exactly one write path")
                key = _write_key(node.writes[0])
                update["state"] = {key: result}
                if self.artifact_resolver is not None:
                    materialize_state(key, result, self.artifact_resolver)
            return update

        return run

    async def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.emit_event is not None:
            await self.emit_event(event_type, payload)

    async def _run_action(self, adapter: Any, context: ActionContext, params: dict[str, Any]) -> Any:
        """Translate adapter updates into stable platform events."""
        if not hasattr(adapter, "astream"):
            return await adapter.run(context, params)
        result: Any = None
        received_result = False
        async for update in adapter.astream(context, params):
            if self.is_cancelled is not None and await self.is_cancelled():
                raise WorkflowCancelled(f"workflow cancelled during node '{context.node_id}'")
            update_type = update.get("type")
            if update_type == "token":
                await self._emit("action_token", {"node_id": context.node_id, "text": str(update.get("text", ""))})
            elif update_type == "progress":
                await self._emit("action_progress", {"node_id": context.node_id, "message": str(update.get("message", ""))})
            elif update_type == "result":
                result = update.get("value")
                received_result = True
            else:
                raise ValueError(f"unknown action update type: {update_type!r}")
        if not received_result:
            raise RuntimeError(f"streaming action '{context.node_id}' ended without a result")
        return result

    def _node(self, node_id: str) -> NodeV2:
        return next(node for node in self.definition.nodes if node.id == node_id)

    def _route_selector(self, node: NodeV2, targets: list[str], edge_targets: dict[str, str]):
        async def select(state: dict[str, Any]) -> str:
            # Route expressions are statically constrained by parser; runtime
            # evaluation is intentionally limited to the declared expression.
            expression = node.expression or ""
            if node.routes:
                for condition, target in node.routes.items():
                    if _evaluate_expression(condition, state):
                        await self._emit("edge_selected", {"node_id": node.id, "from": node.id, "to": target})
                        return edge_targets[target]
            selected = edge_targets[targets[0] if _evaluate_expression(expression, state) else targets[-1]]
            target = next(t for t in targets if edge_targets[t] == selected)
            await self._emit("edge_selected", {"node_id": node.id, "from": node.id, "to": target})
            return selected

        return select


def _run_id(state: dict[str, Any]) -> str:
    return str(state.get("run_id", "unknown"))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _write_key(path: str) -> str:
    parts = path.removeprefix("$.state.").split(".")
    if len(parts) != 1:
        raise ValueError(f"nested state write path is not supported: '{path}'")
    return parts[0]


def _evaluate_expression(expression: str, state: dict[str, Any]) -> bool:
    def replace(match: re.Match[str]) -> str:
        value = lookup_path(match.group(0), state)
        return repr(value)

    translated = re.sub(r"\$\.(?:inputs|state|outputs)(?:\.[A-Za-z_][A-Za-z0-9_]*)+", replace, expression)
    tree = ast.parse(translated, mode="eval")
    return bool(_safe_eval(tree.body))


def _safe_eval(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BoolOp):
        values = [_safe_eval(value) for value in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _safe_eval(node.operand)
    if isinstance(node, ast.Compare):
        left = _safe_eval(node.left)
        for operation, comparator in zip(node.ops, node.comparators, strict=True):
            right = _safe_eval(comparator)
            functions = {ast.Gt: operator.gt, ast.GtE: operator.ge, ast.Lt: operator.lt, ast.LtE: operator.le, ast.Eq: operator.eq, ast.NotEq: operator.ne}
            if not functions[type(operation)](left, right):
                return False
            left = right
        return True
    raise ValueError("route expression contains unsupported syntax")
