"""Offline tests for the code-audit skill's deterministic report renderer.

The ``open-code-review`` skill wraps the ``ocr`` CLI; ``render_report.py`` is
the only script we ship alongside it. It turns an ocr-style findings JSON
file into a deterministic Chinese review report so the agent never has to
transcribe machine output by hand.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
RENDER_SCRIPT = REPO_ROOT / "resources" / "skills" / "open-code-review" / "scripts" / "render_report.py"

SEVERITY_SECTIONS = ("Critical", "High", "Medium", "Low")
MAIN_CATEGORIES = ("bug", "security", "performance", "test")
APPENDIX_CATEGORIES = ("style", "maintainability", "documentation", "other")


def _finding(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "path": "src/main.c",
        "content": "缓冲区拷贝缺少长度校验",
        "start_line": 42,
        "end_line": 42,
        "category": "security",
        "severity": "high",
        "suggestion_code": "strncpy(dst, src, sizeof(dst));",
        "existing_code": "strcpy(dst, src);",
    }
    row.update(overrides)
    return row


def _run_render(tmp_path: Path, payload: object) -> tuple[subprocess.CompletedProcess[str], str]:
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report_path = tmp_path / "review_report.md"
    proc = subprocess.run(
        [
            sys.executable,
            str(RENDER_SCRIPT),
            "--findings",
            str(findings),
            "--out",
            str(report_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    return proc, report


def test_render_groups_and_orders_by_severity(tmp_path: Path) -> None:
    proc, report = _run_render(
        tmp_path,
        [
            _finding(severity="low", content="低危问题"),
            _finding(severity="critical", content="致命问题"),
            _finding(severity="medium", content="中危问题"),
            _finding(severity="high", content="高危问题"),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    positions = [report.index(f"## {title}") for title in SEVERITY_SECTIONS]
    assert positions == sorted(positions)
    assert "致命问题" in report.split("## Critical", 1)[1].split("## High", 1)[0]
    assert "低危问题" in report.split("## Low", 1)[1]


def test_render_expands_main_categories_and_demotes_style_to_appendix(
    tmp_path: Path,
) -> None:
    proc, report = _run_render(
        tmp_path,
        [
            _finding(category="bug", content="空指针解引用"),
            _finding(category="security", content="命令注入"),
            _finding(category="performance", content="循环内重复查询"),
            _finding(category="test", content="缺少回归测试"),
            _finding(category="style", content="命名不清晰"),
            _finding(category="maintainability", content="重复逻辑"),
            _finding(category="documentation", content="注释缺失"),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    for content in ("空指针解引用", "命令注入", "循环内重复查询", "缺少回归测试"):
        assert content in report
    appendix = report.split("## 附录", 1)[1]
    for category in APPENDIX_CATEGORIES:
        assert category in appendix
    # 附录只计数，不展开条目正文
    assert "命名不清晰" not in report
    assert "重复逻辑" not in report
    assert "注释缺失" not in report


def test_render_collects_positioning_failures(tmp_path: Path) -> None:
    proc, report = _run_render(
        tmp_path,
        [
            _finding(start_line=0, end_line=0, content="无法定位的发现"),
            _finding(content="正常定位的发现"),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    section = report.split("## 定位失败条目", 1)[1]
    assert "无法定位的发现" in section
    assert "正常定位的发现" not in section


def test_render_reports_counts(tmp_path: Path) -> None:
    proc, report = _run_render(
        tmp_path,
        [
            _finding(severity="critical"),
            _finding(severity="critical"),
            _finding(severity="high"),
            _finding(category="style", severity="low"),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    assert "有效条目: 4" in report
    assert "critical: 2" in report
    assert "high: 1" in report
    assert "style: 1" in report


def test_render_rejects_invalid_rows_with_reason(tmp_path: Path) -> None:
    proc, report = _run_render(
        tmp_path,
        [
            _finding(),
            {"content": "缺少 path 字段", "severity": "high"},
            _finding(severity="ultra", content="非法严重级别"),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    assert "有效条目: 1" in report
    section = report.split("## 解析失败条目", 1)[1]
    assert "缺少 path 字段" in section
    assert "severity" in section
    assert "非法严重级别" not in report.split("## 解析失败条目", 1)[0]


def test_render_accepts_comments_object_shape(tmp_path: Path) -> None:
    proc, report = _run_render(tmp_path, {"comments": [_finding(content="对象包裹的发现")]})
    assert proc.returncode == 0, proc.stderr
    assert "对象包裹的发现" in report


def test_render_clean_result_still_succeeds(tmp_path: Path) -> None:
    proc, report = _run_render(tmp_path, [])
    assert proc.returncode == 0, proc.stderr
    assert "未发现" in report


def test_render_invalid_json_fails_loudly(tmp_path: Path) -> None:
    findings = tmp_path / "findings.json"
    findings.write_text("not json", encoding="utf-8")
    report_path = tmp_path / "review_report.md"
    proc = subprocess.run(
        [sys.executable, str(RENDER_SCRIPT), "--findings", str(findings), "--out", str(report_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert not report_path.exists()


def test_render_invalid_utf8_fails_gracefully(tmp_path: Path) -> None:
    findings = tmp_path / "findings.json"
    findings.write_bytes(b"\xff\xfe not utf-8")
    report_path = tmp_path / "review_report.md"
    proc = subprocess.run(
        [sys.executable, str(RENDER_SCRIPT), "--findings", str(findings), "--out", str(report_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    # 非法编码必须走友好错误分支（退出码 2），不得抛原始 traceback
    assert proc.returncode == 2
    assert "无法读取 findings 文件" in proc.stderr
    assert "Traceback" not in proc.stderr
    assert not report_path.exists()


def test_render_counts_uncategorized_rows(tmp_path: Path) -> None:
    proc, report = _run_render(
        tmp_path,
        [_finding(), {"path": "a.py", "content": "无类别条目"}],
    )
    assert proc.returncode == 0, proc.stderr
    # 与 severity 的「未分级」对称：空类别条目必须计入「未分类」桶，计数可核对
    assert "未分类: 1" in report


def test_render_keeps_snippet_fences_escaped(tmp_path: Path) -> None:
    proc, report = _run_render(
        tmp_path,
        [_finding(existing_code="```\ninner fenced block\n```")],
    )
    assert proc.returncode == 0, proc.stderr
    # 片段自带三反引号时，外层围栏必须加长，片段不得截断代码块
    assert "````\n```\ninner fenced block\n```\n````" in report


def test_render_timestamp_opt_out_makes_output_deterministic(tmp_path: Path) -> None:
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps([_finding()], ensure_ascii=False), encoding="utf-8")

    def render(out_name: str, *extra: str) -> str:
        out = tmp_path / out_name
        proc = subprocess.run(
            [sys.executable, str(RENDER_SCRIPT), "--findings", str(findings), "--out", str(out), *extra],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        return out.read_text(encoding="utf-8")

    assert "生成时间" in render("default.md")
    first = render("det1.md", "--no-timestamp")
    second = render("det2.md", "--no-timestamp")
    assert "生成时间" not in first
    assert first == second


def test_render_script_has_no_runtime_network_or_install_calls() -> None:
    source = RENDER_SCRIPT.read_text(encoding="utf-8")
    for token in ("-m pip", "subprocess", "urllib", "socket", "requests", "http://"):
        assert token not in source, f"render_report.py must not contain {token!r}: intranet hosts have no network"
