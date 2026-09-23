#!/usr/bin/env python3
"""Run a real Agent using both the isolated KB and live web search."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.acceptance.run_gate7_matrix import Gateway


def _validate_mixed_sources(run: dict) -> None:
    if "knowledge_search" not in run.get("tool_names", []) or "web_search" not in run.get("tool_names", []):
        raise ValueError("mixed_web requires real knowledge_search and web_search tool calls")
    receipts = run.get("retrieval_receipts", [])
    if not any(item.get("archive_status") == "archived" and item.get("items") for item in receipts):
        raise ValueError("mixed_web requires an archived KB receipt with source items")
    if not re.search(r"https?://[^\s)\]]+", run.get("assistant_text", "")):
        raise ValueError("mixed_web assistant response omitted a web URL citation")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--knowledge-base", required=True)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    original = args.config.read_bytes()
    config = yaml.safe_load(original)
    web = {"name": "web_search", "group": "web", "use": "deerflow.community.ddg_search.tools:web_search_tool", "max_results": 5}
    config["tools"] = [item for item in config.get("tools", []) if item.get("name") != "web_search"] + [web]
    try:
        args.config.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
        gateway = Gateway(args.gateway, "user@test.com")
        revisions = gateway.request("GET", f"/api/resources/{args.knowledge_base}/knowledge-revisions")["items"]
        revision = max((item for item in revisions if item.get("status") == "published"), key=lambda item: item["revision_no"])
        slug = f"gate7-mixed-{uuid4().hex[:12]}"
        agent_id = gateway.request("POST", "/api/resources", json={"type": "agent", "slug": slug, "display_name": slug, "storage_kind": "filesystem"})["id"]
        gateway.request("PUT", f"/api/resources/{agent_id}/agent-draft", json={
            "config": {"name": slug, "description": "Gate 7 real mixed KB and web search", "skills": [], "tool_groups": ["knowledge", "web"]},
            "soul": "For the user's request, call knowledge_search exactly once and web_search exactly once. Do not skip either tool. Give separate source attribution: cite the KB source using the exact returned evidence citation and cite the web result using its actual URL.",
            "knowledge_dependencies": [{"resource_id": args.knowledge_base, "dependency_mode": "pinned", "revision_id": revision["id"], "required": True, "purpose": "Gate 7 mixed web scenario"}],
            "expected_revision": 0,
        })
        gateway.request("POST", f"/api/resources/{agent_id}/publish", json={"expected_draft_revision": 1})
        thread = gateway.request("POST", "/api/threads", json={})["thread_id"]
        run_id = gateway.request("POST", f"/api/threads/{thread}/runs", json={"assistant_id": agent_id, "input": {"messages": [{"role": "user", "content": f"Find the exact Gate 7 marker in KB '{args.knowledge_base}'. Also search the web for Python official documentation. Report both findings with their distinct citations."}]}})["run_id"]
        deadline = time.monotonic() + 420
        while True:
            state = gateway.request("GET", f"/api/threads/{thread}/runs/{run_id}")
            if state.get("status") in {"completed", "success", "failed", "error"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"mixed-source run {run_id} did not finish")
            time.sleep(3)
        evidence = gateway.request("GET", f"/api/runs/{run_id}/evidence")
        history = gateway.request("POST", f"/api/threads/{thread}/history", json={"limit": 10})
        messages = next((entry.get("values", {}).get("messages", []) for entry in history if entry.get("values", {}).get("messages")), [])
        names: set[str] = set()
        assistant_text: list[str] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            if message.get("type") == "tool" and message.get("name"):
                names.add(str(message["name"]))
            for call in message.get("tool_calls", []) if isinstance(message.get("tool_calls"), list) else []:
                name = call.get("name") or call.get("function", {}).get("name") if isinstance(call, dict) else None
                if name:
                    names.add(str(name))
            if message.get("type") == "ai" and isinstance(message.get("content"), str):
                assistant_text.append(message["content"])
        run = {"thread_id": thread, "run_id": run_id, "status": state.get("status"), "tool_names": sorted(names), "retrieval_receipts": evidence.get("receipts", []), "assistant_text": "\n".join(assistant_text)}
        if run["status"] not in {"completed", "success"}:
            raise ValueError(f"mixed-source Agent run ended as {run['status']}")
        _validate_mixed_sources(run)
        artifact = {"candidate_commit": os.environ["GATE7_CANDIDATE_COMMIT"], "scenario": "mixed_web", "real_execution": True, "result": "passed", "observed_steps": ["published a real Agent with knowledge and web tool groups", "observed both tool calls in persisted thread history", "verified archived KB receipt and web URL attribution in assistant response"], "pinned_revision_id": revision["id"], "run": run, "recorded_at": datetime.now(UTC).isoformat()}
        output = Path(os.environ["GATE7_EVIDENCE_PATH"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    finally:
        args.config.write_bytes(original)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
