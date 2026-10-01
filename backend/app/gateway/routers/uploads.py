"""Upload router for handling file uploads."""

import asyncio
import logging
import os
import stat
import tempfile
import time
import zipfile
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.agentplatform.code_evidence import (
    CodeEvidencePackageError,
    accept_package,
    delete_package,
)
from app.gateway.authz import require_permission, try_acquire_sandbox_for_request
from app.gateway.deps import get_config
from app.gateway.upload_ingestion import ThreadUploadIngestionService, UnsafeFilenameError, UnsafeUploadDestinationError
from deerflow.config.app_config import AppConfig
from deerflow.config.paths import get_paths
from deerflow.runtime.user_context import get_effective_user_id
from deerflow.sandbox.sandbox_provider import SandboxProvider, get_sandbox_provider
from deerflow.trace_context import ensure_trace_id
from deerflow.uploads.manager import (
    UPLOAD_STAGING_PREFIX,
    UPLOAD_STAGING_SUFFIX,
    PathTraversalError,
    UnsafeUploadPathError,
    claim_unique_filename,
    delete_file_safe,
    enrich_file_listing,
    ensure_uploads_dir,
    get_uploads_dir,
    list_files_in_dir,
    normalize_filename,
    upload_artifact_url,
    upload_virtual_path,
    validate_path_traversal,
)
from deerflow.utils.file_conversion import (
    CONVERTIBLE_EXTENSIONS,
    convert_file_to_markdown,
)
from deerflow.utils.thread_id import ThreadId

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads/{thread_id}/uploads", tags=["uploads"])

# Ingestion bridge surface (Phase-2 Slice C): the shared thread-upload
# ingestion service (``app.gateway.upload_ingestion``) resolves these
# collaborators through this module at call time, so the pre-extraction
# upload tests keep patching one namespace for both this endpoint and the
# project-shelf attach route. They are re-exported deliberately — do not
# prune them as "unused".
__all__ = [
    "UnsafeUploadPathError",
    "claim_unique_filename",
    "convert_file_to_markdown",
    "ensure_uploads_dir",
    "get_sandbox_provider",
    "normalize_filename",
    "router",
    "try_acquire_sandbox_for_request",
    "upload_artifact_url",
    "upload_virtual_path",
]

UPLOAD_CHUNK_SIZE = 8192
DEFAULT_MAX_FILES = 10
DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024
DEFAULT_MAX_TOTAL_SIZE = 100 * 1024 * 1024


@dataclass(slots=True)
class _UploadTempFile:
    file_path: Path
    temp_path: Path
    handle: BinaryIO


class UploadedFileInfo(BaseModel):
    """Metadata for one uploaded file."""

    filename: str
    size: int
    original_filename: str | None = None
    markdown_file: str | None = None
    markdown_path: str | None = None
    markdown_virtual_path: str | None = None
    markdown_artifact_url: str | None = None
    model_config = {"extra": "allow"}

    def __getitem__(self, key: str) -> object:
        """Keep direct-call compatibility with the historical dict result."""
        return getattr(self, key)


class ListedFileInfo(BaseModel):
    """Metadata returned by the upload listing endpoint."""

    filename: str
    size: int
    model_config = {"extra": "allow"}


class UploadResponse(BaseModel):
    """Response model for file upload."""

    success: bool
    files: list[UploadedFileInfo]
    message: str
    skipped_files: list[str] = Field(default_factory=list)
    code_packages: list[dict] = Field(default_factory=list)
    trace_id: str | None = None


class UploadedFilesResponse(BaseModel):
    count: int
    files: list[ListedFileInfo]


class UploadListResponse(BaseModel):
    """Compatibility schema for clients that used the original list name.

    The route returns ``UploadedFilesResponse``; retaining this public model
    keeps generated-schema consumers and older integrations source-compatible.
    """

    count: int
    files: list[UploadedFileInfo]


class UploadLimits(BaseModel):
    """Application-level upload limits exposed to clients."""

    max_files: int
    max_file_size: int
    max_total_size: int


