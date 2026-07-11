from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
REQUIRED_OUTPUTS = [
    "fault_tree.json",
    "fault_tree.svg",
    "bottom_event_assessment.md",
    "analysis_process.svg",
    "zeroing_report.md",
]


def test_fault_zeroing_skill_requires_visual_outputs() -> None:
    content = (REPO_ROOT / "skills" / "custom" / "fault-zeroing" / "SKILL.md").read_text(encoding="utf-8")

    for output in REQUIRED_OUTPUTS:
        assert output in content

    for phrase in [
        "资料盘点",
        "证据台账",
        "故障树构建",
        "底事件评估",
        "根因归因",
        "验证计划",
        "报告生成",
        "报告审查",
        "资料覆盖矩阵",
        "最多只进行一轮核心委托",
        "scripts/validate_fault_zeroing_outputs.py",
        "probability_basis",
        "06_expected_analysis.md",
    ]:
        assert phrase in content

    assert "present_files" in content
    assert "展示五份文件" in content
    assert "不写脚本和外链资源" in content
    assert "evidence-reader 不输出根因" in content
    assert "fault-tree-builder 不给最终归因" in content
    assert "report-reviewer 不新增技术结论" in content


def test_fault_zeroing_soul_requires_visual_outputs() -> None:
    content = (REPO_ROOT / "docs" / "fault-zeroing-agent" / "agent" / "SOUL.md").read_text(encoding="utf-8")

    for output in REQUIRED_OUTPUTS:
        assert output in content

    for phrase in [
        "资料盘点",
        "证据台账",
        "故障树构建",
        "底事件评估",
        "根因归因",
        "验证计划",
        "报告生成",
        "报告审查",
        "资料覆盖矩阵",
        "最多只进行一轮核心委托",
        "scripts/validate_fault_zeroing_outputs.py",
        "probability_basis",
        "06_expected_analysis.md",
    ]:
        assert phrase in content

    assert "SVG 不得包含脚本、外链资源或动态交互代码" in content
    assert "evidence-reader 不输出根因" in content
    assert "fault-tree-builder 不给最终归因" in content
    assert "report-reviewer 不新增技术结论" in content


def test_fault_zeroing_sample_prompt_mentions_visual_outputs() -> None:
    content = (REPO_ROOT / "docs" / "zero_agent_eval_cases" / "README.md").read_text(encoding="utf-8")

    for output in REQUIRED_OUTPUTS:
        assert output in content
