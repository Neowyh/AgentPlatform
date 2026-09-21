from __future__ import annotations

import asyncio

import pytest
from agentplatform_extension.evidence import (
    AuthorizationContext,
    RunEvidenceBinding,
    bind_receipt_archiver,
    bind_run_evidence,
    bind_tool_call_evidence,
    current_run_evidence,
    record_delegated_retrieval_receipts,
    record_retrieval_citations,
    record_retrieval_receipt,
    record_tool_receipt,
)
from agentplatform_extension.knowledge.runtime_adapter import KnowledgeRuntimeAdapter
from agentplatform_extension.knowledge.scope import KnowledgeScope


def _scope() -> KnowledgeScope:
    return KnowledgeScope.from_bindings(
        {"docs": "provider-dataset"},
        revision_metadata={
            "provider-dataset": {
                "knowledge_base_id": "kb-1",
                "revision_id": "revision-1",
                "revision_no": 3,
                "manifest_hash": "a" * 64,
                "configuration_source": "frozen_run_revision",
                "documents": {
                    "provider-doc-1": {
                        "logical_document_id": "document-1",
                        "display_name": "Policies.pdf",
                        "content_hash": "b" * 64,
                    }
                },
            }
        },
    )


@pytest.mark.anyio
async def test_retrieval_receipt_from_child_task_is_visible_to_parent() -> None:
    """LangGraph tool tasks must contribute to the parent Run evidence envelope."""

    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"))

    async def child() -> None:
        record_retrieval_receipt({"receipt_kind": "retrieval", "receipt_id": "child-receipt"})

    with bind_run_evidence(binding):
        await asyncio.create_task(child())
        evidence = current_run_evidence()

    assert evidence is not None
    assert evidence.retrieval_receipts == ({"receipt_kind": "retrieval", "receipt_id": "child-receipt"},)


@pytest.mark.anyio
async def test_authorized_search_records_bounded_receipt_from_real_result() -> None:
    async def provider(query: str, *, dataset_ids: list[str]) -> dict:
        return {
            "chunks": [
                {
                    "document_id": "provider-doc-1",
                    "chunk_id": "chunk-1",
                    "document_keyword": "Policies.pdf",
                    "content": "Untrusted <script>alert(1)</script> fragment",
                    "similarity": 0.91,
                    "page": 4,
                }
            ],
            "total": 1,
        }

    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"))
    with bind_run_evidence(binding):
        result = await KnowledgeRuntimeAdapter(_scope(), provider).search_knowledge("vacation", logical_kb="docs")

        assert result["chunks"]
        receipt = current_run_evidence().retrieval_receipts[0]

    assert receipt["knowledge_base_id"] == "kb-1"
    assert receipt["revision_id"] == "revision-1"
    assert receipt["manifest_hash"] == "a" * 64
    assert receipt["configuration_source"] == "frozen_run_revision"
    assert receipt["query_sha256"]
    assert receipt["items"][0]["content"] == "Untrusted <script>alert(1)</script> fragment"
    assert receipt["items"][0]["document_id"] == "document-1"
    assert "provider-doc-1" not in str(receipt)
    assert "provider-dataset" not in receipt["items"][0]


@pytest.mark.anyio
async def test_retrieval_receipt_keeps_the_exact_active_tool_call_id() -> None:
    async def provider(query: str, *, dataset_ids: list[str]) -> dict:
        return {"chunks": [{"document_id": "provider-doc-1", "content": "fragment"}]}

    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"))
    with bind_run_evidence(binding), bind_tool_call_evidence("call-42"):
        await KnowledgeRuntimeAdapter(_scope(), provider).search_knowledge("vacation", logical_kb="docs")
        receipt = current_run_evidence().retrieval_receipts[0]

    assert receipt["tool_call_id"] == "call-42"