def _make_file_sandbox_writable(file_path: os.PathLike[str] | str) -> None:
    """Ensure uploaded files remain writable when mounted into non-local sandboxes.

    In AIO sandbox mode, the gateway writes the authoritative host-side file
    first, then the sandbox runtime may rewrite the same mounted path. Granting
    world-writable access here prevents permission mismatches between the
    gateway user and the sandbox runtime user.
    """
    file_stat = os.lstat(file_path)
    if stat.S_ISLNK(file_stat.st_mode):
        logger.warning("Skipping sandbox chmod for symlinked upload path: %s", file_path)
        return

    writable_mode = stat.S_IMODE(file_stat.st_mode) | stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH | stat.S_IRGRP | stat.S_IROTH
    chmod_kwargs = {"follow_symlinks": False} if os.chmod in os.supports_follow_symlinks else {}
    os.chmod(file_path, writable_mode, **chmod_kwargs)


def _make_file_sandbox_readable(file_path: os.PathLike[str] | str) -> None:
    """Ensure uploaded files are readable by the sandbox process.

    For Docker sandboxes (AIO), the gateway writes files as root with 0o600
    permissions, then bind-mounts the host directory into the container. The
    sandbox process inside the container runs as a non-root user and cannot
    read those files without group/other read bits. This function adds
    ``S_IRGRP | S_IROTH`` so the sandbox can read the uploaded content.
    """
    file_stat = os.lstat(file_path)
    if stat.S_ISLNK(file_stat.st_mode):
        logger.warning("Skipping sandbox chmod for symlinked upload path: %s", file_path)
        return

    readable_mode = stat.S_IMODE(file_stat.st_mode) | stat.S_IRGRP | stat.S_IROTH
    chmod_kwargs = {"follow_symlinks": False} if os.chmod in os.supports_follow_symlinks else {}
    os.chmod(file_path, readable_mode, **chmod_kwargs)


def _uses_thread_data_mounts(sandbox_provider: SandboxProvider) -> bool:
    return bool(getattr(sandbox_provider, "uses_thread_data_mounts", False))


def _get_uploads_config_value(app_config: AppConfig, key: str, default: object) -> object:
    """Read a value from the uploads config, supporting dict and attribute access."""
    uploads_cfg = getattr(app_config, "uploads", None)
    if isinstance(uploads_cfg, dict):
        return uploads_cfg.get(key, default)
    return getattr(uploads_cfg, key, default)


def _get_upload_limit(app_config: AppConfig, key: str, default: int, *, legacy_key: str | None = None) -> int:
    try:
        value = _get_uploads_config_value(app_config, key, None)
        if value is None and legacy_key is not None:
            value = _get_uploads_config_value(app_config, legacy_key, None)
        if value is None:
            value = default
        limit = int(value)
        if limit <= 0:
            raise ValueError
        return limit
    except Exception:
        logger.warning("Invalid uploads.%s value; falling back to %d", key, default)
        return default


def _get_upload_limits(app_config: AppConfig) -> UploadLimits:
    return UploadLimits(
        max_files=_get_upload_limit(app_config, "max_files", DEFAULT_MAX_FILES, legacy_key="max_file_count"),
        max_file_size=_get_upload_limit(
            app_config,
            "max_file_size",
            DEFAULT_MAX_FILE_SIZE,
            legacy_key="max_single_file_size",
        ),
        max_total_size=_get_upload_limit(app_config, "max_total_size", DEFAULT_MAX_TOTAL_SIZE),
    )


def _cleanup_uploaded_paths(paths: list[os.PathLike[str] | str]) -> None:
    for path in reversed(paths):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        except Exception:
            logger.warning(
                "Failed to clean up upload path after rejected request: %s",
                path,
                exc_info=True,
            )


def _pure_destination(uploads_dir: os.PathLike[str] | str, display_filename: str) -> Path:
    """Normalize + type/confinement-check a destination name.

    The ``lstat`` rejects only a NON-REGULAR destination (a planted symlink
    must never become a write target — and following one during the
    confinement check would misreport a traversal): a stable property, unlike
    the old ``nlink > 1`` check, which raced the atomic link commit (the
    winner's link→unlink pair briefly shows ``nlink == 2`` on the name) and
    misclassified ordinary collisions as unsafe. Existence itself is decided
    by the commit's atomic link, never here.
    """
    base = Path(uploads_dir)
    file_path = base / normalize_filename(display_filename)
    try:
        st = os.lstat(file_path)
    except FileNotFoundError:
        st = None
    if st is not None and not stat.S_ISREG(st.st_mode):
        raise UnsafeUploadPathError(f"Upload destination is not a regular file: {display_filename}")
    validate_path_traversal(file_path, base)
    return file_path


