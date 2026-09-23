#!/usr/bin/env python3
"""Verify a real Agent run's streamed Gateway event sequence and receipt."""

from __future__ import annotations

import json
import os
import re
import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.acceptance.run_gate7_matrix import Gateway, _require_archived_receipts


def _validate_stream_event_types(event_types: list[str]) -> None:
    if (
        not event_types
        or event_types[0] != "metadata"
        or event_types[-1] != "end"
        or len(event_types) < 3
    ):
        raise ValueError("stream must contain intermediate events before its terminal end event")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", default=os.environ.get("GATE7_GATEWAY", "http://127.0.0.1:8017"))
    parser.add_argument("--agent", default=os.environ.get("GATE7_AGENT_ID"), required="GATE7_AGENT_ID" not in os.environ)
    parser.add_argument("--knowledge-base", default=os.environ.get("GATE7_KB_ID"), required="GATE7_KB_ID" not in os.environ)
    args = parser.parse_args()
    gateway_url = args.gateway
    agent_id = args.agent
    knowledge_base = args.knowledge_base
    candidate = os.environ["GATE7_CANDIDATE_COMMIT"]
    output = Path(os.environ["GATE7_EVIDENCE_PATH"])
    gateway = Gateway(gateway_url, "user@test.com")
    thread = gateway.request("POST", "/api/threads", json={})["thread_id"]
    cookies = {key: value for key, value in gateway.cookies.items() if key != "csrf_token"}
    response_headers: dict[str, str] = {"X-CSRF-Token": gateway.cookies["csrf_token"]}
    question = (
        f"Call knowledge_search once with knowledge_base='{knowledge_base}' and "
        "query 'Gate 7 isolated matrix citation marker'. Return the exact source "
        "sentence and citation."
    )
    frames: list[str] = []
    with gateway.client.stream(
        "POST",
        f"/api/threads/{thread}/runs/stream",
        cookies=cookies,
        headers=response_headers,
        json={
            "assistant_id": agent_id,
            "input": {"messages": [{"role": "user", "content": question}]},
        },
        timeout=300,
    ) as response:
        response.raise_for_status()
        location = response.headers.get("content-location", "")
        match = re.search(r"/runs/([^/?]+)$", location)
        if match is None:
            raise ValueError("stream response omitted the canonical run location")
        run_id = match.group(1)
        for line in response.iter_lines():
            if line.startswith("event: "):
                frames.append(line.removeprefix("event: "))
    _validate_stream_event_types(frames)
    evidence = gateway.request("GET", f"/api/runs/{run_id}/evidence")
    _require_archived_receipts(evidence, "streamed Agent run")
    result = {
        "candidate_commit": candidate,
        "scenario": "streaming",
        "real_execution": True,
        "result": "passed",
        "observed_steps": [
            "created a real Gateway thread and Agent run using the SSE stream endpoint",
            "consumed metadata, intermediate stream events, and the terminal end event",
            "read persisted archived retrieval receipts for the streamed run",
        ],
        "thread_id": thread,
        "run_id": run_id,
        "stream_event_types": frames,
        "receipts": evidence["receipts"],
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
