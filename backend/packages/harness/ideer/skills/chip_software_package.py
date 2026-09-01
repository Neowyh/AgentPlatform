"""Conservative extraction and evidence gates for chip software source sets.

The module consumes text already read from source documents.  It deliberately
does not parse PDFs or infer facts: document reading remains the responsibility
of the user-facing Skill and every extracted value must carry its source.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

_TOPICS = (
    "startup_reset",
    "clock",
    "memory",
    "pin_mux",
    "peripheral",
    "register",
    "interrupt",
    "dma",
    "errata_impact",
)
_SUPPORTED_DOCUMENT_TYPES = {"datasheet", "reference_manual", "programming_manual", "errata"}
_PIN_FIELDS = ("pin", "signal", "alternate_function", "peripheral", "interrupt", "source")
_PART_RE = re.compile(r"^\s*([^=|]+?)\s*=\s*(.*?)\s*(?:\||$)")


@dataclass(frozen=True)
class ChipSoftwareDocument:
    name: str
    document_type: str
    part_number: str
    package: str
    source_location: str
    text: str
    is_native_text: bool = True


@dataclass(frozen=True)
class SourceSetValidation:
    accepted: bool
    target_part: str
    target_package: str
    accepted_documents: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()


@dataclass
class ChipSoftwarePackage:
    validation: SourceSetValidation
    structured_rows: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)

    @property
    def confirmed_rows(self) -> list[dict[str, Any]]:
        return [row for row in self.structured_rows if row["confidence"] == "confirmed"]


def validate_source_set(documents: list[ChipSoftwareDocument], *, target_part: str, target_package: str) -> SourceSetValidation:
    issues: list[str] = []
    accepted_documents: list[str] = []
    present_types: set[str] = set()
    for document in documents:
        if not document.is_native_text:
            issues.append(f"{document.name}: source is not native text; scanned/OCR input is unsupported")
            continue
        if document.part_number != target_part:
            issues.append(f"{document.name}: part {document.part_number} does not match target {target_part}")
            continue
        if document.package != target_package:
            issues.append(f"{document.name}: package {document.package} does not match target {target_package}")
            continue
        if document.document_type not in _SUPPORTED_DOCUMENT_TYPES:
            issues.append(f"{document.name}: unsupported document type {document.document_type}")
            continue
        accepted_documents.append(document.name)
        present_types.add(document.document_type)

    gaps: list[str] = []
    if "datasheet" not in present_types:
        gaps.append("datasheet")
    if not present_types.intersection({"reference_manual", "programming_manual"}):
        gaps.append("reference_manual_or_programming_manual")
    if "errata" not in present_types:
        gaps.append("errata")
    return SourceSetValidation(
        accepted=not issues,
        target_part=target_part,
        target_package=target_package,
        accepted_documents=tuple(accepted_documents),
        issues=tuple(issues),
        gaps=tuple(gaps),
    )


def extract_chip_software_package(documents: list[ChipSoftwareDocument], *, target_part: str, target_package: str) -> ChipSoftwarePackage:
    validation = validate_source_set(documents, target_part=target_part, target_package=target_package)
    valid_documents = [document for document in documents if document.is_native_text and document.part_number == target_part and document.package == target_package and document.document_type in _SUPPORTED_DOCUMENT_TYPES]
    rows: list[dict[str, Any]] = []
    for document in valid_documents:
        rows.extend(_extract_document_rows(document, target_package))
    _apply_conflict_gate(rows)
    result = ChipSoftwarePackage(validation=validation, structured_rows=rows)
    result.artifacts = {
        "embedded-software-knowledge-brief.md": _render_brief(result),
        "chip-software-table.json": json.dumps(
            {"target": {"part": target_part, "package": target_package}, "rows": rows},
            ensure_ascii=False,
            indent=2,
        ),
    }
    return result


def _extract_document_rows(document: ChipSoftwareDocument, package: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(document.text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("PIN:"):
            values = _parse_fields(line.removeprefix("PIN:").strip(), first_key="pin")
            row = {field: values.get(field, "") for field in _PIN_FIELDS}
            row.update({"package": package, "topic": "pin_mux", "confidence": "confirmed"})
            row["source"] = values.get("source") or f"{document.name} (line {line_number})"
            if any(not row[field] for field in _PIN_FIELDS if field != "source"):
                row["confidence"] = "review_required"
                row["review_note"] = "incomplete extracted record; 需人工复核"
            rows.append(row)
        elif line.startswith("TOPIC:"):
            values = _parse_fields(line.removeprefix("TOPIC:").strip(), first_key="topic")
            topic = values.get("topic", "")
            if topic not in _TOPICS:
                continue
            row = {
                **{field: "" for field in _PIN_FIELDS},
                "topic": topic,
                "claim": values.get("claim", ""),
                "source": values.get("source") or f"{document.name} (line {line_number})",
                "package": package,
                "confidence": "confirmed",
            }
            if not row["claim"]:
                row["confidence"] = "review_required"
                row["review_note"] = "incomplete extracted record; 需人工复核"
            rows.append(row)
    return rows


def _parse_fields(value: str, *, first_key: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    parts = [part.strip() for part in value.split("|")]
    if parts and "=" not in parts[0]:
        fields[first_key] = parts.pop(0)
    if first_key == "topic" and parts and "=" not in parts[0]:
        fields["claim"] = parts.pop(0)
    for part in parts:
        match = _PART_RE.match(f"{part}|")
        if match:
            fields[match.group(1).strip()] = match.group(2).strip()
    return fields


def _apply_conflict_gate(rows: list[dict[str, Any]]) -> None:
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row.get("topic", ""), row.get("pin", ""))
        if key[0] and (key[1] or row.get("claim")):
            by_key.setdefault(key, []).append(row)
    for key, conflicting_rows in by_key.items():
        if key[1]:
            signatures = {tuple(row.get(field, "") for field in ("signal", "alternate_function", "peripheral", "interrupt")) for row in conflicting_rows}
        else:
            signatures = {row.get("claim", "") for row in conflicting_rows}
        if len(signatures) > 1:
            for row in conflicting_rows:
                row["confidence"] = "review_required"
                row["review_note"] = "conflicting source evidence; 需人工复核"


def _render_brief(result: ChipSoftwarePackage) -> str:
    validation = result.validation
    lines = [
        "# Embedded software knowledge brief",
        "",
        f"- Target part: `{validation.target_part}`",
        f"- Target package: `{validation.target_package}`",
        f"- Accepted source documents: {', '.join(validation.accepted_documents) or 'none'}",
        "- Scope: startup/reset, clock, memory, pin mux, peripherals, registers, interrupts, DMA and errata.",
        "",
        "## Evidence status",
        "",
        "`confirmed` is directly supported by a consistent source location. `review_required` is visible but must not be consumed as an automated fact.",
        "",
    ]
    for row in result.structured_rows:
        label = row.get("claim") or f"{row.get('pin')}: {row.get('signal')}"
        note = f"; {row['review_note']}" if row.get("review_note") else ""
        lines.append(f"- `{row['confidence']}` — {row.get('topic', 'pin_mux')}: {label} ([{row['source']}]){note}")
    lines.extend(["", "## 资料缺口", ""])
    if validation.gaps:
        lines.extend(f"- `{gap}`" for gap in validation.gaps)
    else:
        lines.append("- None identified")
    if validation.issues:
        lines.extend(["", "## Source set rejection", ""])
        lines.extend(f"- {issue}" for issue in validation.issues)
    lines.extend(
        [
            "",
            "## Use boundary",
            "",
            "Only `confirmed` structured rows may be consumed by downstream automation. This package does not generate board-ready initialization code or infer board-level prerequisites.",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "ChipSoftwareDocument",
    "ChipSoftwarePackage",
    "SourceSetValidation",
    "extract_chip_software_package",
    "validate_source_set",
]
