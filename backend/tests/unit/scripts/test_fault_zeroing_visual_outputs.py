from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
REQUIRED_OUTPUTS = [
    "fault_tree.json",
    "fault_tree.svg",
    "bottom_event_assessment.md",
    "analysis_process.svg",
    "zeroing_report.md",
]
STAGE_MARKERS = [
    "证据提取",
    "故障树构建",
    "底事件评估",
    "根因归因",
    "纠正措施",
    "文档生产",
]
RESPONSIBILITY_PHRASES = [
    "演绎建树阶段不依赖证据台账",
    "证据检漏只做添加不做删除",
    "文档阶段不修改分析数据",
]
REMOVED_WORKFLOW_PHRASES = [
    "资料盘点",
    "报告生成",
    "报告审查",
    "最多只进行一轮核心委托",
    "evidence-reader 不输出根因",
    "先生成证据台账，再构建故障树",
]


def test_fault_zeroing_skill_requires_visual_outputs() -> None:
    content = (REPO_ROOT / "resources" / "skills" / "fault-zeroing" / "SKILL.md").read_text(encoding="utf-8")

    for output in REQUIRED_OUTPUTS:
        assert output in content

    for phrase in [
        "证据台账",
        *STAGE_MARKERS,
        "资料覆盖矩阵",
        "scripts/validate_fault_zeroing_outputs.py",
        "probability_basis",
        "06_expected_analysis.md",
        *RESPONSIBILITY_PHRASES,
    ]:
        assert phrase in content

    assert "present_files" in content
    assert "展示五份文件" in content
    assert "不写脚本和外链资源" in content

    assert "read_document" in content
    for phrase in [
        ".docx` / `.pdf",
        "page_range",
        "疑似扫描件",
    ]:
        assert phrase in content

    # Legacy .doc is unsupported: the skill must not advertise it as readable
    # and must instruct recording it as missing material instead.
    assert ".doc` / `.docx" not in content
    assert "不支持 legacy 二进制 `.doc`" in content
    # Tool error responses (e.g. read_document JSON errors) must be treated
    # under the failure contract, never ingested as document content.
    assert "JSON 错误" in content

    for phrase in REMOVED_WORKFLOW_PHRASES:
        assert phrase not in content


def test_fault_zeroing_soul_requires_visual_outputs() -> None:
    content = (REPO_ROOT / "resources" / "agents" / "fault-zeroing" / "SOUL.md").read_text(encoding="utf-8")

    for output in REQUIRED_OUTPUTS:
        assert output in content

    for phrase in [
        "证据台账",
        *STAGE_MARKERS,
        "资料覆盖矩阵",
        "scripts/validate_fault_zeroing_outputs.py",
        "probability_basis",
        "06_expected_analysis.md",
        *RESPONSIBILITY_PHRASES,
    ]:
        assert phrase in content

    assert "SVG 不得包含脚本、外链资源或动态交互代码" in content

    # Drift guards: conclusion status enum must match fault_tree.schema.json
    # (conclusion_status), and the schema path must be the runtime mount path.
    assert "`in_progress`、`not_applicable`" not in content
    assert "skills/custom/fault-zeroing" not in content
    assert "/mnt/skills/fault-zeroing/templates/fault_tree.schema.json" in content
    assert "不得用于结论状态" in content

    for phrase in REMOVED_WORKFLOW_PHRASES:
        assert phrase not in content


def test_fault_zeroing_sample_prompt_mentions_visual_outputs() -> None:
    content = (REPO_ROOT / "docs" / "zero_agent_eval_cases" / "README.md").read_text(encoding="utf-8")

    for output in REQUIRED_OUTPUTS:
        assert output in content
