"""Provider boundary for durable KnowledgeBase document ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProviderIngestionResult:
    provider_document_id: str | None
    status: str = "ready"


class KnowledgeProviderError(Exception):
    """A provider failure safe to classify at the management boundary."""

    def __init__(self, code: str, message: str = "Provider ingestion failed", *, provider_document_id: str | None = None) -> None:
        self.code = code
        self.provider_document_id = provider_document_id
        super().__init__(message)


class KnowledgeProvider(Protocol):
    async def ingest(
        self,
        *,
        dataset_id: str,
        filename: str,
        mime_type: str,
        content: bytes,
        provider_document_id: str | None = None,
        rebuild: bool = False,
    ) -> ProviderIngestionResult: ...

    async def get_status(self, *, dataset_id: str, provider_document_id: str) -> str: ...


def stable_provider_error(exc: Exception) -> tuple[str, str]:
    """Map provider errors to a low-cardinality, non-sensitive user message."""
    if isinstance(exc, KnowledgeProviderError):
        messages = {
            "unavailable": "The knowledge provider is temporarily unavailable.",
            "parse_failed": "The provider could not parse this document.",
            "index_failed": "The provider could not index this document.",
            "invalid_response": "The knowledge provider returned an invalid response.",
        }
        return exc.code, messages.get(exc.code, "Document processing failed.")
    return "provider_error", "Document processing failed. Please try again later."