def _prepare_upload_destination(uploads_dir: os.PathLike[str] | str, display_filename: str) -> _UploadTempFile:
    uploads_dir_path = Path(uploads_dir)
    file_path = _pure_destination(uploads_dir_path, display_filename)
    temp_fd, temp_path_str = tempfile.mkstemp(prefix=UPLOAD_STAGING_PREFIX, suffix=UPLOAD_STAGING_SUFFIX, dir=uploads_dir_path)
    temp_path = Path(temp_path_str)
    try:
        handle = os.fdopen(temp_fd, "wb")
    except Exception:
        try:
            os.close(temp_fd)
        except OSError:
            pass
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise
    return _UploadTempFile(file_path=file_path, temp_path=temp_path, handle=handle)


def _link_staged_no_overwrite(staged_path: Path, uploads_dir: os.PathLike[str] | str, display_filename: str) -> Path:
    """Worker: publish *staged_path* under *display_filename* atomically, never overwriting.

    The ``os.link`` itself is the whole no-overwrite guard: it fails with
    :class:`FileExistsError` when the name exists as ANYTHING — a regular
    file collision (the caller retries with the next suffix), a symlink, a
    hardlink — and a link never writes through an existing file. The
    destination is NOT lstat-validated beforehand: the winner's link→unlink
    pair briefly shows ``nlink == 2`` on the name, so a pre-link multi-link
    check misclassifies an ordinary collision as unsafe (observed as
    intermittent 500s on concurrent same-name uploads). Classification
    happens AFTER the atomic failure: an existing non-regular file (a planted
    symlink — symlinks are excluded from the seeded listing, so one could
    only come from outside) stays an unsafe destination; anything else is a
    plain collision to retry. Any other failure removes the staged file and
    propagates; success unlinks it. Staging and destination are co-located in
    the uploads dir, so the hard link is always same-filesystem.
    """
    file_path = _pure_destination(uploads_dir, display_filename)
    try:
        os.link(staged_path, file_path)
    except FileExistsError:
        try:
            if not stat.S_ISREG(os.lstat(file_path).st_mode):
                raise UnsafeUploadPathError(f"Upload destination is not a regular file: {display_filename}") from None
        except FileNotFoundError:
            pass  # The winner vanished between link and lstat — plain retry.
        raise
    except Exception:
        try:
            os.unlink(staged_path)
        except FileNotFoundError:
            pass
        raise
    os.unlink(staged_path)
    return file_path


def _commit_upload_temp_no_overwrite(upload_temp: _UploadTempFile, uploads_dir: os.PathLike[str] | str, display_filename: str) -> Path:
    """Worker: close the staged handle and publish the ``.part`` atomically via ``os.link``.

    Same no-overwrite contract as :func:`_link_staged_no_overwrite`:
    :class:`FileExistsError` leaves the staged part in place for a
    next-suffix retry (the handle's second ``close`` is idempotent); any
    other failure removes it.
    """
    upload_temp.handle.close()
    return _link_staged_no_overwrite(upload_temp.temp_path, uploads_dir, display_filename)


def _write_upload_chunk(upload_temp: _UploadTempFile, chunk: bytes) -> None:
    upload_temp.handle.write(chunk)


def _abort_upload_temp(upload_temp: _UploadTempFile) -> None:
    try:
        upload_temp.handle.close()
    finally:
        try:
            os.unlink(upload_temp.temp_path)
        except FileNotFoundError:
            pass


def _make_uploaded_paths_sandbox_readable(paths: list[os.PathLike[str] | str]) -> None:
    for file_path in paths:
        _make_file_sandbox_readable(file_path)


def _sync_upload_to_sandbox(sandbox, file_path: os.PathLike[str] | str, virtual_path: str) -> None:
    _make_file_sandbox_writable(file_path)
    sandbox.update_file(virtual_path, Path(file_path).read_bytes())


