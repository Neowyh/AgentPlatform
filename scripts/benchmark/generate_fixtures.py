#!/usr/bin/env python3
"""Generate parseable, content-free fixtures for the multi-attachment TTFT run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

MINIMUM_BYTES = 24 * 1024
FIXTURE_COUNT = 12
FORMATS = ("md", "docx", "pdf")
_GENERATED_NAMES = {
    "benchmark-data.xlsx",
    "benchmark-notes.md",
    "benchmark-notes.txt",
    "benchmark-report.docx",
    "benchmark-report.pdf",
    "fixture-manifest.json",
}
_TTFT_NAME = re.compile(r"ttft-\d{2}\.(?:md|docx|pdf)$")


def _padding(size: int) -> bytes:
    return b" " * size


def _zip_entry(name: str, *, stored: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    return info


def _write_docx(path: Path) -> None:
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="bin" ContentType="application/octet-stream"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>TTFT fixture</w:t></w:r></w:p>"
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>'
        "</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        for name, value in (
            ("[Content_Types].xml", content_types),
            ("_rels/.rels", rels),
            ("word/document.xml", document),
        ):
            encoded = value.encode()
            archive.writestr(_zip_entry(name), encoded)
        padding = _padding(MINIMUM_BYTES)
        archive.writestr(
            _zip_entry("word/ttft-padding.bin", stored=True), padding
        )


def _pdf_bytes() -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>",
        b"<< /Length 4 >>\nstream\nq\nQ\nendstream",
        b"<< /Length "
        + str(MINIMUM_BYTES).encode()
        + b" >>\nstream\n"
        + _padding(MINIMUM_BYTES)
        + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    output.extend(
        b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    )
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(output)


def _write_fixture(path: Path, suffix: str, index: int) -> None:
    if suffix == "md":
        prefix = f"# TTFT fixture {index}\n\n".encode()
        path.write_bytes(prefix + _padding(MINIMUM_BYTES - len(prefix) + 1))
    elif suffix == "docx":
        _write_docx(path)
    else:
        path.write_bytes(_pdf_bytes())

    if path.stat().st_size <= MINIMUM_BYTES:
        raise RuntimeError(f"generated fixture is not larger than 20 KiB: {path}")


def _remove_previous_outputs(output: Path) -> None:
    for path in output.iterdir():
        if path.name in _GENERATED_NAMES or _TTFT_NAME.fullmatch(path.name):
            path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    _remove_previous_outputs(args.output)

    files = []
    for index in range(1, FIXTURE_COUNT + 1):
        suffix = FORMATS[(index - 1) % len(FORMATS)]
        path = args.output / f"ttft-{index:02d}.{suffix}"
        _write_fixture(path, suffix, index)
        files.append(
            {
                "filename": path.name,
                "format": suffix,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )

    manifest = {
        "minimum_bytes": MINIMUM_BYTES,
        "formats": list(FORMATS),
        "files": files,
    }
    (args.output / "fixture-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"generated {len(files)} fixtures in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
