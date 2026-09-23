#!/usr/bin/env python3
"""Verify persisted chat history cannot substitute for a missing receipt."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from run_gate7_matrix import Gateway, _require_archived_receipts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", default=os.environ.get("GATE7_GATEWAY", "http://127.0.0.1:8017"))
    parser.add_argument("--agent", default=os.environ.get("GATE7_AGENT_ID"), required="GATE7_AGENT_ID" not in os.environ)
    parser.add_argument("--knowledge-base", default=os.environ.get("GATE7_KB_ID"), required="GATE7_KB_ID" not in os.environ)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()

    gateway = Gateway(args.gateway, "user@test.com")
    thread = gateway.request("POST", "/api/threads", json={})["thread_id"]
    question = (
        f"Call knowledge_search once with knowledge_base='{args.knowledge_base}' and "
        "query 'Gate 7 isolated matrix citation marker'. Quote the exact returned source and citation."
    )
    run = gateway.request(
        "POST",
        f"/api/threads/{thread}/runs",
        json={"assistant_id": args.agent, "input": {"messages": [{"role": "user", "content": question}]}},
    )["run_id"]
    deadline = time.monotonic() + 900
    while True:
        state = gateway.request("GET", f"/api/threads/{thread}/runs/{run}")
        if state.get("status") in {"completed", "success", "failed", "error"}:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError(f"history run {run} timed out")
        time.sleep(5)
    if state.get("status") not in {"completed", "success"}:
        raise RuntimeError(f"history run status={state.get('status')!r}")

    before = gateway.request("GET", f"/api/runs/{run}/evidence")
    _require_archived_receipts(before, "history run before receipt removal")
    messages = gateway.request("GET", f"/api/threads/{thread}/runs/{run}/messages").get("data", [])
    message_text = json.dumps(messages, ensure_ascii=False)
    if "Gate 7 isolated matrix citation marker 8d7d6179." not in message_text:
        raise ValueError("the persisted run history lacks the retrieved marker")

    connection = sqlite3.connect(args.database)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT user_id, metadata_json FROM runs WHERE run_id = ? AND thread_id = ?",
            (run, thread),
        ).fetchone()
        if row is None or row[0] is None:
            raise ValueError("the exact test run was not found in the isolated Gateway database")
        metadata = json.loads(row[1])
        run_evidence = metadata.get("run_evidence")
        receipts = run_evidence.get("retrieval_receipts") if isinstance(run_evidence, dict) else None
        if not isinstance(receipts, list) or len(receipts) != len(before["receipts"]):
            raise ValueError("run metadata receipts do not match the pre-injection Evidence API response")
        run_evidence["retrieval_receipts"] = []
        cursor = connection.execute(
            "UPDATE runs SET metadata_json = ? WHERE run_id = ? AND thread_id = ? AND user_id = ?",
            (json.dumps(metadata), run, thread, row[0]),
        )
        if cursor.rowcount != 1:
            raise ValueError("fault injection did not update exactly the target Run row")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    after = gateway.request("GET", f"/api/runs/{run}/evidence")
    if after.get("receipts"):
        raise ValueError("Evidence API exposed a receipt after its archive record was removed")

    evidence = {
        "candidate_commit": os.environ["GATE7_CANDIDATE_COMMIT"],
        "scenario": "history_without_receipt",
        "real_execution": True,
        "result": "passed",
        "observed_steps": [
            "completed a real Agent retrieval Run and confirmed an archived receipt",
            "confirmed the persisted Run message history contains the retrieved citation marker",
            "removed only this Run's receipt from the isolated SQLite metadata row",
            "confirmed the Evidence API returned no receipt while historical messages remained readable",
        ],
        "thread_id": thread,
        "run_id": run,
        "receipts_before": len(before["receipts"]),
        "receipts_after": len(after.get("receipts", [])),
        "history_contains_marker": True,
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    output = Path(os.environ["GATE7_EVIDENCE_PATH"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
