"""Static-analysis bridge for Code Evidence Packages (ticket 01).

``analyze_code_evidence`` is the model's only entry to the fixed scan library
(``deerflow.uploads.code_analysis``): it accepts nothing but this thread's
Code Evidence Package root under ``/mnt/user-data/code-evidence/``, resolves
the path inside the server (the filesystem middleware is not involved), runs
the read-only scanner set for the package's language and writes
inventory/findings/scanner_status into the package's ``analysis/`` directory.

Fixed capability, matching the fault-zeroing SKILL promise: no custom paths,
commands or parameters. Scanner unavailability is disclosed honestly — a
missing binary never masquerades as "scanned, no findings" — and every
finding keeps the Finding Confidence semantics: a static alert alone is
never ``confirmed``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain.tools import tool

from app.agentplatform.tools.code_evidence_access import (
    CODE_EVIDENCE_VIRTUAL_ROOT,
    PackageAccessRejected,
    get_thread_id,
    resolve_package_dir,
)
from deerflow.tools.types import Runtime
from deerflow.uploads.code_analysis import (
    detect_language,
    run_static_analysis,
    write_analysis_summary,
)

logger = logging.getLogger(__name__)

_FINDINGS_PREVIEW_LIMIT = 20


def _next_action(result_overall: str, language: str | None) -> str:
    if language is None:
        return "包内未发现受支持的源码文件（C/C++ 或 Python），未运行扫描器；请用 glob/grep/read_file 直接阅读包内文本证据。"
    if result_overall == "scanners_unavailable":
        return "扫描器二进制在当前环境不可用：本次没有机器扫描告警，请如实向用户披露 scanners_unavailable（见 scanner_status.json），并改用 read_file/grep 人工阅读源码与日志；不要把“没扫”说成“扫过无发现”。"
    return "findings 是静态告警证据，confidence 恒为 high_risk_candidate（静态告警单独永不 confirmed）；请结合日志与人工阅读交叉验证后再升级或降级，不得直接写成 confirmed 根因。完整清单见 analysis/findings.json。"


def _analyze_code_evidence_sync(runtime: Runtime, declared_root: str) -> str:
    thread_id = get_thread_id(runtime)
    if not thread_id:
        return json.dumps({"error": "当前会话缺少 thread 上下文，无法分析代码证据包", "reason_code": "thread_context_missing"}, ensure_ascii=False)
    try:
        package_dir, package_id = resolve_package_dir(runtime, declared_root, thread_id)
    except PackageAccessRejected as exc:
        return json.dumps(
            {
                "error": str(exc),
                "reason_code": exc.reason_code,
                "allowed_pattern": f"{CODE_EVIDENCE_VIRTUAL_ROOT}/<package_id>",
            },
            ensure_ascii=False,
        )

    result = run_static_analysis(package_dir)
    try:
        write_analysis_summary(package_dir / "analysis", result)
    except OSError as exc:
        logger.error("Failed to write analysis artifacts for package %s: %s", package_id, exc)
        return json.dumps({"error": f"分析产物写入失败: {exc}", "reason_code": "analysis_write_failed"}, ensure_ascii=False)

    inventory = result.inventory
    language = detect_language(inventory)
    payload: dict[str, Any] = {
        "package_id": package_id,
        "language": language,
        "analysis_dir": f"{CODE_EVIDENCE_VIRTUAL_ROOT}/{package_id}/analysis",
        "inventory_summary": {
            "total_files": len(inventory["files"]),
            "c_cpp_source_files": len(inventory["source_files"]),
            "python_files": len(inventory["python_files"]),
            "headers": len(inventory["headers"]),
            "logs": len(inventory["logs"]),
            "compilation_configuration_verified": inventory["compilation_configuration_verified"],
        },
        "overall": result.overall,
        "scanner_status": [status.as_dict() for status in result.statuses],
        "findings_count": len(result.findings),
        "findings_preview": [finding.as_dict() for finding in result.findings[:_FINDINGS_PREVIEW_LIMIT]],
        "next_action": _next_action(result.overall, language),
    }
    return json.dumps(payload, ensure_ascii=False)


@tool("analyze_code_evidence", parse_docstring=True)
async def analyze_code_evidence_tool(runtime: Runtime, package_root: str) -> str:
    """对本会话的代码证据包运行固定的只读静态扫描并落盘分析产物。

    归零代码证据的机器扫描入口（固定能力）：不接受自定义路径、命令或参数，
    仅接受本会话代码证据包根目录。按语言分发扫描器——C/C++ 用 clang-tidy 与
    cppcheck，Python 用 ruff 与 bandit（均只读）；包内没有 compile_commands.json
    时跳过 clang-tidy 并记录跳过原因。产物写入包内 analysis/（inventory.json、
    findings.json、scanner_status.json）。扫描器二进制缺失时如实返回
    scanner_status（available=false / overall=scanners_unavailable），不会伪装成
    “扫过无发现”。所有告警的 confidence 为 high_risk_candidate：静态告警单独
    永不 confirmed。

    Args:
        package_root: 代码证据包根目录，必须是 /mnt/user-data/code-evidence/<package_id>（也接受以 /source 结尾的源码根形式）。
    """
    return await asyncio.to_thread(_analyze_code_evidence_sync, runtime, package_root)
