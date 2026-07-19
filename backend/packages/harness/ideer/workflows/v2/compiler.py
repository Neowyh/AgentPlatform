"""Compile the constrained workflow graph into a LangGraph StateGraph."""

from __future__ import annotations

import ast
import asyncio
import operator
import re
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .adapters import ActionAdapterRegistry, ActionContext
from .schema import EdgeV2, NodeV2, WorkflowV2


class WorkflowCancelled(RuntimeError):
    """Raised when a queued cancellation is observed at a node boundary."""


class WorkflowNodeTimeout(RuntimeError):
    """Raised when a node exceeds the configured execution limit."""


class WorkflowIterationLimit(RuntimeError):
    """Raised when a declared workflow back-edge exceeds its bound."""


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
    ) -> None:
        self.definition = definition
        self.adapters = adapters
        self.emit_event = emit_event
        self.is_cancelled = is_cancelled
        self.node_timeout_seconds = node_timeout_seconds

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
                await self._emit("node_started", {"node_id": node.id})
                return {"interrupt": interrupt({"node_id": node.id, "roles": node.roles})}
            if node.type != "action":
                return state
            context = ActionContext(
                workflow_name=self.definition.name,
                run_id=_run_id(state),
                node_id=node.id,
                inputs=dict(state.get("inputs", {})),
                state=dict(state.get("state", {})),
                outputs=dict(state.get("outputs", {})),
            )
            params = _render_params(node.action.params, state)  # type: ignore[union-attr]
            await self._emit("node_started", {"node_id": node.id, "idempotency_key": context.idempotency_key})
            try:
                adapter = self.adapters.resolve(node.action.kind, node.action.name)  # type: ignore[union-attr]
                last_error: Exception | None = None
                for attempt in range(node.retry.max_attempts):
                    try:
                        action = self._run_action(adapter, context, params)
                        try:
                            result = await asyncio.wait_for(action, timeout=self.node_timeout_seconds) if self.node_timeout_seconds is not None else await action
                        except TimeoutError as exc:
                            raise WorkflowNodeTimeout("workflow_node_timeout") from exc
                        break
                    except Exception as exc:  # retry policy is deliberately node-local
                        last_error = exc
                        if attempt + 1 < node.retry.max_attempts and node.retry.backoff_seconds:
                            await asyncio.sleep(node.retry.backoff_seconds)
                else:
                    raise last_error or RuntimeError(f"node '{node.id}' failed")
            except Exception as exc:
                await self._emit(
                    "node_failed",
                    {"node_id": node.id, "idempotency_key": context.idempotency_key, "error": str(exc)},
                )
                raise
            await self._emit(
                "node_completed",
                {"node_id": node.id, "idempotency_key": context.idempotency_key, "result": result},
            )
            outputs = dict(state.get("outputs", {}))
            outputs[node.id] = result
            update: dict[str, Any] = {"outputs": {node.id: result}}
            if node.writes:
                if len(node.writes) != 1:
                    raise ValueError(f"action node '{node.id}' must declare exactly one write path")
                update["state"] = {_write_key(node.writes[0]): result}
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
        def select(state: dict[str, Any]) -> str:
            # Route expressions are statically constrained by parser; runtime
            # evaluation is intentionally limited to the declared expression.
            expression = node.expression or ""
            if node.routes:
                for condition, target in node.routes.items():
                    if _evaluate_expression(condition, state):
                        return edge_targets[target]
            return edge_targets[targets[0] if _evaluate_expression(expression, state) else targets[-1]]

        return select


def _run_id(state: dict[str, Any]) -> str:
    return str(state.get("run_id", "unknown"))


def _render_params(value: Any, state: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _render_params(item, state) for key, item in value.items()}
    if isinstance(value, list):
        return [_render_params(item, state) for item in value]
    if not isinstance(value, str) or "{{" not in value:
        return value
    result = value
    while "{{" in result:
        start = result.index("{{")
        end = result.index("}}", start)
        path = result[start + 2 : end].strip()
        replacement = _lookup_path(path, state)
        result = result[:start] + str(replacement) + result[end + 2 :]
    return result


def _lookup_path(path: str, state: dict[str, Any]) -> Any:
    current: Any = state
    for part in path.removeprefix("$.").split("."):
        current = current[part]
    return current


def _write_key(path: str) -> str:
    parts = path.removeprefix("$.state.").split(".")
    if len(parts) != 1:
        raise ValueError(f"nested state write path is not supported: '{path}'")
    return parts[0]


def _evaluate_expression(expression: str, state: dict[str, Any]) -> bool:
    def replace(match: re.Match[str]) -> str:
        value = _lookup_path(match.group(0), state)
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
