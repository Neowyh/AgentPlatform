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


@pytest.mark.anyio
async def test_run_evidence_redacts_receipts_when_current_kb_access_is_revoked(monkeypatch) -> None:
    from app.gateway.routers.runs import run_evidence

    request = SimpleNamespace(_deerflow_test_bypass_auth=True)

    async def resolve_run(run_id, request):
        return {
            "run_id": run_id,
            "thread_id": "thread-1",
            "metadata": {
                "run_evidence": {
                    "retrieval_receipts": [
                        {
                            "receipt_kind": "retrieval",
                            "knowledge_base_id": "kb-private",
                            "revision_no": 1,
                            "manifest_hash": "secret-manifest",
                            "items": [{"evidence_id": "rr-1_i1", "content": "secret fragment"}],
                            "receipt_id": "rr-1",
                        }
                    ]
                }
            },
        }

    monkeypatch.setattr("app.gateway.routers.runs._resolve_run", resolve_run)
    monkeypatch.setattr(
        "app.gateway.routers.runs._readable_knowledge_base_ids",
        lambda current_user, ids: _async_value(set()),
    )

    response = await run_evidence.__wrapped__(run_id="run-1", request=request, receipt_id=None, current_user=object())

    assert response["receipts"] == [
        {
            "receipt_id": "rr-1",
            "receipt_kind": "retrieval",
            "result_status": "access_restricted",
            "returned_count": 0,
            "truncated": False,
            "items": [],
        }
    ]


async def _async_value(value):
    return value


@pytest.mark.anyio
async def test_run_evidence_applies_current_visibility_without_rewriting_frozen_receipts(monkeypatch) -> None:
    from app.gateway.routers.runs import run_evidence

    request = SimpleNamespace(_deerflow_test_bypass_auth=True)
    reader = SimpleNamespace(id="reader", role="user", department_id="dept-1")
    resources = [
        SimpleNamespace(
            id="kb-public",
            owner_id="owner",
            scope_department_id=None,
            visibility="public",
            lifecycle_status="active",
        ),
        SimpleNamespace(
            id="kb-private",
            owner_id="other-user",
            scope_department_id=None,
            visibility="private",
            lifecycle_status="active",
        ),
        SimpleNamespace(
            id="kb-archived",
            owner_id="reader",
            scope_department_id=None,
            visibility="private",
            lifecycle_status="archived",
        ),
    ]

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def execute(self, statement):
            del statement
            return SimpleNamespace(scalars=lambda: [resource for resource in resources if resource.lifecycle_status == "active"])

    monkeypatch.setattr(
        "deerflow.persistence.engine.get_session_factory",
        lambda: lambda: Session(),
    )

    async def resolve_run(run_id, request):
        return {
            "run_id": run_id,
            "thread_id": "thread-1",
            "metadata": {
                "run_evidence": {
                    "retrieval_receipts": [
                        {
                            "receipt_kind": "retrieval",
                            "receipt_id": "rr-public",
                            "knowledge_base_id": "kb-public",
                            "revision_no": 1,
                            "manifest_hash": "rev1-manifest",
                            "items": [{"evidence_id": "rr-public_i1", "content": "Rev1 fragment"}],
                        },
                        {
                            "receipt_kind": "retrieval",
                            "receipt_id": "rr-private",
                            "knowledge_base_id": "kb-private",
                            "revision_no": 1,
                            "manifest_hash": "private-manifest",
                            "items": [{"evidence_id": "rr-private_i1", "content": "Private fragment"}],
                        },
                        {
                            "receipt_kind": "retrieval",
                            "receipt_id": "rr-archived",
                            "knowledge_base_id": "kb-archived",
                            "revision_no": 1,
                            "manifest_hash": "archived-manifest",
                            "items": [{"evidence_id": "rr-archived_i1", "content": "Archived fragment"}],
                        },
                    ]
                }
            },
        }

    monkeypatch.setattr("app.gateway.routers.runs._resolve_run", resolve_run)

    response = await run_evidence.__wrapped__(run_id="run-1", request=request, receipt_id=None, current_user=reader)

    public, private, archived = response["receipts"]
    assert (public["revision_no"], public["manifest_hash"], public["items"][0]["content"]) == (1, "rev1-manifest", "Rev1 fragment")
    assert private["result_status"] == "access_restricted"
    assert archived["result_status"] == "access_restricted"
    assert "knowledge_base_id" not in private
    assert "manifest_hash" not in archived


@pytest.mark.anyio
async def test_run_evidence_fails_closed_when_authorization_storage_is_unavailable(monkeypatch) -> None:
    from app.gateway.routers.runs import run_evidence

    request = SimpleNamespace(_deerflow_test_bypass_auth=True)
    monkeypatch.setattr(
        "app.gateway.routers.runs._resolve_run",
        lambda *_: _async_value(
            {
                "run_id": "run-1",
                "thread_id": "thread-1",
                "metadata": {
                    "run_evidence": {
                        "retrieval_receipts": [
                            {
                                "receipt_kind": "retrieval",
                                "receipt_id": "rr-1",
                                "knowledge_base_id": "kb-1",
                                "items": [{"content": "must not leak"}],
                            }
                        ]
                    }
                },
            }
        ),
    )

    class BrokenSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def execute(self, statement):
            del statement
            raise RuntimeError("database offline")

    monkeypatch.setattr("deerflow.persistence.engine.get_session_factory", lambda: lambda: BrokenSession())

    response = await run_evidence.__wrapped__(
        run_id="run-1",
        request=request,
        receipt_id=None,
        current_user=SimpleNamespace(id="reader", role="user", department_id=None),
    )

    assert response["receipts"][0]["result_status"] == "access_restricted"
    assert response["receipts"][0]["items"] == []
