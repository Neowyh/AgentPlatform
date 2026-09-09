"""Policy-gated local file task handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .files import LocalFileStore
from .policy import LocalPolicy, PolicyDecision


@dataclass(frozen=True)
class FileTaskResult:
    decision: PolicyDecision
    value: Any = None


class LocalFileService:
    def __init__(
        self,
        files: LocalFileStore,
        *,
        policy: LocalPolicy | None = None,
    ) -> None:
        self.files = files
        self.policy = policy or LocalPolicy()

    def execute(self, capability: str, payload: dict[str, Any]) -> FileTaskResult:
        if capability not in {"local.files.list", "local.files.read"}:
            raise ValueError("unsupported local file capability")
        decision = self.policy.authorize(capability, payload)
        if decision is not PolicyDecision.ALLOW:
            return FileTaskResult(decision)
        if capability == "local.files.list":
            return FileTaskResult(decision, self.files.list(str(payload["path"])))
        if capability == "local.files.read":
            return FileTaskResult(decision, self.files.read(str(payload["path"])))
