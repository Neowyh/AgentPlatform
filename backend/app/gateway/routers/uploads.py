"""Upload router for handling file uploads."""

import asyncio
import inspect
import logging
import os
import stat
import tempfile
import time
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.agentplatform.code_evidence import (
    CodeEvidencePackageError,
    accept_package,
    delete_package,
)
from app.gateway.authz import require_permission
from app.gateway.deps import get_config
from deerflow.config.app_config import AppConfig
from deerflow.config.paths import get_paths
from deerflow.runtime.user_context import get_effective_user_id
from deerflow.sandbox.sandbox_provider import SandboxProvider, get_sandbox_provider
from deerflow.trace_context import ensure_trace_id
from deerflow.uploads.manager import (
    PathTraversalError,
    UnsafeUploadPathError,
    claim_unique_filename,
    delete_file_safe,
    enrich_file_listing,
    ensure_uploads_dir,
    get_uploads_dir,
    list_files_in_dir,
    normalize_filename,
    open_upload_file_no_symlink,
    upload_artifact_url,
    upload_virtual_path,
    validate_upload_destination,
)
from deerflow.utils.file_conversion import (
    CONVERTIBLE_EXTENSIONS,
    convert_file_to_markdown,
)
from deerflow.utils.thread_id import ThreadId

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads/{thread_id}/uploads", tags=["uploads"])

UPLOAD_CHUNK_SIZE = 8192
DEFAULT_MAX_FILES = 10
DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024
DEFAULT_MAX_TOTAL_SIZE = 100 * 1024 * 1024
SANDBOX_SYNC_CONCURRENCY = 4


async def _acquire_upload_sandbox(
    provider: SandboxProvider,
    thread_id: str,
    user_id: str,
    *,
    request: Request,
    app_config: AppConfig,
):
    """Acquire an upload sandbox while tolerating synchronous provider doubles.

    Production providers implement ``acquire_async``. Small integration
    fakes often only implement the historical synchronous ``acquire`` method;
    accepting that shape keeps the router boundary testable without weakening
    the real lease path.
    """
    from deerflow.sandbox.lease import SandboxClientLease

    acquire_async = getattr(provider, "acquire_async", None)
    if inspect.iscoroutinefunction(acquire_async):
        from app.gateway.authz import try_acquire_sandbox_for_request

        return await try_acquire_sandbox_for_request(
            request,
            provider,
            thread_id,
            user_id=user_id,
            app_config=app_config,
            owner_prefix="gateway:upload",
            release_on_last=False,
        )
    acquire = getattr(provider, "acquire", None)
    if not callable(acquire):
        raise RuntimeError("Sandbox provider does not expose an acquire method")
    sandbox_id = acquire(thread_id)
    if inspect.isawaitable(sandbox_id):
        sandbox_id = await sandbox_id
    return SandboxClientLease(
        sandbox=provider.get(sandbox_id),
        sandbox_id=sandbox_id,
        owner_id=None,
        provider=provider,
    )


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
        logger.warning(
            "Skipping sandbox chmod for symlinked upload path: %s", file_path
        )
        return

    writable_mode = (
        stat.S_IMODE(file_stat.st_mode)
        | stat.S_IWUSR
        | stat.S_IWGRP
        | stat.S_IWOTH
        | stat.S_IRGRP
        | stat.S_IROTH
    )
    chmod_kwargs = (
        {"follow_symlinks": False} if os.chmod in os.supports_follow_symlinks else {}
    )
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
        logger.warning(
            "Skipping sandbox chmod for symlinked upload path: %s", file_path
        )
        return

    readable_mode = stat.S_IMODE(file_stat.st_mode) | stat.S_IRGRP | stat.S_IROTH
    chmod_kwargs = (
        {"follow_symlinks": False} if os.chmod in os.supports_follow_symlinks else {}
    )
    os.chmod(file_path, readable_mode, **chmod_kwargs)


def _uses_thread_data_mounts(sandbox_provider: SandboxProvider) -> bool:
    return bool(getattr(sandbox_provider, "uses_thread_data_mounts", False))


