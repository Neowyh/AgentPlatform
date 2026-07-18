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
from .schema import NodeV2, WorkflowV2


class WorkflowCancelled(RuntimeError):
    """Raised when a queued cancellation is observed at a node boundary."""


def _merge_maps(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class _GraphState(TypedDict, total=False):
    run_id: str
    inputs: dict[str, Any]
    state: Annotated[dict[str, Any], _merge_maps]
    outputs: Annotated[dict[str, Any], _merge_maps]


class WorkflowGraphCompiler:
    def __init__(
        self,
        definition: WorkflowV2,
        adapters: ActionAdapterRegistry,
        emit_event: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None,
        is_cancelled: Callable[[], Awaitable[bool]] | None = None,
    ) -> None:
        self.definition = definition
        self.adapters = adapters
        self.emit_event = emit_event
        self.is_cancelled = is_cancelled

    def compile(self, *, checkpointer: Any = None) -> Any:
        graph = StateGraph(_GraphState)
        for node in self.definition.nodes:
            graph.add_node(node.id, self._node_handler(node))
        graph.add_edge(START, self.definition.entrypoint)
        outgoing: dict[str, list[str]] = {node.id: [] for node in self.definition.nodes}
        for edge in self.definition.edges:
            outgoing[edge.from_].append(edge.to)
        incoming: dict[str, list[str]] = {node.id: [] for node in self.definition.nodes}
        for source, targets in outgoing.items():
            for target in targets:
                incoming[target].append(source)
        for node in self.definition.nodes:
            targets = outgoing[node.id]
            if node.type == "fork":
                for target in targets:
                    graph.add_edge(node.id, target)
            elif node.type == "join":
                branches = [source for source in incoming[node.id] if source in (self._node(node.fork).branches if node.fork else [])]
                if branches:
                    graph.add_edge(branches, node.id)
                else:
                    graph.add_edge(node.id, END)
            elif node.type == "route":
                graph.add_conditional_edges(node.id, self._route_selector(node, targets), targets)
            elif targets:
                target = targets[0]
                if not (self._node(target).type == "join" and node.id in incoming[target]):
                    graph.add_edge(node.id, target)
            else:
                graph.add_edge(node.id, END)
        return graph.compile(checkpointer=checkpointer)

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
                        result = await adapter.run(context, params)
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

    def _node(self, node_id: str) -> NodeV2:
        return next(node for node in self.definition.nodes if node.id == node_id)

    def _route_selector(self, node: NodeV2, targets: list[str]):
        def select(state: dict[str, Any]) -> str:
            # Route expressions are statically constrained by parser; runtime
            # evaluation is intentionally limited to the declared expression.
            expression = node.expression or ""
            if node.routes:
                for condition, target in node.routes.items():
                    if _evaluate_expression(condition, state):
                        return target
            return targets[0] if _evaluate_expression(expression, state) else targets[-1]

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
