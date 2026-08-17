"""Structured workflow run error model.

Workflow failures used to surface as raw exception strings that could grow
very long (e.g. every invalid file_access path across all nodes joined with
``"; "``), which users could not read or act on.  These helpers mirror the
visibility closure error envelope (``{code, message, violations}``) already
established for resource governance, so the gateway and the frontend render
actionable, localized errors instead of long raw tracebacks.
"""

from __future__ import annotations

from typing import Any

# Error codes surfaced in event payloads and gateway error details.
INVALID_FILE_ROOTS = "invalid_file_roots"
MISSING_INPUT_ROOTS = "missing_input_roots"
AGENT_FAILED = "agent_failed"
TOOL_FAILED = "tool_failed"
SCHEMA_VIOLATION = "schema_violation"
PRECONDITION_FAILED = "precondition_failed"
NODE_TIMEOUT = "node_timeout"
ITERATION_LIMIT = "iteration_limit"
ARTIFACTS_MISSING = "artifacts_missing"
EVENT_LIMIT = "event_limit"
MAX_ATTEMPTS = "max_attempts"
UNKNOWN = "unknown"

# Detail (raw long text) stored in event payloads is capped at this length.
_DETAIL_CAP = 4000

# Short summaries are capped so run.error / list views stay readable.
_SUMMARY_CAP = 120


def _capped(text: str, cap: int = _DETAIL_CAP) -> str:
    if len(text) <= cap:
        return text
    return f"{text[:cap]}…"


def _short_text(text: str, cap: int = 60) -> str:
    """Collapse whitespace and truncate to a short readable phrase."""
    collapsed = " ".join(str(text).split())
    return _capped(collapsed, cap)


def _node_label(node_id: str | None) -> str:
    return f"节点「{node_id}」" if node_id else "工作流节点"


def _node_count(violations: list[dict[str, Any]]) -> int:
    return len({str(v.get("node_id")) for v in violations if v.get("node_id")})


