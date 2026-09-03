"""Tests for the versioned fault-zeroing Result Contract (ticket 01)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = REPO_ROOT / "backend" / "packages" / "harness" / "ideer" / "fault_zeroing" / "contract.py"
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_fault_zeroing_outputs.py"


def load_contract():
    spec = importlib.util.spec_from_file_location("fz_contract", CONTRACT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("fz_contract", module)
    spec.loader.exec_module(module)
    return module


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_fault_zeroing_outputs", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Shared fixture builders (mirrors the legacy validator test fixtures).
# ---------------------------------------------------------------------------


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


def write_outputs(
    tmp_path: Path,
    fault_tree: dict | None = None,
    report: str | None = None,
) -> Path:
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
    return output_dir


def codes_of(verdict) -> set[str]:
    return {finding.code for finding in verdict.findings}


# ---------------------------------------------------------------------------
# Contract behaviour tests.
# ---------------------------------------------------------------------------


def test_valid_outputs_produce_ok_verdict_with_digests(tmp_path: Path) -> None:
    contract = load_contract()
    verdict = contract.evaluate_result_contract(write_outputs(tmp_path))

    assert verdict.ok, verdict.errors
    assert verdict.contract_version == contract.CONTRACT_VERSION
    assert len(verdict.contract_fingerprint) == 64
    assert set(verdict.artifact_digests) == set(contract.REQUIRED_OUTPUTS)
    assert all(len(digest) == 64 for digest in verdict.artifact_digests.values())
    assert verdict.codes() == []


def test_findings_carry_stable_reason_codes_and_locations(tmp_path: Path) -> None:
    contract = load_contract()
    tree = valid_fault_tree()
    tree["bottom_events"][0]["confidence"] = "certain"
    (tmp_path / "outputs").mkdir()
    verdict = contract.evaluate_result_contract(write_outputs(tmp_path, tree))

    assert not verdict.ok
    confidence_findings = [finding for finding in verdict.findings if finding.code == "confidence_invalid"]
    assert len(confidence_findings) == 1
    finding = confidence_findings[0]
    assert finding.artifact == "fault_tree.json"
    assert finding.location == "bottom_events.BE-01"
    assert "BE-01 has invalid confidence certain" in finding.message


def test_missing_output_reason_code(tmp_path: Path) -> None:
    contract = load_contract()
    output_dir = write_outputs(tmp_path)
    (output_dir / "fault_tree.svg").unlink()

    verdict = contract.evaluate_result_contract(output_dir)

    assert not verdict.ok
    assert "output_missing" in codes_of(verdict)


def test_unsupported_contract_version_is_explicit(tmp_path: Path) -> None:
    contract = load_contract()
    verdict = contract.evaluate_result_contract(write_outputs(tmp_path), contract_version="0.9.0")

    assert not verdict.ok
    assert "contract_version_unsupported" in codes_of(verdict)
    assert verdict.contract_version == "0.9.0"


def test_pinned_current_contract_version_passes(tmp_path: Path) -> None:
    contract = load_contract()
    verdict = contract.evaluate_result_contract(write_outputs(tmp_path), contract_version=contract.CONTRACT_VERSION)

    assert verdict.ok, verdict.errors


def test_finding_confidence_values_are_accepted(tmp_path: Path) -> None:
    """Code Evidence "Finding Confidence" values must not be rejected.

    Regression for the confidence drift between the workflow schema gate
    (7-value enum) and the legacy validator (4-value enum).
    """
    contract = load_contract()
    tree = valid_fault_tree()
    tree["bottom_events"][0]["confidence"] = "high_risk_candidate"
    tree["root_causes"][0]["confidence"] = "pending_verification"

    verdict = contract.evaluate_result_contract(write_outputs(tmp_path, tree))

    assert verdict.ok, verdict.errors


def test_root_cause_confidence_is_checked(tmp_path: Path) -> None:
    contract = load_contract()
    tree = valid_fault_tree()
    tree["root_causes"][0]["confidence"] = "definitely"

    verdict = contract.evaluate_result_contract(write_outputs(tmp_path, tree))

    assert not verdict.ok
    confidence_findings = [finding for finding in verdict.findings if finding.code == "confidence_invalid"]
    assert any("RC-01" in finding.message for finding in confidence_findings)


def test_schema_confidence_enum_matches_contract(tmp_path: Path) -> None:
    """Anti-drift guard: the bundled schema and the contract must agree."""

    contract = load_contract()
    schema = json.loads((REPO_ROOT / "resources" / "skills" / "fault-zeroing" / "templates" / "fault_tree.schema.json").read_text(encoding="utf-8"))

    assert set(schema["$defs"]["confidence"]["enum"]) == contract.CONFIDENCE_VALUES
    assert set(schema["$defs"]["conclusion_status"]["enum"]) == contract.STATUS_VALUES
    assert set(schema["$defs"]["verification_status"]["enum"]) == contract.VERIFICATION_STATUS_VALUES
    assert set(schema["$defs"]["evidence_grade"]["enum"]) == contract.EVIDENCE_GRADES


def test_verdict_to_json_is_round_trippable(tmp_path: Path) -> None:
    contract = load_contract()
    tree = valid_fault_tree()
    tree["evidence"][0]["grade"] = "E"
    verdict = contract.evaluate_result_contract(write_outputs(tmp_path, tree))

    payload = json.loads(verdict.to_json())

    assert payload["ok"] is False
    assert payload["contract_version"] == contract.CONTRACT_VERSION
    assert any(f["code"] == "grade_invalid" for f in payload["findings"])


def test_legacy_validate_outputs_alias_keeps_text_contract(tmp_path: Path) -> None:
    """The CLI shim keeps the legacy ``validate_outputs`` API and messages."""

    validator = load_validator()
    output_dir = write_outputs(tmp_path)

    result = validator.validate_outputs(output_dir)
    assert result.ok
    assert result.errors == []

    tree = valid_fault_tree()
    tree["bottom_events"][1]["parent_ids"] = ["IE-MISSING"]
    output_dir = write_outputs(tmp_path, tree)
    result = validator.validate_outputs(output_dir)
    assert not result.ok
    assert "BE-02 references unknown parent_id IE-MISSING" in "\n".join(result.errors)


def test_cli_json_mode_emits_verdict(tmp_path: Path, capsys) -> None:
    validator = load_validator()
    output_dir = write_outputs(tmp_path)

    exit_code = validator.main(["--outputs-dir", str(output_dir), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["contract_version"] == validator.CONTRACT_VERSION


def test_contract_constants_match_schema_files(tmp_path: Path) -> None:
    """Every semantic enum used by the contract has one shared definition."""

    contract = load_contract()
    corrective = json.loads((REPO_ROOT / "resources" / "skills" / "fault-zeroing" / "templates" / "corrective_actions.schema.json").read_text(encoding="utf-8"))

    assert contract.SUPPORTED_CONTRACT_VERSIONS == (contract.CONTRACT_VERSION,)
    assert "corrective_actions" in json.dumps(corrective)


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        (lambda t: t["bottom_events"][0].update(status="likely"), "status_invalid"),
        (lambda t: t["evidence"][0].update(grade="Z"), "grade_invalid"),
        (
            lambda t: t["verification_plan"][0].update(status="to_verify"),
            "verification_status_invalid",
        ),
        (
            lambda t: t["evidence"][0].update(source="06_expected_analysis.md#L3"),
            "evidence_source_forbidden",
        ),
    ],
)
def test_semantic_reason_codes(tmp_path: Path, mutate, expected_code: str) -> None:
    contract = load_contract()
    tree = valid_fault_tree()
    mutate(tree)

    verdict = contract.evaluate_result_contract(write_outputs(tmp_path, tree))

    assert not verdict.ok
    assert expected_code in codes_of(verdict)
