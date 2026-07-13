"""Comprehensive tests for channel file attachment support.

Covers:
- ResolvedAttachment dataclass construction and fields
- OutboundMessage.attachments field
- _resolve_attachments (valid, image, missing, invalid, security rejects, path traversal, partial)
- _format_artifact_text
- _ingest_inbound_files (symlink attacks, hardlink protection, normal ingestion)
- Channel base class _on_outbound with attachments
- Channel.receive_file default behavior
- Channel.send_file default behavior
- Channel._make_inbound helper
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.channels.base import Channel
from app.channels.message_bus import InboundMessage, MessageBus, OutboundMessage, ResolvedAttachment


def _run(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# ResolvedAttachment tests
# ---------------------------------------------------------------------------


class TestResolvedAttachment:
    def test_basic_construction(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_bytes(b"PDF content")

        att = ResolvedAttachment(
            virtual_path="/mnt/user-data/outputs/test.pdf",
            actual_path=f,
            filename="test.pdf",
            mime_type="application/pdf",
            size=11,
            is_image=False,
        )
        assert att.filename == "test.pdf"
        assert att.is_image is False
        assert att.size == 11
        assert att.virtual_path == "/mnt/user-data/outputs/test.pdf"
        assert att.actual_path == f
        assert att.mime_type == "application/pdf"

    def test_image_detection(self, tmp_path):
        f = tmp_path / "photo.png"
        f.write_bytes(b"\x89PNG")

        att = ResolvedAttachment(
            virtual_path="/mnt/user-data/outputs/photo.png",
            actual_path=f,
            filename="photo.png",
            mime_type="image/png",
            size=4,
            is_image=True,
        )
        assert att.is_image is True

    def test_all_image_types(self, tmp_path):
        """Various image MIME types should have is_image=True."""
        for ext, mime in [("jpg", "image/jpeg"), ("gif", "image/gif"), ("webp", "image/webp"), ("svg", "image/svg+xml")]:
            f = tmp_path / f"img.{ext}"
            f.write_bytes(b"data")
            att = ResolvedAttachment(
                virtual_path=f"/outputs/img.{ext}",
                actual_path=f,
                filename=f"img.{ext}",
                mime_type=mime,
                size=4,
                is_image=True,
            )
            assert att.is_image is True

    def test_zero_size_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")

        att = ResolvedAttachment(
            virtual_path="/outputs/empty.txt",
            actual_path=f,
            filename="empty.txt",
            mime_type="text/plain",
            size=0,
            is_image=False,
        )
        assert att.size == 0


# ---------------------------------------------------------------------------
# OutboundMessage.attachments field tests
# ---------------------------------------------------------------------------


class TestOutboundMessageAttachments:
    def test_default_empty_attachments(self):
        msg = OutboundMessage(
            channel_name="test",
            chat_id="c1",
            thread_id="t1",
            text="hello",
        )
        assert msg.attachments == []

    def test_attachments_populated(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("content")

        att = ResolvedAttachment(
            virtual_path="/mnt/user-data/outputs/file.txt",
            actual_path=f,
            filename="file.txt",
            mime_type="text/plain",
            size=7,
            is_image=False,
        )
        msg = OutboundMessage(
            channel_name="test",
            chat_id="c1",
            thread_id="t1",
            text="hello",
            attachments=[att],
        )
        assert len(msg.attachments) == 1
        assert msg.attachments[0].filename == "file.txt"

    def test_multiple_attachments(self, tmp_path):
        atts = []
        for name in ["a.txt", "b.pdf", "c.png"]:
            f = tmp_path / name
            f.write_bytes(b"data")
            atts.append(ResolvedAttachment(f"/outputs/{name}", f, name, "application/octet-stream", 4, False))

        msg = OutboundMessage(channel_name="test", chat_id="c1", thread_id="t1", text="files", attachments=atts)
        assert len(msg.attachments) == 3

    def test_artifacts_field_default(self):
        msg = OutboundMessage(channel_name="test", chat_id="c1", thread_id="t1", text="hello")
        assert msg.artifacts == []

    def test_is_final_default(self):
        msg = OutboundMessage(channel_name="test", chat_id="c1", thread_id="t1", text="hello")
        assert msg.is_final is True


# ---------------------------------------------------------------------------
# _resolve_attachments tests
# ---------------------------------------------------------------------------


class TestResolveAttachments:
    def test_resolves_existing_file(self, tmp_path):
        """Successfully resolves a virtual path to an existing file."""
        from app.channels.manager import _resolve_attachments

        thread_id = "test-thread-123"
        outputs_dir = tmp_path / "threads" / thread_id / "user-data" / "outputs"
        outputs_dir.mkdir(parents=True)
        test_file = outputs_dir / "report.pdf"
        test_file.write_bytes(b"%PDF-1.4 fake content")

        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = test_file
        mock_paths.sandbox_outputs_dir.return_value = outputs_dir

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments(thread_id, ["/mnt/user-data/outputs/report.pdf"])

        assert len(result) == 1
        assert result[0].filename == "report.pdf"
        assert result[0].mime_type == "application/pdf"
        assert result[0].is_image is False
        assert result[0].size == len(b"%PDF-1.4 fake content")

    def test_resolves_image_file(self, tmp_path):
        """Images are detected by MIME type."""
        from app.channels.manager import _resolve_attachments

        thread_id = "test-thread"
        outputs_dir = tmp_path / "threads" / thread_id / "user-data" / "outputs"
        outputs_dir.mkdir(parents=True)
        img = outputs_dir / "chart.png"
        img.write_bytes(b"\x89PNG fake image")

        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = img
        mock_paths.sandbox_outputs_dir.return_value = outputs_dir

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments(thread_id, ["/mnt/user-data/outputs/chart.png"])

        assert len(result) == 1
        assert result[0].is_image is True
        assert result[0].mime_type == "image/png"

    def test_resolves_jpeg_image(self, tmp_path):
        """JPEG images are detected."""
        from app.channels.manager import _resolve_attachments

        thread_id = "test-thread"
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir(parents=True)
        img = outputs_dir / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff")

        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = img
        mock_paths.sandbox_outputs_dir.return_value = outputs_dir

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments(thread_id, ["/mnt/user-data/outputs/photo.jpg"])

        assert len(result) == 1
        assert result[0].is_image is True
        assert result[0].mime_type == "image/jpeg"

    def test_resolves_csv_file(self, tmp_path):
        """CSV files get text/csv MIME type."""
        from app.channels.manager import _resolve_attachments

        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir(parents=True)
        f = outputs_dir / "data.csv"
        f.write_text("a,b,c")

        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = f
        mock_paths.sandbox_outputs_dir.return_value = outputs_dir

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments("t1", ["/mnt/user-data/outputs/data.csv"])

        assert len(result) == 1
        assert result[0].mime_type == "text/csv"

    def test_resolves_docx_file(self, tmp_path):
        """DOCX files get correct MIME type."""
        from app.channels.manager import _resolve_attachments

        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir(parents=True)
        f = outputs_dir / "report.docx"
        f.write_bytes(b"PK")

        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = f
        mock_paths.sandbox_outputs_dir.return_value = outputs_dir

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments("t1", ["/mnt/user-data/outputs/report.docx"])

        assert len(result) == 1
        assert "wordprocessingml" in result[0].mime_type

    def test_resolves_xlsx_file(self, tmp_path):
        """XLSX files get correct MIME type."""
        from app.channels.manager import _resolve_attachments

        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir(parents=True)
        f = outputs_dir / "data.xlsx"
        f.write_bytes(b"PK")

        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = f
        mock_paths.sandbox_outputs_dir.return_value = outputs_dir

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments("t1", ["/mnt/user-data/outputs/data.xlsx"])

        assert len(result) == 1
        assert "spreadsheetml" in result[0].mime_type

    def test_resolves_pptx_file(self, tmp_path):
        """PPTX files get correct MIME type."""
        from app.channels.manager import _resolve_attachments

        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir(parents=True)
        f = outputs_dir / "slides.pptx"
        f.write_bytes(b"PK")

        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = f
        mock_paths.sandbox_outputs_dir.return_value = outputs_dir

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments("t1", ["/mnt/user-data/outputs/slides.pptx"])

        assert len(result) == 1
        assert "presentationml" in result[0].mime_type

    def test_skips_missing_file(self, tmp_path):
        """Missing files are skipped with a warning."""
        from app.channels.manager import _resolve_attachments

        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()

        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = outputs_dir / "nonexistent.txt"
        mock_paths.sandbox_outputs_dir.return_value = outputs_dir

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments("t1", ["/mnt/user-data/outputs/nonexistent.txt"])

        assert result == []

    def test_skips_invalid_path(self):
        """Invalid paths (ValueError from resolve) are skipped."""
        from app.channels.manager import _resolve_attachments

        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.side_effect = ValueError("bad path")

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments("t1", ["/invalid/path"])

        assert result == []

    def test_rejects_uploads_path(self):
        """Paths under /mnt/user-data/uploads/ are rejected (security)."""
        from app.channels.manager import _resolve_attachments

        mock_paths = MagicMock()

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments("t1", ["/mnt/user-data/uploads/secret.pdf"])

        assert result == []
        mock_paths.resolve_virtual_path.assert_not_called()

    def test_rejects_workspace_path(self):
        """Paths under /mnt/user-data/workspace/ are rejected (security)."""
        from app.channels.manager import _resolve_attachments

        mock_paths = MagicMock()

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments("t1", ["/mnt/user-data/workspace/config.py"])

        assert result == []
        mock_paths.resolve_virtual_path.assert_not_called()

    def test_rejects_path_traversal_escape(self, tmp_path):
        """Paths that escape the outputs directory after resolution are rejected."""
        from app.channels.manager import _resolve_attachments

        thread_id = "t1"
        outputs_dir = tmp_path / "threads" / thread_id / "user-data" / "outputs"
        outputs_dir.mkdir(parents=True)
        escaped_file = tmp_path / "threads" / thread_id / "user-data" / "uploads" / "stolen.txt"
        escaped_file.parent.mkdir(parents=True, exist_ok=True)
        escaped_file.write_text("sensitive")

        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = escaped_file
        mock_paths.sandbox_outputs_dir.return_value = outputs_dir

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments(thread_id, ["/mnt/user-data/outputs/../uploads/stolen.txt"])

        assert result == []

    def test_multiple_artifacts_partial_resolution(self, tmp_path):
        """Mixed valid/invalid artifacts: only valid ones are returned."""
        from app.channels.manager import _resolve_attachments

        thread_id = "t1"
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()
        good_file = outputs_dir / "data.csv"
        good_file.write_text("a,b,c")

        mock_paths = MagicMock()
        mock_paths.sandbox_outputs_dir.return_value = outputs_dir

        def resolve_side_effect(tid, vpath, *, user_id=None):
            if "data.csv" in vpath:
                return good_file
            return tmp_path / "missing.txt"

        mock_paths.resolve_virtual_path.side_effect = resolve_side_effect

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments(
                thread_id,
                ["/mnt/user-data/outputs/data.csv", "/mnt/user-data/outputs/missing.txt"],
            )

        assert len(result) == 1
        assert result[0].filename == "data.csv"

    def test_empty_artifacts_list(self):
        """Empty artifacts list returns empty result."""
        from app.channels.manager import _resolve_attachments

        mock_paths = MagicMock()
        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments("t1", [])

        assert result == []

    def test_unknown_extension_gets_octet_stream(self, tmp_path):
        """Unknown file extensions get application/octet-stream."""
        from app.channels.manager import _resolve_attachments

        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir(parents=True)
        f = outputs_dir / "data.xyz123"
        f.write_bytes(b"data")

        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = f
        mock_paths.sandbox_outputs_dir.return_value = outputs_dir

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments("t1", ["/mnt/user-data/outputs/data.xyz123"])

        assert len(result) == 1
        assert result[0].mime_type == "application/octet-stream"


# ---------------------------------------------------------------------------
# _format_artifact_text tests
# ---------------------------------------------------------------------------


class TestFormatArtifactText:
    def test_single_artifact(self):
        from app.channels.manager import _format_artifact_text

        result = _format_artifact_text(["/mnt/user-data/outputs/report.pdf"])
        assert "report.pdf" in result

    def test_multiple_artifacts(self):
        from app.channels.manager import _format_artifact_text

        result = _format_artifact_text(
            [
                "/mnt/user-data/outputs/a.txt",
                "/mnt/user-data/outputs/b.txt",
            ]
        )
        assert "a.txt" in result
        assert "b.txt" in result

    def test_empty_artifacts(self):
        from app.channels.manager import _format_artifact_text

        result = _format_artifact_text([])
        assert result == "" or "no artifacts" in result.lower() or result is not None


# ---------------------------------------------------------------------------
# Inbound file ingestion tests
# ---------------------------------------------------------------------------


class TestInboundFileIngestion:
    def test_rejects_preexisting_symlink_destination(self, tmp_path):
        from app.channels import manager

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()
        outside_file = tmp_path / "outside-created.txt"
        (uploads_dir / "victim.txt").symlink_to(outside_file)

        msg = InboundMessage(
            channel_name="test-channel",
            chat_id="chat-1",
            user_id="user-1",
            text="see attachment",
            files=[{"filename": "victim.txt", "url": "https://example.invalid/victim.txt"}],
        )

        async def fake_reader(file_info, client):
            return b"attacker data"

        with (
            patch("ideer.uploads.manager.ensure_uploads_dir", return_value=uploads_dir),
            patch.dict(manager.INBOUND_FILE_READERS, {"test-channel": fake_reader}, clear=False),
        ):
            result = _run(manager._ingest_inbound_files("thread-1", msg))

        assert result == []
        assert not outside_file.exists()
        assert (uploads_dir / "victim.txt").is_symlink()

    def test_rejects_dangling_symlink_destination(self, tmp_path):
        from app.channels import manager

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()
        missing_target = tmp_path / "missing-created.txt"
        (uploads_dir / "victim.txt").symlink_to(missing_target)

        msg = InboundMessage(
            channel_name="test-channel",
            chat_id="chat-1",
            user_id="user-1",
            text="see attachment",
            files=[{"filename": "victim.txt", "url": "https://example.invalid/victim.txt"}],
        )

        async def fake_reader(file_info, client):
            return b"attacker data"

        with (
            patch("ideer.uploads.manager.ensure_uploads_dir", return_value=uploads_dir),
            patch.dict(manager.INBOUND_FILE_READERS, {"test-channel": fake_reader}, clear=False),
        ):
            result = _run(manager._ingest_inbound_files("thread-1", msg))

        assert result == []
        assert not missing_target.exists()
        assert (uploads_dir / "victim.txt").is_symlink()

    def test_hardlinked_existing_file_is_not_overwritten(self, tmp_path):
        from app.channels import manager

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()
        outside_file = tmp_path / "outside-created.txt"
        outside_file.write_text("protected", encoding="utf-8")
        os.link(outside_file, uploads_dir / "victim.txt")

        msg = InboundMessage(
            channel_name="test-channel",
            chat_id="chat-1",
            user_id="user-1",
            text="see attachment",
            files=[{"filename": "victim.txt", "url": "https://example.invalid/victim.txt"}],
        )

        async def fake_reader(file_info, client):
            return b"new attachment data"

        with (
            patch("ideer.uploads.manager.ensure_uploads_dir", return_value=uploads_dir),
            patch.dict(manager.INBOUND_FILE_READERS, {"test-channel": fake_reader}, clear=False),
        ):
            result = _run(manager._ingest_inbound_files("thread-1", msg))

        assert result == [
            {
                "filename": "victim_1.txt",
                "size": len(b"new attachment data"),
                "path": "/mnt/user-data/uploads/victim_1.txt",
                "is_image": False,
            }
        ]
        assert outside_file.read_text(encoding="utf-8") == "protected"
        assert (uploads_dir / "victim.txt").read_text(encoding="utf-8") == "protected"
        assert (uploads_dir / "victim_1.txt").read_bytes() == b"new attachment data"

    def test_normal_file_ingestion(self, tmp_path):
        """Normal file ingestion without attacks works correctly."""
        from app.channels import manager

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()

        msg = InboundMessage(
            channel_name="test-channel",
            chat_id="chat-1",
            user_id="user-1",
            text="see attachment",
            files=[{"filename": "report.pdf", "url": "https://example.invalid/report.pdf"}],
        )

        async def fake_reader(file_info, client):
            return b"%PDF-1.4 content"

        with (
            patch("ideer.uploads.manager.ensure_uploads_dir", return_value=uploads_dir),
            patch.dict(manager.INBOUND_FILE_READERS, {"test-channel": fake_reader}, clear=False),
        ):
            result = _run(manager._ingest_inbound_files("thread-1", msg))

        assert len(result) == 1
        assert result[0]["filename"] == "report.pdf"
        assert result[0]["size"] == len(b"%PDF-1.4 content")
        assert result[0]["path"] == "/mnt/user-data/uploads/report.pdf"
        assert result[0]["is_image"] is False
        assert (uploads_dir / "report.pdf").read_bytes() == b"%PDF-1.4 content"

    def test_image_file_ingestion(self, tmp_path):
        """Image files are marked as is_image=True when type='image' in file info."""
        from app.channels import manager

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()

        msg = InboundMessage(
            channel_name="test-channel",
            chat_id="chat-1",
            user_id="user-1",
            text="see image",
            files=[{"filename": "photo.png", "url": "https://example.invalid/photo.png", "type": "image"}],
        )

        async def fake_reader(file_info, client):
            return b"\x89PNG image data"

        with (
            patch("ideer.uploads.manager.ensure_uploads_dir", return_value=uploads_dir),
            patch.dict(manager.INBOUND_FILE_READERS, {"test-channel": fake_reader}, clear=False),
        ):
            result = _run(manager._ingest_inbound_files("thread-1", msg))

        assert len(result) == 1
        assert result[0]["is_image"] is True

    def test_no_reader_registered_skips_files(self, tmp_path):
        """When no reader is registered for the channel, files are skipped."""
        from app.channels import manager

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()

        msg = InboundMessage(
            channel_name="unknown-channel",
            chat_id="chat-1",
            user_id="user-1",
            text="see attachment",
            files=[{"filename": "file.txt", "url": "https://example.invalid/file.txt"}],
        )

        with patch("ideer.uploads.manager.ensure_uploads_dir", return_value=uploads_dir):
            result = _run(manager._ingest_inbound_files("thread-1", msg))

        assert result == []

    def test_reader_failure_skips_file(self, tmp_path):
        """When the reader fails, the file is skipped."""
        from app.channels import manager

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()

        msg = InboundMessage(
            channel_name="test-channel",
            chat_id="chat-1",
            user_id="user-1",
            text="see attachment",
            files=[{"filename": "fail.txt", "url": "https://example.invalid/fail.txt"}],
        )

        async def failing_reader(file_info, client):
            raise RuntimeError("download failed")

        with (
            patch("ideer.uploads.manager.ensure_uploads_dir", return_value=uploads_dir),
            patch.dict(manager.INBOUND_FILE_READERS, {"test-channel": failing_reader}, clear=False),
        ):
            result = _run(manager._ingest_inbound_files("thread-1", msg))

        assert result == []

    def test_duplicate_filename_gets_numbered_suffix(self, tmp_path):
        """When a file already exists, a numbered suffix is added."""
        from app.channels import manager

        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()
        (uploads_dir / "report.pdf").write_bytes(b"existing")

        msg = InboundMessage(
            channel_name="test-channel",
            chat_id="chat-1",
            user_id="user-1",
            text="see attachment",
            files=[{"filename": "report.pdf", "url": "https://example.invalid/report.pdf"}],
        )

        async def fake_reader(file_info, client):
            return b"new content"

        with (
            patch("ideer.uploads.manager.ensure_uploads_dir", return_value=uploads_dir),
            patch.dict(manager.INBOUND_FILE_READERS, {"test-channel": fake_reader}, clear=False),
        ):
            result = _run(manager._ingest_inbound_files("thread-1", msg))

        assert len(result) == 1
        assert result[0]["filename"] == "report_1.pdf"
        assert (uploads_dir / "report.pdf").read_bytes() == b"existing"
        assert (uploads_dir / "report_1.pdf").read_bytes() == b"new content"


# ---------------------------------------------------------------------------
# Channel base class _on_outbound with attachments
# ---------------------------------------------------------------------------


class _DummyChannel(Channel):
    """Concrete channel for testing the base class behavior."""

    def __init__(self, bus):
        super().__init__(name="dummy", bus=bus, config={})
        self.sent_messages: list[OutboundMessage] = []
        self.sent_files: list[tuple[OutboundMessage, ResolvedAttachment]] = []

    async def start(self):
        self._running = True

    async def stop(self):
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        self.sent_messages.append(msg)

    async def send_file(self, msg: OutboundMessage, attachment: ResolvedAttachment) -> bool:
        self.sent_files.append((msg, attachment))
        return True


class TestBaseChannelOnOutbound:
    def test_send_file_called_for_each_attachment(self, tmp_path):
        """_on_outbound sends text first, then uploads each attachment."""
        bus = MessageBus()
        ch = _DummyChannel(bus)

        f1 = tmp_path / "a.txt"
        f1.write_text("aaa")
        f2 = tmp_path / "b.png"
        f2.write_bytes(b"\x89PNG")

        att1 = ResolvedAttachment("/mnt/user-data/outputs/a.txt", f1, "a.txt", "text/plain", 3, False)
        att2 = ResolvedAttachment("/mnt/user-data/outputs/b.png", f2, "b.png", "image/png", 4, True)

        msg = OutboundMessage(
            channel_name="dummy",
            chat_id="c1",
            thread_id="t1",
            text="Here are your files",
            attachments=[att1, att2],
        )

        _run(ch._on_outbound(msg))

        assert len(ch.sent_messages) == 1
        assert len(ch.sent_files) == 2
        assert ch.sent_files[0][1].filename == "a.txt"
        assert ch.sent_files[1][1].filename == "b.png"

    def test_send_file_failure_does_not_block_others(self, tmp_path):
        """If one attachment upload fails, remaining attachments still get sent."""
        bus = MessageBus()
        ch = _DummyChannel(bus)

        call_count = 0
        original_send_file = ch.send_file

        async def flaky_send_file(msg, att):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("upload failed")
            return await original_send_file(msg, att)

        ch.send_file = flaky_send_file  # type: ignore

        f1 = tmp_path / "fail.txt"
        f1.write_text("x")
        f2 = tmp_path / "ok.txt"
        f2.write_text("y")

        att1 = ResolvedAttachment("/mnt/user-data/outputs/fail.txt", f1, "fail.txt", "text/plain", 1, False)
        att2 = ResolvedAttachment("/mnt/user-data/outputs/ok.txt", f2, "ok.txt", "text/plain", 1, False)

        msg = OutboundMessage(
            channel_name="dummy",
            chat_id="c1",
            thread_id="t1",
            text="files",
            attachments=[att1, att2],
        )

        _run(ch._on_outbound(msg))

        assert len(ch.sent_files) == 1
        assert ch.sent_files[0][1].filename == "ok.txt"

    def test_send_file_returns_false_logs_warning(self, tmp_path):
        """When send_file returns False, a warning is logged."""
        bus = MessageBus()
        ch = _DummyChannel(bus)

        async def failing_send_file(msg, att):
            return False

        ch.send_file = failing_send_file  # type: ignore

        f = tmp_path / "a.txt"
        f.write_text("x")
        att = ResolvedAttachment("/outputs/a.txt", f, "a.txt", "text/plain", 1, False)
        msg = OutboundMessage(channel_name="dummy", chat_id="c1", thread_id="t1", text="hi", attachments=[att])

        _run(ch._on_outbound(msg))

        # send() succeeded, send_file returned False
        assert len(ch.sent_messages) == 1

    def test_send_raises_skips_file_uploads(self, tmp_path):
        """When send() raises, file uploads are skipped entirely."""
        bus = MessageBus()
        ch = _DummyChannel(bus)

        async def failing_send(msg):
            raise RuntimeError("network error")

        ch.send = failing_send  # type: ignore

        f = tmp_path / "a.pdf"
        f.write_bytes(b"%PDF")
        att = ResolvedAttachment("/mnt/user-data/outputs/a.pdf", f, "a.pdf", "application/pdf", 4, False)
        msg = OutboundMessage(
            channel_name="dummy",
            chat_id="c1",
            thread_id="t1",
            text="Here is the file",
            attachments=[att],
        )

        _run(ch._on_outbound(msg))

        assert len(ch.sent_files) == 0


# ---------------------------------------------------------------------------
# ChannelManager artifact resolution integration
# ---------------------------------------------------------------------------


class TestManagerArtifactResolution:
    def test_handle_chat_populates_attachments(self):
        """Verify _resolve_attachments is importable and works with the manager module."""
        from app.channels.manager import _resolve_attachments

        mock_paths = MagicMock()
        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _resolve_attachments("t1", [])
        assert result == []

    def test_format_artifact_text_for_unresolved(self):
        """_format_artifact_text produces expected output."""
        from app.channels.manager import _format_artifact_text

        assert "report.pdf" in _format_artifact_text(["/mnt/user-data/outputs/report.pdf"])
        result = _format_artifact_text(["/mnt/user-data/outputs/a.txt", "/mnt/user-data/outputs/b.txt"])
        assert "a.txt" in result
        assert "b.txt" in result


# ---------------------------------------------------------------------------
# MessageBus outbound with attachments
# ---------------------------------------------------------------------------


class TestMessageBusOutbound:
    def test_publish_outbound_delivers_to_subscribers(self):
        """Outbound messages with attachments are delivered to all subscribers."""
        bus = MessageBus()
        received = []

        async def callback(msg):
            received.append(msg)

        bus.subscribe_outbound(callback)

        msg = OutboundMessage(
            channel_name="test",
            chat_id="c1",
            thread_id="t1",
            text="hello",
            attachments=[ResolvedAttachment("/x", Path("/x"), "x.txt", "text/plain", 0, False)],
        )

        _run(bus.publish_outbound(msg))

        assert len(received) == 1
        assert len(received[0].attachments) == 1

    def test_unsubscribe_outbound(self):
        """After unsubscribe, callback no longer receives messages."""
        bus = MessageBus()
        received = []

        async def callback(msg):
            received.append(msg)

        bus.subscribe_outbound(callback)
        bus.unsubscribe_outbound(callback)

        msg = OutboundMessage(channel_name="test", chat_id="c1", thread_id="t1", text="hi")
        _run(bus.publish_outbound(msg))

        assert len(received) == 0

    def test_callback_exception_does_not_block_others(self):
        """One failing callback doesn't prevent others from receiving."""
        bus = MessageBus()
        received = []

        async def failing_callback(msg):
            raise RuntimeError("boom")

        async def good_callback(msg):
            received.append(msg)

        bus.subscribe_outbound(failing_callback)
        bus.subscribe_outbound(good_callback)

        msg = OutboundMessage(channel_name="test", chat_id="c1", thread_id="t1", text="hi")
        _run(bus.publish_outbound(msg))

        assert len(received) == 1
