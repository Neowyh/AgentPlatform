"""Additional tests for the artifacts router (backend/app/gateway/routers/artifacts.py).

Covers gaps not addressed by existing test files:
- _build_content_disposition
- _build_attachment_headers
- is_text_file_by_content: binary file, exception
- get_artifact: not found, not a file, binary file, download=true, skill archive errors
- _extract_file_from_skill_archive: bad zip, member not found, nested member
- _read_skill_archive_member: size cap at runtime
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.gateway.routers.artifacts as artifacts_router
from app.gateway.routers.artifacts import (
    MAX_SKILL_ARCHIVE_MEMBER_BYTES,
    _build_attachment_headers,
    _build_content_disposition,
    _extract_file_from_skill_archive,
    _read_skill_archive_member,
    is_text_file_by_content,
)

# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestBuildContentDisposition:
    def test_attachment_disposition(self):
        result = _build_content_disposition("attachment", "test.txt")
        assert result.startswith("attachment;")
        assert "test.txt" in result

    def test_inline_disposition(self):
        result = _build_content_disposition("inline", "image.png")
        assert result.startswith("inline;")

    def test_special_characters_encoded(self):
        result = _build_content_disposition("attachment", "file with spaces.txt")
        assert "file%20with%20spaces.txt" in result

    def test_unicode_filename(self):
        result = _build_content_disposition("attachment", "中文.txt")
        assert "attachment;" in result


class TestBuildAttachmentHeaders:
    def test_basic_headers(self):
        headers = _build_attachment_headers("test.txt")
        assert "Content-Disposition" in headers
        assert "attachment;" in headers["Content-Disposition"]

    def test_extra_headers_merged(self):
        headers = _build_attachment_headers("test.txt", {"Cache-Control": "no-cache"})
        assert headers["Cache-Control"] == "no-cache"
        assert "Content-Disposition" in headers

    def test_no_extra_headers(self):
        headers = _build_attachment_headers("test.txt", None)
        assert "Content-Disposition" in headers


class TestIsTextFileByContent:
    def test_text_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        assert is_text_file_by_content(f) is True

    def test_binary_file_with_null_bytes(self, tmp_path):
        """Files with null bytes are detected as binary."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x01\x02")
        assert is_text_file_by_content(f) is False

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        assert is_text_file_by_content(f) is True

    def test_exception_returns_false(self):
        assert is_text_file_by_content(Path("/nonexistent/file")) is False


class TestExtractFileFromSkillArchive:
    def test_not_a_zip(self, tmp_path):
        f = tmp_path / "not-a.skill"
        f.write_bytes(b"not a zip file")
        result = _extract_file_from_skill_archive(f, "SKILL.md")
        assert result is None

    def test_file_not_found_in_archive(self, tmp_path):
        f = tmp_path / "test.skill"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("other.txt", "content")
        result = _extract_file_from_skill_archive(f, "SKILL.md")
        assert result is None

    def test_direct_path_match(self, tmp_path):
        f = tmp_path / "test.skill"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("SKILL.md", "# Test Skill")
        result = _extract_file_from_skill_archive(f, "SKILL.md")
        assert result == b"# Test Skill"

    def test_nested_path_match(self, tmp_path):
        f = tmp_path / "test.skill"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("my-skill/SKILL.md", "# Nested Skill")
        result = _extract_file_from_skill_archive(f, "SKILL.md")
        assert result == b"# Nested Skill"

    def test_bad_zip_returns_none(self, tmp_path):
        f = tmp_path / "corrupt.skill"
        f.write_bytes(b"PK\x03\x04corrupt data")
        result = _extract_file_from_skill_archive(f, "SKILL.md")
        assert result is None


class TestReadSkillArchiveMember:
    def test_oversized_member_raises_413(self, tmp_path):
        f = tmp_path / "big.skill"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("big.txt", "x" * (MAX_SKILL_ARCHIVE_MEMBER_BYTES + 1))

        with zipfile.ZipFile(f, "r") as zf:
            info = zf.infolist()[0]
            with pytest.raises(HTTPException) as exc:
                _read_skill_archive_member(zf, info)
            assert exc.value.status_code == 413


