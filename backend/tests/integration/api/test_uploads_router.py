import asyncio
import os
import stat
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _router_auth_helpers import call_unwrapped, make_authed_test_app
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from app.gateway.deps import get_config
from app.gateway.routers import uploads


class ChunkedUpload:
    def __init__(self, filename: str, chunks: list[bytes]):
        self.filename = filename
        self._chunks = list(chunks)
        self.read_calls: list[int | None] = []

    async def read(self, size: int | None = None) -> bytes:
        self.read_calls.append(size)
        if size is None:
            raise AssertionError("upload must be read with an explicit chunk size")
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


def _mounted_provider() -> MagicMock:
    provider = MagicMock()
    provider.uses_thread_data_mounts = True
    return provider


# ---------------------------------------------------------------------------
# _make_file_sandbox_writable / _make_file_sandbox_readable
# ---------------------------------------------------------------------------


def test_make_file_sandbox_writable_adds_write_bits_for_regular_files(tmp_path):
    file_path = tmp_path / "report.pdf"
    file_path.write_bytes(b"pdf-bytes")
    os_chmod_mode = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
    file_path.chmod(os_chmod_mode)

    uploads._make_file_sandbox_writable(file_path)

    updated_mode = stat.S_IMODE(file_path.stat().st_mode)
    assert updated_mode & stat.S_IWUSR
    assert updated_mode & stat.S_IWGRP
    assert updated_mode & stat.S_IWOTH


def test_make_file_sandbox_writable_skips_symlinks(tmp_path):
    file_path = tmp_path / "target-link.txt"
    file_path.write_text("hello", encoding="utf-8")
    symlink_stat = MagicMock(st_mode=stat.S_IFLNK)

    with (
        patch.object(uploads.os, "lstat", return_value=symlink_stat),
        patch.object(uploads.os, "chmod") as chmod,
    ):
        uploads._make_file_sandbox_writable(file_path)

    chmod.assert_not_called()


def test_make_file_sandbox_readable_adds_read_bits_for_regular_files(tmp_path):
    file_path = tmp_path / "data.csv"
    file_path.write_bytes(b"csv-data")
    file_path.chmod(0o600)

    uploads._make_file_sandbox_readable(file_path)

    updated_mode = stat.S_IMODE(file_path.stat().st_mode)
    assert updated_mode & stat.S_IRUSR
    assert updated_mode & stat.S_IRGRP
    assert updated_mode & stat.S_IROTH


def test_make_file_sandbox_readable_skips_symlinks(tmp_path):
    file_path = tmp_path / "target-link.txt"
    file_path.write_text("hello", encoding="utf-8")
    symlink_stat = MagicMock(st_mode=stat.S_IFLNK)

    with (
        patch.object(uploads.os, "lstat", return_value=symlink_stat),
        patch.object(uploads.os, "chmod") as chmod,
    ):
        uploads._make_file_sandbox_readable(file_path)

    chmod.assert_not_called()


# ---------------------------------------------------------------------------
# _uses_thread_data_mounts
# ---------------------------------------------------------------------------


def test_uses_thread_data_mounts_true():
    provider = MagicMock()
    provider.uses_thread_data_mounts = True
    assert uploads._uses_thread_data_mounts(provider) is True


def test_uses_thread_data_mounts_false():
    provider = MagicMock()
    provider.uses_thread_data_mounts = False
    assert uploads._uses_thread_data_mounts(provider) is False


def test_uses_thread_data_mounts_no_attr():
    provider = MagicMock(spec=[])
    assert uploads._uses_thread_data_mounts(provider) is False


# ---------------------------------------------------------------------------
# _get_uploads_config_value
# ---------------------------------------------------------------------------


def test_get_uploads_config_value_dict_access():
    cfg = MagicMock()
    cfg.uploads = {"key1": "val1"}
    assert uploads._get_uploads_config_value(cfg, "key1", "default") == "val1"


