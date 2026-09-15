"""Gate 7 live acceptance for the provider-to-retrieval-receipt source chain."""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import pytest
from agentplatform_extension.evidence import (
    AuthorizationContext,
    RunEvidenceBinding,
    bind_run_evidence,
    current_run_evidence,
)
from agentplatform_extension.knowledge.runtime_adapter import KnowledgeRuntimeAdapter
from agentplatform_extension.knowledge.scope import KnowledgeScope

from deerflow.community.ragflow import tools as ragflow_tools

pytestmark = pytest.mark.live

_skip_reason = None
if os.environ.get("CI"):
    _skip_reason = "Live tests skipped in CI"
elif os.environ.get("DEER_FLOW_RUN_LIVE_TESTS") != "1":
    _skip_reason = "Set DEER_FLOW_RUN_LIVE_TESTS=1 to run Gate 7 against RAGFlow"
elif not Path(__file__).resolve().parents[2].joinpath("config.yaml").exists():
    _skip_reason = "No config.yaml found — real RAGFlow settings are required"
elif not os.environ.get("RAGFLOW_GATE7_DATASET_ID"):
    _skip_reason = "Set RAGFLOW_GATE7_DATASET_ID to an isolated RAGFlow dataset"

if _skip_reason:
    pytest.skip(_skip_reason, allow_module_level=True)


async def _wait_for(predicate, *, timeout: float = 180) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if await predicate():
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Timed out waiting for the Gate 7 RAGFlow state")
        await asyncio.sleep(2)


@pytest.mark.asyncio
async def test_gate7_real_provider_content_matches_archived_delivery() -> None:
    settings, error = ragflow_tools._settings_or_error()
    assert settings is not None, error
    client = ragflow_tools._build_client(settings)
    dataset_id = os.environ["RAGFLOW_GATE7_DATASET_ID"]
    marker = f"knowledge-gate7-{uuid.uuid4().hex}"
    document_id = await client.upload_document(
        dataset_id,
        filename=f"{marker}.txt",
        content=f"Gate 7 source marker: {marker}".encode(),
        mime_type="text/plain",
    )

    try:
        await client.parse_document(dataset_id, document_id)
        await _wait_for(
            lambda: _document_is_ready(client, dataset_id, document_id),
        )
        await _wait_for(lambda: _marker_is_searchable(client, dataset_id, marker))

        scope = KnowledgeScope.from_bindings(
            {"gate-kb": dataset_id},
            revision_metadata={
                dataset_id: {
                    "knowledge_base_id": "gate7-kb",
                    "revision_id": "gate7-revision-1",
                    "revision_no": 1,
                    "manifest_hash": "a" * 64,
                    "configuration_source": "frozen_run_revision",
                    "documents": {
                        document_id: {
                            "logical_document_id": "gate7-document",
                            "display_name": f"{marker}.txt",
                            "content_hash": "b" * 64,
                        }
                    },
                }
            },
        )
        binding = RunEvidenceBinding(
            [],
            AuthorizationContext("gate7-user", "gate7-agent", "gate7-policy"),
            run_id="gate7-run",
            knowledge_scope={"bindings": {"gate-kb": dataset_id}},
        )
        with bind_run_evidence(binding):
            delivered = await KnowledgeRuntimeAdapter(scope, client.retrieve).search_knowledge(marker, logical_kb="gate-kb")
            evidence = current_run_evidence()

        assert evidence is not None
        assert len(evidence.retrieval_receipts) == 1
        receipt = evidence.retrieval_receipts[0]
        assert receipt["knowledge_base_id"] == "gate7-kb"
        assert receipt["revision_id"] == "gate7-revision-1"
        assert receipt["items"]
        item = receipt["items"][0]
        assert item["document_id"] == "gate7-document"
        assert marker in item["content"]
        assert item["evidence_id"] in delivered
        assert item["content"] in delivered
    finally:
        await client.delete_document(dataset_id, document_id)


async def _document_is_ready(client, dataset_id: str, document_id: str) -> bool:
    return await client.get_document_status(dataset_id=dataset_id, document_id=document_id) == "ready"


async def _marker_is_searchable(client, dataset_id: str, marker: str) -> bool:
    result = await client.retrieve(marker, dataset_ids=[dataset_id], page_size=8)
    return any(marker in str(chunk) for chunk in result.get("chunks", []))
