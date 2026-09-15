"""Bounded, caller-safe receipts for one authorized knowledge search."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

MAX_RECEIPT_ITEMS = 20
MAX_ITEM_CHARS = 4_000
_ITEM_RE = re.compile(r"^\[(\d+)\]\s+(.+?)(?:\s+\(score\s+([0-9.]+)\))?$", re.MULTILINE)


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def _chunk_reference(document_id: object, chunk_id: object) -> str | None:
    if chunk_id is None:
        return None
    value = f"{document_id or ''}\0{chunk_id}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _bounded_text(value: object) -> str:
    text = str(value or "")
    return text if len(text) <= MAX_ITEM_CHARS else text[:MAX_ITEM_CHARS].rstrip() + "…"


def _status(result: object) -> str:
    if isinstance(result, dict) and isinstance(result.get("chunks"), list):
        return "success" if result["chunks"] else "empty_hit"
    text = str(result or "")
    if text == "No relevant content found.":
        return "empty_hit"
    if text.startswith("Error:"):
        return "provider_error"
    return "success"


def _items(result: object, metadata: dict[str, object]) -> list[dict[str, object]]:
    documents = metadata.get("documents")
    documents = documents if isinstance(documents, dict) else {}
    raw_chunks: list[object] = []
    if isinstance(result, dict):
        raw_chunks = result.get("chunks") if isinstance(result.get("chunks"), list) else []
    elif isinstance(result, str):
        matches = list(_ITEM_RE.finditer(result))
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(result)
            raw_chunks.append({"document_keyword": match.group(2), "similarity": match.group(3), "content": result[start:end].strip()})

    items: list[dict[str, object]] = []
    for chunk in raw_chunks[:MAX_RECEIPT_ITEMS]:
        if not isinstance(chunk, dict):
            continue
        document_id = chunk.get("document_id")
        document = documents.get(str(document_id), {}) if document_id is not None else {}
        document = document if isinstance(document, dict) else {}
        item: dict[str, object] = {
            "document_id": document.get("logical_document_id"),
            "display_name": chunk.get("document_keyword") or document.get("display_name"),
            "content_hash": document.get("content_hash"),
            "chunk_ref": _chunk_reference(document.get("logical_document_id"), chunk.get("chunk_id")),
            "content": _bounded_text(chunk.get("content")),
            "score": chunk.get("similarity") if chunk.get("similarity") is not None else None,
            "position": {key: chunk[key] for key in ("page", "page_number", "section", "position") if key in chunk},
        }
        items.append(item)
    return items


def _citation_label(item: dict[str, object]) -> str:
    label = str(item.get("display_name") or "Knowledge source")
    position = item.get("position")
    if isinstance(position, dict):
        page = position.get("page") if position.get("page") is not None else position.get("page_number")
        if isinstance(page, (str, int)) and str(page):
            return f"{label} — Page {page}"
        section = position.get("section")
        if isinstance(section, str) and section.strip():
            return f"{label} — {section.strip()}"
    return label


def _model_facing_result(result: object, receipt: dict[str, object]) -> object:
    """Add opaque, run-local citation links without changing provider content."""
    if not isinstance(result, str):
        return result
    items = receipt.get("items")
    if not isinstance(items, list) or not items:
        return result
    links = []
    for item in items:
        if not isinstance(item, dict) or not item.get("evidence_id"):
            continue
        evidence_id = item["evidence_id"]
        links.append(f"- [citation:{_citation_label(item)}](evidence://{evidence_id})")
    if not links:
        return result
    return result.rstrip() + "\n\nKnowledge citations (copy the exact link when citing):\n" + "\n".join(links)


def build_retrieval_receipt(
    query: str,
    logical_kb: str,
    scope: Any,
    result: object,
    *,
    tool_call_id: str | None = None,
    parent_tool_receipt_id: str | None = None,
) -> dict[str, object]:
    """Project provider output without exposing provider IDs or configuration secrets."""
    dataset_id = scope.resolve(logical_kb)
    metadata = scope.revision_metadata_for(dataset_id)
    items = _items(result, metadata)
    status = _status(result)
    created_at = datetime.now(UTC).isoformat()
    receipt_id = "rr_" + hashlib.sha256(f"{query}\0{logical_kb}\0{created_at}".encode()).hexdigest()[:24]
    receipt = {
        "receipt_id": receipt_id,
        "receipt_kind": "retrieval",
        "logical_knowledge_base": logical_kb,
        "knowledge_base_id": metadata.get("knowledge_base_id", logical_kb),
        "revision_id": metadata.get("revision_id"),
        "revision_no": metadata.get("revision_no"),
        "manifest_hash": metadata.get("manifest_hash"),
        "configuration_source": metadata.get("configuration_source"),
        "tool_call_id": tool_call_id,
        "parent_tool_receipt_id": parent_tool_receipt_id,
        "created_at": created_at,
        "query_sha256": _query_hash(query),
        "result_status": status,
        "budget": {"max_items": MAX_RECEIPT_ITEMS, "max_chars_per_item": MAX_ITEM_CHARS},
        "returned_count": len(items),
        "truncated": isinstance(result, dict) and isinstance(result.get("chunks"), list) and len(result["chunks"]) > len(items),
        "items": items,
    }
    receipt_id = str(receipt["receipt_id"])
    for index, item in enumerate(items, start=1):
        item["evidence_id"] = f"{receipt_id}_i{index}"
        item["citation_label"] = _citation_label(item)
    return receipt


def model_facing_retrieval_result(result: object, receipt: dict[str, object]) -> object:
    """Return provider output annotated with only archived item identifiers."""
    return _model_facing_result(result, receipt)


def build_denied_retrieval_receipt(query: str, logical_kb: str | None) -> dict[str, object]:
    """Record a denied attempt without resolving or exposing a guessed KB."""
    created_at = datetime.now(UTC).isoformat()
    receipt_id = "rr_" + hashlib.sha256(f"{query}\0denied\0{created_at}".encode()).hexdigest()[:24]
    return {
        "receipt_id": receipt_id,
        "receipt_kind": "retrieval",
        "logical_knowledge_base": logical_kb if logical_kb else None,
        "knowledge_base_id": None,
        "revision_id": None,
        "revision_no": None,
        "manifest_hash": None,
        "tool_call_id": None,
        "parent_tool_receipt_id": None,
        "created_at": created_at,
        "query_sha256": _query_hash(query),
        "result_status": "access_denied",
        "budget": {"max_items": MAX_RECEIPT_ITEMS, "max_chars_per_item": MAX_ITEM_CHARS},
        "returned_count": 0,
        "truncated": False,
        "items": [],
    }