def test_get_uploads_config_value_dict_missing():
    cfg = MagicMock()
    cfg.uploads = {}
    assert uploads._get_uploads_config_value(cfg, "missing", "default") == "default"


def test_get_uploads_config_value_attr_access():
    cfg = MagicMock()
    cfg.uploads = SimpleNamespace(key1="val1")
    assert uploads._get_uploads_config_value(cfg, "key1", "default") == "val1"


def test_get_uploads_config_value_attr_missing():
    cfg = MagicMock()
    cfg.uploads = SimpleNamespace()
    assert uploads._get_uploads_config_value(cfg, "missing", "default") == "default"


def test_get_uploads_config_value_none_uploads():
    cfg = MagicMock()
    cfg.uploads = None
    assert uploads._get_uploads_config_value(cfg, "key", "default") == "default"


# ---------------------------------------------------------------------------
# _get_upload_limit
# ---------------------------------------------------------------------------


def test_get_upload_limit_valid_value():
    cfg = MagicMock()
    cfg.uploads = {"max_files": 5}
    assert uploads._get_upload_limit(cfg, "max_files", 10) == 5


def test_get_upload_limit_uses_legacy_key():
    cfg = MagicMock()
    cfg.uploads = {"max_file_count": 7}
    assert uploads._get_upload_limit(cfg, "max_files", 10, legacy_key="max_file_count") == 7


def test_get_upload_limit_falls_back_to_default():
    cfg = MagicMock()
    cfg.uploads = {}
    assert uploads._get_upload_limit(cfg, "max_files", 10) == 10


def test_get_upload_limit_invalid_value_falls_back():
    cfg = MagicMock()
    cfg.uploads = {"max_files": "not_a_number"}
    assert uploads._get_upload_limit(cfg, "max_files", 10) == 10


def test_get_upload_limit_zero_falls_back():
    cfg = MagicMock()
    cfg.uploads = {"max_files": 0}
    assert uploads._get_upload_limit(cfg, "max_files", 10) == 10


def test_get_upload_limit_negative_falls_back():
    cfg = MagicMock()
    cfg.uploads = {"max_files": -1}
    assert uploads._get_upload_limit(cfg, "max_files", 10) == 10


def test_get_upload_limit_legacy_key_primary_missing():
    cfg = MagicMock()
    cfg.uploads = {"max_single_file_size": 500}
    result = uploads._get_upload_limit(cfg, "max_file_size", 1000, legacy_key="max_single_file_size")
    assert result == 500


# ---------------------------------------------------------------------------
# _get_upload_limits
# ---------------------------------------------------------------------------


def test_get_upload_limits_returns_defaults():
    cfg = MagicMock()
    cfg.uploads = {}
    limits = uploads._get_upload_limits(cfg)
    assert limits.max_files == uploads.DEFAULT_MAX_FILES
    assert limits.max_file_size == uploads.DEFAULT_MAX_FILE_SIZE
    assert limits.max_total_size == uploads.DEFAULT_MAX_TOTAL_SIZE


def test_get_upload_limits_reads_custom_values():
    cfg = MagicMock()
    cfg.uploads = {"max_files": 5, "max_file_size": 1024, "max_total_size": 2048}
    limits = uploads._get_upload_limits(cfg)
    assert limits.max_files == 5
    assert limits.max_file_size == 1024
    assert limits.max_total_size == 2048


# ---------------------------------------------------------------------------
# _cleanup_uploaded_paths
# ---------------------------------------------------------------------------