def test_root_retrieval_receipt_does_not_invent_parent_call_linkage() -> None:
    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"))
    receipt = {"receipt_id": "rr-root", "receipt_kind": "retrieval", "items": []}
    with bind_run_evidence(binding), bind_tool_call_evidence("call-root"):
        record_retrieval_receipt(receipt)
        record_tool_receipt({"tool_name": "knowledge_search", "tool_call_id": "call-root"})
        recorded = current_run_evidence().retrieval_receipts[0]

    assert "tool_call_id" not in recorded
    assert "parent_tool_receipt_id" not in recorded


@pytest.mark.anyio
async def test_retrieval_citation_is_delivered_only_after_archive_callback_succeeds() -> None:
    async def provider(query: str, *, dataset_ids: list[str]) -> dict:
        return {"chunks": [{"document_id": "provider-doc-1", "content": "fragment"}]}

    archived: list[str] = []

    async def archive(receipt: dict) -> bool:
        archived.append(str(receipt["receipt_id"]))
        return True

    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"))
    with bind_run_evidence(binding), bind_receipt_archiver(archive):
        result = await KnowledgeRuntimeAdapter(_scope(), provider).search_knowledge("vacation", logical_kb="docs")
        receipt = current_run_evidence().retrieval_receipts[0]

    assert archived == [receipt["receipt_id"]]
    assert receipt["archive_status"] == "archived"
    assert receipt["items"][0]["evidence_id"] in str(result)


@pytest.mark.anyio
async def test_archive_failure_does_not_deliver_a_verifiable_citation() -> None:
    async def provider(query: str, *, dataset_ids: list[str]) -> dict:
        return {"chunks": [{"document_id": "provider-doc-1", "content": "fragment"}]}

    async def archive(receipt: dict) -> bool:
        return False

    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"))
    with bind_run_evidence(binding), bind_receipt_archiver(archive):
        result = await KnowledgeRuntimeAdapter(_scope(), provider).search_knowledge("vacation", logical_kb="docs")

    assert result == "Knowledge evidence could not be archived; no verifiable citation is available."


@pytest.mark.anyio
async def test_archive_exception_fails_closed_without_leaking_provider_result() -> None:
    async def provider(query: str, *, dataset_ids: list[str]) -> dict:
        return {"chunks": [{"document_id": "provider-doc-1", "content": "fragment"}]}

    async def archive(receipt: dict) -> bool:
        raise RuntimeError("storage unavailable")

    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"))
    with bind_run_evidence(binding), bind_receipt_archiver(archive):
        result = await KnowledgeRuntimeAdapter(_scope(), provider).search_knowledge("vacation", logical_kb="docs")
        receipt = current_run_evidence().retrieval_receipts[0]

    assert receipt["archive_status"] == "failed"
    assert result == "Knowledge evidence could not be archived; no verifiable citation is available."


@pytest.mark.anyio
async def test_structured_search_delivers_evidence_id_and_citation_to_model() -> None:
    async def provider(query: str, *, dataset_ids: list[str]) -> dict:
        return {
            "chunks": [
                {
                    "document_id": "provider-doc-1",
                    "chunk_id": "chunk-1",
                    "document_keyword": "Policies.pdf",
                    "content": "Policy fragment",
                    "similarity": 0.91,
                    "page": 4,
                }
            ]
        }

    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"))
    with bind_run_evidence(binding):
        result = await KnowledgeRuntimeAdapter(_scope(), provider).search_knowledge("vacation", logical_kb="docs")
        receipt = current_run_evidence().retrieval_receipts[0]

    evidence_id = receipt["items"][0]["evidence_id"]
    delivered = result["chunks"][0]
    assert delivered["evidence_id"] == evidence_id
    assert delivered["citation"] == f"[citation:Policies.pdf — Page 4](evidence://{evidence_id})"
    assert receipt["items"][0]["document_id"] == "document-1"
    assert receipt["items"][0]["chunk_ref"]
    assert "document_id" not in delivered
    assert "chunk_id" not in delivered


