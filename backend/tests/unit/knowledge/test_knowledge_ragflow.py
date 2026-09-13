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


class DatasetCreatingClient:
    async def create_dataset(self, *, name: str):
        return "dataset-1"

    async def list_dataset_documents(self, dataset_id: str):
        return [{"id": "provider-doc-1", "name": "guide.txt"}]


class DatasetRejectingClient:
    async def create_dataset(self, *, name: str):
        raise RAGFlowAPIError("quota exceeded", code=400)


@pytest.mark.asyncio
async def test_dataset_creation_is_exposed_through_the_provider_boundary() -> None:
    provider = RAGFlowKnowledgeProvider(DatasetCreatingClient())

    assert await provider.create_dataset(name="ideer-kb-abc12234-rev1-ef567890") == "dataset-1"
    assert await provider.list_dataset_documents(dataset_id="dataset-1") == [{"id": "provider-doc-1", "name": "guide.txt"}]


@pytest.mark.asyncio
async def test_dataset_creation_failure_is_classified_without_provider_detail() -> None:
    provider = RAGFlowKnowledgeProvider(DatasetRejectingClient())

    with pytest.raises(KnowledgeProviderError) as error:
        await provider.create_dataset(name="ideer-kb-abc12234-rev1-ef567890")

    assert error.value.code == "dataset_failed"
    assert "quota" not in str(error.value)