def test_cleanup_uploaded_paths_removes_files(tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("a")
    f2.write_text("b")
    uploads._cleanup_uploaded_paths([f1, f2])
    assert not f1.exists()
    assert not f2.exists()


def test_cleanup_uploaded_paths_handles_missing(tmp_path):
    missing = tmp_path / "nope.txt"
    uploads._cleanup_uploaded_paths([missing])


def test_cleanup_uploaded_paths_handles_unlink_error(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("data")
    with patch("os.unlink", side_effect=OSError("perm")):
        uploads._cleanup_uploaded_paths([f])


# ---------------------------------------------------------------------------
# _auto_convert_documents_enabled
# ---------------------------------------------------------------------------


def test_auto_convert_documents_enabled_defaults_to_false():
    cfg = MagicMock()
    cfg.uploads = {}
    assert uploads._auto_convert_documents_enabled(cfg) is False


def test_auto_convert_documents_enabled_true():
    cfg = MagicMock()
    cfg.uploads = {"auto_convert_documents": True}
    assert uploads._auto_convert_documents_enabled(cfg) is True


def test_auto_convert_documents_enabled_string_true():
    cfg = MagicMock()
    cfg.uploads = {"auto_convert_documents": "true"}
    assert uploads._auto_convert_documents_enabled(cfg) is True


def test_auto_convert_documents_enabled_string_yes():
    cfg = MagicMock()
    cfg.uploads = {"auto_convert_documents": "yes"}
    assert uploads._auto_convert_documents_enabled(cfg) is True


def test_auto_convert_documents_enabled_string_on():
    cfg = MagicMock()
    cfg.uploads = {"auto_convert_documents": "on"}
    assert uploads._auto_convert_documents_enabled(cfg) is True


def test_auto_convert_documents_enabled_string_1():
    cfg = MagicMock()
    cfg.uploads = {"auto_convert_documents": "1"}
    assert uploads._auto_convert_documents_enabled(cfg) is True


def test_auto_convert_documents_enabled_string_false():
    cfg = MagicMock()
    cfg.uploads = {"auto_convert_documents": "false"}
    assert uploads._auto_convert_documents_enabled(cfg) is False


def test_auto_convert_documents_enabled_exception():
    cfg = MagicMock()
    cfg.uploads = None
    assert uploads._auto_convert_documents_enabled(cfg) is False


def test_auto_convert_documents_enabled_defaults_to_false_on_config_errors():
    class BrokenConfig:
        def __getattribute__(self, name):
            if name == "uploads":
                raise RuntimeError("boom")
            return super().__getattribute__(name)

    assert uploads._auto_convert_documents_enabled(BrokenConfig()) is False


def test_auto_convert_documents_enabled_reads_dict_backed_uploads_config():
    cfg = MagicMock()
    cfg.uploads = {"auto_convert_documents": True}
    assert uploads._auto_convert_documents_enabled(cfg) is True


def test_auto_convert_documents_enabled_accepts_boolean_and_string_truthy_values():
    false_cfg = MagicMock()
    false_cfg.uploads = MagicMock(auto_convert_documents=False)
    true_cfg = MagicMock()
    true_cfg.uploads = MagicMock(auto_convert_documents=True)
    string_true_cfg = MagicMock()
    string_true_cfg.uploads = MagicMock(auto_convert_documents="YES")
    string_false_cfg = MagicMock()
    string_false_cfg.uploads = MagicMock(auto_convert_documents="false")

    assert uploads._auto_convert_documents_enabled(false_cfg) is False
    assert uploads._auto_convert_documents_enabled(true_cfg) is True
    assert uploads._auto_convert_documents_enabled(string_true_cfg) is True
    assert uploads._auto_convert_documents_enabled(string_false_cfg) is False


# ---------------------------------------------------------------------------
# Upload endpoint: direct-call tests
# ---------------------------------------------------------------------------


def test_upload_files_writes_thread_storage_and_skips_local_sandbox_sync(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True
    provider.acquire.return_value = "local"
    sandbox = MagicMock()
    provider.get.return_value = sandbox

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
    ):
        file = UploadFile(filename="notes.txt", file=BytesIO(b"hello uploads"))
        result = asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert result.success is True
    assert len(result.files) == 1
    assert result.files[0]["filename"] == "notes.txt"
    assert (thread_uploads_dir / "notes.txt").read_bytes() == b"hello uploads"
    sandbox.update_file.assert_not_called()


def test_upload_files_auto_renames_duplicate_form_filenames(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
    ):
        result = asyncio.run(
            call_unwrapped(
                uploads.upload_files,
                "thread-local",
                request=MagicMock(),
                files=[
                    UploadFile(filename="data.txt", file=BytesIO(b"first")),
                    UploadFile(filename="data.txt", file=BytesIO(b"second")),
                ],
                config=SimpleNamespace(),
            )
        )

    assert result.success is True
    assert [file_info["filename"] for file_info in result.files] == ["data.txt", "data_1.txt"]
    assert "original_filename" not in result.files[0]
    assert result.files[1]["original_filename"] == "data.txt"
    assert (thread_uploads_dir / "data.txt").read_bytes() == b"first"
    assert (thread_uploads_dir / "data_1.txt").read_bytes() == b"second"


def test_upload_files_skips_acquire_when_thread_data_is_mounted(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
    ):
        file = UploadFile(filename="notes.txt", file=BytesIO(b"hello uploads"))
        result = asyncio.run(call_unwrapped(uploads.upload_files, "thread-mounted", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert result.success is True
    assert (thread_uploads_dir / "notes.txt").read_bytes() == b"hello uploads"
    provider.acquire.assert_not_called()
    provider.get.assert_not_called()


def test_upload_files_does_not_auto_convert_documents_by_default(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
        patch.object(uploads, "_auto_convert_documents_enabled", return_value=False),
        patch.object(uploads, "convert_file_to_markdown", AsyncMock()) as convert_mock,
    ):
        file = UploadFile(filename="report.pdf", file=BytesIO(b"pdf-bytes"))
        result = asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert result.success is True
    assert len(result.files) == 1
    assert result.files[0]["filename"] == "report.pdf"
    assert "markdown_file" not in result.files[0]
    convert_mock.assert_not_called()


def test_upload_files_syncs_non_local_sandbox_and_marks_markdown_file(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = False
    provider.acquire.return_value = "aio-1"
    sandbox = MagicMock()
    provider.get.return_value = sandbox

    async def fake_convert(file_path: Path) -> Path:
        md_path = file_path.with_suffix(".md")
        md_path.write_text("converted", encoding="utf-8")
        return md_path

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
        patch.object(uploads, "_auto_convert_documents_enabled", return_value=True),
        patch.object(uploads, "convert_file_to_markdown", AsyncMock(side_effect=fake_convert)),
    ):
        file = UploadFile(filename="report.pdf", file=BytesIO(b"pdf-bytes"))
        result = asyncio.run(call_unwrapped(uploads.upload_files, "thread-aio", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert result.success is True
    assert len(result.files) == 1
    file_info = result.files[0]
    assert file_info["filename"] == "report.pdf"
    assert file_info["markdown_file"] == "report.md"
    assert (thread_uploads_dir / "report.pdf").read_bytes() == b"pdf-bytes"
    assert (thread_uploads_dir / "report.md").read_text(encoding="utf-8") == "converted"
    sandbox.update_file.assert_any_call("/mnt/user-data/uploads/report.pdf", b"pdf-bytes")
    sandbox.update_file.assert_any_call("/mnt/user-data/uploads/report.md", b"converted")


def test_upload_files_makes_non_local_files_sandbox_writable(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = False
    provider.acquire.return_value = "aio-1"
    sandbox = MagicMock()
    provider.get.return_value = sandbox

    async def fake_convert(file_path: Path) -> Path:
        md_path = file_path.with_suffix(".md")
        md_path.write_text("converted", encoding="utf-8")
        return md_path

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
        patch.object(uploads, "_auto_convert_documents_enabled", return_value=True),
        patch.object(uploads, "convert_file_to_markdown", AsyncMock(side_effect=fake_convert)),
        patch.object(uploads, "_make_file_sandbox_writable") as make_writable,
    ):
        file = UploadFile(filename="report.pdf", file=BytesIO(b"pdf-bytes"))
        result = asyncio.run(call_unwrapped(uploads.upload_files, "thread-aio", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert result.success is True
    make_writable.assert_any_call(thread_uploads_dir / "report.pdf")
    make_writable.assert_any_call(thread_uploads_dir / "report.md")


def test_upload_files_does_not_adjust_permissions_for_local_sandbox(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True
    provider.needs_upload_permission_adjustment = False

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
        patch.object(uploads, "_make_file_sandbox_writable") as make_writable,
        patch.object(uploads, "_make_file_sandbox_readable") as make_readable,
    ):
        file = UploadFile(filename="notes.txt", file=BytesIO(b"hello uploads"))
        result = asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert result.success is True
    make_writable.assert_not_called()
    make_readable.assert_called_once()


def test_upload_files_acquires_non_local_sandbox_before_writing(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = False
    sandbox = MagicMock()
    provider.get.return_value = sandbox

    def acquire_before_writes(thread_id: str) -> str:
        assert list(thread_uploads_dir.iterdir()) == []
        return "aio-1"

    provider.acquire.side_effect = acquire_before_writes

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
    ):
        file = UploadFile(filename="notes.txt", file=BytesIO(b"hello uploads"))
        result = asyncio.run(call_unwrapped(uploads.upload_files, "thread-aio", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert result.success is True
    provider.acquire.assert_called_once_with("thread-aio")
    sandbox.update_file.assert_called_once_with("/mnt/user-data/uploads/notes.txt", b"hello uploads")


def test_upload_files_fails_before_writing_when_non_local_sandbox_unavailable(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = False
    provider.acquire.side_effect = RuntimeError("sandbox unavailable")
    file = ChunkedUpload("notes.txt", [b"hello uploads"])

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
    ):
        with pytest.raises(RuntimeError, match="sandbox unavailable"):
            asyncio.run(call_unwrapped(uploads.upload_files, "thread-aio", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert list(thread_uploads_dir.iterdir()) == []
    assert file.read_calls == []


def test_upload_files_rejects_too_many_files_before_writing(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=_mounted_provider()),
        patch.object(uploads, "_get_upload_limits", return_value=uploads.UploadLimits(max_files=1, max_file_size=10, max_total_size=20)),
    ):
        files = [
            ChunkedUpload("one.txt", [b"one"]),
            ChunkedUpload("two.txt", [b"two"]),
        ]
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=files, config=SimpleNamespace()))

    assert exc_info.value.status_code == 413
    assert list(thread_uploads_dir.iterdir()) == []
    assert files[0].read_calls == []
    assert files[1].read_calls == []


def test_upload_files_rejects_oversized_single_file_and_removes_partial_file(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = _mounted_provider()
    file = ChunkedUpload("big.txt", [b"123456"])

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
        patch.object(uploads, "_get_upload_limits", return_value=uploads.UploadLimits(max_files=10, max_file_size=5, max_total_size=20)),
    ):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert exc_info.value.status_code == 413
    assert not (thread_uploads_dir / "big.txt").exists()


def test_upload_files_rejects_total_size_over_limit_and_cleans_request_files(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=_mounted_provider()),
        patch.object(uploads, "_get_upload_limits", return_value=uploads.UploadLimits(max_files=10, max_file_size=10, max_total_size=5)),
    ):
        files = [
            ChunkedUpload("first.txt", [b"123"]),
            ChunkedUpload("second.txt", [b"456"]),
        ]
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=files, config=SimpleNamespace()))

    assert exc_info.value.status_code == 413
    assert not (thread_uploads_dir / "first.txt").exists()
    assert not (thread_uploads_dir / "second.txt").exists()


def test_upload_files_does_not_sync_non_local_sandbox_when_total_size_exceeds_limit(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = False
    provider.acquire.return_value = "aio-1"
    sandbox = MagicMock()
    provider.get.return_value = sandbox

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
        patch.object(uploads, "_get_upload_limits", return_value=uploads.UploadLimits(max_files=10, max_file_size=10, max_total_size=5)),
    ):
        files = [
            ChunkedUpload("first.txt", [b"123"]),
            ChunkedUpload("second.txt", [b"456"]),
        ]
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.upload_files, "thread-aio", request=MagicMock(), files=files, config=SimpleNamespace()))

    assert exc_info.value.status_code == 413
    sandbox.update_file.assert_not_called()


def test_upload_files_does_not_sync_non_local_sandbox_when_conversion_fails(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = False
    provider.acquire.return_value = "aio-1"
    sandbox = MagicMock()
    provider.get.return_value = sandbox

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
        patch.object(uploads, "_auto_convert_documents_enabled", return_value=True),
        patch.object(uploads, "convert_file_to_markdown", AsyncMock(side_effect=RuntimeError("conversion failed"))),
    ):
        file = UploadFile(filename="report.pdf", file=BytesIO(b"pdf-bytes"))
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.upload_files, "thread-aio", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert exc_info.value.status_code == 500
    sandbox.update_file.assert_not_called()
    assert not (thread_uploads_dir / "report.pdf").exists()


def test_upload_files_adjusts_read_permissions_for_mounted_non_local_sandbox(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True
    provider.needs_upload_permission_adjustment = True

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
        patch.object(uploads, "_make_file_sandbox_readable") as make_readable,
    ):
        file = UploadFile(filename="notes.txt", file=BytesIO(b"hello uploads"))
        result = asyncio.run(call_unwrapped(uploads.upload_files, "thread-aio", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert result.success is True
    make_readable.assert_called_once()


def test_upload_files_rejects_dotdot_and_dot_filenames(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.acquire.return_value = "local"
    sandbox = MagicMock()
    provider.get.return_value = sandbox

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
    ):
        for bad_name in ["..", "."]:
            file = UploadFile(filename=bad_name, file=BytesIO(b"data"))
            result = asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=[file], config=SimpleNamespace()))
            assert result.success is True
            assert result.files == [], f"Expected no files for unsafe filename {bad_name!r}"

        file = UploadFile(filename="../etc/passwd", file=BytesIO(b"data"))
        result = asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=[file], config=SimpleNamespace()))
        assert result.success is True
        assert len(result.files) == 1
        assert result.files[0]["filename"] == "passwd"

    assert [f.name for f in thread_uploads_dir.iterdir()] == ["passwd"]


def test_upload_files_rejects_preexisting_symlink_destination(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("protected", encoding="utf-8")
    (thread_uploads_dir / "victim.txt").symlink_to(outside_file)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
    ):
        file = UploadFile(filename="victim.txt", file=BytesIO(b"attacker upload"))
        result = asyncio.run(uploads.upload_files("thread-local", files=[file]))

    assert result.success is False
    assert result.files == []
    assert result.skipped_files == ["victim.txt"]
    assert "skipped 1 unsafe file" in result.message
    assert outside_file.read_text(encoding="utf-8") == "protected"


def test_upload_files_rejects_dangling_symlink_destination(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)
    missing_target = tmp_path / "missing-target.txt"
    (thread_uploads_dir / "victim.txt").symlink_to(missing_target)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
    ):
        file = UploadFile(filename="victim.txt", file=BytesIO(b"attacker upload"))
        result = asyncio.run(uploads.upload_files("thread-local", files=[file]))

    assert result.success is False
    assert result.files == []
    assert result.skipped_files == ["victim.txt"]
    assert not missing_target.exists()


def test_upload_files_rejects_hardlinked_destination_without_truncating(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("protected", encoding="utf-8")
    os.link(outside_file, thread_uploads_dir / "victim.txt")

    provider = MagicMock()
    provider.uses_thread_data_mounts = True

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
    ):
        file = UploadFile(filename="victim.txt", file=BytesIO(b"attacker upload"))
        result = asyncio.run(uploads.upload_files("thread-local", files=[file]))

    assert result.success is False
    assert result.files == []
    assert result.skipped_files == ["victim.txt"]
    assert outside_file.read_text(encoding="utf-8") == "protected"


def test_upload_files_overwrites_existing_regular_file(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)
    existing_file = thread_uploads_dir / "notes.txt"
    existing_file.write_bytes(b"old upload")
    assert existing_file.stat().st_nlink == 1

    provider = MagicMock()
    provider.uses_thread_data_mounts = True

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
    ):
        file = UploadFile(filename="notes.txt", file=BytesIO(b"new upload"))
        result = asyncio.run(uploads.upload_files("thread-local", files=[file]))

    assert result.success is True
    assert [file_info["filename"] for file_info in result.files] == ["notes.txt"]
    assert existing_file.read_bytes() == b"new upload"


