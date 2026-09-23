#!/usr/bin/env python3
"""Verify provider output truncation in a real streamed Gateway run."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.acceptance.run_gate7_matrix import Gateway, _require_archived_receipts


def _validate_truncated_output(transcript: str) -> None:
    if "(response truncated)" not in transcript:
        raise ValueError("stream did not contain the provider output truncation marker")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--knowledge-base", required=True)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    original = args.config.read_bytes()
    config = yaml.safe_load(original)
    knowledge = next(item for item in config["tools"] if item.get("name") == "knowledge_search")
    old_chunk, old_total = knowledge.get("max_chars_per_chunk"), knowledge.get("max_total_chars")
    knowledge["max_chars_per_chunk"] = 40
    knowledge["max_total_chars"] = 100
    try:
        args.config.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
        gateway = Gateway(args.gateway, "user@test.com")
        revisions = gateway.request("GET", f"/api/resources/{args.knowledge_base}/knowledge-revisions")["items"]
        revision = max((item for item in revisions if item.get("status") == "published"), key=lambda item: item["revision_no"])
        agent_name = f"gate7-truncated-{uuid4().hex[:12]}"
        agent_id = gateway.request("POST", "/api/resources", json={"type": "agent", "slug": agent_name, "display_name": agent_name, "storage_kind": "filesystem"})["id"]
        gateway.request("PUT", f"/api/resources/{agent_id}/agent-draft", json={
            "config": {"name": agent_name, "description": "Gate 7 real truncation scenario", "skills": [], "tool_groups": ["knowledge"]},
            "soul": "You must call knowledge_search exactly once for the exact knowledge_base and query given by the user. Do not answer from memory. Do not call other tools. Return the complete tool output verbatim, including any truncation marker.",
            "knowledge_dependencies": [{"resource_id": args.knowledge_base, "dependency_mode": "pinned", "revision_id": revision["id"], "required": True, "purpose": "Gate 7 truncation acceptance"}],
            "expected_revision": 0,
        })
        gateway.request("POST", f"/api/resources/{agent_id}/publish", json={"expected_draft_revision": 1})
        thread = gateway.request("POST", "/api/threads", json={})["thread_id"]
        cookies = {key: value for key, value in gateway.cookies.items() if key != "csrf_token"}
        headers = {"X-CSRF-Token": gateway.cookies["csrf_token"]}
        query = f"Call knowledge_search once for '{args.knowledge_base}' using query 'Gate 7 isolated matrix citation marker'. Return the full source."
        frames: list[str] = []
        transcript: list[str] = []
        with gateway.client.stream(
            "POST", f"/api/threads/{thread}/runs/stream", cookies=cookies,
            headers=headers,
            json={"assistant_id": agent_id, "input": {"messages": [{"role": "user", "content": query}]}},
            timeout=300,
        ) as response:
            response.raise_for_status()
            match = re.search(r"/runs/([^/?]+)$", response.headers.get("content-location", ""))
            if match is None:
                raise ValueError("stream response omitted the canonical run location")
            run_id = match.group(1)
            for line in response.iter_lines():
                transcript.append(line)
                if line.startswith("event: "):
                    frames.append(line.removeprefix("event: "))
        _validate_truncated_output("\n".join(transcript))
        evidence = gateway.request("GET", f"/api/runs/{run_id}/evidence")
        _require_archived_receipts(evidence, "truncated Agent run")
        result = {
            "candidate_commit": os.environ["GATE7_CANDIDATE_COMMIT"],
            "scenario": "truncated", "real_execution": True, "result": "passed",
            "observed_steps": ["published a scenario-specific real Agent pinned to the current published revision", "lowered isolated formatter limits", "observed the real truncation marker in Gateway SSE", "verified persisted archived retrieval receipts"],
            "thread_id": thread, "run_id": run_id, "probe_agent_id": agent_id, "stream_event_types": frames,
            "receipts": evidence["receipts"], "recorded_at": datetime.now(UTC).isoformat(),
        }
        output = Path(os.environ["GATE7_EVIDENCE_PATH"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    finally:
        if old_chunk is None:
            knowledge.pop("max_chars_per_chunk", None)
        else:
            knowledge["max_chars_per_chunk"] = old_chunk
        if old_total is None:
            knowledge.pop("max_total_chars", None)
        else:
            knowledge["max_total_chars"] = old_total
        args.config.write_bytes(original)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