def _get_uploads_config_value(
    app_config: AppConfig, key: str, default: object
) -> object:
    """Read a value from the uploads config, supporting dict and attribute access."""
    uploads_cfg = getattr(app_config, "uploads", None)
    if isinstance(uploads_cfg, dict):
        return uploads_cfg.get(key, default)
    return getattr(uploads_cfg, key, default)


def _get_upload_limit(
    app_config: AppConfig, key: str, default: int, *, legacy_key: str | None = None
) -> int:
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
        max_files=_get_upload_limit(
            app_config, "max_files", DEFAULT_MAX_FILES, legacy_key="max_file_count"
        ),
        max_file_size=_get_upload_limit(
            app_config,
            "max_file_size",
            DEFAULT_MAX_FILE_SIZE,
            legacy_key="max_single_file_size",
        ),
        max_total_size=_get_upload_limit(
            app_config, "max_total_size", DEFAULT_MAX_TOTAL_SIZE
        ),
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


async def _sync_upload_to_sandbox(
    sandbox: object,
    file_path: Path,
    virtual_path: str,
    semaphore: asyncio.Semaphore,
) -> None:
    """Copy one upload to a remote sandbox without blocking other uploads."""
    async with semaphore:
        await asyncio.to_thread(_make_file_sandbox_writable, file_path)
        content = await asyncio.to_thread(file_path.read_bytes)
        await asyncio.to_thread(sandbox.update_file, virtual_path, content)


async def _write_upload_file_with_limits(
    file: UploadFile,
    *,
    uploads_dir: os.PathLike[str] | str,
    display_filename: str,
    max_single_file_size: int,
    max_total_size: int,
    total_size: int,
) -> tuple[os.PathLike[str] | str, int, int]:
    file_size = 0
    try:
        destination, staging_name, fh = await asyncio.to_thread(
            _prepare_upload_staging, uploads_dir, display_filename
        )
    except Exception:
        raise
    try:
        while chunk := await file.read(UPLOAD_CHUNK_SIZE):
            file_size += len(chunk)
            total_size += len(chunk)
            if file_size > max_single_file_size:
                raise HTTPException(
                    status_code=413, detail=f"File too large: {display_filename}"
                )
            if total_size > max_total_size:
                raise HTTPException(
                    status_code=413, detail="Total upload size too large"
                )
            await asyncio.to_thread(fh.write, chunk)
    except Exception:
        await asyncio.to_thread(fh.close)
        try:
            await asyncio.to_thread(os.unlink, staging_name)
        except FileNotFoundError:
            pass
        raise
    else:
        await asyncio.to_thread(fh.close)
        await asyncio.to_thread(os.replace, staging_name, destination)
    return destination, file_size, total_size


