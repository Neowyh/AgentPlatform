"""Real RAGFlow Gate4 acceptance: upload, index, search, delete, and no-hit."""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import pytest

from deerflow.community.ragflow import tools as ragflow_tools

pytestmark = pytest.mark.live

_skip_reason = None
if os.environ.get("CI"):
    _skip_reason = "Live tests skipped in CI"
elif os.environ.get("DEER_FLOW_RUN_LIVE_TESTS") != "1":
    _skip_reason = "Set DEER_FLOW_RUN_LIVE_TESTS=1 to run the real RAGFlow Gate4 acceptance"
elif not Path(__file__).resolve().parents[2].joinpath("config.yaml").exists():
    _skip_reason = "No config.yaml found — real RAGFlow settings are required"
elif not os.environ.get("RAGFLOW_GATE4_DATASET_ID"):
    _skip_reason = "Set RAGFLOW_GATE4_DATASET_ID to an isolated RAGFlow dataset"

if _skip_reason:
    pytest.skip(_skip_reason, allow_module_level=True)


async def _wait_for(predicate, *, expected: bool, timeout: float = 180) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if await predicate() is expected:
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Timed out waiting for the RAGFlow Gate4 state")
        await asyncio.sleep(2)


@pytest.mark.asyncio
async def test_ragflow_gate4_provider_lifecycle() -> None:
    settings, error = ragflow_tools._settings_or_error()
    assert settings is not None, error
    client = ragflow_tools._build_client(settings)
    dataset_id = os.environ["RAGFLOW_GATE4_DATASET_ID"]
    marker = f"knowledge-gate4-{uuid.uuid4().hex}"

    document_id = await client.upload_document(
        dataset_id,
        filename=f"{marker}.txt",
        content=f"Real Gate4 acceptance marker: {marker}".encode(),
        mime_type="text/plain",
    )
    try:
        await client.parse_document(dataset_id, document_id)

        async def is_ready() -> bool:
            return await client.get_document_status(dataset_id=dataset_id, document_id=document_id) == "ready"

        await _wait_for(is_ready, expected=True)

        async def is_searchable() -> bool:
            result = await client.retrieve(marker, dataset_ids=[dataset_id], page_size=8)
            return any(marker in str(chunk) for chunk in result.get("chunks", []))

        await _wait_for(is_searchable, expected=True)
    finally:
        await client.delete_document(dataset_id, document_id)

    async def is_absent() -> bool:
        result = await client.retrieve(marker, dataset_ids=[dataset_id], page_size=8)
        return not any(marker in str(chunk) for chunk in result.get("chunks", []))

    await _wait_for(is_absent, expected=True)
