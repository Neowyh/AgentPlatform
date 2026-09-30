"""Encoding-sniffing regression for read_file and grep (fault-zeroing T2).

Sniff order (spec docs/plans/2026-09-30-fault-zeroing-toolchain-spec.md):
UTF-8 strict (UTF-8 BOM stripped) -> GB18030 strict -> the caller's existing
error behavior. GB hits surface a ``[encoding: GB18030]`` prefix: on the first
line of read_file tool output and before each matched GB file's line group in
grep output. Illegal-byte files keep the explicit binary-file error — no
silent ``errors="replace"`` mojibake.
"""

from __future__ import annotations

import codecs
from pathlib import Path

import pytest

from deerflow.sandbox.local.local_sandbox import LocalSandbox, PathMapping
from deerflow.sandbox.search import GrepMatch, find_grep_matches

_GBK_TEXT = "中文注释：设备自检失败，报警代码 E-402"
_GB18030_EXT_TEXT = "生僻字𠀀与擓混合文本"
_UTF8_TEXT = "UTF-8 中文注释：泵振动超标"
_BOM_TEXT = "带 BOM 的 UTF-8 日志：启动超时"


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _sandbox(tmp_path: Path) -> LocalSandbox:
    return LocalSandbox("t", [PathMapping(container_path="/mnt/user-data", local_path=str(tmp_path))])


# ---------------------------------------------------------------------------
# Shared sniff helper
# ---------------------------------------------------------------------------


def test_sniff_decode_pure_ascii_is_utf8_without_label():
    from deerflow.sandbox.encoding import sniff_decode

    text, label = sniff_decode(b"plain ascii log line\nsecond line")

    assert text == "plain ascii log line\nsecond line"
    assert label is None


def test_sniff_decode_gbk_hits_gb18030_fallback():
    from deerflow.sandbox.encoding import sniff_decode

    text, label = sniff_decode(_GBK_TEXT.encode("gbk"))

    assert text == _GBK_TEXT
    assert label == "GB18030"


def test_sniff_decode_gb18030_four_byte_extension_hits_fallback():
    from deerflow.sandbox.encoding import sniff_decode

    raw = _GB18030_EXT_TEXT.encode("gb18030")
    assert b"\x00" not in raw  # fixture sanity: exercises the decoder, not the NUL guard

    text, label = sniff_decode(raw)

    assert text == _GB18030_EXT_TEXT
    assert label == "GB18030"


def test_sniff_decode_utf8_bom_is_stripped_without_label():
    from deerflow.sandbox.encoding import sniff_decode

    text, label = sniff_decode(codecs.BOM_UTF8 + _BOM_TEXT.encode("utf-8"))

    assert text == _BOM_TEXT
    assert label is None


def test_sniff_decode_illegal_bytes_raise_unicode_error():
    from deerflow.sandbox.encoding import sniff_decode

    # 0xFF is invalid in UTF-8 and not a valid GB18030 lead/trail byte.
    with pytest.raises(UnicodeDecodeError):
        sniff_decode(b"\xff\xfe\x03")


def test_sniff_decode_binary_with_nul_keeps_explicit_error():
    """GB18030 can decode nearly any byte stream into plausible mojibake; NUL
    bytes never occur in real GB text, so the fallback must refuse them and
    keep the explicit binary-file error (no silent replacement)."""
    from deerflow.sandbox.encoding import sniff_decode

    png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

    with pytest.raises(UnicodeDecodeError):
        sniff_decode(png_header)


def test_sniff_decode_utf8_text_with_embedded_nul_keeps_utf8_fast_path():
    """UTF-8 decodes NUL legally, so an already-UTF-8 file is untouched by the
    binary guard — the guard only gates the GB18030 fallback."""
    from deerflow.sandbox.encoding import sniff_decode

    text, label = sniff_decode(b"hello\x00world")

    assert text == "hello\x00world"
    assert label is None


def test_with_encoding_prefix_adds_marker_line_only_for_gb_hits():
    from deerflow.sandbox.encoding import GB18030_ENCODING_LABEL, with_encoding_prefix

    assert with_encoding_prefix("line1\nline2", GB18030_ENCODING_LABEL) == "[encoding: GB18030]\nline1\nline2"
    assert with_encoding_prefix("line1", None) == "line1"


def test_encoding_label_of_plain_str_is_none():
    """Non-sniffing sandboxes return plain str; only DecodedText carries a label."""
    from deerflow.sandbox.encoding import GB18030_ENCODING_LABEL, DecodedText, encoding_label_of

    assert encoding_label_of(DecodedText("中文", GB18030_ENCODING_LABEL)) == GB18030_ENCODING_LABEL
    assert encoding_label_of(DecodedText("plain")) is None
    assert encoding_label_of("plain str from another sandbox") is None


