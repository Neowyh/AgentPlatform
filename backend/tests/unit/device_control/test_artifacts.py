import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from app.device_control.artifacts import ArtifactStoreError, DeviceArtifactStore


async def _chunks(*values: bytes):
    for value in values:
        yield value


def _grant(store: DeviceArtifactStore, **overrides):
    values = {
        "device_id": "device-1",
        "session_id": "session-1",
        "run_id": "run-1",
        "task_id": "task-1",
        "thread_id": "thread-1",
        "filename": "result.txt",
        "expires_at": datetime.now(UTC) + timedelta(minutes=1),
    }
    values.update(overrides)
    return store.issue_grant(**values)


@pytest.mark.asyncio
async def test_upload_is_streamed_hash_checked_and_single_use(tmp_path):
    store = DeviceArtifactStore(tmp_path)
    content = b"hello world"
    grant = _grant(store, expected_sha256=hashlib.sha256(content).hexdigest())
    handle, size, digest = await store.upload(grant.token, _chunks(b"hello ", b"world"))
    assert handle == f"local://{digest}/result.txt"
    assert size == len(content)
    with pytest.raises(ArtifactStoreError, match="invalid"):
        await store.upload(grant.token, _chunks(content))


@pytest.mark.asyncio
async def test_upload_rejects_expiry_hash_and_size(tmp_path):
    store = DeviceArtifactStore(tmp_path)
    expired = _grant(store, expires_at=datetime.now(UTC) - timedelta(seconds=1))
    with pytest.raises(ArtifactStoreError) as expired_error:
        await store.upload(expired.token, _chunks(b"x"))
    assert expired_error.value.code == "GRANT_EXPIRED"

    mismatch = _grant(store, expected_sha256="0" * 64)
    with pytest.raises(ArtifactStoreError) as hash_error:
        await store.upload(mismatch.token, _chunks(b"x"))
    assert hash_error.value.code == "HASH_MISMATCH"

    limited = _grant(store, max_bytes=1)
    with pytest.raises(ArtifactStoreError) as size_error:
        await store.upload(limited.token, _chunks(b"xx"))
    assert size_error.value.code == "SIZE_LIMIT"


def test_grant_rejects_path_traversal(tmp_path):
    with pytest.raises(ArtifactStoreError) as error:
        _grant(DeviceArtifactStore(tmp_path), filename="../secret.txt")
    assert error.value.code == "INVALID_FILENAME"
