"""Fixed Hybrid Evidence Intake for fault-zeroing runs (ticket 02).

Every new fault-zeroing run accepts document evidence and a Code Evidence
Package side by side.  This module is the single authority for deciding, at
run creation and before any model execution:

- both sides present  -> execute immediately;
- one side missing    -> persistent pause awaiting explicit user
  confirmation bound to the input snapshot;
- both sides missing  -> reject before model execution (no usable run).

Per the CONTEXT.md glossary, a non-empty problem description or any
document-type attachment satisfies the documentary side; the code side
requires a Code Evidence Package.  The evidence mode is a derived system
result (always ``hybrid`` for a run that continues) — it is never a
user-selectable input.

Confirmations are bound to an input snapshot hash: any material added after
confirmation changes the hash and requires re-confirmation.  Runs that
continue with one side missing stay ``hybrid`` and must disclose the gap in
the coverage matrix and residual risks (enforced by the Result Contract via
``missing_evidence_sides``).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

SIDES = ("document_evidence", "code_evidence_package")

# Intake statuses.
EXECUTE = "execute"
PAUSE = "pause"
REJECT = "reject"

# Stable reason codes.
INTAKE_COMPLETE = "intake_evidence_complete"
INTAKE_CONFIRMATION_REQUIRED = "intake_confirmation_required"
INTAKE_MISSING_BOTH = "intake_evidence_missing_both"
INTAKE_SNAPSHOT_CHANGED = "intake_snapshot_changed"

INTERRUPT_TYPE = "evidence_confirmation"

# The evidence mode is a derived system result: every run that continues is
# ``hybrid`` (CONTEXT.md Avoid "Evidence Mode selection", "document-only
# Run", "code-only Run").  It is never a user-selectable input.
DERIVED_EVIDENCE_MODE = "hybrid"


class IntakeError(RuntimeError):
    """Raised when intake inputs are structurally invalid."""


@dataclass(frozen=True)
class EvidenceIntakeDecision:
    """Structured intake decision persisted with the run snapshot."""

    status: str
    evidence_mode: str
    missing: tuple[str, ...]
    reason_code: str
    input_snapshot: dict[str, str]
    input_snapshot_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "evidence_mode": self.evidence_mode,
            "missing": list(self.missing),
            "reason_code": self.reason_code,
            "input_snapshot": dict(self.input_snapshot),
            "input_snapshot_hash": self.input_snapshot_hash,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EvidenceIntakeDecision:
        try:
            return cls(
                status=str(payload["status"]),
                evidence_mode=str(payload["evidence_mode"]),
                missing=tuple(payload["missing"]),
                reason_code=str(payload["reason_code"]),
                input_snapshot=dict(payload["input_snapshot"]),
                input_snapshot_hash=str(payload["input_snapshot_hash"]),
            )
        except (KeyError, TypeError) as exc:
            raise IntakeError(f"invalid evidence intake record: {exc}") from exc


def build_input_snapshot(
    problem_description: str | None,
    upload_dir: str | None,
    code_package_source: str | None,
) -> dict[str, str]:
    """Canonical, comparable snapshot of the two evidence sides.

    Per the Hybrid Evidence Intake glossary, the document side is satisfied
    by a non-empty problem description *or* any document-type attachment
    (proxied at intake by a non-empty ``upload_dir``; the file-level
    manifest is the gateway's domain).  The ``document_evidence`` value is
    therefore the normalized representation of "description and/or path",
    and the confirmation hash is sensitive to a description change: any
    material added after confirmation changes the hash and requires
    re-confirmation.  Adding brand-new files inside an already-declared
    directory does not change this hash; callers that accept additional
    material mid-run should surface it as a new declared input (a new
    path/package id), which does change the hash.
    """

    description = (problem_description or "").strip()
    document_evidence = ""
    if description or upload_dir:
        # JSON encoding keeps the two sources unambiguously separated
        # (a description containing "|" must not collide with a path).
        document_evidence = json.dumps(
            {"problem_description": description, "upload_dir": str(upload_dir) if upload_dir else ""},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return {
        "document_evidence": document_evidence,
        "code_evidence_package": str(code_package_source) if code_package_source else "",
    }


def input_snapshot_hash(snapshot: dict[str, str]) -> str:
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def assess_evidence_intake(
    *,
    problem_description: str | None = None,
    upload_dir: str | None = None,
    code_package_source: str | None = None,
) -> EvidenceIntakeDecision:
    """Decide how a run starts based on the evidence sides it provides.

    The evidence mode is a derived system result, never a user declaration:
    a run that executes is always ``hybrid`` (a missing side stays visible
    in ``missing`` and must be disclosed downstream), so no document-only or
    code-only mode can be resurrected through the derived value.
    """

    snapshot = build_input_snapshot(problem_description, upload_dir, code_package_source)
    snapshot_hash = input_snapshot_hash(snapshot)
    missing = tuple(side for side in SIDES if not snapshot.get(side))

    if len(missing) == len(SIDES):
        # Both sides missing: refuse before any model execution, no usable run.
        return EvidenceIntakeDecision(
            status=REJECT,
            evidence_mode=DERIVED_EVIDENCE_MODE,
            missing=missing,
            reason_code=INTAKE_MISSING_BOTH,
            input_snapshot=snapshot,
            input_snapshot_hash=snapshot_hash,
        )
    if missing:
        # One side missing: persistent pause awaiting user confirmation.
        return EvidenceIntakeDecision(
            status=PAUSE,
            evidence_mode=DERIVED_EVIDENCE_MODE,
            missing=missing,
            reason_code=INTAKE_CONFIRMATION_REQUIRED,
            input_snapshot=snapshot,
            input_snapshot_hash=snapshot_hash,
        )
    return EvidenceIntakeDecision(
        status=EXECUTE,
        evidence_mode=DERIVED_EVIDENCE_MODE,
        missing=(),
        reason_code=INTAKE_COMPLETE,
        input_snapshot=snapshot,
        input_snapshot_hash=snapshot_hash,
    )


def confirmation_is_current(confirmed_snapshot_hash: str | None, current_snapshot_hash: str) -> bool:
    """Whether a prior confirmation still covers the current input snapshot.

    New material added after confirmation changes the snapshot hash and
    requires re-confirmation.
    """

    return bool(confirmed_snapshot_hash) and confirmed_snapshot_hash == current_snapshot_hash


def interrupt_payload(decision: EvidenceIntakeDecision) -> dict[str, Any]:
    """Interrupt payload persisted for the confirmation pause."""

    return {
        "type": INTERRUPT_TYPE,
        "reason_code": decision.reason_code,
        "missing": list(decision.missing),
        "input_snapshot": dict(decision.input_snapshot),
        "input_snapshot_hash": decision.input_snapshot_hash,
        "message": missing_evidence_message(decision.missing),
    }


def missing_evidence_message(missing: tuple[str, ...]) -> str:
    if not missing:
        return ""
    labels = {
        "document_evidence": "文档证据",
        "code_evidence_package": "代码证据包",
    }
    names = "、".join(labels.get(side, side) for side in missing)
    return f"缺少证据侧：{names}。请确认是否在缺失该侧证据的情况下继续归零分析；确认后新增材料需要重新确认。"


def missing_evidence_disclosure(missing: tuple[str, ...]) -> tuple[str, ...]:
    """Disclosure phrases that the report must contain for missing sides."""

    from app.agentplatform.fault_zeroing.contract import EVIDENCE_SIDE_DISCLOSURE

    return tuple(EVIDENCE_SIDE_DISCLOSURE[side] for side in missing if side in EVIDENCE_SIDE_DISCLOSURE)