# ---------------------------------------------------------------------------
# LocalSandbox.read_file / read_file_with_encoding
# ---------------------------------------------------------------------------


def test_read_file_carries_gb18030_encoding_label(tmp_path):
    path = _write(tmp_path, "gbk.txt", _GBK_TEXT.encode("gbk"))

    result = _sandbox(tmp_path).read_file(str(path))

    assert result == _GBK_TEXT
    assert result.encoding_label == "GB18030"


def test_read_file_returns_decoded_content_without_embedded_marker(tmp_path):
    """The marker belongs to the tool display layer; sandbox.read_file must
    stay raw so str_replace/read-modify-write never persists the marker."""
    path = _write(tmp_path, "gbk.txt", _GBK_TEXT.encode("gbk"))

    content = _sandbox(tmp_path).read_file(str(path))

    assert content == _GBK_TEXT


def test_read_file_utf8_bom_file_is_stripped_without_label(tmp_path):
    path = _write(tmp_path, "bom.txt", codecs.BOM_UTF8 + _BOM_TEXT.encode("utf-8"))

    result = _sandbox(tmp_path).read_file(str(path))

    assert result == _BOM_TEXT
    assert result.encoding_label is None


def test_read_file_ascii_file_has_no_label(tmp_path):
    path = _write(tmp_path, "ascii.txt", b"hello world")

    result = _sandbox(tmp_path).read_file(str(path))

    assert result == "hello world"
    assert result.encoding_label is None


def test_read_file_preserves_trailing_newline_on_full_read(tmp_path):
    """Full reads keep the trailing newline exactly like the previous
    text-mode open, so str_replace/read-modify-write round-trips byte-stable
    for UTF-8 files."""
    path = _write(tmp_path, "trailing.txt", b"line-1\nline-2\n")

    result = _sandbox(tmp_path).read_file(str(path))

    assert result == "line-1\nline-2\n"
    assert result.encoding_label is None


