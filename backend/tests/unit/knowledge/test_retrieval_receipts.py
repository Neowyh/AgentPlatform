from __future__ import annotations

import pytest
from agentplatform_extension.evidence import AuthorizationContext, RunEvidenceBinding, bind_run_evidence, current_run_evidence
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
async def test_authorized_search_records_bounded_receipt_from_real_result() -> None:
    async def provider(query: str, *, dataset_ids: list[str]) -> dict:
        return {
            "chunks": [
                {
                    "document_id": "provider-doc-1",
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
