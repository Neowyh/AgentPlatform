"""Compile the constrained workflow graph into a LangGraph StateGraph."""

from __future__ import annotations

import ast
import asyncio
import json
import operator
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, TypedDict

from jsonschema import Draft202012Validator
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .adapters import ActionAdapterRegistry, ActionContext
from .errors import node_failure_payload
from .file_roots import lookup_path, materialize_state, missing_written_artifacts, path_within_root, render_template, workflow_state_path, workflow_state_root
from .schema import EdgeV2, NodeV2, WorkflowV2


class WorkflowCancelled(RuntimeError):
    """Raised when a queued cancellation is observed at a node boundary."""


class WorkflowNodeTimeout(RuntimeError):
    """Raised when a node exceeds the configured execution limit."""


class WorkflowIterationLimit(RuntimeError):
    """Raised when a declared workflow back-edge exceeds its bound."""


class WorkflowNodeFailed(RuntimeError):
    """Raised when a node's response declares failure via the ``FAILED:`` marker."""


class WorkflowPreconditionFailed(WorkflowNodeFailed):
    """Raised when a node's input preconditions are not satisfied.

    Carries the full violation list so callers can render every reason the
    node cannot run instead of a generic failure.
    """

    def __init__(self, node_id: str, violations: list[str]) -> None:
        super().__init__(f"node '{node_id}' precondition failed: {'; '.join(violations)}")
        self.violations = violations


class WorkflowSchemaViolation(WorkflowNodeFailed):
    """Raised when a node's written output violates a declared JSON schema.

    Carries the full violation list so the retry loop can feed it back to the
    agent on the next attempt instead of re-running blindly.
    """

    def __init__(self, node_id: str, violations: list[str]) -> None:
        super().__init__(f"node '{node_id}' schema validation failed: {'; '.join(violations)}")
        self.violations = violations


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

# Schema gate violations reported per node: every violation is collected up to
# this cap (jsonschema stops at the first error by default, which hides the
# rest of the defect list from both the operator and retry feedback).
_SCHEMA_VIOLATION_LIMIT = 10
_SCHEMA_FEEDBACK_MAX_CHARS = 4000


def _schema_feedback_message(node_id: str, attempt: int, violations: list[str]) -> str:
    """Human-readable retry feedback carrying the schema violations."""
    joined = "; ".join(violations)
    if len(joined) > _SCHEMA_FEEDBACK_MAX_CHARS:
        joined = f"{joined[:_SCHEMA_FEEDBACK_MAX_CHARS]}…"
    return f"第 {attempt} 次尝试，schema 校验反馈：节点 {node_id} 上一次写入的输出文件未通过 JSON Schema 校验，将重试。请先读取校验错误，仅修复输出文件中的问题后重新写入（不要重复已完成的工作，不要改动与这些错误无关的内容）：\n{joined}"


def _inject_prompt_feedback(params: dict[str, Any], feedback: str) -> dict[str, Any]:
    """Append retry feedback to the next attempt's agent prompt."""
    updated = dict(params)
    for key in ("prompt", "input"):
        if isinstance(updated.get(key), str):
            updated[key] = f"{updated[key]}\n\n{feedback}"
            return updated
    updated["prompt"] = feedback
    return updated


