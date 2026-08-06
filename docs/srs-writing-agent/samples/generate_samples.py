#!/usr/bin/env python3
"""Regenerate the sample task-book artifacts (.docx via officecli, .pdf via fpdf2)
from the markdown master copy.

Requires:
  - the vendored officecli binary at vendor/officecli/officecli
  - python3 with pymupdf installed (for the .pdf sample; optional, PDF is
    skipped with a warning when fitz is unavailable)

Usage:
  python3 docs/srs-writing-agent/samples/generate_samples.py
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
OFFICECLI = REPO_ROOT / "vendor" / "officecli" / "officecli"
HERE = Path(__file__).resolve().parent
MD_SAMPLE = HERE / "taskbook_detection_management.md"


def _run(cmd: list[str]) -> str:
    """Run a command with stdout/stderr redirected to a file.

    officecli spawns a resident background process that inherits the stdout
    pipe; capturing via pipes would hang waiting for EOF. A temp file keeps
    the call synchronous while the resident writes nowhere, then is unlinked.
    """
    with tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False, encoding="utf-8") as tf:
        tmp_name = tf.name
        try:
            subprocess.run(cmd, check=True, stdout=tf, stderr=tf)
            tf.seek(0)
            return tf.read()
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

FONTS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]


def _run_allow_fail(cmd: list[str]) -> None:
    """Run a command ignoring failures (used to close stale residents)."""
    try:
        _run(cmd)
    except subprocess.CalledProcessError:
        pass


def build_docx() -> None:
    out = HERE / "taskbook_detection_management.docx"
    _run_allow_fail([str(OFFICECLI), "close", str(out)])
    _run([str(OFFICECLI), "create", str(out), "--force"])
    commands = []
    with MD_SAMPLE.open(encoding="utf-8") as fh:
        for raw in fh.read().splitlines():
            line = raw.rstrip()
            text = line.strip()
            if not text:
                continue
            if text.startswith("#"):
                _, _, body = text.partition(" ")
                level = min(len(raw) - len(raw.lstrip("#")), 6)
                style = f"Heading{level}"
                props = {"text": body.strip(), "style": style}
                commands.append({"command": "add", "parent": "/body", "type": "paragraph", "props": props})
            elif text.startswith("- "):
                props = {"text": text[2:].strip(), "style": "List Bullet"}
                commands.append({"command": "add", "parent": "/body", "type": "paragraph", "props": props})
            else:
                props = {"text": text, "style": "Normal"}
                commands.append({"command": "add", "parent": "/body", "type": "paragraph", "props": props})
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(commands, tf, ensure_ascii=False)
        tmp_name = tf.name
    try:
        _run([str(OFFICECLI), "batch", str(out), "--input", tmp_name])
    finally:
        os.unlink(tmp_name)
    _run_allow_fail([str(OFFICECLI), "close", str(out)])
    print(f"docx -> {out}")


def build_pdf() -> None:
    try:
        import fitz
    except ImportError:
        print("pdf  skipped: pymupdf not installed (pip install pymupdf)")
        return

    lines = []
    with MD_SAMPLE.open(encoding="utf-8") as fh:
        for raw in fh.read().splitlines():
            line = raw.rstrip()
            if not line.strip():
                continue
            head = ""
            body = line.strip()
            if body.startswith("#"):
                head = body[: len(body) - len(body.lstrip("#"))]
                body = body.lstrip("# ").strip()
            lines.append((head, body))

    doc = fitz.open()
    page = doc.new_page()
    ypos = 56.0
    bottom = 780.0
    for head, body in lines:
        size = 15 if head == "#" else (13 if head == "##" else (12 if head == "###" else 11))
        rect = fitz.Rect(56, ypos, 540, ypos + 48)
        rc = page.insert_textbox(rect, body, fontname="china-s", fontsize=size)
        if rc < 0:
            page = doc.new_page()
            ypos = 56.0
            rect = fitz.Rect(56, ypos, 540, ypos + 48)
            page.insert_textbox(rect, body, fontname="china-s", fontsize=size)
        ypos = rect.y1 + 5
        if ypos > bottom:
            page = doc.new_page()
            ypos = 56.0
    out = HERE / "taskbook_detection_management.pdf"
    doc.save(str(out))
    doc.close()
    print(f"pdf  -> {out}")


def main() -> None:
    if not OFFICECLI.exists():
        raise SystemExit(f"officecli binary not found at {OFFICECLI}")
    build_docx()
    build_pdf()
    print("done")


if __name__ == "__main__":
    main()