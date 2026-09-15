from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.anyio
async def test_run_evidence_only_returns_receipts_from_the_run_knowledge_scope(monkeypatch) -> None:
    from app.gateway.routers.runs import run_evidence

    request = SimpleNamespace(_deerflow_test_bypass_auth=True)

    async def resolve_run(run_id, request):
        return {
            "run_id": run_id,
            "thread_id": "thread-1",
            "metadata": {
                "run_evidence": {
                    "knowledge_scope": {"bindings": {"docs": "frozen-dataset"}},
                    "retrieval_receipts": [
                        {"receipt_kind": "retrieval", "logical_knowledge_base": "docs", "receipt_id": "rr-1"},
                        {"receipt_kind": "retrieval", "logical_knowledge_base": "other", "receipt_id": "rr-2"},
                    ],
                }
            },
        }

    monkeypatch.setattr("app.gateway.routers.runs._resolve_run", resolve_run)

    response = await run_evidence.__wrapped__(run_id="run-1", request=request, receipt_id=None)

    assert [receipt["receipt_id"] for receipt in response["receipts"]] == ["rr-1"]