@pytest.mark.anyio
async def test_structured_delivery_uses_the_same_bounded_content_as_archive() -> None:
    source = "x" * 5_000

    async def provider(query: str, *, dataset_ids: list[str]) -> dict:
        return {
            "chunks": [
                {
                    "document_id": "provider-doc-1",
                    "document_keyword": "Policies.pdf",
                    "content": source,
                    "similarity": 0.91,
                }
            ],
            "total": 1,
        }

    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"))
    with bind_run_evidence(binding):
        result = await KnowledgeRuntimeAdapter(_scope(), provider).search_knowledge("vacation", logical_kb="docs")
        receipt = current_run_evidence().retrieval_receipts[0]

    archived = receipt["items"][0]["content"]
    delivered = result["chunks"][0]["content"]
    assert delivered == archived
    assert receipt["truncated"] is True
    assert receipt["truncation"] == {"items": False, "characters": True}


@pytest.mark.anyio
async def test_authorized_search_delivers_archived_item_citation_to_model() -> None:
    async def provider(query: str, *, dataset_ids: list[str]) -> str:
        return "[1] Policies.pdf (score 0.91)\nPolicy fragment"

    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"))
    with bind_run_evidence(binding):
        result = await KnowledgeRuntimeAdapter(_scope(), provider).search_knowledge("vacation", logical_kb="docs")
        receipt = current_run_evidence().retrieval_receipts[0]

    evidence_id = receipt["items"][0]["evidence_id"]
    assert f"evidence://{evidence_id}" in result
    assert receipt["items"][0]["citation_label"] == "Policies.pdf"


@pytest.mark.anyio
async def test_provider_label_is_safe_inside_model_facing_markdown() -> None:
    async def provider(query: str, *, dataset_ids: list[str]) -> str:
        return "[1] Policies.pdf](https://evil.example)\nPolicy fragment"

    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"))
    with bind_run_evidence(binding):
        result = await KnowledgeRuntimeAdapter(_scope(), provider).search_knowledge("vacation", logical_kb="docs")

    citations = result.split("Knowledge citations", 1)[1]
    assert "\\]" in citations
    assert "](https://evil.example)" not in citations


@pytest.mark.anyio
async def test_only_archived_citations_are_recorded() -> None:
    async def provider(query: str, *, dataset_ids: list[str]) -> str:
        return "[1] Policies.pdf\nPolicy fragment"

    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"))
    with bind_run_evidence(binding):
        await KnowledgeRuntimeAdapter(_scope(), provider).search_knowledge("vacation", logical_kb="docs")
        receipt = current_run_evidence().retrieval_receipts[0]
        evidence_id = receipt["items"][0]["evidence_id"]
        record_retrieval_citations(f"[citation:Policies](evidence://{evidence_id})")
        record_retrieval_citations("[citation:Fake](evidence://rr_other_i1)")
        recorded = current_run_evidence().retrieval_receipts[0]

    assert recorded["cited_item_ids"] == [evidence_id]


@pytest.mark.anyio
async def test_code_block_evidence_link_is_not_recorded_as_citation() -> None:
    async def provider(query: str, *, dataset_ids: list[str]) -> str:
        return "[1] Policies.pdf\nPolicy fragment"

    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"))
    with bind_run_evidence(binding):
        await KnowledgeRuntimeAdapter(_scope(), provider).search_knowledge("vacation", logical_kb="docs")
        receipt = current_run_evidence().retrieval_receipts[0]
        evidence_id = receipt["items"][0]["evidence_id"]
        record_retrieval_citations(f"```md\n[citation:Example](evidence://{evidence_id})\n```")
        recorded = current_run_evidence().retrieval_receipts[0]

    assert "cited_item_ids" not in recorded