def test_upload_files_no_files_provided(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
    ):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=[], config=SimpleNamespace()))

    assert exc_info.value.status_code == 400


def test_upload_files_ensure_dir_value_error(tmp_path):
    with (
        patch.object(uploads, "ensure_uploads_dir", side_effect=ValueError("bad thread")),
        patch.object(uploads, "get_sandbox_provider", return_value=_mounted_provider()),
    ):
        file = UploadFile(filename="test.txt", file=BytesIO(b"data"))
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert exc_info.value.status_code == 400


def test_upload_files_sandbox_acquire_returns_none(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = False
    provider.acquire.return_value = "aio-1"
    provider.get.return_value = None

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
    ):
        file = UploadFile(filename="test.txt", file=BytesIO(b"x"))
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert exc_info.value.status_code == 500


def test_upload_files_no_filename_skipped(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
    ):
        file = UploadFile(filename=None, file=BytesIO(b"data"))
        result = asyncio.run(uploads.upload_files("thread-local", files=[file]))

    assert result.success is True
    assert result.files == []


def test_upload_files_unsafe_path_error_skipped(tmp_path):
    """UnsafeUploadPathError results in skipped_files, not a crash."""
    from ideer.uploads.manager import UnsafeUploadPathError

    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
        patch.object(uploads, "upload_virtual_path", side_effect=UnsafeUploadPathError("unsafe")),
    ):
        file = UploadFile(filename="bad.txt", file=BytesIO(b"data"))
        result = asyncio.run(uploads.upload_files("thread-local", files=[file]))

    assert result.success is False
    assert len(result.skipped_files) == 1


