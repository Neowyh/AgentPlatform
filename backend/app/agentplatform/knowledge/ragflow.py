"""Management-side RAGFlow adapter; provider details stay outside API payloads."""

from __future__ import annotations

from deerflow.community.ragflow import tools as ragflow_tools
from deerflow.community.ragflow.client import RAGFlowAPIError, RAGFlowClient, RAGFlowConnectionError, RAGFlowProtocolError

from .provider import KnowledgeProviderError, ProviderIngestionResult


class RAGFlowKnowledgeProvider:
    def __init__(self, client: RAGFlowClient) -> None:
        self.client = client

    async def ingest(
        self,
        *,
        dataset_id: str,
        filename: str,
        mime_type: str,
        content: bytes,
        provider_document_id: str | None = None,
        rebuild: bool = False,
    ) -> ProviderIngestionResult:
        document_id = provider_document_id
        try:
            document_id = document_id or await self.client.upload_document(dataset_id, filename=filename, content=content, mime_type=mime_type)
            await self.client.parse_document(dataset_id, document_id)
            return ProviderIngestionResult(document_id, "processing")
        except RAGFlowConnectionError as exc:
            raise KnowledgeProviderError("unavailable") from exc
        except RAGFlowProtocolError as exc:
            raise KnowledgeProviderError("invalid_response") from exc
        except RAGFlowAPIError as exc:
            code = "parse_failed" if "parse" in str(exc).lower() else "index_failed"
            raise KnowledgeProviderError(code, provider_document_id=document_id) from exc

    async def get_status(self, *, dataset_id: str, provider_document_id: str) -> str:
        try:
            return await self.client.get_document_status(dataset_id, provider_document_id)
        except RAGFlowConnectionError as exc:
            raise KnowledgeProviderError("unavailable", provider_document_id=provider_document_id) from exc
        except RAGFlowProtocolError as exc:
            raise KnowledgeProviderError("invalid_response", provider_document_id=provider_document_id) from exc
        except RAGFlowAPIError as exc:
            raise KnowledgeProviderError("index_failed", provider_document_id=provider_document_id) from exc

    async def delete_document(self, *, dataset_id: str, provider_document_id: str) -> None:
        try:
            await self.client.delete_document(dataset_id, provider_document_id)
        except RAGFlowConnectionError as exc:
            raise KnowledgeProviderError("unavailable", provider_document_id=provider_document_id) from exc
        except RAGFlowProtocolError as exc:
            raise KnowledgeProviderError("invalid_response", provider_document_id=provider_document_id) from exc
        except RAGFlowAPIError as exc:
            raise KnowledgeProviderError("delete_failed", provider_document_id=provider_document_id) from exc

    async def create_dataset(self, *, name: str) -> str:
        try:
            return await self.client.create_dataset(name=name)
        except RAGFlowConnectionError as exc:
            raise KnowledgeProviderError("unavailable") from exc
        except RAGFlowProtocolError as exc:
            raise KnowledgeProviderError("invalid_response") from exc
        except RAGFlowAPIError as exc:
            raise KnowledgeProviderError("dataset_failed") from exc

    async def list_dataset_documents(self, *, dataset_id: str) -> list[dict]:
        try:
            return await self.client.list_dataset_documents(dataset_id)
        except RAGFlowConnectionError as exc:
            raise KnowledgeProviderError("unavailable") from exc
        except RAGFlowProtocolError as exc:
            raise KnowledgeProviderError("invalid_response") from exc
        except RAGFlowAPIError as exc:
            raise KnowledgeProviderError("invalid_response") from exc

    async def list_datasets(self, *, dataset_id: str | None = None) -> list[dict]:
        try:
            return await self.client.list_datasets(dataset_id=dataset_id)
        except RAGFlowConnectionError as exc:
            raise KnowledgeProviderError("unavailable") from exc
        except RAGFlowProtocolError as exc:
            raise KnowledgeProviderError("invalid_response") from exc
        except RAGFlowAPIError as exc:
            raise KnowledgeProviderError("invalid_response") from exc


def configured_ragflow_provider() -> RAGFlowKnowledgeProvider | None:
    settings, _ = ragflow_tools._settings_or_error()
    return RAGFlowKnowledgeProvider(ragflow_tools._build_client(settings)) if settings is not None else None
