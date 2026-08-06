"""Per-run execution record written to the run workspace.

Every persisted workflow event is appended to a JSONL file
(``.workflow/logs/run_record.jsonl``); once the run reaches a terminal state a
human-readable Markdown summary (``.workflow/logs/run_record.md``) is rendered
from the persisted event log.  Host paths are never written — all paths are
virtual sandbox paths resolved through the run's resolver.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ideer.persistence.models.workflow_v2 import WorkflowV2EventRow, WorkflowV2RunRow

from .store import WorkflowV2Store

logger = logging.getLogger(__name__)

_TERMINAL = {"completed", "failed", "cancelled"}

_MD_PAYLOAD_CAP = 2000


def _render_payload(payload: dict[str, Any]) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(payload)


class RunRecordWriter:
    """Append events to JSONL and finalize a Markdown summary per run."""

    def __init__(self, resolver, record_dir: str) -> None:
        self.resolver = resolver
        self.record_dir = record_dir
        self._lock = asyncio.Lock()

    def _host_path(self, extension: str) -> Path | None:
        host = self.resolver(f"{self.record_dir}/run_record.{extension}")
        if host is None:
            return None
        return Path(host)

    async def on_event(self, event: WorkflowV2EventRow | None) -> None:
        if event is None:
            return
        path = self._host_path("jsonl")
        if path is None:
            return
        line = json.dumps(
            {
                "seq": event.seq,
                "type": event.event_type,
                "payload": event.payload,
                "created_at": event.created_at.isoformat() if isinstance(event.created_at, datetime) else None,
            },
            ensure_ascii=False,
            default=str,
        )
        async with self._lock:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
            except OSError:
                logger.exception("failed to append run record %s", path)

    async def finalize(self, store: WorkflowV2Store, run: WorkflowV2RunRow) -> None:
        path = self._host_path("md")
        if path is None:
            return
        events = await store.list_events(run.run_id)
        async with self._lock:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(_render_markdown(run, events), encoding="utf-8")
            except OSError:
                logger.exception("failed to write run record %s", path)


def _render_markdown(run: WorkflowV2RunRow, events: list[WorkflowV2EventRow]) -> str:
    lines: list[str] = []
    lines.append(f"# 运行记录 `{run.run_id}`")
    lines.append("")
    lines.append(f"- 工作流: `{run.workflow_name}`")
    lines.append(f"- 定义版本: v{run.definition_version}")
    lines.append(f"- 状态: `{run.status}`")
    if run.error:
        lines.append(f"- 错误: `{run.error}`")
    lines.append(f"- 创建人: `{run.created_by}`")
    if isinstance(run.inputs, dict):
        lines.append(f"- 输入: ```json\n{json.dumps(run.inputs, ensure_ascii=False, indent=2, default=str)}\n```")
    lines.append("")

    node_sections: dict[str, list[WorkflowV2EventRow]] = {}
    node_states: dict[str, dict[str, Any]] = {}
    for event in events:
        node_id = event.payload.get("node_id")
        if event.event_type in {"node_started", "node_completed", "node_failed", "node_skipped"} and isinstance(node_id, str):
            node_sections.setdefault(node_id, []).append(event)
            node_states.setdefault(node_id, {})[event.event_type] = event

    if node_sections:
        lines.append("## 节点执行摘要")
        lines.append("")
        lines.append("| 节点 | 状态 | 耗时 | 结果/错误 |")
        lines.append("|------|------|------|-----------|")
        for node_id, state in node_states.items():
            started = state.get("node_started")
            terminal = state.get("node_completed") or state.get("node_failed") or state.get("node_skipped")
            if "node_completed" in state:
                status = "completed"
            elif "node_failed" in state:
                status = "failed"
            elif "node_skipped" in state:
                status = "skipped"
            else:
                status = "running"
            duration = ""
            if started and terminal:
                try:
                    start = datetime.fromisoformat(started.payload.get("started_at", ""))
                    end = datetime.fromisoformat(terminal.payload.get("finished_at", ""))
                    duration = f"{(end - start).total_seconds():.1f}s"
                except (ValueError, TypeError):
                    duration = ""
            summary = ""
            if terminal is not None:
                if "node_completed" in state:
                    summary = json.dumps(terminal.payload.get("result"), ensure_ascii=False, default=str)[:_MD_PAYLOAD_CAP]
                elif "node_skipped" in state:
                    summary = "跳过: " + json.dumps(terminal.payload.get("reasons"), ensure_ascii=False, default=str)[:_MD_PAYLOAD_CAP]
                else:
                    summary = json.dumps(terminal.payload.get("error"), ensure_ascii=False, default=str)[:_MD_PAYLOAD_CAP]
            lines.append(f"| `{node_id}` | {status} | {duration} | {summary.replace('|', '\\|')} |")
        lines.append("")

    progress_counts: dict[str, int] = {}
    for event in events:
        if event.event_type == "action_progress":
            node_id = event.payload.get("node_id")
            if isinstance(node_id, str):
                progress_counts[node_id] = progress_counts.get(node_id, 0) + 1

    if progress_counts:
        lines.append("## 节点交互")
        lines.append("")
        for node_id, count in sorted(progress_counts.items()):
            lines.append(f"- `{node_id}`: {count} 条工具调用/进度消息")
        lines.append("")

    lines.append("## 事件时间线")
    lines.append("")
    lines.append("| seq | 类型 | 节点 | payload |")
    lines.append("|-----|------|------|---------|")
    for event in events:
        node_id = event.payload.get("node_id") if isinstance(event.payload, dict) else None
        payload = _render_payload(event.payload)[:_MD_PAYLOAD_CAP].replace("\n", " ").replace("|", "\\|")
        lines.append(f"| {event.seq} | `{event.event_type}` | {node_id if isinstance(node_id, str) else ''} | {payload} |")
    lines.append("")
    return "\n".join(lines)
