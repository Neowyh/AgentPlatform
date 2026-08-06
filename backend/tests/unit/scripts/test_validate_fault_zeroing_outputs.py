from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_fault_zeroing_outputs.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_fault_zeroing_outputs", VALIDATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_fault_tree() -> dict:
    return {
        "top_event": "热流传感器 HF-07 测值超过试验允许上限",
        "intermediate_events": [
            {
                "id": "IE-01",
                "name": "测量链路异常",
                "description": "传感器、接线和采集链路需要排查",
                "parent_ids": ["TOP"],
                "logic": "OR",
            }
        ],
        "bottom_events": [
            {
                "id": "BE-01",
                "name": "HF-07 零点漂移",
                "description": "关车后零位偏差超过试验前校准范围",
                "parent_ids": ["IE-01"],
                "evidence_ids": ["EV-01", "EV-02"],
                "probability": "high",
                "probability_basis": "同通道历史复核 3 次出现类似漂移，且本次零点复测复现。",
                "confidence": "high",
                "status": "confirmed",
                "verification_suggestion": "复测 HF-07 零位并替换采集通道交叉验证",
            },
            {
                "id": "BE-02",
                "name": "局部热流真实超限",
                "description": "需要通过相邻测点和流场复核确认真实热环境",
                "parent_ids": ["IE-01"],
                "evidence_ids": ["EV-03"],
                "probability": None,
                "probability_basis": None,
                "confidence": "low",
                "status": "to_verify",
                "verification_suggestion": "复核相邻测点、喷管状态和试验重复性",
            },
        ],
        "logic": [{"source": "TOP", "target": "IE-01", "type": "OR"}],
        "evidence": [
            {
                "id": "EV-01",
                "source": "03_test_records.md#L12-L18",
                "grade": "A",
                "type": "test_record",
                "summary": "HF-07 关车后零位复测偏差超出校准范围。",
                "supports": ["BE-01"],
                "contradicts": [],
            },
            {
                "id": "EV-02",
                "source": "05_review_record.md#L8-L12",
                "grade": "B",
                "type": "review_record",
                "summary": "历史复核中同通道出现过类似零漂。",
                "supports": ["BE-01"],
                "contradicts": [],
            },
            {
                "id": "EV-03",
                "source": "04_summary_report.md#L20-L25",
                "grade": "C",
                "type": "summary_report",
                "summary": "相邻测点未全部同步升高，真实超限仍需复核。",
                "supports": ["BE-02"],
                "contradicts": ["BE-01"],
            },
        ],
        "root_causes": [
            {
                "id": "RC-01",
                "name": "HF-07 测量链路零点漂移",
                "description": "零点复测和历史复核共同支持测量链路异常。",
                "evidence_ids": ["EV-01", "EV-02"],
                "status": "confirmed",
                "confidence": "high",
            }
        ],
        "verification_plan": [
            {
                "id": "VP-01",
                "target_id": "BE-02",
                "item": "真实热流超限复核",
                "method": "复查相邻测点和重复试验数据",
                "expected_result": "确认是否存在真实热环境异常",
                "status": "pending",
            }
        ],
    }


def valid_report() -> str:
    return """# 归零报告

## 1. 问题概述

- 顶事件：热流传感器 HF-07 测值超过试验允许上限
- 主根因：HF-07 测量链路零点漂移

## 2. 输入资料

### 资料覆盖矩阵

| 类别 | 检查结果 | 来源 | 缺失影响 |
| --- | --- | --- | --- |
| 问题描述 | 已覆盖 | 01_problem.md | 无 |
| 设计约束 | 已覆盖 | 02_design.md | 无 |
| 试验记录或日志 | 已覆盖 | 03_test_records.md | 无 |
| 总结报告 | 已覆盖 | 04_summary_report.md | 无 |
| 历史或复核记录 | 已覆盖 | 05_review_record.md | 无 |

## 3. 故障现象

HF-07 测值超过允许上限。[EV-01]

## 4. 故障树分析

顶事件：热流传感器 HF-07 测值超过试验允许上限

## 5. 底事件评估

BE-01 confirmed；BE-02 to_verify。

## 6. 根因归因

主根因：HF-07 测量链路零点漂移。证据：[EV-01] [EV-02]

## 7. 验证计划

| ID | 待验证项 | 方法 | 状态 |
| --- | --- | --- | --- |
| VP-01 | 真实热流超限复核 | 复查相邻测点和重复试验数据 | to_verify |

## 8. 纠正措施

替换采集链路并复测。

## 9. 遗留风险

暂无缺失资料风险；BE-02 仍待验证。

## 10. 附录：证据引用

### 证据台账摘要

| ID | 等级 | 来源 | 摘要 | 支撑 |
| --- | --- | --- | --- | --- |
| EV-01 | A | 03_test_records.md#L12-L18 | 零位复测偏差超限 | BE-01 |
| EV-02 | B | 05_review_record.md#L8-L12 | 历史复核类似零漂 | BE-01 |

### 阶段顺序痕迹

证据提取 -> 故障树构建 -> 底事件评估 -> 根因归因 -> 纠正措施 -> 文档生产

### 子智能体职责说明

演绎建树阶段不依赖证据台账；证据检漏只做添加不做删除；文档阶段不修改分析数据。
"""