def _merge_maps(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class _GraphState(TypedDict, total=False):
    run_id: str
    inputs: dict[str, Any]
    model_name: str | None
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
                await self._emit("node_failed", node_failure_payload(edge.from_, WorkflowIterationLimit("workflow_iteration_limit_exceeded")))
                raise WorkflowIterationLimit("workflow_iteration_limit_exceeded")
            return {"edge_iterations": {key: count}}

        return run

    def _node_handler(self, node: NodeV2):
        async def run(state: dict[str, Any]) -> dict[str, Any]:
            if self.is_cancelled is not None and await self.is_cancelled():
                raise WorkflowCancelled(f"workflow cancelled before node '{node.id}'")
            if node.type == "interrupt":
                await self._emit("node_started", {"node_id": node.id, "started_at": _now_iso()})
                value = interrupt({"node_id": node.id, "roles": node.roles})
                await self._emit("node_completed", {"node_id": node.id, "finished_at": _now_iso()})
                return {"interrupt": value}
            if node.type != "action":
                await self._emit("node_started", {"node_id": node.id, "started_at": _now_iso()})
                await self._emit("node_completed", {"node_id": node.id, "finished_at": _now_iso()})
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
                model_name=state.get("model_name"),
            )
            params = render_template(node.action.params, render_state)  # type: ignore[union-attr]
            await self._emit(
                "node_started",
                {"node_id": node.id, "idempotency_key": context.idempotency_key, "model_name": context.model_name, "started_at": _now_iso()},
            )
            violations = self._check_preconditions(node, render_state)
            if violations and node.on_precondition_failure == "skip":
                await self._emit(
                    "node_skipped",
                    {"node_id": node.id, "idempotency_key": context.idempotency_key, "reasons": violations, "finished_at": _now_iso()},
                )
                return {"outputs": {node.id: None}}
            try:
                if violations:
                    raise WorkflowPreconditionFailed(node.id, violations)
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
                                raise WorkflowNodeFailed(f"node '{node.id}' reported failure: {result[:4000]}")
                            if self.artifact_resolver is not None and context.file_access is not None:
                                missing = missing_written_artifacts(context.file_access.get("write", []), self.artifact_resolver)
                                if missing:
                                    raise ArtifactsMissing(missing)
                            schema_violations = self._check_write_schemas(node, render_state)
                            if schema_violations:
                                raise WorkflowSchemaViolation(node.id, schema_violations)
                            break
                        except WorkflowTransientError as exc:
                            # transient provider/network errors leave the node-retry
                            # policy and get their own backoff budget below
                            last_error = exc
                            break
                        except Exception as exc:  # retry policy is deliberately node-local
                            last_error = exc
                            if isinstance(exc, WorkflowSchemaViolation) and attempt + 1 < node.retry.max_attempts and node.action is not None and node.action.kind == "agent":
                                feedback = _schema_feedback_message(node.id, attempt + 1, exc.violations)
                                await self._emit("action_progress", {"node_id": node.id, "message": feedback})
                                params = _inject_prompt_feedback(params, feedback)
                            if attempt + 1 < node.retry.max_attempts and node.retry.backoff_seconds:
                                await asyncio.sleep(node.retry.backoff_seconds)
                    else:
                        if isinstance(last_error, ArtifactsMissing) and node.on_missing_artifact == "pause":
                            # Two-phase interrupt so every resume re-verifies the
                            # gate: on resume the node re-runs and the first
                            # interrupt() consumes the resume value without raising,
                            # then the second interrupt() has no resume value left
                            # and raises a fresh GraphInterrupt — pausing again.
                            interrupt({"type": "artifacts_missing", "node_id": node.id, "missing": last_error.missing})
                            return {"interrupt": interrupt({"type": "artifacts_missing", "node_id": node.id, "missing": last_error.missing})}
                        # Default: missing artifacts are not something a resume
                        # can fix — the node fails explicitly instead.
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
                    {**node_failure_payload(node.id, exc), "idempotency_key": context.idempotency_key, "finished_at": _now_iso()},
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

    def _check_preconditions(self, node: NodeV2, render_state: dict[str, Any]) -> list[str]:
        """Report every unsatisfied input precondition for the node.

        Each violation carries a concrete reason (missing file, empty file,
        unparseable JSON, no matching value) so operators see exactly why the
        node would fail instead of a generic agent failure.  Callers decide
        whether a violation fails the node or skips it.
        """
        if not node.preconditions or self.artifact_resolver is None:
            return []
        read_roots: list[str] = [workflow_state_root()]
        if node.action is not None and node.action.file_access is not None:
            rendered_access = render_template(node.action.file_access.model_dump(), render_state)
            read_roots.extend(rendered_access.get("read", []))
        violations: list[str] = []
        for precondition in node.preconditions:
            file = render_template(precondition.file, render_state)
            if not isinstance(file, str) or "{{" in file:
                violations.append(f"precondition file '{precondition.file}' could not be resolved")
                continue
            if not any(path_within_root(file, root) for root in read_roots):
                violations.append(f"precondition file '{file}' is not under the node's read roots")
                continue
            host = self.artifact_resolver(file)
            if host is None:
                violations.append(f"precondition file '{file}' cannot be resolved to the sandbox")
                continue
            path = Path(host)
            if not path.is_file():
                violations.append(f"precondition file '{file}' does not exist")
                continue
            if precondition.non_empty and path.stat().st_size == 0:
                violations.append(f"precondition file '{file}' is empty")
                continue
            if precondition.json_path is not None or precondition.some_equals is not None or precondition.none_equals is not None:
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    violations.append(f"precondition file '{file}' is not valid JSON")
                    continue
                if precondition.json_path is not None:
                    try:
                        values = _pick_json_values(data, precondition.json_path)
                    except ValueError as exc:
                        violations.append(f"precondition file '{file}': {exc}")
                        continue
                    if precondition.some_equals is not None:
                        if not any(value == precondition.some_equals for value in values):
                            violations.append(f"precondition '{precondition.json_path}' of '{file}' has no value equal to {precondition.some_equals!r} (found {values!r})")
                    elif precondition.none_equals is not None:
                        if any(value == precondition.none_equals for value in values):
                            violations.append(f"precondition '{precondition.json_path}' of '{file}' must not contain {precondition.none_equals!r} (found {values!r})")
                elif precondition.some_equals is not None and data != precondition.some_equals:
                    violations.append(f"precondition file '{file}' must equal {precondition.some_equals!r}")
                elif precondition.none_equals is not None and data == precondition.none_equals:
                    violations.append(f"precondition file '{file}' must not equal {precondition.none_equals!r}")
        return violations

    def _check_write_schemas(self, node: NodeV2, render_state: dict[str, Any]) -> list[str]:
        """Validate every declared write root against its JSON schema.

        Returns concrete violations (unresolvable schema, unwritten target,
        unparseable file, schema violation) so the node fails with a reason
        an operator can act on instead of a generic agent failure.  All
        schema violations are collected (up to ``_SCHEMA_VIOLATION_LIMIT``)
        instead of just the first, so the defect list is complete for both
        the operator and the retry feedback.
        """
        if not node.schemas or self.artifact_resolver is None:
            return []
        read_roots: list[str] = [workflow_state_root()]
        write_roots: list[str] = []
        if node.action is not None and node.action.file_access is not None:
            rendered_access = render_template(node.action.file_access.model_dump(), render_state)
            read_roots.extend(rendered_access.get("read", []))
            write_roots.extend(rendered_access.get("write", []))
        violations: list[str] = []
        for spec in node.schemas:
            file = render_template(spec.file, render_state)
            schema_file = render_template(spec.schema_file, render_state)
            if not isinstance(file, str) or not isinstance(schema_file, str) or "{{" in file or "{{" in schema_file:
                violations.append(f"schema gate '{spec.file}' → '{spec.schema_file}' could not be resolved")
                continue
            if not any(path_within_root(file, root) for root in write_roots):
                violations.append(f"schema target '{file}' is not under the node's write roots")
                continue
            if not any(path_within_root(schema_file, root) for root in read_roots):
                violations.append(f"schema file '{schema_file}' is not under the node's read roots")
                continue
            schema_host = self.artifact_resolver(schema_file)
            if schema_host is None or not Path(schema_host).is_file():
                violations.append(f"schema file '{schema_file}' cannot be resolved to the sandbox")
                continue
            file_host = self.artifact_resolver(file)
            if file_host is None or not Path(file_host).is_file():
                violations.append(f"schema target '{file}' was not written")
                continue
            try:
                instance = json.loads(Path(file_host).read_text(encoding="utf-8"))
                schema = json.loads(Path(schema_host).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                violations.append(f"schema target '{file}' or schema '{schema_file}' is not valid JSON: {exc}")
                continue
            try:
                validator = Draft202012Validator(schema)
                for index, error in enumerate(validator.iter_errors(instance)):
                    if index >= _SCHEMA_VIOLATION_LIMIT:
                        break
                    violations.append(f"'{file}' violates '{schema_file}' at {error.json_path or '$'}: {error.message}")
            except Exception as exc:
                violations.append(f"schema '{schema_file}' could not be applied: {exc}")
        return violations

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


def _pick_json_values(data: Any, path: str) -> list[Any]:
    """Collect the values addressed by a compact JSON path.

    Supports dotted keys, ``[*]`` (expand every list/dict value) and integer
    indexes, e.g. ``$.root_causes[*].status``.  Missing keys simply produce no
    values — callers decide what that means.
    """
    segments = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\[\*\]|\[[+-]?\d+\]", path)
    current: list[Any] = [data]
    for segment in segments:
        if segment == "[*]":
            expanded: list[Any] = []
            for item in current:
                if isinstance(item, list):
                    expanded.extend(item)
                elif isinstance(item, dict):
                    expanded.extend(item.values())
            current = expanded
            continue
        if segment.startswith("[") and segment.endswith("]"):
            try:
                index = int(segment[1:-1])
            except ValueError as exc:
                raise ValueError(f"invalid json_path segment '{segment}'") from exc
            indexed: list[Any] = []
            for item in current:
                if isinstance(item, list) and -len(item) <= index < len(item):
                    indexed.append(item[index])
            current = indexed
            continue
        narrowed: list[Any] = []
        for item in current:
            if isinstance(item, dict) and segment in item:
                narrowed.append(item[segment])
        current = narrowed
    return current


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
