"""Shared fault-zeroing execution kernel (ticket 03).

The single resumable Run seam for fault-zeroing analysis.  Skill, Expert and
Workflow entries (ticket 04) are presentation adapters over this kernel;
none of them re-implements stages or result validation.

Responsibilities:

- hybrid evidence intake before any model execution (ticket 02);
- pinning the Result Contract version per run (ticket 01);
- completion judgment based on the full five artifacts and their semantic
  consistency via the Result Contract — never on file existence alone;
- ``pending_verification`` as a fully-disclosed completion status: it passes
  the contract only when the report discloses it and it never equals a
  confirmed root cause;
- observable, stable reason codes on every pause, confirmation, rejection
  and failure (ticket 05).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4

from ideer.fault_zeroing import intake as intake_mod
from ideer.fault_zeroing import policy
from ideer.fault_zeroing.contract import (
    CONTRACT_VERSION,
    ContractUnavailableError,
    ContractVerdict,
    evaluate_result_contract,
)
from ideer.fault_zeroing.intake import EvidenceIntakeDecision

KERNEL_WORKER_ID = "fault-zeroing-kernel"

SNAPSHOT_INTAKE_KEY = "evidence_intake"
SNAPSHOT_CONTRACT_VERSION_KEY = "contract_version"

# Kernel event types (persisted through the store's event log).
# Rejection before run creation (both evidence sides missing) raises
# EvidenceIntakeRejected with its reason code; no run row exists, so there
# is no run-scoped event log to append to — the gateway surfaces the code.
EVENT_INTERRUPTED = "interrupted"
EVENT_CONFIRMED = "resumed"
EVENT_CONFIRMATION_REJECTED = "kernel_confirmation_rejected"
EVENT_CONTRACT_EVALUATED = "kernel_contract_evaluated"
EVENT_CONTRACT_FAILED = "kernel_contract_failed"

COMPLETION_STATUS_COMPLETED = "completed"
COMPLETION_STATUS_FAILED = "failed"

REASON_RUN_NOT_PAUSED = "run_not_paused_for_confirmation"


class EvidenceIntakeRejected(RuntimeError):
    """Both evidence sides are missing: no usable run is created."""

    def __init__(self, decision: EvidenceIntakeDecision) -> None:
        super().__init__(decision.reason_code)
        self.decision = decision
        self.reason_code = decision.reason_code


class ConfirmationStaleError(RuntimeError):
    """Inputs changed after the pause: re-confirmation is required."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class RunNotFoundError(KeyError):
    pass


class KernelStore(Protocol):
    """Narrow store surface the kernel depends on."""

    async def create_run(self, *args: Any, **kwargs: Any) -> Any: ...

    async def create_paused_run(self, *args: Any, **kwargs: Any) -> Any: ...

    async def append_event(self, *args: Any, **kwargs: Any) -> Any: ...

    async def get_run(self, run_id: str) -> Any: ...

    async def update_snapshot(self, run_id: str, snapshot: dict, *, worker_id: str) -> bool: ...

    async def submit_command(self, *args: Any, **kwargs: Any) -> Any: ...


@dataclass
class KernelStartResult:
    run_id: str
    status: str  # "queued" | "paused"
    intake: EvidenceIntakeDecision
    reason_code: str


@dataclass
class KernelCompletion:
    run_id: str
    status: str  # completed | failed
    verdict: ContractVerdict
    reason_codes: list[str] = field(default_factory=list)
    pending_verification: bool = False