def valid_corrective_actions() -> dict:
    return {
        "corrective_actions": [
            {
                "id": "CA-001",
                "name": "更换采集链路",
                "description": "替换 HF-07 采集链路并复测。",
                "target_root_cause_id": "RC-01",
                "owner": "计量部门",
                "completion_criteria": "连续 3 次试验零位复测通过",
                "priority": "high",
                "status": "planned",
            }
        ]
    }


def write_outputs(
    tmp_path: Path,
    fault_tree: dict | None = None,
    report: str | None = None,
    corrective_actions: dict | None = None,
) -> Path:
    import json

    output_dir = tmp_path / "outputs"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "fault_tree.json").write_text(
        json.dumps(fault_tree or valid_fault_tree(), ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "fault_tree.svg").write_text("<svg><rect/><text>fault tree</text></svg>", encoding="utf-8")
    (output_dir / "bottom_event_assessment.md").write_text(
        "| 底事件 | 证据 | 概率判断 | 置信度 | 验证状态 |\n| --- | --- | --- | --- | --- |\n| BE-01 | EV-01 | high | high | confirmed |\n",
        encoding="utf-8",
    )
    (output_dir / "analysis_process.svg").write_text(
        "<svg><text>证据提取 故障树构建 底事件评估 根因归因 纠正措施 文档生产</text></svg>",
        encoding="utf-8",
    )
    (output_dir / "zeroing_report.md").write_text(report or valid_report(), encoding="utf-8")
    if corrective_actions is not None:
        artifacts_dir = output_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        (artifacts_dir / "corrective_actions.json").write_text(
            json.dumps(corrective_actions, ensure_ascii=False),
            encoding="utf-8",
        )
    return output_dir


def assert_invalid(output_dir: Path, expected: str) -> None:
    validator = load_validator()
    result = validator.validate_outputs(output_dir)
    assert not result.ok
    assert expected in "\n".join(result.errors)


def test_valid_fault_zeroing_outputs_pass(tmp_path: Path) -> None:
    validator = load_validator()
    result = validator.validate_outputs(write_outputs(tmp_path))

    assert result.ok
    assert result.errors == []


def test_missing_or_empty_required_output_fails(tmp_path: Path) -> None:
    output_dir = write_outputs(tmp_path)
    (output_dir / "fault_tree.svg").write_text("", encoding="utf-8")

    assert_invalid(output_dir, "fault_tree.svg is empty")


def test_schema_status_and_dangling_parent_fail(tmp_path: Path) -> None:
    fault_tree = valid_fault_tree()
    fault_tree["bottom_events"][0]["status"] = "likely"
    fault_tree["bottom_events"][1]["parent_ids"] = ["IE-MISSING"]

    assert_invalid(write_outputs(tmp_path, fault_tree), "invalid status")
    assert_invalid(write_outputs(tmp_path, fault_tree), "unknown parent_id IE-MISSING")


def test_schema_rejects_nested_type_and_enum_mismatches(tmp_path: Path) -> None:
    fault_tree = valid_fault_tree()
    fault_tree["intermediate_events"][0]["parent_ids"] = "TOP"
    fault_tree["logic"][0]["type"] = "XOR"

    assert_invalid(write_outputs(tmp_path, fault_tree), "fault_tree.json schema violation")


def test_schema_rejects_empty_min_length_strings(tmp_path: Path) -> None:
    fault_tree = valid_fault_tree()
    fault_tree["evidence"][0]["source"] = ""
    fault_tree["evidence"][1]["summary"] = ""
    fault_tree["verification_plan"][0]["item"] = ""

    output_dir = write_outputs(tmp_path, fault_tree)
    assert_invalid(output_dir, "fault_tree.json.evidence[0].source")
    assert_invalid(output_dir, "fault_tree.json.evidence[1].summary")
    assert_invalid(output_dir, "fault_tree.json.verification_plan[0].item")


def test_evidence_ids_must_be_unique_and_references_known(tmp_path: Path) -> None:
    fault_tree = valid_fault_tree()
    fault_tree["evidence"][1]["id"] = "EV-01"
    fault_tree["root_causes"][0]["evidence_ids"] = ["EV-MISSING"]

    assert_invalid(write_outputs(tmp_path, fault_tree), "duplicate evidence id EV-01")
    assert_invalid(write_outputs(tmp_path, fault_tree), "unknown evidence id EV-MISSING")


def test_material_coverage_matrix_must_cover_required_categories(tmp_path: Path) -> None:
    report = valid_report().replace("| 历史或复核记录 | 已覆盖 | 05_review_record.md | 无 |\n", "")
    report = report.replace(
        "暂无缺失资料风险；BE-02 仍待验证。",
        "历史或复核记录只在遗留风险中提及，BE-02 仍待验证。",
    )

    assert_invalid(write_outputs(tmp_path, report=report), "资料覆盖矩阵缺少：历史或复核记录")


def test_material_coverage_matrix_ignores_other_input_tables(tmp_path: Path) -> None:
    report = valid_report().replace("| 历史或复核记录 | 已覆盖 | 05_review_record.md | 无 |\n", "")
    report = report.replace(
        "## 3. 故障现象",
        "### 其他资料表\n\n| 类别 | 说明 |\n| --- | --- |\n| 历史或复核记录 | 这个表不是资料覆盖矩阵 |\n\n## 3. 故障现象",
    )

    assert_invalid(write_outputs(tmp_path, report=report), "资料覆盖矩阵缺少：历史或复核记录")


def test_material_coverage_matrix_must_be_table_under_matrix_heading(tmp_path: Path) -> None:
    matrix_table = (
        "| 类别 | 检查结果 | 来源 | 缺失影响 |\n"
        "| --- | --- | --- | --- |\n"
        "| 问题描述 | 已覆盖 | 01_problem.md | 无 |\n"
        "| 设计约束 | 已覆盖 | 02_design.md | 无 |\n"
        "| 试验记录或日志 | 已覆盖 | 03_test_records.md | 无 |\n"
        "| 总结报告 | 已覆盖 | 04_summary_report.md | 无 |\n"
        "| 历史或复核记录 | 已覆盖 | 05_review_record.md | 无 |\n"
    )
    later_table = (
        "### 其他资料表\n\n"
        "| 类别 | 说明 |\n"
        "| --- | --- |\n"
        "| 问题描述 | 这个表不是资料覆盖矩阵 |\n"
        "| 设计约束 | 这个表不是资料覆盖矩阵 |\n"
        "| 试验记录或日志 | 这个表不是资料覆盖矩阵 |\n"
        "| 总结报告 | 这个表不是资料覆盖矩阵 |\n"
        "| 历史或复核记录 | 这个表不是资料覆盖矩阵 |\n\n"
    )
    report = valid_report().replace(matrix_table, "矩阵待补充。\n\n" + later_table)

    assert_invalid(
        write_outputs(tmp_path, report=report),
        "资料覆盖矩阵缺少：问题描述、设计约束、试验记录或日志、总结报告、历史或复核记录",
    )


def test_material_coverage_matrix_requires_matrix_header(tmp_path: Path) -> None:
    report = (
        valid_report()
        .replace(
            "| 类别 | 检查结果 | 来源 | 缺失影响 |",
            "| 类别 | 说明 |",
        )
        .replace(
            "| 问题描述 | 已覆盖 | 01_problem.md | 无 |",
            "| 问题描述 | 这个表不是资料覆盖矩阵 |",
        )
        .replace(
            "| 设计约束 | 已覆盖 | 02_design.md | 无 |",
            "| 设计约束 | 这个表不是资料覆盖矩阵 |",
        )
        .replace(
            "| 试验记录或日志 | 已覆盖 | 03_test_records.md | 无 |",
            "| 试验记录或日志 | 这个表不是资料覆盖矩阵 |",
        )
        .replace(
            "| 总结报告 | 已覆盖 | 04_summary_report.md | 无 |",
            "| 总结报告 | 这个表不是资料覆盖矩阵 |",
        )
        .replace(
            "| 历史或复核记录 | 已覆盖 | 05_review_record.md | 无 |",
            "| 历史或复核记录 | 这个表不是资料覆盖矩阵 |",
        )
    )

    assert_invalid(
        write_outputs(tmp_path, report=report),
        "资料覆盖矩阵缺少：问题描述、设计约束、试验记录或日志、总结报告、历史或复核记录",
    )


def test_confirmed_root_cause_requires_ab_evidence(tmp_path: Path) -> None:
    fault_tree = valid_fault_tree()
    fault_tree["root_causes"][0]["evidence_ids"] = ["EV-03"]

    assert_invalid(write_outputs(tmp_path, fault_tree), "confirmed root cause RC-01 lacks A/B evidence")


def test_cd_only_bottom_event_cannot_be_confirmed(tmp_path: Path) -> None:
    fault_tree = valid_fault_tree()
    fault_tree["bottom_events"][1]["status"] = "confirmed"

    assert_invalid(write_outputs(tmp_path, fault_tree), "BE-02 is confirmed with only C/D evidence")


def test_rejected_bottom_event_requires_counterevidence(tmp_path: Path) -> None:
    fault_tree = valid_fault_tree()
    fault_tree["bottom_events"][1]["status"] = "rejected"

    assert_invalid(write_outputs(tmp_path, fault_tree), "rejected bottom event BE-02 lacks counterevidence")


def test_report_must_match_json_top_event_root_cause_and_to_verify_items(tmp_path: Path) -> None:
    report = valid_report().replace("热流传感器 HF-07 测值超过试验允许上限", "另一个顶事件", 1)
    assert_invalid(write_outputs(tmp_path, report=report), "report top event does not match fault_tree.json")

    report = valid_report().replace("HF-07 测量链路零点漂移", "另一个根因", 1)
    assert_invalid(write_outputs(tmp_path, report=report), "report main root cause does not match fault_tree.json")

    report = valid_report().replace("真实热流超限复核", "未列出的验证项")
    assert_invalid(write_outputs(tmp_path, report=report), "report missing pending verification item VP-01")


def test_verification_plan_target_id_must_reference_known_node_or_root_cause(tmp_path: Path) -> None:
    fault_tree = valid_fault_tree()
    fault_tree["verification_plan"][0]["target_id"] = "BE-MISSING"

    assert_invalid(write_outputs(tmp_path, fault_tree), "verification item VP-01 references unknown target_id BE-MISSING")


@pytest.mark.parametrize(
    "svg_content,expected",
    [
        ("<svg><script>alert(1)</script></svg>", "contains <script"),
        ('<svg><rect onclick="alert(1)"/></svg>', "contains event handler"),
        ('<svg><image href="https://example.com/a.png"/></svg>', "contains external URL"),
        ('<svg><image href="//example.com/a.png"/></svg>', "contains external URL"),
    ],
)
def test_svg_active_content_fails(tmp_path: Path, svg_content: str, expected: str) -> None:
    output_dir = write_outputs(tmp_path)
    (output_dir / "fault_tree.svg").write_text(svg_content, encoding="utf-8")

    assert_invalid(output_dir, expected)


def test_expected_analysis_file_cannot_be_root_cause_evidence(tmp_path: Path) -> None:
    fault_tree = valid_fault_tree()
    fault_tree["evidence"][0]["source"] = "06_expected_analysis.md#L3"

    assert_invalid(write_outputs(tmp_path, fault_tree), "expected-analysis files cannot be used as evidence")


@pytest.mark.parametrize(
    "source",
    [
        "06_expected_analysis.md:L3",
        "06_expected_analysis.md 第3行",
        "06_expected_analysis.md第3行",
        "cases/case_01_expected_analysis.md：第10行",
    ],
)
def test_expected_analysis_file_cannot_use_line_suffixes(tmp_path: Path, source: str) -> None:
    fault_tree = valid_fault_tree()
    fault_tree["evidence"][0]["source"] = source

    assert_invalid(write_outputs(tmp_path, fault_tree), "expected-analysis files cannot be used as evidence")


def test_old_evidence_grading_stage_marker_no_longer_satisfies_required_flow(tmp_path: Path) -> None:
    report = valid_report().replace(
        "证据提取 -> 故障树构建 -> 底事件评估 -> 根因归因 -> 纠正措施 -> 文档生产",
        "证据提取 -> 证据分级 -> 底事件评估 -> 根因归因 -> 纠正措施 -> 文档生产",
    )
    output_dir = write_outputs(tmp_path, report=report)
    (output_dir / "analysis_process.svg").write_text(
        "<svg><text>证据提取 证据分级 底事件评估 根因归因 纠正措施 文档生产</text></svg>",
        encoding="utf-8",
    )

    assert_invalid(output_dir, "missing stage marker 故障树构建")


def test_expected_analysis_file_cannot_be_bottom_event_evidence(tmp_path: Path) -> None:
    fault_tree = valid_fault_tree()
    fault_tree["evidence"][2]["source"] = "cases/case_01_expected_analysis.md#L10"

    assert_invalid(write_outputs(tmp_path, fault_tree), "expected-analysis files cannot be used as evidence")


def test_numeric_probability_requires_basis(tmp_path: Path) -> None:
    fault_tree = valid_fault_tree()
    fault_tree["bottom_events"][0]["probability"] = 0.82
    fault_tree["bottom_events"][0]["probability_basis"] = None

    assert_invalid(write_outputs(tmp_path, fault_tree), "numeric probability for BE-01 lacks probability_basis")


def test_valid_corrective_actions_pass(tmp_path: Path) -> None:
    validator = load_validator()
    result = validator.validate_outputs(write_outputs(tmp_path, corrective_actions=valid_corrective_actions()))

    assert result.ok
    assert result.errors == []


def test_corrective_actions_missing_required_key_fails(tmp_path: Path) -> None:
    corrective = valid_corrective_actions()
    del corrective["corrective_actions"][0]["completion_criteria"]

    assert_invalid(
        write_outputs(tmp_path, corrective_actions=corrective),
        "corrective_actions.json.corrective_actions[0]: missing required key completion_criteria",
    )


def test_corrective_actions_invalid_enum_fails(tmp_path: Path) -> None:
    corrective = valid_corrective_actions()
    corrective["corrective_actions"][0]["priority"] = "urgent"
    corrective["corrective_actions"][0]["status"] = "done"

    output_dir = write_outputs(tmp_path, corrective_actions=corrective)
    assert_invalid(output_dir, "corrective_actions.json.corrective_actions[0].priority")
    assert_invalid(output_dir, "corrective_actions.json.corrective_actions[0].status")


def test_corrective_actions_empty_name_fails(tmp_path: Path) -> None:
    corrective = valid_corrective_actions()
    corrective["corrective_actions"][0]["name"] = ""

    assert_invalid(
        write_outputs(tmp_path, corrective_actions=corrective),
        "corrective_actions.json.corrective_actions[0].name",
    )


def test_corrective_actions_target_root_cause_must_exist(tmp_path: Path) -> None:
    corrective = valid_corrective_actions()
    corrective["corrective_actions"][0]["target_root_cause_id"] = "RC-MISSING"

    assert_invalid(
        write_outputs(tmp_path, corrective_actions=corrective),
        "corrective action CA-001 references unknown root cause RC-MISSING",
    )


def test_corrective_actions_invalid_json_fails(tmp_path: Path) -> None:
    output_dir = write_outputs(tmp_path)
    artifacts_dir = output_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "corrective_actions.json").write_text("{not json", encoding="utf-8")

    assert_invalid(output_dir, "corrective_actions.json is invalid JSON")


def test_corrective_actions_root_must_be_object(tmp_path: Path) -> None:
    output_dir = write_outputs(tmp_path)
    artifacts_dir = output_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "corrective_actions.json").write_text("[]", encoding="utf-8")

    assert_invalid(output_dir, "corrective_actions.json root must be an object")
