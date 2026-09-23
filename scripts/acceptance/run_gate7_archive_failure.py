#!/usr/bin/env python3
"""Inject an isolated SQLite receipt-archive failure during a real Agent run."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx


_TRIGGER = "gate7_inject_archive_failure"


def _validate_archive_failure(run: dict) -> None:
    receipts = run.get("receipts", [])
    failed_ids = {item.get("receipt_id") for item in receipts if item.get("archive_status") == "failed"}
    assistant_text = run.get("assistant_text", "")
    if (
        len(receipts) != 1
        or receipts[0].get("archive_status") != "failed"
        or receipts[0].get("cited_item_ids")
        or any(receipt_id and f"evidence://{receipt_id}" in assistant_text for receipt_id in failed_ids)
    ):
        raise ValueError("archive_failure must fail closed: persist a failed receipt and keep its evidence citation out of the assistant response")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--knowledge-base", required=True)
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    with sqlite3.connect(args.database, timeout=10) as database:
        database.execute(f"DROP TRIGGER IF EXISTS {_TRIGGER}")
        database.execute(
            f"""CREATE TRIGGER {_TRIGGER} BEFORE UPDATE OF metadata_json ON runs
            WHEN EXISTS (
              SELECT 1 FROM json_each(json_extract(NEW.metadata_json, '$.run_evidence.retrieval_receipts')) AS receipt
              WHERE json_extract(receipt.value, '$.archive_status') = 'archived'
            )
            BEGIN SELECT RAISE(ABORT, 'Gate 7 isolated archive failure injection'); END"""
        )
    client = httpx.Client(base_url=args.gateway, timeout=120)
    try:
        username = "user@test.com"
        login = client.post("/api/v1/auth/login/local", data={"username": username, "password": username})
        login.raise_for_status()
        cookies = {item.name: item.value for item in login.cookies.jar}

        def request(method: str, path: str, **kwargs: object) -> dict:
            response = client.request(method, path, cookies={k: v for k, v in cookies.items() if k != "csrf_token"}, headers={"X-CSRF-Token": cookies["csrf_token"]}, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}

        thread = request("POST", "/api/threads", json={})["thread_id"]
        run_id = request("POST", f"/api/threads/{thread}/runs", json={"assistant_id": args.agent, "input": {"messages": [{"role": "user", "content": f"Call knowledge_search exactly once for knowledge_base '{args.knowledge_base}' and query 'Gate 7 isolated matrix citation marker'. If it fails, report that no verifiable citation is available."}]}})["run_id"]
        deadline = time.monotonic() + 300
        while True:
            state = request("GET", f"/api/threads/{thread}/runs/{run_id}")
            if state.get("status") in {"completed", "success", "failed", "error"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Gate 7 run {run_id} did not finish")
            time.sleep(2)
        evidence = request("GET", f"/api/runs/{run_id}/evidence")
        history = request("POST", f"/api/threads/{thread}/history", json={"limit": 10})
        messages = next((entry.get("values", {}).get("messages", []) for entry in history if entry.get("values", {}).get("messages")), [])
        assistant_text = "\n".join(str(getattr(message, "get", lambda *_: "content")("content", "")) for message in messages if (message.get("type") if isinstance(message, dict) else "") == "ai")
        run = {"thread_id": thread, "run_id": run_id, "status": state.get("status"), "receipts": evidence.get("receipts", []), "assistant_text": assistant_text}
        _validate_archive_failure(run)
        artifact = {
            "candidate_commit": os.environ["GATE7_CANDIDATE_COMMIT"],
            "scenario": "archive_failure", "real_execution": True, "result": "passed",
            "observed_steps": ["installed a temporary SQLite trigger on the isolated run-evidence row to reject archived retrieval receipt writes", "executed a real model-backed Agent retrieval", "verified the failed receipt was not cited in the persisted assistant response", "removed the trigger in a finally block"],
            "run": run, "recorded_at": datetime.now(UTC).isoformat(),
        }
        output = Path(os.environ["GATE7_EVIDENCE_PATH"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    finally:
        client.close()
        with sqlite3.connect(args.database, timeout=10) as database:
            database.execute(f"DROP TRIGGER IF EXISTS {_TRIGGER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