def _tree_has_pending_verification(outputs_dir: str) -> bool:
    import json
    from pathlib import Path

    tree_path = Path(outputs_dir) / "fault_tree.json"
    try:
        tree = json.loads(tree_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    plan = tree.get("verification_plan")
    if not isinstance(plan, list):
        return False
    return any(isinstance(item, dict) and item.get("status") == "pending" for item in plan)


def _current_inputs_snapshot(inputs: dict[str, Any]) -> dict[str, str]:
    return intake_mod.build_input_snapshot(inputs.get("upload_dir"), inputs.get("code_package_source"))


def _current_snapshot_hash(inputs: dict[str, Any]) -> str:
    return intake_mod.input_snapshot_hash(_current_inputs_snapshot(inputs))


def _intake_record_from_snapshot(snapshot: dict[str, Any]) -> EvidenceIntakeDecision:
    try:
        payload = snapshot[SNAPSHOT_INTAKE_KEY]
    except (KeyError, TypeError) as exc:
        raise ConfirmationStaleError(
            "intake_record_missing",
            "run snapshot has no evidence intake record",
        ) from exc
    return intake_mod.EvidenceIntakeDecision.from_dict(payload)


class FaultZeroingKernel:
    """Unified, resumable fault-zeroing Run seam."""

    def __init__(
        self,
        store: KernelStore,
        *,
        contract_version: str | None = None,
        id_factory: Any = uuid4,
    ) -> None:
        self._store = store
        self._contract_version = contract_version or CONTRACT_VERSION
        self._id_factory = id_factory

    # ------------------------------------------------------------------
    # Run seam
    # ------------------------------------------------------------------

    async def start_run(
        self,
        *,
        workflow_name: str,
        definition_version: int,
        inputs: dict[str, Any],
        created_by: str,
        run_id: str | None = None,
        department_id: str | None = None,
    ) -> KernelStartResult:
        """Start a run through hybrid evidence intake.

        - both evidence sides present: queue the run immediately;
        - one side missing: park the run in a persistent, persisted pause
          awaiting explicit user confirmation (no task to claim, so no model
          execution can happen);
        - both sides missing: reject before model execution — no usable run.
        """

        run_id = run_id or str(self._id_factory())
        decision = intake_mod.assess_evidence_intake(
            upload_dir=inputs.get("upload_dir"),
            code_package_source=inputs.get("code_package_source"),
            evidence_mode=inputs.get("evidence_mode", "hybrid"),
        )

        if decision.status == intake_mod.REJECT:
            # No run is created: the rejection itself is the observable record.
            raise EvidenceIntakeRejected(decision)

        pinned_snapshot = {
            SNAPSHOT_INTAKE_KEY: decision.to_dict(),
            SNAPSHOT_CONTRACT_VERSION_KEY: self._contract_version,
        }

        if decision.status == intake_mod.PAUSE:
            payload = intake_mod.interrupt_payload(decision)
            await self._store.create_paused_run(
                run_id,
                workflow_name,
                definition_version,
                dict(inputs),
                created_by,
                snapshot={**pinned_snapshot, "interrupt": [payload]},
                department_id=department_id,
            )
            await self._store.append_event(
                run_id,
                EVENT_INTERRUPTED,
                {"code": decision.reason_code, **payload},
                worker_id=KERNEL_WORKER_ID,
            )
            return KernelStartResult(
                run_id=run_id,
                status="paused",
                intake=decision,
                reason_code=decision.reason_code,
            )

        await self._store.create_run(
            run_id,
            workflow_name,
            definition_version,
            dict(inputs),
            created_by,
            department_id=department_id,
            snapshot=pinned_snapshot,
        )
        await self._store.append_event(
            run_id,
            "run_started",
            {
                "code": decision.reason_code,
                "evidence_mode": decision.evidence_mode,
                "missing_evidence_sides": list(decision.missing),
                "contract_version": self._contract_version,
            },
            worker_id=KERNEL_WORKER_ID,
        )
        return KernelStartResult(
            run_id=run_id,
            status="queued",
            intake=decision,
            reason_code=decision.reason_code,
        )

    # ------------------------------------------------------------------
    # Evidence confirmation (pause/resume)
    # ------------------------------------------------------------------

    async def confirm_evidence(
        self,
        run_id: str,
        *,
        payload: dict[str, Any],
        confirmed_by: str,
        command_id: str | None = None,
    ) -> dict[str, Any]:
        """Resume a paused run after the user confirms the evidence gap.

        The confirmation is bound to the input snapshot the user saw; new
        material added afterwards changes the hash and forces a
        re-confirmation instead of silently continuing.
        """

        run = await self._store.get_run(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        if getattr(run, "status", None) != "paused":
            # Evidence confirmation only applies to a run parked by intake;
            # confirming a queued/running/finished run would silently resume
            # something that never paused for evidence.
            await self._store.append_event(
                run_id,
                EVENT_CONFIRMATION_REJECTED,
                {"code": REASON_RUN_NOT_PAUSED, "run_status": getattr(run, "status", None)},
                worker_id=KERNEL_WORKER_ID,
            )
            raise ConfirmationStaleError(
                REASON_RUN_NOT_PAUSED,
                "evidence confirmation requires a run paused by evidence intake",
            )
        record = _intake_record_from_snapshot(dict(run.snapshot or {}))
        if not record.missing:
            await self._store.append_event(
                run_id,
                EVENT_CONFIRMATION_REJECTED,
                {"code": REASON_RUN_NOT_PAUSED, "missing": []},
                worker_id=KERNEL_WORKER_ID,
            )
            raise ConfirmationStaleError(
                REASON_RUN_NOT_PAUSED,
                "run intake record shows no missing evidence side to confirm",
            )
        current_hash = _current_snapshot_hash(dict(run.inputs or {}))
        presented_hash = payload.get("input_snapshot_hash")

        if presented_hash != current_hash:
            message = "inputs changed after the confirmation pause: re-confirmation with the current snapshot is required"
            await self._store.append_event(
                run_id,
                EVENT_CONFIRMATION_REJECTED,
                {
                    "code": intake_mod.INTAKE_SNAPSHOT_CHANGED,
                    "presented_hash": presented_hash,
                    "current_hash": current_hash,
                },
                worker_id=KERNEL_WORKER_ID,
            )
            raise ConfirmationStaleError(intake_mod.INTAKE_SNAPSHOT_CHANGED, message)

        confirmed_record = {
            **record.to_dict(),
            "confirmed": True,
            "confirmed_by": confirmed_by,
            "confirmed_snapshot_hash": current_hash,
        }
        snapshot = {**dict(run.snapshot or {}), SNAPSHOT_INTAKE_KEY: confirmed_record}
        await self._store.update_snapshot(run_id, snapshot, worker_id=KERNEL_WORKER_ID)
        command = await self._store.submit_command(
            command_id or str(self._id_factory()),
            run_id,
            "resume",
            {
                "confirmed_evidence": True,
                "input_snapshot_hash": current_hash,
                "reason_code": record.reason_code,
            },
            confirmed_by,
        )
        await self._store.append_event(
            run_id,
            EVENT_CONFIRMED,
            {
                "code": record.reason_code,
                "missing_evidence_sides": list(record.missing),
                "input_snapshot_hash": current_hash,
                "confirmed_by": confirmed_by,
            },
            worker_id=KERNEL_WORKER_ID,
        )
        return {
            "command_id": command.command_id,
            "input_snapshot_hash": current_hash,
            "missing_evidence_sides": list(record.missing),
        }

    # ------------------------------------------------------------------
    # Completion judgment
    # ------------------------------------------------------------------

    async def evaluate_completion(
        self,
        run_id: str,
        outputs_dir: str,
        *,
        contract_version: str | None = None,
    ) -> KernelCompletion:
        """Judge completion by the Result Contract, not file existence.

        A run completes only when the full five artifacts pass the contract
        pinned for the run.  ``pending_verification`` is a legitimate
        completion status as long as it is fully disclosed by the report —
        it never implies a confirmed root cause.
        """

        run = await self._store.get_run(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        record = _intake_record_from_snapshot(dict(run.snapshot or {}))
        pinned_version = contract_version or (run.snapshot or {}).get(SNAPSHOT_CONTRACT_VERSION_KEY, self._contract_version)

        try:
            verdict = evaluate_result_contract(
                outputs_dir,
                contract_version=pinned_version,
                missing_evidence_sides=record.missing,
            )
        except ContractUnavailableError:
            decision = policy.classify_failure(
                policy.CONTRACT_UNAVAILABLE,
                detail="result contract or bundled schemas cannot be loaded",
            )
            await self._store.append_event(
                run_id,
                EVENT_CONTRACT_FAILED,
                {"code": decision.reason_code, "detail": decision.message},
                worker_id=KERNEL_WORKER_ID,
            )
            raise

        if verdict.ok:
            await self._store.append_event(
                run_id,
                EVENT_CONTRACT_EVALUATED,
                {
                    "code": "contract_passed",
                    "contract_version": verdict.contract_version,
                    "pending_verification_disclosed": _tree_has_pending_verification(outputs_dir),
                },
                worker_id=KERNEL_WORKER_ID,
            )
        else:
            await self._store.append_event(
                run_id,
                EVENT_CONTRACT_FAILED,
                {
                    "code": "contract_failed",
                    "contract_version": verdict.contract_version,
                    "reason_codes": verdict.codes(),
                },
                worker_id=KERNEL_WORKER_ID,
            )

        return KernelCompletion(
            run_id=run_id,
            status=(COMPLETION_STATUS_COMPLETED if verdict.ok else COMPLETION_STATUS_FAILED),
            verdict=verdict,
            reason_codes=verdict.codes(),
            pending_verification=(verdict.ok and _tree_has_pending_verification(outputs_dir)),
        )