def test_upload_files_generic_exception_returns_500(tmp_path):
    """Generic exception during file write triggers cleanup and 500."""
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
        patch.object(uploads, "open_upload_file_no_symlink", side_effect=RuntimeError("disk full")),
    ):
        file = UploadFile(filename="test.txt", file=BytesIO(b"x"))
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Delete endpoint
# ---------------------------------------------------------------------------


def test_delete_uploaded_file_removes_generated_markdown_companion(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)
    (thread_uploads_dir / "report.pdf").write_bytes(b"pdf-bytes")
    (thread_uploads_dir / "report.md").write_text("converted", encoding="utf-8")

    with patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir):
        result = asyncio.run(call_unwrapped(uploads.delete_uploaded_file, "thread-aio", "report.pdf", request=MagicMock()))

    assert result == {"success": True, "message": "Deleted report.pdf"}
    assert not (thread_uploads_dir / "report.pdf").exists()
    assert not (thread_uploads_dir / "report.md").exists()


def test_delete_uploaded_file_value_error(tmp_path):
    with patch.object(uploads, "get_uploads_dir", side_effect=ValueError("bad thread")):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.delete_uploaded_file, "thread-local", "test.txt", request=MagicMock()))

    assert exc_info.value.status_code == 400


def test_delete_uploaded_file_not_found(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    with patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.delete_uploaded_file, "thread-local", "missing.txt", request=MagicMock()))

    assert exc_info.value.status_code == 404


