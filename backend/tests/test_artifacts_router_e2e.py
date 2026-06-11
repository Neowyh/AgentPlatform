"""E2E tests for the artifacts router (backend/app/gateway/routers/artifacts.py).

Covers:
- GET /api/threads/{thread_id}/artifacts/{path:path}
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.routers.artifacts import router as artifacts_router

pytestmark = pytest.mark.no_auto_user

THREAD_ID = "thread-1"

MOCK_TARGET = "app.gateway.routers.artifacts.resolve_thread_virtual_path"


def _make_app():
    app = make_authed_test_app()
    app.include_router(artifacts_router)
    return app


def _write_temp_file(content: bytes | str, suffix: str = ".txt") -> Path:
    """Write content to a temp file and return its path."""
    raw = content.encode("utf-8") if isinstance(content, str) else content
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(raw)
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Tests — GET /api/threads/{thread_id}/artifacts/{path:path}
# ---------------------------------------------------------------------------


class TestGetArtifact:
    """Tests for GET /api/threads/{thread_id}/artifacts/{path:path}."""

    @patch(MOCK_TARGET)
    def test_get_artifact_text(self, mock_resolve):
        """Get text artifact returns inline plain-text content."""
        tmp = _write_temp_file("Hello World", suffix=".txt")
        mock_resolve.return_value = tmp
        try:
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get(f"/api/threads/{THREAD_ID}/artifacts/test.txt")
            assert resp.status_code == 200
            assert "Hello World" in resp.text
            assert "text/plain" in resp.headers.get("content-type", "")
        finally:
            tmp.unlink(missing_ok=True)

    @patch(MOCK_TARGET)
    def test_get_artifact_binary(self, mock_resolve):
        """Get binary artifact returns content with application/octet-stream."""
        tmp = _write_temp_file(b"\x89PNG\r\n\x1a\n\x00\x00", suffix=".bin")
        mock_resolve.return_value = tmp
        try:
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get(f"/api/threads/{THREAD_ID}/artifacts/test.bin")
            assert resp.status_code == 200
        finally:
            tmp.unlink(missing_ok=True)

    @patch(MOCK_TARGET)
    def test_get_artifact_not_found(self, mock_resolve):
        """Get artifact returns 404 when the file does not exist."""
        fake_path = Path("/nonexistent/file.txt")
        mock_resolve.return_value = fake_path
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get(f"/api/threads/{THREAD_ID}/artifacts/nonexistent.txt")
        assert resp.status_code == 404

    @patch(MOCK_TARGET)
    def test_get_skill_artifact(self, mock_resolve):
        """Get .skill artifact that is not a .skill/... path returns the raw file."""
        # A plain .skill path (no internal "/") goes through the normal
        # file-reading branch, not the ZIP extraction branch.
        tmp = _write_temp_file(b"PKzip-content", suffix=".skill")
        mock_resolve.return_value = tmp
        try:
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get(f"/api/threads/{THREAD_ID}/artifacts/test.skill")
            assert resp.status_code == 200
        finally:
            tmp.unlink(missing_ok=True)
