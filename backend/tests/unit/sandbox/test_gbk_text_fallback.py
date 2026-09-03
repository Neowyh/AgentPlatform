"""Regression tests: GBK-encoded C source files uploaded directly must be readable.

Direct uploads land under ``/mnt/user-data/uploads/`` (not the code-evidence
tree), so they must go through the same UTF-8 -> GB18030 fallback decoding
instead of failing with a UnicodeDecodeError (read_file) or mojibake misses
(grep).
"""

from types import SimpleNamespace

from ideer.sandbox.local.local_sandbox import LocalSandbox
from ideer.sandbox.search import find_grep_matches
from ideer.sandbox.tools import grep_tool, read_file_tool

GBK_C_SOURCE = "#include <stdio.h>\n// \u6545\u969c\u5f52\u96f6\u5206\u6790\nint main() { return 0; }\n"


def _make_runtime(tmp_path):
    workspace = tmp_path / "workspace"
    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    workspace.mkdir()
    uploads.mkdir()
    outputs.mkdir()
    return SimpleNamespace(
        state={
            "sandbox": {"sandbox_id": "local"},
            "thread_data": {
                "workspace_path": str(workspace),
                "uploads_path": str(uploads),
                "outputs_path": str(outputs),
            },
        },
        context={"thread_id": "thread-1"},
    )


def _write_gbk_c(uploads_dir):
    target = uploads_dir / "fault.c"
    target.write_bytes(GBK_C_SOURCE.encode("gbk"))
    return target


def test_local_sandbox_reads_gbk_file(tmp_path) -> None:
    target = tmp_path / "fault.c"
    target.write_bytes(GBK_C_SOURCE.encode("gbk"))

    assert LocalSandbox("t").read_file(str(target)) == GBK_C_SOURCE


def test_find_grep_matches_chinese_keyword_in_gbk_file(tmp_path) -> None:
    target = tmp_path / "fault.c"
    target.write_bytes(GBK_C_SOURCE.encode("gbk"))

    matches, _ = find_grep_matches(tmp_path, "\u6545\u969c", glob_pattern="**/*.c")

    assert [m.path for m in matches] == [str(target)]
    assert "\u6545\u969c\u5f52\u96f6\u5206\u6790" in matches[0].line


def test_read_file_tool_reads_gbk_c_upload(tmp_path, monkeypatch) -> None:
    runtime = _make_runtime(tmp_path)
    _write_gbk_c(tmp_path / "uploads")
    monkeypatch.setattr("ideer.sandbox.tools.ensure_sandbox_initialized", lambda runtime: LocalSandbox(id="local"))

    result = read_file_tool.func(
        runtime=runtime,
        description="read gbk c file",
        path="/mnt/user-data/uploads/fault.c",
    )

    assert result.startswith("Error:") is False
    assert "\u6545\u969c\u5f52\u96f6\u5206\u6790" in result


def test_grep_tool_finds_keyword_in_gbk_c_upload(tmp_path, monkeypatch) -> None:
    runtime = _make_runtime(tmp_path)
    _write_gbk_c(tmp_path / "uploads")
    monkeypatch.setattr("ideer.sandbox.tools.ensure_sandbox_initialized", lambda runtime: LocalSandbox(id="local"))

    result = grep_tool.func(
        runtime=runtime,
        description="search gbk c file",
        pattern="\u6545\u969c",
        path="/mnt/user-data/uploads",
        glob="**/*.c",
    )

    assert "fault.c:2:" in result
    assert "\u6545\u969c\u5f52\u96f6\u5206\u6790" in result