def test_delete_uploaded_file_generic_error(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    with (
        patch.object(uploads, "get_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "delete_file_safe", side_effect=RuntimeError("boom")),
    ):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.delete_uploaded_file, "thread-local", "test.txt", request=MagicMock()))

    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Limits endpoint
# ---------------------------------------------------------------------------


def test_upload_limits_endpoint_reads_uploads_config():
    cfg = MagicMock()
    cfg.uploads = {"max_files": 15, "max_file_size": "1048576", "max_total_size": 2097152}

    result = asyncio.run(call_unwrapped(uploads.get_upload_limits, "thread-local", request=MagicMock(), config=cfg))

    assert result.max_files == 15
    assert result.max_file_size == 1048576
    assert result.max_total_size == 2097152


def test_upload_limits_accept_legacy_config_keys():
    cfg = MagicMock()
    cfg.uploads = {"max_file_count": 7, "max_single_file_size": 123, "max_total_size": 456}

    limits = uploads._get_upload_limits(cfg)

    assert limits == uploads.UploadLimits(max_files=7, max_file_size=123, max_total_size=456)


def test_upload_limits_endpoint_requires_thread_access():
    cfg = MagicMock()
    cfg.uploads = {}
    app = make_authed_test_app(owner_check_passes=False)
    app.state.config = cfg
    app.dependency_overrides[get_config] = lambda: cfg
    app.include_router(uploads.router)

    with TestClient(app) as client:
        response = client.get("/api/threads/thread-local/uploads/limits")

    assert response.status_code == 404


