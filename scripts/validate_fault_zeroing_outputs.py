#!/usr/bin/env python3
"""Validate fault-zeroing agent output artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

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
REQUIRED_STAGE_MARKERS = (
    "证据提取",
    "故障树构建",
    "底事件评估",
    "根因归因",
    "纠正措施",
    "文档生产",
)
STATUS_VALUES = {"confirmed", "rejected", "to_verify", "not_applicable"}
VERIFICATION_STATUS_VALUES = {"pending", "in_progress", "passed", "failed", "blocked"}
CONFIDENCE_VALUES = {"high", "medium", "low", "unknown"}
EVIDENCE_GRADES = {"A", "B", "C", "D"}
AB_GRADES = {"A", "B"}
CD_GRADES = {"C", "D"}
ROOT_CAUSE_STATUSES = {"confirmed"}
EVIDENCE_ID_PATTERN = re.compile(r"\bEV-[A-Za-z0-9_-]+\b")
EXPECTED_ANALYSIS_PATTERN = re.compile(
    r"(?:^|[/\\])[^/\\]*_expected_analysis\.md(?=$|[^\w./\\-]|第)",
    re.IGNORECASE,
)


class ValidationResult:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, message: str) -> None:
        self.errors.append(message)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_schema_path() -> Path:
    return (
        _repo_root()
        / "skills"
        / "custom"
        / "fault-zeroing"
        / "templates"
        / "fault_tree.schema.json"
    )


def _default_corrective_schema_path() -> Path:
    return (
        _repo_root()
        / "skills"
        / "custom"
        / "fault-zeroing"
        / "templates"
        / "corrective_actions.schema.json"
    )


def _read_text(path: Path, result: ValidationResult) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        result.add(f"{path.name} is not valid UTF-8")
    except OSError as exc:
        result.add(f"{path.name} cannot be read: {exc}")
    return ""


def _load_json(path: Path, result: ValidationResult) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        result.add(f"{path.name} is invalid JSON: {exc}")
        return None
    except OSError as exc:
        result.add(f"{path.name} cannot be read: {exc}")
        return None
    if not isinstance(value, dict):
        result.add(f"{path.name} root must be an object")
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


def _require_keys(
    obj: dict[str, Any], keys: tuple[str, ...], prefix: str, result: ValidationResult
) -> None:
    for key in keys:
        if key not in obj:
            result.add(f"{prefix} missing required key {key}")


def _validate_required_files(outputs_dir: Path, result: ValidationResult) -> None:
    for name in REQUIRED_OUTPUTS:
        path = outputs_dir / name
        if not path.exists():
            result.add(f"{name} is missing")
            continue
        if not path.is_file():
            result.add(f"{name} is not a file")
            continue
        if path.stat().st_size == 0:
            result.add(f"{name} is empty")


def _validate_schema_presence(
    schema_path: Path, result: ValidationResult
) -> dict[str, Any] | None:
    schema = _load_json(schema_path, result)
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
            result.add(f"schema missing property {key}")
    return schema


def _validate_json_schema(
    value: Any,
    schema: dict[str, Any],
    result: ValidationResult,
    path: str = "fault_tree.json",
    root_schema: dict[str, Any] | None = None,
) -> None:
    root = root_schema or schema
    ref = schema.get("$ref")
    if isinstance(ref, str):
        resolved = _resolve_schema_ref(ref, root)
        if resolved is None:
            result.add(
                f"fault_tree.json schema violation at {path}: unresolved schema ref {ref}"
            )
            return
        _validate_json_schema(value, resolved, result, path, root)
        return

    if "enum" in schema and value not in _list(schema.get("enum")):
        result.add(
            f"fault_tree.json schema violation at {path}: value {value!r} is not allowed"
        )
        return

    expected_type = schema.get("type")
    if expected_type is not None and not _matches_schema_type(value, expected_type):
        expected = (
            "/".join(expected_type)
            if isinstance(expected_type, list)
            else str(expected_type)
        )
        result.add(f"fault_tree.json schema violation at {path}: expected {expected}")
        return

    min_length = schema.get("minLength")
    if (
        isinstance(value, str)
        and isinstance(min_length, int)
        and len(value) < min_length
    ):
        result.add(
            f"fault_tree.json schema violation at {path}: string shorter than minLength {min_length}"
        )
        return

    if isinstance(value, dict):
        for key in _id_list(schema.get("required")):
            if key not in value:
                result.add(
                    f"fault_tree.json schema violation at {path}: missing required key {key}"
                )
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    _validate_json_schema(
                        value[key], child_schema, result, f"{path}.{key}", root
                    )
    elif isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate_json_schema(
                    item, item_schema, result, f"{path}[{index}]", root
                )


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


def _validate_fault_tree_shape(tree: dict[str, Any], result: ValidationResult) -> None:
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
        result,
    )
    if not _string(tree.get("top_event")).strip():
        result.add("fault_tree.json top_event is empty")

    for list_key in (
        "intermediate_events",
        "bottom_events",
        "logic",
        "evidence",
        "root_causes",
        "verification_plan",
    ):
        if list_key in tree and not isinstance(tree.get(list_key), list):
            result.add(f"fault_tree.json {list_key} must be a list")

    for event in _list(tree.get("intermediate_events")):
        if not isinstance(event, dict):
            result.add("intermediate event must be an object")
            continue
        event_id = _string(event.get("id")) or "<missing>"
        _require_keys(
            event,
            ("id", "name", "description", "parent_ids", "logic"),
            f"intermediate event {event_id}",
            result,
        )

    for event in _list(tree.get("bottom_events")):
        if not isinstance(event, dict):
            result.add("bottom event must be an object")
            continue
        event_id = _string(event.get("id")) or "<missing>"
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
            result,
        )
        if _string(event.get("status")) not in STATUS_VALUES:
            result.add(
                f"bottom event {event_id} has invalid status {_string(event.get('status'))}"
            )
        if _string(event.get("confidence")) not in CONFIDENCE_VALUES:
            result.add(
                f"bottom event {event_id} has invalid confidence {_string(event.get('confidence'))}"
            )
        if (
            not _string(event.get("description")).strip()
            or not _string(event.get("verification_suggestion")).strip()
        ):
            result.add(f"bottom event {event_id} lacks verifiable object or condition")
        if isinstance(event.get("probability"), int | float) and event.get(
            "probability_basis"
        ) in (None, ""):
            result.add(f"numeric probability for {event_id} lacks probability_basis")

    for evidence in _list(tree.get("evidence")):
        if not isinstance(evidence, dict):
            result.add("evidence entry must be an object")
            continue
        evidence_id = _string(evidence.get("id")) or "<missing>"
        _require_keys(
            evidence,
            ("id", "source", "grade", "type", "summary", "supports", "contradicts"),
            f"evidence {evidence_id}",
            result,
        )
        if _string(evidence.get("grade")) not in EVIDENCE_GRADES:
            result.add(
                f"evidence {evidence_id} has invalid grade {_string(evidence.get('grade'))}"
            )
        source = _string(evidence.get("source"))
        if _is_expected_analysis_source(source):
            result.add(f"expected-analysis files cannot be used as evidence: {source}")

    for root_cause in _list(tree.get("root_causes")):
        if not isinstance(root_cause, dict):
            result.add("root cause must be an object")
            continue
        cause_id = _string(root_cause.get("id")) or "<missing>"
        _require_keys(
            root_cause,
            ("id", "name", "description", "evidence_ids", "status", "confidence"),
            f"root cause {cause_id}",
            result,
        )
        if _string(root_cause.get("status")) not in STATUS_VALUES:
            result.add(
                f"root cause {cause_id} has invalid status {_string(root_cause.get('status'))}"
            )

    for item in _list(tree.get("verification_plan")):
        if not isinstance(item, dict):
            result.add("verification item must be an object")
            continue
        item_id = _string(item.get("id")) or "<missing>"
        _require_keys(
            item,
            ("id", "target_id", "item", "method", "expected_result", "status"),
            f"verification item {item_id}",
            result,
        )
        if _string(item.get("status")) not in VERIFICATION_STATUS_VALUES:
            result.add(
                f"verification item {item_id} has invalid status {_string(item.get('status'))}"
            )


def _validate_references(
    tree: dict[str, Any], report_text: str, result: ValidationResult
) -> None:
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
            result.add(f"duplicate evidence id {evidence_id}")
        evidence_by_id[evidence_id] = evidence

    for key in ("intermediate_events", "bottom_events"):
        for node in _list(tree.get(key)):
            if not isinstance(node, dict):
                continue
            node_id = _string(node.get("id")) or "<missing>"
            for parent_id in _id_list(node.get("parent_ids")):
                if parent_id not in node_ids:
                    result.add(f"{node_id} references unknown parent_id {parent_id}")

    for logic in _list(tree.get("logic")):
        if not isinstance(logic, dict):
            continue
        for key in ("source", "target", "parent"):
            ref = _string(logic.get(key))
            if ref and ref not in node_ids:
                result.add(f"logic references unknown node {ref}")
        for child in _id_list(logic.get("children")):
            if child not in node_ids:
                result.add(f"logic references unknown node {child}")

    referenced_evidence: list[tuple[str, str]] = []
    for node in _list(tree.get("bottom_events")):
        if isinstance(node, dict):
            referenced_evidence.extend(
                (_string(node.get("id")) or "<missing>", evidence_id)
                for evidence_id in _evidence_ids_for(node)
            )
    for root_cause in _list(tree.get("root_causes")):
        if isinstance(root_cause, dict):
            referenced_evidence.extend(
                (_string(root_cause.get("id")) or "<missing>", evidence_id)
                for evidence_id in _evidence_ids_for(root_cause)
            )
    for owner, evidence_id in referenced_evidence:
        if evidence_id not in evidence_by_id:
            result.add(f"{owner} references unknown evidence id {evidence_id}")

    for evidence_id in EVIDENCE_ID_PATTERN.findall(report_text):
        if evidence_id not in evidence_by_id:
            result.add(f"report references unknown evidence id {evidence_id}")

    event_ids = node_ids | {
        _string(cause.get("id"))
        for cause in _list(tree.get("root_causes"))
        if isinstance(cause, dict)
    }
    for evidence in evidence_by_id.values():
        for key in ("supports", "contradicts"):
            for target_id in _id_list(evidence.get(key)):
                if target_id and target_id not in event_ids:
                    result.add(
                        f"evidence {_string(evidence.get('id'))} {key} unknown target {target_id}"
                    )

    for item in _list(tree.get("verification_plan")):
        if not isinstance(item, dict):
            continue
        item_id = _string(item.get("id")) or "<missing>"
        target_id = _string(item.get("target_id"))
        if target_id and target_id not in event_ids:
            result.add(
                f"verification item {item_id} references unknown target_id {target_id}"
            )


def _grades_for(
    evidence_ids: list[str], evidence_by_id: dict[str, dict[str, Any]]
) -> set[str]:
    return {
        _string(evidence_by_id.get(evidence_id, {}).get("grade"))
        for evidence_id in evidence_ids
    }


def _has_counterevidence(
    event_id: str, evidence_by_id: dict[str, dict[str, Any]]
) -> bool:
    return any(
        event_id in _id_list(evidence.get("contradicts"))
        for evidence in evidence_by_id.values()
    )


def _validate_evidence_strength(tree: dict[str, Any], result: ValidationResult) -> None:
    evidence_by_id = {
        _string(evidence.get("id")): evidence
        for evidence in _list(tree.get("evidence"))
        if isinstance(evidence, dict) and _string(evidence.get("id"))
    }

    for event in _list(tree.get("bottom_events")):
        if not isinstance(event, dict):
            continue
        event_id = _string(event.get("id")) or "<missing>"
        evidence_ids = _evidence_ids_for(event)
        grades = _grades_for(evidence_ids, evidence_by_id)
        status = _string(event.get("status"))
        if status == "confirmed" and not grades.intersection(AB_GRADES):
            result.add(f"{event_id} is confirmed with only C/D evidence")
        if status == "rejected" and not _has_counterevidence(event_id, evidence_by_id):
            result.add(f"rejected bottom event {event_id} lacks counterevidence")

    for root_cause in _list(tree.get("root_causes")):
        if not isinstance(root_cause, dict):
            continue
        cause_id = _string(root_cause.get("id")) or "<missing>"
        evidence_ids = _evidence_ids_for(root_cause)
        grades = _grades_for(evidence_ids, evidence_by_id)
        status = _string(root_cause.get("status"))
        confidence = _string(root_cause.get("confidence"))
        if status in ROOT_CAUSE_STATUSES and not grades.intersection(AB_GRADES):
            result.add(f"confirmed root cause {cause_id} lacks A/B evidence")
        if status in ROOT_CAUSE_STATUSES and grades and grades.issubset(CD_GRADES):
            result.add(
                f"confirmed root cause {cause_id} is supported only by C/D evidence"
            )
        if confidence == "high" and not grades.intersection(AB_GRADES):
            result.add(f"high-confidence root cause {cause_id} lacks A/B evidence")


def _validate_report(
    report_text: str, tree: dict[str, Any], result: ValidationResult
) -> None:
    for section in REQUIRED_REPORT_SECTIONS:
        if section not in report_text:
            result.add(f"zeroing_report.md missing section {section}")
    for phrase in ("资料覆盖矩阵", "证据台账摘要", "待验证项", "遗留风险"):
        if phrase not in report_text:
            result.add(f"zeroing_report.md missing {phrase}")
    for marker in REQUIRED_STAGE_MARKERS:
        if marker not in report_text:
            result.add(f"zeroing_report.md missing stage marker {marker}")
    for phrase in (
        "演绎建树阶段不依赖证据台账",
        "证据检漏只做添加不做删除",
        "文档阶段不修改分析数据",
    ):
        if phrase not in report_text:
            result.add(
                f"zeroing_report.md missing subagent responsibility statement: {phrase}"
            )
    forbidden_claims = (
        "演绎建树阶段依赖证据台账",
        "证据检漏删除已有证据",
        "文档阶段修改分析数据",
    )
    for claim in forbidden_claims:
        if claim in report_text:
            result.add(f"zeroing_report.md contains forbidden subagent claim: {claim}")

    coverage_rows = _coverage_matrix_rows(report_text)
    missing_coverage = [
        category
        for category in REQUIRED_COVERAGE
        if not any(category in row for row in coverage_rows)
    ]
    if missing_coverage:
        result.add(f"资料覆盖矩阵缺少：{'、'.join(missing_coverage)}")

    top_event = _string(tree.get("top_event")).strip()
    report_top_event = _extract_labeled_value(report_text, "顶事件")
    if top_event and report_top_event and report_top_event != top_event:
        result.add("report top event does not match fault_tree.json")
    elif top_event and not report_top_event and top_event not in report_text:
        result.add("report top event does not match fault_tree.json")

    confirmed_roots = [
        root
        for root in _list(tree.get("root_causes"))
        if isinstance(root, dict) and _string(root.get("status")) == "confirmed"
    ]
    if confirmed_roots:
        first_root_name = _string(confirmed_roots[0].get("name")).strip()
        report_root = _extract_labeled_value(report_text, "主根因")
        if first_root_name and report_root and report_root != first_root_name:
            result.add("report main root cause does not match fault_tree.json")
        elif first_root_name and not report_root and first_root_name not in report_text:
            result.add("report main root cause does not match fault_tree.json")

    for item in _list(tree.get("verification_plan")):
        if not isinstance(item, dict):
            continue
        if _string(item.get("status")) != "pending":
            continue
        item_id = _string(item.get("id")) or "<missing>"
        item_name = _string(item.get("item")).strip()
        if item_name and item_name not in report_text:
            result.add(f"report missing pending verification item {item_id}")

    missing_rows = [
        line
        for line in coverage_rows
        if "缺失" in line or "未提供" in line or "未覆盖" in line
    ]
    if missing_rows:
        input_section = _section_text(report_text, "输入资料")
        risk_section = _section_text(report_text, "遗留风险")
        for row in missing_rows:
            category = next((item for item in REQUIRED_COVERAGE if item in row), "")
            if category and (
                category not in input_section or category not in risk_section
            ):
                result.add(
                    f"missing material {category} must appear in 输入资料 and 遗留风险"
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
            if "类别" in stripped and "检查结果" in stripped:
                has_matrix_header = True
            continue
        if re.match(r"^\|\s*:?-{3,}:?\s*(?:\||$)", stripped):
            continue
        rows.append(stripped)
    return rows


def _section_text(text: str, title: str) -> str:
    match = re.search(rf"^#+\s*.*{re.escape(title)}.*$", text, flags=re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^##\s+", text[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(text)
    return text[match.start() : end]


def _extract_labeled_value(text: str, label: str) -> str:
    match = re.search(
        rf"(?:^|\n)\s*(?:[-*]\s*)?{re.escape(label)}[:：]\s*([^\n。；;]+)", text
    )
    if not match:
        return ""
    return match.group(1).strip().strip(" 。；;")


def _validate_analysis_process(process_text: str, result: ValidationResult) -> None:
    for marker in REQUIRED_STAGE_MARKERS:
        if marker not in process_text:
            result.add(f"analysis_process.svg missing stage marker {marker}")


def _validate_svg(name: str, svg_text: str, result: ValidationResult) -> None:
    lowered = svg_text.lower()
    if "<script" in lowered:
        result.add(f"{name} contains <script")
    if re.search(r"\son[a-z]+\s*=", lowered):
        result.add(f"{name} contains event handler")
    if re.search(r"""(?:href|src|xlink:href)\s*=\s*["']\s*(?:https?:)?//""", lowered):
        result.add(f"{name} contains external URL")
    if re.search(r"""url\(\s*["']?(?:https?:)?//""", lowered):
        result.add(f"{name} contains external URL")


