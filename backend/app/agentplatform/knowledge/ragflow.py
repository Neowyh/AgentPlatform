"""Management-side RAGFlow adapter; provider details stay outside API payloads."""

from __future__ import annotations

import logging
import time

from deerflow.community.ragflow import tools as ragflow_tools
from deerflow.community.ragflow.client import RAGFlowAPIError, RAGFlowClient, RAGFlowConnectionError, RAGFlowProtocolError

from .provider import KnowledgeProviderError, ProviderIngestionResult

logger = logging.getLogger(__name__)


def _record_ingestion_metric(*, result: str, latency_ms: float, error_category: str | None = None) -> None:
    fields: dict[str, object] = {
        "operation": "knowledge_ingestion",
        "result": result,
        "latency_ms": round(latency_ms, 2),
    }
    if error_category is not None:
        fields["error_category"] = error_category
    logger.info("knowledge_metric %s", fields)


class RAGFlowKnowledgeProvider:
    def __init__(self, client: RAGFlowClient) -> None:
        self.client = client

    async def create_dataset(self, *, name: str, embedding_model: str | None = None) -> str:
        try:
            list_datasets = getattr(self.client, "list_datasets", None)
            existing = [] if list_datasets is None else [item for item in await list_datasets() if item.get("name") == name and isinstance(item.get("id"), str)]
            if len(existing) == 1:
                return str(existing[0]["id"])
            if len(existing) > 1:
                raise KnowledgeProviderError("invalid_response")
            try:
                return await self.client.create_dataset(name, embedding_model=embedding_model)
            except TypeError:
                # Keep compatibility with lightweight provider clients that
                # implement the original name-only boundary.
                return await self.client.create_dataset(name=name)
        except RAGFlowConnectionError as exc:
            raise KnowledgeProviderError("unavailable") from exc
        except RAGFlowProtocolError as exc:
            raise KnowledgeProviderError("invalid_response") from exc
        except RAGFlowAPIError as exc:
            raise KnowledgeProviderError("dataset_failed") from exc

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
        started = time.monotonic()
        try:
            document_id = document_id or await self.client.upload_document(dataset_id, filename=filename, content=content, mime_type=mime_type)
            await self.client.parse_document(dataset_id, document_id)
            result = ProviderIngestionResult(document_id, "processing")
            _record_ingestion_metric(result="accepted", latency_ms=(time.monotonic() - started) * 1000)
            return result
        except RAGFlowConnectionError as exc:
            _record_ingestion_metric(result="error", latency_ms=(time.monotonic() - started) * 1000, error_category="connection")
            raise KnowledgeProviderError("unavailable") from exc
        except RAGFlowProtocolError as exc:
            _record_ingestion_metric(result="error", latency_ms=(time.monotonic() - started) * 1000, error_category="protocol")
            raise KnowledgeProviderError("invalid_response") from exc
        except RAGFlowAPIError as exc:
            code = "parse_failed" if "parse" in str(exc).lower() else "index_failed"
            _record_ingestion_metric(result="error", latency_ms=(time.monotonic() - started) * 1000, error_category=code)
            raise KnowledgeProviderError(code, provider_document_id=document_id) from exc
        except Exception:
            _record_ingestion_metric(result="error", latency_ms=(time.monotonic() - started) * 1000, error_category="unexpected")
            raise

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