def test_read_file_illegal_bytes_raise_unicode_decode_error(tmp_path):
    path = _write(tmp_path, "binary.bin", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    with pytest.raises(UnicodeDecodeError):
        _sandbox(tmp_path).read_file(str(path))


def test_read_file_gbk_line_slice(tmp_path):
    raw = "\n".join(["line-1", "中文行-2", "line-3", "中文行-4"]).encode("gbk")
    path = _write(tmp_path, "gbk_lines.txt", raw)

    result = _sandbox(tmp_path).read_file(str(path), start_line=2, end_line=3)

    assert result == "中文行-2\nline-3"
    assert result.encoding_label == "GB18030"


def test_read_file_normalizes_crlf_line_endings(tmp_path):
    path = _write(tmp_path, "crlf.txt", "中文行-1\r\nline-2\r\n中文行-3".encode("gbk"))

    result = _sandbox(tmp_path).read_file(str(path))

    assert result == "中文行-1\nline-2\n中文行-3"
    assert result.encoding_label == "GB18030"


def test_read_file_sliced_read_keeps_line_numbers_aligned(tmp_path):
    """grep line numbers must stay valid against read_file(start_line=...):
    the slice is taken before any marker is prepended by the tool layer."""
    raw = "\n".join(["a", "b", "中文行-3", "d"]).encode("gbk")
    path = _write(tmp_path, "aligned.txt", raw)

    result = _sandbox(tmp_path).read_file(str(path), start_line=3, end_line=3)

    assert result == "中文行-3"
    assert result.encoding_label == "GB18030"


# ---------------------------------------------------------------------------
# grep (find_grep_matches) per-file sniffing
# ---------------------------------------------------------------------------


def test_find_grep_matches_decodes_gbk_file_and_labels_matches(tmp_path):
    _write(tmp_path, "keep.txt", _GBK_TEXT.encode("gbk"))
    _write(tmp_path, "utf8.txt", _UTF8_TEXT.encode("utf-8"))

    matches, truncated = find_grep_matches(tmp_path, "报警代码")

    assert truncated is False
    assert [match.line for match in matches] == [_GBK_TEXT]
    assert matches[0].encoding == "GB18030"

    utf8_matches, _ = find_grep_matches(tmp_path, "泵振动")
    assert [match.line for match in utf8_matches] == [_UTF8_TEXT]
    assert utf8_matches[0].encoding is None


def test_find_grep_matches_gb18030_extension_text(tmp_path):
    _write(tmp_path, "ext.txt", _GB18030_EXT_TEXT.encode("gb18030"))

    matches, _ = find_grep_matches(tmp_path, "生僻字")

    assert [match.line for match in matches] == [_GB18030_EXT_TEXT]
    assert matches[0].encoding == "GB18030"


def test_find_grep_matches_skips_undecodable_file_without_crashing(tmp_path):
    _write(tmp_path, "binary.bin", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    _write(tmp_path, "illegal.raw", b"\xff\xfe\x03")
    _write(tmp_path, "utf8.txt", _UTF8_TEXT.encode("utf-8"))

    matches, truncated = find_grep_matches(tmp_path, "中文|启动")

    assert [match.path for match in matches] == [str(tmp_path / "utf8.txt")]
    assert truncated is False


def test_find_grep_matches_single_file_root_with_illegal_bytes_yields_no_matches(tmp_path):
    path = _write(tmp_path, "illegal.raw", b"\xff\xfe\x03")

    matches, truncated = find_grep_matches(path, "anything")

    assert matches == []
    assert truncated is False


def test_grep_match_encoding_defaults_to_none_for_other_providers():
    match = GrepMatch(path="/mnt/x", line_number=1, line="text")

    assert match.encoding is None


# ---------------------------------------------------------------------------
# grep output formatting: prefix before each GB file's line group
# ---------------------------------------------------------------------------


def test_format_grep_results_puts_marker_before_gb_file_group():
    from deerflow.sandbox.tools import _format_grep_results

    matches = [
        GrepMatch(path="/root/utf8.log", line_number=2, line="泵振动超标"),
        GrepMatch(path="/root/gbk.log", line_number=3, line="报警代码 E-402", encoding="GB18030"),
        GrepMatch(path="/root/gbk.log", line_number=9, line="设备自检失败", encoding="GB18030"),
    ]

    output = _format_grep_results("/root", matches, truncated=False)

    lines = output.splitlines()
    assert lines[0] == "Found 3 matches under /root"
    assert lines[1] == "/root/utf8.log:2: 泵振动超标"
    assert lines[2] == "[encoding: GB18030]"
    assert lines[3] == "/root/gbk.log:3: 报警代码 E-402"
    assert lines[4] == "/root/gbk.log:9: 设备自检失败"


def test_format_grep_results_repeats_marker_for_each_gb_file():
    from deerflow.sandbox.tools import _format_grep_results

    matches = [
        GrepMatch(path="/root/a.log", line_number=1, line="甲", encoding="GB18030"),
        GrepMatch(path="/root/b.log", line_number=2, line="乙", encoding="GB18030"),
    ]

    output = _format_grep_results("/root", matches, truncated=False)

    lines = output.splitlines()
    assert lines[1] == "[encoding: GB18030]"
    assert lines[2] == "/root/a.log:1: 甲"
    assert lines[3] == "[encoding: GB18030]"
    assert lines[4] == "/root/b.log:2: 乙"


def test_format_grep_results_without_gb_matches_has_no_marker():
    from deerflow.sandbox.tools import _format_grep_results

    matches = [GrepMatch(path="/root/utf8.log", line_number=1, line="plain")]

    output = _format_grep_results("/root", matches, truncated=False)

    assert "[encoding:" not in output


# ---------------------------------------------------------------------------
# Tool layer: read_file_tool / grep_tool / str_replace round-trip safety
# ---------------------------------------------------------------------------


def _tool_sandbox(tmp_path: Path) -> LocalSandbox:
    user_data = tmp_path / "user-data"
    (user_data / "workspace").mkdir(parents=True, exist_ok=True)
    (user_data / "uploads").mkdir(parents=True, exist_ok=True)
    (user_data / "outputs").mkdir(parents=True, exist_ok=True)
    return LocalSandbox("local:user:thread", [PathMapping(container_path="/mnt/user-data", local_path=str(user_data))])


def _tool_runtime(tmp_path: Path):
    from unittest.mock import MagicMock

    runtime = MagicMock()
    runtime.state = {
        "sandbox": {"sandbox_id": "local:user:thread"},
        "thread_data": {
            "workspace_path": str(tmp_path / "user-data" / "workspace"),
            "uploads_path": str(tmp_path / "user-data" / "uploads"),
            "outputs_path": str(tmp_path / "user-data" / "outputs"),
        },
    }
    runtime.context = {"thread_id": "thread"}
    runtime.config = {"configurable": {"thread_id": "thread"}}
    return runtime


@pytest.fixture()
def patched_sandbox(tmp_path, monkeypatch):
    import deerflow.sandbox.tools as tools

    sandbox = _tool_sandbox(tmp_path)
    monkeypatch.setattr(tools, "ensure_sandbox_initialized", lambda runtime: sandbox)
    monkeypatch.setattr(tools, "ensure_thread_directories_exist", lambda runtime: None)
    return tmp_path, sandbox


def test_read_file_tool_prepends_gb18030_marker_for_gbk_file(patched_sandbox):
    from deerflow.sandbox.tools import read_file_tool

    tmp_path, _sandbox = patched_sandbox
    (tmp_path / "user-data" / "workspace" / "log.txt").write_bytes(_GBK_TEXT.encode("gbk"))

    output = read_file_tool.func(_tool_runtime(tmp_path), "/mnt/user-data/workspace/log.txt")

    assert output == f"[encoding: GB18030]\n{_GBK_TEXT}"


def test_read_file_tool_slice_read_prepends_marker_after_content(patched_sandbox):
    from deerflow.sandbox.tools import read_file_tool

    tmp_path, _sandbox = patched_sandbox
    (tmp_path / "user-data" / "workspace" / "lines.txt").write_bytes("中文行-1\nline-2\n中文行-3".encode("gbk"))

    output = read_file_tool.func(_tool_runtime(tmp_path), "/mnt/user-data/workspace/lines.txt", start_line=2, end_line=3)

    assert output == "[encoding: GB18030]\nline-2\n中文行-3"


def test_read_file_tool_ascii_file_has_no_marker(patched_sandbox):
    from deerflow.sandbox.tools import read_file_tool

    tmp_path, _sandbox = patched_sandbox
    (tmp_path / "user-data" / "workspace" / "ascii.txt").write_bytes(b"hello world")

    output = read_file_tool.func(_tool_runtime(tmp_path), "/mnt/user-data/workspace/ascii.txt")

    assert output == "hello world"


def test_read_file_tool_illegal_bytes_report_binary_file_error(patched_sandbox):
    from deerflow.sandbox.tools import read_file_tool

    tmp_path, _sandbox = patched_sandbox
    (tmp_path / "user-data" / "workspace" / "blob.bin").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    output = read_file_tool.func(_tool_runtime(tmp_path), "/mnt/user-data/workspace/blob.bin")

    assert output.startswith("Error: cannot read '/mnt/user-data/workspace/blob.bin' as text")
    assert "binary file" in output
    assert "UTF-8 and GB18030" in output


def test_str_replace_on_gb_file_never_persists_the_marker_line(patched_sandbox):
    """str_replace reads via sandbox.read_file (raw decoded text) and writes
    the result back; the tool-layer marker must never round-trip into the
    file, and a marker copied into old_str fails safely instead of matching."""
    from deerflow.sandbox.tools import read_file_tool, str_replace_tool

    tmp_path, _sandbox = patched_sandbox
    target = tmp_path / "user-data" / "workspace" / "src.txt"
    target.write_bytes(_GBK_TEXT.encode("gbk"))
    runtime = _tool_runtime(tmp_path)

    read_output = read_file_tool.func(runtime, "/mnt/user-data/workspace/src.txt")
    assert read_output.startswith("[encoding: GB18030]")

    result = str_replace_tool.func(runtime, "/mnt/user-data/workspace/src.txt", "设备自检失败", "设备自检通过")

    assert result == "OK"
    # The file is rewritten as UTF-8 with the replacement applied and without
    # the display-only marker line.
    assert target.read_text(encoding="utf-8") == _GBK_TEXT.replace("设备自检失败", "设备自检通过")


def test_grep_tool_output_carries_gb18030_group_marker(patched_sandbox):
    from deerflow.sandbox.tools import grep_tool

    tmp_path, _sandbox = patched_sandbox
    (tmp_path / "user-data" / "workspace" / "gbk.txt").write_bytes(_GBK_TEXT.encode("gbk"))
    (tmp_path / "user-data" / "workspace" / "utf8.txt").write_bytes(_UTF8_TEXT.encode("utf-8"))

    output = grep_tool.func(_tool_runtime(tmp_path), "报警代码|泵振动", "/mnt/user-data/workspace")

    lines = output.splitlines()
    assert lines[0] == "Found 2 matches under /mnt/user-data/workspace"
    gbk_index = lines.index("[encoding: GB18030]")
    assert "gbk.txt:1:" in lines[gbk_index + 1]
    assert "报警代码 E-402" in lines[gbk_index + 1]
    assert any("utf8.txt" in line and "泵振动超标" in line for line in lines)
