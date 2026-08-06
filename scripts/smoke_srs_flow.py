#!/usr/bin/env python3
"""End-to-end smoke test for the SRS-writing agent flow (offline simulation).

Simulates the agent pipeline against the sample taskbook:
  1. parse taskbook (via officecli view) -> function item list
  2. candidate requirements per function item
  3. user confirmation (accepted/modified/rejected + one declared gap)
  4. generate srs_document.docx + traceability-matrix.docx via officecli
  5. write progress.json + requirement-catalog.md
  6. run validate_srs_outputs.py -> expect exit 0

Usage: python3 smoke_srs_flow.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OFFICECLI = REPO / "vendor" / "officecli" / "officecli"

FUNCTIONS = [
    ("F-5.1", "登录与权限管理"),
    ("F-5.2", "检测项目管理"),
    ("F-5.3", "检测流程执行"),
    ("F-5.4", "数据采集与存储"),
    ("F-5.5", "参数标定"),
    ("F-5.6", "履历管理"),
    ("F-5.7", "报告生成"),
    ("F-5.8", "数据导出"),
]

REQUIREMENTS = [
    ("F-5.1-1", "accepted", "F-5.1", "5.1", "软件启动后应显示登录界面，支持账号密码登录，认证通过后方可进入系统"),
    ("F-5.1-2", "accepted", "F-5.1", "4.4", "软件应实现三级用户权限体系（管理员、操作员、只读），按角色控制功能菜单可见性与操作权限"),
    ("F-5.1-3", "accepted", "F-5.1", "5.1", "密码连续错误5次应锁定账号30分钟"),
    ("F-5.1-4", "modified", "F-5.1", "5.1", "锁定期间应禁止该账号再次登录尝试，锁定到期后自动解锁（终稿）"),
    ("F-5.1-5", "rejected", "F-5.1", "5.1", "记住登录密码功能（用户拒绝：涉密环境不允许）"),
    ("F-5.2-1", "accepted", "F-5.2", "5.2", "软件应支持检测项目的创建、编辑与删除"),
    ("F-5.2-2", "accepted", "F-5.2", "5.2", "检测项目应包含编号、名称、委托单位、检测类型、计划时间字段"),
    ("F-5.2-3", "accepted", "F-5.2", "5.2", "项目列表应支持按状态筛选"),
    ("F-5.2-4", "accepted", "F-5.2", "4.2", "数据库记录数不小于100万条时，常见查询响应时间应不大于3秒"),
    ("F-5.3-1", "accepted", "F-5.3", "5.3", "软件应按照检测项模板顺序执行检测流程"),
    ("F-5.3-2", "accepted", "F-5.3", "5.3", "每个检测项执行前应显示操作提示"),
    ("F-5.3-3", "accepted", "F-5.3", "5.3", "检测项应支持手动跳过并记录原因"),
    ("F-5.3-4", "accepted", "F-5.3", "5.3", "执行过程中应实时显示采集曲线与当前状态"),
    ("F-5.3-5", "accepted", "F-5.3", "4.2", "单检测项执行周期应不大于2秒"),
    ("F-5.4-1", "accepted", "F-5.4", "5.4", "软件应按照设定采样率采集检测数据并实时入库"),
    ("F-5.4-2", "accepted", "F-5.4", "5.4", "单项目检测数据应自动归档，数据按项目目录组织"),
    ("F-5.4-3", "accepted", "F-5.4", "4.2", "连续采集8小时应不丢数"),
    ("F-5.4-4", "accepted", "F-5.4", "4.3", "与上位机应通过RS-422串口通信（波特率115200，8位数据位、1位停止位、无校验）"),
    ("F-5.5-1", "accepted", "F-5.5", "5.5", "软件应支持对传感器输出进行线性标定，标定系数可编辑保存"),
    ("F-5.5-2", "accepted", "F-5.5", "5.5", "标定过程应两次采样取均值"),
    ("F-5.5-3", "accepted", "F-5.5", "5.5", "标定结果应与检测数据关联记录"),
    ("F-5.6-1", "accepted", "F-5.6", "5.6", "软件应按装备编号建立履历档案"),
    ("F-5.6-2", "accepted", "F-5.6", "5.6", "履历应记录检测时间、检测结论、标定变更"),
    ("F-5.6-3", "accepted", "F-5.6", "5.6", "履历应支持按时间范围检索与打印"),
    ("F-5.6-4", "accepted", "F-5.6", "4.4", "履历数据删除应有审计记录，不可物理删除"),
    ("F-5.7-1", "accepted", "F-5.7", "5.7", "软件应根据检测结果自动生成检测报告（Word格式）"),
    ("F-5.7-2", "accepted", "F-5.7", "5.7", "报告应含封面、检测项明细、结论与签发栏"),
    ("F-5.7-3", "accepted", "F-5.7", "5.7", "报告模板应可维护"),
    ("F-5.8-1", "accepted", "F-5.8", "5.8", "软件应支持按项目导出检测数据，导出格式支持CSV与XML"),
    ("F-5.8-2", "accepted", "F-5.8", "5.8", "导出前应校验数据完整性，完整性校验不通过时给出警告清单"),
]

GAPS = [{"function_id": "F-6.1", "reason": "任务书第6章交付文档要求为交付物，不构成软件运行需求"}]


def run(cmd: list[str]) -> str:
    with tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False, encoding="utf-8") as tf:
        try:
            subprocess.run(cmd, check=True, stdout=tf, stderr=tf)
            tf.seek(0)
            return tf.read()
        finally:
            tf.close()


def build_progress() -> dict:
    return {
        "stage": "complete",
        "taskbook": "taskbook_detection_management.docx",
        "current_function": None,
        "functions": [{"id": fid, "name": name} for fid, name in FUNCTIONS],
        "requirements": [
            {
                "id": rid,
                "status": status,
                "source_function": src,
                "source_chapter": ch,
                "description": desc,
                "type": "功能" if src.startswith("F-5") and src != "F-5.4" and ch.startswith("5") else "性能/接口/安全",
                "priority": "高",
                "verification": "评审/测试",
            }
            for rid, status, src, ch, desc in REQUIREMENTS
        ],
        "gaps": GAPS,
        "declared_gaps": [g["function_id"] for g in GAPS],
        "srs_sections": {},
    }


def build_docx(path: Path, title: str, body_paras: list[str]) -> None:
    run([str(OFFICECLI), "close", str(path)])
    run([str(OFFICECLI), "create", str(path), "--force"])
    commands = [
        {"command": "add", "parent": "/body", "type": "paragraph", "props": {"text": title, "style": "Heading 1"}}
    ]
    for para in body_paras:
        commands.append({"command": "add", "parent": "/body", "type": "paragraph", "props": {"text": para, "style": "Normal"}})
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(commands, tf, ensure_ascii=False)
        tmp = tf.name
    try:
        run([str(OFFICECLI), "batch", str(path), "--input", tmp])
    finally:
        os.unlink(tmp)
    run([str(OFFICECLI), "close", str(path)])


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="End-to-end smoke test for SRS-writing agent outputs.")
    parser.add_argument("--outputs-dir", default="/tmp/srs-smoke-outputs", help="Temp dir holding generated outputs")
    args = parser.parse_args()
    outputs = Path(args.outputs_dir)
    outputs.mkdir(parents=True, exist_ok=True)
    progress = build_progress()

    accepted = [r for r in REQUIREMENTS if r[1] != "rejected"]
    srs_body = [f"{rid} {desc}" for rid, _, _, _, desc in accepted]
    matrix_body = [f"{rid} <- {src} ({ch})" for rid, _, src, ch, _ in accepted]
    build_docx(outputs / "srs_document.docx", "软件需求规格说明书（GJB438C-2021）", srs_body)
    build_docx(outputs / "traceability-matrix.docx", "需求追踪矩阵", matrix_body)

    (outputs / "progress.json").write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")

    catalog_lines = ["| ID | 状态 | 来源功能项 | 来源章节 | 描述 |", "|---|---|---|---|---|"]
    for rid, status, src, ch, desc in REQUIREMENTS:
        catalog_lines.append(f"| {rid} | {status} | {src} | {ch} | {desc} |")
    (outputs / "requirement-catalog.md").write_text("\n".join(catalog_lines) + "\n", encoding="utf-8")

    print("=== outputs generated under", outputs)
    for f in sorted(outputs.iterdir()):
        print(f"  {f.name} ({f.stat().st_size} bytes)")

    print("=== running offline validator against generated outputs")
    print(run([sys.executable, str(REPO / "scripts" / "validate_srs_outputs.py"), "--outputs-dir", str(outputs)]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