def _list_uploaded_files_for_thread(thread_id: str, user_id: str) -> dict:
    uploads_dir = get_uploads_dir(thread_id, user_id=user_id)
    result = list_files_in_dir(uploads_dir)
    enrich_file_listing(result, thread_id)

    sandbox_uploads = get_paths().sandbox_uploads_dir(thread_id, user_id=user_id)
    for f in result["files"]:
        f["path"] = str(sandbox_uploads / f["filename"])
    return result


def _delete_uploaded_file_for_thread(thread_id: str, filename: str, user_id: str) -> dict:
    uploads_dir = get_uploads_dir(thread_id, user_id=user_id)
    return delete_file_safe(uploads_dir, filename, convertible_extensions=CONVERTIBLE_EXTENSIONS)


async def _stream_upload_file(file: UploadFile) -> AsyncIterator[bytes]:
    """Adapt an ``UploadFile`` to the ingestion service's chunk stream."""
    while chunk := await file.read(UPLOAD_CHUNK_SIZE):
        yield chunk


def _auto_convert_documents_enabled(app_config: AppConfig) -> bool:
    """Return whether automatic host-side document conversion is enabled.

    The secure default is disabled unless an operator explicitly opts in via
    uploads.auto_convert_documents in config.yaml.
    """
    try:
        raw = _get_uploads_config_value(app_config, "auto_convert_documents", False)
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        return bool(raw)
    except Exception:
        return False


@router.post("", response_model=UploadResponse)
@require_permission("threads", "write", owner_check=True, require_existing=False)
async def upload_files(
    thread_id: ThreadId,
    request: Request,
    files: list[UploadFile] = File(...),
    config: AppConfig = Depends(get_config),
) -> UploadResponse:
    """Upload multiple files to a thread's uploads directory.

    Thin adapter over the shared thread-upload ingestion service
    (``app.gateway.upload_ingestion``, Phase-2 spec §7.3 item 3), which owns
    staging, filename claiming, size checks, conversion, permissions and
    sandbox sync. When the sandbox provider is not thread-mounted, uploaded
    files are also synced into the thread's sandbox. Under
    ``authorization.enabled``, a caller denied ``sandbox:execute`` skips that
    sync (the upload itself still succeeds — files stay in the uploads dir;
    a sandbox-denied agent cannot consume them anyway).

    Local extensions layered on the shared pipeline: ``.zip`` parts are also
    ingested as thread-private code-evidence packages, the response carries
    ``code_packages``/``trace_id``, and each file's ``path`` is reported
    sandbox-relative (matching the list endpoint's contract).
    """
    upload_started = time.perf_counter()
    trace_id = ensure_trace_id()
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    limits = _get_upload_limits(config)
    if len(files) > limits.max_files:
        raise HTTPException(status_code=413, detail=f"Too many files: maximum is {limits.max_files}")

    # Setup runs INSIDE the cleanup scope: open() can acquire the sandbox
    # request lease and then raise (e.g. the acquired lease yields no
    # sandbox), and the finally's aclose() is what releases that partially
    # acquired holder.
    service = ThreadUploadIngestionService(request=request, thread_id=thread_id, user_id=get_effective_user_id(), app_config=config)
    uploaded_files = []
    skipped_files = []
    code_packages = []
    created_package_ids: list[str] = []
    sandbox_uploads = await asyncio.to_thread(
        get_paths().sandbox_uploads_dir,
        thread_id,
        user_id=get_effective_user_id(),
    )
    try:
        try:
            await service.open()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        for file in files:
            if not file.filename:
                continue
            try:
                file_info = await service.ingest_chunks(_stream_upload_file(file), display_name=file.filename)
            except UnsafeFilenameError:
                logger.warning(f"Skipping file with unsafe filename: {file.filename!r}")
                continue
            except UnsafeUploadDestinationError as e:
                logger.warning("Skipping upload with unsafe destination %s: %s", file.filename, e)
                skipped_files.append(e.filename)
                continue
            except HTTPException:
                await service.cleanup_written()
                for package_id in created_package_ids:
                    try:
                        delete_package(thread_id, package_id)
                    except FileNotFoundError:
                        pass
                raise
            except Exception as e:
                logger.error(f"Failed to upload {file.filename}: {e}")
                await service.cleanup_written()
                for package_id in created_package_ids:
                    try:
                        delete_package(thread_id, package_id)
                    except FileNotFoundError:
                        pass
                raise HTTPException(status_code=500, detail=f"Failed to upload {file.filename}: {str(e)}")

            # Local wire contract: the sandbox-relative path, not the host
            # uploads dir (the list endpoint below reports the same shape).
            file_info["path"] = str(sandbox_uploads / file_info["filename"])

            # Local code-evidence ingestion: after the ordinary bytes land,
            # a .zip part is validated and archived as a thread-private
            # evidence package (rollback deletes every package this request
            # created if a later part fails).
            if str(file.filename).lower().endswith(".zip"):
                file.file.seek(0)
                try:
                    manifest, _root = await asyncio.to_thread(
                        accept_package,
                        file.file,
                        thread_id=thread_id,
                        original_filename=file_info["filename"],
                    )
                except CodeEvidencePackageError as exc:
                    await service.cleanup_written()
                    for package_id in created_package_ids:
                        try:
                            delete_package(thread_id, package_id)
                        except FileNotFoundError:
                            pass
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                except (OSError, zipfile.BadZipFile) as exc:
                    await service.cleanup_written()
                    for package_id in created_package_ids:
                        try:
                            delete_package(thread_id, package_id)
                        except FileNotFoundError:
                            pass
                    raise HTTPException(status_code=400, detail=f"Invalid code evidence package: {exc}") from exc
                finally:
                    file.file.seek(0, 2)
                code_packages.append(manifest.as_dict())
                created_package_ids.append(manifest.package_id)

            uploaded_files.append(file_info)

        await service.finalize()

        logger.info(
            "first_token_timing trace_id=%s stage=upload thread_id=%s attachment_count=%d attachment_total_bytes=%d upload_ms=%.1f",
            trace_id,
            thread_id,
            len(uploaded_files),
            sum(int(item.get("size") or 0) for item in uploaded_files),
            (time.perf_counter() - upload_started) * 1000,
        )

        message = f"Successfully uploaded {len(uploaded_files)} file(s)"
        if skipped_files:
            message += f"; skipped {len(skipped_files)} unsafe file(s)"

        return UploadResponse(
            success=not skipped_files,
            files=uploaded_files,
            message=message,
            skipped_files=skipped_files,
            code_packages=code_packages,
            trace_id=trace_id,
        )
    finally:
        await service.aclose()


