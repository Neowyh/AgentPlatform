"""Deterministic Chinese report renderer for open-code-review findings JSON.

Reads the findings file produced by the ``ocr`` CLI (a JSON array of comment
objects, or an object wrapping them under ``comments``) and renders a stable
Markdown report: findings grouped by severity, only core categories expanded,
positioning failures and unparseable rows quarantined in dedicated sections.
Output is byte-for-byte reproducible for the same input when
``--no-timestamp`` is passed.
Pure standard library, runs standalone — safe for intranet hosts.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SEVERITY_ORDER = ("critical", "high", "medium", "low", "")
SEVERITY_TITLES = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "": "未分级",
}
CORE_CATEGORIES = ("bug", "security", "performance", "test")
APPENDIX_CATEGORIES = ("style", "maintainability", "documentation", "other")
ALL_CATEGORIES = CORE_CATEGORIES + APPENDIX_CATEGORIES


class InvalidFindings(Exception):
    """Raised when the input file is not a usable findings document."""


def _extract_rows(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("comments"), list):
        return payload["comments"]
    raise InvalidFindings("findings 必须是 JSON 数组，或含 comments 数组的对象")


def _validate_row(index: int, row: object) -> tuple[dict[str, object] | None, str | None]:
    if not isinstance(row, dict):
        return None, f"条目 #{index}: 不是对象"
    path = row.get("path")
    content = row.get("content")
    if not isinstance(path, str) or not path.strip():
        return None, f"条目 #{index}: 缺少必填字段 path"
    if not isinstance(content, str) or not content.strip():
        return None, f"条目 #{index}: 缺少必填字段 content"
    severity = row.get("severity", "")
    if severity != "" and (
        not isinstance(severity, str) or severity not in ("critical", "high", "medium", "low")
    ):
        return None, f"条目 #{index}: severity 不在允许枚举内 ({severity!r})"
    category = row.get("category", "")
    if category != "" and (not isinstance(category, str) or category not in ALL_CATEGORIES):
        return None, f"条目 #{index}: category 不在允许枚举内 ({category!r})"
    return row, None


def _anchor(row: dict[str, object]) -> str:
    path = str(row["path"])
    start = row.get("start_line")
    end = row.get("end_line")
    if isinstance(start, int) and start > 0:
        if isinstance(end, int) and end > start:
            return f"`{path}:{start}-{end}`"
        return f"`{path}:{start}`"
    if isinstance(end, int) and end > 0:
        return f"`{path}:{end}`"
    return f"`{path}`"


def _is_positioning_failure(row: dict[str, object]) -> bool:
    start = row.get("start_line")
    end = row.get("end_line")
    return start == 0 and end == 0


def _fence_for(text: str) -> str:
    longest = 0
    run = 0
    for char in text:
        run = run + 1 if char == "`" else 0
        longest = max(longest, run)
    return "`" * max(3, longest + 1)


def _code_block(code: object) -> str:
    if not isinstance(code, str) or not code.strip():
        return ""
    text = code.strip("\n")
    fence = _fence_for(text)
    return f"{fence}\n{text}\n{fence}\n"


def _render_entry(row: dict[str, object], *, positioned: bool) -> str:
    category = str(row.get("category", "")) or "未分类"
    suffix = "" if positioned else "（定位失败，需读取文件人工定位）"
    lines = [f"### {_anchor(row)} [{category}]{suffix}", "", f"**{row['content']}**", ""]
    existing = _code_block(row.get("existing_code"))
    if existing:
        lines += ["原代码：", "", existing]
    suggestion = _code_block(row.get("suggestion_code"))
    if suggestion:
        lines += ["修复建议：", "", suggestion]
    lines.append("")
    return "\n".join(lines)


def render_report(
    rows: list[object],
    *,
    source_name: str,
    title: str,
    generated_at: str | None = None,
) -> str:
    valid: list[dict[str, object]] = []
    rejected: list[str] = []
    for index, row in enumerate(rows, start=1):
        parsed, reason = _validate_row(index, row)
        if parsed is None:
            assert reason is not None
            preview = ""
            if isinstance(row, dict) and isinstance(row.get("content"), str):
                preview = f" —「{row['content']}」"
            rejected.append(f"- {reason}{preview}")
        else:
            valid.append(parsed)

    severity_counts = {key: 0 for key in SEVERITY_ORDER}
    category_counts = {key: 0 for key in ALL_CATEGORIES}
    for row in valid:
        severity_counts[str(row.get("severity", ""))] += 1
        category = str(row.get("category", ""))
        if category in category_counts:
            category_counts[category] += 1

    main_rows = [row for row in valid if str(row.get("category", "")) not in APPENDIX_CATEGORIES]
    failure_rows = [row for row in main_rows if _is_positioning_failure(row)]
    anchored_rows = [row for row in main_rows if not _is_positioning_failure(row)]

    lines = [f"# {title}", ""]
    if generated_at is not None:
        lines.append(f"- 生成时间: {generated_at}")
    lines.append(f"- 结果文件: {source_name}")
    lines.append(
        f"- 条目总数: {len(rows)}（有效条目: {len(valid)}，解析失败条目: {len(rejected)}）"
    )
    lines.append(
        "- 严重级别分布: "
        + ", ".join(f"{key or '未分级'}: {count}" for key, count in severity_counts.items())
    )
    uncategorized = sum(1 for row in valid if not str(row.get("category", "")))
    lines.append(
        "- 类别分布: "
        + ", ".join(f"{key}: {count}" for key, count in category_counts.items())
        + f", 未分类: {uncategorized}"
    )
    lines.append("")

    if not main_rows:
        lines.append("未发现需要报告的问题条目。")
    for severity in SEVERITY_ORDER:
        grouped = [row for row in anchored_rows if str(row.get("severity", "")) == severity]
        if not grouped:
            continue
        lines.append(f"## {SEVERITY_TITLES[severity]}")
        lines.append("")
        for row in grouped:
            lines.append(_render_entry(row, positioned=True))
    if failure_rows:
        lines.append("## 定位失败条目")
        lines.append("")
        lines.append("以下条目未能定位到具体行号（start_line 与 end_line 均为 0），")
        lines.append("请阅读目标文件并结合评论上下文人工定位：")
        lines.append("")
        for row in failure_rows:
            lines.append(_render_entry(row, positioned=False))
    if any(category_counts[key] for key in APPENDIX_CATEGORIES):
        lines.append("## 附录：非核心类别计数")
        lines.append("")
        lines.append(
            "style / maintainability / documentation / other 类问题属于规范与设计评审"
            "（code-review 技能）的职责范围，本报告仅计数，不展开："
        )
        lines.append("")
        for key in APPENDIX_CATEGORIES:
            lines.append(f"- {key}: {category_counts[key]}")
        lines.append("")
    if rejected:
        lines.append("## 解析失败条目")
        lines.append("")
        lines.extend(rejected)
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="渲染 ocr findings 为中文审计报告")
    parser.add_argument("--findings", required=True, help="ocr 输出的 findings JSON 文件")
    parser.add_argument("--out", required=True, help="输出的 Markdown 报告路径")
    parser.add_argument("--title", default="代码审计报告", help="报告标题")
    parser.add_argument(
        "--no-timestamp",
        action="store_true",
        help="省略生成时间行，使输出可复现（同输入同输出）",
    )
    args = parser.parse_args(argv)

    findings_path = Path(args.findings)
    try:
        payload = json.loads(findings_path.read_text(encoding="utf-8"))
        rows = _extract_rows(payload)
    # ValueError 同时覆盖 json.JSONDecodeError 与 UnicodeDecodeError
    except (OSError, ValueError, InvalidFindings) as exc:
        print(f"无法读取 findings 文件: {exc}", file=sys.stderr)
        return 2

    generated_at = (
        None
        if args.no_timestamp
        else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )
    report = render_report(
        rows,
        source_name=findings_path.name,
        title=args.title,
        generated_at=generated_at,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
