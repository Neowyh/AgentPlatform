"""Gate 8 live acceptance against an isolated RAGFlow dataset."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

import pytest

from deerflow.community.ragflow import tools as ragflow_tools
from tests.gate8_acceptance import validate_gate8_artifact

pytestmark = pytest.mark.live


def _skip_reason() -> str | None:
    if os.environ.get("CI"):
        return "Live tests are not run in CI"
    if os.environ.get("DEER_FLOW_RUN_LIVE_TESTS") != "1":
        return "Set DEER_FLOW_RUN_LIVE_TESTS=1 to run Gate 8 against RAGFlow"
    if not Path(__file__).resolve().parents[2].joinpath("config.yaml").exists():
        return "No config.yaml found — real RAGFlow settings are required"
    if not os.environ.get("RAGFLOW_GATE8_DATASET_ID"):
        return "Set RAGFLOW_GATE8_DATASET_ID to an isolated RAGFlow dataset"
    return None


if _skip_reason():
    pytest.skip(_skip_reason(), allow_module_level=True)


@pytest.mark.asyncio
async def test_gate8_real_provider_probe_is_searchable_and_distinguishes_zero_hit() -> None:
    settings, error = ragflow_tools._settings_or_error()
    assert settings is not None, error
    client = ragflow_tools._build_client(settings)
    dataset_id = os.environ["RAGFLOW_GATE8_DATASET_ID"]
    marker = f"knowledge-gate8-{uuid.uuid4().hex}"
    document_id = await client.upload_document(
        dataset_id,
        filename=f"{marker}.txt",
        content=f"Gate 8 canonical document marker: {marker}".encode(),
        mime_type="text/plain",
    )
    try:
        await client.parse_document(dataset_id, document_id)
        await _wait_for(lambda: _document_ready(client, dataset_id, document_id))
        await _wait_for(lambda: _marker_searchable(client, dataset_id, marker))
        hit = await client.retrieve(marker, dataset_ids=[dataset_id], page_size=8)
        miss = await client.retrieve(f"unmatched-{marker}", dataset_ids=[dataset_id], page_size=8)
        assert any(marker in str(chunk) for chunk in hit.get("chunks", []))
        assert not any(marker in str(chunk) for chunk in miss.get("chunks", []))
    finally:
        await client.delete_document(dataset_id, document_id)


def test_gate8_real_artifact_is_required_for_a_passed_acceptance() -> None:
    path = os.environ.get("RAGFLOW_GATE8_ARTIFACT_JSON")
    if not path:
        pytest.skip("Set RAGFLOW_GATE8_ARTIFACT_JSON to the recorded Gate 8 artifact")
    validate_gate8_artifact(json.loads(Path(path).read_text(encoding="utf-8")))


async def _wait_for(predicate, *, timeout: float = 180) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if await predicate():
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Timed out waiting for the Gate 8 RAGFlow state")
        await asyncio.sleep(2)


async def _document_ready(client: object, dataset_id: str, document_id: str) -> bool:
    return await client.get_document_status(dataset_id=dataset_id, document_id=document_id) == "ready"  # type: ignore[attr-defined]


async def _marker_searchable(client: object, dataset_id: str, marker: str) -> bool:
    result = await client.retrieve(marker, dataset_ids=[dataset_id], page_size=8)  # type: ignore[attr-defined]
    return any(marker in str(chunk) for chunk in result.get("chunks", []))