@pytest.mark.anyio
async def test_empty_and_error_results_do_not_create_fake_items() -> None:
    async def provider(query: str, *, dataset_ids: list[str]) -> str:
        return "No relevant content found."

    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"))
    with bind_run_evidence(binding):
        result = await KnowledgeRuntimeAdapter(_scope(), provider).search_knowledge("missing", logical_kb="docs")
        recorded = current_run_evidence()

    assert result == "No relevant content found."
    assert recorded is not None
    assert recorded.retrieval_receipts[0]["result_status"] == "empty_hit"
    assert recorded.retrieval_receipts[0]["items"] == []


def test_same_query_calls_are_kept_separate_but_duplicate_delivery_is_idempotent() -> None:
    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"), run_id="run-1")
    first = {"receipt_id": "rr-1", "query_sha256": "same", "run_id": "run-1"}
    retry = {**first, "created_at": "later"}
    second_call = {"receipt_id": "rr-2", "query_sha256": "same", "run_id": "run-1"}

    with bind_run_evidence(binding):
        record_retrieval_receipt(first)
        record_retrieval_receipt(retry)
        record_retrieval_receipt(second_call)
        receipts = current_run_evidence().retrieval_receipts

    assert [receipt["receipt_id"] for receipt in receipts] == ["rr-1", "rr-2"]


def test_delegated_receipts_require_parent_run_and_frozen_scope() -> None:
    binding = RunEvidenceBinding(
        [],
        AuthorizationContext("caller", "agent", "policy"),
        run_id="run-1",
        knowledge_scope={"bindings": {"docs": "dataset-1"}},
    )
    valid = {
        "receipt_id": "rr-child",
        "run_id": "run-1",
        "logical_knowledge_base": "docs",
        "parent_tool_receipt_id": "task-call-1",
        "items": [{"evidence_id": "rr-child_i1"}],
    }

    with bind_run_evidence(binding):
        assert (
            record_delegated_retrieval_receipts(
                [
                    valid,
                    {**valid, "receipt_id": "rr-other-run", "run_id": "run-2"},
                    {
                        **valid,
                        "receipt_id": "rr-other-kb",
                        "logical_knowledge_base": "private",
                    },
                ],
                parent_tool_receipt_id="task-call-1",
                child_task_id="child-1",
                child_agent_id="researcher",
            )
            == 1
        )
        receipt = current_run_evidence().retrieval_receipts[0]

    assert receipt["delegated"] is True
    assert receipt["child_task_id"] == "child-1"
    assert receipt["child_agent_id"] == "researcher"


def test_delegated_receipts_without_frozen_scope_are_rejected() -> None:
    binding = RunEvidenceBinding([], AuthorizationContext("caller", "agent", "policy"), run_id="run-1")
    receipt = {
        "receipt_id": "rr-child",
        "run_id": "run-1",
        "logical_knowledge_base": "docs",
        "parent_tool_receipt_id": "task-call-1",
    }

    with bind_run_evidence(binding):
        assert (
            record_delegated_retrieval_receipts(
                [receipt],
                parent_tool_receipt_id="task-call-1",
                child_task_id="child-1",
            )
            == 0
        )
        assert current_run_evidence().retrieval_receipts == ()


def test_rejected_delegated_receipts_leave_an_unavailable_status() -> None:
    binding = RunEvidenceBinding(
        [],
        AuthorizationContext("caller", "agent", "policy"),
        run_id="run-1",
        knowledge_scope={"bindings": {"docs": "dataset-1"}},
    )
    rejected = {
        "receipt_id": "rr-child",
        "run_id": "run-2",
        "logical_knowledge_base": "docs",
        "parent_tool_receipt_id": "task-call-1",
    }

    with bind_run_evidence(binding):
        assert (
            record_delegated_retrieval_receipts(
                [rejected],
                parent_tool_receipt_id="task-call-1",
                child_task_id="child-1",
            )
            == 0
        )
        status = current_run_evidence().subagent_verification[0]

    assert status["status"] == "UNAVAILABLE"
    assert status["task_id"] == "child-1"
    assert status["reason"] == "delegated_retrieval_unavailable"
