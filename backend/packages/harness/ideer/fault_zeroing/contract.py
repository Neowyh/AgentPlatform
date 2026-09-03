"""Versioned, immutable Result Contract for fault-zeroing runs.

This module is the single source of truth for judging whether a set of
fault-zeroing output artifacts is structurally complete, reference-closed,
evidence-sufficient, status-consistent and safe.  It is intentionally
stdlib-only so that it can be consumed by:

- the offline CLI shim ``scripts/validate_fault_zeroing_outputs.py``;
- the shared execution kernel (``ideer.fault_zeroing.kernel``) quality gates;
- downstream automation that may only consume ``confirmed`` facts.

Contract versioning: ``CONTRACT_VERSION`` is bumped together with the
bundled schemas and the semantic rules encoded below.  Callers may pin a
contract version per run; unsupported versions yield an explicit
``contract_version_unsupported`` finding instead of silently drifting.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "1.0.0"
SUPPORTED_CONTRACT_VERSIONS = ("1.0.0",)

REQUIRED_OUTPUTS = (
    "fault_tree.json",
    "fault_tree.svg",
    "bottom_event_assessment.md",
    "analysis_process.svg",
    "zeroing_report.md",
)
REQUIRED_COVERAGE = (
    "问题描述",
    "设计约束",
    "试验记录或日志",
    "总结报告",
    "历史或复核记录",
)
REQUIRED_REPORT_SECTIONS = (
    "问题概述",
    "输入资料",
    "故障现象",
    "故障树分析",
    "底事件评估",
    "根因归因",
    "验证计划",
    "纠正措施",
    "遗留风险",
    "证据引用",
)
REQUIRED_REPORT_KEY_PHRASES = (
    "资料覆盖矩阵",
    "证据台账摘要",
    "待验证项",
    "遗留风险",
)
REQUIRED_STAGE_MARKERS = (
    "证据提取",
    "故障树构建",
    "底事件评估",
    "根因归因",
    "纠正措施",
    "文档生产",
)
REQUIRED_RESPONSIBILITY_PHRASES = (
    "演绎建树阶段不依赖证据台账",
    "证据检漏只做添加不做删除",
    "文档阶段不修改分析数据",
)
FORBIDDEN_RESPONSIBILITY_CLAIMS = (
    "演绎建树阶段依赖证据台账",
    "证据检漏删除已有证据",
    "文档阶段修改分析数据",
)
STATUS_VALUES = {"confirmed", "rejected", "to_verify", "not_applicable"}
VERIFICATION_STATUS_VALUES = {"pending", "in_progress", "passed", "failed", "blocked"}
# Unified with resources/skills/fault-zeroing/templates/fault_tree.schema.json
# $defs.confidence: mixes classic confidence levels with the Code Evidence
# Package "Finding Confidence" values.  Both schema gate and this contract
# must accept exactly the same set (anti-drift rule).
CONFIDENCE_VALUES = {
    "confirmed",
    "high_risk_candidate",
    "pending_verification",
    "high",
    "medium",
    "low",
    "unknown",
}
EVIDENCE_GRADES = {"A", "B", "C", "D"}
AB_GRADES = {"A", "B"}
CD_GRADES = {"C", "D"}
ROOT_CAUSE_STATUSES = {"confirmed"}
EVIDENCE_ID_PATTERN = re.compile(r"\bEV-[A-Za-z0-9_-]+\b")
EXPECTED_ANALYSIS_PATTERN = re.compile(
    r"(?:^|[/\\])[^/\\]*_expected_analysis\.md(?=$|[^\w./\\-]|第)",
    re.IGNORECASE,
)
# Hybrid evidence intake: when a run proceeds with one evidence side missing,
# the report must disclose the gap both in the coverage matrix and in the
# residual-risks section (stable disclosure phrases, shared with intake.py).
EVIDENCE_SIDE_DISCLOSURE = {
    "document_evidence": "文档证据未提供",
    "code_evidence_package": "代码证据包未提供",
}


class ContractUnavailableError(RuntimeError):
    """Raised when the contract or its bundled schemas cannot be loaded."""


@dataclass(frozen=True)
class ContractFinding:
    """One structured contract finding with a stable reason code."""

    code: str
    message: str
    artifact: str = ""
    location: str = ""
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "artifact": self.artifact,
            "location": self.location,
            "severity": self.severity,
        }


@dataclass
class ContractVerdict:
    """Structured, machine-readable contract judgment for one artifact set."""

    contract_version: str
    contract_fingerprint: str
    findings: list[ContractFinding] = field(default_factory=list)
    artifact_digests: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not any(finding.severity == "error" for finding in self.findings)

    @property
    def errors(self) -> list[str]:
        """Human-readable error messages (legacy validator text contract)."""
        return [finding.message for finding in self.findings if finding.severity == "error"]

    def codes(self) -> list[str]:
        return [finding.code for finding in self.findings]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "contract_fingerprint": self.contract_fingerprint,
            "ok": self.ok,
            "findings": [finding.to_dict() for finding in self.findings],
            "artifact_digests": dict(self.artifact_digests),
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class _Sink:
    """Finding collector passed through the check pipeline."""

    def __init__(self) -> None:
        self.findings: list[ContractFinding] = []

    def add(
        self,
        code: str,
        message: str,
        artifact: str = "",
        location: str = "",
        severity: str = "error",
    ) -> None:
        self.findings.append(
            ContractFinding(
                code=code,
                message=message,
                artifact=artifact,
                location=location,
                severity=severity,
            )
        )


def _repo_root() -> Path:
    # backend/packages/harness/ideer/fault_zeroing/contract.py -> repo root
    return Path(__file__).resolve().parents[5]


def default_schema_path(repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else _repo_root()
    return root / "resources" / "skills" / "fault-zeroing" / "templates" / "fault_tree.schema.json"


def default_corrective_schema_path(repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else _repo_root()
    return root / "resources" / "skills" / "fault-zeroing" / "templates" / "corrective_actions.schema.json"


def contract_fingerprint(schema_path: Path, corrective_schema_path: Path | None = None) -> str:
    """Stable fingerprint of the contract version plus bundled schemas."""

    digest = hashlib.sha256()
    digest.update(f"contract-version:{CONTRACT_VERSION}\n".encode())
    for path in (schema_path, corrective_schema_path):
        if path is None or not Path(path).is_file():
            continue
        digest.update(f"schema:{path.name}\n".encode())
        try:
            digest.update(Path(path).read_bytes())
        except OSError:
            continue
    return digest.hexdigest()


def _read_text(path: Path, sink: _Sink) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        sink.add("artifact_not_utf8", f"{path.name} is not valid UTF-8", artifact=path.name)
    except OSError as exc:
        sink.add("artifact_unreadable", f"{path.name} cannot be read: {exc}", artifact=path.name)
    return ""


def _load_json(path: Path, sink: _Sink) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sink.add("json_invalid", f"{path.name} is invalid JSON: {exc}", artifact=path.name)
        return None
    except OSError as exc:
        sink.add("artifact_unreadable", f"{path.name} cannot be read: {exc}", artifact=path.name)
        return None
    if not isinstance(value, dict):
        sink.add("json_root_not_object", f"{path.name} root must be an object", artifact=path.name)
        return None
    return value


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _id_list(value: Any) -> list[str]:
    return [item for item in _list(value) if isinstance(item, str)]


def _node_id(node: Any) -> str:
    return _string(node.get("id")) if isinstance(node, dict) else ""


def _evidence_ids_for(item: dict[str, Any]) -> list[str]:
    if "evidence_ids" in item:
        return _id_list(item.get("evidence_ids"))
    return _id_list(item.get("evidence"))


def _is_expected_analysis_source(source: str) -> bool:
    return bool(EXPECTED_ANALYSIS_PATTERN.search(source))


def _require_keys(obj: dict[str, Any], keys: tuple[str, ...], prefix: str, sink: _Sink, artifact: str) -> None:
    for key in keys:
        if key not in obj:
            sink.add(
                "tree_key_missing",
                f"{prefix} missing required key {key}",
                artifact=artifact,
                location=prefix,
            )


def _validate_required_files(outputs_dir: Path, sink: _Sink) -> None:
    for name in REQUIRED_OUTPUTS:
        path = outputs_dir / name
        if not path.exists():
            sink.add("output_missing", f"{name} is missing", artifact=name)
            continue
        if not path.is_file():
            sink.add("output_not_file", f"{name} is not a file", artifact=name)
            continue
        if path.stat().st_size == 0:
            sink.add("output_empty", f"{name} is empty", artifact=name)


def _validate_schema_presence(schema_path: Path, sink: _Sink) -> dict[str, Any] | None:
    schema = _load_json(schema_path, sink)
    if not schema:
        return None
    for key in (
        "top_event",
        "intermediate_events",
        "bottom_events",
        "logic",
        "evidence",
        "root_causes",
        "verification_plan",
    ):
        if key not in schema.get("properties", {}):
            sink.add(
                "schema_property_missing",
                f"schema missing property {key}",
                artifact=schema_path.name,
            )
    return schema


def _validate_json_schema(
    value: Any,
    schema: dict[str, Any],
    sink: _Sink,
    path: str = "fault_tree.json",
    root_schema: dict[str, Any] | None = None,
) -> None:
    root = root_schema or schema
    ref = schema.get("$ref")
    if isinstance(ref, str):
        resolved = _resolve_schema_ref(ref, root)
        if resolved is None:
            sink.add(
                "schema_ref_unresolved",
                f"fault_tree.json schema violation at {path}: unresolved schema ref {ref}",
                artifact=path.split(".")[0] + ".json" if "." in path else path,
                location=path,
            )
            return
        _validate_json_schema(value, resolved, sink, path, root)
        return

    if "enum" in schema and value not in _list(schema.get("enum")):
        sink.add(
            "schema_violation",
            f"fault_tree.json schema violation at {path}: value {value!r} is not allowed",
            artifact=path,
            location=path,
        )
        return

    expected_type = schema.get("type")
    if expected_type is not None and not _matches_schema_type(value, expected_type):
        expected = "/".join(expected_type) if isinstance(expected_type, list) else str(expected_type)
        sink.add(
            "schema_violation",
            f"fault_tree.json schema violation at {path}: expected {expected}",
            artifact=path,
            location=path,
        )
        return

    min_length = schema.get("minLength")
    if isinstance(value, str) and isinstance(min_length, int) and len(value) < min_length:
        sink.add(
            "schema_violation",
            f"fault_tree.json schema violation at {path}: string shorter than minLength {min_length}",
            artifact=path,
            location=path,
        )
        return

    if isinstance(value, dict):
        for key in _id_list(schema.get("required")):
            if key not in value:
                sink.add(
                    "schema_violation",
                    f"fault_tree.json schema violation at {path}: missing required key {key}",
                    artifact=path,
                    location=path,
                )
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    _validate_json_schema(value[key], child_schema, sink, f"{path}.{key}", root)
    elif isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate_json_schema(item, item_schema, sink, f"{path}[{index}]", root)


def _resolve_schema_ref(ref: str, root_schema: dict[str, Any]) -> dict[str, Any] | None:
    if not ref.startswith("#/"):
        return None
    current: Any = root_schema
    for segment in ref.removeprefix("#/").split("/"):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current if isinstance(current, dict) else None


def _matches_schema_type(value: Any, expected_type: Any) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_schema_type(value, item) for item in expected_type)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def _validate_fault_tree_shape(tree: dict[str, Any], sink: _Sink) -> None:
    artifact = "fault_tree.json"
    _require_keys(
        tree,
        (
            "top_event",
            "intermediate_events",
            "bottom_events",
            "logic",
            "evidence",
            "root_causes",
            "verification_plan",
        ),
        "fault_tree.json",
        sink,
        artifact,
    )
    if not _string(tree.get("top_event")).strip():
        sink.add(
            "tree_field_invalid",
            "fault_tree.json top_event is empty",
            artifact=artifact,
            location="top_event",
        )

    for list_key in (
        "intermediate_events",
        "bottom_events",
        "logic",
        "evidence",
        "root_causes",
        "verification_plan",
    ):
        if list_key in tree and not isinstance(tree.get(list_key), list):
            sink.add(
                "tree_list_invalid",
                f"fault_tree.json {list_key} must be a list",
                artifact=artifact,
                location=list_key,
            )

    for event in _list(tree.get("intermediate_events")):
        if not isinstance(event, dict):
            sink.add("tree_event_invalid", "intermediate event must be an object", artifact=artifact)
            continue
        event_id = _string(event.get("id")) or "<missing>"
        _require_keys(
            event,
            ("id", "name", "description", "parent_ids", "logic"),
            f"intermediate event {event_id}",
            sink,
            artifact,
        )

    for event in _list(tree.get("bottom_events")):
        if not isinstance(event, dict):
            sink.add("tree_event_invalid", "bottom event must be an object", artifact=artifact)
            continue
        event_id = _string(event.get("id")) or "<missing>"
        location = f"bottom_events.{event_id}"
        _require_keys(
            event,
            (
                "id",
                "name",
                "description",
                "parent_ids",
                "evidence_ids",
                "probability",
                "probability_basis",
                "confidence",
                "status",
                "verification_suggestion",
            ),
            f"bottom event {event_id}",
            sink,
            artifact,
        )
        if _string(event.get("status")) not in STATUS_VALUES:
            sink.add(
                "status_invalid",
                f"bottom event {event_id} has invalid status {_string(event.get('status'))}",
                artifact=artifact,
                location=location,
            )
        if _string(event.get("confidence")) not in CONFIDENCE_VALUES:
            sink.add(
                "confidence_invalid",
                f"bottom event {event_id} has invalid confidence {_string(event.get('confidence'))}",
                artifact=artifact,
                location=location,
            )
        if not _string(event.get("description")).strip() or not _string(event.get("verification_suggestion")).strip():
            sink.add(
                "verifiable_object_missing",
                f"bottom event {event_id} lacks verifiable object or condition",
                artifact=artifact,
                location=location,
            )
        if isinstance(event.get("probability"), int | float) and event.get("probability_basis") in (None, ""):
            sink.add(
                "probability_basis_missing",
                f"numeric probability for {event_id} lacks probability_basis",
                artifact=artifact,
                location=location,
            )

    for evidence in _list(tree.get("evidence")):
        if not isinstance(evidence, dict):
            sink.add("tree_event_invalid", "evidence entry must be an object", artifact=artifact)
            continue
        evidence_id = _string(evidence.get("id")) or "<missing>"
        _require_keys(
            evidence,
            ("id", "source", "grade", "type", "summary", "supports", "contradicts"),
            f"evidence {evidence_id}",
            sink,
            artifact,
        )
        if _string(evidence.get("grade")) not in EVIDENCE_GRADES:
            sink.add(
                "grade_invalid",
                f"evidence {evidence_id} has invalid grade {_string(evidence.get('grade'))}",
                artifact=artifact,
                location=f"evidence.{evidence_id}",
            )
        source = _string(evidence.get("source"))
        if _is_expected_analysis_source(source):
            sink.add(
                "evidence_source_forbidden",
                f"expected-analysis files cannot be used as evidence: {source}",
                artifact=artifact,
                location=f"evidence.{evidence_id}.source",
            )

    for root_cause in _list(tree.get("root_causes")):
        if not isinstance(root_cause, dict):
            sink.add("tree_event_invalid", "root cause must be an object", artifact=artifact)
            continue
        cause_id = _string(root_cause.get("id")) or "<missing>"
        location = f"root_causes.{cause_id}"
        _require_keys(
            root_cause,
            ("id", "name", "description", "evidence_ids", "status", "confidence"),
            f"root cause {cause_id}",
            sink,
            artifact,
        )
        if _string(root_cause.get("status")) not in STATUS_VALUES:
            sink.add(
                "status_invalid",
                f"root cause {cause_id} has invalid status {_string(root_cause.get('status'))}",
                artifact=artifact,
                location=location,
            )
        if _string(root_cause.get("confidence")) not in CONFIDENCE_VALUES:
            sink.add(
                "confidence_invalid",
                f"root cause {cause_id} has invalid confidence {_string(root_cause.get('confidence'))}",
                artifact=artifact,
                location=location,
            )

    for item in _list(tree.get("verification_plan")):
        if not isinstance(item, dict):
            sink.add("tree_event_invalid", "verification item must be an object", artifact=artifact)
            continue
        item_id = _string(item.get("id")) or "<missing>"
        _require_keys(
            item,
            ("id", "target_id", "item", "method", "expected_result", "status"),
            f"verification item {item_id}",
            sink,
            artifact,
        )
        if _string(item.get("status")) not in VERIFICATION_STATUS_VALUES:
            sink.add(
                "verification_status_invalid",
                f"verification item {item_id} has invalid status {_string(item.get('status'))}",
                artifact=artifact,
                location=f"verification_plan.{item_id}",
            )


def _validate_references(tree: dict[str, Any], report_text: str, sink: _Sink) -> None:
    artifact = "fault_tree.json"
    node_ids = {"TOP"}
    for key in ("intermediate_events", "bottom_events"):
        for node in _list(tree.get(key)):
            node_id = _node_id(node)
            if node_id:
                node_ids.add(node_id)

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for evidence in _list(tree.get("evidence")):
        if not isinstance(evidence, dict):
            continue
        evidence_id = _string(evidence.get("id"))
        if not evidence_id:
            continue
        if evidence_id in evidence_by_id:
            sink.add(
                "evidence_id_duplicate",
                f"duplicate evidence id {evidence_id}",
                artifact=artifact,
                location=f"evidence.{evidence_id}",
            )
        evidence_by_id[evidence_id] = evidence

    for key in ("intermediate_events", "bottom_events"):
        for node in _list(tree.get(key)):
            if not isinstance(node, dict):
                continue
            node_id = _string(node.get("id")) or "<missing>"
            for parent_id in _id_list(node.get("parent_ids")):
                if parent_id not in node_ids:
                    sink.add(
                        "parent_reference_unresolved",
                        f"{node_id} references unknown parent_id {parent_id}",
                        artifact=artifact,
                        location=node_id,
                    )

    for logic in _list(tree.get("logic")):
        if not isinstance(logic, dict):
            continue
        for key in ("source", "target", "parent"):
            ref = _string(logic.get(key))
            if ref and ref not in node_ids:
                sink.add(
                    "logic_reference_unresolved",
                    f"logic references unknown node {ref}",
                    artifact=artifact,
                )
        for child in _id_list(logic.get("children")):
            if child not in node_ids:
                sink.add(
                    "logic_reference_unresolved",
                    f"logic references unknown node {child}",
                    artifact=artifact,
                )

    referenced_evidence: list[tuple[str, str]] = []
    for node in _list(tree.get("bottom_events")):
        if isinstance(node, dict):
            referenced_evidence.extend((_string(node.get("id")) or "<missing>", evidence_id) for evidence_id in _evidence_ids_for(node))
    for root_cause in _list(tree.get("root_causes")):
        if isinstance(root_cause, dict):
            referenced_evidence.extend((_string(root_cause.get("id")) or "<missing>", evidence_id) for evidence_id in _evidence_ids_for(root_cause))
    for owner, evidence_id in referenced_evidence:
        if evidence_id not in evidence_by_id:
            sink.add(
                "evidence_reference_unresolved",
                f"{owner} references unknown evidence id {evidence_id}",
                artifact=artifact,
                location=owner,
            )

    for evidence_id in EVIDENCE_ID_PATTERN.findall(report_text):
        if evidence_id not in evidence_by_id:
            sink.add(
                "report_reference_unresolved",
                f"report references unknown evidence id {evidence_id}",
                artifact="zeroing_report.md",
            )

    event_ids = node_ids | {_string(cause.get("id")) for cause in _list(tree.get("root_causes")) if isinstance(cause, dict)}
    for evidence in evidence_by_id.values():
        for key in ("supports", "contradicts"):
            for target_id in _id_list(evidence.get(key)):
                if target_id and target_id not in event_ids:
                    sink.add(
                        "evidence_target_unresolved",
                        f"evidence {_string(evidence.get('id'))} {key} unknown target {target_id}",
                        artifact=artifact,
                    )

    for item in _list(tree.get("verification_plan")):
        if not isinstance(item, dict):
            continue
        item_id = _string(item.get("id")) or "<missing>"
        target_id = _string(item.get("target_id"))
        if target_id and target_id not in event_ids:
            sink.add(
                "verification_target_unresolved",
                f"verification item {item_id} references unknown target_id {target_id}",
                artifact=artifact,
                location=f"verification_plan.{item_id}",
            )


def _grades_for(evidence_ids: list[str], evidence_by_id: dict[str, dict[str, Any]]) -> set[str]:
    return {_string(evidence_by_id.get(evidence_id, {}).get("grade")) for evidence_id in evidence_ids}


def _has_counterevidence(event_id: str, evidence_by_id: dict[str, dict[str, Any]]) -> bool:
    return any(event_id in _id_list(evidence.get("contradicts")) for evidence in evidence_by_id.values())


def _validate_evidence_strength(tree: dict[str, Any], sink: _Sink) -> None:
    artifact = "fault_tree.json"
    evidence_by_id = {_string(evidence.get("id")): evidence for evidence in _list(tree.get("evidence")) if isinstance(evidence, dict) and _string(evidence.get("id"))}

    for event in _list(tree.get("bottom_events")):
        if not isinstance(event, dict):
            continue
        event_id = _string(event.get("id")) or "<missing>"
        evidence_ids = _evidence_ids_for(event)
        grades = _grades_for(evidence_ids, evidence_by_id)
        status = _string(event.get("status"))
        if status == "confirmed" and not grades.intersection(AB_GRADES):
            sink.add(
                "evidence_strength_insufficient",
                f"{event_id} is confirmed with only C/D evidence",
                artifact=artifact,
                location=f"bottom_events.{event_id}",
            )
        if status == "rejected" and not _has_counterevidence(event_id, evidence_by_id):
            sink.add(
                "counterevidence_missing",
                f"rejected bottom event {event_id} lacks counterevidence",
                artifact=artifact,
                location=f"bottom_events.{event_id}",
            )

    for root_cause in _list(tree.get("root_causes")):
        if not isinstance(root_cause, dict):
            continue
        cause_id = _string(root_cause.get("id")) or "<missing>"
        evidence_ids = _evidence_ids_for(root_cause)
        grades = _grades_for(evidence_ids, evidence_by_id)
        status = _string(root_cause.get("status"))
        confidence = _string(root_cause.get("confidence"))
        if status in ROOT_CAUSE_STATUSES and not grades.intersection(AB_GRADES):
            sink.add(
                "evidence_strength_insufficient",
                f"confirmed root cause {cause_id} lacks A/B evidence",
                artifact=artifact,
                location=f"root_causes.{cause_id}",
            )
        if status in ROOT_CAUSE_STATUSES and grades and grades.issubset(CD_GRADES):
            sink.add(
                "evidence_strength_insufficient",
                f"confirmed root cause {cause_id} is supported only by C/D evidence",
                artifact=artifact,
                location=f"root_causes.{cause_id}",
            )
        if confidence == "high" and not grades.intersection(AB_GRADES):
            sink.add(
                "evidence_strength_insufficient",
                f"high-confidence root cause {cause_id} lacks A/B evidence",
                artifact=artifact,
                location=f"root_causes.{cause_id}",
            )


def _validate_report(report_text: str, tree: dict[str, Any], sink: _Sink) -> None:
    artifact = "zeroing_report.md"
    for section in REQUIRED_REPORT_SECTIONS:
        if section not in report_text:
            sink.add(
                "report_section_missing",
                f"zeroing_report.md missing section {section}",
                artifact=artifact,
            )
    for phrase in REQUIRED_REPORT_KEY_PHRASES:
        if phrase not in report_text:
            sink.add(
                "report_phrase_missing",
                f"zeroing_report.md missing {phrase}",
                artifact=artifact,
            )
    for marker in REQUIRED_STAGE_MARKERS:
        if marker not in report_text:
            sink.add(
                "stage_marker_missing",
                f"zeroing_report.md missing stage marker {marker}",
                artifact=artifact,
            )
    for phrase in REQUIRED_RESPONSIBILITY_PHRASES:
        if phrase not in report_text:
            sink.add(
                "responsibility_missing",
                f"zeroing_report.md missing subagent responsibility statement: {phrase}",
                artifact=artifact,
            )
    for claim in FORBIDDEN_RESPONSIBILITY_CLAIMS:
        if claim in report_text:
            sink.add(
                "forbidden_claim",
                f"zeroing_report.md contains forbidden subagent claim: {claim}",
                artifact=artifact,
            )

    coverage_rows = _coverage_matrix_rows(report_text)
    missing_coverage = [category for category in REQUIRED_COVERAGE if not any(category in row for row in coverage_rows)]
    if missing_coverage:
        sink.add(
            "coverage_matrix_incomplete",
            f"资料覆盖矩阵缺少：{'、'.join(missing_coverage)}",
            artifact=artifact,
            location="资料覆盖矩阵",
        )

    top_event = _string(tree.get("top_event")).strip()
    report_top_event = _extract_labeled_value(report_text, "顶事件")
    if top_event and report_top_event and report_top_event != top_event:
        sink.add(
            "report_mismatch",
            "report top event does not match fault_tree.json",
            artifact=artifact,
        )
    elif top_event and not report_top_event and top_event not in report_text:
        sink.add(
            "report_mismatch",
            "report top event does not match fault_tree.json",
            artifact=artifact,
        )

    confirmed_roots = [root for root in _list(tree.get("root_causes")) if isinstance(root, dict) and _string(root.get("status")) == "confirmed"]
    if confirmed_roots:
        first_root_name = _string(confirmed_roots[0].get("name")).strip()
        report_root = _extract_labeled_value(report_text, "主根因")
        if first_root_name and report_root and report_root != first_root_name:
            sink.add(
                "report_mismatch",
                "report main root cause does not match fault_tree.json",
                artifact=artifact,
            )
        elif first_root_name and not report_root and first_root_name not in report_text:
            sink.add(
                "report_mismatch",
                "report main root cause does not match fault_tree.json",
                artifact=artifact,
            )

    expected_verification_ids = {_string(item.get("id")) for item in _list(tree.get("verification_plan")) if isinstance(item, dict) and _string(item.get("id"))}
    pending_verification_ids = {_string(item.get("id")) for item in _list(tree.get("verification_plan")) if isinstance(item, dict) and _string(item.get("status")) == "pending" and _string(item.get("id"))}
    report_verification_ids = _verification_plan_ids(report_text)
    report_verification_id_set = set(report_verification_ids)
    for item_id in report_verification_id_set - expected_verification_ids:
        sink.add(
            "report_verification_mismatch",
            f"report references unknown verification item id {item_id}",
            artifact=artifact,
        )
    for item_id in pending_verification_ids:
        count = report_verification_ids.count(item_id)
        if count == 0:
            sink.add(
                "report_verification_mismatch",
                f"report missing pending verification item {item_id}",
                artifact=artifact,
            )
        elif count > 1:
            sink.add(
                "report_verification_mismatch",
                f"report contains duplicate verification item id {item_id}",
                artifact=artifact,
            )

    missing_rows = [line for line in coverage_rows if "缺失" in line or "未提供" in line or "未覆盖" in line]
    if missing_rows:
        input_section = _section_text(report_text, "输入资料")
        risk_section = _section_text(report_text, "遗留风险")
        for row in missing_rows:
            category = next((item for item in REQUIRED_COVERAGE if item in row), "")
            if category and (category not in input_section or category not in risk_section):
                sink.add(
                    "missing_material_undisclosed",
                    f"missing material {category} must appear in 输入资料 and 遗留风险",
                    artifact=artifact,
                )


def _validate_hybrid_disclosure(report_text: str, missing_sides: tuple[str, ...], sink: _Sink) -> None:
    artifact = "zeroing_report.md"
    for side in missing_sides:
        phrase = EVIDENCE_SIDE_DISCLOSURE.get(side)
        if not phrase:
            continue
        coverage_section = _section_text(report_text, "资料覆盖矩阵")
        risk_section = _section_text(report_text, "遗留风险")
        if phrase not in coverage_section:
            sink.add(
                "hybrid_disclosure_missing",
                f"zeroing_report.md 资料覆盖矩阵 must disclose missing evidence side: {phrase}",
                artifact=artifact,
                location="资料覆盖矩阵",
            )
        if phrase not in risk_section:
            sink.add(
                "hybrid_disclosure_missing",
                f"zeroing_report.md 遗留风险 must disclose missing evidence side: {phrase}",
                artifact=artifact,
                location="遗留风险",
            )


def _coverage_matrix_rows(report_text: str) -> list[str]:
    matrix_section = _section_text(report_text, "资料覆盖矩阵")
    rows: list[str] = []
    in_table = False
    has_matrix_header = False
    for line in matrix_section.splitlines()[1:]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table:
                break
            if stripped:
                break
            continue
        in_table = True
        if not has_matrix_header:
            if _is_coverage_matrix_header(stripped):
                has_matrix_header = True
            continue
        if re.match(r"^\|\s*:?-{3,}:?\s*(?:\||$)", stripped):
            continue
        rows.append(stripped)
    return rows


def _is_coverage_matrix_header(line: str) -> bool:
    return ("类别" in line or "资料类别" in line) and any(phrase in line for phrase in ("检查结果", "覆盖状态", "覆盖情况", "覆盖结论")) and any(phrase in line for phrase in ("来源", "文件", "证据"))


def _verification_plan_ids(report_text: str) -> list[str]:
    section = _section_text(report_text, "验证计划")
    ids: list[str] = []
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if not cells:
            continue
        match = re.fullmatch(r"VP-[A-Za-z0-9_-]+", cells[0])
        if match:
            ids.append(match.group(0))
    return ids


def _section_text(text: str, title: str) -> str:
    match = re.search(rf"^#+\s*.*{re.escape(title)}.*$", text, flags=re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^##\s+", text[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(text)
    return text[match.start() : end]


def _extract_labeled_value(text: str, label: str) -> str:
    match = re.search(rf"(?:^|\n)\s*(?:[-*]\s*)?{re.escape(label)}[:：]\s*([^\n。；;]+)", text)
    if not match:
        return ""
    return match.group(1).strip().strip(" 。；;")


def _validate_analysis_process(process_text: str, sink: _Sink) -> None:
    for marker in REQUIRED_STAGE_MARKERS:
        if marker not in process_text:
            sink.add(
                "analysis_marker_missing",
                f"analysis_process.svg missing stage marker {marker}",
                artifact="analysis_process.svg",
            )


def _validate_svg(name: str, svg_text: str, sink: _Sink) -> None:
    lowered = svg_text.lower()
    if "<script" in lowered:
        sink.add("svg_unsafe", f"{name} contains <script", artifact=name)
    if re.search(r"\son[a-z]+\s*=", lowered):
        sink.add("svg_unsafe", f"{name} contains event handler", artifact=name)
    if re.search(r"""(?:href|src|xlink:href)\s*=\s*["']\s*(?:https?:)?//""", lowered):
        sink.add("svg_unsafe", f"{name} contains external URL", artifact=name)
    if re.search(r"""url\(\s*["']?(?:https?:)?//""", lowered):
        sink.add("svg_unsafe", f"{name} contains external URL", artifact=name)


