"""Read-only hex viewer for binary evidence in Code Evidence Packages (ticket 03).

``read_binary_hex`` is the model's only entry to the whitelisted binary
evidence (firmware images, compiler artifacts) that the code-evidence
pipeline now accepts.  It accepts nothing but a file path inside this
thread's package source tree, renders a fixed three-column view — offset,
hex bytes, printable ASCII (xxd-style) — and pages through
``offset``/``length``.  The whitelist and the per-file size limit come from
``app.agentplatform.code_evidence`` (single source of truth shared with the
pipeline); the per-call output cap keeps a single response bounded and
truncates with an explicit notice instead of exploding the context.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import PurePosixPath

from langchain.tools import tool

from app.agentplatform import code_evidence
from app.agentplatform.tools.code_evidence_access import (
    CODE_EVIDENCE_VIRTUAL_ROOT,
    PackageAccessRejected,
    get_thread_id,
    resolve_package_dir,
)
from deerflow.tools.types import Runtime

BINARY_EVIDENCE_FILE_PATTERN = f"{CODE_EVIDENCE_VIRTUAL_ROOT}/<package_id>/source/<file>"
_FILE_PATH_PATTERN = re.compile(rf"^{re.escape(CODE_EVIDENCE_VIRTUAL_ROOT)}/([^/]+)/source/(.+)$")
DEFAULT_VIEW_BYTES = 4096
MAX_VIEW_BYTES = 16_384
_VIEW_WIDTH = 16


def _format_hex_view(data: bytes, base_offset: int) -> str:
    lines: list[str] = []
    for start in range(0, len(data), _VIEW_WIDTH):
        chunk = data[start : start + _VIEW_WIDTH]
        left = " ".join(f"{byte:02x}" for byte in chunk[:8])
        right = " ".join(f"{byte:02x}" for byte in chunk[8:])
        printable = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in chunk)
        lines.append(f"{base_offset + start:08x}  {left:<23}  {right:<23} |{printable}|")
    return "\n".join(lines)


def _parse_file_path(declared: str) -> tuple[str, PurePosixPath] | None:
    match = _FILE_PATH_PATTERN.match(declared)
    if not match:
        return None
    relative = PurePosixPath(match.group(2))
    if ".." in relative.parts:
        return None
    return match.group(1), relative


def _rejection(reason_code: str, message: str) -> str:
    return json.dumps(
        {"error": message, "reason_code": reason_code, "allowed_pattern": BINARY_EVIDENCE_FILE_PATTERN},
        ensure_ascii=False,
    )


def _next_action(truncated: bool, has_more: bool, next_offset: int) -> str:
    if truncated:
        return f"单次输出上限 {MAX_VIEW_BYTES} 字节已截断，请用 offset={next_offset} 继续翻页读取。"
    if has_more:
        return f"文件还有未读内容，可用 offset={next_offset} 继续翻页。"
    return "十六进制视图仅供只读检查固件/编译产物类证据；文本类证据请改用 read_file/grep 阅读。"


def _read_binary_hex_sync(runtime: Runtime, declared_path: str, offset: int, length: int) -> str:
    thread_id = get_thread_id(runtime)
    if not thread_id:
        return json.dumps(
            {"error": "当前会话缺少 thread 上下文，无法读取代码证据包内的二进制证据", "reason_code": "thread_context_missing"},
            ensure_ascii=False,
        )
    normalized_path = (declared_path or "").strip()
    parsed = _parse_file_path(normalized_path)
    if parsed is None:
        return _rejection("file_path_rejected", f"read_binary_hex 只接受代码包 source/ 内的文件路径，收到: {normalized_path or '<空>'}")
    package_id, relative = parsed
    try:
        package_dir, package_id = resolve_package_dir(runtime, f"{CODE_EVIDENCE_VIRTUAL_ROOT}/{package_id}", thread_id)
    except PackageAccessRejected as exc:
        return _rejection(exc.reason_code, str(exc))

    source_root = (package_dir / "source").resolve()
    target = source_root.joinpath(*relative.parts).resolve()
    if not target.is_relative_to(source_root):
        return _rejection("file_path_rejected", f"文件路径越出代码包 source/ 边界: {relative.as_posix()}")
    if not target.is_file():
        return _rejection("file_not_found", f"代码包内不存在该文件: {relative.as_posix()}")
    if target.suffix.lower() not in code_evidence.BINARY_EVIDENCE_SUFFIXES:
        suffix = target.suffix.lower() or "<无后缀>"
        return _rejection(
            "not_binary_evidence",
            f"{relative.as_posix()} 的后缀 {suffix} 不在二进制证据白名单内；文本证据请改用 read_file/grep 阅读",
        )
    limit = code_evidence.BINARY_EVIDENCE_MAX_BYTES
    file_size = target.stat().st_size
    if file_size > limit:
        return _rejection("file_too_large", f"二进制证据(binary evidence)超过单文件上限 {limit} 字节: {relative.as_posix()}")
    if offset < 0 or length < 0:
        return _rejection("invalid_paging", f"offset/length 必须为非负整数，收到 offset={offset}, length={length}")

    with target.open("rb") as handle:
        handle.seek(offset)
        view = handle.read(min(length, MAX_VIEW_BYTES))

    truncated = length > MAX_VIEW_BYTES
    has_more = offset + len(view) < file_size
    payload = {
        "path": normalized_path,
        "package_id": package_id,
        "file_size": file_size,
        "offset": offset,
        "length": len(view),
        "max_view_bytes": MAX_VIEW_BYTES,
        "truncated": truncated,
        "has_more": has_more,
        "hex_view": _format_hex_view(view, offset),
        "next_action": _next_action(truncated, has_more, offset + len(view)),
    }
    return json.dumps(payload, ensure_ascii=False)


@tool("read_binary_hex", parse_docstring=True)
async def read_binary_hex_tool(runtime: Runtime, file_path: str, offset: int = 0, length: int = DEFAULT_VIEW_BYTES) -> str:
    """以十六进制 + ASCII 视图只读查看代码证据包内的二进制证据文件。

    归零代码证据的固件/编译产物检查入口（固定能力）：仅接受本会话代码证据包
    source/ 内的文件路径（/mnt/user-data/code-evidence/<package_id>/source/<file>），
    输出类 xxd 的三列视图（偏移量 + 十六进制 + 可打印 ASCII）。默认读取前 4096
    字节，用 offset/length 翻页；超过单次输出上限会被截断并提示。仅接受二进制
    证据白名单后缀（.bin/.elf/.o/.obj/.a/.so/.dll/.dylib/.exe/.lib/.axf/.map/.hex），
    超过单文件上限或非二进制文件会被结构化拒绝。

    Args:
        file_path: 代码包内的二进制证据文件路径，必须是 /mnt/user-data/code-evidence/<package_id>/source/<file>。
        offset: 起始字节偏移量，默认 0（从头开始）。
        length: 本次读取的字节数，默认 4096，超过单次输出上限会被截断并提示。
    """
    return await asyncio.to_thread(_read_binary_hex_sync, runtime, file_path, offset, length)
