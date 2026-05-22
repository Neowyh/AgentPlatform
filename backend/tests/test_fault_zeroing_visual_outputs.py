from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
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

    assert "present_files" in content
    assert "展示五份文件" in content
    assert "不写脚本和外链资源" in content


def test_fault_zeroing_soul_requires_visual_outputs() -> None:
    content = (REPO_ROOT / "docs" / "fault-zeroing-agent" / "agent" / "SOUL.md").read_text(encoding="utf-8")

    for output in REQUIRED_OUTPUTS:
        assert output in content

    assert "SVG 不得包含脚本、外链资源或动态交互代码" in content


def test_fault_zeroing_sample_prompt_mentions_visual_outputs() -> None:
    content = (REPO_ROOT / "docs" / "zero_agent_eval_cases" / "README.md").read_text(encoding="utf-8")

    for output in REQUIRED_OUTPUTS:
        assert output in content