def _validate_corrective_actions(
    outputs_dir: Path,
    tree: dict[str, Any],
    sink: _Sink,
    schema_path: Path | None = None,
) -> None:
    actions_path = outputs_dir / "artifacts" / "corrective_actions.json"
    if not actions_path.exists():
        return
    actions = _load_json(actions_path, sink)
    if actions is None:
        return
    if not isinstance(actions, dict):
        sink.add(
            "json_root_not_object",
            f"{actions_path.name} root must be an object",
            artifact=actions_path.name,
        )
        return

    schema = Path(schema_path) if schema_path else default_corrective_schema_path()
    schema_doc = _load_json(schema, sink)
    if schema_doc is not None:
        _validate_json_schema(
            actions,
            schema_doc,
            sink,
            path="corrective_actions.json",
        )

    root_cause_ids = {_string(cause.get("id")) for cause in _list(tree.get("root_causes")) if isinstance(cause, dict) and _string(cause.get("id"))}
    for item in _list(actions.get("corrective_actions")):
        if not isinstance(item, dict):
            continue
        action_id = _string(item.get("id")) or "<missing>"
        target = _string(item.get("target_root_cause_id"))
        if target and target not in root_cause_ids:
            sink.add(
                "corrective_action_unresolved",
                f"corrective action {action_id} references unknown root cause {target}",
                artifact="corrective_actions.json",
                location=action_id,
            )


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        digest.update(path.read_bytes())
    except OSError:
        return ""
    return digest.hexdigest()


