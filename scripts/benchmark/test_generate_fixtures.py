from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pypdfium2


SCRIPT = Path(__file__).with_name("generate_fixtures.py")
MIN_BYTES = 20 * 1024


def _generate(output: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_generates_parseable_large_md_docx_pdf_fixtures(tmp_path: Path) -> None:
    _generate(tmp_path)
    files = (
        sorted(tmp_path.glob("*.md"))
        + sorted(tmp_path.glob("*.docx"))
        + sorted(tmp_path.glob("*.pdf"))
    )

    assert len(files) == 12
    assert {path.suffix for path in files} == {".md", ".docx", ".pdf"}
    assert all(path.stat().st_size > MIN_BYTES for path in files)

    docx_files = [path for path in files if path.suffix == ".docx"]
    with zipfile.ZipFile(docx_files[0]) as archive:
        assert "[Content_Types].xml" in archive.namelist()
        assert "word/document.xml" in archive.namelist()
        assert "word/ttft-padding.bin" in archive.namelist()

    pdf_files = [path for path in files if path.suffix == ".pdf"]
    document = pypdfium2.PdfDocument(str(pdf_files[0]))
    assert len(document) == 1
    document.close()


def test_manifest_matches_files_and_regeneration_preserves_unrelated_files(
    tmp_path: Path,
) -> None:
    sentinel = tmp_path / "keep.me"
    sentinel.write_text("preserve", encoding="utf-8")
    _generate(tmp_path)
    _generate(tmp_path)

    manifest = json.loads(
        (tmp_path / "fixture-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["minimum_bytes"] > MIN_BYTES
    assert len(manifest["files"]) == 12
    for entry in manifest["files"]:
        path = tmp_path / entry["filename"]
        assert path.is_file()
        assert path.stat().st_size == entry["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    assert sentinel.read_text(encoding="utf-8") == "preserve"
