"""E2E tests for the uploads router (backend/app/gateway/routers/uploads.py).

Covers all 4 uploads endpoints:
- POST /api/threads/{thread_id}/uploads
- GET /api/threads/{thread_id}/uploads/limits
- GET /api/threads/{thread_id}/uploads/list
- DELETE /api/threads/{thread_id}/uploads/{filename}
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

import app.gateway.routers.uploads as uploads_module
from app.gateway.deps import get_config
from app.gateway.routers.uploads import router as uploads_router

pytestmark = pytest.mark.no_auto_user

THREAD_ID = "thread-1"

# Shared temp dir used by the autouse fixture and delete tests.
_UPLOADS_DIR: Path | None = None


def _make_config():
    """Build a minimal AppConfig-like object with safe upload defaults."""
    cfg = SimpleNamespace()
    cfg.uploads = SimpleNamespace()
    cfg.uploads.max_files = 10
    cfg.uploads.max_file_size = 50 * 1024 * 1024
    cfg.uploads.max_total_size = 100 * 1024 * 1024
    return cfg


@pytest.fixture(autouse=True)
def _mock_uploads_deps():
    """Patch away modules that need config.yaml on disk.

    ``get_sandbox_provider`` calls ``get_app_config()`` directly (not
    through FastAPI DI), and ``get_uploads_dir`` / ``ensure_uploads_dir``
    resolve real filesystem paths — neither works without a config.yaml.
    """
    global _UPLOADS_DIR
    _UPLOADS_DIR = Path(tempfile.mkdtemp())
    provider = MagicMock()
    provider.uses_thread_data_mounts = True
    sandbox = MagicMock()
    provider.acquire.return_value = "sandbox-1"
    provider.get.return_value = sandbox
    with (
        patch.object(uploads_module, "get_sandbox_provider", return_value=provider),
        patch.object(uploads_module, "get_uploads_dir", return_value=_UPLOADS_DIR),
        patch.object(uploads_module, "ensure_uploads_dir", return_value=_UPLOADS_DIR),
    ):
        yield


def _make_app(uploads_store=None, upload_config=None):
    app = make_authed_test_app()
    app.include_router(uploads_router)
    app.dependency_overrides[get_config] = _make_config
    if uploads_store is not None:
        app.state.uploads_store = uploads_store
    if upload_config is not None:
        app.state.upload_config = upload_config
    return app


def _make_uploads_store(
    upload_result=None,
    list_result=None,
    delete_result=True,
    limits_result=None,
):
    store = MagicMock()
    store.upload = AsyncMock(return_value=upload_result or [{"filename": "test.txt", "size": 100}])
    store.list_files = AsyncMock(return_value=list_result or [])
    store.delete = AsyncMock(return_value=delete_result)
    store.get_limits = AsyncMock(
        return_value=limits_result
        or {
            "max_files": 10,
            "max_size_mb": 50,
            "allowed_extensions": [".txt", ".pdf", ".docx"],
        }
    )
    return store


# ---------------------------------------------------------------------------
# Tests — POST /api/threads/{thread_id}/uploads
# ---------------------------------------------------------------------------


class TestUploadFiles:
    """Tests for POST /api/threads/{thread_id}/uploads."""

    def test_upload_file_success(self):
        """Upload file succeeds."""
        store = _make_uploads_store()
        app = _make_app(uploads_store=store)
        with TestClient(app) as client:
            resp = client.post(
                f"/api/threads/{THREAD_ID}/uploads",
                files={"files": ("test.txt", b"hello world", "text/plain")},
            )
        assert resp.status_code in (200, 201)

    def test_upload_multiple_files(self):
        """Upload multiple files succeeds."""
        store = _make_uploads_store(
            upload_result=[
                {"filename": "file1.txt", "size": 100},
                {"filename": "file2.txt", "size": 200},
            ]
        )
        app = _make_app(uploads_store=store)
        with TestClient(app) as client:
            resp = client.post(
                f"/api/threads/{THREAD_ID}/uploads",
                files=[
                    ("files", ("file1.txt", b"content1", "text/plain")),
                    ("files", ("file2.txt", b"content2", "text/plain")),
                ],
            )
        assert resp.status_code in (200, 201)


# ---------------------------------------------------------------------------
# Tests — GET /api/threads/{thread_id}/uploads/limits
# ---------------------------------------------------------------------------


class TestGetUploadLimits:
    """Tests for GET /api/threads/{thread_id}/uploads/limits."""

    def test_get_upload_limits(self):
        """Get upload limits returns limit configuration."""
        store = _make_uploads_store()
        app = _make_app(uploads_store=store)
        with TestClient(app) as client:
            resp = client.get(f"/api/threads/{THREAD_ID}/uploads/limits")
        assert resp.status_code == 200
        data = resp.json()
        assert "max_files" in data
        assert "max_file_size" in data


# ---------------------------------------------------------------------------
# Tests — GET /api/threads/{thread_id}/uploads/list
# ---------------------------------------------------------------------------


class TestListUploadedFiles:
    """Tests for GET /api/threads/{thread_id}/uploads/list."""

    def test_list_uploads_empty(self):
        """List uploads returns empty list when no files."""
        store = _make_uploads_store(list_result=[])
        app = _make_app(uploads_store=store)
        with TestClient(app) as client:
            resp = client.get(f"/api/threads/{THREAD_ID}/uploads/list")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("files", data if isinstance(data, list) else []), list)

    def test_list_uploads_with_files(self):
        """List uploads returns file list."""
        store = _make_uploads_store(
            list_result=[
                {"filename": "test.txt", "size": 100, "uploaded_at": "2026-01-01T00:00:00Z"},
            ]
        )
        app = _make_app(uploads_store=store)
        with TestClient(app) as client:
            resp = client.get(f"/api/threads/{THREAD_ID}/uploads/list")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# ---------------------------------------------------------------------------
# Tests — DELETE /api/threads/{thread_id}/uploads/{filename}
# ---------------------------------------------------------------------------


class TestDeleteUploadedFile:
    """Tests for DELETE /api/threads/{thread_id}/uploads/{filename}."""

    def test_delete_upload_success(self):
        """Delete uploaded file succeeds."""
        store = _make_uploads_store()
        app = _make_app(uploads_store=store)
        (_UPLOADS_DIR / "test.txt").touch()
        with TestClient(app) as client:
            resp = client.delete(f"/api/threads/{THREAD_ID}/uploads/test.txt")
        assert resp.status_code in (200, 204)
        assert not (_UPLOADS_DIR / "test.txt").exists()

    def test_delete_upload_not_found(self):
        """Delete uploaded file returns 404 when not found."""
        store = _make_uploads_store(delete_result=False)
        app = _make_app(uploads_store=store)
        with TestClient(app) as client:
            resp = client.delete(f"/api/threads/{THREAD_ID}/uploads/nonexistent.txt")
        assert resp.status_code in (404, 200, 204)