class WorkflowRunError(Exception):
    """Structured workflow failure carried through events and the run record.

    ``summary`` is a short, user-readable Chinese sentence; ``detail`` holds
    the raw long text; ``violations`` is a structured list (e.g. invalid
    file_access paths) mirroring the visibility closure violation shape.
    """

    def __init__(
        self,
        code: str,
        summary: str,
        *,
        node_id: str | None = None,
        detail: str = "",
        violations: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(summary)
        self.code = code
        self.summary = summary
        self.node_id = node_id
        self.detail = detail
        self.violations = list(violations or [])

    def payload(self) -> dict[str, Any]:
        """Serialize for event payloads (node_failed / run_failed)."""
        payload: dict[str, Any] = {"code": self.code, "summary": self.summary}
        if self.node_id is not None:
            payload["node_id"] = self.node_id
        if self.detail:
            payload["error"] = _capped(self.detail)
        if self.violations:
            payload["violations"] = self.violations
        return payload

    def api_detail(self) -> dict[str, Any]:
        """Serialize for gateway HTTP error detail (``{code, message, violations}``)."""
        detail: dict[str, Any] = {"code": self.code, "message": self.summary}
        if self.violations:
            detail["violations"] = self.violations
        return detail


def summarize_root_violations(code: str, violations: list[dict[str, Any]]) -> str:
    """Short summary for file_access root violations (run creation pre-flight)."""
    total = len(violations)
    nodes = _node_count(violations)
    if code == MISSING_INPUT_ROOTS:
        return f"无法启动工作流：{total} 个输入路径缺失或为空（涉及 {nodes} 个节点）"
    return f"无法启动工作流：{total} 个文件访问路径不在允许的挂载范围内（涉及 {nodes} 个节点）"


def format_root_violations(violations: list[dict[str, Any]]) -> list[str]:
    """Human-readable lines for a structured root violation list."""
    lines = []
    for violation in violations:
        node_id = violation.get("node_id")
        access = violation.get("access", "read")
        path = violation.get("path", "")
        prefix = f"node '{node_id}': " if node_id else ""
        lines.append(f"{prefix}{access}:{path}")
    return lines


class WorkflowInvalidRootsError(WorkflowRunError):
    """Raised when a workflow definition declares file_access paths outside
    the allowed mount allowlist (run creation and worker pre-flight)."""

    def __init__(self, violations: list[dict[str, Any]]) -> None:
        super().__init__(
            INVALID_FILE_ROOTS,
            summarize_root_violations(INVALID_FILE_ROOTS, violations),
            violations=violations,
            detail="; ".join(format_root_violations(violations)),
        )


class WorkflowMissingInputRootsError(WorkflowRunError):
    """Raised when a run's input read roots are missing or empty."""

    def __init__(self, violations: list[dict[str, Any]]) -> None:
        super().__init__(
            MISSING_INPUT_ROOTS,
            summarize_root_violations(MISSING_INPUT_ROOTS, violations),
            violations=violations,
            detail="; ".join(format_root_violations(violations)),
        )


def node_failure_payload(node_id: str | None, exc: Exception) -> dict[str, Any]:
    """Map one node-level exception to a structured ``node_failed`` payload.

    The compiler imports this module, so the compiler exception classes are
    imported lazily to keep the import graph acyclic.
    """
    from .adapters import ActionResolutionError
    from .compiler import (
        ArtifactsMissing,
        WorkflowIterationLimit,
        WorkflowNodeFailed,
        WorkflowNodeTimeout,
        WorkflowPreconditionFailed,
        WorkflowSchemaViolation,
    )

    code = UNKNOWN
    label = _node_label(node_id)
    summary = f"{label}执行失败"
    detail = str(exc)
    if isinstance(exc, WorkflowSchemaViolation):
        code = SCHEMA_VIOLATION
        summary = f"{label}输出未通过 schema 校验（{len(exc.violations)} 项违规）"
        detail = "\n".join(exc.violations)
    elif isinstance(exc, WorkflowPreconditionFailed):
        code = PRECONDITION_FAILED
        summary = f"{label}前置条件不满足（{len(exc.violations)} 项）"
        detail = "\n".join(exc.violations)
    elif isinstance(exc, WorkflowNodeFailed):
        code = AGENT_FAILED
        summary = f"{label}执行失败：{_short_text(_agent_failure_reason(str(exc)))}"
        detail = str(exc)
    elif isinstance(exc, WorkflowNodeTimeout):
        code = NODE_TIMEOUT
        summary = f"{label}执行超时"
    elif isinstance(exc, WorkflowIterationLimit):
        code = ITERATION_LIMIT
        summary = f"{label}循环次数达到上限"
    elif isinstance(exc, ArtifactsMissing):
        code = ARTIFACTS_MISSING
        summary = f"{label}未产出声明的工作文件（{len(exc.missing)} 个）"
        detail = "\n".join(exc.missing)
    elif isinstance(exc, ActionResolutionError):
        code = UNKNOWN
        summary = f"{label}依赖的动作不可用：{_short_text(str(exc))}"
    payload: dict[str, Any] = {"node_id": node_id, "code": code, "summary": summary, "error": _capped(detail)}
    if node_id is None:
        payload.pop("node_id")
    return payload


def run_failure_payload(exc: Exception) -> dict[str, Any]:
    """Map a run-level failure to a structured ``run_failed`` payload.

    Structured exceptions pass through; node-level exceptions (whose detailed
    ``node_failed`` event was already emitted) collapse to a short summary.
    """
    if isinstance(exc, WorkflowRunError):
        return exc.payload()
    payload = node_failure_payload(None, exc)
    return {"code": payload["code"], "summary": f"工作流失败：{payload['summary']}", "error": payload.get("error", _capped(str(exc)))}


def run_error_summary(exc: Exception) -> str:
    """Short summary persisted to ``run.error`` (run list / run record header)."""
    if isinstance(exc, WorkflowRunError):
        return exc.summary
    payload = node_failure_payload(None, exc)
    return _capped(payload["summary"], _SUMMARY_CAP)


def _agent_failure_reason(message: str) -> str:
    """Extract the agent's own explanation from a ``FAILED:`` node message."""
    marker = "FAILED:"
    if marker in message:
        return message.split(marker, 1)[1].strip()
    prefix = "reported failure:"
    if prefix in message:
        return message.split(prefix, 1)[1].strip()
    return message
