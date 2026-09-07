"""Legacy fault-zeroing run lifecycle handling (ticket 06).

The canonical bundled resource module is the only lifecycle source for the
fault-zeroing Skill–Expert–Workflow closure.  Runs created before the
cutover on legacy (name+version) definitions must never be silently
re-interpreted against the new semantics:

- completed / failed / cancelled legacy runs stay readable as-is;
- queued / paused legacy runs are explicitly terminated with a stable
  reason code and an audit event.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

LEGACY_WORKFLOW_NAME = "fault-zeroing"

REASON_LEGACY_RUN_TERMINATED = "legacy_run_terminated"

TERMINATABLE_STATUSES = ("queued", "paused")
TERMINAL_STATUS = "cancelled"


class LegacyStore(Protocol):
    """Narrow store surface needed for legacy run migration."""

    async def list_runs(self, *args: Any, **kwargs: Any) -> Any: ...

    async def append_event(self, *args: Any, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class LegacyRunMigrationReport:
    terminated_run_ids: tuple[str, ...]
    untouched_run_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "terminated_run_ids": list(self.terminated_run_ids),
            "untouched_run_ids": list(self.untouched_run_ids),
        }


async def terminate_legacy_runs(
    store: Any,
    *,
    workflow_name: str = LEGACY_WORKFLOW_NAME,
    worker_id: str = "fault-zeroing-legacy-migration",
) -> LegacyRunMigrationReport:
    """Explicitly terminate queued/paused legacy runs; keep finished ones readable.

    A legacy run is one whose row carries ``workflow_resource_id IS NULL`` —
    i.e. it was created through the old name+version path instead of the
    canonical resource snapshot.  Termination cancels the run and appends a
    ``run_cancelled`` event with reason code ``legacy_run_terminated``.
    """

    runs, _total = await store.list_runs(workflow_name=workflow_name, limit=10000)
    terminated: list[str] = []
    untouched: list[str] = []
    for run in runs:
        if getattr(run, "workflow_resource_id", None) is not None:
            untouched.append(run.run_id)
            continue
        if run.status not in TERMINATABLE_STATUSES:
            untouched.append(run.run_id)
            continue
        updated = await store.cancel_legacy_run(run.run_id, status=TERMINAL_STATUS, reason_code=REASON_LEGACY_RUN_TERMINATED)
        if updated is False:
            untouched.append(run.run_id)
            continue
        await store.append_event(
            run.run_id,
            "run_cancelled",
            {
                "code": REASON_LEGACY_RUN_TERMINATED,
                "summary": ("legacy fault-zeroing run explicitly terminated during canonical resource cutover; it is not re-interpreted under the new semantics"),
            },
            worker_id=worker_id,
        )
        terminated.append(run.run_id)
    return LegacyRunMigrationReport(
        terminated_run_ids=tuple(terminated),
        untouched_run_ids=tuple(untouched),
    )
