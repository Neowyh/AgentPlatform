"""Skill / Expert / Workflow entry adapters (ticket 04).

All three entries route to the same shared execution kernel with the same
input snapshot, evidence rules, stage policy and contract version.  The
adapters are call+presentation shims ONLY: they never re-implement
fault-zeroing stages or result validation.

Concept explanations and limited edits stay ordinary agent interactions —
an entry only starts a real Run through :func:`start_fault_zeroing_run`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SUPPORTED_ENTRIES = ("skill", "expert", "workflow")


class EntryConfigError(RuntimeError):
    """Raised when an entry name or its routing config is invalid."""


@dataclass(frozen=True)
class EntryAdapter:
    """One call+presentation adapter over the shared kernel."""

    entry: str

    def __post_init__(self) -> None:
        if self.entry not in SUPPORTED_ENTRIES:
            raise EntryConfigError(f"unsupported entry {self.entry!r}; supported: {', '.join(SUPPORTED_ENTRIES)}")

    async def start_run(self, kernel: Any, *, run_inputs: dict[str, Any], created_by: str, **kwargs: Any) -> Any:
        """Route a real Run through the shared kernel seam.

        Every entry passes the identical input snapshot, evidence rules and
        contract pinning — there is deliberately no per-entry branching.
        """

        return await kernel.start_run(
            inputs=dict(run_inputs),
            created_by=created_by,
            **kwargs,
        )


def adapter_for(entry: str) -> EntryAdapter:
    return EntryAdapter(entry)


# ---------------------------------------------------------------------------
# Semantic equivalence extraction (used by the cross-entry acceptance tests).
# ---------------------------------------------------------------------------


def semantic_fields(outputs_dir: str | Path) -> dict[str, Any]:
    """Extract the entry-independent semantic fields of a finished run.

    Two runs are semantically equivalent when these fields agree; wording,
    explanation order and SVG layout are presentation-only and excluded.
    """

    outputs = Path(outputs_dir)
    fields: dict[str, Any] = {}
    try:
        tree = json.loads((outputs / "fault_tree.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        tree = None
    if isinstance(tree, dict):
        fields["top_event"] = tree.get("top_event")
        fields["root_causes"] = sorted(
            (
                {
                    "id": cause.get("id"),
                    "status": cause.get("status"),
                    "confidence": cause.get("confidence"),
                }
                for cause in tree.get("root_causes", [])
                if isinstance(cause, dict)
            ),
            key=lambda item: str(item.get("id")),
        )
        fields["evidence_ids"] = sorted(evidence.get("id") for evidence in tree.get("evidence", []) if isinstance(evidence, dict) and evidence.get("id"))
        fields["verification_targets"] = sorted(
            (
                {
                    "id": item.get("id"),
                    "target_id": item.get("target_id"),
                    "status": item.get("status"),
                }
                for item in tree.get("verification_plan", [])
                if isinstance(item, dict)
            ),
            key=lambda item: str(item.get("id")),
        )

    try:
        report_text = (outputs / "zeroing_report.md").read_text(encoding="utf-8")
    except OSError:
        report_text = ""
    fields["missing_evidence_disclosed"] = [phrase for phrase in ("文档证据未提供", "代码证据包未提供") if phrase in report_text]
    return fields


def semantic_equivalent(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Whether two ``semantic_fields`` results agree on every field."""

    return left == right