# ---------------------------------------------------------------------------
# Endpoint-level tests using TestClient
# ---------------------------------------------------------------------------


def _make_test_app(monkeypatch, artifact_path):
    """Build a test app that resolves to artifact_path."""
    app = make_authed_test_app()
    app.include_router(artifacts_router.router)
    monkeypatch.setattr(
        artifacts_router,
        "resolve_thread_virtual_path",
        lambda _tid, _path: artifact_path,
    )
    return app


class TestGetArtifactErrors:
    def test_not_found(self, tmp_path, monkeypatch):
        app = _make_test_app(monkeypatch, tmp_path / "nonexistent.txt")
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads/t1/artifacts/mnt/user-data/outputs/nonexistent.txt")
        assert resp.status_code == 404

    def test_not_a_file(self, tmp_path, monkeypatch):
        dir_path = tmp_path / "dir"
        dir_path.mkdir()
        app = _make_test_app(monkeypatch, dir_path)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads/t1/artifacts/mnt/user-data/outputs/dir")
        assert resp.status_code == 400

    def test_binary_file_with_null_bytes(self, tmp_path, monkeypatch):
        """Binary file with null bytes returns as binary response."""
        bin_path = tmp_path / "data.bin"
        bin_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x01\x02")
        app = _make_test_app(monkeypatch, bin_path)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads/t1/artifacts/mnt/user-data/outputs/data.bin")
        assert resp.status_code == 200

    def test_download_true_forces_attachment(self, tmp_path, monkeypatch):
        txt_path = tmp_path / "file.txt"
        txt_path.write_text("hello", encoding="utf-8")
        app = _make_test_app(monkeypatch, txt_path)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads/t1/artifacts/mnt/user-data/outputs/file.txt?download=true")
        assert resp.status_code == 200
        assert "attachment" in resp.headers.get("content-disposition", "")


class TestSkillArchiveEdgeCases:
    def test_not_found(self, tmp_path, monkeypatch):
        app = _make_test_app(monkeypatch, tmp_path / "nonexistent.skill")
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads/t1/artifacts/mnt/user-data/outputs/nonexistent.skill/SKILL.md")
        assert resp.status_code == 404

    def test_not_a_file(self, tmp_path, monkeypatch):
        skill_dir = tmp_path / "dir.skill"
        skill_dir.mkdir()
        app = _make_test_app(monkeypatch, skill_dir)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads/t1/artifacts/mnt/user-data/outputs/dir.skill/SKILL.md")
        assert resp.status_code == 400

    def test_member_not_found(self, tmp_path, monkeypatch):
        skill_path = tmp_path / "test.skill"
        with zipfile.ZipFile(skill_path, "w") as zf:
            zf.writestr("other.txt", "content")
        app = _make_test_app(monkeypatch, skill_path)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads/t1/artifacts/mnt/user-data/outputs/test.skill/MISSING.md")
        assert resp.status_code == 404

    def test_text_content(self, tmp_path, monkeypatch):
        skill_path = tmp_path / "test.skill"
        with zipfile.ZipFile(skill_path, "w") as zf:
            zf.writestr("notes.txt", "hello from archive")
        app = _make_test_app(monkeypatch, skill_path)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads/t1/artifacts/mnt/user-data/outputs/test.skill/notes.txt")
        assert resp.status_code == 200

    def test_download_forces_attachment(self, tmp_path, monkeypatch):
        skill_path = tmp_path / "test.skill"
        with zipfile.ZipFile(skill_path, "w") as zf:
            zf.writestr("data.csv", "a,b,c")
        app = _make_test_app(monkeypatch, skill_path)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads/t1/artifacts/mnt/user-data/outputs/test.skill/data.csv?download=true")
        assert resp.status_code == 200
        assert "attachment" in resp.headers.get("content-disposition", "")
