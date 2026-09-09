"""Adapters from local execution receipts to the canonical tool evidence ledger."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def tool_receipt_from_local(receipt: Mapping[str, Any], *, tool_call_id: str | None = None) -> dict[str, Any]:
    value = dict(receipt)
    value.update({"tool_name": value.get("capability", "local.unknown"), "receipt_kind": "local_execution"})
    if tool_call_id is not None:
        value["tool_call_id"] = tool_call_id
    return value