@router.get("/limits", response_model=UploadLimits)
@require_permission("threads", "read", owner_check=True)
async def get_upload_limits(
    thread_id: ThreadId,
    request: Request,
    config: AppConfig = Depends(get_config),
) -> UploadLimits:
    """Return upload limits used by the gateway for this thread."""
    return _get_upload_limits(config)


@router.get("/list", response_model=UploadedFilesResponse)
@require_permission("threads", "read", owner_check=True)
async def list_uploaded_files(thread_id: ThreadId, request: Request) -> UploadedFilesResponse:
    """List all files in a thread's uploads directory."""
    try:
        uploads_dir = await asyncio.to_thread(get_uploads_dir, thread_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result = await asyncio.to_thread(list_files_in_dir, uploads_dir)
    await asyncio.to_thread(enrich_file_listing, result, thread_id)

    # Gateway additionally includes the sandbox-relative path.
    sandbox_uploads = await asyncio.to_thread(
        get_paths().sandbox_uploads_dir,
        thread_id,
        user_id=get_effective_user_id(),
    )
    for f in result["files"]:
        f["path"] = str(sandbox_uploads / f["filename"])

    return UploadedFilesResponse(**result)


@router.delete("/{filename}")
@require_permission("threads", "delete", owner_check=True, require_existing=True)
async def delete_uploaded_file(thread_id: ThreadId, filename: str, request: Request) -> dict:
    """Delete a file from a thread's uploads directory."""
    try:
        uploads_dir = await asyncio.to_thread(get_uploads_dir, thread_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        return await asyncio.to_thread(
            delete_file_safe,
            uploads_dir,
            filename,
            convertible_extensions=CONVERTIBLE_EXTENSIONS,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    except PathTraversalError:
        raise HTTPException(status_code=400, detail="Invalid path")
    except Exception as e:
        logger.error(f"Failed to delete {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete {filename}: {str(e)}")