def evaluate_result_contract(
    outputs_dir: str | Path,
    *,
    contract_version: str | None = None,
    schema_path: str | Path | None = None,
    corrective_schema_path: str | Path | None = None,
    repo_root: Path | None = None,
    missing_evidence_sides: Sequence[str] = (),
) -> ContractVerdict:
    """Evaluate the versioned Result Contract over one output artifact set.

    ``contract_version`` pins the semantic rules used for this evaluation
    (per-run pinning).  Unknown versions produce an explicit
    ``contract_version_unsupported`` finding instead of silently drifting.
    """

    requested_version = contract_version or CONTRACT_VERSION
    resolved_schema = Path(schema_path) if schema_path else default_schema_path(repo_root)
    resolved_corrective = Path(corrective_schema_path) if corrective_schema_path else default_corrective_schema_path(repo_root)
    fingerprint = contract_fingerprint(resolved_schema, resolved_corrective)

    sink = _Sink()
    if requested_version not in SUPPORTED_CONTRACT_VERSIONS:
        sink.add(
            "contract_version_unsupported",
            f"unsupported contract version {requested_version!r}; supported versions: {', '.join(SUPPORTED_CONTRACT_VERSIONS)}",
        )

    output_path = Path(outputs_dir)
    if not output_path.exists():
        sink.add("outputs_dir_missing", f"outputs dir does not exist: {output_path}")
        return _finish(sink, requested_version, fingerprint, output_path)
    if not output_path.is_dir():
        sink.add("outputs_dir_not_directory", f"outputs path is not a directory: {output_path}")
        return _finish(sink, requested_version, fingerprint, output_path)

    _validate_required_files(output_path, sink)
    schema_doc = _validate_schema_presence(resolved_schema, sink)
    tree = _load_json(output_path / "fault_tree.json", sink)
    if tree is None:
        return _finish(sink, requested_version, fingerprint, output_path)

    report_text = _read_text(output_path / "zeroing_report.md", sink)
    analysis_process = _read_text(output_path / "analysis_process.svg", sink)
    if schema_doc is not None:
        _validate_json_schema(tree, schema_doc, sink)
    _validate_fault_tree_shape(tree, sink)
    _validate_references(tree, report_text, sink)
    _validate_evidence_strength(tree, sink)
    _validate_report(report_text, tree, sink)
    _validate_analysis_process(analysis_process, sink)
    _validate_svg("fault_tree.svg", _read_text(output_path / "fault_tree.svg", sink), sink)
    _validate_svg("analysis_process.svg", analysis_process, sink)
    _validate_corrective_actions(output_path, tree, sink, resolved_corrective)
    _validate_hybrid_disclosure(report_text, tuple(missing_evidence_sides), sink)
    return _finish(sink, requested_version, fingerprint, output_path)


def _finish(sink: _Sink, version: str, fingerprint: str, output_path: Path) -> ContractVerdict:
    digests: dict[str, str] = {}
    names = list(REQUIRED_OUTPUTS) + ["artifacts/corrective_actions.json"]
    for name in names:
        path = output_path / name
        if path.is_file():
            digest = _digest_file(path)
            if digest:
                digests[name] = digest
    return ContractVerdict(
        contract_version=version,
        contract_fingerprint=fingerprint,
        findings=sink.findings,
        artifact_digests=digests,
    )
