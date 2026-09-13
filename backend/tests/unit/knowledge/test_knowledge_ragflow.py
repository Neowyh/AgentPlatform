from __future__ import annotations

import pytest

from app.agentplatform.knowledge.provider import KnowledgeProviderError
from app.agentplatform.knowledge.ragflow import RAGFlowKnowledgeProvider
from deerflow.community.ragflow.client import RAGFlowAPIError


class UploadRejectingClient:
    async def upload_document(self, *args, **kwargs):
        raise RAGFlowAPIError("upload rejected", code=400)


class ParsingClient:
    async def upload_document(self, *args, **kwargs):
        return "provider-doc-1"

    async def parse_document(self, *args, **kwargs):
        return None

    async def get_document_status(self, *args, **kwargs):
        return "ready"


@pytest.mark.asyncio
async def test_upload_api_failure_is_classified_without_secondary_exception() -> None:
    provider = RAGFlowKnowledgeProvider(UploadRejectingClient())

    with pytest.raises(KnowledgeProviderError) as error:
        await provider.ingest(
            dataset_id="dataset-1",
            filename="guide.txt",
            mime_type="text/plain",
            content=b"guide",
        )

    assert error.value.code == "index_failed"
    assert error.value.provider_document_id is None


@pytest.mark.asyncio
async def test_parse_acceptance_remains_processing_until_provider_reports_ready() -> None:
    provider = RAGFlowKnowledgeProvider(ParsingClient())

    result = await provider.ingest(
        dataset_id="dataset-1",
        filename="guide.txt",
        mime_type="text/plain",
        content=b"guide",
    )

    assert result.status == "processing"


@pytest.mark.asyncio
async def test_provider_reports_a_persisted_document_status() -> None:
    provider = RAGFlowKnowledgeProvider(ParsingClient())

    assert await provider.get_status(dataset_id="dataset-1", provider_document_id="provider-doc-1") == "ready"
