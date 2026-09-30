"""Byte-level encoding sniffing shared by read_file and grep.

The fault-zeroing toolchain promises (``resources/skills/fault-zeroing/SKILL.md``
and the code-evidence context middleware) that GBK-encoded Chinese source and
logs are readable: files are decoded strictly in the order UTF-8 (with the
UTF-8 BOM stripped) -> GB18030 (a superset of GBK), and GB hits surface a
``[encoding: GB18030]`` marker to the agent. Files that no encoding decodes
strictly keep the caller's existing explicit error behavior — silent
``errors="replace"`` mojibake is never produced.
"""

from __future__ import annotations

import codecs

#: Label reported by :func:`sniff_decode` when the GB18030 fallback decided the
#: decoding, and rendered by :func:`with_encoding_prefix` / grep output.
GB18030_ENCODING_LABEL = "GB18030"


def sniff_decode(raw: bytes) -> tuple[str, str | None]:
    """Decode file bytes with the shared UTF-8 -> UTF-8 BOM -> GB18030 order.

    Returns ``(text, encoding_label)`` where the label is ``None`` for UTF-8
    input (BOM stripped when present) and :data:`GB18030_ENCODING_LABEL` when
    only the GB18030 fallback decodes the bytes.

    Raises:
        UnicodeDecodeError: When no encoding decodes the bytes strictly. A NUL
            byte in non-UTF-8 input raises too: GB18030 maps almost any binary
            stream to plausible text, but NUL never occurs in real GB text, so
            refusing it keeps binary deliverables on the explicit
            binary-file error path instead of silently producing mojibake.
    """
    if raw.startswith(codecs.BOM_UTF8):
        try:
            return raw.decode("utf-8-sig"), None
        except UnicodeDecodeError:
            # BOM-prefixed body that is not valid UTF-8: fall through to the
            # GB18030 attempt, per the declared sniff order.
            pass
    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError:
        pass
    if b"\x00" in raw:
        raise UnicodeDecodeError("gb18030", raw, 0, 1, "NUL byte found: file appears to be binary, not GB18030 text")
    return raw.decode("gb18030"), GB18030_ENCODING_LABEL


class DecodedText(str):
    """Decoded file text carrying the sniffed source-encoding label.

    ``sandbox.read_file`` returns this instead of a bare ``str`` when a
    fallback encoding decided the decoding, so tool layers can render the
    ``[encoding: <label>]`` marker while every str consumer (str_replace
    round-trips, hashing, masking) keeps working unchanged. The label is
    metadata only — it is never embedded in the text itself.
    """

    encoding_label: str | None

    def __new__(cls, text: str, encoding_label: str | None = None) -> DecodedText:
        obj = super().__new__(cls, text)
        obj.encoding_label = encoding_label
        return obj


def encoding_label_of(content: object) -> str | None:
    """Extract the sniffed encoding label from sandbox read output.

    Only :class:`DecodedText` (produced by sandboxes that sniff) carries a
    label; plain ``str`` results from other sandbox implementations report
    ``None`` and get no marker.
    """
    if isinstance(content, DecodedText):
        return content.encoding_label
    return None


def universal_newlines(text: str) -> str:
    """Translate CRLF and bare CR to LF, matching text-mode universal newlines."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def universal_newline_lines(text: str) -> list[str]:
    """Split decoded text into lines the way text-mode iteration would.

    Shares :func:`universal_newlines` and drops the phantom final element a
    trailing newline would produce, so callers share one line-numbering
    contract: grep match numbers and read_file line slices stay aligned with
    each other and with the previous text-mode ``open`` behavior.
    """
    lines = universal_newlines(text).split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # a trailing newline does not create a phantom final line
    return lines


def with_encoding_prefix(content: str, encoding_label: str | None) -> str:
    """Prepend the ``[encoding: <label>]`` marker line for non-UTF-8 hits."""
    if encoding_label:
        return f"[encoding: {encoding_label}]\n{content}"
    return content
