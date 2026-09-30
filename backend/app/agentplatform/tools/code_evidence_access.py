"""Shared package-root access constraint for Code Evidence tools.

``analyze_code_evidence`` (ticket 01) and ``read_binary_hex`` (ticket 03) both
accept nothing but this thread's Code Evidence Package under the fixed virtual
root ``/mnt/user-data/code-evidence/``: the constraint is resolved inside the
server (the filesystem middleware is not involved), so the model never sees a
host path and can never point the tools elsewhere.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.agentplatform.code_evidence import package_root as code_evidence_package_root
from deerflow.runtime.user_context import resolve_runtime_user_id
from deerflow.tools.types import Runtime

CODE_EVIDENCE_VIRTUAL_ROOT = "/mnt/user-data/code-evidence"
_ALLOWED_PACKAGE_ROOT = re.compile(rf"^{re.escape(CODE_EVIDENCE_VIRTUAL_ROOT)}/[^/]+(/source)?$")


class PackageAccessRejected(ValueError):
    """The declared package root is outside the allowed closure or unknown."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def get_thread_id(runtime: Runtime) -> str | None:
    thread_id = runtime.context.get("thread_id") if runtime.context else None
    if thread_id:
        return thread_id
    runtime_config = getattr(runtime, "config", None) or {}
    return runtime_config.get("configurable", {}).get("thread_id")


def resolve_package_dir(runtime: Runtime, declared_root: str, thread_id: str) -> tuple[Path, str]:
    declared = (declared_root or "").strip()
    normalized = declared.rstrip("/")
    if normalized.endswith("/source"):
        normalized = normalized[: -len("/source")]
    if not (_ALLOWED_PACKAGE_ROOT.match(declared) or _ALLOWED_PACKAGE_ROOT.match(normalized)):
        raise PackageAccessRejected(
            "package_path_rejected",
            f"只接受本会话的代码证据包根 {CODE_EVIDENCE_VIRTUAL_ROOT}/<package_id>，收到: {declared or '<空>'}",
        )
    package_id = normalized[len(CODE_EVIDENCE_VIRTUAL_ROOT) + 1 :]
    try:
        root = code_evidence_package_root(thread_id, package_id, user_id=resolve_runtime_user_id(runtime))
    except ValueError as exc:
        raise PackageAccessRejected("package_path_rejected", f"代码证据包 id 不合法: {package_id}（{exc}）") from exc
    if not root.is_dir():
        raise PackageAccessRejected("package_not_found", f"本会话不存在该代码证据包: {package_id}")
    return root, package_id