def test_upload_files_uses_configured_file_count_limit(tmp_path):
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    cfg = MagicMock()
    cfg.uploads = {"max_files": 1}

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=_mounted_provider()),
    ):
        files = [
            ChunkedUpload("one.txt", [b"one"]),
            ChunkedUpload("two.txt", [b"two"]),
        ]
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=files, config=cfg))

    assert exc_info.value.status_code == 413


# ---------------------------------------------------------------------------
# List endpoint
# ---------------------------------------------------------------------------


def test_list_uploaded_files_value_error():
    with patch.object(uploads, "get_uploads_dir", side_effect=ValueError("bad thread")):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.list_uploaded_files, "thread-local", request=MagicMock()))

    assert exc_info.value.status_code == 400


def test_upload_files_generic_error_returns_500(tmp_path):
    """Generic exception during file write triggers cleanup and 500."""
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
        patch.object(uploads, "open_upload_file_no_symlink", side_effect=RuntimeError("boom")),
    ):
        file = UploadFile(filename="test.txt", file=BytesIO(b"x"))
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert exc_info.value.status_code == 500
    assert "boom" in exc_info.value.detail


def test_upload_files_http_exception_during_write_is_reraised(tmp_path):
    """HTTPException raised during _write_upload_file_with_limits is re-raised, not wrapped."""
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
        patch.object(uploads, "open_upload_file_no_symlink", side_effect=HTTPException(status_code=413, detail="File too large")),
    ):
        file = UploadFile(filename="big.bin", file=BytesIO(b"x"))
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert exc_info.value.status_code == 413


def test_upload_files_with_auto_convert_returns_none_md_path(tmp_path):
    """When convert_file_to_markdown returns None, no markdown_file key is added."""
    thread_uploads_dir = tmp_path / "uploads"
    thread_uploads_dir.mkdir(parents=True)

    provider = MagicMock()
    provider.uses_thread_data_mounts = True

    with (
        patch.object(uploads, "ensure_uploads_dir", return_value=thread_uploads_dir),
        patch.object(uploads, "get_sandbox_provider", return_value=provider),
        patch.object(uploads, "_auto_convert_documents_enabled", return_value=True),
        patch.object(uploads, "convert_file_to_markdown", AsyncMock(return_value=None)),
        patch.object(uploads, "CONVERTIBLE_EXTENSIONS", {".pdf"}),
    ):
        file = UploadFile(filename="report.pdf", file=BytesIO(b"pdf"))
        result = asyncio.run(call_unwrapped(uploads.upload_files, "thread-local", request=MagicMock(), files=[file], config=SimpleNamespace()))

    assert result.success is True
    assert "markdown_file" not in result.files[0]