def _validate_corrective_actions(
    outputs_dir: Path,
    tree: dict[str, Any],
    result: ValidationResult,
    schema_path: Path | None = None,
) -> None:
    actions_path = outputs_dir / "artifacts" / "corrective_actions.json"
    if not actions_path.exists():
        return
    actions = _load_json(actions_path, result)
    if actions is None:
        return
    if not isinstance(actions, dict):
        result.add(f"{actions_path.name} root must be an object")
        return

    schema = Path(schema_path) if schema_path else _default_corrective_schema_path()
    schema_doc = _load_json(schema, result)
    if schema_doc is not None:
        _validate_json_schema(
            actions,
            schema_doc,
            result,
            path="corrective_actions.json",
        )

    root_cause_ids = {
        _string(cause.get("id"))
        for cause in _list(tree.get("root_causes"))
        if isinstance(cause, dict) and _string(cause.get("id"))
    }
    for item in _list(actions.get("corrective_actions")):
        if not isinstance(item, dict):
            continue
        action_id = _string(item.get("id")) or "<missing>"
        target = _string(item.get("target_root_cause_id"))
        if target and target not in root_cause_ids:
            result.add(
                f"corrective action {action_id} references unknown root cause {target}"
            )


def validate_outputs(
    outputs_dir: str | Path, schema_path: str | Path | None = None
) -> ValidationResult:
    output_path = Path(outputs_dir)
    result = ValidationResult()
    schema = Path(schema_path) if schema_path else _default_schema_path()

    if not output_path.exists():
        result.add(f"outputs dir does not exist: {output_path}")
        return result
    if not output_path.is_dir():
        result.add(f"outputs path is not a directory: {output_path}")
        return result

    _validate_required_files(output_path, result)
    schema_doc = _validate_schema_presence(schema, result)
    tree = _load_json(output_path / "fault_tree.json", result)
    if tree is None:
        return result

    report_text = _read_text(output_path / "zeroing_report.md", result)
    analysis_process = _read_text(output_path / "analysis_process.svg", result)
    if schema_doc is not None:
        _validate_json_schema(tree, schema_doc, result)
    _validate_fault_tree_shape(tree, result)
    _validate_references(tree, report_text, result)
    _validate_evidence_strength(tree, result)
    _validate_report(report_text, tree, result)
    _validate_analysis_process(analysis_process, result)
    _validate_svg(
        "fault_tree.svg", _read_text(output_path / "fault_tree.svg", result), result
    )
    _validate_svg("analysis_process.svg", analysis_process, result)
    _validate_corrective_actions(output_path, tree, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate fault-zeroing agent output files."
    )
    parser.add_argument(
        "--outputs-dir",
        required=True,
        help="Directory containing the five fault-zeroing outputs.",
    )
    parser.add_argument(
        "--schema",
        default=str(_default_schema_path()),
        help="Path to fault_tree.schema.json.",
    )
    args = parser.parse_args(argv)

    result = validate_outputs(args.outputs_dir, args.schema)
    if result.ok:
        print("fault-zeroing outputs validation passed")
        return 0

    print("fault-zeroing outputs validation failed", file=sys.stderr)
    for error in result.errors:
        print(f"- {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
