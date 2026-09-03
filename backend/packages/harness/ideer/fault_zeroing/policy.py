"""Bounded retry, pause and observable error policy (ticket 05).

One decision table for every failure a fault-zeroing run can hit:

- transient model/network errors  -> bounded provider retry, then pause;
- structural errors               -> at most ONE in-stage repair with the
  concrete violation fed back, then explicit failure;
- missing evidence                -> persistent user-confirmation pause,
  never resolved by model retry;
- semantic conflicts              -> local repair only;
- contract unavailable or repair budget exhausted -> explicit failure.

Every decision carries a stable reason code so each retry, pause, rejection
and failure is diagnosable from the run's event log.
"""

from __future__ import annotations

from dataclasses import dataclass

# Failure kinds (what the runtime observed).
TRANSIENT_PROVIDER_ERROR = "transient_provider_error"
STRUCTURAL_ERROR = "structural_error"
MISSING_EVIDENCE = "missing_evidence"
SEMANTIC_CONFLICT = "semantic_conflict"
CONTRACT_UNAVAILABLE = "contract_unavailable"

# Actions (what the kernel does next).
ACTION_PROVIDER_RETRY = "provider_retry"
ACTION_STAGE_REPAIR = "stage_repair"
ACTION_LOCAL_REPAIR = "local_repair"
ACTION_USER_PAUSE = "user_pause"
ACTION_EXPLICIT_FAILURE = "explicit_failure"

# Stable reason codes attached to every event.
REASON_PROVIDER_RETRY = "provider_retry_scheduled"
REASON_PROVIDER_RETRY_EXHAUSTED = "provider_retry_exhausted"
REASON_STAGE_REPAIR = "stage_repair_scheduled"
REASON_REPAIR_BUDGET_EXHAUSTED = "repair_budget_exhausted"
REASON_USER_PAUSE = "user_confirmation_pause"
REASON_LOCAL_REPAIR = "local_repair_scheduled"
REASON_CONTRACT_UNAVAILABLE = "contract_unavailable"
REASON_EXPLICIT_FAILURE = "explicit_failure"

# Bounds.
PROVIDER_RETRY_BUDGET = 3
STAGE_REPAIR_BUDGET = 1
LOCAL_REPAIR_BUDGET = 1


@dataclass(frozen=True)
class PolicyDecision:
    """One observable policy decision."""

    action: str
    reason_code: str
    kind: str
    message: str

    @property
    def is_terminal(self) -> bool:
        return self.action in (ACTION_USER_PAUSE, ACTION_EXPLICIT_FAILURE)


def classify_failure(
    kind: str,
    *,
    provider_retries_used: int = 0,
    repairs_used: int = 0,
    detail: str = "",
) -> PolicyDecision:
    """Map an observed failure kind to the next bounded action."""

    if kind == TRANSIENT_PROVIDER_ERROR:
        if provider_retries_used < PROVIDER_RETRY_BUDGET:
            return PolicyDecision(
                action=ACTION_PROVIDER_RETRY,
                reason_code=REASON_PROVIDER_RETRY,
                kind=kind,
                message=detail or "transient provider error; retrying with backoff",
            )
        return PolicyDecision(
            action=ACTION_USER_PAUSE,
            reason_code=REASON_PROVIDER_RETRY_EXHAUSTED,
            kind=kind,
            message=detail or "provider retry budget exhausted; pausing for operator",
        )

    if kind == STRUCTURAL_ERROR:
        if repairs_used < STAGE_REPAIR_BUDGET:
            return PolicyDecision(
                action=ACTION_STAGE_REPAIR,
                reason_code=REASON_STAGE_REPAIR,
                kind=kind,
                message=detail or "structural error; one in-stage repair with concrete reasons",
            )
        return PolicyDecision(
            action=ACTION_EXPLICIT_FAILURE,
            reason_code=REASON_REPAIR_BUDGET_EXHAUSTED,
            kind=kind,
            message=detail or "structural repair budget exhausted; failing explicitly",
        )

    if kind == MISSING_EVIDENCE:
        return PolicyDecision(
            action=ACTION_USER_PAUSE,
            reason_code=REASON_USER_PAUSE,
            kind=kind,
            message=detail or "missing evidence requires user confirmation; never retried by the model",
        )

    if kind == SEMANTIC_CONFLICT:
        if repairs_used < LOCAL_REPAIR_BUDGET:
            return PolicyDecision(
                action=ACTION_LOCAL_REPAIR,
                reason_code=REASON_LOCAL_REPAIR,
                kind=kind,
                message=detail or "semantic conflict; local repair only",
            )
        return PolicyDecision(
            action=ACTION_EXPLICIT_FAILURE,
            reason_code=REASON_REPAIR_BUDGET_EXHAUSTED,
            kind=kind,
            message=detail or "local repair budget exhausted; failing explicitly",
        )

    if kind == CONTRACT_UNAVAILABLE:
        return PolicyDecision(
            action=ACTION_EXPLICIT_FAILURE,
            reason_code=REASON_CONTRACT_UNAVAILABLE,
            kind=kind,
            message=detail or "result contract unavailable; failing explicitly",
        )

    return PolicyDecision(
        action=ACTION_EXPLICIT_FAILURE,
        reason_code=REASON_EXPLICIT_FAILURE,
        kind=kind,
        message=detail or f"unclassified failure {kind!r}; failing explicitly",
    )