def _prepare_upload_staging(
    uploads_dir: os.PathLike[str] | str,
    display_filename: str,
) -> tuple[os.PathLike[str] | str, str, object]:
    """Validate and open a staging file without blocking the event loop."""
    destination = validate_upload_destination(Path(uploads_dir), display_filename)
    staging_fd, staging_name = tempfile.mkstemp(prefix=".upload-", dir=str(uploads_dir))
    os.close(staging_fd)
    try:
        # Exercise the shared no-symlink boundary before streaming.
        _probe_path, probe_fh = open_upload_file_no_symlink(
            Path(uploads_dir), Path(staging_name).name
        )
        probe_fh.close()
        fh = open(staging_name, "wb")
    except Exception:
        try:
            os.unlink(staging_name)
        except FileNotFoundError:
            pass
        raise
    return destination, staging_name, fh


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
    """Upload multiple files to a thread's uploads directory."""
    upload_started = time.perf_counter()
    trace_id = ensure_trace_id()
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    limits = _get_upload_limits(config)
    if len(files) > limits.max_files:
        raise HTTPException(
            status_code=413, detail=f"Too many files: maximum is {limits.max_files}"
        )

    try:
        uploads_dir = await asyncio.to_thread(ensure_uploads_dir, thread_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sandbox_uploads = await asyncio.to_thread(
        get_paths().sandbox_uploads_dir,
        thread_id,
        user_id=get_effective_user_id(),
    )
    uploaded_files = []
    written_paths = []
    sandbox_sync_targets = []
    skipped_files = []
    code_packages = []
    created_package_ids: list[str] = []
    file_timings: list[dict[str, object]] = []
    total_size = 0
    # Track filenames within this request so duplicate form parts do not
    # silently truncate each other. Existing uploads keep the historical
    # overwrite behavior for a single replacement upload.
    seen_filenames: set[str] = set()

    sandbox_provider = get_sandbox_provider()
    sync_to_sandbox = not _uses_thread_data_mounts(sandbox_provider)
    sandbox = None
    sandbox_lease = None
    sandbox_prepare_started = time.perf_counter()
    if sync_to_sandbox:
        sandbox_lease = await _acquire_upload_sandbox(
            sandbox_provider,
            thread_id,
            get_effective_user_id(),
            request=request,
            app_config=config,
        )
        sandbox = sandbox_lease.sandbox
        if getattr(sandbox_lease, "denied", False):
            sandbox_lease = None
            sync_to_sandbox = False
        if sandbox is None:
            if sandbox_lease is not None:
                await sandbox_lease.release()
            raise HTTPException(status_code=500, detail="Failed to acquire sandbox")
    sandbox_prepare_ms = (time.perf_counter() - sandbox_prepare_started) * 1000
    auto_convert_documents = _auto_convert_documents_enabled(config)

    for file in files:
        if not file.filename:
            continue

        file_started = time.perf_counter()
        try:
            original_filename = normalize_filename(file.filename)
            safe_filename = claim_unique_filename(original_filename, seen_filenames)
        except ValueError:
            logger.warning(f"Skipping file with unsafe filename: {file.filename!r}")
            continue

        try:
            file_path, file_size, total_size = await _write_upload_file_with_limits(
                file,
                uploads_dir=uploads_dir,
                display_filename=safe_filename,
                max_single_file_size=limits.max_file_size,
                max_total_size=limits.max_total_size,
                total_size=total_size,
            )
            written_paths.append(file_path)

            if original_filename.lower().endswith(".zip"):
                file.file.seek(0)
                try:
                    manifest, _root = await asyncio.to_thread(
                        accept_package,
                        file.file,
                        thread_id=thread_id,
                        original_filename=original_filename,
                    )
                except CodeEvidencePackageError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                except (OSError, zipfile.BadZipFile) as exc:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid code evidence package: {exc}"
                    ) from exc
                finally:
                    file.file.seek(0, 2)
                code_packages.append(manifest.as_dict())
                created_package_ids.append(manifest.package_id)

            virtual_path = upload_virtual_path(safe_filename)

            if sync_to_sandbox:
                sandbox_sync_targets.append((file_path, virtual_path))

            file_info = {
                "filename": safe_filename,
                "size": file_size,
                "path": str(sandbox_uploads / safe_filename),
                "virtual_path": virtual_path,
                "artifact_url": upload_artifact_url(thread_id, safe_filename),
            }
            if safe_filename != original_filename:
                file_info["original_filename"] = original_filename

            logger.info(
                f"Saved file: {safe_filename} ({file_size} bytes) to {file_info['path']}"
            )

            file_ext = file_path.suffix.lower()
            convert_started = time.perf_counter()
            if auto_convert_documents and file_ext in CONVERTIBLE_EXTENSIONS:
                # Reserve the companion name in the same request namespace as
                # user uploads so conversion cannot overwrite a sibling file.
                companion_name = claim_unique_filename(
                    f"{file_path.stem}.md", seen_filenames
                )
                try:
                    md_path = await convert_file_to_markdown(
                        file_path, output_path=uploads_dir / companion_name
                    )
                except TypeError as exc:
                    # Keep compatibility with older conversion adapters that
                    # only accept the source path. Do not hide other TypeErrors.
                    if "output_path" not in str(exc):
                        raise
                    md_path = await convert_file_to_markdown(file_path)
                if md_path is None:
                    seen_filenames.discard(companion_name)
                if md_path:
                    written_paths.append(md_path)
                    md_virtual_path = upload_virtual_path(md_path.name)

                    if sync_to_sandbox:
                        sandbox_sync_targets.append((md_path, md_virtual_path))

                    file_info["markdown_file"] = md_path.name
                    file_info["markdown_path"] = str(sandbox_uploads / md_path.name)
                    file_info["markdown_virtual_path"] = md_virtual_path
                    file_info["markdown_artifact_url"] = upload_artifact_url(
                        thread_id, md_path.name
                    )

            uploaded_files.append(file_info)
            file_timings.append(
                {
                    "filename": safe_filename,
                    "size": file_size,
                    "type": file_ext or "<none>",
                    "convert_ms": round(
                        (time.perf_counter() - convert_started) * 1000, 1
                    ),
                    "total_ms": round((time.perf_counter() - file_started) * 1000, 1),
                }
            )

        except HTTPException as e:
            _cleanup_uploaded_paths(written_paths)
            for package_id in created_package_ids:
                try:
                    delete_package(thread_id, package_id)
                except FileNotFoundError:
                    pass
            if sandbox_lease is not None:
                await sandbox_lease.release()
            raise e
        except UnsafeUploadPathError as e:
            logger.warning(
                "Skipping upload with unsafe destination %s: %s", file.filename, e
            )
            skipped_files.append(safe_filename)
            continue
        except Exception as e:
            logger.error(f"Failed to upload {file.filename}: {e}")
            _cleanup_uploaded_paths(written_paths)
            for package_id in created_package_ids:
                try:
                    delete_package(thread_id, package_id)
                except FileNotFoundError:
                    pass
            if sandbox_lease is not None:
                await sandbox_lease.release()
            raise HTTPException(
                status_code=500, detail=f"Failed to upload {file.filename}: {str(e)}"
            )

    # Uploaded files are created with 0o600 permissions (owner read/write only).
    # In Docker sandbox deployments the gateway writes as root but the sandbox
    # process runs as a non-root user (typically UID 1000).  Without group/other
    # read bits the sandbox cannot access the files — whether the uploads
    # directory is bind-mounted into the container or synced via
    # sandbox.update_file.  Always add group/other read bits so every sandbox
    # configuration can read the uploaded content.
    for file_path in written_paths:
        _make_file_sandbox_readable(file_path)

    sandbox_sync_started = time.perf_counter()
    try:
        if sync_to_sandbox:
            semaphore = asyncio.Semaphore(SANDBOX_SYNC_CONCURRENCY)
            sync_results = await asyncio.gather(
                *(
                    _sync_upload_to_sandbox(sandbox, file_path, virtual_path, semaphore)
                    for file_path, virtual_path in sandbox_sync_targets
                ),
                return_exceptions=True,
            )
            for result in sync_results:
                if isinstance(result, BaseException):
                    raise result
    finally:
        if sandbox_lease is not None:
            await sandbox_lease.release()

    logger.info(
        "first_token_timing trace_id=%s stage=upload thread_id=%s attachment_count=%d attachment_total_bytes=%d attachment_types=%s upload_ms=%.1f convert_ms=%.1f sandbox_prepare_ms=%.1f sandbox_sync_ms=%.1f file_timings=%s",
        trace_id,
        thread_id,
        len(uploaded_files),
        sum(int(item["size"]) for item in file_timings),
        sorted({str(item["type"]) for item in file_timings}),
        (time.perf_counter() - upload_started) * 1000,
        sum(float(item["convert_ms"]) for item in file_timings),
        sandbox_prepare_ms,
        (time.perf_counter() - sandbox_sync_started) * 1000 if sync_to_sandbox else 0.0,
        file_timings,
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
async def list_uploaded_files(
    thread_id: ThreadId, request: Request
) -> UploadedFilesResponse:
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
async def delete_uploaded_file(
    thread_id: ThreadId, filename: str, request: Request
) -> dict:
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
        raise HTTPException(
            status_code=500, detail=f"Failed to delete {filename}: {str(e)}"
        )
