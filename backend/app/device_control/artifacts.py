"""Device-task artifact grants and bounded, streaming server storage."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import AsyncIterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


class ArtifactStoreError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class ArtifactUploadGrant:
    device_id: str
    session_id: str
    run_id: str
    task_id: str
    thread_id: str
    filename: str
    expires_at: datetime
    expected_sha256: str | None = None
    max_bytes: int = 10 * 1024 * 1024
    token: str = ""
    consumed: bool = False

    def __post_init__(self) -> None:
        self.token = self.token or secrets.token_urlsafe(32)


class DeviceArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._grants: dict[str, ArtifactUploadGrant] = {}

    def issue_grant(self, **kwargs) -> ArtifactUploadGrant:
        filename = Path(str(kwargs.get("filename", ""))).name
        if not filename or filename != kwargs.get("filename"):
            raise ArtifactStoreError("INVALID_FILENAME", "artifact filename is invalid")
        grant = ArtifactUploadGrant(filename=filename, **{k: v for k, v in kwargs.items() if k != "filename"})
        self._grants[grant.token] = grant
        return grant

    async def upload(self, token: str, chunks: AsyncIterable[bytes]) -> tuple[str, int, str]:
        grant = self._grants.get(token)
        if grant is None or grant.consumed:
            raise ArtifactStoreError("GRANT_INVALID", "artifact upload grant is invalid")
        if grant.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC):
            raise ArtifactStoreError("GRANT_EXPIRED", "artifact upload grant expired")
        target_dir = self.root / grant.thread_id / "outputs"
        target_dir.mkdir(parents=True, exist_ok=True)
        temporary = target_dir / f".upload-{secrets.token_hex(12)}"
        digest = hashlib.sha256()
        size = 0
        try:
            with temporary.open("wb") as output:
                async for chunk in chunks:
                    if not isinstance(chunk, bytes):
                        raise ArtifactStoreError("INVALID_CHUNK", "artifact upload chunk is invalid")
                    size += len(chunk)
                    if size > grant.max_bytes:
                        raise ArtifactStoreError("SIZE_LIMIT", "artifact exceeds configured size limit")
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
            actual_hash = digest.hexdigest()
            if grant.expected_sha256 is not None and actual_hash != grant.expected_sha256:
                raise ArtifactStoreError("HASH_MISMATCH", "artifact content hash does not match grant")
            destination = target_dir / f"{actual_hash}-{grant.filename}"
            if destination.exists() and destination.read_bytes() != temporary.read_bytes():
                raise ArtifactStoreError("CONTENT_CONFLICT", "artifact handle content conflict")
            temporary.replace(destination)
            grant.consumed = True
            return f"local://{actual_hash}/{grant.filename}", size, actual_hash
        finally:
            temporary.unlink(missing_ok=True)
